from __future__ import annotations

# SMTP protocol plugin implementation.
import asyncio
from typing import Any

from libs.stubs import StubStore

from ..base import ProtocolPlugin, ProtocolStubStore
from .session import SMTPServerSession


class SMTPPlugin(ProtocolPlugin):
    name: str = "smtp"
    description: str = "SMTP message mock"
    default_port: int = 2779

    def create_store(self) -> ProtocolStubStore:
        return StubStore()

    def create_session(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> SMTPServerSession:
        return SMTPServerSession(reader, writer, store, config or {})
