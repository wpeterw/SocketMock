from __future__ import annotations

import asyncio
from typing import Any

from ..base import ProtocolSession, ProtocolStubStore


class ExampleSession(ProtocolSession):
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.store = store
        self.config = config or {}

    async def run(self) -> None:
        try:
            while True:
                chunk = await self.reader.read(4096)
                if not chunk:
                    break
        finally:
            self.writer.close()
