from ..base import ProtocolRegistry
from .plugin import SMTPPlugin

ProtocolRegistry.register(SMTPPlugin)

__all__ = ["SMTPPlugin"]
