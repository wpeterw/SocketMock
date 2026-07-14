from __future__ import annotations

from typing import Any


def decode_message(data: bytes) -> dict[str, Any]:
    text = data.decode("latin-1", errors="replace")
    segments = [segment for segment in text.split("~") if segment]
    isa = segments[0].split("*") if segments else []
    st_segment = next((segment.split("*") for segment in segments if segment.startswith("ST*")), [])
    return {
        "raw": text,
        "segments": segments,
        "isa": {
            "control_id": isa[13] if len(isa) > 13 else "",
            "sender": isa[6] if len(isa) > 6 else "",
            "receiver": isa[8] if len(isa) > 8 else "",
        },
        "transaction_control": st_segment[2] if len(st_segment) > 2 else "",
    }


def encode_ack(message: dict[str, Any]) -> bytes:
    isa = message.get("isa", {})
    control_id = message.get("transaction_control") or isa.get("control_id") or "0001"
    ack = (
        f"ISA*00*          *00*          *01*{isa.get('sender', 'SENDER')}*01*"
        f"{isa.get('receiver', 'RECEIVER')}*240101*0101*U*00401*{control_id}*0*P*:~"
        f"GS*FA*{isa.get('sender', 'SENDER')}*"
        f"{isa.get('receiver', 'RECEIVER')}*240101*0101*1*X*004010~"
        f"ST*997*{control_id}~"
        f"AK1*HC*{control_id}~"
        f"AK9*A*1*1*1~"
        f"SE*4*{control_id}~"
    )
    return ack.encode("latin-1")
