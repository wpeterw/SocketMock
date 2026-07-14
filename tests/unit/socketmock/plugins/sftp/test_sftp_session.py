import asyncio
import os
from pathlib import Path
from typing import Any, cast

import paramiko

from socketmock.plugins.sftp import codec as sftp_codec
from socketmock.plugins.sftp.session import (
    SFTPSession,
    _ParamikoSFTPHandle,
    _ParamikoSFTPServer,
)
from socketmock.plugins.sftp.stubs import StubStore
from tests.unit.socketmock.plugins._helpers import FakeWriter


def test_sftp_session_handles_file_and_directory_ops(tmp_path: Path) -> None:
    async def run_test() -> None:
        data_path = tmp_path / "data.txt"
        data_path.write_text("hello", encoding="utf-8")
        nested_dir = tmp_path / "nested"
        nested_dir.mkdir()
        temp_file = tmp_path / "temp.txt"
        temp_file.write_text("x", encoding="utf-8")

        reader = asyncio.StreamReader()
        writer = FakeWriter()
        session = SFTPSession(
            reader, cast(asyncio.StreamWriter, writer), StubStore(), {"root": str(tmp_path)}
        )

        open_payload = (
            sftp_codec.pack_string("/data.txt")
            + sftp_codec.pack_u32(sftp_codec.SSH_FXF_READ | sftp_codec.SSH_FXF_WRITE)
            + sftp_codec.encode_attrs(str(data_path))
        )
        await session._handle_open(1, open_payload)
        file_handle = next(iter(session._handles))

        read_payload = (
            sftp_codec.pack_bytes(file_handle) + sftp_codec.pack_u64(0) + sftp_codec.pack_u32(5)
        )
        await session._handle_read(2, read_payload)

        write_payload = (
            sftp_codec.pack_bytes(file_handle)
            + sftp_codec.pack_u64(0)
            + sftp_codec.pack_bytes(b"!")
        )
        await session._handle_write(3, write_payload)

        await session._handle_stat(4, sftp_codec.pack_string("/data.txt"))
        await session._handle_lstat(5, sftp_codec.pack_string("/data.txt"))
        await session._handle_setstat(
            6,
            sftp_codec.pack_string("/data.txt") + sftp_codec.encode_attrs(str(data_path)),
        )

        await session._handle_opendir(7, sftp_codec.pack_string("/"))
        dir_handle = next(key for key in session._handles if key != file_handle)
        await session._handle_readdir(8, sftp_codec.pack_bytes(dir_handle))

        await session._handle_remove(9, sftp_codec.pack_string("/temp.txt"))
        await session._handle_mkdir(10, sftp_codec.pack_string("/created"))
        await session._handle_rmdir(11, sftp_codec.pack_string("/created"))
        await session._handle_realpath(12, sftp_codec.pack_string("/nested/../data.txt"))
        await session._handle_close(13, sftp_codec.pack_bytes(file_handle))
        await session._handle_close(14, sftp_codec.pack_bytes(b"missing"))
        await session._handle_stat(15, sftp_codec.pack_string("/missing"))
        await session._handle_remove(16, sftp_codec.pack_string("/missing"))
        await session._handle_rmdir(17, sftp_codec.pack_string("/missing"))
        await session._handle_opendir(18, sftp_codec.pack_string("/missing-dir"))

        assert writer.writes

    asyncio.run(run_test())


def test_sftp_session_uses_stubbed_responses(tmp_path: Path) -> None:
    async def run_test() -> None:
        store = StubStore()
        store.add(
            {
                "request": {"operation": "open", "path": "/blocked.txt"},
                "response": {"statusCode": 3, "message": "blocked"},
            }
        )
        writer = FakeWriter()
        session = SFTPSession(
            asyncio.StreamReader(),
            cast(asyncio.StreamWriter, writer),
            store,
            {"root": str(tmp_path)},
        )
        payload = (
            sftp_codec.pack_string("/blocked.txt")
            + sftp_codec.pack_u32(1)
            + sftp_codec.encode_attrs(str(tmp_path))
        )
        await session._handle_open(1, payload)
        assert writer.writes
        packet = sftp_codec.decode_packet(writer.writes[0])
        assert packet is not None
        packet_type, _ = packet
        assert packet_type == sftp_codec.SSH_FXP_STATUS

    asyncio.run(run_test())


