import asyncio
from typing import cast

from SocketMock.plugins.smpp import codec as smpp_codec
from SocketMock.plugins.smpp.session import SMPPSession
from SocketMock.plugins.smpp.stubs import StubStore
from tests.plugins._helpers import FakeWriter


def test_smpp_session_handles_bind_submit_unbind_and_receipt() -> None:
    async def run_test() -> None:
        store = StubStore()
        writer = FakeWriter()
        session = SMPPSession(
            asyncio.StreamReader(),
            cast(asyncio.StreamWriter, writer),
            store,
            {"credentials": {"sys": "pwd"}},
        )

        await session._handle_pdu(
            {
                "command_name": "bind_transceiver",
                "sequence_number": 1,
                "system_id": "sys",
                "password": "pwd",
            }
        )
        assert session.bound is True
        assert session.system_id == "sys"
        assert writer.writes

        await session._handle_pdu(
            {
                "command_name": "submit_sm",
                "sequence_number": 2,
                "source_addr": "src",
                "destination_addr": "dst",
                "short_message": b"hello",
            }
        )
        assert any(
            smpp_codec.decode_pdu(packet)["command_name"] == "submit_sm_resp"
            for packet in writer.writes
        )

        await session._handle_pdu({"command_name": "query_sm", "sequence_number": 3})
        assert any(
            smpp_codec.decode_pdu(packet)["command_name"] == "generic_nack"
            for packet in writer.writes
        )

        store.add(
            {
                "request": {"commandName": "submit_sm"},
                "response": {
                    "commandStatus": 0,
                    "deliveryReceipt": {"enabled": True, "delayMs": 0, "finalStatus": "DELIVRD"},
                },
            }
        )
        await session._handle_submit_sm(
            {
                "command_name": "submit_sm",
                "sequence_number": 4,
                "source_addr": "src",
                "destination_addr": "dst",
                "short_message": b"receipt",
            }
        )
        await asyncio.sleep(0.01)
        assert any(
            smpp_codec.decode_pdu(packet)["command_name"] == "deliver_sm"
            for packet in writer.writes
        )

        await session._handle_pdu({"command_name": "unbind", "sequence_number": 5})
        assert session.bound is False
        assert writer.closed is True

    asyncio.run(run_test())


def test_smpp_session_run_processes_packets_from_reader() -> None:
    async def run_test() -> None:
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        session = SMPPSession(reader, cast(asyncio.StreamWriter, writer), StubStore(), {})
        reader.feed_data(
            smpp_codec.encode_pdu({"command_name": "enquire_link", "sequence_number": 1})
        )
        reader.feed_eof()
        await session.run()
        assert writer.closed is True
        assert writer.writes

    asyncio.run(run_test())
