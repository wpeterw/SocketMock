from __future__ import annotations

import poplib

from tests.functional.socketmock.plugins._helpers import run_protocol_server


def test_pop3_server_accepts_real_pop3_client() -> None:
    with run_protocol_server("pop3") as port:
        client = poplib.POP3("127.0.0.1", port, timeout=5)
        try:
            client.user("user")
            client.pass_("pass")
            message_count, size = client.stat()
            assert isinstance(message_count, int)
            assert isinstance(size, int)
        finally:
            client.quit()
