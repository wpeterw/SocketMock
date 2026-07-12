import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from libs.stubs import ProtocolStubStore, StubStore
from socketmock.plugins import discover_plugins
from socketmock.plugins.base import ProtocolPlugin, ProtocolRegistry, ProtocolSession
from socketmock.plugins.sftp.stubs import request_matches
from socketmock.plugins.smpp.stubs import next_seq, pdu_matches
from socketmock.server import ProtocolServer, SocketMockServer


class FakeSession(ProtocolSession):
    def __init__(self) -> None:
        self.session_id = "fake"
        self.peer = ("127.0.0.1", 1234)
        self.ran = False

    async def run(self) -> None:
        self.ran = True


class FakePlugin(ProtocolPlugin):
    name = "fake"
    description = "fake protocol"
    default_port = 0

    def __init__(self) -> None:
        self.session = FakeSession()

    def create_session(
        self,
        reader: Any,
        writer: Any,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> ProtocolSession:
        return self.session


class FakeWriter:
    def write(self, data: bytes | bytearray | memoryview) -> None:
        return None

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None

    def get_extra_info(self, name: str, default: object | None = None) -> object | None:
        if name == "peername":
            return ("127.0.0.1", 1234)
        return default


def test_stub_store_returns_highest_priority_match() -> None:
    store = StubStore(matcher=lambda request, pdu: request.get("value") == pdu.get("value"))
    store.add(
        {"id": "stub-1", "priority": 5, "request": {"value": "ok"}, "response": {"status": "ok"}}
    )
    store.add(
        {
            "id": "stub-2",
            "priority": 1,
            "request": {"value": "ok"},
            "response": {"status": "fallback"},
        }
    )

    stub = store.find_match({"value": "ok"})

    assert stub is not None
    assert stub.id == "stub-1"


def test_protocol_plugin_matchers_and_server_helpers() -> None:
    discover_plugins()
    plugin = ProtocolRegistry.get("sftp")
    assert plugin is not None
    assert plugin.create_store() is not None
    assert next_seq() > 0
    assert pdu_matches(
        {"commandName": "submit_sm", "sourceAddr": {"equalTo": "src"}},
        {"command_name": "submit_sm", "source_addr": "src"},
    )
    assert not pdu_matches(
        {"commandName": "submit_sm", "sourceAddr": {"equalTo": "src"}},
        {"command_name": "submit_sm", "source_addr": "dst"},
    )
    assert request_matches(
        {"operation": "open", "path": {"contains": "/tmp"}},
        {"operation": "open", "path": "/tmp/file"},
    )
    assert not request_matches(
        {"operation": "open", "path": {"equalTo": "/tmp/file"}},
        {"operation": "open", "path": "/tmp/other"},
    )

    async def run_server_test() -> None:
        store = StubStore()
        plugin = FakePlugin()
        server = ProtocolServer(store, plugin=plugin, host="127.0.0.1", port=0, config={})
        await server._on_connect(asyncio.StreamReader(), cast(asyncio.StreamWriter, FakeWriter()))
        assert plugin.session.ran is True

        await server.start()
        assert server._server is not None
        task = asyncio.create_task(server.serve_forever())
        await asyncio.sleep(0.01)
        server._server.close()
        await server._server.wait_closed()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        socketmock_server = SocketMockServer(store, host="127.0.0.1", port=0, config={})
        assert socketmock_server.plugin is not None

    asyncio.run(run_server_test())


def test_protocol_server_serve_forever_raises_when_not_started() -> None:
    async def run_test() -> None:
        server = ProtocolServer(StubStore(), plugin=FakePlugin(), host="127.0.0.1", port=0)
        server.start = AsyncMock(return_value=None)
        with pytest.raises(RuntimeError):
            await server.serve_forever()

    asyncio.run(run_test())
