"""
Asyncio server core plus the built-in SocketMock protocol plugin.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from .plugins import ProtocolPlugin, ProtocolRegistry
from .plugins.socketmock import StubStore
from .plugins.socketmock import pdu as pdumod

logger = logging.getLogger("SocketMock.server")

BIND_COMMANDS = {"bind_transmitter", "bind_receiver", "bind_transceiver"}
BIND_RESP = {
    "bind_transmitter": "bind_transmitter_resp",
    "bind_receiver": "bind_receiver_resp",
    "bind_transceiver": "bind_transceiver_resp",
}
CAN_SUBMIT = {"bind_transmitter", "bind_transceiver"}
CAN_RECEIVE = {"bind_receiver", "bind_transceiver"}


class SocketMockSession:
    _id_counter = itertools.count(1)

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: StubStore,
        config: dict[str, Any],
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.store = store
        self.config = config
        self.session_id = f"sess-{next(self._id_counter)}"
        self.peer = writer.get_extra_info("peername")
        self.bind_type: str | None = None
        self.system_id: str | None = None
        self.bound = False
        self._out_seq = itertools.count(1)
        self._write_lock = asyncio.Lock()
        self._closed = False

    def next_seq(self) -> int:
        return next(self._out_seq)

    async def send(self, pdu: dict[str, Any]) -> None:
        raw = pdumod.encode_pdu(pdu)
        async with self._write_lock:
            if self._closed:
                return
            self.writer.write(raw)
            try:
                await self.writer.drain()
            except ConnectionError:
                self._closed = True

    def as_info(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "peer": f"{self.peer[0]}:{self.peer[1]}" if self.peer else None,
            "systemId": self.system_id,
            "bindType": self.bind_type,
            "bound": self.bound,
            "handle": self,
        }

    async def run(self) -> None:
        buf = bytearray()
        try:
            while True:
                chunk = await self.reader.read(4096)
                if not chunk:
                    break
                buf.extend(chunk)
                while True:
                    try:
                        pdu, consumed = pdumod.try_extract_one(buf)
                    except pdumod.PDUParseError as exc:
                        logger.warning("[%s] malformed PDU, closing: %s", self.session_id, exc)
                        return
                    if consumed == 0 or pdu is None:
                        break
                    del buf[:consumed]
                    await self._handle_pdu(pdu)
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            self.store.unregister_session(self.session_id)
            self._closed = True
            try:
                self.writer.close()
            except Exception:
                pass
            logger.info("[%s] connection closed (system_id=%s)", self.session_id, self.system_id)

    async def _handle_pdu(self, in_pdu: dict[str, Any]) -> None:
        name = in_pdu["command_name"]
        seq = in_pdu["sequence_number"]

        self.store.log_request(
            {
                "sessionId": self.session_id,
                "systemId": self.system_id,
                "direction": "in",
                "commandName": name,
                "sequenceNumber": seq,
                "timestamp": time.time(),
                "pdu": _jsonable_pdu(in_pdu),
            }
        )

        if name in BIND_COMMANDS:
            await self._handle_bind(in_pdu)
        elif name == "submit_sm":
            await self._handle_submit_sm(in_pdu)
        elif name == "enquire_link":
            await self.send(
                {
                    "command_name": "enquire_link_resp",
                    "sequence_number": seq,
                    "command_status": 0,
                }
            )
        elif name == "unbind":
            await self.send(
                {
                    "command_name": "unbind_resp",
                    "sequence_number": seq,
                    "command_status": 0,
                }
            )
            self.bound = False
            self.writer.close()
        elif name in ("deliver_sm_resp",):
            pass
        else:
            await self.send(
                {
                    "command_name": "generic_nack",
                    "sequence_number": seq,
                    "command_status": pdumod.ESME_RINVCMDID,
                }
            )

    async def _handle_bind(self, in_pdu: dict[str, Any]) -> None:
        name = in_pdu["command_name"]
        seq = in_pdu["sequence_number"]
        resp_name = BIND_RESP[name]

        creds = self.config.get("credentials")
        status = 0
        if creds:
            expected = creds.get(in_pdu.get("system_id"))
            if expected is None or expected != in_pdu.get("password"):
                status = pdumod.ESME_RINVPASWD

        if status == 0:
            self.bound = True
            self.bind_type = name
            self.system_id = in_pdu.get("system_id")
            self.store.register_session(self.session_id, self.as_info())
            logger.info("[%s] bound as %s (%s)", self.session_id, self.system_id, name)

        await self.send(
            {
                "command_name": resp_name,
                "sequence_number": seq,
                "command_status": status,
                "system_id": self.config.get("system_id", "socketmock"),
            }
        )

    async def _handle_submit_sm(self, in_pdu: dict[str, Any]) -> None:
        seq = in_pdu["sequence_number"]

        if not self.bound or self.bind_type not in CAN_SUBMIT:
            await self.send(
                {
                    "command_name": "submit_sm_resp",
                    "sequence_number": seq,
                    "command_status": pdumod.ESME_RINVBNDSTS,
                    "message_id": "",
                }
            )
            return

        stub = self.store.find_match(in_pdu)
        response_cfg = (stub.response if stub else {}) or {}
        matched_id = stub.id if stub else None

        status = response_cfg.get("commandStatus", 0)
        message_id = _render_message_id(response_cfg.get("messageId"))
        delay_ms = response_cfg.get("delayMs", 0)

        if delay_ms:
            await asyncio.sleep(delay_ms / 1000.0)

        await self.send(
            {
                "command_name": "submit_sm_resp",
                "sequence_number": seq,
                "command_status": status,
                "message_id": message_id,
            }
        )

        self.store.log_request(
            {
                "sessionId": self.session_id,
                "systemId": self.system_id,
                "direction": "out",
                "commandName": "submit_sm_resp",
                "sequenceNumber": seq,
                "timestamp": time.time(),
                "matchedStubId": matched_id,
                "pdu": {"command_status": status, "message_id": message_id},
            }
        )

        receipt_cfg = response_cfg.get("deliveryReceipt")
        if status == 0 and receipt_cfg and receipt_cfg.get("enabled"):
            asyncio.create_task(self._send_delivery_receipt(in_pdu, message_id, receipt_cfg))

    async def _send_delivery_receipt(
        self,
        submit_pdu: dict[str, Any],
        message_id: str,
        receipt_cfg: dict[str, Any],
    ) -> None:
        delay_ms = receipt_cfg.get("delayMs", 1000)
        await asyncio.sleep(delay_ms / 1000.0)
        if self._closed or not self.bound or self.bind_type not in CAN_RECEIVE:
            return

        final_status = receipt_cfg.get("finalStatus", "DELIVRD")
        err = receipt_cfg.get("errorCode", 0)
        now = datetime.now(UTC)
        datestr = now.strftime("%y%m%d%H%M")
        short_message = (
            f"id:{message_id} sub:001 dlvrd:{'001' if final_status == 'DELIVRD' else '000'} "
            f"submit date:{datestr} done date:{datestr} stat:{final_status} err:{err:03d} text:"
        )

        deliver_pdu = {
            "command_name": "deliver_sm",
            "sequence_number": self.next_seq(),
            "command_status": 0,
            "service_type": "",
            "source_addr_ton": submit_pdu.get("dest_addr_ton", 0),
            "source_addr_npi": submit_pdu.get("dest_addr_npi", 0),
            "source_addr": submit_pdu.get("destination_addr", ""),
            "dest_addr_ton": submit_pdu.get("source_addr_ton", 0),
            "dest_addr_npi": submit_pdu.get("source_addr_npi", 0),
            "destination_addr": submit_pdu.get("source_addr", ""),
            "esm_class": 0x04,
            "protocol_id": 0,
            "priority_flag": 0,
            "registered_delivery": 0,
            "data_coding": 0,
            "short_message": short_message,
        }
        await self.send(deliver_pdu)
        self.store.log_request(
            {
                "sessionId": self.session_id,
                "systemId": self.system_id,
                "direction": "out",
                "commandName": "deliver_sm",
                "sequenceNumber": deliver_pdu["sequence_number"],
                "timestamp": time.time(),
                "pdu": {"short_message": short_message},
            }
        )


def _render_message_id(template: str | None) -> str:
    if not template:
        return uuid.uuid4().hex[:10]
    out = template.replace("{{randomId}}", uuid.uuid4().hex[:10])
    out = out.replace("{{seq}}", str(random.randint(1, 999999)))
    return out


def _jsonable_pdu(pdu: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pdu.items():
        if isinstance(value, bytes):
            out[key] = value.decode("latin-1", errors="replace")
        elif isinstance(value, dict) and key == "tlvs":
            out[key] = {str(tk): tv.hex() for tk, tv in value.items()}
        else:
            out[key] = value
    return out


class ProtocolServer:
    def __init__(
        self,
        store: StubStore,
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


class SocketMockPlugin(ProtocolPlugin):
    name: str = "socketmock"
    description: str = "Wiremock-style SocketMock mock service"
    default_port: int = 2775

    def create_session(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: StubStore,
        config: dict[str, Any] | None = None,
    ) -> SocketMockSession:
        return SocketMockSession(reader, writer, store, config or {})


ProtocolRegistry.register(SocketMockPlugin)


class SocketMockServer(ProtocolServer):
    def __init__(
        self,
        store: StubStore,
        host: str = "0.0.0.0",
        port: int = 2775,
        config: dict[str, Any] | None = None,
        plugin: ProtocolPlugin | None = None,
    ) -> None:
        super().__init__(store, plugin or SocketMockPlugin(), host=host, port=port, config=config)
