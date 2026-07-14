from libs.stubs import StubStore
from socketmock.plugins import ProtocolRegistry
from socketmock.plugins.base import ProtocolPlugin
from socketmock.plugins.imap.plugin import IMAPPlugin
from socketmock.server import ProtocolServer


def test_imap_plugin_is_registered() -> None:
    plugin = ProtocolRegistry.get("imap")
    assert plugin is not None
    assert isinstance(plugin, ProtocolPlugin)
    assert plugin.name == "imap"
    assert plugin.default_port == 2781


def test_protocol_server_keeps_selected_plugin() -> None:
    store = StubStore()
    plugin = IMAPPlugin()
    server = ProtocolServer(store, plugin=plugin, host="127.0.0.1", port=0)
    assert server.plugin is plugin
