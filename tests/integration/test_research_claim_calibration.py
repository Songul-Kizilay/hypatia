"""Calibration reports the gap between what was claimed and what is recorded.

The rule these tests enforce is that calibration never touches a claim. An
epistemic state is someone's judgement about what they are willing to assert,
and a system that quietly downgraded it would be overruling that judgement while
calling the change bookkeeping. So every test that produces a finding also
asserts the claim came out the other side unchanged.

The second rule is the asymmetry. Claiming more than the record can carry is a
finding; claiming less is not. Being careful is not an error to be corrected,
and nothing here nudges anyone toward more confidence.

A supported ceiling is not a verdict on truth. Meeting it does not make a claim
true and exceeding it does not make one false — it describes only what our own
record can bear the weight of.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CalibrationApplicationService import CalibrationApplicationService
from cognition.CalibrationEvents import (
    CALIBRATION_REPORTED,
    CALIBRATION_REVISION_PREPARED,
)
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.CalibrationVerdict import CalibrationVerdict
from research.EvidenceSupportProfile import EvidenceSupportProfile
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchCalibrationReport import ResearchCalibrationReport
from research.ResearchClaimCalibrator import ResearchClaimCalibrator
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the ring system have a measured age?"
FETCHED = datetime(2026, 8, 1, tzinfo=UTC)


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


class CalibrationFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        document = self.root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(document)
        self.manager = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        self.manager.load()
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            InMemoryContentStore(),  # type: ignore[arg-type]
        )
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.calibrator = ResearchClaimCalibrator()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def service(self) -> CalibrationApplicationService:
        return CalibrationApplicationService(
            self.manager,
            ResponseComposer(),
            event_bus=self.event_bus,
        )

    def new_run(self) -> str:
        return self.manager.create(QUESTION).run_id

    def accept_source(self, run_id: str, slug: str) -> str:
        result = self.acceptance.accept(
            ResearchSource(
                url=f"https://example.test/{slug}",
                title=f"Source {slug}",
                content="Saturn has a prominent ring system with a debated age.",
                content_type="text/html",
                fetched_at=FETCHED,
            ),
            run_id,
        )
        assert result.document_id is not None
        return result.document_id

    def add_evidence(self, run_id: str, document_id: str) -> str:
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == document_id and candidate.index == 0
        )
        updated = self.manager.add_evidence(run_id, chunk, "Directly relevant.")
        return updated.evidence[-1].evidence_id

    def assess(
        self,
        run_id: str,
        document_id: str,
        evidence_id: str,
        trust: ResearchInformationTrust,
        **judgement: str,
    ) -> None:
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Assessed for the calibration test.",
            None,
            trust,
            judgement.get("usefulness", "unknown"),
            judgement.get("applicability", "unknown"),
            judgement.get("independence", "unknown"),
            judgement.get("publication_status", "unknown"),
        )

    def claim(
        self,
        run_id: str,
        evidence_ids: list[str],
        state: ResearchEpistemicState,
        confidence: ResearchClaimConfidence,
        text: str = "The rings have a measurable age.",
    ) -> str:
        run = self.manager.record_claim(run_id, evidence_ids, text, state, confidence)
        return run.claims[-1].claim_id

    def verdict(self, run_id: str) -> CalibrationVerdict:
        calibrations = self.calibrator.calibrate(self.manager.get(run_id))
        self.assertEqual(len(calibrations), 1)
        return calibrations[0].verdict

    def request(self, run_id: str) -> BrainRequest:
        return BrainRequest(
            message="Calibrate",
            metadata={
                "intent": "research_calibration_report",
                "research_run_id": run_id,
            },
        )

    def revision_request(self, run_id: str, claim_id: str) -> BrainRequest:
        return BrainRequest(
            message="Prepare claim review",
            metadata={
                "intent": "research_calibration_revision_prepare",
                "research_run_id": run_id,
                "research_claim_id": claim_id,
            },
        )


class AssessmentWarningReportTests(CalibrationFixture):
    """What the operator actually reads when a judgement conflicts with a claim."""

    def _run_with(self, **judgement: str) -> str:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "one")
        evidence_id = self.add_evidence(run_id, document_id)
        self.assess(
            run_id,
            document_id,
            evidence_id,
            ResearchInformationTrust.HIGH,
            **judgement,
        )
        self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.LIKELY,
            ResearchClaimConfidence.HIGH,
        )
        return run_id

    def test_the_report_shows_the_warning_beside_the_verdict(self) -> None:
        run_id = self._run_with(publication_status="retracted")

        response = self.service().process_report(self.request(run_id))

        self.assertIn("source_retracted", response.message)
        self.assertIn("high_attention", response.message)
        self.assertIn("Claims with source warnings: 1", response.message)

    def test_the_report_identifies_the_exact_claim_and_its_provenance(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "exact")
        evidence_id = self.add_evidence(run_id, document_id)
        claim_text = "The rings have a measurable age."
        claim_id = self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.FACT,
            ResearchClaimConfidence.HIGH,
            claim_text,
        )

        response = self.service().process_report(self.request(run_id))

        assert response.research_calibration is not None
        [calibration] = response.research_calibration.calibrations
        self.assertEqual(calibration.claim_id, claim_id)
        self.assertEqual(calibration.claim_text, claim_text)
        self.assertEqual(calibration.evidence_ids, (evidence_id,))
        self.assertEqual(calibration.source_document_ids, (document_id,))
        self.assertIn(f"- {claim_id} [overstated_both]", response.message)
        self.assertIn(f"    {claim_text}", response.message)
        self.assertIn(f"evidence IDs: {evidence_id}", response.message)
        self.assertIn(f"source document IDs: {document_id}", response.message)

    def test_the_report_says_plainly_that_nothing_was_corrected(self) -> None:
        """The whole risk of a warning is that it reads as a correction."""
        run_id = self._run_with(publication_status="retracted")

        message = self.service().process_report(self.request(run_id)).message

        self.assertIn("Warnings are warnings only", message)
        self.assertIn("no confidence was lowered", message)
        self.assertIn("no claim withdrawn", message)

    def test_a_claim_without_warnings_is_never_called_verified(self) -> None:
        """It may simply be resting on sources nobody has looked at."""
        run_id = self._run_with()

        message = self.service().process_report(self.request(run_id)).message

        self.assertIn("No assessment-aware warnings.", message)
        # The only sentence allowed to use the word says the opposite of what a
        # reader might assume: silence is not verification. Remove it and no
        # affirmative claim of verification may remain anywhere.
        self.assertIn("has not been verified", message)
        remainder = message.casefold().replace(
            "a claim with no warnings has not been verified", ""
        )
        self.assertNotIn("verified", remainder)

    def test_the_claim_is_untouched_after_the_report_is_read(self) -> None:
        run_id = self._run_with(publication_status="retracted")
        before = self.manager.get(run_id)

        self.service().process_report(self.request(run_id))

        after = self.manager.get(run_id)
        self.assertEqual(after.claims, before.claims)
        self.assertEqual(after.claims[0].confidence, ResearchClaimConfidence.HIGH)
        self.assertEqual(after.evidence, before.evidence)
        self.assertEqual(after.sources, before.sources)
        self.assertEqual(after.assessments, before.assessments)

    def test_the_event_carries_counts_and_codes_and_no_prose(self) -> None:
        run_id = self._run_with(publication_status="retracted")

        self.service().process_report(self.request(run_id))

        [event] = [
            event for event in self.events if event.name == "calibration.reported"
        ]
        self.assertEqual(event.payload["warning_count"], 1)
        self.assertEqual(event.payload["warned_claim_count"], 1)
        self.assertEqual(event.payload["warning_kinds"], {"source_retracted": 1})
        self.assertEqual(event.payload["claims_modified"], 0)
        self.assertNotIn("Assessed for the calibration test.", str(event.payload))

    def test_reporting_twice_produces_the_same_warnings(self) -> None:
        """Derived means recomputed, and recomputed means stable."""
        run_id = self._run_with(usefulness="not_useful")
        service = self.service()

        first = service.process_report(self.request(run_id))
        second = service.process_report(self.request(run_id))

        self.assertEqual(first.message, second.message)

    def test_revising_the_judgement_changes_the_report_with_no_stale_warning(
        self,
    ) -> None:
        run_id = self._run_with(publication_status="retracted")
        run = self.manager.get(run_id)
        self.manager.record_source_assessment(
            run_id,
            run.sources[0].document_id,
            [run.evidence[0].evidence_id],
            "Checked the journal: it stands.",
            run.assessments[0].assessment_id,
            "high",
            "unknown",
            "unknown",
            "unknown",
            "normal",
        )

        message = self.service().process_report(self.request(run_id)).message

        self.assertNotIn("source_retracted", message)
        self.assertIn("No assessment-aware warnings.", message)
        self.assertEqual(len(self.manager.get(run_id).assessments), 2)


class SupportCeilingTests(CalibrationFixture):
    def test_duplicate_records_do_not_hide_an_unassessed_resource(self) -> None:
        run_id = self.new_run()
        documents: list[str] = []
        for url, title in (
            ("https://www.example.test/shared", "Shared record one"),
            ("https://example.test/shared/", "Shared record two"),
            ("https://other.test/distinct", "Distinct resource"),
        ):
            result = self.acceptance.accept(
                ResearchSource(
                    url=url,
                    title=title,
                    content=f"{title} discusses the measured age of Saturn's rings.",
                    content_type="text/html",
                    fetched_at=FETCHED,
                ),
                run_id,
            )
            assert result.document_id is not None
            documents.append(result.document_id)

        evidence_ids = [
            self.add_evidence(run_id, document_id) for document_id in documents
        ]
        for document_id, evidence_id in zip(
            documents[:2], evidence_ids[:2], strict=True
        ):
            self.assess(
                run_id,
                document_id,
                evidence_id,
                ResearchInformationTrust.HIGH,
            )
        self.claim(
            run_id,
            evidence_ids,
            ResearchEpistemicState.STRONG_EVIDENCE,
            ResearchClaimConfidence.HIGH,
        )

        [calibration] = self.calibrator.calibrate(self.manager.get(run_id))

        self.assertEqual(calibration.profile.source_count, 2)
        self.assertEqual(calibration.profile.assessed_source_count, 1)
        self.assertFalse(calibration.profile.fully_assessed)
        self.assertIs(calibration.supported_state, ResearchEpistemicState.LIKELY)
        self.assertIs(
            calibration.supported_confidence,
            ResearchClaimConfidence.MEDIUM,
        )
        self.assertIs(calibration.verdict, CalibrationVerdict.OVERSTATED_BOTH)

    def test_one_unassessed_source_cannot_carry_a_fact(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "a")
        evidence_id = self.add_evidence(run_id, document_id)
        self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.FACT,
            ResearchClaimConfidence.HIGH,
        )

        self.assertIs(self.verdict(run_id), CalibrationVerdict.OVERSTATED_BOTH)

    def test_one_unassessed_source_carries_a_low_hypothesis(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "a")
        evidence_id = self.add_evidence(run_id, document_id)
        self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
        )

        self.assertIs(self.verdict(run_id), CalibrationVerdict.WITHIN_SUPPORT)

    def test_one_high_trust_source_carries_a_likely_claim(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "a")
        evidence_id = self.add_evidence(run_id, document_id)
        self.assess(run_id, document_id, evidence_id, ResearchInformationTrust.HIGH)
        self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.LIKELY,
            ResearchClaimConfidence.MEDIUM,
        )

        self.assertIs(self.verdict(run_id), CalibrationVerdict.WITHIN_SUPPORT)

    def test_one_high_trust_source_still_cannot_carry_strong_evidence(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "a")
        evidence_id = self.add_evidence(run_id, document_id)
        self.assess(run_id, document_id, evidence_id, ResearchInformationTrust.HIGH)
        self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.STRONG_EVIDENCE,
            ResearchClaimConfidence.MEDIUM,
        )

        self.assertIs(self.verdict(run_id), CalibrationVerdict.OVERSTATED_STATE)

    def test_two_medium_trust_sources_carry_strong_evidence(self) -> None:
        run_id, evidence_ids = self.corroborated_run(ResearchInformationTrust.MEDIUM)
        self.claim(
            run_id,
            evidence_ids,
            ResearchEpistemicState.STRONG_EVIDENCE,
            ResearchClaimConfidence.HIGH,
        )

        self.assertIs(self.verdict(run_id), CalibrationVerdict.WITHIN_SUPPORT)

    def test_two_sources_still_cannot_carry_a_fact(self) -> None:
        run_id, evidence_ids = self.corroborated_run(ResearchInformationTrust.HIGH)
        self.claim(
            run_id,
            evidence_ids,
            ResearchEpistemicState.FACT,
            ResearchClaimConfidence.HIGH,
        )

        self.assertIs(self.verdict(run_id), CalibrationVerdict.OVERSTATED_STATE)

    def test_one_low_trust_source_among_two_lowers_the_ceiling(self) -> None:
        run_id = self.new_run()
        first = self.accept_source(run_id, "a")
        second = self.accept_source(run_id, "b")
        first_evidence = self.add_evidence(run_id, first)
        second_evidence = self.add_evidence(run_id, second)
        self.assess(run_id, first, first_evidence, ResearchInformationTrust.HIGH)
        self.assess(run_id, second, second_evidence, ResearchInformationTrust.LOW)
        self.claim(
            run_id,
            [first_evidence, second_evidence],
            ResearchEpistemicState.STRONG_EVIDENCE,
            ResearchClaimConfidence.HIGH,
        )

        self.assertIs(self.verdict(run_id), CalibrationVerdict.OVERSTATED_BOTH)

    def test_parallel_high_trust_does_not_hide_active_low_trust(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "a")
        evidence_id = self.add_evidence(run_id, document_id)
        self.assess(
            run_id,
            document_id,
            evidence_id,
            ResearchInformationTrust.LOW,
        )
        self.assess(
            run_id,
            document_id,
            evidence_id,
            ResearchInformationTrust.HIGH,
        )
        self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.LIKELY,
            ResearchClaimConfidence.MEDIUM,
        )

        [calibration] = self.calibrator.calibrate(self.manager.get(run_id))

        self.assertIs(
            calibration.profile.lowest_trust,
            ResearchInformationTrust.LOW,
        )
        self.assertIs(calibration.verdict, CalibrationVerdict.OVERSTATED_BOTH)

    def test_a_contradicted_claim_carries_nothing(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "a")
        evidence_id = self.add_evidence(run_id, document_id)
        first = self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
            "The rings are young.",
        )
        second = self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
            "The rings are ancient.",
        )
        self.manager.record_claim_contradiction(
            run_id,
            [first, second],
            "These two cannot both hold.",
        )

        calibrations = self.calibrator.calibrate(self.manager.get(run_id))

        self.assertEqual(len(calibrations), 2)
        for entry in calibrations:
            self.assertIs(entry.verdict, CalibrationVerdict.CONTRADICTED)
            self.assertIs(
                entry.supported_state,
                ResearchEpistemicState.CONTRADICTED,
            )

    def test_understatement_is_reported_but_needs_no_attention(self) -> None:
        run_id, evidence_ids = self.corroborated_run(ResearchInformationTrust.HIGH)
        self.claim(
            run_id,
            evidence_ids,
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
        )

        calibrations = self.calibrator.calibrate(self.manager.get(run_id))

        self.assertIs(calibrations[0].verdict, CalibrationVerdict.UNDERSTATED)
        self.assertFalse(calibrations[0].needs_attention)
        self.assertFalse(calibrations[0].verdict.overstated)

    def test_a_superseded_claim_is_not_calibrated(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "a")
        evidence_id = self.add_evidence(run_id, document_id)
        earlier = self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.FACT,
            ResearchClaimConfidence.HIGH,
        )
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may have a measurable age.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
            supersedes_claim_id=earlier,
        )

        calibrations = self.calibrator.calibrate(self.manager.get(run_id))

        self.assertEqual(len(calibrations), 1)
        self.assertNotEqual(calibrations[0].claim_id, earlier)

    def test_a_run_without_claims_calibrates_nothing(self) -> None:
        run_id = self.new_run()

        self.assertEqual(self.calibrator.calibrate(self.manager.get(run_id)), ())

    def test_calibration_requires_an_actual_run(self) -> None:
        with self.assertRaises(ResearchError):
            self.calibrator.calibrate("run-1")  # type: ignore[arg-type]

    def corroborated_run(
        self,
        trust: ResearchInformationTrust,
    ) -> tuple[str, list[str]]:
        """Return a run with two assessed sources and one evidence record each."""
        run_id = self.new_run()
        evidence_ids: list[str] = []
        for slug in ("a", "b"):
            document_id = self.accept_source(run_id, slug)
            evidence_id = self.add_evidence(run_id, document_id)
            self.assess(run_id, document_id, evidence_id, trust)
            evidence_ids.append(evidence_id)
        return run_id, evidence_ids


class CalibrationChangesNothingTests(CalibrationFixture):
    def overstated_run(self) -> tuple[str, str]:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "a")
        evidence_id = self.add_evidence(run_id, document_id)
        claim_id = self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.FACT,
            ResearchClaimConfidence.HIGH,
        )
        return run_id, claim_id

    def test_an_overstated_claim_keeps_its_authored_state(self) -> None:
        run_id, claim_id = self.overstated_run()

        self.calibrator.calibrate(self.manager.get(run_id))

        claim = next(
            entry
            for entry in self.manager.get(run_id).claims
            if entry.claim_id == claim_id
        )
        self.assertIs(claim.epistemic_state, ResearchEpistemicState.FACT)
        self.assertIs(claim.confidence, ResearchClaimConfidence.HIGH)

    def test_calibrating_leaves_the_run_byte_identical(self) -> None:
        run_id, _ = self.overstated_run()
        before = self.run_path.read_bytes()
        service = self.service()

        for _ in range(3):
            service.process_report(self.request(run_id))

        self.assertEqual(self.run_path.read_bytes(), before)

    def test_the_report_says_no_claim_was_changed(self) -> None:
        run_id, _ = self.overstated_run()

        response = self.service().process_report(self.request(run_id))

        self.assertIn("No claim was changed", response.message)
        self.assertIn("does not make a claim true", response.message)
        self.assertIn("Understating is never reported as a problem", response.message)

    def test_the_report_is_derived_not_stored(self) -> None:
        run_id, _ = self.overstated_run()
        service = self.service()

        service.process_report(self.request(run_id))
        files = sorted(path.name for path in self.root.glob("*.json"))

        self.assertEqual(files, ["runs.json"])

    def test_the_report_tracks_a_later_change_to_the_claim(self) -> None:
        run_id, claim_id = self.overstated_run()
        service = self.service()
        first = service.process_report(self.request(run_id))
        assert first.research_calibration is not None

        self.manager.record_claim(
            run_id,
            list(self.manager.get(run_id).claims[-1].evidence_ids),
            "The rings may have a measurable age.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
            supersedes_claim_id=claim_id,
        )
        second = service.process_report(self.request(run_id))

        assert second.research_calibration is not None
        self.assertTrue(first.research_calibration.overstated)
        self.assertEqual(second.research_calibration.overstated, ())


class ClaimRevisionPreparationTests(CalibrationFixture):
    def overstated_claim(self) -> tuple[str, str, str, str]:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "review")
        evidence_id = self.add_evidence(run_id, document_id)
        claim_id = self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.FACT,
            ResearchClaimConfidence.HIGH,
            "The rings are exactly one hundred million years old.",
        )
        return run_id, claim_id, evidence_id, document_id

    def test_an_overstated_claim_gets_one_exact_inert_handoff(self) -> None:
        run_id, claim_id, evidence_id, document_id = self.overstated_claim()

        response = self.service().process_revision_prepare(
            self.revision_request(run_id, claim_id)
        )

        preparation = response.research_claim_revision_preparation
        assert preparation is not None
        self.assertEqual(preparation.run_id, run_id)
        self.assertEqual(preparation.supersedes_claim_id, claim_id)
        self.assertEqual(preparation.current_evidence_ids, (evidence_id,))
        self.assertEqual(
            preparation.current_source_document_ids,
            (document_id,),
        )
        self.assertIn("Current claim:", response.message)
        self.assertIn("record supports up to", response.message)
        self.assertIn("No replacement was drafted or recorded", response.message)
        self.assertIn("a person must decide", response.message)

    def test_preparation_recomputes_current_state_and_changes_no_file(self) -> None:
        run_id, claim_id, _, _ = self.overstated_claim()
        before = self.run_path.read_bytes()

        for _ in range(3):
            self.service().process_revision_prepare(
                self.revision_request(run_id, claim_id)
            )

        self.assertEqual(self.run_path.read_bytes(), before)

    def test_a_warning_can_prompt_review_without_overstating_the_claim(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "warning")
        evidence_id = self.add_evidence(run_id, document_id)
        self.assess(
            run_id,
            document_id,
            evidence_id,
            ResearchInformationTrust.HIGH,
            publication_status="retracted",
        )
        claim_id = self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.LIKELY,
            ResearchClaimConfidence.MEDIUM,
        )

        response = self.service().process_revision_prepare(
            self.revision_request(run_id, claim_id)
        )

        preparation = response.research_claim_revision_preparation
        assert preparation is not None
        self.assertFalse(preparation.calibration.needs_attention)
        self.assertTrue(preparation.calibration.warnings)
        self.assertIn("source_retracted", response.message)

    def test_a_supported_or_understated_claim_is_not_nudged_upward(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "careful")
        evidence_id = self.add_evidence(run_id, document_id)
        claim_id = self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.SPECULATION,
            ResearchClaimConfidence.UNASSESSED,
        )

        with self.assertRaisesRegex(ResearchError, "no reason for a second look"):
            self.service().process_revision_prepare(
                self.revision_request(run_id, claim_id)
            )

    def test_a_superseded_or_unknown_claim_cannot_be_prepared(self) -> None:
        run_id, claim_id, evidence_id, _ = self.overstated_claim()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may have a measurable age.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
            supersedes_claim_id=claim_id,
        )

        for unavailable_id in (claim_id, "claim-missing"):
            with (
                self.subTest(claim_id=unavailable_id),
                self.assertRaisesRegex(
                    ResearchError,
                    "Active research claim was not found",
                ),
            ):
                self.service().process_revision_prepare(
                    self.revision_request(run_id, unavailable_id)
                )

    def test_preparation_event_is_bounded_and_carries_no_claim_content(self) -> None:
        run_id, claim_id, evidence_id, document_id = self.overstated_claim()

        self.service().process_revision_prepare(self.revision_request(run_id, claim_id))

        [event] = [
            event
            for event in self.events
            if event.name == CALIBRATION_REVISION_PREPARED
        ]
        self.assertEqual(event.payload["run_id"], run_id)
        self.assertEqual(event.payload["verdict"], "overstated_both")
        self.assertEqual(event.payload["claims_modified"], 0)
        serialized = json.dumps(event.payload)
        self.assertNotIn(claim_id, serialized)
        self.assertNotIn(evidence_id, serialized)
        self.assertNotIn(document_id, serialized)
        self.assertNotIn("one hundred million", serialized)


class CalibrationProfileTests(unittest.TestCase):
    def test_a_profile_rejects_more_assessments_than_sources(self) -> None:
        with self.assertRaises(ResearchError):
            EvidenceSupportProfile(source_count=1, assessed_source_count=2)

    def test_a_profile_rejects_negative_counts(self) -> None:
        with self.assertRaises(ResearchError):
            EvidenceSupportProfile(source_count=-1)

    def test_a_profile_rejects_trust_without_an_assessed_source(self) -> None:
        with self.assertRaisesRegex(ResearchError, "requires an assessed source"):
            EvidenceSupportProfile(
                source_count=1,
                lowest_trust=ResearchInformationTrust.HIGH,
                highest_trust=ResearchInformationTrust.HIGH,
            )

    def test_a_profile_rejects_a_reversed_trust_range(self) -> None:
        with self.assertRaisesRegex(ResearchError, "range is reversed"):
            EvidenceSupportProfile(
                source_count=2,
                assessed_source_count=2,
                lowest_trust=ResearchInformationTrust.HIGH,
                highest_trust=ResearchInformationTrust.LOW,
            )

    def test_a_profile_rejects_non_boolean_states(self) -> None:
        with self.assertRaisesRegex(ResearchError, "states must be boolean"):
            EvidenceSupportProfile(contradicted="yes")  # type: ignore[arg-type]

    def test_corroboration_needs_more_than_one_source(self) -> None:
        self.assertFalse(EvidenceSupportProfile(source_count=1).corroborated)
        self.assertTrue(EvidenceSupportProfile(source_count=2).corroborated)

    def test_full_assessment_needs_every_source_judged(self) -> None:
        self.assertFalse(
            EvidenceSupportProfile(
                source_count=2,
                assessed_source_count=1,
            ).fully_assessed
        )
        self.assertTrue(
            EvidenceSupportProfile(
                source_count=2,
                assessed_source_count=2,
            ).fully_assessed
        )

    def test_an_empty_profile_is_not_fully_assessed(self) -> None:
        self.assertFalse(EvidenceSupportProfile().fully_assessed)

    def test_the_profile_renders_each_count_separately(self) -> None:
        lines = EvidenceSupportProfile(source_count=2, evidence_count=3).lines()

        self.assertIn("Distinct sources: 2", lines)
        self.assertIn("Evidence records: 3", lines)

    def test_only_overstatement_needs_attention(self) -> None:
        self.assertFalse(CalibrationVerdict.WITHIN_SUPPORT.needs_attention)
        self.assertFalse(CalibrationVerdict.UNDERSTATED.needs_attention)
        self.assertTrue(CalibrationVerdict.OVERSTATED_BOTH.needs_attention)
        self.assertTrue(CalibrationVerdict.CONTRADICTED.needs_attention)

    def test_a_contradiction_is_not_counted_as_overstatement(self) -> None:
        self.assertFalse(CalibrationVerdict.CONTRADICTED.overstated)
        self.assertTrue(CalibrationVerdict.OVERSTATED_STATE.overstated)

    def test_a_report_rejects_a_blank_run_identifier(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchCalibrationReport(run_id="  ", calibrations=())


class CalibrationEventTests(CalibrationFixture):
    def test_reporting_emits_one_bounded_event(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "a")
        evidence_id = self.add_evidence(run_id, document_id)
        self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.FACT,
            ResearchClaimConfidence.HIGH,
        )

        self.service().process_report(self.request(run_id))

        events = [event for event in self.events if event.name == CALIBRATION_REPORTED]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["claim_count"], 1)
        self.assertEqual(events[0].payload["overstated_count"], 1)
        self.assertEqual(events[0].payload["claims_modified"], 0)

    def test_no_event_carries_claim_or_question_text(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "a")
        evidence_id = self.add_evidence(run_id, document_id)
        self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.FACT,
            ResearchClaimConfidence.HIGH,
            "The rings are demonstrably young.",
        )

        self.service().process_report(self.request(run_id))

        payloads = json.dumps(
            [
                event.payload
                for event in self.events
                if event.name.startswith("calibration")
            ]
        )
        self.assertTrue(payloads)
        self.assertNotIn("demonstrably young", payloads)
        self.assertNotIn(QUESTION, payloads)
        self.assertNotIn("example.test", payloads)


class CalibrationCompositionTests(CalibrationFixture):
    def test_the_engine_routes_calibration_over_the_run_manager(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        response = engine.process(self.request(run_id))

        service = engine._calibration_service
        self.assertIsInstance(service, CalibrationApplicationService)
        assert service is not None
        self.assertIs(service._run_manager, self.manager)
        assert response.research_calibration is not None
        self.assertEqual(response.research_calibration.run_id, run_id)

    def test_calibration_is_refused_without_run_persistence(self) -> None:
        engine = self.build_engine(with_runs=False)

        response = engine.process(self.request("run-1"))

        self.assertIsNone(engine._calibration_service)
        self.assertFalse(response.success)
        self.assertIn("unavailable", response.message)

    def test_the_engine_routes_one_claim_preparation_and_stops_before_write(
        self,
    ) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "engine-review")
        evidence_id = self.add_evidence(run_id, document_id)
        claim_id = self.claim(
            run_id,
            [evidence_id],
            ResearchEpistemicState.FACT,
            ResearchClaimConfidence.HIGH,
        )
        before = self.run_path.read_bytes()

        response = self.build_engine().process(self.revision_request(run_id, claim_id))

        self.assertTrue(response.success)
        self.assertIsNotNone(response.research_claim_revision_preparation)
        self.assertEqual(self.run_path.read_bytes(), before)

    def test_claim_preparation_is_refused_without_run_persistence(self) -> None:
        response = self.build_engine(with_runs=False).process(
            self.revision_request("run-1", "claim-1")
        )

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "research_calibration_revision_prepare")
        self.assertIn("unavailable", response.message)

    def test_an_unknown_run_is_refused_without_raising(self) -> None:
        engine = self.build_engine()

        response = engine.process(self.request("run-missing"))

        self.assertFalse(response.success)
        self.assertIn("rejected", response.message)

    def build_engine(self, with_runs: bool = True) -> CognitiveEngine:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        session_manager = SessionManager(event_bus)
        return CognitiveEngine(
            self.knowledge_engine,
            memory_manager,
            Planner(),
            event_bus,
            ResponseComposer(),
            session_manager,
            SessionRenameTransactionService(
                session_manager=session_manager,
                memory_manager=memory_manager,
                event_bus=event_bus,
            ),
            research_run_manager=self.manager if with_runs else None,
        )


if __name__ == "__main__":
    unittest.main()
