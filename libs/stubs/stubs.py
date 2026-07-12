from __future__ import annotations

import builtins
import re
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


def match_one(matcher: Any, value: Any) -> bool:
    if matcher is None:
        return True
    if isinstance(matcher, dict):
        if "absent" in matcher:
            is_absent = value is None or value == ""
            return is_absent == bool(matcher["absent"])
        if "equalTo" in matcher:
            return value == matcher["equalTo"]
        if "contains" in matcher:
            return str(matcher["contains"]) in str(value)
        if "regex" in matcher:
            return re.search(matcher["regex"], str(value)) is not None
        if "matches" in matcher:
            return re.search(matcher["matches"], str(value)) is not None
    return True


@runtime_checkable
class ProtocolStubMapping(Protocol):
    id: str
    priority: int
    request: dict[str, Any]
    response: dict[str, Any]

    def to_dict(self) -> dict[str, Any]: ...


@runtime_checkable
class ProtocolStubStore(Protocol):
    def add(self, mapping: dict[str, Any]) -> ProtocolStubMapping: ...

    def list(self) -> builtins.list[dict[str, Any]]: ...

    def get(self, stub_id: str) -> dict[str, Any] | None: ...

    def delete(self, stub_id: str) -> bool: ...

    def reset_mappings(self) -> None: ...

    def find_match(self, pdu: dict[str, Any]) -> ProtocolStubMapping | None: ...

    def log_request(self, entry: dict[str, Any]) -> None: ...

    def journal(self) -> builtins.list[dict[str, Any]]: ...

    def reset_journal(self) -> None: ...

    def reset_all(self) -> None: ...

    def register_session(self, session_id: str, info: dict[str, Any]) -> None: ...

    def unregister_session(self, session_id: str) -> None: ...

    def list_sessions(self) -> builtins.list[dict[str, Any]]: ...

    def get_session_handle(self, session_id: str) -> Any: ...


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
    """Thread-safe store of stub mappings + request journal."""

    def __init__(
        self,
        matcher: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._stubs: dict[str, StubMapping] = {}
        self._journal: list[dict[str, Any]] = []
        self._sessions: dict[str, dict[str, Any]] = {}
        self._matcher = matcher or (lambda _request, _pdu: True)

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
            return [
                s.to_dict()
                for s in sorted(self._stubs.values(), key=lambda s: s.priority, reverse=True)
            ]

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
            candidates = sorted(self._stubs.values(), key=lambda s: s.priority, reverse=True)
        for stub in candidates:
            if self._matcher(stub.request, pdu):
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
            out: list[dict[str, Any]] = []
            for info in self._sessions.values():
                row = {k: v for k, v in info.items() if k != "handle"}
                row.setdefault("bound", False)
                out.append(row)
            return out

    def get_session_handle(self, session_id: str) -> Any:
        with self._lock:
            info = self._sessions.get(session_id)
            return info.get("handle") if info else None
