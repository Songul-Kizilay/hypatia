"""Exact prior-observation selections become inert revalidation plans, not authority."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from brain.BrainRequest import BrainRequest
from cognition.ResearchPlanPreviewApplicationService import (
    ResearchPlanPreviewApplicationService,
)
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRevalidationDraft import preview_source_revalidation
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.SourceRevalidationStepBinding import SourceRevalidationStepBinding
from response.ResponseComposer import ResponseComposer

QUESTION = "Is the advisory content still what this run recorded?"
REQUESTED_URL = "https://example.test/advisory"
FETCHED_AT = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)


class ContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


class RevalidationDraftTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "runs.json"
        self.manager = ResearchRunManager(JsonFileResearchRunStore(self.path))
        self.knowledge = KnowledgeEngine()
        self.content = ContentStore()
        run = self.manager.create(QUESTION)
        self.run_id = run.run_id
        accepted = ResearchSourceAcceptanceService(
            self.knowledge, self.manager, self.content  # type: ignore[arg-type]
        ).accept(
            ResearchSource(
                url=REQUESTED_URL,
                title="Advisory",
                content="Version one.",
                content_type="text/plain",
                fetched_at=FETCHED_AT,
            ),
            self.run_id,
            requested_url=REQUESTED_URL,
        )
        assert accepted.accepted and accepted.document_id is not None
        self.run = self.manager.get(self.run_id)
        self.observation_id = self.run.sources[0].observation_id
        assert self.observation_id is not None

    def test_selected_prior_observation_produces_the_expected_binding(self) -> None:
        before = self.path.read_bytes()

        result = preview_source_revalidation(self.run, self.observation_id)

        self.assertIsNotNone(result.plan)
        assert result.plan is not None
        (step,) = result.plan.steps
        self.assertIs(step.capability, ResearchPlanStepCapability.SOURCE_REVALIDATION)
        self.assertEqual(
            step.source_revalidation_binding,
            SourceRevalidationStepBinding(
                self.run_id,
                self.observation_id,
                REQUESTED_URL,
                len(self.run.sources) + 1,
            ),
        )
        self.assertEqual(before, self.path.read_bytes())

    def test_missing_blank_or_unknown_observation_is_refused(self) -> None:
        for observation_id in ("", "   ", "no-such-observation", None):
            with self.subTest(observation_id=observation_id):
                self.assertIsNone(
                    preview_source_revalidation(
                        self.run, observation_id  # type: ignore[arg-type]
                    ).plan
                )

    def test_a_legacy_record_missing_requested_url_is_refused(self) -> None:
        legacy_source = replace(self.run.sources[0], requested_url=None)
        run = replace(self.run, sources=(legacy_source,))

        self.assertIsNone(preview_source_revalidation(run, self.observation_id).plan)

    def test_a_legacy_record_missing_observation_id_can_never_be_named(self) -> None:
        legacy_source = replace(self.run.sources[0], observation_id=None)
        run = replace(self.run, sources=(legacy_source,))

        # No observation ID names a record whose own observation ID is None:
        # the legacy record is simply unreachable, not specially rejected.
        self.assertIsNone(preview_source_revalidation(run, self.observation_id).plan)

    def test_a_closed_or_wrong_run_is_refused(self) -> None:
        for run in (
            replace(self.run, status=ResearchRunStatus.COMPLETED),
            self.manager.create("A different question entirely?"),
        ):
            self.assertIsNone(
                preview_source_revalidation(run, self.observation_id).plan
            )

    def test_a_terminal_run_is_refused_cleanly_at_preview_time(self) -> None:
        """`preview_source_revalidation`'s own terminal-run refusal, isolated.

        This is deliberately the same shape of run as
        `SourceRevalidationStepOperation.run()`'s own independent terminal-run
        check would see at execution time -- a run whose sources are otherwise
        completely valid, only its status is terminal -- so the preview-layer
        refusal is proven to fire on its own, not merely alongside the
        unrelated "wrong run" case above.
        """
        terminal_run = replace(self.run, status=ResearchRunStatus.COMPLETED)

        result = preview_source_revalidation(terminal_run, self.observation_id)

        self.assertFalse(result.allowed)
        self.assertIsNone(result.plan)
        self.assertIn("open research run", result.reason)

    def test_an_empty_sources_tuple_is_refused_cleanly(self) -> None:
        run = replace(self.run, sources=())

        result = preview_source_revalidation(run, self.observation_id)

        self.assertFalse(result.allowed)
        self.assertIsNone(result.plan)
        self.assertIn("does not belong to this research run", result.reason)

    def test_digest_is_deterministic_and_binds_run_observation_url_and_count(
        self,
    ) -> None:
        def digest(run=self.run, observation_id=self.observation_id):
            return plan_digest(preview_source_revalidation(run, observation_id).plan)

        expected = digest()
        self.assertEqual(expected, digest())
        other_run = self.manager.create("Another question?")
        self.assertNotEqual(
            expected,
            digest(
                run=replace(other_run, sources=self.run.sources),
                observation_id=self.observation_id,
            ),
        )
        widened = self.manager.add_source(
            self.run_id,
            ResearchSource(
                url="https://example.test/other",
                title="Other",
                content="Other content.",
                content_type="text/plain",
                fetched_at=FETCHED_AT,
            ),
            "document-other",
            requested_url="https://example.test/other",
        )
        self.assertNotEqual(expected, digest(run=widened))

    def test_application_loads_current_state_and_rejects_implicit_overrides(
        self,
    ) -> None:
        service = ResearchPlanPreviewApplicationService(
            ResponseComposer(), research_run_manager=self.manager
        )
        metadata = {
            "intent": "research_revalidation_step_preview",
            "research_run_id": self.run_id,
            "prior_observation_id": self.observation_id,
        }
        before = self.path.read_bytes()
        self.assertTrue(
            service.process_draft_preview(
                BrainRequest("preview", metadata=metadata)
            ).success
        )
        for extra in (
            {"research_plan_question": "override"},
            {"research_plan_steps": ()},
            {"research_plan_constraints": ()},
            {"research_plan_restriction": None},
            {"research_plan_target_binding": None},
            {"research_run_id": "missing"},
        ):
            self.assertFalse(
                service.process_draft_preview(
                    BrainRequest("preview", metadata={**metadata, **extra})
                ).success
            )
        self.assertEqual(before, self.path.read_bytes())

    def test_missing_storage_and_malformed_requests_fail_closed(self) -> None:
        request = BrainRequest(
            "preview", metadata={"intent": "research_revalidation_step_preview"}
        )
        for service in (
            ResearchPlanPreviewApplicationService(ResponseComposer()),
            ResearchPlanPreviewApplicationService(
                ResponseComposer(), research_run_manager=self.manager
            ),
        ):
            self.assertFalse(service.process_draft_preview(request).success)


if __name__ == "__main__":
    unittest.main()
