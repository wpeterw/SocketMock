from __future__ import annotations

import paramiko

from tests.functional.socketmock.plugins._helpers import run_protocol_server


def test_sftp_server_accepts_real_paramiko_client() -> None:
    with run_protocol_server("sftp") as port:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect("127.0.0.1", port, username="user", password="pass", timeout=5)
        try:
            sftp = client.open_sftp()
            try:
                sftp.mkdir("functional")
                with sftp.open("functional/hello.txt", "w") as handle:
                    handle.write("hello from sftp")
                with sftp.open("functional/hello.txt", "r") as handle:
                    assert handle.read() == b"hello from sftp"
                sftp.rename("functional/hello.txt", "functional/renamed.txt")
                assert sftp.stat("functional/renamed.txt").st_size == len("hello from sftp")
            finally:
                sftp.close()
        finally:
            client.close()
