from __future__ import annotations

import socket

from ISO8583 import ISO8583

from tests.functional.socketmock.plugins._helpers import run_protocol_server


def test_iso8583_server_accepts_real_iso8583_client() -> None:
    with run_protocol_server("iso8583") as port:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            message = ISO8583.ISO8583()
            message.setMTI("0800")
            message.setBit(11, "123456")
            message.setBit(39, "00")
            payload = message.getNetworkISO()

            sock.sendall(payload)
            response = sock.recv(4096)

            assert response[2:6] == b"0810"
            assert response[-2:] == b"00"
