"""Environment wiring tests for explicit Crossref source discovery."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.Bootstrap import Bootstrap
from core.Exceptions import ContainerError
from research.CrossrefResearchSourceDiscoveryProvider import (
    CrossrefResearchSourceDiscoveryProvider,
)


class BootstrapResearchSourceDiscoveryTests(unittest.TestCase):
    def test_process_environment_enables_crossref_without_network_access(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(os.environ, {}, clear=True),
        ):
            root = Path(temporary_directory)
            bootstrap = Bootstrap.from_process_environment(
                memory_path=root / "memory.json",
                session_path=root / "sessions.json",
                knowledge_relation_path=root / "relations.json",
                research_run_path=root / "research-runs.json",
            )
            bootstrap.initialize()

            provider = bootstrap.container.resolve(
                CrossrefResearchSourceDiscoveryProvider
            )

        self.assertEqual(provider.provider_name, "crossref-rest-v1")

    def test_process_environment_can_disable_network_discovery(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {"HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled"},
                clear=True,
            ),
        ):
            root = Path(temporary_directory)
            bootstrap = Bootstrap.from_process_environment(
                memory_path=root / "memory.json",
                session_path=root / "sessions.json",
                knowledge_relation_path=root / "relations.json",
                research_run_path=root / "research-runs.json",
            )
            bootstrap.initialize()

            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(CrossrefResearchSourceDiscoveryProvider)

    def test_invalid_process_provider_is_rejected_before_bootstrap(self) -> None:
        with patch.dict(
            os.environ,
            {"HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "unknown"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "must be 'crossref' or 'disabled'",
            ):
                Bootstrap.from_process_environment()


if __name__ == "__main__":
    unittest.main()
