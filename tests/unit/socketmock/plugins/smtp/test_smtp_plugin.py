from libs.stubs import StubStore
from socketmock.plugins import ProtocolRegistry
from socketmock.plugins.base import ProtocolPlugin
from socketmock.plugins.smtp.plugin import SMTPPlugin
from socketmock.server import ProtocolServer


def test_smtp_plugin_is_registered() -> None:
    plugin = ProtocolRegistry.get("smtp")
    assert plugin is not None
    assert isinstance(plugin, ProtocolPlugin)
    assert plugin.name == "smtp"
    assert plugin.default_port == 2779


def test_protocol_server_keeps_selected_plugin() -> None:
    plugin = SMTPPlugin()
    server = ProtocolServer(StubStore(), plugin=plugin, host="127.0.0.1", port=0)
    assert server.plugin is plugin
