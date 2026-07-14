import asyncio
from typing import cast

from libs.stubs import StubStore
from socketmock.plugins.iso8583.codec import decode_message, encode_response
from socketmock.plugins.iso8583.session import ISO8583Session
from tests.plugins._helpers import FakeWriter


def test_iso8583_session_returns_response_for_message() -> None:
    async def run_test() -> None:
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        session = ISO8583Session(reader, cast(asyncio.StreamWriter, writer), StubStore(), {})
        message = encode_response({"mti": "0200", "fields": {11: b"123456"}})
        reader.feed_data(message)
        reader.feed_eof()
        await session.run()
        assert writer.closed is True
        assert writer.writes
        response = writer.writes[0]
        decoded = decode_message(response)
        assert decoded is not None
        assert decoded["mti"] == "0210"
        assert decoded["fields"].get(39) == b"00"

    asyncio.run(run_test())
