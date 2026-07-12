"""
Stub matching engine, modeled after Wiremock's mapping/journal concepts.
"""

from __future__ import annotations

import builtins
import itertools
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

_seq_counter = itertools.count(1)


def next_seq() -> int:
    return next(_seq_counter)


def _match_one(matcher: dict[str, Any] | None, value: str | None) -> bool:
    if matcher is None:
        return True
    if "absent" in matcher:
        is_absent = value is None or value == ""
        return is_absent == bool(matcher["absent"])
    value = value or ""
    if "equalTo" in matcher:
        return value == matcher["equalTo"]
    if "contains" in matcher:
        return matcher["contains"] in value
    if "regex" in matcher:
        return re.search(matcher["regex"], value) is not None
    if "matches" in matcher:
        return re.search(matcher["matches"], value) is not None
    return True


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
        if not _match_one(stub_request[wm_field], raw_value):
            return False

    return True


@dataclass
class StubMapping:
    id: str
    priority: int
    request: dict[str, Any]
    response: dict[str, Any]
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "priority": self.priority,
            "request": self.request,
            "response": self.response,
            "createdAt": self.created_at,
        }


class StubStore:
    """Thread-safe store of stub mappings + request journal, à la Wiremock."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stubs: dict[str, StubMapping] = {}
        self._journal: list[dict[str, Any]] = []
        self._sessions: dict[str, dict[str, Any]] = {}

    def add(self, mapping: dict[str, Any]) -> StubMapping:
        mid = mapping.get("id") or str(uuid.uuid4())
        stub = StubMapping(
            id=mid,
            priority=mapping.get("priority", 5),
            request=mapping.get("request", {}),
            response=mapping.get("response", {}),
        )
        with self._lock:
            self._stubs[mid] = stub
        return stub

    def list(self) -> builtins.list[dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in sorted(self._stubs.values(), key=lambda s: s.priority)]

    def get(self, stub_id: str) -> dict[str, Any] | None:
        with self._lock:
            s = self._stubs.get(stub_id)
            return s.to_dict() if s else None

    def delete(self, stub_id: str) -> bool:
        with self._lock:
            return self._stubs.pop(stub_id, None) is not None

    def reset_mappings(self) -> None:
        with self._lock:
            self._stubs.clear()

    def find_match(self, pdu: dict[str, Any]) -> StubMapping | None:
        with self._lock:
            candidates = sorted(self._stubs.values(), key=lambda s: s.priority)
        for stub in candidates:
            if pdu_matches(stub.request, pdu):
                return stub
        return None

    def log_request(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._journal.append(entry)

    def journal(self) -> builtins.list[dict[str, Any]]:
        with self._lock:
            return list(self._journal)

    def reset_journal(self) -> None:
        with self._lock:
            self._journal.clear()

    def reset_all(self) -> None:
        self.reset_mappings()
        self.reset_journal()

    def register_session(self, session_id: str, info: dict[str, Any]) -> None:
        with self._lock:
            self._sessions[session_id] = info

    def unregister_session(self, session_id: str) -> None:
        with self._lock:
            info = self._sessions.get(session_id)
            if info is not None:
                info["bound"] = False
                info["lastSeen"] = time.time()

    def list_sessions(self) -> builtins.list[dict[str, Any]]:
        with self._lock:
            out: builtins.list[dict[str, Any]] = []
            for info in self._sessions.values():
                row = {k: v for k, v in info.items() if k != "handle"}
                row.setdefault("bound", False)
                out.append(row)
            return out

    def get_session_handle(self, session_id: str) -> Any:
        with self._lock:
            info = self._sessions.get(session_id)
            return info.get("handle") if info else None
