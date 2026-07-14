from __future__ import annotations

import asyncio
import time
from typing import Any

from ..base import ProtocolSession, ProtocolStubStore
from . import codec as x12_codec


class X12Session(ProtocolSession):
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
        self.session_id = f"x12-session-{id(self)}"
        self.peer = writer.get_extra_info("peername")
        self._closed = False
        self._write_lock = asyncio.Lock()

    async def run(self) -> None:
        self.store.register_session(
            self.session_id,
            {"sessionId": self.session_id, "peer": self.peer, "bound": True, "handle": self},
        )
        buffer = bytearray()
        try:
            while True:
                chunk = await self.reader.read(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                if b"~" not in buffer:
                    continue
                while b"~" in buffer:
                    end = buffer.find(b"~")
                    payload = bytes(buffer[: end + 1])
                    del buffer[: end + 1]
                    await self._handle_message(payload)
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            self.store.unregister_session(self.session_id)
            self._closed = True
            self.writer.close()

    async def _handle_message(self, payload: bytes) -> None:
        message = x12_codec.decode_message(payload)
        self.store.log_request(
            {
                "sessionId": self.session_id,
                "direction": "in",
                "commandName": "x12_message",
                "timestamp": time.time(),
                "pdu": {"message": message["raw"]},
            }
        )
        await self.send(x12_codec.encode_ack(message))

    async def send(self, payload: bytes) -> None:
        async with self._write_lock:
            if self._closed:
                return
            self.writer.write(payload)
            try:
                await self.writer.drain()
            except ConnectionError:
                self._closed = True
