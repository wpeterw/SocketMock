from __future__ import annotations

import asyncio
from typing import Any

from ..base import ProtocolPlugin, ProtocolStubStore
from .session import SFTPSession
from .stubs import StubStore


class SFTPPlugin(ProtocolPlugin):
    name: str = "sftp"
    description: str = "Protocol mock service"
    default_port: int = 2222

    def create_store(self) -> ProtocolStubStore:
        return StubStore()

    def create_session(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> SFTPSession:
        return SFTPSession(reader, writer, store, config)