def test_sftp_session_supports_rename_and_directory_eof(tmp_path: Path) -> None:
    async def run_test() -> None:
        source = tmp_path / "source.txt"
        source.write_text("hello", encoding="utf-8")
        nested_dir = tmp_path / "nested"
        nested_dir.mkdir()
        (nested_dir / "child.txt").write_text("x", encoding="utf-8")

        writer = FakeWriter()
        session = SFTPSession(
            asyncio.StreamReader(),
            cast(asyncio.StreamWriter, writer),
            StubStore(),
            {"root": str(tmp_path)},
        )

        await session._handle_rename(
            1,
            sftp_codec.pack_string("/source.txt")
            + sftp_codec.pack_string("/renamed.txt")
            + sftp_codec.pack_u32(0),
        )
        assert not source.exists()
        assert (tmp_path / "renamed.txt").exists()

        await session._handle_opendir(2, sftp_codec.pack_string("/nested"))
        dir_handle = next(key for key in session._handles if key != b"")
        await session._handle_readdir(3, sftp_codec.pack_bytes(dir_handle))
        await session._handle_readdir(4, sftp_codec.pack_bytes(dir_handle))
        last_packet = sftp_codec.decode_packet(writer.writes[-1])
        assert last_packet is not None
        packet_type, _ = last_packet
        assert packet_type == sftp_codec.SSH_FXP_STATUS

    asyncio.run(run_test())


def test_sftp_session_covers_additional_branches(tmp_path: Path) -> None:
    async def run_test() -> None:
        (tmp_path / "demo.txt").write_text("hello", encoding="utf-8")
        nested_dir = tmp_path / "nested"
        nested_dir.mkdir()
        (nested_dir / "child.txt").write_text("x", encoding="utf-8")

        writer = FakeWriter()
        store = StubStore()
        store.add(
            {
                "request": {"operation": "open", "path": {"equalTo": "/stubbed"}},
                "response": {"statusCode": 3, "message": "blocked"},
            }
        )
        store.add({"request": {"operation": "read"}, "response": {"data": b"stubbed-data"}})
        session = SFTPSession(
            asyncio.StreamReader(),
            cast(asyncio.StreamWriter, writer),
            store,
            {"root": str(tmp_path)},
        )

        blocked_payload = (
            sftp_codec.pack_string("/blocked.txt")
            + sftp_codec.pack_u32(sftp_codec.SSH_FXF_READ)
            + sftp_codec.encode_attrs(str(tmp_path))
        )
        original_is_allowed = session._is_allowed
        session._is_allowed = cast(Any, lambda _target, _pflags: False)
        await session._handle_open(1, blocked_payload)
        session._is_allowed = cast(Any, original_is_allowed)

        await session._handle_open(
            2,
            sftp_codec.pack_string("/stubbed")
            + sftp_codec.pack_u32(sftp_codec.SSH_FXF_READ)
            + sftp_codec.encode_attrs(str(tmp_path)),
        )
        await session._handle_read(
            3,
            sftp_codec.pack_bytes(b"ignored") + sftp_codec.pack_u64(0) + sftp_codec.pack_u32(5),
        )
        await session._maybe_respond_with_stub(4, None)
        await session._maybe_respond_with_stub(
            5, {"statusCode": sftp_codec.SSH_FX_FAILURE, "message": "boom"}
        )
        await session._maybe_respond_with_stub(6, {"data": b"payload"})

        assert session._to_os_flags(sftp_codec.SSH_FXF_APPEND) == "ab"
        assert session._to_os_flags(sftp_codec.SSH_FXF_WRITE | sftp_codec.SSH_FXF_TRUNC) == "wb"
        assert session._to_os_flags(sftp_codec.SSH_FXF_WRITE | sftp_codec.SSH_FXF_CREAT) == "w+b"
        assert session._to_os_flags(sftp_codec.SSH_FXF_CREAT) == "xb"
        assert session._to_os_flags(sftp_codec.SSH_FXF_READ) == "rb"
        assert session._resolve("demo.txt") == tmp_path / "demo.txt"
        assert session._resolve("/tmp/outside") == tmp_path / "outside"
        locked_dir = tmp_path / "locked"
        locked_dir.mkdir()
        locked_dir.chmod(0o500)
        assert not session._is_allowed(locked_dir / "file", sftp_codec.SSH_FXF_WRITE)

        await session._handle_open(
            7,
            sftp_codec.pack_string("/demo.txt")
            + sftp_codec.pack_u32(sftp_codec.SSH_FXF_READ)
            + sftp_codec.encode_attrs(str(tmp_path)),
        )
        read_handle = next(iter(session._handles))
        await session._handle_read(
            8,
            sftp_codec.pack_bytes(read_handle) + sftp_codec.pack_u64(0) + sftp_codec.pack_u32(5),
        )

        await session._handle_open(
            9,
            sftp_codec.pack_string("/writable.txt")
            + sftp_codec.pack_u32(sftp_codec.SSH_FXF_WRITE | sftp_codec.SSH_FXF_CREAT)
            + sftp_codec.encode_attrs(str(tmp_path)),
        )
        write_handle = next(key for key in session._handles if key != read_handle)
        await session._handle_write(
            10,
            sftp_codec.pack_bytes(write_handle)
            + sftp_codec.pack_u64(0)
            + sftp_codec.pack_bytes(b"X"),
        )
        await session._handle_fstat(11, sftp_codec.pack_bytes(write_handle))
        await session._handle_fsetstat(
            12,
            sftp_codec.pack_bytes(write_handle) + sftp_codec.encode_attrs(str(tmp_path)),
        )
        await session._handle_stat(13, sftp_codec.pack_string("/writable.txt"))
        await session._handle_lstat(14, sftp_codec.pack_string("/writable.txt"))
        await session._handle_setstat(
            15,
            sftp_codec.pack_string("/writable.txt") + sftp_codec.encode_attrs(str(tmp_path)),
        )
        await session._handle_opendir(16, sftp_codec.pack_string("/"))
        dir_handle = next(key for key in session._handles if key not in {read_handle, write_handle})
        await session._handle_readdir(17, sftp_codec.pack_bytes(dir_handle))
        await session._handle_readdir(18, sftp_codec.pack_bytes(dir_handle))
        await session._handle_remove(19, sftp_codec.pack_string("/writable.txt"))
        await session._handle_mkdir(20, sftp_codec.pack_string("/created"))
        await session._handle_rmdir(21, sftp_codec.pack_string("/created"))
        await session._handle_rename(
            22,
            sftp_codec.pack_string("/demo.txt")
            + sftp_codec.pack_string("/renamed.txt")
            + sftp_codec.pack_u32(0),
        )
        await session._handle_realpath(23, sftp_codec.pack_string("/nested/../renamed.txt"))
        await session._handle_close(24, sftp_codec.pack_bytes(write_handle))
        await session._handle_close(25, sftp_codec.pack_bytes(b"missing"))
        await session._handle_stat(26, sftp_codec.pack_string("/missing"))
        await session._handle_remove(27, sftp_codec.pack_string("/missing"))
        await session._handle_rmdir(28, sftp_codec.pack_string("/missing"))
        await session._handle_opendir(29, sftp_codec.pack_string("/missing-dir"))

        assert writer.writes
        assert session.store.journal()
        assert session._build_directory_entries(tmp_path)
        assert session._encode_attrs_response(1, tmp_path)
        session._apply_attrs(tmp_path / "renamed.txt", {"permissions": 0o600, "mtime": 42})
        assert (tmp_path / "renamed.txt").exists()

    asyncio.run(run_test())


