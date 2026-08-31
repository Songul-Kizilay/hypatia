"""An accepted CVE has to be an ordinary source, all the way down.

Ingestion was the interesting half and it is finished. This is the boring half,
and it is the half where a provider-specific route usually leaks: an assessment
that reads a provider name, a confidence that rises because NIST said it, a
comparison join that breaks the moment a source's bytes stop coming from the URL
that names it. So these tests walk the whole operator journey with a structured
NVD source and assert that nothing downstream noticed anything unusual.

The one thing that genuinely was not ordinary is fixed here rather than guarded:
restoration rebuilt each indexed document from the persisted content record, and
that record had nowhere to keep how the bytes were obtained. An accepted CVE came
back after a restart describing itself as an ordinary HTTPS read of the detail
page — a page that serves an application shell and cannot produce those bytes.
The document identity is derived from the URL, so it still matched, indexing
still succeeded, and nothing anywhere said the provenance had changed.

No operator judgement is authored here. Every usefulness, applicability,
independence and publication value below is fixture data in a temporary
directory, and the point of most of these tests is that the system records what
a person said rather than deciding it for them.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.JsonFileResearchSourceContentStore import (
    JsonFileResearchSourceContentStore,
)
from research.NvdResearchSourceDiscoveryProvider import (
    NVD_CVE_ENDPOINT,
    NVD_DETAIL_PREFIX,
)
from research.NvdResearchSourceFetcher import NVD_API_ACQUISITION
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchProviderComparisonBuilder import (
    ResearchProviderComparisonBuilder,
)
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import HTTPS_ACQUISITION, ResearchSource
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceContentRestorer import ResearchSourceContentRestorer
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourceUsefulness import ResearchSourceUsefulness
from research.ResearchVulnerabilityRecord import ResearchVulnerabilityRecord
from research.SourceIdentity import identity_of

CVE = "CVE-2025-29927"
DETAIL_URL = f"{NVD_DETAIL_PREFIX}{CVE}"
DOI_URL = "https://doi.org/10.1000/paper"
REFERENCE_URL = "https://github.test/advisory"
FETCHED_AT = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
STORED_AT = datetime(2026, 8, 20, 12, 1, tzinfo=UTC)

NVD_CONTENT = "\n".join(
    (
        "This document was materialized from the NVD CVE API 2.0 response for "
        "this CVE. References below were listed by NVD; none of them was "
        "fetched.",
        "",
        f"CVE: {CVE}",
        "Provider record status: Analyzed",
        "Weaknesses: CWE-285",
        "Published: 2025-03-21T15:15:42.660000+00:00",
        "",
        "Description (as published by NVD):",
        "Next.js middleware authorization bypass affecting several releases.",
        "",
        "References listed by NVD (not fetched, not verified):",
        f"- {REFERENCE_URL} [Patch, Vendor Advisory]",
    )
)

CROSSREF_CONTENT = "\n".join(
    ("A scholarly paper about middleware.", "", "Its second paragraph of body text.")
)


def nvd_source() -> ResearchSource:
    """The source an accepted NVD candidate materializes into."""
    return ResearchSource(
        url=DETAIL_URL,
        title=f"{CVE}: Next.js middleware authorization bypass",
        content=NVD_CONTENT,
        content_type="text/plain",
        fetched_at=FETCHED_AT,
        content_resource=NVD_CVE_ENDPOINT,
        acquisition=NVD_API_ACQUISITION,
    )


def crossref_source() -> ResearchSource:
    """An ordinary source loaded by the generic HTTPS path."""
    return ResearchSource(
        url=DOI_URL,
        title="A paper",
        content=CROSSREF_CONTENT,
        content_type="text/html",
        fetched_at=FETCHED_AT,
    )


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[Any] = []

    def load(self) -> list[Any]:
        return list(self.records)

    def save(self, records: list[Any]) -> None:
        self.records = list(records)


class DownstreamWorkflowTests(unittest.TestCase):
    """One accepted CVE, carried through the existing operator journey."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.content_store = InMemoryContentStore()
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            self.content_store,  # type: ignore[arg-type]
        )
        self.run_id = self.manager.create(CVE).run_id
        self.nvd_discovery_id = (
            self.manager.add_discovery(
                self.run_id,
                CVE,
                "nvd",
                [
                    ResearchSourceCandidate(
                        url=DETAIL_URL,
                        title=f"{CVE}: bypass",
                        snippet="Authorization bypass.",
                        vulnerability=ResearchVulnerabilityRecord(cve_id=CVE),
                    )
                ],
            )
            .discoveries[0]
            .discovery_id
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _accept_nvd(self) -> str:
        result = self.acceptance.accept(nvd_source(), self.run_id)
        self.assertTrue(result.accepted)
        return result.document_id

    def _first_chunk(self, document_id: str) -> Any:
        chunks = [
            chunk
            for chunk in self.knowledge_engine.chunks()
            if chunk.document_id == document_id
        ]
        self.assertTrue(chunks, "the accepted source exposed no chunks")
        return chunks[0]

    def _evidence_id(self, document_id: str) -> str:
        run = self.manager.add_evidence(
            self.run_id,
            self._first_chunk(document_id),
            "The record states the affected releases.",
        )
        return run.evidence[-1].evidence_id

    # ---- accepted source selector -------------------------------------

    def test_the_accepted_cve_appears_in_the_run_source_set(self) -> None:
        document_id = self._accept_nvd()

        run = self.manager.get(self.run_id)
        self.assertEqual([source.document_id for source in run.sources], [document_id])
        self.assertEqual(run.sources[0].url, DETAIL_URL)

    def test_ingestion_creates_no_assessment_evidence_or_claim(self) -> None:
        self._accept_nvd()

        run = self.manager.get(self.run_id)
        self.assertEqual((run.assessments, run.evidence, run.claims), ((), (), ()))

    # ---- assessment ---------------------------------------------------

    def test_the_cve_is_assessed_through_the_ordinary_preview(self) -> None:
        document_id = self._accept_nvd()

        preview = self.manager.preview_source_assessment(self.run_id, document_id)

        self.assertEqual(preview.source.document_id, document_id)
        self.assertEqual(preview.source.url, DETAIL_URL)

    def test_the_operator_records_the_unchanged_assessment_vocabulary(self) -> None:
        document_id = self._accept_nvd()
        evidence_id = self._evidence_id(document_id)

        run = self.manager.record_source_assessment(
            self.run_id,
            document_id,
            [evidence_id],
            "Read the record; it names the affected versions.",
            usefulness=ResearchSourceUsefulness.USEFUL,
            applicability=ResearchSourceApplicability.DIRECT,
            independence=ResearchSourceIndependence.INDEPENDENT,
        )

        [assessment] = run.assessments
        self.assertEqual(assessment.source_document_id, document_id)
        self.assertIs(assessment.usefulness, ResearchSourceUsefulness.USEFUL)
        self.assertIs(assessment.applicability, ResearchSourceApplicability.DIRECT)

    def test_an_unassessed_cve_stays_unknown_rather_than_authoritative(self) -> None:
        """NVD being authoritative metadata is not an operator's judgement."""
        document_id = self._accept_nvd()
        evidence_id = self._evidence_id(document_id)

        run = self.manager.record_source_assessment(
            self.run_id, document_id, [evidence_id], "Recorded without judging it."
        )

        [assessment] = run.assessments
        self.assertIs(assessment.usefulness, ResearchSourceUsefulness.UNKNOWN)
        self.assertIs(assessment.applicability, ResearchSourceApplicability.UNKNOWN)
        self.assertIs(assessment.independence, ResearchSourceIndependence.UNKNOWN)

    def test_assessing_a_document_absent_from_the_run_fails_closed(self) -> None:
        self._accept_nvd()

        with self.assertRaises(ResearchError):
            self.manager.preview_source_assessment(self.run_id, "document-absent")

    # ---- evidence -----------------------------------------------------

    def test_the_cve_exposes_readable_chunks_carrying_its_text(self) -> None:
        document_id = self._accept_nvd()

        chunks = [
            chunk
            for chunk in self.knowledge_engine.chunks()
            if chunk.document_id == document_id
        ]

        self.assertTrue(chunks)
        combined = " ".join(chunk.content for chunk in chunks)
        self.assertIn(CVE, combined)
        self.assertIn("authorization bypass", combined.casefold())

    def test_evidence_preserves_exact_document_and_chunk_identity(self) -> None:
        document_id = self._accept_nvd()
        chunk = self._first_chunk(document_id)

        run = self.manager.add_evidence(self.run_id, chunk, "A note about the record.")

        [evidence] = run.evidence
        self.assertEqual(evidence.source_document_id, document_id)
        self.assertEqual(evidence.chunk_id, chunk.chunk_id)
        self.assertEqual(evidence.chunk_index, chunk.index)

    def test_recording_evidence_creates_no_claim(self) -> None:
        document_id = self._accept_nvd()

        run = self.manager.add_evidence(
            self.run_id, self._first_chunk(document_id), "A note."
        )

        self.assertEqual(len(run.evidence), 1)
        self.assertEqual(run.claims, ())

    # ---- claims -------------------------------------------------------

    def test_a_claim_cites_cve_evidence_through_the_ordinary_model(self) -> None:
        document_id = self._accept_nvd()
        evidence_id = self._evidence_id(document_id)

        run = self.manager.record_claim(
            self.run_id,
            [evidence_id],
            "The middleware check can be bypassed on the listed releases.",
            ResearchEpistemicState.STRONG_EVIDENCE,
        )

        [claim] = run.claims
        self.assertEqual(list(claim.evidence_ids), [evidence_id])

    def test_confidence_does_not_rise_because_the_provider_was_nvd(self) -> None:
        document_id = self._accept_nvd()
        evidence_id = self._evidence_id(document_id)

        run = self.manager.record_claim(
            self.run_id,
            [evidence_id],
            "A claim recorded without stating a confidence.",
            ResearchEpistemicState.HYPOTHESIS,
        )

        [claim] = run.claims
        self.assertIs(claim.confidence, ResearchClaimConfidence.UNASSESSED)
        self.assertIs(claim.epistemic_state, ResearchEpistemicState.HYPOTHESIS)

    # ---- provider comparison ------------------------------------------

    def test_the_comparison_joins_the_accepted_cve_to_its_candidate(self) -> None:
        """The join is on candidate identity, which the API origin must not move."""
        self._accept_nvd()

        report = ResearchProviderComparisonBuilder().build(
            self.manager.get(self.run_id)
        )

        [side] = [entry for entry in report.sides if entry.provider == "nvd"]
        self.assertEqual(side.discovery_id, self.nvd_discovery_id)
        self.assertEqual(side.accepted_count, 1)

    def test_the_api_origin_never_becomes_the_source_identity(self) -> None:
        self._accept_nvd()

        source = self.manager.get(self.run_id).sources[0]
        self.assertEqual(identity_of(source.url), identity_of(DETAIL_URL))
        self.assertNotEqual(identity_of(source.url), identity_of(NVD_CVE_ENDPOINT))

    # ---- references stay inert ----------------------------------------

    def test_no_reference_becomes_a_source_through_the_whole_journey(self) -> None:
        document_id = self._accept_nvd()
        evidence_id = self._evidence_id(document_id)
        self.manager.record_source_assessment(
            self.run_id, document_id, [evidence_id], "Assessed."
        )
        self.manager.record_claim(
            self.run_id, [evidence_id], "A claim.", ResearchEpistemicState.HYPOTHESIS
        )

        run = self.manager.get(self.run_id)
        self.assertEqual([source.url for source in run.sources], [DETAIL_URL])
        self.assertNotIn(
            REFERENCE_URL,
            [document.source for document in self.knowledge_engine.documents()],
        )

    # ---- Crossref regression ------------------------------------------

    def test_a_crossref_source_takes_the_same_journey_unchanged(self) -> None:
        result = self.acceptance.accept(crossref_source(), self.run_id)
        self.assertTrue(result.accepted)

        preview = self.manager.preview_source_assessment(
            self.run_id, result.document_id
        )
        run = self.manager.add_evidence(
            self.run_id, self._first_chunk(result.document_id), "A note."
        )

        self.assertEqual(preview.source.url, DOI_URL)
        self.assertEqual(run.evidence[-1].source_document_id, result.document_id)
        stored = self.content_store.records[0]
        self.assertEqual(stored.acquisition, HTTPS_ACQUISITION)
        self.assertEqual(stored.content_resource, "")

    def test_a_crossref_url_is_not_accepted_under_the_nvd_discovery(self) -> None:
        with self.assertRaises(ResearchError):
            self.manager.preview_candidate_acceptance(
                self.run_id, self.nvd_discovery_id, DOI_URL
            )


class RestoredProvenanceTests(unittest.TestCase):
    """Provenance has to survive a restart, because that is when it is reread."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.content_path = self.root / "content.json"
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.run_id = self.manager.create(CVE).run_id

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _accept_into_a_fresh_process(self) -> tuple[KnowledgeEngine, str]:
        engine = KnowledgeEngine()
        store = JsonFileResearchSourceContentStore(self.content_path)
        result = ResearchSourceAcceptanceService(engine, self.manager, store).accept(
            nvd_source(), self.run_id
        )
        return engine, result.document_id

    def test_a_restarted_cve_still_says_it_came_from_the_api(self) -> None:
        """The defect this milestone found, guarded at the boundary that lost it."""
        _engine, document_id = self._accept_into_a_fresh_process()

        restored_engine = KnowledgeEngine()
        status = ResearchSourceContentRestorer(
            JsonFileResearchSourceContentStore(self.content_path),
            restored_engine,
        ).restore(self.manager.list())

        self.assertTrue(status.available)
        [document] = [
            document
            for document in restored_engine.documents()
            if document.document_id == document_id
        ]
        restored = restored_engine.remove_document(document_id)
        self.assertEqual(restored.metadata["acquisition"], NVD_API_ACQUISITION)
        self.assertEqual(restored.metadata["content_resource"], NVD_CVE_ENDPOINT)
        self.assertEqual(document.source, DETAIL_URL)

    def test_a_restarted_ordinary_source_is_unchanged(self) -> None:
        engine = KnowledgeEngine()
        store = JsonFileResearchSourceContentStore(self.content_path)
        result = ResearchSourceAcceptanceService(engine, self.manager, store).accept(
            crossref_source(), self.run_id
        )

        restored_engine = KnowledgeEngine()
        ResearchSourceContentRestorer(
            JsonFileResearchSourceContentStore(self.content_path),
            restored_engine,
        ).restore(self.manager.list())

        restored = restored_engine.remove_document(result.document_id)
        self.assertEqual(restored.metadata["acquisition"], HTTPS_ACQUISITION)
        self.assertNotIn("content_resource", restored.metadata)


if __name__ == "__main__":
    unittest.main()
