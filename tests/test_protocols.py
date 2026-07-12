from SocketMock.plugins import ProtocolRegistry
from SocketMock.server import ProtocolServer, SocketMockPlugin
from SocketMock.stubs import StubStore


def test_socketmock_plugin_is_registered() -> None:
    plugin = ProtocolRegistry.get("socketmock")
    assert plugin is not None
    assert isinstance(plugin, SocketMockPlugin)
    assert plugin.name == "socketmock"
    assert plugin.default_port == 2775


def test_protocol_server_keeps_selected_plugin() -> None:
    store = StubStore()
    plugin = SocketMockPlugin()
    server = ProtocolServer(store, plugin=plugin, host="127.0.0.1", port=0)
    assert server.plugin is plugin
