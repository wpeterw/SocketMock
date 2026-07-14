import asyncio
from typing import cast

from libs.stubs import StubStore
from socketmock.plugins.imap.session import IMAPServerSession
from tests.plugins._helpers import FakeWriter


def test_imap_session_handles_login_list_fetch_and_logout() -> None:
    async def run_test() -> None:
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        session = IMAPServerSession(reader, cast(asyncio.StreamWriter, writer), StubStore(), {})
        reader.feed_data(
            b"a001 LOGIN user password\r\n"
            b"a002 LIST \"\" *\r\n"
            b"a003 SELECT INBOX\r\n"
            b"a004 FETCH 1 BODY[TEXT]\r\n"
            b"a005 LOGOUT\r\n"
        )
        reader.feed_eof()
        await session.run()
        assert writer.closed is True
        assert any(b"a001 OK LOGIN completed" in payload for payload in writer.writes)
        assert any(b'* LIST (\\HasNoChildren) "/" "INBOX"' in payload for payload in writer.writes)
        assert any(b"* 1 FETCH (BODY[TEXT] {13}" in payload for payload in writer.writes)
        assert any(b"first message" in payload for payload in writer.writes)

    asyncio.run(run_test())
