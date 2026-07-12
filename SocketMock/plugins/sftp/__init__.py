from ..base import ProtocolRegistry
from .plugin import SFTPPlugin

ProtocolRegistry.register(SFTPPlugin)

__all__ = ["SFTPPlugin"]
