from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import cast

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.HybridSemanticMemoryRanker import HybridSemanticMemoryRanker
from memory.MemoryRecord import MemoryRecord
from memory.SemanticMemoryMatch import SemanticMemoryMatch

V1_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "semantic_memory_hybrid_v1.json"
)
V2_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "semantic_memory_hybrid_v2.json"
)


class HybridSemanticMemoryRankerTests(unittest.TestCase):
    def test_versioned_evaluation_fixture_matches_expected_orders(self) -> None:
        document = json.loads(V1_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(document["schema_version"], 1)
        for case_data in cast(list[dict[str, object]], document["cases"]):
            with self.subTest(name=case_data["name"]):
                semantic_order = cast(list[str], case_data["semantic_order"])
                lexical_order = cast(list[str], case_data["lexical_order"])
                expected_order = cast(list[str], case_data["expected_order"])

                ranked = HybridSemanticMemoryRanker().rank(
                    tuple(
                        SemanticMemoryMatch(memory_id=memory_id, score=1.0)
                        for memory_id in semantic_order
                    ),
                    tuple(
                        MemoryRecord(memory_id=memory_id, content=memory_id)
                        for memory_id in lexical_order
                    ),
                )

                self.assertEqual(
                    [match.memory_id for match in ranked],
                    expected_order,
                )

    def test_curated_relevance_fixture_matches_expected_orders(self) -> None:
        document = json.loads(V2_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(
            document["evaluation_scope"], "explicit semantic recall rank-only"
        )
        for case_data in cast(list[dict[str, object]], document["cases"]):
            with self.subTest(name=case_data["name"]):
                query = cast(str, case_data["query"])
                semantic_order = cast(list[str], case_data["semantic_order"])
                lexical_order = cast(list[str], case_data["lexical_order"])
                expected_order = cast(list[str], case_data["expected_order"])
                relevance_rationale = cast(
                    dict[str, str], case_data["relevance_rationale"]
                )
                candidate_ids = set(semantic_order).union(lexical_order)

                self.assertIsInstance(query, str)
                self.assertTrue(query.strip())
                self.assertEqual(len(expected_order), len(set(expected_order)))
                self.assertEqual(set(expected_order), candidate_ids)
                self.assertEqual(set(relevance_rationale), candidate_ids)
                self.assertTrue(
                    all(rationale.strip() for rationale in relevance_rationale.values())
                )

                ranked = HybridSemanticMemoryRanker().rank(
                    tuple(
                        SemanticMemoryMatch(memory_id=memory_id, score=1.0)
                        for memory_id in semantic_order
                    ),
                    tuple(
                        MemoryRecord(memory_id=memory_id, content=memory_id)
                        for memory_id in lexical_order
                    ),
                )

                self.assertEqual(
                    [match.memory_id for match in ranked],
                    expected_order,
                )

    def test_limit_applies_after_fusion_and_preserves_no_duplicates(self) -> None:
        ranked = HybridSemanticMemoryRanker().rank(
            (
                SemanticMemoryMatch(memory_id="shared", score=1.0),
                SemanticMemoryMatch(memory_id="semantic-only", score=0.5),
            ),
            (
                MemoryRecord(memory_id="shared", content="shared"),
                MemoryRecord(memory_id="lexical-only", content="lexical-only"),
            ),
            limit=2,
        )

        self.assertEqual(
            [match.memory_id for match in ranked], ["shared", "lexical-only"]
        )
        self.assertEqual(len({match.memory_id for match in ranked}), len(ranked))

    def test_rejects_invalid_rank_constants_and_limits(self) -> None:
        for rank_constant in (0, -1, True):
            with self.subTest(rank_constant=rank_constant):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    HybridSemanticMemoryRanker(rank_constant)

        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            HybridSemanticMemoryRanker().rank((), (), limit=-1)


if __name__ == "__main__":
    unittest.main()
