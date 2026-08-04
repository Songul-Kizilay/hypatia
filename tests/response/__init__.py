"""Test package setup for response composition services."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

source_response_dir = str(SRC_DIR / "response")
if source_response_dir not in __path__:
    __path__.append(source_response_dir)
