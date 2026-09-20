"""Deterministic contract coverage for one explicit source revalidation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import KnowledgeError, ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceRevalidationOutcome import ResearchSourceRevalidationOutcome
from research.SourceRevalidationStepBinding import SourceRevalidationStepBinding
from research.SourceRevalidationStepOperation import SourceRevalidationStepOperation

REQUESTED_URL = "https://example.test/advisory"
FINAL_URL = "https://cdn.example.test/advisory.txt"
EARLIER = datetime(2026, 9, 18, tzinfo=UTC)
LATER = EARLIER + timedelta(days=1)


class _Fetcher:
    def __init__(
        self, content: str = "Version two.", error: Exception | None = None
    ) -> None:
        self.content = content
        self.error = error
        self.urls: list[str] = []

    def fetch(self, url: str) -> ResearchSource:
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        return ResearchSource(
            url=FINAL_URL,
            title="Advisory",
            content=self.content,
            content_type="text/plain",
            fetched_at=LATER,
        )


class _ContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


class SourceRevalidationStepOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(root / "runs.json"),
            observation_id_factory=iter(("OA", "OB", "OC")).__next__,
            revalidation_id_factory=lambda: "relation-1",
        )
        self.knowledge = KnowledgeEngine()
        self.content = _ContentStore()
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge, self.manager, self.content  # type: ignore[arg-type]
        )
        self.run_id = self.manager.create("What does the advisory say?").run_id
        self.manager.add_source(
            self.run_id,
            ResearchSource(
                url=FINAL_URL,
                title="Advisory",
                content="Version one.",
                content_type="text/plain",
                fetched_at=EARLIER,
            ),
            "document-one",
            requested_url=REQUESTED_URL,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _step(
        self, *, requested_url: str = REQUESTED_URL, max_sources: int = 2
    ) -> ResearchPlanStep:
        return ResearchPlanStep(
            "revalidate-1",
            "Re-fetch the exact recorded source observation once.",
            capability=Cap.SOURCE_REVALIDATION,
            source_revalidation_binding=SourceRevalidationStepBinding(
                self.run_id, "OA", requested_url, max_sources
            ),
        )

    def _operation(self, fetcher: _Fetcher) -> SourceRevalidationStepOperation:
        return SourceRevalidationStepOperation(
            fetcher, self.acceptance, self.manager  # type: ignore[arg-type]
        )

    def _context(self) -> ResearchPlanExecutionContext:
        return ResearchPlanExecutionContext(
            research_run_id=self.run_id, execution_id="execution-1"
        )

    def test_revalidates_the_exact_prior_observation_and_records_changed_content(
        self,
    ) -> None:
        fetcher = _Fetcher()
        before = self.manager.get(self.run_id)

        result = self._operation(fetcher).run(self._step(), self._context())

        self.assertTrue(result.performed)
        self.assertTrue(result.succeeded)
        self.assertEqual(fetcher.urls, [REQUESTED_URL])
        after = self.manager.get(self.run_id)
        self.assertEqual(before.sources[0], after.sources[0])
        self.assertEqual(
            [source.observation_id for source in after.sources], ["OA", "OB"]
        )
        self.assertEqual(after.sources[-1].requested_url, REQUESTED_URL)
        self.assertEqual(after.sources[-1].url, FINAL_URL)
        (relation,) = self.manager.source_revalidations()
        self.assertEqual(relation.record.earlier_observation_id, "OA")
        self.assertEqual(relation.record.later_observation_id, "OB")
        self.assertEqual(
            relation.record.outcome, ResearchSourceRevalidationOutcome.CONTENT_CHANGED
        )
        self.assertEqual(result.source_observation_id, "OB")
        self.assertEqual(result.source_revalidation_id, "relation-1")

    def test_same_content_records_only_the_explicit_unchanged_relation(self) -> None:
        result = self._operation(_Fetcher("Version one.")).run(
            self._step(), self._context()
        )

        self.assertTrue(result.succeeded)
        (relation,) = self.manager.source_revalidations()
        self.assertEqual(
            relation.record.outcome, ResearchSourceRevalidationOutcome.CONTENT_UNCHANGED
        )
        self.assertNotIn("is fresh", result.detail.casefold())

    def test_caller_cannot_substitute_a_url_before_fetch(self) -> None:
        fetcher = _Fetcher()

        result = self._operation(fetcher).run(
            self._step(requested_url="https://other.example.test/"), self._context()
        )

        self.assertFalse(result.performed)
        self.assertEqual(fetcher.urls, [])
        self.assertEqual(len(self.manager.get(self.run_id).sources), 1)
        self.assertEqual(self.manager.source_revalidations(), [])

    def test_normal_source_capacity_is_enforced_before_fetch(self) -> None:
        fetcher = _Fetcher()

        result = self._operation(fetcher).run(
            self._step(max_sources=1), self._context()
        )

        self.assertFalse(result.performed)
        self.assertEqual(fetcher.urls, [])
        self.assertEqual(self.manager.source_revalidations(), [])

    def test_failed_fetch_adds_no_observation_or_relation(self) -> None:
        fetcher = _Fetcher(error=ResearchError("Network unavailable."))

        with self.assertRaisesRegex(ResearchError, "Network unavailable"):
            self._operation(fetcher).run(self._step(), self._context())

        self.assertEqual(fetcher.urls, [REQUESTED_URL])
        self.assertEqual(len(self.manager.get(self.run_id).sources), 1)
        self.assertEqual(self.manager.source_revalidations(), [])

    def test_repeated_execution_is_refused_without_another_fetch(self) -> None:
        fetcher = _Fetcher()
        operation = self._operation(fetcher)
        self.assertTrue(operation.run(self._step(), self._context()).succeeded)

        repeated = operation.run(self._step(), self._context())

        self.assertFalse(repeated.performed)
        self.assertEqual(fetcher.urls, [REQUESTED_URL])
        self.assertEqual(len(self.manager.get(self.run_id).sources), 2)
        self.assertEqual(len(self.manager.source_revalidations()), 1)

    def test_revalidation_does_not_mutate_evidence_claims_or_lifecycle(self) -> None:
        before = self.manager.get(self.run_id)
        self.assertTrue(
            self._operation(_Fetcher()).run(self._step(), self._context()).succeeded
        )
        after = self.manager.get(self.run_id)

        self.assertEqual(after.status, before.status)
        self.assertEqual(after.evidence, before.evidence)
        self.assertEqual(after.claims, before.claims)

    def test_a_source_fetch_step_is_never_executed_as_revalidation(self) -> None:
        fetcher = _Fetcher()
        step = ResearchPlanStep(
            "fetch-1",
            "Fetch the advisory.",
            capability=Cap.SOURCE_FETCH,
            authorized_source_url=REQUESTED_URL,
        )

        result = self._operation(fetcher).run(step, self._context())

        self.assertFalse(result.performed)
        self.assertEqual(fetcher.urls, [])
        self.assertEqual(self.manager.source_revalidations(), [])

    def test_an_unknown_prior_observation_is_refused_before_fetch(self) -> None:
        fetcher = _Fetcher()
        step = ResearchPlanStep(
            "revalidate-1",
            "Re-fetch an observation that was never recorded.",
            capability=Cap.SOURCE_REVALIDATION,
            source_revalidation_binding=SourceRevalidationStepBinding(
                self.run_id, "OZ", REQUESTED_URL, 2
            ),
        )

        result = self._operation(fetcher).run(step, self._context())

        self.assertFalse(result.performed)
        self.assertEqual(fetcher.urls, [])

    def test_a_prior_without_a_requested_url_is_not_inferred_from_its_final_url(
        self,
    ) -> None:
        run_id = self.manager.create("A legacy question?").run_id
        self.manager.add_source(
            run_id,
            ResearchSource(
                url=FINAL_URL,
                title="Advisory",
                content="Version one.",
                content_type="text/plain",
                fetched_at=EARLIER,
            ),
            "document-legacy",
        )
        prior_id = self.manager.get(run_id).sources[0].observation_id
        assert prior_id is not None
        fetcher = _Fetcher()
        step = ResearchPlanStep(
            "revalidate-1",
            "Re-fetch the recorded observation.",
            capability=Cap.SOURCE_REVALIDATION,
            source_revalidation_binding=SourceRevalidationStepBinding(
                run_id, prior_id, FINAL_URL, 2
            ),
        )

        result = self._operation(fetcher).run(
            step,
            ResearchPlanExecutionContext(
                research_run_id=run_id, execution_id="execution-1"
            ),
        )

        self.assertFalse(result.performed)
        self.assertEqual(fetcher.urls, [])
        self.assertEqual(self.manager.source_revalidations(), [])

    def test_a_legacy_observation_without_identity_cannot_be_bound(self) -> None:
        path = Path(self.temporary_directory.name) / "runs.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["schema_version"] = 17
        document.pop("source_revalidations")
        for run in document["runs"]:
            for source in run["sources"]:
                for field in (
                    "observation_id",
                    "revalidation_of_observation_id",
                    "revalidation_execution_id",
                ):
                    source.pop(field)
        path.write_text(json.dumps(document), encoding="utf-8")
        self.manager = ResearchRunManager(JsonFileResearchRunStore(path))
        self.manager.load()
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge, self.manager, self.content  # type: ignore[arg-type]
        )
        self.assertIsNone(self.manager.get(self.run_id).sources[0].observation_id)
        fetcher = _Fetcher()

        result = self._operation(fetcher).run(self._step(), self._context())

        self.assertFalse(result.performed)
        self.assertEqual(fetcher.urls, [])
        self.assertIsNone(self.manager.get(self.run_id).sources[0].observation_id)

    def test_cross_run_provenance_is_refused_without_authority(self) -> None:
        other_run = self.manager.create("A different question?").run_id
        fetcher = _Fetcher()

        # The binding names this run's observation; the execution runs another.
        result = self._operation(fetcher).run(
            self._step(),
            ResearchPlanExecutionContext(
                research_run_id=other_run, execution_id="execution-1"
            ),
        )

        self.assertFalse(result.performed)
        self.assertEqual(fetcher.urls, [])
        self.assertEqual(self.manager.source_revalidations(), [])

    def test_acceptance_failure_records_no_relation_or_observation(self) -> None:
        class _FailingAcceptance:
            def accept(self, *args: object, **kwargs: object) -> object:
                raise KnowledgeError("Index unavailable.")

        fetcher = _Fetcher()
        operation = SourceRevalidationStepOperation(
            fetcher, _FailingAcceptance(), self.manager  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(ResearchError, "indexing failed"):
            operation.run(self._step(), self._context())

        self.assertEqual(fetcher.urls, [REQUESTED_URL])
        self.assertEqual(len(self.manager.get(self.run_id).sources), 1)
        self.assertEqual(self.manager.source_revalidations(), [])

    def test_recorded_result_belongs_only_to_the_execution_that_committed_it(
        self,
    ) -> None:
        fetcher = _Fetcher()
        operation = self._operation(fetcher)
        self.assertIsNone(operation.recorded_result(self._step(), self._context()))
        self.assertTrue(operation.run(self._step(), self._context()).succeeded)

        recovered = self._operation(_Fetcher()).recorded_result(
            self._step(), self._context()
        )
        foreign = self._operation(_Fetcher()).recorded_result(
            self._step(),
            ResearchPlanExecutionContext(
                research_run_id=self.run_id, execution_id="execution-2"
            ),
        )

        assert recovered is not None
        self.assertTrue(recovered.performed)
        self.assertEqual(recovered.source_observation_id, "OB")
        self.assertEqual(recovered.source_revalidation_id, "relation-1")
        self.assertIn("No second fetch", recovered.detail)
        self.assertIsNone(foreign)
        self.assertEqual(fetcher.urls, [REQUESTED_URL])

    def test_the_manager_refuses_a_second_revalidation_of_the_same_prior(
        self,
    ) -> None:
        self.assertTrue(
            self._operation(_Fetcher()).run(self._step(), self._context()).succeeded
        )

        with self.assertRaisesRegex(ResearchError, "already recorded"):
            self.manager.add_revalidated_source(
                self.run_id,
                "OA",
                ResearchSource(
                    url=FINAL_URL,
                    title="Advisory",
                    content="Version three.",
                    content_type="text/plain",
                    fetched_at=LATER + timedelta(days=1),
                ),
                "document-three",
                requested_url=REQUESTED_URL,
                execution_id="execution-9",
            )
        self.assertEqual(len(self.manager.source_revalidations()), 1)

    def test_a_revalidation_observation_without_its_relation_fails_to_load(
        self,
    ) -> None:
        self.assertTrue(
            self._operation(_Fetcher()).run(self._step(), self._context()).succeeded
        )
        path = Path(self.temporary_directory.name) / "runs.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["source_revalidations"] = []
        path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaisesRegex(ResearchError, "lacks its recorded relation"):
            JsonFileResearchRunStore(path).load()

    def test_an_ordinary_duplicate_content_version_is_still_refused(self) -> None:
        with self.assertRaisesRegex(ResearchError, "already attached"):
            self.manager.add_source(
                self.run_id,
                ResearchSource(
                    url=FINAL_URL,
                    title="Advisory",
                    content="Version one.",
                    content_type="text/plain",
                    fetched_at=LATER,
                ),
                "document-one",
                requested_url=REQUESTED_URL,
            )


if __name__ == "__main__":
    unittest.main()
