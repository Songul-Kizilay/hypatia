"""Input review binding, not authorization or a live-model quality evaluation."""

import json
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from unittest.mock import Mock

from core.Exceptions import ResearchError
from research.LLMSemanticEvidenceProposalProvider import (
    LLMSemanticEvidenceProposalProvider,
)
from research.SemanticEvidenceRequest import SemanticEvidenceRequest
from tests.desktop.test_research_source_preview_panel import preview


class SemanticEvidenceRequestTests(unittest.TestCase):
    def setUp(self):
        self.first = preview(text="Literal source body")
        self.second = preview("step-2", "Another body")
        self.request = SemanticEvidenceRequest(
            "Exact question", (self.first, self.second)
        )

    def test_same_content_has_same_fingerprint_and_cannot_be_mutated(self):
        other = SemanticEvidenceRequest(
            "Exact question", (replace(self.first), replace(self.second))
        )
        self.assertEqual(self.request.content_fingerprint, other.content_fingerprint)
        self.assertEqual(len(other.content_fingerprint), 64)
        with self.assertRaises(FrozenInstanceError):
            other.question = "different"
        self.assertNotIn("Exact question", repr(other))
        self.assertNotIn(self.first.source.content, repr(other))

    def test_question_limit_order_and_membership_change_fingerprint(self):
        for changed in (
            replace(self.request, question="Exact question "),
            replace(self.request, question="Another question"),
            replace(self.request, limit=1),
            replace(self.request, previews=(self.second, self.first)),
            replace(self.request, previews=(self.first,)),
        ):
            self.assertNotEqual(
                self.request.content_fingerprint, changed.content_fingerprint
            )

    def test_every_preview_identity_field_is_bound(self):
        for name in ("execution_id", "run_id", "step_id", "requested_url"):
            original = SemanticEvidenceRequest("Q", (self.first,))
            changed = SemanticEvidenceRequest(
                "Q", (replace(self.first, **{name: "different"}),)
            )
            self.assertNotEqual(
                original.content_fingerprint, changed.content_fingerprint
            )

    def test_every_source_field_is_bound(self):
        original = SemanticEvidenceRequest("Q", (self.first,))
        for name, value in (
            ("url", "https://example.org/other"),
            ("title", "New title"),
            ("content", "Changed body"),
            ("content_type", "text/html"),
            ("content_resource", "https://example.org/other-api"),
            ("acquisition", "other"),
            ("fetched_at", self.first.source.fetched_at + timedelta(seconds=1)),
        ):
            with self.subTest(name=name):
                item = replace(
                    self.first, source=replace(self.first.source, **{name: value})
                )
                changed = SemanticEvidenceRequest("Q", (item,))
                self.assertNotEqual(
                    original.content_fingerprint, changed.content_fingerprint
                )

    def test_model_data_is_exact_and_excludes_review_provenance(self):
        data = json.loads(self.request.model_input_json())
        self.assertEqual(
            data,
            {
                "question": "Exact question",
                "sources": [
                    {"source": "0", "text": self.first.source.content},
                    {"source": "1", "text": self.second.source.content},
                ],
            },
        )
        self.assertEqual(
            self.request.source_byte_count,
            self.first.content_byte_count + self.second.content_byte_count,
        )
        self.assertNotIn(
            self.request.content_fingerprint, self.request.model_input_json()
        )

    def test_review_constructs_without_model_and_mismatch_calls_nothing(self):
        model = Mock()
        provider = LLMSemanticEvidenceProposalProvider(model)
        for changed in (
            replace(self.request, question="Different"),
            replace(self.request, limit=1),
            replace(self.request, previews=(self.first,)),
        ):
            with self.assertRaises(ResearchError):
                provider.propose_prepared(changed, self.request.content_fingerprint)
        for fingerprint in (None, "", "x" * 64):
            with self.assertRaises(ResearchError):
                provider.propose_prepared(self.request, fingerprint)
        with self.assertRaises(ResearchError):
            provider.propose_prepared(None, self.request.content_fingerprint)
        self.assertEqual(model.mock_calls, [])

    def test_prepared_call_uses_reviewed_data_and_original_source(self):
        model = Mock()
        model.generate_json.return_value = json.dumps(
            {
                "candidates": [
                    {
                        "source": "1",
                        "quote": self.second.source.content,
                        "rationale": "Review",
                    }
                ]
            }
        )
        (candidate,) = LLMSemanticEvidenceProposalProvider(model).propose_prepared(
            self.request, self.request.content_fingerprint
        )
        self.assertIs(candidate.preview, self.second)
        model.generate_json.assert_called_once()
        prompt = model.generate_json.call_args.args[0]
        self.assertEqual(
            prompt.split("UNTRUSTED_DATA\n", 1)[1], self.request.model_input_json()
        )


if __name__ == "__main__":
    unittest.main()
