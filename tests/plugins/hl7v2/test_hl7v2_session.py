import asyncio
from typing import cast

from libs.stubs import StubStore
from socketmock.plugins.hl7v2.codec import frame_message
from socketmock.plugins.hl7v2.session import HL7V2Session
from tests.plugins._helpers import FakeWriter


def test_hl7v2_session_returns_ack_for_message() -> None:
    async def run_test() -> None:
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        session = HL7V2Session(reader, cast(asyncio.StreamWriter, writer), StubStore(), {})
        reader.feed_data(
            frame_message(
                "MSH|^~\\&|APP|FAC|OTHER|FAC2|20240101120000||ADT^A01|12345|P|2.4\r"
                "PID|1||12345||DOE^JOHN||"
            )
        )
        reader.feed_eof()
        await session.run()
        assert writer.closed is True
        assert writer.writes
        assert b"MSA|AA|12345" in writer.writes[0]

    asyncio.run(run_test())
