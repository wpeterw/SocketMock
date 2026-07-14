from __future__ import annotations

# HL7 v2 protocol plugin implementation.
import asyncio
from typing import Any

from libs.stubs import StubStore

from ..base import ProtocolPlugin, ProtocolStubStore
from .session import HL7V2Session


class HL7V2Plugin(ProtocolPlugin):
    name: str = "hl7v2"
    description: str = "HL7 v2 message mock"
    default_port: int = 2776

    def create_store(self) -> ProtocolStubStore:
        return StubStore()

    def create_session(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> HL7V2Session:
        return HL7V2Session(reader, writer, store, config or {})
