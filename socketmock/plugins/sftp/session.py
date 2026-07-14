from __future__ import annotations

import asyncio
import itertools
import logging
import os
import socket
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import paramiko
import paramiko.sftp as paramiko_sftp
import paramiko.util

from ..base import ProtocolSession, ProtocolStubStore
from . import codec as sftp_codec


@dataclass
class OpenHandle:
    path: Path
    fileobj: Any
    kind: str = "file"
    dir_entries: list[tuple[str, str, bytes]] | None = None
    dir_index: int = 0


class _ParamikoSFTPHandle(paramiko.SFTPHandle):
    def __init__(self, path: Path, fileobj: Any) -> None:
        super().__init__()
        self._path = path
        self._fileobj = fileobj

    def read(self, offset: int, length: int) -> bytes:
        self._fileobj.seek(offset)
        return self._fileobj.read(length)

    def write(self, offset: int, data: Any) -> int:
        self._fileobj.seek(offset)
        self._fileobj.write(data)
        self._fileobj.flush()
        return paramiko_sftp.SFTP_OK

    def stat(self) -> paramiko.SFTPAttributes:
        return paramiko.SFTPAttributes.from_stat(self._path.stat())

    def chattr(self, attr: paramiko.SFTPAttributes) -> int:
        if attr.st_mode is not None:
            os.chmod(self._path, attr.st_mode)
        if attr.st_mtime is not None:
            os.utime(self._path, (attr.st_mtime, attr.st_mtime))
        return paramiko_sftp.SFTP_OK

    def close(self) -> None:
        self._fileobj.close()


class _ParamikoSFTPServer(paramiko.SFTPServerInterface):
    def __init__(self, server: paramiko.ServerInterface, session: SFTPSession) -> None:
        super().__init__(server)
        self._session = session

    def _resolve(self, path: str) -> Path:
        return self._session._resolve(path)

    def list_folder(self, path: str) -> list[paramiko.SFTPAttributes] | int:
        target = self._resolve(path)
        if not target.exists() or not target.is_dir():
            return paramiko_sftp.SFTP_NO_SUCH_FILE
        return [
            paramiko.SFTPAttributes.from_stat(child.stat())
            for child in sorted(target.iterdir(), key=lambda item: item.name)
        ]

    def stat(self, path: str) -> paramiko.SFTPAttributes:
        target = self._resolve(path)
        if not target.exists():
            raise FileNotFoundError(path)
        return paramiko.SFTPAttributes.from_stat(target.stat())

    def lstat(self, path: str) -> paramiko.SFTPAttributes:
        return self.stat(path)

    def open(self, path: str, flags: int, attr: paramiko.SFTPAttributes) -> _ParamikoSFTPHandle:
        target = self._resolve(path)
        if flags & os.O_CREAT:
            target.parent.mkdir(parents=True, exist_ok=True)
        mode = "rb"
        if flags & (os.O_WRONLY | os.O_RDWR):
            mode = "r+b"
            if flags & os.O_TRUNC:
                mode = "w+b"
            elif flags & os.O_APPEND:
                mode = "a+b"
        elif flags & os.O_RDONLY:
            mode = "rb"
        elif flags & os.O_APPEND:
            mode = "ab"
        fileobj = open(target, mode)
        if flags & os.O_CREAT and not target.exists():
            fileobj.close()
            fileobj = open(target, mode)
        return _ParamikoSFTPHandle(target, fileobj)

    def remove(self, path: str) -> int:
        target = self._resolve(path)
        if not target.exists():
            return paramiko_sftp.SFTP_NO_SUCH_FILE
        target.unlink()
        return paramiko_sftp.SFTP_OK

    def mkdir(self, path: str, attr: paramiko.SFTPAttributes) -> int:
        target = self._resolve(path)
        target.mkdir(parents=True, exist_ok=True)
        return paramiko_sftp.SFTP_OK

    def rmdir(self, path: str) -> int:
        target = self._resolve(path)
        if not target.exists() or not target.is_dir():
            return paramiko_sftp.SFTP_NO_SUCH_FILE
        target.rmdir()
        return paramiko_sftp.SFTP_OK

    def rename(self, oldpath: str, newpath: str) -> int:
        source = self._resolve(oldpath)
        destination = self._resolve(newpath)
        if not source.exists():
            return paramiko_sftp.SFTP_NO_SUCH_FILE
        source.rename(destination)
        return paramiko_sftp.SFTP_OK

    def chattr(self, path: str, attr: paramiko.SFTPAttributes) -> int:
        target = self._resolve(path)
        if not target.exists():
            return paramiko_sftp.SFTP_NO_SUCH_FILE
        if attr.st_mode is not None:
            os.chmod(target, attr.st_mode)
        if attr.st_mtime is not None:
            os.utime(target, (attr.st_mtime, attr.st_mtime))
        return paramiko_sftp.SFTP_OK


