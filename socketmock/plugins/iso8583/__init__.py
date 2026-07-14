from ..base import ProtocolRegistry
from .plugin import ISO8583Plugin

ProtocolRegistry.register(ISO8583Plugin)

__all__ = ["ISO8583Plugin"]
