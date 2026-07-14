from __future__ import annotations

import socket

from pyx12.segment import Segment

from tests.functional.socketmock.plugins._helpers import run_protocol_server


def test_x12_server_accepts_real_pyx12_segments() -> None:
    with run_protocol_server("x12") as port:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            segments = [
                Segment(
                    "ISA*00*          *00*          *01*SENDER      *01*RECEIVER    *240101*"
                    "0101*U*00401*000000001*0*P*:",
                    "~",
                    "*",
                    ">",
                ),
                Segment("GS*FA*SENDER*RECEIVER*240101*0101*1*X*004010", "~", "*", ">"),
                Segment("ST*997*000000001", "~", "*", ">"),
                Segment("AK1*HC*000000001", "~", "*", ">"),
                Segment("AK9*A*1*1*1", "~", "*", ">"),
                Segment("SE*4*000000001", "~", "*", ">"),
            ]
            payload = "".join(segment.format() for segment in segments)
            sock.sendall(payload.encode("latin-1"))
            response = sock.recv(4096)

            assert b"ISA*00*" in response
            assert b"AK9*A*1*1*1" in response
