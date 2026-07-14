import asyncio
from typing import cast

from libs.stubs import StubStore
from socketmock.plugins.x12.session import X12Session
from tests.unit.socketmock.plugins._helpers import FakeWriter


def test_x12_session_returns_ack_for_message() -> None:
    async def run_test() -> None:
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        session = X12Session(reader, cast(asyncio.StreamWriter, writer), StubStore(), {})
        reader.feed_data(
            b"ISA*00*          *00*          *01*SENDER*01*RECEIVER*240101*0101*"
            b"U*00401*000000001*0*P*:~"
        )
        reader.feed_eof()
        await session.run()
        assert writer.closed is True
        assert writer.writes
        assert b"AK9" in writer.writes[0]

    asyncio.run(run_test())
