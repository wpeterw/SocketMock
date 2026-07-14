from __future__ import annotations

import imaplib

from tests.functional.socketmock.plugins._helpers import run_protocol_server


def test_imap_server_accepts_real_imap_client() -> None:
    with run_protocol_server("imap") as port:
        with imaplib.IMAP4("127.0.0.1", port, timeout=5) as client:
            status, _ = client.login("user", "pass")
            assert status == "OK"
            status, _ = client.list()
            assert status == "OK"
            client.logout()
