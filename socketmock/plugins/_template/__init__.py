from ..base import ProtocolRegistry
from .plugin import ExamplePlugin

ProtocolRegistry.register(ExamplePlugin)

__all__ = ["ExamplePlugin"]
