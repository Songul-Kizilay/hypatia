"""Persistence tests for strict atomic research-run JSON snapshots."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from core.Exceptions import ResearchError
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceRecord import ResearchSourceRecord
from research.ResearchSourceUsefulness import ResearchSourceUsefulness
from research.ResearchVulnerabilityMetric import ResearchVulnerabilityMetric
from research.ResearchVulnerabilityRecord import ResearchVulnerabilityRecord
from research.ResearchVulnerabilityReference import ResearchVulnerabilityReference


class JsonFileResearchRunStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "research_runs.json"
        self.store = JsonFileResearchRunStore(self.path)
        self.now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_missing_store_loads_as_empty(self) -> None:
        self.assertEqual(self.store.load(), [])

    def _minimal_run(self, run_id: str = "run-1") -> ResearchRun:
        return ResearchRun(
            run_id=run_id,
            question="Question",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=self.now,
            updated_at=self.now,
        )

    def test_round_trip_preserves_sources_failures_and_unicode(self) -> None:
        run = ResearchRun(
            run_id="run-1",
            question="Songül için kanıt nedir?",
            status=ResearchRunStatus.COMPLETED,
            sources=(
                ResearchSourceRecord(
                    document_id="document-1",
                    url="https://example.com/research",
                    title="Example",
                    content_type="text/html",
                    fetched_at=self.now,
                    added_at=self.now,
                ),
            ),
            failures=(
                ResearchFailureRecord(
                    stage="source_discovery",
                    reason="Timed out.",
                    occurred_at=self.now,
                    provider="nvd",
                ),
            ),
            created_at=self.now,
            updated_at=self.now,
            evidence=(
                ResearchEvidenceRecord(
                    evidence_id="evidence-1",
                    source_document_id="document-1",
                    chunk_id="chunk-1",
                    chunk_index=0,
                    excerpt="Evidence paragraph.",
                    excerpt_truncated=False,
                    chunk_sha256="a" * 64,
                    note="Supports the claim.",
                    recorded_at=self.now,
                ),
            ),
            discoveries=(
                ResearchSourceDiscoveryRecord(
                    discovery_id="discovery-1",
                    query="Songül için kanıt nedir?",
                    provider="test-provider",
                    candidates=(
                        ResearchSourceCandidate(
                            url="https://example.com/candidate",
                            title="Candidate",
                            snippet="A possible source.",
                        ),
                    ),
                    discovered_at=self.now,
                ),
            ),
            assessments=(
                ResearchSourceAssessmentRecord(
                    assessment_id="assessment-1",
                    source_document_id="document-1",
                    evidence_ids=("evidence-1",),
                    text="The source supports the claim.",
                    recorded_at=self.now,
                ),
                ResearchSourceAssessmentRecord(
                    assessment_id="assessment-2",
                    source_document_id="document-1",
                    evidence_ids=("evidence-1",),
                    text="The corrected assessment narrows the claim.",
                    recorded_at=self.now,
                    supersedes_assessment_id="assessment-1",
                ),
            ),
            claims=(
                ResearchClaimRecord(
                    claim_id="claim-1",
                    text="The corrected assessment supports a narrower claim.",
                    epistemic_state=ResearchEpistemicState.STRONG_EVIDENCE,
                    confidence=ResearchClaimConfidence.HIGH,
                    source_document_ids=("document-1",),
                    evidence_ids=("evidence-1",),
                    recorded_at=self.now,
                ),
            ),
        )

        self.store.save([run])

        self.assertEqual(self.store.load(), [run])
        self.assertTrue(self.path.read_text(encoding="utf-8").endswith("\n"))
        with self.assertRaisesRegex(ResearchError, "duplicate assessment IDs"):
            self.store.save([run, replace(run, run_id="run-2")])

    def test_rejects_unknown_fields_schema_and_duplicate_ids(self) -> None:
        for document in (
            {"schema_version": 14, "runs": []},
            {"schema_version": True, "runs": []},
            {"schema_version": 1, "runs": [], "unexpected": True},
        ):
            with self.subTest(document=document):
                self.path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaises(ResearchError):
                    self.store.load()

        run = ResearchRun(
            run_id="run-1",
            question="Question",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=self.now,
            updated_at=self.now,
        )
        with self.assertRaisesRegex(ResearchError, "duplicate run IDs"):
            self.store.save([run, run])

    def test_loads_v1_without_new_collections_and_rewrites_as_v13(self) -> None:
        legacy_document = {
            "schema_version": 1,
            "runs": [
                {
                    "run_id": "legacy-run",
                    "question": "Legacy question",
                    "status": "collecting",
                    "sources": [],
                    "failures": [],
                    "created_at": self.now.isoformat(),
                    "updated_at": self.now.isoformat(),
                }
            ],
        }
        self.path.write_text(json.dumps(legacy_document), encoding="utf-8")

        runs = self.store.load()
        self.store.save(runs)

        self.assertEqual(runs[0].evidence, ())
        self.assertEqual(runs[0].discoveries, ())
        self.assertEqual(runs[0].assessments, ())
        self.assertEqual(runs[0].comparison_notes, ())
        rewritten = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(rewritten["schema_version"], 13)
        self.assertEqual(rewritten["runs"][0]["evidence"], [])
        self.assertEqual(rewritten["runs"][0]["discoveries"], [])
        self.assertEqual(rewritten["runs"][0]["assessments"], [])
        self.assertEqual(rewritten["runs"][0]["comparison_notes"], [])
        self.assertEqual(rewritten["runs"][0]["claims"], [])
        self.assertEqual(rewritten["runs"][0]["claim_contradictions"], [])

    def test_loads_v2_without_discoveries_and_rewrites_as_v13(self) -> None:
        legacy_document = {
            "schema_version": 2,
            "runs": [
                {
                    "run_id": "legacy-run",
                    "question": "Legacy question",
                    "status": "collecting",
                    "sources": [],
                    "failures": [],
                    "evidence": [],
                    "created_at": self.now.isoformat(),
                    "updated_at": self.now.isoformat(),
                }
            ],
        }
        self.path.write_text(json.dumps(legacy_document), encoding="utf-8")

        runs = self.store.load()
        self.store.save(runs)

        self.assertEqual(runs[0].discoveries, ())
        rewritten = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(rewritten["schema_version"], 13)
        self.assertEqual(rewritten["runs"][0]["discoveries"], [])
        self.assertEqual(rewritten["runs"][0]["assessments"], [])
        self.assertEqual(rewritten["runs"][0]["comparison_notes"], [])
        self.assertEqual(rewritten["runs"][0]["claims"], [])
        self.assertEqual(rewritten["runs"][0]["claim_contradictions"], [])

    def test_loads_v3_without_assessments_and_rewrites_as_v13(self) -> None:
        legacy_document = {
            "schema_version": 3,
            "runs": [
                {
                    "run_id": "legacy-run",
                    "question": "Legacy question",
                    "status": "collecting",
                    "sources": [],
                    "failures": [],
                    "evidence": [],
                    "discoveries": [],
                    "created_at": self.now.isoformat(),
                    "updated_at": self.now.isoformat(),
                }
            ],
        }
        self.path.write_text(json.dumps(legacy_document), encoding="utf-8")

        runs = self.store.load()
        self.store.save(runs)

        self.assertEqual(runs[0].assessments, ())
        rewritten = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(rewritten["schema_version"], 13)
        self.assertEqual(rewritten["runs"][0]["assessments"], [])
        self.assertEqual(rewritten["runs"][0]["comparison_notes"], [])
        self.assertEqual(rewritten["runs"][0]["claims"], [])
        self.assertEqual(rewritten["runs"][0]["claim_contradictions"], [])

    def test_loads_v4_assessments_without_supersession_and_rewrites_as_v13(
        self,
    ) -> None:
        legacy_document = {
            "schema_version": 4,
            "runs": [
                {
                    "run_id": "legacy-run",
                    "question": "Legacy question",
                    "status": "collecting",
                    "sources": [
                        {
                            "document_id": "document-1",
                            "url": "https://example.com/source",
                            "title": "Source",
                            "content_type": "text/plain",
                            "fetched_at": self.now.isoformat(),
                            "added_at": self.now.isoformat(),
                        }
                    ],
                    "failures": [],
                    "evidence": [
                        {
                            "evidence_id": "evidence-1",
                            "source_document_id": "document-1",
                            "chunk_id": "chunk-1",
                            "chunk_index": 0,
                            "excerpt": "Evidence.",
                            "excerpt_truncated": False,
                            "chunk_sha256": "a" * 64,
                            "note": "Relevant.",
                            "recorded_at": self.now.isoformat(),
                        }
                    ],
                    "discoveries": [],
                    "assessments": [
                        {
                            "assessment_id": "assessment-1",
                            "source_document_id": "document-1",
                            "evidence_ids": ["evidence-1"],
                            "text": "Legacy assessment.",
                            "recorded_at": self.now.isoformat(),
                        }
                    ],
                    "created_at": self.now.isoformat(),
                    "updated_at": self.now.isoformat(),
                }
            ],
        }
        self.path.write_text(json.dumps(legacy_document), encoding="utf-8")

        runs = self.store.load()
        self.store.save(runs)

        self.assertIsNone(runs[0].assessments[0].supersedes_assessment_id)
        self.assertEqual(
            runs[0].assessments[0].information_trust,
            ResearchInformationTrust.UNASSESSED,
        )
        self.assertEqual(runs[0].sources[0].taint_label, "external_untrusted_data")
        self.assertEqual(runs[0].sources[0].instruction_authority, "none")
        rewritten = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(rewritten["schema_version"], 13)
        self.assertIsNone(
            rewritten["runs"][0]["assessments"][0]["supersedes_assessment_id"]
        )
        self.assertEqual(
            rewritten["runs"][0]["assessments"][0]["information_trust"],
            "unassessed",
        )
        self.assertEqual(
            rewritten["runs"][0]["sources"][0]["taint_label"],
            "external_untrusted_data",
        )
        self.assertEqual(
            rewritten["runs"][0]["sources"][0]["instruction_authority"],
            "none",
        )
        self.assertEqual(rewritten["runs"][0]["comparison_notes"], [])
        self.assertEqual(rewritten["runs"][0]["claims"], [])
        self.assertEqual(rewritten["runs"][0]["claim_contradictions"], [])

    def test_loads_v5_without_comparison_notes_and_rewrites_as_v13(self) -> None:
        legacy_document = {
            "schema_version": 5,
            "runs": [
                {
                    "run_id": "legacy-run",
                    "question": "Legacy question",
                    "status": "collecting",
                    "sources": [],
                    "failures": [],
                    "evidence": [],
                    "discoveries": [],
                    "assessments": [],
                    "created_at": self.now.isoformat(),
                    "updated_at": self.now.isoformat(),
                }
            ],
        }
        self.path.write_text(json.dumps(legacy_document), encoding="utf-8")

        runs = self.store.load()
        self.store.save(runs)

        self.assertEqual(runs[0].comparison_notes, ())
        rewritten = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(rewritten["schema_version"], 13)
        self.assertEqual(rewritten["runs"][0]["comparison_notes"], [])
        self.assertEqual(rewritten["runs"][0]["claims"], [])
        self.assertEqual(rewritten["runs"][0]["claim_contradictions"], [])

    def test_loads_v6_without_trust_metadata_and_rewrites_as_v13(self) -> None:
        legacy_document = {
            "schema_version": 6,
            "runs": [
                {
                    "run_id": "legacy-run",
                    "question": "Legacy question",
                    "status": "collecting",
                    "sources": [
                        {
                            "document_id": "document-1",
                            "url": "https://example.com/source",
                            "title": "Source",
                            "content_type": "text/plain",
                            "fetched_at": self.now.isoformat(),
                            "added_at": self.now.isoformat(),
                        }
                    ],
                    "failures": [],
                    "evidence": [
                        {
                            "evidence_id": "evidence-1",
                            "source_document_id": "document-1",
                            "chunk_id": "chunk-1",
                            "chunk_index": 0,
                            "excerpt": "Evidence.",
                            "excerpt_truncated": False,
                            "chunk_sha256": "a" * 64,
                            "note": "Relevant.",
                            "recorded_at": self.now.isoformat(),
                        }
                    ],
                    "discoveries": [],
                    "assessments": [
                        {
                            "assessment_id": "assessment-1",
                            "source_document_id": "document-1",
                            "evidence_ids": ["evidence-1"],
                            "text": "Legacy assessment.",
                            "recorded_at": self.now.isoformat(),
                            "supersedes_assessment_id": None,
                        }
                    ],
                    "comparison_notes": [],
                    "created_at": self.now.isoformat(),
                    "updated_at": self.now.isoformat(),
                }
            ],
        }
        self.path.write_text(json.dumps(legacy_document), encoding="utf-8")

        runs = self.store.load()
        self.store.save(runs)

        source = runs[0].sources[0]
        assessment = runs[0].assessments[0]
        self.assertEqual(source.taint_label, "external_untrusted_data")
        self.assertEqual(source.instruction_authority, "none")
        self.assertEqual(
            assessment.information_trust,
            ResearchInformationTrust.UNASSESSED,
        )
        rewritten = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(rewritten["schema_version"], 13)
        self.assertEqual(
            rewritten["runs"][0]["sources"][0]["taint_label"],
            "external_untrusted_data",
        )
        self.assertEqual(
            rewritten["runs"][0]["sources"][0]["instruction_authority"],
            "none",
        )
        self.assertEqual(
            rewritten["runs"][0]["assessments"][0]["information_trust"],
            "unassessed",
        )
        self.assertEqual(rewritten["runs"][0]["claims"], [])
        self.assertEqual(rewritten["runs"][0]["claim_contradictions"], [])

    def test_loads_v7_without_claims_and_rewrites_as_v13(self) -> None:
        run = self._minimal_run()
        self.store.save([run])
        legacy_document = json.loads(self.path.read_text(encoding="utf-8"))
        legacy_document["schema_version"] = 7
        legacy_document["runs"][0].pop("claims")
        legacy_document["runs"][0].pop("claim_contradictions")
        self.path.write_text(json.dumps(legacy_document), encoding="utf-8")

        runs = self.store.load()
        self.store.save(runs)

        self.assertEqual(runs[0].claims, ())
        rewritten = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(rewritten["schema_version"], 13)
        self.assertEqual(rewritten["runs"][0]["claims"], [])
        self.assertEqual(rewritten["runs"][0]["claim_contradictions"], [])

    def test_loads_v8_without_claim_contradictions_and_rewrites_as_v13(self) -> None:
        run = self._minimal_run()
        self.store.save([run])
        legacy_document = json.loads(self.path.read_text(encoding="utf-8"))
        legacy_document["schema_version"] = 8
        legacy_document["runs"][0].pop("claim_contradictions")
        self.path.write_text(json.dumps(legacy_document), encoding="utf-8")

        runs = self.store.load()
        self.store.save(runs)

        self.assertEqual(runs[0].claims, run.claims)
        self.assertEqual(runs[0].claim_contradictions, ())
        rewritten = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(rewritten["schema_version"], 13)
        self.assertEqual(rewritten["runs"][0]["claim_contradictions"], [])

    def test_v10_keeps_the_venue_and_year_a_candidate_was_discovered_with(
        self,
    ) -> None:
        run = self._minimal_run()
        discovery = ResearchSourceDiscoveryRecord(
            "discovery-1",
            "web application security",
            "crossref",
            (
                ResearchSourceCandidate(
                    url="https://doi.org/10.1/paper",
                    title="A paper",
                    snippet="USENIX Security · 2025",
                    container="USENIX Security",
                    published_year=2025,
                ),
            ),
            self.now,
        )
        stored = replace(run, discoveries=(discovery,))
        self.store.save([stored])

        [loaded] = self.store.load()

        candidate = loaded.discoveries[0].candidates[0]
        self.assertEqual(candidate.container, "USENIX Security")
        self.assertEqual(candidate.published_year, 2025)

    def test_a_v9_candidate_loads_without_a_year_being_invented_for_it(self) -> None:
        """It truthfully has none: the field was discarded before it was written."""
        run = self._minimal_run()
        discovery = ResearchSourceDiscoveryRecord(
            "discovery-1",
            "web application security",
            "crossref",
            (
                ResearchSourceCandidate(
                    url="https://doi.org/10.1/paper",
                    title="A paper",
                    snippet="USENIX Security · 2025",
                    container="USENIX Security",
                    published_year=2025,
                ),
            ),
            self.now,
        )
        self.store.save([replace(run, discoveries=(discovery,))])
        legacy_document = json.loads(self.path.read_text(encoding="utf-8"))
        legacy_document["schema_version"] = 9
        legacy_candidate = legacy_document["runs"][0]["discoveries"][0]["candidates"][0]
        legacy_candidate.pop("container")
        legacy_candidate.pop("published_year")
        # A version 9 record predates the vulnerability record too: no provider
        # had ever returned one, so the field simply was not there.
        legacy_candidate.pop("vulnerability")
        self.path.write_text(json.dumps(legacy_document), encoding="utf-8")

        [loaded] = self.store.load()

        candidate = loaded.discoveries[0].candidates[0]
        self.assertIsNone(candidate.published_year)
        self.assertEqual(candidate.container, "")
        self.assertEqual(candidate.snippet, "USENIX Security · 2025")

    def test_a_candidate_carrying_an_implausible_year_is_refused(self) -> None:
        run = self._minimal_run()
        discovery = ResearchSourceDiscoveryRecord(
            "discovery-1",
            "web application security",
            "crossref",
            (ResearchSourceCandidate("https://doi.org/10.1/p", "A paper", ""),),
            self.now,
        )
        self.store.save([replace(run, discoveries=(discovery,))])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["runs"][0]["discoveries"][0]["candidates"][0]["published_year"] = True
        self.path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def _run_with_assessment(self, **judgement: str) -> ResearchRun:
        run = replace(
            self._minimal_run(),
            sources=(
                ResearchSourceRecord(
                    document_id="document-1",
                    url="https://doi.org/10.1000/paper",
                    title="A paper",
                    content_type="text/plain",
                    fetched_at=self.now,
                    added_at=self.now,
                ),
            ),
            evidence=(
                ResearchEvidenceRecord(
                    evidence_id="evidence-1",
                    source_document_id="document-1",
                    chunk_id="chunk-1",
                    chunk_index=0,
                    excerpt="Body text.",
                    excerpt_truncated=False,
                    chunk_sha256=sha256(b"Body text.").hexdigest(),
                    note="A note.",
                    recorded_at=self.now,
                ),
            ),
        )
        assessment = ResearchSourceAssessmentRecord(
            assessment_id="assessment-1",
            source_document_id="document-1",
            evidence_ids=("evidence-1",),
            text="I read it and it does not hold up.",
            recorded_at=self.now,
            information_trust=ResearchInformationTrust.LOW,
            usefulness=ResearchSourceUsefulness(judgement.get("usefulness", "unknown")),
            applicability=ResearchSourceApplicability(
                judgement.get("applicability", "unknown")
            ),
            independence=ResearchSourceIndependence(
                judgement.get("independence", "unknown")
            ),
            publication_status=ResearchSourcePublicationStatus(
                judgement.get("publication_status", "unknown")
            ),
        )
        return replace(run, assessments=(assessment,))

    def test_v11_keeps_every_dimension_the_operator_answered(self) -> None:
        stored = self._run_with_assessment(
            usefulness="partially_useful",
            applicability="background_only",
            independence="derivative",
            publication_status="retracted",
        )
        self.store.save([stored])

        [loaded] = self.store.load()

        assessment = loaded.assessments[0]
        self.assertEqual(
            assessment.usefulness, ResearchSourceUsefulness.PARTIALLY_USEFUL
        )
        self.assertEqual(
            assessment.applicability, ResearchSourceApplicability.BACKGROUND_ONLY
        )
        self.assertEqual(assessment.independence, ResearchSourceIndependence.DERIVATIVE)
        self.assertEqual(
            assessment.publication_status,
            ResearchSourcePublicationStatus.RETRACTED,
        )
        self.assertEqual(assessment.information_trust, ResearchInformationTrust.LOW)
        self.assertEqual(assessment.text, stored.assessments[0].text)
        self.assertEqual(assessment.recorded_at, stored.assessments[0].recorded_at)

    def test_a_v10_assessment_loads_without_a_judgement_being_invented(self) -> None:
        """Nobody was ever asked, so `unknown` is what those records hold."""
        self.store.save([self._run_with_assessment(usefulness="useful")])
        legacy = json.loads(self.path.read_text(encoding="utf-8"))
        legacy["schema_version"] = 10
        stored_assessment = legacy["runs"][0]["assessments"][0]
        for field in (
            "usefulness",
            "applicability",
            "independence",
            "publication_status",
        ):
            stored_assessment.pop(field)
        self.path.write_text(json.dumps(legacy), encoding="utf-8")

        [loaded] = self.store.load()

        assessment = loaded.assessments[0]
        self.assertEqual(assessment.usefulness, ResearchSourceUsefulness.UNKNOWN)
        self.assertEqual(assessment.applicability, ResearchSourceApplicability.UNKNOWN)
        self.assertEqual(assessment.independence, ResearchSourceIndependence.UNKNOWN)
        self.assertEqual(
            assessment.publication_status, ResearchSourcePublicationStatus.UNKNOWN
        )
        self.assertEqual(assessment.information_trust, ResearchInformationTrust.LOW)

    def test_a_judgement_this_build_cannot_read_fails_the_load(self) -> None:
        """Showing it as never made would be worse than refusing to open it."""
        self.store.save([self._run_with_assessment(usefulness="useful")])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["runs"][0]["assessments"][0]["usefulness"] = "outstanding"
        self.path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_an_assessment_missing_a_dimension_at_v11_fails_closed(self) -> None:
        self.store.save([self._run_with_assessment(usefulness="useful")])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["runs"][0]["assessments"][0].pop("independence")
        self.path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def _run_with_vulnerability_candidate(self) -> ResearchRun:
        run = self._minimal_run()
        candidate = ResearchSourceCandidate(
            url="https://nvd.nist.gov/vuln/detail/CVE-2025-29927",
            title="CVE-2025-29927: Next.js middleware authorization bypass.",
            snippet="Next.js middleware authorization bypass.",
            container="security@vercel.com",
            published_year=2025,
            vulnerability=ResearchVulnerabilityRecord(
                cve_id="CVE-2025-29927",
                status="Analyzed",
                source_identifier="security@vercel.com",
                last_modified=self.now,
                weaknesses=("CWE-285",),
                metrics=(
                    ResearchVulnerabilityMetric(
                        version="3.1",
                        source="nvd@nist.gov",
                        score=9.1,
                        severity="CRITICAL",
                    ),
                ),
                references=(
                    ResearchVulnerabilityReference(
                        url="https://github.test/advisory",
                        source="security@vercel.com",
                        tags=("Patch",),
                    ),
                ),
                reference_total=42,
                known_exploited_at="2025-03-25",
                known_exploited_name="Next.js Authorization Bypass",
            ),
        )
        discovery = ResearchSourceDiscoveryRecord(
            "discovery-1",
            "Next.js middleware authorization bypass",
            "nvd",
            (candidate,),
            self.now,
        )
        return replace(run, discoveries=(discovery,))

    def test_v13_round_trips_a_vulnerability_record_exactly(self) -> None:
        stored = self._run_with_vulnerability_candidate()
        self.store.save([stored])

        [loaded] = self.store.load()

        record = loaded.discoveries[0].candidates[0].vulnerability
        self.assertEqual(record, stored.discoveries[0].candidates[0].vulnerability)
        self.assertEqual(record.reference_total, 42)
        self.assertTrue(record.references_truncated)
        self.assertTrue(record.known_exploited)

    def test_a_v12_failure_loads_without_invented_provider_provenance(self) -> None:
        run = replace(
            self._minimal_run(),
            failures=(
                ResearchFailureRecord(
                    stage="source_discovery",
                    reason="Failed.",
                    occurred_at=self.now,
                    provider="nvd",
                ),
            ),
        )
        self.store.save([run])
        legacy = json.loads(self.path.read_text(encoding="utf-8"))
        legacy["schema_version"] = 12
        legacy["runs"][0]["failures"][0].pop("provider")
        self.path.write_text(json.dumps(legacy), encoding="utf-8")

        [loaded] = self.store.load()

        self.assertIsNone(loaded.failures[0].provider)

    def test_a_scholarly_candidate_stores_no_vulnerability(self) -> None:
        """Crossref never returned one, and an empty record would read like a CVE."""
        run = self._minimal_run()
        discovery = ResearchSourceDiscoveryRecord(
            "discovery-1",
            "web application security",
            "crossref",
            (
                ResearchSourceCandidate(
                    url="https://doi.org/10.1000/paper",
                    title="A paper",
                    snippet="",
                    container="USENIX Security",
                    published_year=2025,
                ),
            ),
            self.now,
        )
        self.store.save([replace(run, discoveries=(discovery,))])

        [loaded] = self.store.load()

        self.assertIsNone(loaded.discoveries[0].candidates[0].vulnerability)

    def test_a_v11_candidate_gains_no_invented_vulnerability(self) -> None:
        self.store.save([self._run_with_vulnerability_candidate()])
        legacy = json.loads(self.path.read_text(encoding="utf-8"))
        legacy["schema_version"] = 11
        legacy["runs"][0]["discoveries"][0]["candidates"][0].pop("vulnerability")
        self.path.write_text(json.dumps(legacy), encoding="utf-8")

        [loaded] = self.store.load()

        self.assertIsNone(loaded.discoveries[0].candidates[0].vulnerability)

    def test_a_malformed_vulnerability_record_fails_the_load(self) -> None:
        """One this build cannot decode is one somebody discovered."""
        self.store.save([self._run_with_vulnerability_candidate()])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["runs"][0]["discoveries"][0]["candidates"][0]["vulnerability"][
            "cve_id"
        ] = "not-a-cve"
        self.path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_a_vulnerability_record_missing_a_field_fails_closed(self) -> None:
        self.store.save([self._run_with_vulnerability_candidate()])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["runs"][0]["discoveries"][0]["candidates"][0]["vulnerability"].pop(
            "weaknesses"
        )
        self.path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_a_stored_reference_is_never_turned_into_a_request(self) -> None:
        """Loading a run reads a file. It does not open a socket."""
        stored = self._run_with_vulnerability_candidate()
        self.store.save([stored])

        with patch("urllib.request.urlopen") as opened:
            self.store.load()

        opened.assert_not_called()

    def test_v9_rejects_mutable_source_authority_and_invalid_trust_labels(
        self,
    ) -> None:
        run = ResearchRun(
            run_id="run-1",
            question="Question",
            status=ResearchRunStatus.COLLECTING,
            sources=(
                ResearchSourceRecord(
                    "document-1",
                    "https://example.com/source",
                    "Source",
                    "text/plain",
                    self.now,
                    self.now,
                ),
            ),
            failures=(),
            created_at=self.now,
            updated_at=self.now,
            evidence=(
                ResearchEvidenceRecord(
                    "evidence-1",
                    "document-1",
                    "chunk-1",
                    0,
                    "Evidence.",
                    False,
                    "a" * 64,
                    "Relevant.",
                    self.now,
                ),
            ),
            assessments=(
                ResearchSourceAssessmentRecord(
                    "assessment-1",
                    "document-1",
                    ("evidence-1",),
                    "Assessment.",
                    self.now,
                    information_trust=ResearchInformationTrust.HIGH,
                ),
            ),
            claims=(
                ResearchClaimRecord(
                    "claim-1",
                    "Evidence supports the claim.",
                    ResearchEpistemicState.STRONG_EVIDENCE,
                    ResearchClaimConfidence.HIGH,
                    ("document-1",),
                    ("evidence-1",),
                    self.now,
                ),
            ),
        )
        self.store.save([run])
        valid_document = json.loads(self.path.read_text(encoding="utf-8"))

        for field, invalid_value, message in (
            ("taint_label", "trusted", "taint label"),
            ("instruction_authority", "execute", "authority must be none"),
        ):
            with self.subTest(field=field):
                document = json.loads(json.dumps(valid_document))
                document["runs"][0]["sources"][0][field] = invalid_value
                self.path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaisesRegex(ResearchError, message):
                    self.store.load()

        document = json.loads(json.dumps(valid_document))
        document["runs"][0]["assessments"][0]["information_trust"] = "trusted"
        self.path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(ResearchError, "information trust"):
            self.store.load()

        invalid_claim_values: tuple[tuple[str, object, str], ...] = (
            ("epistemic_state", "certain", "epistemic state"),
            ("confidence", 100, "claim confidence"),
        )
        for claim_field, invalid_claim_value, claim_message in invalid_claim_values:
            with self.subTest(claim_field=claim_field):
                document = json.loads(json.dumps(valid_document))
                document["runs"][0]["claims"][0][claim_field] = invalid_claim_value
                self.path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaisesRegex(ResearchError, claim_message):
                    self.store.load()

        document = json.loads(json.dumps(valid_document))
        document["runs"][0]["claims"][0]["source_document_ids"] = ["document-mismatch"]
        self.path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(ResearchError, "match its evidence"):
            self.store.load()

    def test_round_trip_preserves_comparison_note_references(self) -> None:
        sources = tuple(
            ResearchSourceRecord(
                document_id=f"document-{number}",
                url=f"https://example.com/{number}",
                title=f"Source {number}",
                content_type="text/plain",
                fetched_at=self.now,
                added_at=self.now,
            )
            for number in (1, 2)
        )
        evidence = tuple(
            ResearchEvidenceRecord(
                evidence_id=f"evidence-{number}",
                source_document_id=f"document-{number}",
                chunk_id=f"chunk-{number}",
                chunk_index=number - 1,
                excerpt=f"Evidence {number}.",
                excerpt_truncated=False,
                chunk_sha256=str(number) * 64,
                note=f"Note {number}",
                recorded_at=self.now,
            )
            for number in (1, 2)
        )
        assessments = tuple(
            ResearchSourceAssessmentRecord(
                assessment_id=f"assessment-{number}",
                source_document_id=f"document-{number}",
                evidence_ids=(f"evidence-{number}",),
                text=f"Assessment {number}",
                recorded_at=self.now,
            )
            for number in (1, 2)
        )
        note = ResearchSourceComparisonNoteRecord(
            note_id="comparison-note-1",
            source_document_ids=("document-1", "document-2"),
            evidence_ids=("evidence-1", "evidence-2"),
            assessment_ids=("assessment-1", "assessment-2"),
            text="My comparison note.",
            recorded_at=self.now,
        )
        run = ResearchRun(
            run_id="run-1",
            question="Compare sources",
            status=ResearchRunStatus.COLLECTING,
            sources=sources,
            failures=(),
            created_at=self.now,
            updated_at=self.now,
            evidence=evidence,
            assessments=assessments,
            comparison_notes=(note,),
        )

        self.store.save([run])

        self.assertEqual(self.store.load(), [run])

    def test_round_trip_preserves_claim_contradiction_and_rejects_tampering(
        self,
    ) -> None:
        sources = tuple(
            ResearchSourceRecord(
                f"document-{number}",
                f"https://example.com/{number}",
                f"Source {number}",
                "text/plain",
                self.now,
                self.now,
            )
            for number in (1, 2)
        )
        evidence = tuple(
            ResearchEvidenceRecord(
                f"evidence-{number}",
                f"document-{number}",
                f"chunk-{number}",
                0,
                f"Evidence {number}.",
                False,
                str(number) * 64,
                "Relevant.",
                self.now,
            )
            for number in (1, 2)
        )
        claims = tuple(
            ResearchClaimRecord(
                f"claim-{number}",
                f"Claim {number}.",
                ResearchEpistemicState.LIKELY,
                ResearchClaimConfidence.MEDIUM,
                (f"document-{number}",),
                (f"evidence-{number}",),
                self.now,
            )
            for number in (1, 2)
        )
        contradiction = ResearchClaimContradictionRecord(
            "contradiction-1",
            ("claim-1", "claim-2"),
            ("evidence-1", "evidence-2"),
            "The claims conflict.",
            self.now,
        )
        run = ResearchRun(
            "run-1",
            "Compare claims",
            ResearchRunStatus.COLLECTING,
            sources,
            (),
            self.now,
            self.now,
            evidence=evidence,
            claims=claims,
            claim_contradictions=(contradiction,),
        )

        self.store.save([run])

        self.assertEqual(self.store.load(), [run])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["runs"][0]["claim_contradictions"][0]["evidence_ids"] = [
            "evidence-2",
            "evidence-1",
        ]
        self.path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(ResearchError, "evidence must match"):
            self.store.load()

    def test_invalid_json_is_reported_without_exposing_raw_content(self) -> None:
        self.path.write_text("{secret", encoding="utf-8")

        with self.assertRaisesRegex(ResearchError, "Unable to read") as context:
            self.store.load()

        self.assertNotIn("secret", str(context.exception))

    def test_oversized_file_is_rejected_before_json_decoding(self) -> None:
        self.path.write_bytes(b"{}")

        with (
            patch(
                "research.JsonFileResearchRunStore.MAX_RESEARCH_RUN_STORE_BYTES",
                1,
            ),
            patch(
                "research.JsonFileResearchRunStore.json.loads",
                side_effect=AssertionError("Oversized JSON must not be decoded."),
            ),
        ):
            with self.assertRaisesRegex(ResearchError, "too large"):
                self.store.load()

    def test_collection_bound_is_checked_before_run_parsing(self) -> None:
        self.store.save([self._minimal_run()])

        with (
            patch(
                "research.JsonFileResearchRunStore."
                "MAX_RESEARCH_RUN_STORE_COLLECTION_ITEMS",
                0,
            ),
            patch.object(
                self.store,
                "_parse_run",
                side_effect=AssertionError("Oversized runs must not be parsed."),
            ),
        ):
            with self.assertRaisesRegex(ResearchError, "too many collection items"):
                self.store.load()

    def test_exact_collection_bound_remains_compatible(self) -> None:
        run = self._minimal_run()

        with patch(
            "research.JsonFileResearchRunStore."
            "MAX_RESEARCH_RUN_STORE_COLLECTION_ITEMS",
            1,
        ):
            self.store.save([run])
            loaded = self.store.load()

        self.assertEqual(loaded, [run])

    def test_collection_bound_counts_nested_records_aggregately(self) -> None:
        run = replace(
            self._minimal_run(),
            sources=(
                ResearchSourceRecord(
                    document_id="document-1",
                    url="https://example.com/source",
                    title="Source",
                    content_type="text/plain",
                    fetched_at=self.now,
                    added_at=self.now,
                ),
            ),
        )

        with patch(
            "research.JsonFileResearchRunStore."
            "MAX_RESEARCH_RUN_STORE_COLLECTION_ITEMS",
            1,
        ):
            with self.assertRaisesRegex(ResearchError, "too many collection items"):
                self.store.save([run])

        self.assertFalse(self.path.exists())

    def test_oversized_save_preserves_snapshot_and_cleans_temporary_file(self) -> None:
        original = self._minimal_run("original-run")
        self.store.save([original])
        original_bytes = self.path.read_bytes()

        with patch(
            "research.JsonFileResearchRunStore.MAX_RESEARCH_RUN_STORE_BYTES",
            1,
        ):
            with self.assertRaisesRegex(ResearchError, "too large"):
                self.store.save([])

        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_utf8_byte_limit_is_exact_and_includes_the_final_newline(self) -> None:
        run = replace(self._minimal_run(), question="Songül için kanıt")
        self.store.save([run])
        encoded_snapshot = self.path.read_bytes()

        with patch(
            "research.JsonFileResearchRunStore.MAX_RESEARCH_RUN_STORE_BYTES",
            len(encoded_snapshot),
        ):
            self.store.save([run])

        self.assertEqual(self.path.read_bytes(), encoded_snapshot)
        with patch(
            "research.JsonFileResearchRunStore.MAX_RESEARCH_RUN_STORE_BYTES",
            len(encoded_snapshot) - 1,
        ):
            with self.assertRaisesRegex(ResearchError, "too large"):
                self.store.save([run])
        self.assertEqual(self.path.read_bytes(), encoded_snapshot)

    def test_oversized_collection_is_rejected_before_serialization(self) -> None:
        original = self._minimal_run("original-run")
        self.store.save([original])
        original_bytes = self.path.read_bytes()

        with (
            patch(
                "research.JsonFileResearchRunStore."
                "MAX_RESEARCH_RUN_STORE_COLLECTION_ITEMS",
                0,
            ),
            patch.object(
                self.store,
                "_serialize_run",
                side_effect=AssertionError("Oversized runs must not be serialized."),
            ),
        ):
            with self.assertRaisesRegex(ResearchError, "too many collection items"):
                self.store.save([self._minimal_run("replacement-run")])

        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_failed_atomic_replace_preserves_previous_snapshot_and_cleans_temp(
        self,
    ) -> None:
        original = ResearchRun(
            run_id="run-1",
            question="Original question",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=self.now,
            updated_at=self.now,
        )
        replacement = ResearchRun(
            run_id="run-2",
            question="Replacement question",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=self.now,
            updated_at=self.now,
        )
        self.store.save([original])
        original_document = self.path.read_text(encoding="utf-8")

        with patch(
            "research.JsonFileResearchRunStore.os.replace",
            side_effect=OSError("replace unavailable"),
        ):
            with self.assertRaisesRegex(ResearchError, "Unable to write"):
                self.store.save([replacement])

        self.assertEqual(self.path.read_text(encoding="utf-8"), original_document)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
