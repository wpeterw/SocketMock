from socketmock.plugins.base import ProtocolRegistry


def test_protocol_registry_discovers_builtin_plugins() -> None:
    ProtocolRegistry._plugins.clear()
    ProtocolRegistry._discovered = False

    ProtocolRegistry.discover()

    assert ProtocolRegistry.get("smpp") is not None
    assert ProtocolRegistry.get("sftp") is not None
