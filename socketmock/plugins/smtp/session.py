from __future__ import annotations

import asyncio
import time
from typing import Any

from ..base import ProtocolSession, ProtocolStubStore
from .codec import SMTPCodec


class SMTPServerSession(ProtocolSession):
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
        self.session_id = f"smtp-session-{id(self)}"
        self.peer = writer.get_extra_info("peername")
        self._closed = False
        self._write_lock = asyncio.Lock()
        self.state = "connect"
        self.helo_name: str | None = None
        self.mail_from: str | None = None
        self.recipients: list[str] = []
        self.message_lines: list[str] = []
        self.received_messages: list[str] = []
        self._message_count = 0

    async def run(self) -> None:
        self.store.register_session(
            self.session_id,
            {"sessionId": self.session_id, "peer": self.peer, "bound": True, "handle": self},
        )
        await self._send_line(SMTPCodec.build_banner("socketmock"))
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
                "commandName": "smtp_command",
                "timestamp": time.time(),
                "pdu": {"command": command},
            }
        )
        if self.state == "data":
            if command == ".":
                self.received_messages.append("\n".join(self.message_lines))
                self._message_count += 1
                self.message_lines = []
                self.state = "mail"
                await self._send_line(SMTPCodec.build_response(250, "message accepted"))
                return
            self.message_lines.append(command)
            return

        if not command:
            await self._send_line(SMTPCodec.build_response(500, "empty command"))
            return

        verb, arg = SMTPCodec.parse_command(command)

        if verb in {"HELO", "EHLO"}:
            self.helo_name = arg
            self.state = "mail"
            await self._send_line(SMTPCodec.build_response(250, "socketmock hello"))
        elif verb == "AUTH":
            await self._send_line(SMTPCodec.build_response(235, "2.7.0 authentication successful"))
        elif verb == "MAIL" and arg.upper().startswith("FROM:"):
            self.mail_from = SMTPCodec.parse_mail_from(arg)
            self.recipients = []
            self.state = "mail"
            await self._send_line(SMTPCodec.build_response(250, "mail from accepted"))
        elif verb == "RCPT" and arg.upper().startswith("TO:"):
            self.recipients.append(SMTPCodec.parse_rcpt_to(arg))
            await self._send_line(SMTPCodec.build_response(250, "recipient accepted"))
        elif verb == "DATA":
            self.message_lines = []
            self.state = "data"
            await self._send_line(SMTPCodec.build_response(354, "end data with <CR><LF>.<CR><LF>"))
        elif verb == "RSET":
            self.mail_from = None
            self.recipients = []
            self.message_lines = []
            self.state = "mail"
            await self._send_line(SMTPCodec.build_response(250, "reset complete"))
        elif verb == "NOOP":
            await self._send_line(SMTPCodec.build_response(250, "noop"))
        elif verb == "QUIT":
            await self._send_line(SMTPCodec.build_response(221, "bye"))
            self._closed = True
        else:
            await self._send_line(SMTPCodec.build_response(500, "unsupported"))

    async def _send_line(self, message: str) -> None:
        async with self._write_lock:
            if self._closed:
                return
            self.writer.write(f"{message}\r\n".encode("latin-1"))
            try:
                await self.writer.drain()
            except ConnectionError:
                self._closed = True