class _ParamikoServerInterface(paramiko.ServerInterface):
    def __init__(self, session: SFTPSession) -> None:
        self._session = session

    def check_auth_password(self, username: str, password: str) -> int:
        return 0

    def get_allowed_auths(self, username: str) -> str:
        return "password"

    def check_channel_request(self, kind: str, chanid: int) -> int:
        if kind == "session":
            return 0
        return 1

    def check_channel_subsystem_request(self, channel: paramiko.Channel, name: str) -> bool:
        return super().check_channel_subsystem_request(channel, name)


class SFTPSession(ProtocolSession):
    _id_counter = itertools.count(1)

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.store = store
        self.config = config or {}
        self.session_id = f"sftp-session-{next(self._id_counter)}"
        self.peer = writer.get_extra_info("peername")
        self.root = Path(self.config.get("root", tempfile.gettempdir()))
        self.root.mkdir(parents=True, exist_ok=True)
        self._handles: dict[bytes, OpenHandle] = {}
        self._handle_counter = 0

    async def run(self) -> None:
        self.store.register_session(
            self.session_id,
            {"sessionId": self.session_id, "peer": self.peer, "bound": True, "handle": self},
        )
        try:
            print("RUN_START", flush=True)
            socket_obj = None
            writer_transport = getattr(self.writer, "get_extra_info", None)
            if callable(writer_transport):
                try:
                    socket_obj = writer_transport("socket")
                except Exception:
                    socket_obj = None
            if socket_obj is None:
                transport = getattr(self.writer, "transport", None)
                if transport is not None:
                    transport_get_extra_info = getattr(transport, "get_extra_info", None)
                    if callable(transport_get_extra_info):
                        try:
                            socket_obj = transport_get_extra_info("socket")
                        except Exception:
                            socket_obj = None
            if socket_obj is not None:
                transport_obj = getattr(self.writer, "transport", None)
                if hasattr(socket_obj, "dup"):
                    socket_obj = socket_obj.dup()
                if transport_obj is not None and hasattr(transport_obj, "pause_reading"):
                    transport_obj.pause_reading()
                if transport_obj is not None and hasattr(transport_obj, "close"):
                    transport_obj.close()
                try:
                    await asyncio.to_thread(self._run_paramiko_server, socket_obj)
                except Exception:
                    raise
            else:
                buf = bytearray()
                try:
                    while True:
                        chunk = await self.reader.read(4096)
                        if not chunk:
                            break
                        buf.extend(chunk)
                        while True:
                            packet = sftp_codec.decode_packet(bytes(buf))
                            if packet is None:
                                break
                            packet_type, payload = packet
                            del buf[: 4 + len(payload) + 1]
                            await self._dispatch_packet(packet_type, payload)
                except (ConnectionResetError, asyncio.IncompleteReadError):
                    pass
        finally:
            self.store.unregister_session(self.session_id)
            for handle in self._handles.values():
                close = getattr(handle.fileobj, "close", None)
                if callable(close):
                    close()
            self.writer.close()

    def _run_paramiko_server(self, socket_obj: Any) -> None:
        logging.basicConfig(level=logging.DEBUG)
        paramiko.util.get_logger("paramiko").setLevel(logging.DEBUG)
        print("RUN_PARAMIKO_START", flush=True)
        if hasattr(socket_obj, "detach"):
            fd = socket_obj.detach()
            socket_obj = socket.socket(fileno=fd)
        socket_obj.setblocking(True)
        socket_obj.settimeout(None)
        host_key = paramiko.RSAKey.generate(2048)
        transport = paramiko.Transport(socket_obj)
        print("TRANSPORT_CREATED", flush=True)
        transport.add_server_key(host_key)
        transport.set_subsystem_handler(
            "sftp",
            paramiko.SFTPServer,
            _ParamikoSFTPServer,
            self,
        )
        print("BEFORE_START_SERVER", flush=True)
        transport.start_server(server=_ParamikoServerInterface(self))
        print("AFTER_START_SERVER", flush=True)
        while transport.is_active():
            channel = transport.accept(1)
            if channel is not None:
                print("CHANNEL", channel, flush=True)
                print("CHANNEL_OPEN", channel.get_name(), channel.closed, flush=True)
                channel.set_name("sftp")
        if transport.is_active():
            transport.close()
        print("RUN_PARAMIKO_DONE", flush=True)

    async def _dispatch_packet(self, packet_type: int, payload: bytes) -> None:
        if packet_type == sftp_codec.SSH_FXP_INIT:
            await self._send_version(payload)
            return

        request_id, offset = sftp_codec.unpack_u32(payload)
        if packet_type == sftp_codec.SSH_FXP_OPEN:
            await self._handle_open(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_CLOSE:
            await self._handle_close(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_READ:
            await self._handle_read(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_WRITE:
            await self._handle_write(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_OPENDIR:
            await self._handle_opendir(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_READDIR:
            await self._handle_readdir(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_STAT:
            await self._handle_stat(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_LSTAT:
            await self._handle_lstat(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_FSTAT:
            await self._handle_fstat(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_SETSTAT:
            await self._handle_setstat(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_FSETSTAT:
            await self._handle_fsetstat(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_REMOVE:
            await self._handle_remove(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_RENAME:
            await self._handle_rename(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_MKDIR:
            await self._handle_mkdir(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_RMDIR:
            await self._handle_rmdir(request_id, payload[offset:])
        elif packet_type == sftp_codec.SSH_FXP_REALPATH:
            await self._handle_realpath(request_id, payload[offset:])
        else:
            await self._send_status(
                request_id,
                sftp_codec.SSH_FX_OP_UNSUPPORTED,
                "unsupported request",
            )

    async def _send_version(self, payload: bytes) -> None:
        version, _ = sftp_codec.unpack_u32(payload)
        response = sftp_codec.pack_u32(version) + sftp_codec.pack_u32(0)
        await self._send_packet(sftp_codec.SSH_FXP_VERSION, response)

    async def _handle_open(self, request_id: int, payload: bytes) -> None:
        path, offset = sftp_codec.unpack_string(payload)
        pflags, offset = sftp_codec.unpack_u32(payload, offset)
        attrs, _ = sftp_codec.decode_attrs(payload, offset)

        request = {
            "operation": "open",
            "requestId": request_id,
            "path": path,
            "pflags": pflags,
            "attrs": attrs,
        }
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        target = self._resolve(path)
        if not self._is_allowed(target, pflags):
            await self._send_status(
                request_id,
                sftp_codec.SSH_FX_PERMISSION_DENIED,
                "permission denied",
            )
            return
        if pflags & sftp_codec.SSH_FXF_CREAT:
            target.parent.mkdir(parents=True, exist_ok=True)
        flags = self._to_os_flags(pflags)
        try:
            fileobj = open(target, flags)
        except FileNotFoundError:
            await self._send_status(request_id, sftp_codec.SSH_FX_NO_SUCH_FILE, "not found")
            return
        handle_id = f"h{self._handle_counter}".encode("ascii")
        self._handle_counter += 1
        self._handles[handle_id] = OpenHandle(path=target, fileobj=fileobj)
        await self._send_packet(
            sftp_codec.SSH_FXP_HANDLE,
            sftp_codec.encode_handle(request_id, handle_id),
        )

    async def _handle_close(self, request_id: int, payload: bytes) -> None:
        handle, _ = sftp_codec.unpack_bytes(payload)

        request = {"operation": "close", "requestId": request_id, "handle": handle}
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        entry = self._handles.pop(handle, None)
        if entry is None:
            await self._send_status(request_id, sftp_codec.SSH_FX_FAILURE, "unknown handle")
            return
        close = getattr(entry.fileobj, "close", None)
        if callable(close):
            close()
        await self._send_status(request_id, sftp_codec.SSH_FX_OK)

    async def _handle_read(self, request_id: int, payload: bytes) -> None:
        handle, offset = sftp_codec.unpack_bytes(payload)
        offset_value, offset = sftp_codec.unpack_u64(payload, offset)
        length, _ = sftp_codec.unpack_u32(payload, offset)

        request = {
            "operation": "read",
            "requestId": request_id,
            "handle": handle,
            "offset": offset_value,
            "length": length,
        }
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        entry = self._handles.get(handle)
        if entry is None:
            await self._send_status(request_id, sftp_codec.SSH_FX_FAILURE, "unknown handle")
            return
        entry.fileobj.seek(offset_value)
        data = entry.fileobj.read(length)
        await self._send_packet(sftp_codec.SSH_FXP_DATA, sftp_codec.encode_data(request_id, data))

    async def _handle_write(self, request_id: int, payload: bytes) -> None:
        handle, offset = sftp_codec.unpack_bytes(payload)
        offset_value, offset = sftp_codec.unpack_u64(payload, offset)
        data, _ = sftp_codec.unpack_bytes(payload, offset)

        request = {
            "operation": "write",
            "requestId": request_id,
            "handle": handle,
            "offset": offset_value,
            "data": data,
        }
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        entry = self._handles.get(handle)
        if entry is None:
            await self._send_status(request_id, sftp_codec.SSH_FX_FAILURE, "unknown handle")
            return
        entry.fileobj.seek(offset_value)
        entry.fileobj.write(data)
        entry.fileobj.flush()
        await self._send_status(request_id, sftp_codec.SSH_FX_OK)

    async def _handle_opendir(self, request_id: int, payload: bytes) -> None:
        path, _ = sftp_codec.unpack_string(payload)
        request = {"operation": "opendir", "requestId": request_id, "path": path}
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        target = self._resolve(path)
        if not target.exists() or not target.is_dir():
            await self._send_status(
                request_id,
                sftp_codec.SSH_FX_NO_SUCH_FILE,
                "directory not found",
            )
            return
        handle_id = f"d{self._handle_counter}".encode("ascii")
        self._handle_counter += 1
        self._handles[handle_id] = OpenHandle(
            path=target,
            fileobj=iter(()),
            kind="dir",
            dir_entries=self._build_directory_entries(target),
        )
        await self._send_packet(
            sftp_codec.SSH_FXP_HANDLE, sftp_codec.encode_handle(request_id, handle_id)
        )

    async def _handle_readdir(self, request_id: int, payload: bytes) -> None:
        handle, _ = sftp_codec.unpack_bytes(payload)
        request = {"operation": "readdir", "requestId": request_id, "handle": handle}
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        entry = self._handles.get(handle)
        if entry is None:
            await self._send_status(request_id, sftp_codec.SSH_FX_FAILURE, "unknown handle")
            return
        if entry.kind != "dir":
            await self._send_status(request_id, sftp_codec.SSH_FX_FAILURE, "not a directory")
            return
        if entry.dir_entries is None:
            entry.dir_entries = self._build_directory_entries(entry.path)
        if entry.dir_index >= len(entry.dir_entries):
            await self._send_status(request_id, sftp_codec.SSH_FX_EOF)
            return
        chunk = entry.dir_entries[entry.dir_index : entry.dir_index + 1]
        entry.dir_index += 1
        await self._send_packet(sftp_codec.SSH_FXP_NAME, sftp_codec.encode_name(request_id, chunk))

    async def _handle_stat(self, request_id: int, payload: bytes) -> None:
        path, _ = sftp_codec.unpack_string(payload)
        request = {"operation": "stat", "requestId": request_id, "path": path}
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        target = self._resolve(path)
        if not target.exists():
            await self._send_status(request_id, sftp_codec.SSH_FX_NO_SUCH_FILE, "not found")
            return
        await self._send_packet(
            sftp_codec.SSH_FXP_ATTRS, self._encode_attrs_response(request_id, target)
        )

    async def _handle_lstat(self, request_id: int, payload: bytes) -> None:
        await self._handle_stat(request_id, payload)

    async def _handle_setstat(self, request_id: int, payload: bytes) -> None:
        path, offset = sftp_codec.unpack_string(payload)
        attrs, _ = sftp_codec.decode_attrs(payload, offset)
        request = {"operation": "setstat", "requestId": request_id, "path": path, "attrs": attrs}
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        target = self._resolve(path)
        if not target.exists():
            await self._send_status(request_id, sftp_codec.SSH_FX_NO_SUCH_FILE, "not found")
            return
        self._apply_attrs(target, attrs)
        await self._send_status(request_id, sftp_codec.SSH_FX_OK)

    async def _handle_remove(self, request_id: int, payload: bytes) -> None:
        path, _ = sftp_codec.unpack_string(payload)
        request = {"operation": "remove", "requestId": request_id, "path": path}
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        target = self._resolve(path)
        if target.exists():
            target.unlink()
            await self._send_status(request_id, sftp_codec.SSH_FX_OK)
            return
        await self._send_status(request_id, sftp_codec.SSH_FX_NO_SUCH_FILE, "not found")

    async def _handle_fstat(self, request_id: int, payload: bytes) -> None:
        handle, _ = sftp_codec.unpack_bytes(payload)
        request = {"operation": "fstat", "requestId": request_id, "handle": handle}
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        entry = self._handles.get(handle)
        if entry is None:
            await self._send_status(request_id, sftp_codec.SSH_FX_FAILURE, "unknown handle")
            return
        await self._send_packet(
            sftp_codec.SSH_FXP_ATTRS, self._encode_attrs_response(request_id, entry.path)
        )

    async def _handle_fsetstat(self, request_id: int, payload: bytes) -> None:
        handle, offset = sftp_codec.unpack_bytes(payload)
        attrs, _ = sftp_codec.decode_attrs(payload, offset)
        request = {
            "operation": "fsetstat",
            "requestId": request_id,
            "handle": handle,
            "attrs": attrs,
        }
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        entry = self._handles.get(handle)
        if entry is None:
            await self._send_status(request_id, sftp_codec.SSH_FX_FAILURE, "unknown handle")
            return
        self._apply_attrs(entry.path, attrs)
        await self._send_status(request_id, sftp_codec.SSH_FX_OK)

    async def _handle_rename(self, request_id: int, payload: bytes) -> None:
        old_path, offset = sftp_codec.unpack_string(payload)
        new_path, offset = sftp_codec.unpack_string(payload, offset)
        flags, _ = sftp_codec.unpack_u32(payload, offset)
        request = {
            "operation": "rename",
            "requestId": request_id,
            "oldPath": old_path,
            "newPath": new_path,
            "flags": flags,
        }
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        source = self._resolve(old_path)
        destination = self._resolve(new_path)
        if not source.exists():
            await self._send_status(request_id, sftp_codec.SSH_FX_NO_SUCH_FILE, "not found")
            return
        if destination.exists() and not flags:
            await self._send_status(request_id, sftp_codec.SSH_FX_FAILURE, "destination exists")
            return
        try:
            if destination.exists():
                if destination.is_dir() and not source.is_dir():
                    destination.rmdir()
                else:
                    destination.unlink()
            source.replace(destination)
        except OSError as exc:
            await self._send_status(request_id, sftp_codec.SSH_FX_FAILURE, str(exc))
            return
        await self._send_status(request_id, sftp_codec.SSH_FX_OK)

    async def _handle_mkdir(self, request_id: int, payload: bytes) -> None:
        path, _ = sftp_codec.unpack_string(payload)
        request = {"operation": "mkdir", "requestId": request_id, "path": path}
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        target = self._resolve(path)
        target.mkdir(parents=True, exist_ok=True)
        await self._send_status(request_id, sftp_codec.SSH_FX_OK)

    async def _handle_rmdir(self, request_id: int, payload: bytes) -> None:
        path, _ = sftp_codec.unpack_string(payload)
        request = {"operation": "rmdir", "requestId": request_id, "path": path}
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        target = self._resolve(path)
        if target.exists() and target.is_dir():
            target.rmdir()
            await self._send_status(request_id, sftp_codec.SSH_FX_OK)
            return
        await self._send_status(request_id, sftp_codec.SSH_FX_NO_SUCH_FILE, "not found")

    async def _handle_realpath(self, request_id: int, payload: bytes) -> None:
        path, _ = sftp_codec.unpack_string(payload)
        request = {"operation": "realpath", "requestId": request_id, "path": path}
        stub = self._find_stub(request)
        if stub is not None:
            self._log_request(request, stub)
            if await self._maybe_respond_with_stub(request_id, stub):
                return

        target = self._resolve(path)
        await self._send_packet(
            sftp_codec.SSH_FXP_NAME,
            sftp_codec.encode_name(
                request_id, [(str(target), str(target), sftp_codec.encode_attrs(str(target)))]
            ),
        )

    async def _send_status(self, request_id: int, code: int, message: str = "") -> None:
        await self._send_packet(
            sftp_codec.SSH_FXP_STATUS, sftp_codec.encode_status(request_id, code, message)
        )

    async def _send_packet(self, packet_type: int, payload: bytes) -> None:
        self.writer.write(sftp_codec.encode_packet(packet_type, payload))
        await self.writer.drain()

    def _encode_attrs_response(self, request_id: int, target: Path) -> bytes:
        return sftp_codec.pack_u32(request_id) + sftp_codec.encode_attrs(str(target))

    def _build_directory_entries(self, directory: Path) -> list[tuple[str, str, bytes]]:
        return [
            (child.name, child.name, sftp_codec.encode_attrs(str(child)))
            for child in sorted(directory.iterdir(), key=lambda item: item.name)
        ]

    def _apply_attrs(self, target: Path, attrs: dict[str, Any]) -> None:
        if "permissions" in attrs:
            os.chmod(target, attrs["permissions"])
        if "mtime" in attrs:
            os.utime(target, (attrs["mtime"], attrs["mtime"]))

    def _resolve(self, path: str) -> Path:
        target = Path(path)
        if not target.is_absolute():
            target = self.root / target
        else:
            target = Path(path)
        resolved = target.resolve(strict=False)
        try:
            resolved.relative_to(self.root.resolve(strict=False))
        except ValueError:
            resolved = self.root / target.name
        return resolved

    def _to_os_flags(self, pflags: int) -> str:
        if pflags & sftp_codec.SSH_FXF_APPEND:
            return "ab"
        if pflags & sftp_codec.SSH_FXF_WRITE:
            if pflags & sftp_codec.SSH_FXF_TRUNC:
                return "wb"
            if pflags & sftp_codec.SSH_FXF_CREAT:
                return "w+b"
            return "r+b"
        if pflags & sftp_codec.SSH_FXF_CREAT:
            return "xb"
        return "rb"

    def _is_allowed(self, target: Path, pflags: int) -> bool:
        if pflags & sftp_codec.SSH_FXF_WRITE and not os.access(target.parent, os.W_OK):
            return False
        return True

    def _find_stub(self, request: dict[str, Any]) -> dict[str, Any] | None:
        stub = self.store.find_match(request)
        return stub.response if stub else None

    def _log_request(self, request: dict[str, Any], response: dict[str, Any] | None) -> None:
        self.store.log_request(
            {
                "sessionId": self.session_id,
                "direction": "in",
                "operation": request.get("operation"),
                "requestId": request.get("requestId"),
                "timestamp": time.time(),
                "request": request,
                "matchedResponse": response,
            }
        )

    async def _maybe_respond_with_stub(
        self, request_id: int, response: dict[str, Any] | None
    ) -> bool:
        if response is None:
            return False
        status_code = response.get("statusCode", sftp_codec.SSH_FX_OK)
        if status_code != sftp_codec.SSH_FX_OK:
            await self._send_status(request_id, status_code, str(response.get("message", "")))
            return True
        if "data" in response:
            await self._send_packet(
                sftp_codec.SSH_FXP_DATA,
                sftp_codec.encode_data(request_id, response["data"]),
            )
            return True
        return False
