from libs.stubs import StubStore
from socketmock.plugins import ProtocolRegistry
from socketmock.plugins.base import ProtocolPlugin
from socketmock.plugins.x12.plugin import X12Plugin
from socketmock.server import ProtocolServer


def test_x12_plugin_is_registered() -> None:
    plugin = ProtocolRegistry.get("x12")
    assert plugin is not None
    assert isinstance(plugin, ProtocolPlugin)
    assert plugin.name == "x12"
    assert plugin.default_port == 2777


def test_protocol_server_keeps_selected_plugin() -> None:
    plugin = X12Plugin()
    server = ProtocolServer(StubStore(), plugin=plugin, host="127.0.0.1", port=0)
    assert server.plugin is plugin
