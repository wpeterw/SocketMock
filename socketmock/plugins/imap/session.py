from __future__ import annotations

import asyncio
import time
from typing import Any

from ..base import ProtocolSession, ProtocolStubStore
from .codec import IMAPCodec


class IMAPServerSession(ProtocolSession):
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
        self.session_id = f"imap-session-{id(self)}"
        self.peer = writer.get_extra_info("peername")
        self._closed = False
        self._write_lock = asyncio.Lock()
        self.logged_in = False
        self.selected_mailbox: str | None = None
        self.mailbox_messages = ["first message", "second message"]
        self.deleted: set[int] = set()
        self.tag_counter = 0

    async def run(self) -> None:
        self.store.register_session(
            self.session_id,
            {"sessionId": self.session_id, "peer": self.peer, "bound": True, "handle": self},
        )
        await self._send_line("* OK [CAPABILITY IMAP4rev1 LOGIN] socketmock ready")
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
                "commandName": "imap_command",
                "timestamp": time.time(),
                "pdu": {"command": command},
            }
        )
        if not command:
            await self._send_tagged("A000", "BAD", "empty command")
            return

        tag, verb, arg = IMAPCodec.parse_command(command)
        if verb == "LOGIN":
            self.logged_in = True
            await self._send_tagged(tag, "OK", "LOGIN completed")
        elif verb == "CAPABILITY":
            await self._send_line("* CAPABILITY IMAP4rev1 LOGIN")
            await self._send_tagged(tag, "OK", "CAPABILITY completed")
        elif verb == "LIST":
            await self._send_line(IMAPCodec.build_list_response())
            await self._send_tagged(tag, "OK", "LIST completed")
        elif verb == "SELECT":
            self.selected_mailbox = arg.strip('"')
            await self._send_line("* FLAGS (\\Answered \\Flagged \\Deleted \\Seen \\Draft)")
            await self._send_line("* 2 EXISTS")
            await self._send_line("* 0 RECENT")
            await self._send_tagged(tag, "OK", "[READ-WRITE] SELECT completed")
        elif verb == "FETCH":
            if not self.logged_in:
                await self._send_tagged(tag, "BAD", "not authenticated")
                return
            number = arg.split()[0]
            body = self.mailbox_messages[0]
            for line in IMAPCodec.build_fetch_response(int(number), body):
                await self._send_line(line)
            await self._send_tagged(tag, "OK", "FETCH completed")
        elif verb == "EXPUNGE":
            self.deleted.clear()
            await self._send_tagged(tag, "OK", "EXPUNGE completed")
        elif verb == "CLOSE":
            await self._send_tagged(tag, "OK", "CLOSE completed")
        elif verb == "NOOP":
            await self._send_tagged(tag, "OK", "NOOP completed")
        elif verb == "LOGOUT":
            await self._send_line("* BYE Logging out")
            await self._send_tagged(tag, "OK", "LOGOUT completed")
            self._closed = True
        else:
            await self._send_tagged(tag, "BAD", "unsupported")

    def _parse_command(self, command: str) -> tuple[str, str, str]:
        parts = command.split(maxsplit=2)
        tag = parts[0] if parts else "A000"
        verb = parts[1].upper() if len(parts) > 1 else ""
        arg = parts[2] if len(parts) > 2 else ""
        return tag, verb, arg

    async def _send_tagged(self, tag: str, status: str, message: str) -> None:
        await self._send_line(IMAPCodec.build_tagged(tag, status, message))

    async def _send_line(self, message: str) -> None:
        async with self._write_lock:
            if self._closed:
                return
            self.writer.write(f"{message}\r\n".encode("latin-1"))
            try:
                await self.writer.drain()
            except ConnectionError:
                self._closed = True
