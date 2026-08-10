from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import main as main_module
from core.Logger import Logger
from planner.Planner import Planner


class MainTests(unittest.TestCase):
    def test_main_uses_process_environment_application_factory(self) -> None:
        logger = Mock(spec=Logger)
        planner = Mock(spec=Planner)
        plan = Mock()
        plan.task_count.return_value = 1
        planner.create_plan.return_value = plan
        container = Mock()
        container.resolve.side_effect = {
            Logger: logger,
            Planner: planner,
        }.get
        application = Mock()
        application.bootstrap.container = container

        with patch(
            "main.HypatiaApplication.from_process_environment",
            return_value=application,
        ) as application_factory:
            main_module.main()

        application_factory.assert_called_once_with()
        application.start.assert_called_once_with()
