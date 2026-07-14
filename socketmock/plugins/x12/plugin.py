from __future__ import annotations

# X12 EDI protocol plugin implementation.
import asyncio
from typing import Any

from libs.stubs import StubStore

from ..base import ProtocolPlugin, ProtocolStubStore
from .session import X12Session


class X12Plugin(ProtocolPlugin):
    name: str = "x12"
    description: str = "X12 EDI message mock"
    default_port: int = 2777

    def create_store(self) -> ProtocolStubStore:
        return StubStore()

    def create_session(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> X12Session:
        return X12Session(reader, writer, store, config or {})
