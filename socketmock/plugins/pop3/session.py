from __future__ import annotations

import asyncio
import time
from typing import Any

from ..base import ProtocolSession, ProtocolStubStore
from .codec import POP3Codec


class POP3ServerSession(ProtocolSession):
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
        self.session_id = f"pop3-session-{id(self)}"
        self.peer = writer.get_extra_info("peername")
        self._closed = False
        self._write_lock = asyncio.Lock()
        self.state = "authorization"
        self.username: str | None = None
        self.authenticated = False
        self.messages: list[str] = ["hello from socketmock", "second message"]
        self.deleted: set[int] = set()

    async def run(self) -> None:
        self.store.register_session(
            self.session_id,
            {"sessionId": self.session_id, "peer": self.peer, "bound": True, "handle": self},
        )
        await self._send_line(POP3Codec.build_ok("socketmock POP3 ready"))
        try:
            while not self._closed:
                line = await self.reader.readline()
                if not line:
                    break
                command = line.decode("latin-1", errors="replace").rstrip("\r\n")
                await self._handle_command(command)
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            self.store.unregister_session(self.session_id)
            self._closed = True
            self.writer.close()

    async def _handle_command(self, command: str) -> None:
        self.store.log_request(
            {
                "sessionId": self.session_id,
                "direction": "in",
                "commandName": "pop3_command",
                "timestamp": time.time(),
                "pdu": {"command": command},
            }
        )
        if not command:
            await self._send_line(POP3Codec.build_err("empty command"))
            return

        verb, arg = POP3Codec.parse_command(command)

        if verb == "USER":
            self.username = arg
            await self._send_line(POP3Codec.build_ok("user accepted"))
        elif verb == "PASS":
            self.authenticated = bool(self.username)
            self.state = "transaction"
            await self._send_line(POP3Codec.build_ok("pass accepted"))
        elif verb == "STAT":
            if not self.authenticated:
                await self._send_line(POP3Codec.build_err("not authenticated"))
                return
            active = [i for i in range(len(self.messages)) if i not in self.deleted]
            total_size = sum(len(self.messages[i]) for i in active)
            await self._send_line(POP3Codec.build_stat(len(active), total_size))
        elif verb == "LIST":
            if not self.authenticated:
                await self._send_line(POP3Codec.build_err("not authenticated"))
                return
            if arg:
                index = int(arg) - 1
                if 0 <= index < len(self.messages):
                    await self._send_line(POP3Codec.build_ok(f"{arg} {len(self.messages[index])}"))
                else:
                    await self._send_line(POP3Codec.build_err("no such message"))
            else:
                active = [i for i in range(len(self.messages)) if i not in self.deleted]
                await self._send_line(POP3Codec.build_ok(f"{len(active)} messages"))
                for i, message in enumerate(self.messages, start=1):
                    if i - 1 not in self.deleted:
                        await self._send_line(f"{i} {len(message)}")
                await self._send_line(".")
        elif verb == "RETR":
            if not self.authenticated:
                await self._send_line(POP3Codec.build_err("not authenticated"))
                return
            index = int(arg) - 1
            if 0 <= index < len(self.messages):
                await self._send_line(POP3Codec.build_ok(f"{len(self.messages[index])} octets"))
                await self._send_line(self.messages[index])
                await self._send_line(".")
            else:
                await self._send_line(POP3Codec.build_err("no such message"))
        elif verb == "DELE":
            if not self.authenticated:
                await self._send_line(POP3Codec.build_err("not authenticated"))
                return
            index = int(arg) - 1
            if 0 <= index < len(self.messages):
                self.deleted.add(index)
                await self._send_line(POP3Codec.build_ok("message marked deleted"))
            else:
                await self._send_line(POP3Codec.build_err("no such message"))
        elif verb == "RSET":
            self.deleted.clear()
            await self._send_line(POP3Codec.build_ok("reset complete"))
        elif verb == "NOOP":
            await self._send_line(POP3Codec.build_ok(""))
        elif verb == "QUIT":
            await self._send_line(POP3Codec.build_ok("bye"))
            self._closed = True
        else:
            await self._send_line(POP3Codec.build_err("unknown command"))

    async def _send_line(self, message: str) -> None:
        async with self._write_lock:
            if self._closed:
                return
            self.writer.write(f"{message}\r\n".encode("latin-1"))
            try:
                await self.writer.drain()
            except ConnectionError:
                self._closed = True
