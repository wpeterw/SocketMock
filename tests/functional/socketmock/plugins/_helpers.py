from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def run_protocol_server(protocol: str) -> Iterator[int]:
    port = _find_free_port()
    cmd = [
        sys.executable,
        "-m",
        "socketmock.app",
        "--protocol",
        protocol,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--admin-port",
        "0",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            if proc.poll() is not None:
                raise AssertionError(f"{protocol} server exited early with code {proc.returncode}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError(f"{protocol} server did not start on port {port}")
        yield port
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
