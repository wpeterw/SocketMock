from __future__ import annotations

import itertools
from typing import Any

from libs.stubs import StubMapping as BaseStubMapping
from libs.stubs import StubStore as BaseStubStore
from libs.stubs import match_one

_seq_counter = itertools.count(1)


def next_seq() -> int:
    return next(_seq_counter)


FIELD_MAP: dict[str, str] = {
    "sourceAddr": "source_addr",
    "destinationAddr": "destination_addr",
    "shortMessage": "short_message",
    "serviceType": "service_type",
    "systemId": "system_id",
}


def pdu_matches(stub_request: dict[str, Any], pdu: dict[str, Any]) -> bool:
    cmd_name = stub_request.get("commandName")
    if cmd_name and pdu.get("command_name") != cmd_name:
        return False

    for wm_field, pdu_field in FIELD_MAP.items():
        if wm_field not in stub_request:
            continue
        raw_value = pdu.get(pdu_field)
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("latin-1", errors="replace")
        if not match_one(stub_request[wm_field], raw_value):
            return False

    return True


class StubMapping(BaseStubMapping):
    pass


class StubStore(BaseStubStore):
    def __init__(self) -> None:
        super().__init__(matcher=pdu_matches)
