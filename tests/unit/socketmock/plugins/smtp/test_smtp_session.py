import asyncio
from typing import cast

from libs.stubs import StubStore
from socketmock.plugins.smtp.session import SMTPServerSession
from tests.unit.socketmock.plugins._helpers import FakeWriter


def test_smtp_session_handles_ehlo_and_data() -> None:
    async def run_test() -> None:
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        session = SMTPServerSession(reader, cast(asyncio.StreamWriter, writer), StubStore(), {})
        reader.feed_data(b"EHLO localhost\r\nDATA\r\nSubject: test\r\n\r\nhello\r\n.\r\nQUIT\r\n")
        reader.feed_eof()
        await session.run()
        assert writer.closed is True
        assert any(b"250 socketmock hello" in payload for payload in writer.writes)
        assert any(b"250 message accepted" in payload for payload in writer.writes)

    asyncio.run(run_test())


def test_smtp_session_handles_auth_mail_rcpt_reset_and_noop() -> None:
    async def run_test() -> None:
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        session = SMTPServerSession(reader, cast(asyncio.StreamWriter, writer), StubStore(), {})
        reader.feed_data(
            b"\r\nAUTH PLAIN dGVzdA==\r\nMAIL FROM:<sender@example.com>\r\n"
            b"RCPT TO:<recipient@example.com>\r\nRSET\r\nNOOP\r\nQUIT\r\n"
        )
        reader.feed_eof()
        await session.run()
        assert writer.closed is True
        assert any(b"235 2.7.0 authentication successful" in payload for payload in writer.writes)
        assert any(b"250 mail from accepted" in payload for payload in writer.writes)
        assert any(b"250 recipient accepted" in payload for payload in writer.writes)
        assert any(b"250 reset complete" in payload for payload in writer.writes)
        assert any(b"250 noop" in payload for payload in writer.writes)

    asyncio.run(run_test())
