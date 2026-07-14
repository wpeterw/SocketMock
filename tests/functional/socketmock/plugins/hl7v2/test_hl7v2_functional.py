from __future__ import annotations

import socket

from hl7apy.core import Message

from tests.functional.socketmock.plugins._helpers import run_protocol_server


def test_hl7v2_server_accepts_real_hl7apy_client() -> None:
    with run_protocol_server("hl7v2") as port:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            message = Message("ORM_O01")
            message.msh.msh_3 = "APP"
            message.msh.msh_4 = "FAC"
            message.msh.msh_7 = "20260714121347"
            message.msh.msh_9 = "ORM^O01"
            message.msh.msh_10 = "123"
            payload = message.to_mllp().encode("latin-1")

            sock.sendall(payload)
            response = sock.recv(4096)

            assert b"MSA|AA|123" in response
            assert b"ACK" in response
