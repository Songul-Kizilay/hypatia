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
                "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER must be",
            ):
                Bootstrap.from_process_environment()

    def test_a_named_provider_must_come_from_the_closed_vocabulary(self) -> None:
        """The list grew by one. What may not grow is what a name can be.

        `nvd` joined `crossref` and `disabled` because a provider was added, and
        the refusal above still stands for everything else. A provider name is
        never a URL and never free text: the name decides which host an approved
        step contacts.
        """
        for name in ("crossref", "nvd", "disabled"):
            with self.subTest(accepted=name):
                with patch.dict(
                    os.environ,
                    {"HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": name},
                    clear=True,
                ):
                    Bootstrap.from_process_environment()
        for name in ("https://attacker.example", "NVD ", "", "crossref,nvd"):
            with self.subTest(refused=name):
                with patch.dict(
                    os.environ,
                    {"HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": name},
                    clear=True,
                ):
                    with self.assertRaises(ValueError):
                        Bootstrap.from_process_environment()


if __name__ == "__main__":
    unittest.main()
