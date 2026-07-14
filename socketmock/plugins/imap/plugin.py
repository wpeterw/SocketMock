from __future__ import annotations

# IMAP protocol plugin implementation.
import asyncio
from typing import Any

from libs.stubs import StubStore

from ..base import ProtocolPlugin, ProtocolStubStore
from .session import IMAPServerSession


class IMAPPlugin(ProtocolPlugin):
    name: str = "imap"
    description: str = "IMAP mailbox mock"
    default_port: int = 2781

    def create_store(self) -> ProtocolStubStore:
        return StubStore()

    def create_session(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> IMAPServerSession:
        return IMAPServerSession(reader, writer, store, config or {})
