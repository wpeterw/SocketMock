from socketmock.plugins import ProtocolRegistry
from socketmock.plugins.smpp import StubStore
from socketmock.plugins.smpp.plugin import SMPPPlugin
from socketmock.server import ProtocolServer, SocketMockPlugin


def test_smpp_plugin_is_registered() -> None:
    plugin = ProtocolRegistry.get("smpp")
    assert plugin is not None
    assert isinstance(plugin, SocketMockPlugin)
    assert plugin.name == "smpp"
    assert plugin.default_port == 2775


def test_protocol_server_keeps_selected_plugin() -> None:
    store = StubStore()
    plugin = SMPPPlugin()
    server = ProtocolServer(store, plugin=plugin, host="127.0.0.1", port=0)
    assert server.plugin is plugin
