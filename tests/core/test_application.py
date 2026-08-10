from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Application import HypatiaApplication
from core.Bootstrap import Bootstrap


class HypatiaApplicationTests(unittest.TestCase):
    def test_injected_bootstrap_is_preserved_and_controls_lifecycle(self) -> None:
        sentinel_bootstrap = Mock(spec=Bootstrap)

        application = HypatiaApplication(bootstrap=sentinel_bootstrap)
        application.start()
        application.stop()

        self.assertIs(application.bootstrap, sentinel_bootstrap)
        sentinel_bootstrap.initialize.assert_called_once_with()
        sentinel_bootstrap.shutdown.assert_called_once_with()
