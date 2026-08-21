"""Contract for the one-way cooperative cancellation signal."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.CancellationSignal import CancellationSignal


class CancellationSignalTests(unittest.TestCase):
    def test_cancel_is_one_way_and_idempotent(self) -> None:
        signal = CancellationSignal()

        self.assertFalse(signal.is_cancelled())
        signal.cancel()
        signal.cancel()

        self.assertTrue(signal.is_cancelled())


if __name__ == "__main__":
    unittest.main()
