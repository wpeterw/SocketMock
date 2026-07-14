from __future__ import annotations

from typing import Any

MLLP_START = b"\x0b"
MLLP_END = b"\x1c\x0d"


def decode_message(data: bytes) -> dict[str, Any] | None:
    if not data:
        return None
    if data.startswith(MLLP_START):
        data = data[1:]
    if data.endswith(MLLP_END):
        data = data[:-2]
    if not data:
        return None
    text = data.decode("latin-1", errors="replace")
    segments = [segment for segment in text.split("\r") if segment]
    msh_parts = segments[0].split("|") if segments else []
    msh = msh_parts[1:] if msh_parts and msh_parts[0] == "MSH" else msh_parts
    return {
        "raw": text,
        "segments": segments,
        "msh": {
            "field_separator": "|",
            "encoding_chars": msh[0] if len(msh) > 0 else "^~\\&",
            "sending_app": msh[1] if len(msh) > 1 else "",
            "sending_facility": msh[2] if len(msh) > 2 else "",
            "receiving_app": msh[3] if len(msh) > 3 else "",
            "receiving_facility": msh[4] if len(msh) > 4 else "",
            "message_type": msh[7] if len(msh) > 7 else "",
            "message_control_id": msh[8] if len(msh) > 8 else "",
        },
        "message_type": msh[7] if len(msh) > 7 else "",
        "control_id": msh[8] if len(msh) > 8 else "",
    }


def encode_ack(message: dict[str, Any]) -> bytes:
    msh = message.get("msh", {})
    control_id = message.get("control_id") or msh.get("message_control_id") or "1"
    ack = (
        f"MSH|^~\\&|{msh.get('receiving_app', 'SOCKETMOCK')}|"
        f"{msh.get('receiving_facility', 'TEST')}|{msh.get('sending_app', 'SOCKETMOCK')}|"
        f"{msh.get('sending_facility', 'TEST')}|{msh.get('encoding_chars', '^~\\&')}||ACK|"
        f"{control_id}|P|2.4\r"
        f"MSA|AA|{control_id}\r"
    )
    return MLLP_START + ack.encode("latin-1") + MLLP_END


def frame_message(payload: str) -> bytes:
    return MLLP_START + payload.encode("latin-1") + MLLP_END
