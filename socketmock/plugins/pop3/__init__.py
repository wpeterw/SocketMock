from ..base import ProtocolRegistry
from .plugin import POP3Plugin

ProtocolRegistry.register(POP3Plugin)

__all__ = ["POP3Plugin"]
