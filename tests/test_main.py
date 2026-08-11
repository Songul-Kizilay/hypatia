from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import main as main_module
from brain.Brain import Brain
from core.Logger import Logger


class MainTests(unittest.TestCase):
    def test_main_uses_process_environment_application_factory(self) -> None:
        logger = Mock(spec=Logger)
        brain = Mock(spec=Brain)
        response = Mock()
        response.message = "Hello from Hypatia."
        brain.process.return_value = response
        container = Mock()
        container.resolve.side_effect = {
            Logger: logger,
            Brain: brain,
        }.get
        application = Mock()
        application.bootstrap.container = container

        with (
            patch("builtins.input", return_value="Hello Hypatia") as user_input,
            patch(
                "main.HypatiaApplication.from_process_environment",
                return_value=application,
            ) as application_factory,
        ):
            main_module.main()

        application_factory.assert_called_once_with()
        application.start.assert_called_once_with()
        user_input.assert_called_once_with("You: ")
        brain.process.assert_called_once_with("Hello Hypatia")
        logger.info.assert_called_once_with(response.message)
