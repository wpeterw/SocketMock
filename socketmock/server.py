"""Asyncio server core that delegates connection handling to protocol plugins."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .plugins import ProtocolPlugin, ProtocolRegistry, ProtocolStubStore
from .plugins.smpp.plugin import SMPPPlugin

logger = logging.getLogger("socketmock.server")


class ProtocolServer:
    def __init__(
        self,
        store: ProtocolStubStore,
        plugin: ProtocolPlugin,
        host: str = "0.0.0.0",
        port: int = 2775,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.store = store
        self.plugin = plugin
        self.host = host
        self.port = port
        self.config = config or {}
        self._server: asyncio.Server | None = None

    async def _on_connect(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        session = self.plugin.create_session(reader, writer, self.store, self.config)
        session_id = getattr(session, "session_id", "unknown")
        logger.info("[%s] connection from %s", session_id, getattr(session, "peer", None))
        await session.run()

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._on_connect, self.host, self.port)
        logger.info("%s protocol listening on %s:%s", self.plugin.name, self.host, self.port)

    async def serve_forever(self) -> None:
        await self.start()
        if self._server is None:
            raise RuntimeError("server was not started")
        async with self._server:
            await self._server.serve_forever()


SocketMockPlugin = SMPPPlugin
ProtocolRegistry.register(SocketMockPlugin)


class SocketMockServer(ProtocolServer):
    def __init__(
        self,
        store: ProtocolStubStore,
        host: str = "0.0.0.0",
        port: int = 2775,
        config: dict[str, Any] | None = None,
        plugin: ProtocolPlugin | None = None,
    ) -> None:
        super().__init__(store, plugin or SocketMockPlugin(), host=host, port=port, config=config)
