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


def test_pop3_session_covers_more_commands() -> None:
    async def run_test() -> None:
        writer = FakeWriter()
        session = POP3ServerSession(
            asyncio.StreamReader(), cast(asyncio.StreamWriter, writer), StubStore(), {}
        )

        await session._handle_command("STAT")
        await session._handle_command("")
        await session._handle_command("USER alice")
        await session._handle_command("PASS secret")
        await session._handle_command("STAT")
        await session._handle_command("LIST")
        await session._handle_command("LIST 1")
        await session._handle_command("LIST 99")
        await session._handle_command("RETR 1")
        await session._handle_command("RETR 99")
        await session._handle_command("DELE 1")
        await session._handle_command("DELE 99")
        await session._handle_command("RSET")
        await session._handle_command("NOOP")
        await session._handle_command("QUIT")
        await session._handle_command("BOGUS")

        assert writer.writes

    asyncio.run(run_test())
