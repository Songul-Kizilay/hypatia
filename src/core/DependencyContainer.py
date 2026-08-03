"""Minimal dependency container for the Hypatia runtime."""

from __future__ import annotations

from typing import Any

from core.Exceptions import ContainerError


class DependencyContainer:
    """Stores initialized shared dependencies by a stable name."""

    def __init__(self) -> None:
        self._services: dict[Any, Any] = {}

    def register(self, service: Any, instance: Any | None = None) -> None:
        """Register a service by its type or by an explicit key."""
        if instance is None:
            self._services[type(service)] = service
            return

        self._services[service] = instance

    def resolve(self, key: Any) -> Any:
        try:
            return self._services[key]
        except KeyError as error:
            raise ContainerError(f"Dependency is not registered: {key}") from error
