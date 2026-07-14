import asyncio
from typing import cast

from libs.stubs import StubStore
from socketmock.plugins.pop3.session import POP3ServerSession
from tests.unit.socketmock.plugins._helpers import FakeWriter


def test_pop3_session_handles_auth_and_stat() -> None:
    async def run_test() -> None:
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        session = POP3ServerSession(reader, cast(asyncio.StreamWriter, writer), StubStore(), {})
        reader.feed_data(b"USER alice\r\nPASS secret\r\nSTAT\r\nQUIT\r\n")
        reader.feed_eof()
        await session.run()
        assert writer.closed is True
        assert any(b"+OK pass accepted" in payload for payload in writer.writes)
        assert any(b"+OK 2 35" in payload for payload in writer.writes)

    asyncio.run(run_test())
