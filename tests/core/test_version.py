from __future__ import annotations

import sys
import tomllib
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Constants import APP_VERSION
from core.Version import VERSION


class VersionTests(unittest.TestCase):
    def test_runtime_and_package_versions_are_aligned(self) -> None:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with pyproject_path.open("rb") as pyproject_file:
            package_version = tomllib.load(pyproject_file)["project"]["version"]

        self.assertEqual(VERSION.short, package_version)
        self.assertEqual(APP_VERSION, package_version)


if __name__ == "__main__":
    unittest.main()
