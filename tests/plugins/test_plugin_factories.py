import asyncio
from typing import Any

import pytest

from libs.stubs import StubStore
from socketmock.plugins.base import ProtocolPlugin, ProtocolSession, ProtocolStubStore
from socketmock.plugins.hl7v2.plugin import HL7V2Plugin
from socketmock.plugins.hl7v2.session import HL7V2Session
from socketmock.plugins.imap.plugin import IMAPPlugin
from socketmock.plugins.imap.session import IMAPServerSession
from socketmock.plugins.iso8583.plugin import ISO8583Plugin
from socketmock.plugins.iso8583.session import ISO8583Session
from socketmock.plugins.pop3.plugin import POP3Plugin
from socketmock.plugins.pop3.session import POP3ServerSession
from socketmock.plugins.sftp.plugin import SFTPPlugin
from socketmock.plugins.sftp.session import SFTPSession
from socketmock.plugins.smpp.plugin import SMPPPlugin
from socketmock.plugins.smpp.session import SMPPSession
from socketmock.plugins.smtp.plugin import SMTPPlugin
from socketmock.plugins.smtp.session import SMTPServerSession
from socketmock.plugins.x12.plugin import X12Plugin
from socketmock.plugins.x12.session import X12Session
from tests.plugins._helpers import FakeWriter


class DummySession(ProtocolSession):
    async def run(self) -> None:
        await super().run()


class DummyPlugin(ProtocolPlugin):
    name = "dummy"
    description = "dummy"

    def create_session(
        self,
        reader: Any,
        writer: Any,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> ProtocolSession:
        return super().create_session(reader, writer, store, config)


@pytest.mark.parametrize(
    ("plugin", "session_type"),
    [
        (SMPPPlugin(), SMPPSession),
        (SFTPPlugin(), SFTPSession),
        (HL7V2Plugin(), HL7V2Session),
        (X12Plugin(), X12Session),
        (ISO8583Plugin(), ISO8583Session),
        (SMTPPlugin(), SMTPServerSession),
        (POP3Plugin(), POP3ServerSession),
        (IMAPPlugin(), IMAPServerSession),
    ],
)
def test_plugin_factories_create_store_and_session(plugin, session_type) -> None:
    store = plugin.create_store()
    assert store is not None

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        session = plugin.create_session(reader, writer, store, {})
    finally:
        asyncio.set_event_loop(None)
        loop.close()

    assert isinstance(session, session_type)
    assert session.store is store


def test_base_protocol_interfaces_raise_not_implemented() -> None:
    session = DummySession()

    with pytest.raises(NotImplementedError):
        asyncio.run(session.run())

    plugin = DummyPlugin()

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        with pytest.raises(NotImplementedError):
            plugin.create_session(asyncio.StreamReader(), FakeWriter(), StubStore(), {})
    finally:
        asyncio.set_event_loop(None)
        loop.close()
