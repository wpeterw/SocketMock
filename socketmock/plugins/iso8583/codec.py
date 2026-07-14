from __future__ import annotations

from typing import Any


def _bitmap_bytes(fields: list[int]) -> bytes:
    bitmap = bytearray(16)
    for field in fields:
        if field <= 0:
            continue
        if field > 128:
            continue
        byte_index = (field - 1) // 8
        bit_index = (field - 1) % 8
        if byte_index < len(bitmap):
            bitmap[byte_index] |= 1 << (7 - bit_index)
    return bytes(bitmap)


def decode_message(data: bytes) -> dict[str, Any] | None:
    if len(data) < 2:
        return None
    candidate_length = int.from_bytes(data[:2], "big")
    if candidate_length + 2 <= len(data) and candidate_length >= 20:
        body = data[2 : 2 + candidate_length]
    else:
        body = data
    if len(body) < 20:
        return None
    mti = body[:4].decode("ascii", errors="replace")
    bitmap = body[4:20]
    fields: dict[int, bytes] = {}
    offset = 20
    for field_no in range(1, 129):
        if field_no > 128:
            break
        byte_index = (field_no - 1) // 8
        bit_index = (field_no - 1) % 8
        if byte_index >= len(bitmap):
            break
        if bitmap[byte_index] & (1 << (7 - bit_index)):
            if offset + 2 > len(body):
                break
            size = int.from_bytes(body[offset : offset + 2], "big")
            offset += 2
            if offset + size > len(body):
                break
            fields[field_no] = body[offset : offset + size]
            offset += size
    return {"mti": mti, "fields": fields}


def encode_response(message: dict[str, Any]) -> bytes:
    request_mti = str(message.get("mti", "0800"))
    if request_mti.startswith("08"):
        response_mti = "0810"
    elif request_mti.startswith("02"):
        response_mti = "0210"
    else:
        response_mti = "0110"
    fields = dict(message.get("fields", {}))
    response_fields = {39: b"00"}
    if 11 in fields:
        response_fields[11] = fields[11]
    if 12 in fields:
        response_fields[12] = fields[12]
    if 37 in fields:
        response_fields[37] = fields[37]
    bitmap = _bitmap_bytes(list(response_fields))
    payload = response_mti.encode("ascii") + bitmap
    field_parts: list[bytes] = []
    for field_no in sorted(response_fields):
        value = response_fields[field_no]
        field_parts.append(len(value).to_bytes(2, "big") + value)
    payload += b"".join(field_parts)
    return len(payload).to_bytes(2, "big") + payload
