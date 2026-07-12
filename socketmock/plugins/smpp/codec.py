"""
Minimal SocketMock v3.4 PDU codec.
"""

from __future__ import annotations

import struct
from typing import Any

CMD: dict[str, int] = {
    "generic_nack": 0x80000000,
    "bind_receiver": 0x00000001,
    "bind_receiver_resp": 0x80000001,
    "bind_transmitter": 0x00000002,
    "bind_transmitter_resp": 0x80000002,
    "query_sm": 0x00000003,
    "query_sm_resp": 0x80000003,
    "submit_sm": 0x00000004,
    "submit_sm_resp": 0x80000004,
    "deliver_sm": 0x00000005,
    "deliver_sm_resp": 0x80000005,
    "unbind": 0x00000006,
    "unbind_resp": 0x80000006,
    "replace_sm": 0x00000007,
    "replace_sm_resp": 0x80000007,
    "cancel_sm": 0x00000008,
    "cancel_sm_resp": 0x80000008,
    "bind_transceiver": 0x00000009,
    "bind_transceiver_resp": 0x80000009,
    "outbind": 0x0000000B,
    "enquire_link": 0x00000015,
    "enquire_link_resp": 0x80000015,
    "data_sm": 0x00000103,
    "data_sm_resp": 0x80000103,
    "alert_notification": 0x00000102,
}
CMD_NAME: dict[int, str] = {v: k for k, v in CMD.items()}

ESME_ROK = 0x00000000
ESME_RINVMSGLEN = 0x00000001
ESME_RINVCMDLEN = 0x00000002
ESME_RINVCMDID = 0x00000003
ESME_RINVBNDSTS = 0x00000004
ESME_RALYBND = 0x00000005
ESME_RSYSERR = 0x00000008
ESME_RINVSRCADR = 0x0000000A
ESME_RINVDSTADR = 0x0000000B
ESME_RINVPASWD = 0x0000000E
ESME_RINVSYSID = 0x0000000F
ESME_RTHROTTLED = 0x00000058
ESME_RMSGQFUL = 0x00000014

PDU = dict[str, Any]


class PDUParseError(Exception):
    pass


def _read_cstring(buf: bytes, offset: int) -> tuple[str, int]:
    end = buf.index(b"\x00", offset)
    return buf[offset:end].decode("latin-1"), end + 1


def _cstring(value: str | bytes | None) -> bytes:
    if value is None:
        value = ""
    if isinstance(value, bytes):
        return value + (b"\x00" if not value.endswith(b"\x00") else b"")
    return value.encode("latin-1") + b"\x00"


def _u8(n: int) -> bytes:
    return struct.pack("!B", n & 0xFF)


def _read_u8(buf: bytes, offset: int) -> tuple[int, int]:
    return buf[offset], offset + 1


def _encode_tlvs(tlvs: dict[int, bytes | str] | None) -> bytes:
    out = b""
    for tag, value in (tlvs or {}).items():
        if isinstance(value, str):
            value = value.encode("latin-1")
        out += struct.pack("!HH", tag, len(value)) + value
    return out


def _decode_tlvs(buf: bytes, offset: int) -> dict[int, bytes]:
    tlvs: dict[int, bytes] = {}
    while offset < len(buf):
        if offset + 4 > len(buf):
            break
        tag, length = struct.unpack("!HH", buf[offset : offset + 4])
        offset += 4
        value = buf[offset : offset + length]
        offset += length
        tlvs[tag] = value
    return tlvs


def encode_pdu(pdu: PDU) -> bytes:
    name = pdu["command_name"]
    command_id = CMD[name]
    status = pdu.get("command_status", 0)
    seq = pdu.get("sequence_number", 0)

    body = b""

    if name in ("bind_receiver", "bind_transmitter", "bind_transceiver"):
        body += _cstring(pdu.get("system_id"))
        body += _cstring(pdu.get("password"))
        body += _cstring(pdu.get("system_type"))
        body += _u8(pdu.get("interface_version", 0x34))
        body += _u8(pdu.get("addr_ton", 0))
        body += _u8(pdu.get("addr_npi", 0))
        body += _cstring(pdu.get("address_range"))
    elif name in ("bind_receiver_resp", "bind_transmitter_resp", "bind_transceiver_resp"):
        body += _cstring(pdu.get("system_id"))
        if pdu.get("sc_interface_version") is not None:
            body += struct.pack("!HHB", 0x0210, 1, pdu["sc_interface_version"])
    elif name in ("submit_sm", "deliver_sm"):
        body += _cstring(pdu.get("service_type"))
        body += _u8(pdu.get("source_addr_ton", 0))
        body += _u8(pdu.get("source_addr_npi", 0))
        body += _cstring(pdu.get("source_addr"))
        body += _u8(pdu.get("dest_addr_ton", 0))
        body += _u8(pdu.get("dest_addr_npi", 0))
        body += _cstring(pdu.get("destination_addr"))
        body += _u8(pdu.get("esm_class", 0))
        body += _u8(pdu.get("protocol_id", 0))
        body += _u8(pdu.get("priority_flag", 0))
        body += _cstring(pdu.get("schedule_delivery_time"))
        body += _cstring(pdu.get("validity_period"))
        body += _u8(pdu.get("registered_delivery", 0))
        body += _u8(pdu.get("replace_if_present_flag", 0))
        body += _u8(pdu.get("data_coding", 0))
        body += _u8(pdu.get("sm_default_msg_id", 0))
        short_message = pdu.get("short_message", b"") or b""
        if isinstance(short_message, str):
            short_message = short_message.encode("latin-1")
        body += _u8(len(short_message))
        body += short_message
        body += _encode_tlvs(pdu.get("tlvs"))
    elif name in ("submit_sm_resp", "deliver_sm_resp"):
        body += _cstring(pdu.get("message_id"))
    elif name in ("unbind", "unbind_resp", "enquire_link", "enquire_link_resp", "generic_nack"):
        pass
    else:
        body = pdu.get("raw_body", b"")

    header = struct.pack("!IIII", 16 + len(body), command_id, status, seq)
    return header + body


