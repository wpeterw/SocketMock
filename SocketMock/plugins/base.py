from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProtocolPlugin(ABC):
    name: str = ""
    description: str = ""
    default_port: int = 0

    @abstractmethod
    def create_session(
        self,
        reader: Any,
        writer: Any,
        store: Any,
        config: dict[str, Any] | None = None,
    ) -> Any:
        raise NotImplementedError


class ProtocolRegistry:
    _plugins: dict[str, ProtocolPlugin] = {}

    @classmethod
    def register(cls, plugin: ProtocolPlugin | type[ProtocolPlugin]) -> ProtocolPlugin:
        if isinstance(plugin, type):
            plugin = plugin()
        cls._plugins[plugin.name] = plugin
        return plugin

    @classmethod
    def get(cls, name: str) -> ProtocolPlugin | None:
        return cls._plugins.get(name)

    @classmethod
    def available(cls) -> list[str]:
        return sorted(cls._plugins)
