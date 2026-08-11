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
        first_response = Mock()
        first_response.message = "First response."
        second_response = Mock()
        second_response.message = "Second response."
        brain.process.side_effect = [first_response, second_response]
        container = Mock()
        container.resolve.side_effect = {
            Logger: logger,
            Brain: brain,
        }.get
        application = Mock()
        application.bootstrap.container = container

        with (
            patch(
                "builtins.input",
                side_effect=["First message", "Second message", "exit"],
            ) as user_input,
            patch(
                "main.HypatiaApplication.from_process_environment",
                return_value=application,
            ) as application_factory,
        ):
            main_module.main()

        application_factory.assert_called_once_with()
        application.start.assert_called_once_with()
        application.stop.assert_called_once_with()
        self.assertEqual(user_input.call_args_list, [(("You: ",),)] * 3)
        self.assertEqual(
            brain.process.call_args_list,
            [(("First message",),), (("Second message",),)],
        )
        self.assertEqual(
            logger.info.call_args_list,
            [((first_response.message,),), ((second_response.message,),)],
        )

    def test_main_stops_application_when_input_is_interrupted(self) -> None:
        logger = Mock(spec=Logger)
        brain = Mock(spec=Brain)
        container = Mock()
        container.resolve.side_effect = {
            Logger: logger,
            Brain: brain,
        }.get
        application = Mock()
        application.bootstrap.container = container

        with (
            patch("builtins.input", side_effect=KeyboardInterrupt),
            patch(
                "main.HypatiaApplication.from_process_environment",
                return_value=application,
            ) as application_factory,
        ):
            main_module.main()

        application_factory.assert_called_once_with()
        application.start.assert_called_once_with()
        application.stop.assert_called_once_with()
        brain.process.assert_not_called()

    def test_main_stops_application_when_input_reaches_end_of_file(self) -> None:
        logger = Mock(spec=Logger)
        brain = Mock(spec=Brain)
        container = Mock()
        container.resolve.side_effect = {
            Logger: logger,
            Brain: brain,
        }.get
        application = Mock()
        application.bootstrap.container = container

        with (
            patch("builtins.input", side_effect=EOFError),
            patch(
                "main.HypatiaApplication.from_process_environment",
                return_value=application,
            ) as application_factory,
        ):
            main_module.main()

        application_factory.assert_called_once_with()
        application.start.assert_called_once_with()
        application.stop.assert_called_once_with()
        brain.process.assert_not_called()

    def test_main_ignores_whitespace_only_input(self) -> None:
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
            patch(
                "builtins.input",
                side_effect=["   ", "Hello Hypatia", "exit"],
            ) as user_input,
            patch(
                "main.HypatiaApplication.from_process_environment",
                return_value=application,
            ) as application_factory,
        ):
            main_module.main()

        application_factory.assert_called_once_with()
        application.start.assert_called_once_with()
        application.stop.assert_called_once_with()
        self.assertEqual(user_input.call_args_list, [(("You: ",),)] * 3)
        brain.process.assert_called_once_with("Hello Hypatia")
        logger.info.assert_called_once_with(response.message)
