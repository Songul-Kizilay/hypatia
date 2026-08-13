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

    def test_parses_one_valid_candidate_with_exact_content_and_source(self) -> None:
        source_text = "  Ben Python tercih ediyorum.  "

        batch = parse_learned_memory_candidate_batch(
            source_text=source_text,
            payload=(
                '{"candidates":['
                '{"kind":"preference",'
                '"key":"preferred_language",'
                '"value":"  Python  "}'
                "]}"
            ),
        )

        self.assertEqual(batch.source_text, source_text)
        self.assertEqual(len(batch.candidates), 1)

        candidate = batch.candidates[0]
        self.assertEqual(candidate.source_text, source_text)
        self.assertEqual(candidate.memory.kind, "preference")
        self.assertEqual(candidate.memory.key, "preferred_language")
        self.assertEqual(candidate.memory.value, "  Python  ")

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
            ('{"candidates":[' '{"kind":"unknown","key":"key","value":"value"}' "]}"),
            ('{"candidates":[' '{"kind":1,"key":"key","value":"value"}' "]}"),
            ('{"candidates":[' '{"key":"key","value":"value"}' "]}"),
            ('{"candidates":[' '{"kind":"preference","value":"value"}' "]}"),
            ('{"candidates":[' '{"kind":"preference","key":"key"}' "]}"),
            ('{"candidates":[' '{"kind":"preference","key":1,"value":"value"}' "]}"),
            ('{"candidates":[' '{"kind":"preference","key":"key","value":1}' "]}"),
            (
                '{"candidates":['
                '{"kind":"preference","key":"key","value":"value",'
                '"extra":"field"}'
                "]}"
            ),
            '{"candidates":[],"extra":"field"}',
            (
                '{"candidates":['
                '{"kind":"preference","key":"first","value":"Python"},'
                '{"kind":"goal","key":"second","value":"Rust"}'
                "]}"
            ),
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
