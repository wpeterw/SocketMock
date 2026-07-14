from __future__ import annotations

import smpplib.client
import smpplib.smpp as smpp

from tests.functional.socketmock.plugins._helpers import run_protocol_server


def test_smpp_server_accepts_real_smpplib_client() -> None:
    with run_protocol_server("smpp") as port:
        client = smpplib.client.Client(
            "127.0.0.1",
            port,
            timeout=5,
            allow_unknown_opt_params=True,
        )
        try:
            client.connect()
            bind_resp = client.bind_transmitter(system_id="user", password="pass")
            assert bind_resp.command == "bind_transmitter_resp"
            assert bind_resp.status == 0

            submit_pdu = smpp.make_pdu(
                "submit_sm",
                client=client,
                service_type="",
                source_addr_ton=1,
                source_addr_npi=1,
                source_addr="1234",
                dest_addr_ton=1,
                dest_addr_npi=1,
                destination_addr="5678",
                short_message=b"hello",
                registered_delivery=0,
            )
            client.send_pdu(submit_pdu)
            submit_resp = client.read_pdu()
            assert submit_resp.command == "submit_sm_resp"
            assert submit_resp.status == 0
            assert isinstance(submit_resp.message_id, bytes)
        finally:
            try:
                client.unbind()
            except Exception:
                pass
            client.disconnect()
