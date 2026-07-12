
import asyncio


class FakeWriter:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes | bytearray | memoryview) -> None:
        self.writes.append(bytes(data))

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    def get_extra_info(self, name: str, default: object | None = None) -> object | None:
        if name == "peername":
            return ("127.0.0.1", 4000)
        return default


class FakeSession:
    def __init__(self) -> None:
        self.session_id = "fake"
        self.peer = ("127.0.0.1", 1234)
        self.ran = False

    async def run(self) -> None:
        self.ran = True
