"""
Global constants.
"""

from pathlib import Path

from core.Version import VERSION

APP_NAME = "Hypatia"

APP_VERSION = VERSION.short

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

SRC_DIR = ROOT_DIR / "src"

DATA_DIR = ROOT_DIR / "data"

CONFIG_DIR = ROOT_DIR / "configs"

LOG_DIR = ROOT_DIR / "logs"

MODELS_DIR = ROOT_DIR / "models"

KNOWLEDGE_DIR = ROOT_DIR / "knowledge"