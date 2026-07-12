from __future__ import annotations

import os
import stat
import struct
import time
from typing import Any

SSH_FXP_INIT = 1
SSH_FXP_VERSION = 2
SSH_FXP_OPEN = 3
SSH_FXP_CLOSE = 4
SSH_FXP_READ = 5
SSH_FXP_WRITE = 6
SSH_FXP_LSTAT = 7
SSH_FXP_FSTAT = 8
SSH_FXP_SETSTAT = 9
SSH_FXP_FSETSTAT = 10
SSH_FXP_OPENDIR = 11
SSH_FXP_READDIR = 12
SSH_FXP_REMOVE = 13
SSH_FXP_MKDIR = 14
SSH_FXP_RMDIR = 15
SSH_FXP_REALPATH = 16
SSH_FXP_STAT = 17
SSH_FXP_RENAME = 18
SSH_FXP_READLINK = 19
SSH_FXP_SYMLINK = 20

SSH_FXP_STATUS = 101
SSH_FXP_HANDLE = 102
SSH_FXP_DATA = 103
SSH_FXP_NAME = 104
SSH_FXP_ATTRS = 105

SSH_FX_OK = 0
SSH_FX_EOF = 1
SSH_FX_NO_SUCH_FILE = 2
SSH_FX_PERMISSION_DENIED = 3
SSH_FX_FAILURE = 4
SSH_FX_BAD_MESSAGE = 5
SSH_FX_NO_CONNECTION = 6
SSH_FX_CONNECTION_LOST = 7
SSH_FX_OP_UNSUPPORTED = 8

SSH_FXF_READ = 0x00000001
SSH_FXF_WRITE = 0x00000002
SSH_FXF_APPEND = 0x00000004
SSH_FXF_CREAT = 0x00000008
SSH_FXF_TRUNC = 0x00000010
SSH_FXF_EXCL = 0x00000020

SSH_FILEXFER_ATTR_SIZE = 0x00000001
SSH_FILEXFER_ATTR_UIDGID = 0x00000002
SSH_FILEXFER_ATTR_PERMISSIONS = 0x00000004
SSH_FILEXFER_ATTR_ACMODTIME = 0x00000008
SSH_FILEXFER_ATTR_EXTENDED = 0x80000000


def encode_packet(packet_type: int, payload: bytes) -> bytes:
    body = bytes([packet_type]) + payload
    return struct.pack("!I", len(body)) + body


def decode_packet(data: bytes) -> tuple[int, bytes] | None:
    if len(data) < 4:
        return None
    length = struct.unpack("!I", data[:4])[0]
    if len(data) < 4 + length:
        return None
    body = data[4 : 4 + length]
    return body[0], body[1:]


def unpack_u32(data: bytes, offset: int = 0) -> tuple[int, int]:
    return struct.unpack_from("!I", data, offset)[0], offset + 4


def unpack_u64(data: bytes, offset: int = 0) -> tuple[int, int]:
    return struct.unpack_from("!Q", data, offset)[0], offset + 8


def unpack_string(data: bytes, offset: int = 0) -> tuple[str, int]:
    length, offset = unpack_u32(data, offset)
    return data[offset : offset + length].decode("utf-8"), offset + length


def unpack_bytes(data: bytes, offset: int = 0) -> tuple[bytes, int]:
    length, offset = unpack_u32(data, offset)
    return data[offset : offset + length], offset + length


def pack_u32(value: int) -> bytes:
    return struct.pack("!I", value)


def pack_u64(value: int) -> bytes:
    return struct.pack("!Q", value)


def pack_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return pack_u32(len(encoded)) + encoded


def pack_bytes(value: bytes) -> bytes:
    return pack_u32(len(value)) + value


def encode_status(request_id: int, code: int, message: str = "", language: str = "") -> bytes:
    payload = pack_u32(request_id) + pack_u32(code) + pack_string(message) + pack_string(language)
    return payload


def encode_handle(request_id: int, handle: bytes) -> bytes:
    return pack_u32(request_id) + pack_bytes(handle)


def encode_data(request_id: int, data: bytes) -> bytes:
    return pack_u32(request_id) + data


def encode_name(request_id: int, entries: list[tuple[str, str, bytes]]) -> bytes:
    payload = pack_u32(request_id) + pack_u32(len(entries))
    for filename, longname, attrs in entries:
        payload += pack_string(filename) + pack_string(longname) + attrs
    return payload


def encode_attrs(path: str) -> bytes:
    stat_result = os.stat(path, follow_symlinks=False)
    flags = SSH_FILEXFER_ATTR_SIZE | SSH_FILEXFER_ATTR_PERMISSIONS | SSH_FILEXFER_ATTR_ACMODTIME
    payload = pack_u32(flags)
    payload += pack_u64(stat_result.st_size)
    payload += pack_u32(stat.S_IMODE(stat_result.st_mode))
    now = int(time.time())
    payload += pack_u32(now) + pack_u32(now)
    return payload


def decode_attrs(data: bytes, offset: int = 0) -> tuple[dict[str, Any], int]:
    flags, offset = unpack_u32(data, offset)
    attrs: dict[str, Any] = {"flags": flags}
    if flags & SSH_FILEXFER_ATTR_SIZE:
        attrs["size"], offset = unpack_u64(data, offset)
    if flags & SSH_FILEXFER_ATTR_UIDGID:
        attrs["uid"], offset = unpack_u32(data, offset)
        attrs["gid"], offset = unpack_u32(data, offset)
    if flags & SSH_FILEXFER_ATTR_PERMISSIONS:
        attrs["permissions"], offset = unpack_u32(data, offset)
    if flags & SSH_FILEXFER_ATTR_ACMODTIME:
        attrs["atime"], offset = unpack_u32(data, offset)
        attrs["mtime"], offset = unpack_u32(data, offset)
    return attrs, offset
