from __future__ import annotations

# Template plugin module for creating new protocol plugins.
from ..base import ProtocolPlugin, ProtocolStubStore
from .session import ExampleSession


class ExamplePlugin(ProtocolPlugin):
    name: str = "example"
    description: str = "Template protocol plugin"
    default_port: int = 0

    def create_session(
        self,
        reader,
        writer,
        store: ProtocolStubStore,
        config: dict[str, object] | None = None,
    ) -> ExampleSession:
        return ExampleSession(reader, writer, store, config or {})
