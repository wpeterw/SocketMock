from ..base import ProtocolRegistry
from .plugin import IMAPPlugin

ProtocolRegistry.register(IMAPPlugin)

__all__ = ["IMAPPlugin"]
