from libs.stubs import StubStore
from socketmock.plugins import ProtocolRegistry
from socketmock.plugins.base import ProtocolPlugin
from socketmock.plugins.iso8583.plugin import ISO8583Plugin
from socketmock.server import ProtocolServer


def test_iso8583_plugin_is_registered() -> None:
    plugin = ProtocolRegistry.get("iso8583")
    assert plugin is not None
    assert isinstance(plugin, ProtocolPlugin)
    assert plugin.name == "iso8583"
    assert plugin.default_port == 2778


def test_protocol_server_keeps_selected_plugin() -> None:
    plugin = ISO8583Plugin()
    server = ProtocolServer(StubStore(), plugin=plugin, host="127.0.0.1", port=0)
    assert server.plugin is plugin
