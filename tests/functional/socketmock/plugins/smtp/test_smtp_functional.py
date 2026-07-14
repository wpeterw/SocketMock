from __future__ import annotations

import smtplib

from tests.functional.socketmock.plugins._helpers import run_protocol_server


def test_smtp_server_accepts_real_smtp_client() -> None:
    with run_protocol_server("smtp") as port:
        with smtplib.SMTP("127.0.0.1", port, timeout=5) as client:
            client.ehlo("localhost")
            response = client.sendmail(
                "sender@example.com",
                ["recipient@example.com"],
                "Subject: functional test\n\nhello from smtp",
            )
            assert response == {}
            client.quit()
