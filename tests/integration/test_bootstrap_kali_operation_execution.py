"""Production bootstrap installs Kali execution only by explicit opt-in."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Bootstrap import Bootstrap
from core.Exceptions import ContainerError
from core.RuntimeOptIn import (
    KALI_OPERATION_EXECUTION_ENABLED_VARIABLE,
    kali_operation_execution_enabled,
)
from research.WslKaliOperationProcessAdapter import WslKaliOperationProcessAdapter
from research.WslKaliRuntimeProbe import WslKaliRuntimeProbe


class BootstrapKaliOperationExecutionTests(unittest.TestCase):
    def test_kali_operation_execution_opt_in_is_strict(self) -> None:
        self.assertFalse(kali_operation_execution_enabled({}))
        self.assertFalse(
            kali_operation_execution_enabled(
                {KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "True"}
            )
        )
        self.assertFalse(
            kali_operation_execution_enabled(
                {KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "1"}
            )
        )
        self.assertTrue(
            kali_operation_execution_enabled(
                {KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "true"}
            )
        )

    def test_default_process_environment_does_not_install_kali_process_adapter(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {"HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled"},
                clear=True,
            ),
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap.from_process_environment(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                research_run_path=temporary_path / "runs.json",
                research_source_content_path=temporary_path / "content.json",
                research_program_scope_revision_path=(
                    temporary_path / "program_scope_revisions.json"
                ),
            )
            bootstrap.initialize()

            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(WslKaliRuntimeProbe)
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(WslKaliOperationProcessAdapter)

        run.assert_not_called()
        popen.assert_not_called()

    def test_enabled_process_environment_installs_adapters_without_process_start(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                    KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "true",
                },
                clear=True,
            ),
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap.from_process_environment(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                research_run_path=temporary_path / "runs.json",
                research_source_content_path=temporary_path / "content.json",
                research_program_scope_revision_path=(
                    temporary_path / "program_scope_revisions.json"
                ),
            )
            bootstrap.initialize()

            self.assertIsInstance(
                bootstrap.container.resolve(WslKaliRuntimeProbe),
                WslKaliRuntimeProbe,
            )
            self.assertIsInstance(
                bootstrap.container.resolve(WslKaliOperationProcessAdapter),
                WslKaliOperationProcessAdapter,
            )

        run.assert_not_called()
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
