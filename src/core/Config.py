"""
Configuration manager.
"""

from __future__ import annotations

import json
from typing import Any

from core.Constants import CONFIG_DIR


class Config:

    def __init__(self) -> None:

        self._config: dict[str, Any] = {}

        self.load()

    def load(self) -> None:

        config_file = CONFIG_DIR / "development" / "config.json"

        if config_file.exists():

            with open(config_file, encoding="utf-8-sig") as file:

                self._config = json.load(file)

    def get(self, key: str, default: Any = None) -> Any:

        return self._config.get(key, default)
