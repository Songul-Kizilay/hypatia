"""
Logging system.
"""

from __future__ import annotations

import logging


class Logger:

    def __init__(self) -> None:

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(message)s",
        )

        self.logger = logging.getLogger("Hypatia")

    def info(self, message: str) -> None:

        self.logger.info(message)

    def warning(self, message: str) -> None:

        self.logger.warning(message)

    def error(self, message: str) -> None:

        self.logger.error(message)