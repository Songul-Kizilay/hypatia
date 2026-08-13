from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemoryCandidateParser import (
    parse_learned_memory_candidate_batch,
)


class LearnedMemoryCandidateParserTests(unittest.TestCase):
    def test_parses_exact_empty_candidate_payload_with_exact_source(self) -> None:
        source_text = "  Merhaba nasılsın?  "

        batch = parse_learned_memory_candidate_batch(
            source_text=source_text,
            payload='{"candidates":[]}',
        )

        self.assertEqual(batch.source_text, source_text)
        self.assertEqual(batch.candidates, ())

    def test_rejects_malformed_or_unsupported_payloads_with_exact_error(self) -> None:
        invalid_payloads = (
            "",
            "not json",
            "[]",
            "{}",
            '{"candidates":null}',
            '{"candidates":{}}',
            '{"candidates":[1]}',
            '{"candidates":[{"kind":"preference"}]}',
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(
                    ValueError,
                    r"^Learned memory candidate payload invalid\.$",
                ):
                    parse_learned_memory_candidate_batch(
                        source_text="source",
                        payload=payload,
                    )
