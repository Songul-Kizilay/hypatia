"""One end-to-end scenario for explicit research-plan execution.

Drives the whole chain through the real `CognitiveEngine` composition path in a
single narrative: question, discovery, explicit authorization, fetch,
acceptance, evidence, assessment, claims, contradiction, comparison, and honest
closure.

Deterministic doubles stand in for the discovery provider and source fetcher, so
no network is required and the scenario is stable in CI. Every other component
is the real one, including the run manager, knowledge engine, acceptance
transaction, and epistemic domain. Live-model and live-network validation
remain separate manual diagnostics.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAssessmentAuthorization import ResearchAssessmentAuthorization
from research.ResearchClaimAuthorization import ResearchClaimAuthorization
from research.ResearchComparisonAuthorization import ResearchComparisonAuthorization
from research.ResearchCompletionAuthorization import ResearchCompletionAuthorization
from research.ResearchContradictionAuthorization import (
    ResearchContradictionAuthorization,
)
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the ring system of Saturn have a measured age?"

FIRST_URL = "https://example.test/first-study"
SECOND_URL = "https://example.test/second-study"

SOURCE_BODIES = {
    FIRST_URL: "The first study reports a young ring system age estimate.",
    SECOND_URL: "The second study reports an ancient ring system age estimate.",
}


class ScenarioDiscoveryProvider:
    """Return two deterministic candidates and record every query."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    @property
    def provider_name(self) -> str:
        return "scenario_discovery"

    def discover(self, query: str, *, limit: int) -> list[ResearchSourceCandidate]:
        self.queries.append(query)
        return [
            ResearchSourceCandidate(
                url=url,
                title=f"Study at {url}",
                snippet="A bounded snippet describing the study.",
            )
            for url in list(SOURCE_BODIES)[:limit]
        ]


