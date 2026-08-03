"""Cognitive layer test package."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

SOURCE_COGNITION_DIR = str(SRC_DIR / "cognition")
if SOURCE_COGNITION_DIR not in __path__:
    __path__.append(SOURCE_COGNITION_DIR)

loaded_brain = sys.modules.get("brain")
if loaded_brain is not None:
    source_brain_dir = str(SRC_DIR / "brain")
    if source_brain_dir not in loaded_brain.__path__:
        loaded_brain.__path__.append(source_brain_dir)
