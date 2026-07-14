from ..base import ProtocolRegistry
from .plugin import X12Plugin

ProtocolRegistry.register(X12Plugin)

__all__ = ["X12Plugin"]
