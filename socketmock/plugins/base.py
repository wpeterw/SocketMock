from __future__ import annotations

import importlib
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from libs.stubs import ProtocolStubStore, StubStore

logger = logging.getLogger("socketmock.plugins")


class ProtocolSession(ABC):
    @abstractmethod
    async def run(self) -> None:
        raise NotImplementedError


class ProtocolPlugin(ABC):
    name: str = ""
    description: str = ""
    default_port: int = 0

    def create_store(self) -> ProtocolStubStore:
        return StubStore()

    @abstractmethod
    def create_session(
        self,
        reader: Any,
        writer: Any,
        store: ProtocolStubStore,
        config: dict[str, Any] | None = None,
    ) -> ProtocolSession:
        raise NotImplementedError


class ProtocolRegistry:
    _plugins: dict[str, ProtocolPlugin] = {}
    _discovered = False

    @classmethod
    def register(cls, plugin: ProtocolPlugin | type[ProtocolPlugin]) -> ProtocolPlugin:
        if isinstance(plugin, type):
            plugin = plugin()
        cls._plugins[plugin.name] = plugin
        return plugin

    @classmethod
    def discover(cls) -> None:
        if cls._discovered:
            return

        package_dir = Path(__file__).resolve().parent
        for child in sorted(package_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            if not (child / "__init__.py").exists():
                continue
            module_name = f"{__package__}.{child.name}"
            try:
                module = importlib.import_module(module_name)
                if module_name in sys.modules:
                    importlib.reload(module)
            except Exception as exc:  # pragma: no cover - defensive import handling
                logger.warning("Failed to import plugin package %s: %s", module_name, exc)

        cls._discovered = True

    @classmethod
    def get(cls, name: str) -> ProtocolPlugin | None:
        cls.discover()
        return cls._plugins.get(name)

    @classmethod
    def available(cls) -> list[str]:
        cls.discover()
        return sorted(cls._plugins)
