import asyncio
from pathlib import Path
from typing import cast

from socketmock.plugins.sftp import codec as sftp_codec
from socketmock.plugins.sftp.session import SFTPSession
from socketmock.plugins.sftp.stubs import StubStore
from tests.plugins._helpers import FakeWriter


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
