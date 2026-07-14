from __future__ import annotations

# POP3 protocol plugin implementation.
import asyncio
from typing import Any

from libs.stubs import StubStore

from ..base import ProtocolPlugin, ProtocolStubStore
from .session import POP3ServerSession


class POP3Plugin(ProtocolPlugin):
    name: str = "pop3"
    description: str = "POP3 mailbox mock"
    default_port: int = 2780

    def create_store(self) -> ProtocolStubStore:
        return StubStore()

    def create_session(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> POP3ServerSession:
        return POP3ServerSession(reader, writer, store, config or {})
