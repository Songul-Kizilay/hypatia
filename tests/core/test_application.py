from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Application import HypatiaApplication
from core.Bootstrap import Bootstrap


class HypatiaApplicationTests(unittest.TestCase):
    def test_process_environment_factory_preserves_bootstrap_without_lifecycle(
        self,
    ) -> None:
        sentinel_bootstrap = Mock(spec=Bootstrap)

        with patch(
            "core.Application.Bootstrap.from_process_environment",
            return_value=sentinel_bootstrap,
        ) as bootstrap_factory:
            application = HypatiaApplication.from_process_environment()

        bootstrap_factory.assert_called_once_with(defer_mission_recovery=False)
        self.assertIs(application.bootstrap, sentinel_bootstrap)
        sentinel_bootstrap.initialize.assert_not_called()
        sentinel_bootstrap.shutdown.assert_not_called()

    def test_injected_bootstrap_is_preserved_and_controls_lifecycle(self) -> None:
        sentinel_bootstrap = Mock(spec=Bootstrap)

        application = HypatiaApplication(bootstrap=sentinel_bootstrap)
        application.start()
        application.stop()

        self.assertIs(application.bootstrap, sentinel_bootstrap)
        sentinel_bootstrap.initialize.assert_called_once_with()
        sentinel_bootstrap.shutdown.assert_called_once_with()

    def test_process_environment_factory_passes_explicit_local_data_paths(
        self,
    ) -> None:
        sentinel_bootstrap = Mock(spec=Bootstrap)
        memory_path = Path("C:/Hypatia/memory/memory.json")
        session_path = Path("C:/Hypatia/sessions/sessions.json")
        relation_path = Path("C:/Hypatia/knowledge/relations.json")
        research_run_path = Path("C:/Hypatia/research/runs.json")
        research_source_content_path = Path("C:/Hypatia/research/content.json")
        research_program_scope_revision_path = Path(
            "C:/Hypatia/research/program_scope_revisions.json"
        )

        with patch(
            "core.Application.Bootstrap.from_process_environment",
            return_value=sentinel_bootstrap,
        ) as bootstrap_factory:
            application = HypatiaApplication.from_process_environment(
                memory_path=memory_path,
                session_path=session_path,
                knowledge_relation_path=relation_path,
                research_run_path=research_run_path,
                research_source_content_path=research_source_content_path,
                research_program_scope_revision_path=(
                    research_program_scope_revision_path
                ),
            )

        bootstrap_factory.assert_called_once_with(
            memory_path=memory_path,
            session_path=session_path,
            knowledge_relation_path=relation_path,
            research_run_path=research_run_path,
            research_source_content_path=research_source_content_path,
            research_program_scope_revision_path=research_program_scope_revision_path,
            defer_mission_recovery=False,
        )
        self.assertIs(application.bootstrap, sentinel_bootstrap)
