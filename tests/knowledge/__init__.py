"""Knowledge Foundation test package."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

SOURCE_KNOWLEDGE_DIR = str(SRC_DIR / "knowledge")
if SOURCE_KNOWLEDGE_DIR not in __path__:
    __path__.append(SOURCE_KNOWLEDGE_DIR)