def test_sftp_session_paramiko_helpers_cover_more_code(tmp_path: Path) -> None:
    async def run_test() -> None:
        sample_path = tmp_path / "sample.txt"
        sample_path.write_text("hello", encoding="utf-8")

        writer = FakeWriter()
        session = SFTPSession(
            asyncio.StreamReader(),
            cast(asyncio.StreamWriter, writer),
            StubStore(),
            {"root": str(tmp_path)},
        )
        fileobj = sample_path.open("r+b")
        handle = _ParamikoSFTPHandle(sample_path, fileobj)
        assert handle.read(0, 5) == b"hello"
        assert handle.write(0, b"!") == paramiko.sftp.SFTP_OK
        attrs = paramiko.SFTPAttributes.from_stat(sample_path.stat())
        attrs.st_mode = 0o600
        attrs.st_mtime = 1234
        assert handle.chattr(attrs) == paramiko.sftp.SFTP_OK
        handle.close()

        server = _ParamikoSFTPServer(server=cast(Any, None), session=session)
        assert server.list_folder("/")
        assert server.stat("/sample.txt") is not None
        assert server.lstat("/sample.txt") is not None
        (tmp_path / "created.txt").touch()
        file_handle = server.open(
            "/created.txt",
            os.O_CREAT | os.O_WRONLY,
            paramiko.SFTPAttributes(),
        )
        assert isinstance(file_handle, _ParamikoSFTPHandle)
        assert server.remove("/created.txt") == paramiko.sftp.SFTP_OK
        assert server.mkdir("/nested", paramiko.SFTPAttributes()) == paramiko.sftp.SFTP_OK
        assert server.rmdir("/nested") == paramiko.sftp.SFTP_OK
        assert server.rename("/sample.txt", "/renamed.txt") == paramiko.sftp.SFTP_OK
        assert server.chattr("/renamed.txt", attrs) == paramiko.sftp.SFTP_OK

    asyncio.run(run_test())


def test_sftp_session_run_processes_packets(tmp_path: Path) -> None:
    async def run_test() -> None:
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        session = SFTPSession(
            reader, cast(asyncio.StreamWriter, writer), StubStore(), {"root": str(tmp_path)}
        )
        reader.feed_data(sftp_codec.encode_packet(sftp_codec.SSH_FXP_INIT, sftp_codec.pack_u32(3)))
        reader.feed_eof()
        await session.run()
        assert writer.closed is True

    asyncio.run(run_test())
