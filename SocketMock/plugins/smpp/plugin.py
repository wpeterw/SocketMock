from __future__ import annotations

import asyncio
from typing import Any

from ..base import ProtocolPlugin, ProtocolStubStore
from .session import SMPPSession
from .stubs import StubStore


class SMPPPlugin(ProtocolPlugin):
    name: str = "smpp"
    description: str = "Protocol mock service"
    default_port: int = 2775

    def create_store(self) -> ProtocolStubStore:
        return StubStore()

    def create_session(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> SMPPSession:
        return SMPPSession(reader, writer, store, config or {})
