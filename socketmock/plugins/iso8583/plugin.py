from __future__ import annotations

# ISO 8583 protocol plugin implementation.
import asyncio
from typing import Any

from libs.stubs import StubStore

from ..base import ProtocolPlugin, ProtocolStubStore
from .session import ISO8583Session


class ISO8583Plugin(ProtocolPlugin):
    name: str = "iso8583"
    description: str = "ISO 8583 payment message mock"
    default_port: int = 2778

    def create_store(self) -> ProtocolStubStore:
        return StubStore()

    def create_session(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> ISO8583Session:
        return ISO8583Session(reader, writer, store, config or {})
