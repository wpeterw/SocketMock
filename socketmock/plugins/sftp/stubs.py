from __future__ import annotations

from typing import Any

from libs.stubs import StubStore as BaseStubStore
from libs.stubs import match_one

FIELD_MAP: dict[str, str] = {
    "operation": "operation",
    "requestId": "requestId",
    "path": "path",
    "flags": "pflags",
    "handle": "handle",
}


def request_matches(stub_request: dict[str, Any], request: dict[str, Any]) -> bool:
    operation = stub_request.get("operation")
    if operation and request.get("operation") != operation:
        return False

    for stub_field, request_field in FIELD_MAP.items():
        if stub_field not in stub_request:
            continue
        if not match_one(stub_request[stub_field], request.get(request_field)):
            return False

    return True


class StubStore(BaseStubStore):
    def __init__(self) -> None:
        super().__init__(matcher=request_matches)
