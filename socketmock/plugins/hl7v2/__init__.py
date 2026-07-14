from ..base import ProtocolRegistry
from .plugin import HL7V2Plugin

ProtocolRegistry.register(HL7V2Plugin)

__all__ = ["HL7V2Plugin"]
