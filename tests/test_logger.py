"""Unit tests for Hypatia logging."""

from __future__ import annotations

import io
import logging
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Logger import Logger


class LoggerTests(unittest.TestCase):
    """Verify the application logger emits consistently formatted records."""

    def test_log_format_contains_timestamp_level_name_and_message(self) -> None:
        stream = io.StringIO()
        logger_wrapper = Logger()
        logger = logger_wrapper.logger
        handler = logging.StreamHandler(stream)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )

        original_handlers = logger.handlers[:]
        original_propagate = logger.propagate
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.propagate = False

        try:
            logger_wrapper.info("test message")
        finally:
            logger.handlers.clear()
            logger.handlers.extend(original_handlers)
            logger.propagate = original_propagate

        output = stream.getvalue()

        self.assertIn("INFO", output)
        self.assertIn("Hypatia", output)
        self.assertIn("test message", output)
        self.assertRegex(output, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
