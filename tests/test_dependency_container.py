"""Unit tests for DependencyContainer."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.DependencyContainer import DependencyContainer
from core.Exceptions import ContainerError


class SampleService:
    pass


class DependencyContainerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = DependencyContainer()

    def test_registers_and_resolves_service_by_type(self) -> None:
        service = SampleService()
        self.container.register(service)

        self.assertIs(self.container.resolve(SampleService), service)

    def test_registers_and_resolves_service_by_explicit_key(self) -> None:
        service = SampleService()
        self.container.register("sample", service)

        self.assertIs(self.container.resolve("sample"), service)

    def test_latest_registration_replaces_previous_service(self) -> None:
        first = SampleService()
        second = SampleService()
        self.container.register(first)
        self.container.register(second)

        self.assertIs(self.container.resolve(SampleService), second)

    def test_resolve_missing_service_raises_container_error(self) -> None:
        with self.assertRaises(ContainerError):
            self.container.resolve(SampleService)

    def test_explicit_key_can_be_any_hashable_value(self) -> None:
        marker = object()
        service = SampleService()
        self.container.register(marker, service)

        self.assertIs(self.container.resolve(marker), service)
