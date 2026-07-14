from libs.stubs import StubStore
from socketmock.plugins import ProtocolRegistry
from socketmock.plugins.base import ProtocolPlugin
from socketmock.plugins.hl7v2.plugin import HL7V2Plugin
from socketmock.server import ProtocolServer


def test_hl7v2_plugin_is_registered() -> None:
    plugin = ProtocolRegistry.get("hl7v2")
    assert plugin is not None
    assert isinstance(plugin, ProtocolPlugin)
    assert plugin.name == "hl7v2"
    assert plugin.default_port == 2776


def test_protocol_server_keeps_selected_plugin() -> None:
    plugin = HL7V2Plugin()
    server = ProtocolServer(StubStore(), plugin=plugin, host="127.0.0.1", port=0)
    assert server.plugin is plugin