def decode_pdu(raw: bytes) -> PDU:
    if len(raw) < 16:
        raise PDUParseError("PDU shorter than header")
    length, command_id, status, seq = struct.unpack("!IIII", raw[:16])
    body = raw[16:length] if length <= len(raw) else raw[16:]
    name = CMD_NAME.get(command_id, hex(command_id))

    pdu: PDU = {
        "command_id": command_id,
        "command_name": name,
        "command_status": status,
        "sequence_number": seq,
        "tlvs": {},
    }

    off = 0
    try:
        if name in ("bind_receiver", "bind_transmitter", "bind_transceiver"):
            pdu["system_id"], off = _read_cstring(body, off)
            pdu["password"], off = _read_cstring(body, off)
            pdu["system_type"], off = _read_cstring(body, off)
            pdu["interface_version"], off = _read_u8(body, off)
            pdu["addr_ton"], off = _read_u8(body, off)
            pdu["addr_npi"], off = _read_u8(body, off)
            pdu["address_range"], off = _read_cstring(body, off)
        elif name in ("bind_receiver_resp", "bind_transmitter_resp", "bind_transceiver_resp"):
            pdu["system_id"], off = _read_cstring(body, off)
            pdu["tlvs"] = _decode_tlvs(body, off)
        elif name in ("submit_sm", "deliver_sm"):
            pdu["service_type"], off = _read_cstring(body, off)
            pdu["source_addr_ton"], off = _read_u8(body, off)
            pdu["source_addr_npi"], off = _read_u8(body, off)
            pdu["source_addr"], off = _read_cstring(body, off)
            pdu["dest_addr_ton"], off = _read_u8(body, off)
            pdu["dest_addr_npi"], off = _read_u8(body, off)
            pdu["destination_addr"], off = _read_cstring(body, off)
            pdu["esm_class"], off = _read_u8(body, off)
            pdu["protocol_id"], off = _read_u8(body, off)
            pdu["priority_flag"], off = _read_u8(body, off)
            pdu["schedule_delivery_time"], off = _read_cstring(body, off)
            pdu["validity_period"], off = _read_cstring(body, off)
            pdu["registered_delivery"], off = _read_u8(body, off)
            pdu["replace_if_present_flag"], off = _read_u8(body, off)
            pdu["data_coding"], off = _read_u8(body, off)
            pdu["sm_default_msg_id"], off = _read_u8(body, off)
            sm_length, off = _read_u8(body, off)
            pdu["short_message"] = body[off : off + sm_length]
            off += sm_length
            pdu["tlvs"] = _decode_tlvs(body, off)
        elif name in ("submit_sm_resp", "deliver_sm_resp"):
            pdu["message_id"], off = _read_cstring(body, off)
        elif name in ("unbind", "unbind_resp", "enquire_link", "enquire_link_resp", "generic_nack"):
            pass
        else:
            pdu["raw_body"] = body
    except (IndexError, ValueError) as exc:
        raise PDUParseError(f"Malformed {name} body: {exc}") from exc

    return pdu


def try_extract_one(buf: bytearray) -> tuple[PDU | None, int]:
    if len(buf) < 4:
        return None, 0
    (length,) = struct.unpack("!I", bytes(buf[:4]))
    if length < 16 or length > 64 * 1024:
        raise PDUParseError(f"Implausible PDU length {length}")
    if len(buf) < length:
        return None, 0
    raw = bytes(buf[:length])
    pdu = decode_pdu(raw)
    return pdu, length