class ScenarioSourceFetcher:
    """Serve deterministic bodies and record every fetched URL."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch(self, url: str) -> ResearchSource:
        self.urls.append(url)
        return ResearchSource(
            url=url,
            title=f"Study at {url}",
            content=SOURCE_BODIES[url],
            content_type="text/html",
            fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
        )


class ExplicitResearchExecutionScenarioTests(unittest.TestCase):
    """One narrative covering the whole explicit research chain."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.knowledge_engine = KnowledgeEngine()
        self.session_manager = SessionManager(self.event_bus)
        self.run_manager = ResearchRunManager(
            JsonFileResearchRunStore(root / "runs.json")
        )
        self.discovery_provider = ScenarioDiscoveryProvider()
        self.source_fetcher = ScenarioSourceFetcher()
        self.engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            SessionRenameTransactionService(
                session_manager=self.session_manager,
                memory_manager=self.memory_manager,
                event_bus=self.event_bus,
            ),
            research_run_manager=self.run_manager,
            research_source_discovery_provider=self.discovery_provider,
            research_source_fetcher=self.source_fetcher,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _execute(self, draft: ResearchPlanStepDraftInput, run_id: str):  # type: ignore[no-untyped-def]
        """Start and advance one authored single-step plan, then report it."""
        started = self.engine.process(
            BrainRequest(
                message="Start research plan",
                metadata={
                    "intent": "research_plan_execution_start",
                    "research_plan_question": QUESTION,
                    "research_plan_steps": (draft,),
                    "research_run_id": run_id,
                },
            )
        )
        self.assertTrue(started.success, started.message)
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id

        advanced = self.engine.process(
            BrainRequest(
                message="Advance research plan",
                metadata={
                    "intent": "research_plan_execution_advance",
                    "research_plan_id": plan_id,
                },
            )
        )
        state = advanced.research_plan_execution
        assert state is not None
        return state

    def _expect_completed(self, state, operation: str) -> None:  # type: ignore[no-untyped-def]
        self.assertEqual(state.status.value, "completed", state.steps[0].detail)
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].operation, operation)

    def test_question_to_closed_run_with_uncertainty_intact(self) -> None:
        run = self.run_manager.create(QUESTION)
        run_id = run.run_id

        # 1. Discovery proposes candidates. Nothing is accepted by proposing.
        self._expect_completed(
            self._execute(
                ResearchPlanStepDraftInput(
                    instruction="Find candidate sources for the question",
                    capability="source_discovery",
                ),
                run_id,
            ),
            "source_discovery",
        )
        after_discovery = self.run_manager.get(run_id)
        self.assertEqual(self.discovery_provider.queries, [QUESTION])
        self.assertEqual(len(after_discovery.discoveries), 1)
        self.assertEqual(after_discovery.sources, ())
        self.assertEqual(self.source_fetcher.urls, [])

        # 2. A human authorizes one candidate. Acquisition accepts nothing.
        self._expect_completed(
            self._execute(
                ResearchPlanStepDraftInput(
                    instruction="Acquire the authorized source",
                    capability="source_fetch",
                    authorized_source_url=FIRST_URL,
                ),
                run_id,
            ),
            "source_fetch",
        )
        self.assertEqual(self.source_fetcher.urls, [FIRST_URL])
        self.assertEqual(self.run_manager.get(run_id).sources, ())

        # 3. Acceptance brings each authorized source into the run.
        document_ids: list[str] = []
        for url in (FIRST_URL, SECOND_URL):
            self._expect_completed(
                self._execute(
                    ResearchPlanStepDraftInput(
                        instruction="Accept the authorized source",
                        capability="source_accept",
                        authorized_source_url=url,
                    ),
                    run_id,
                ),
                "source_accept",
            )
            document_ids.append(self.run_manager.get(run_id).sources[-1].document_id)
        self.assertEqual(len(self.run_manager.get(run_id).sources), 2)

        # 4. Evidence is recorded from exact accepted chunks.
        evidence_ids: list[str] = []
        for document_id in document_ids:
            self._expect_completed(
                self._execute(
                    ResearchPlanStepDraftInput(
                        instruction="Record evidence from the accepted source",
                        capability="evidence_recording",
                        evidence_authorization=self._evidence(document_id),
                    ),
                    run_id,
                ),
                "evidence_recording",
            )
            evidence_ids.append(self.run_manager.get(run_id).evidence[-1].evidence_id)

        # 5. Each source is assessed, grounded in its own evidence.
        assessment_ids: list[str] = []
        for document_id, evidence_id in zip(document_ids, evidence_ids, strict=True):
            self._expect_completed(
                self._execute(
                    ResearchPlanStepDraftInput(
                        instruction="Assess the accepted source",
                        capability="source_assessment",
                        assessment_authorization=ResearchAssessmentAuthorization(
                            document_id=document_id,
                            evidence_ids=(evidence_id,),
                            text="The study states its age estimate directly.",
                            information_trust="medium",  # type: ignore[arg-type]
                        ),
                    ),
                    run_id,
                ),
                "source_assessment",
            )
            assessment_ids.append(
                self.run_manager.get(run_id).assessments[-1].assessment_id
            )

        # 6. Two conflicting claims are authored, neither as fact.
        claim_ids: list[str] = []
        for evidence_id, text in zip(
            evidence_ids,
            ("The ring system is young.", "The ring system is ancient."),
            strict=True,
        ):
            self._expect_completed(
                self._execute(
                    ResearchPlanStepDraftInput(
                        instruction="Record the authored claim",
                        capability="claim_creation",
                        claim_authorization=ResearchClaimAuthorization(
                            evidence_ids=(evidence_id,),
                            text=text,
                            epistemic_state=ResearchEpistemicState.HYPOTHESIS,
                        ),
                    ),
                    run_id,
                ),
                "claim_creation",
            )
            claim_ids.append(self.run_manager.get(run_id).claims[-1].claim_id)

        claims_before_contradiction = self.run_manager.get(run_id).claims

        # 7. The conflict is recorded without deciding either claim.
        self._expect_completed(
            self._execute(
                ResearchPlanStepDraftInput(
                    instruction="Record the confirmed contradiction",
                    capability="claim_contradiction",
                    contradiction_authorization=ResearchContradictionAuthorization(
                        claim_ids=(claim_ids[0], claim_ids[1]),
                        note="The two studies cannot both be correct.",
                    ),
                ),
                run_id,
            ),
            "claim_contradiction",
        )
        self.assertEqual(
            self.run_manager.get(run_id).claims,
            claims_before_contradiction,
        )

        # 8. The sources are compared without naming a winner.
        self._expect_completed(
            self._execute(
                ResearchPlanStepDraftInput(
                    instruction="Compare the accepted sources",
                    capability="source_comparison",
                    comparison_authorization=ResearchComparisonAuthorization(
                        document_ids=tuple(document_ids),
                        evidence_ids=tuple(evidence_ids),
                        assessment_ids=tuple(assessment_ids),
                        text="The studies disagree on the age estimate.",
                    ),
                ),
                run_id,
            ),
            "source_comparison",
        )

        # 9. The run closes honestly, with the disagreement intact.
        completion = self._execute(
            ResearchPlanStepDraftInput(
                instruction="Close the research run",
                capability="research_run_completion",
                completion_authorization=ResearchCompletionAuthorization(
                    target_status=ResearchRunStatus.COMPLETED
                ),
            ),
            run_id,
        )
        self._expect_completed(completion, "research_run_completion")
        detail = completion.steps[0].detail
        self.assertIn("closed as 'completed'", detail)
        self.assertIn("2 unresolved claim(s)", detail)
        self.assertIn("1 contradiction(s)", detail)
        self.assertIn("resolves nothing", detail)

        final = self.run_manager.get(run_id)
        self.assertIs(final.status, ResearchRunStatus.COMPLETED)
        self.assertEqual(final.question, QUESTION)
        self.assertEqual(len(final.discoveries), 1)
        self.assertEqual(len(final.sources), 2)
        self.assertEqual(len(final.evidence), 2)
        self.assertEqual(len(final.assessments), 2)
        self.assertEqual(len(final.claims), 2)
        self.assertEqual(len(final.comparison_notes), 1)
        self.assertEqual(len(final.claim_contradictions), 1)

        # Nothing was silently promoted anywhere along the chain.
        for claim in final.claims:
            self.assertIs(claim.epistemic_state, ResearchEpistemicState.HYPOTHESIS)
            self.assertEqual(claim.confidence.value, "unassessed")

        # Only the authorized URLs were ever contacted.
        self.assertEqual(
            self.source_fetcher.urls,
            [FIRST_URL, FIRST_URL, SECOND_URL],
        )

        # Research execution wrote no conversation memory.
        self.assertEqual(self.memory_manager.all(), [])

    def _evidence(self, document_id: str):  # type: ignore[no-untyped-def]
        from research.ResearchEvidenceAuthorization import (
            ResearchEvidenceAuthorization,
        )

        return ResearchEvidenceAuthorization(
            document_id=document_id,
            chunk_index=0,
            note="Directly states the study's age estimate.",
        )


if __name__ == "__main__":
    unittest.main()
