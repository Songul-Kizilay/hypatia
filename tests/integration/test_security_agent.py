"""The security agent audits Hypatia, and has no vocabulary to audit anyone else.

The scope is the safety property. There is no scan intent, no probe intent, no
target parameter, and no field anywhere in this component for someone else's
system — an agent that reached outward would need authorisation this software
cannot establish, so it does not have the words to try. The tests assert that
absence directly, and assert the audit opens no socket.

The second property is that a clean report stays interpretable. "No findings"
over nothing examined and "no findings" over four hundred sources are very
different sentences, so scope is reported alongside findings and asserted here.

The third is that nothing is repaired. A finding says what is wrong; what to do
about a source already accepted, cited, and reasoned from is a judgement with
consequences the auditor cannot see.
"""

from __future__ import annotations

import json
import socket
import sys
import tempfile
import unittest
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from cognition.SecurityAgentApplicationService import SecurityAgentApplicationService
from cognition.SecurityAgentEvents import POSTURE_AUDITED
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceRecord import ResearchSourceRecord
from response.ResponseComposer import ResponseComposer
from security.SecurityFinding import SecurityFinding
from security.SecurityFindingKind import (
    SecurityFindingKind,
    SecurityFindingSeverity,
    severity_for,
)
from security.SecurityPostureAuditor import CHECK_COUNT, SecurityPostureAuditor
from security.SecurityPostureReport import SecurityPostureReport
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the ring system have a measured age?"
FETCHED = datetime(2026, 8, 1, tzinfo=UTC)

FORBIDDEN_FIELDS = ("target", "host", "port", "scan_target", "endpoint")


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


class AuditScopeTests(unittest.TestCase):
    def test_a_finding_has_nowhere_to_name_an_external_system(self) -> None:
        names = {entry.name for entry in fields(SecurityFinding)}

        for forbidden in FORBIDDEN_FIELDS:
            with self.subTest(field=forbidden):
                self.assertNotIn(forbidden, names)

    def test_the_service_offers_no_scan_or_probe(self) -> None:
        """The absence is the design, so it is asserted rather than assumed."""
        service = SecurityAgentApplicationService

        for forbidden in ("process_scan", "process_probe", "process_exploit"):
            with self.subTest(method=forbidden):
                self.assertFalse(hasattr(service, forbidden))

    def test_every_finding_kind_declares_a_severity(self) -> None:
        for kind in SecurityFindingKind:
            self.assertIsInstance(severity_for(kind), SecurityFindingSeverity)

    def test_an_unclassified_finding_kind_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            severity_for("invented_kind")  # type: ignore[arg-type]

    def test_only_the_serious_severities_need_action(self) -> None:
        self.assertFalse(SecurityFindingSeverity.INFO.needs_action)
        self.assertFalse(SecurityFindingSeverity.LOW.needs_action)
        self.assertTrue(SecurityFindingSeverity.MEDIUM.needs_action)
        self.assertTrue(SecurityFindingSeverity.HIGH.needs_action)

    def test_severity_ranks_in_the_expected_order(self) -> None:
        ranks = [severity.rank for severity in SecurityFindingSeverity]

        self.assertEqual(ranks, sorted(ranks))

    def test_acquisition_findings_are_distinguished(self) -> None:
        self.assertTrue(SecurityFindingKind.NON_HTTPS_SOURCE.concerns_acquisition)
        self.assertFalse(SecurityFindingKind.DUPLICATE_SOURCE_URL.concerns_acquisition)

    def test_a_report_rejects_a_negative_scope_count(self) -> None:
        with self.assertRaises(ResearchError):
            SecurityPostureReport(
                findings=(),
                checks_run=-1,
                runs_examined=0,
                sources_examined=0,
                evidence_examined=0,
                claims_examined=0,
            )

    def test_an_empty_report_reports_no_highest_severity(self) -> None:
        report = SecurityPostureReport(
            findings=(),
            checks_run=CHECK_COUNT,
            runs_examined=0,
            sources_examined=0,
            evidence_examined=0,
            claims_examined=0,
        )

        self.assertTrue(report.clean)
        self.assertIsNone(report.highest_severity)


class AuditorFixture(unittest.TestCase):
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
        self.auditor = SecurityPostureAuditor()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def service(self) -> SecurityAgentApplicationService:
        return SecurityAgentApplicationService(
            self.manager,
            ResponseComposer(),
            event_bus=self.event_bus,
        )

    def new_run(self) -> str:
        return self.manager.create(QUESTION).run_id

    def accept(self, run_id: str, slug: str = "a") -> str:
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

    @staticmethod
    def with_source_url(run: ResearchRun, url: str) -> ResearchRun:
        """Return the run with its one source rewritten to a different URL.

        Constructed directly rather than through the manager, because the fetch
        boundary refuses these URLs — which is the point. The audit exists for
        the case where such a record reached the store anyway.
        """
        source = run.sources[0]
        rewritten = ResearchSourceRecord(
            document_id=source.document_id,
            url=url,
            title=source.title,
            content_type=source.content_type,
            fetched_at=source.fetched_at,
            added_at=source.added_at,
        )
        return replace(run, sources=(rewritten,))

    def request(self, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="Audit",
            metadata={"intent": "security_posture_audit", **metadata},
        )

    def named(self, name: str) -> list[Event]:
        return [event for event in self.events if event.name == name]


class AuditorTests(AuditorFixture):
    def test_a_healthy_run_produces_no_findings(self) -> None:
        run_id = self.new_run()
        document_id = self.accept(run_id)
        self.add_evidence(run_id, document_id)

        report = self.auditor.audit(self.manager.list())

        self.assertTrue(report.clean)
        self.assertEqual(report.sources_examined, 1)
        self.assertEqual(report.evidence_examined, 1)

    def test_a_clean_report_still_states_what_it_examined(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)

        report = self.auditor.audit(self.manager.list())

        self.assertEqual(report.checks_run, CHECK_COUNT)
        self.assertIn("Sources examined: 1", report.scope_lines())

    def test_a_plain_http_source_is_found(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)
        run = self.with_source_url(self.manager.get(run_id), "http://example.test/a")

        report = self.auditor.audit((run,))

        self.assertEqual(len(report.of_kind(SecurityFindingKind.NON_HTTPS_SOURCE)), 1)

    def test_a_loopback_source_is_found(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)
        for url in (
            "https://127.0.0.1/a",
            "https://localhost/a",
            "https://[::1]/a",
            "https://10.0.0.5/a",
            "https://192.168.1.1/a",
            "https://169.254.169.254/a",
        ):
            with self.subTest(url=url):
                run = self.with_source_url(self.manager.get(run_id), url)

                report = self.auditor.audit((run,))

                self.assertEqual(
                    len(report.of_kind(SecurityFindingKind.NON_PUBLIC_SOURCE)),
                    1,
                    url,
                )

    def test_a_public_source_is_not_reported_as_private(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)
        run = self.with_source_url(self.manager.get(run_id), "https://93.184.216.34/a")

        report = self.auditor.audit((run,))

        self.assertEqual(report.of_kind(SecurityFindingKind.NON_PUBLIC_SOURCE), ())

    def test_embedded_credentials_are_found(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)
        run = self.with_source_url(
            self.manager.get(run_id),
            "https://user:secret@example.test/a",
        )

        report = self.auditor.audit((run,))

        findings = report.of_kind(SecurityFindingKind.CREDENTIALS_IN_SOURCE_URL)
        self.assertEqual(len(findings), 1)
        self.assertNotIn("secret", findings[0].detail)

    def test_a_source_that_lost_its_untrusted_label_is_found(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)
        run = self.manager.get(run_id)
        source = run.sources[0]
        tampered = object.__new__(ResearchSourceRecord)
        for name, value in (
            ("document_id", source.document_id),
            ("url", source.url),
            ("title", source.title),
            ("content_type", source.content_type),
            ("fetched_at", source.fetched_at),
            ("added_at", source.added_at),
            ("taint_label", "trusted"),
            ("instruction_authority", "none"),
        ):
            object.__setattr__(tampered, name, value)

        report = self.auditor.audit((replace(run, sources=(tampered,)),))

        self.assertEqual(len(report.of_kind(SecurityFindingKind.UNLABELLED_SOURCE)), 1)

    def test_a_source_claiming_instruction_authority_is_high_severity(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)
        run = self.manager.get(run_id)
        source = run.sources[0]
        tampered = object.__new__(ResearchSourceRecord)
        for name, value in (
            ("document_id", source.document_id),
            ("url", source.url),
            ("title", source.title),
            ("content_type", source.content_type),
            ("fetched_at", source.fetched_at),
            ("added_at", source.added_at),
            ("taint_label", source.taint_label),
            ("instruction_authority", "full"),
        ):
            object.__setattr__(tampered, name, value)

        report = self.auditor.audit((replace(run, sources=(tampered,)),))

        findings = report.of_kind(
            SecurityFindingKind.SOURCE_CLAIMS_INSTRUCTION_AUTHORITY
        )
        self.assertEqual(len(findings), 1)
        self.assertIs(findings[0].severity, SecurityFindingSeverity.HIGH)
        self.assertIn("must never be able to direct behaviour", findings[0].detail)

    def test_referential_integrity_is_the_type_s_job_not_the_audit_s(self) -> None:
        """The run type refuses these outright, so auditing them would be theatre."""
        run_id = self.new_run()
        document_id = self.accept(run_id)
        evidence_id = self.add_evidence(run_id, document_id)
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings exist.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        run = self.manager.get(run_id)

        with self.assertRaises(ResearchError):
            replace(run, sources=())
        with self.assertRaises(ResearchError):
            replace(run, evidence=())

    def test_one_page_accepted_twice_is_found(self) -> None:
        """Two records sharing a URL would read as independent corroboration."""
        run_id = self.new_run()
        self.accept(run_id, "a")
        run = self.manager.get(run_id)
        original = run.sources[0]
        twin = ResearchSourceRecord(
            document_id="second-document",
            url=original.url,
            title=original.title,
            content_type=original.content_type,
            fetched_at=original.fetched_at,
            added_at=original.added_at,
        )

        report = self.auditor.audit(
            (replace(run, sources=(original, twin), evidence=()),)
        )

        self.assertEqual(
            len(report.of_kind(SecurityFindingKind.DUPLICATE_SOURCE_URL)),
            2,
        )

    def test_two_different_pages_are_not_reported_as_duplicates(self) -> None:
        run_id = self.new_run()
        self.accept(run_id, "a")
        self.accept(run_id, "b")

        report = self.auditor.audit(self.manager.list())

        self.assertEqual(report.of_kind(SecurityFindingKind.DUPLICATE_SOURCE_URL), ())

    def test_an_unacceptable_content_type_is_found(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)
        run = self.manager.get(run_id)
        original = run.sources[0]
        rewritten = ResearchSourceRecord(
            document_id=original.document_id,
            url=original.url,
            title=original.title,
            content_type="application/pdf",
            fetched_at=original.fetched_at,
            added_at=original.added_at,
        )

        report = self.auditor.audit((replace(run, sources=(rewritten,), evidence=()),))

        self.assertEqual(
            len(report.of_kind(SecurityFindingKind.UNSUPPORTED_CONTENT_TYPE)),
            1,
        )

    def test_timestamps_in_the_wrong_order_are_found(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)
        run = self.manager.get(run_id)
        original = run.sources[0]
        rewritten = ResearchSourceRecord(
            document_id=original.document_id,
            url=original.url,
            title=original.title,
            content_type=original.content_type,
            fetched_at=original.added_at + timedelta(days=1),
            added_at=original.added_at,
        )

        report = self.auditor.audit((replace(run, sources=(rewritten,), evidence=()),))

        self.assertEqual(
            len(report.of_kind(SecurityFindingKind.IMPLAUSIBLE_PROVENANCE)),
            1,
        )

    def test_the_taint_checks_are_declared_as_defence_in_depth(self) -> None:
        """They duplicate a type invariant, and the code says so."""
        self.assertTrue(SecurityFindingKind.UNLABELLED_SOURCE.covered_by_a_type)
        self.assertTrue(
            SecurityFindingKind.SOURCE_CLAIMS_INSTRUCTION_AUTHORITY.covered_by_a_type
        )
        self.assertFalse(SecurityFindingKind.NON_HTTPS_SOURCE.covered_by_a_type)
        self.assertFalse(SecurityFindingKind.DUPLICATE_SOURCE_URL.covered_by_a_type)

    def test_findings_are_ordered_worst_first(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)
        run = self.with_source_url(self.manager.get(run_id), "http://127.0.0.1/a")

        report = self.auditor.audit((run,))
        ranks = [finding.severity.rank for finding in report.findings]

        self.assertTrue(report.findings)
        self.assertEqual(ranks, sorted(ranks, reverse=True))

    def test_no_run_means_a_clean_report_over_nothing(self) -> None:
        report = self.auditor.audit(())

        self.assertTrue(report.clean)
        self.assertEqual(report.runs_examined, 0)
        self.assertEqual(report.checks_run, CHECK_COUNT)


class AuditContactsNothingTests(AuditorFixture):
    def test_the_audit_opens_no_socket(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)
        run = self.with_source_url(self.manager.get(run_id), "https://example.test/a")

        with patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("the audit reached the network"),
        ):
            with patch.object(
                socket,
                "getaddrinfo",
                side_effect=AssertionError("the audit resolved a name"),
            ):
                report = self.auditor.audit((run,))

        self.assertTrue(report.clean)

    def test_the_audit_changes_no_record(self) -> None:
        run_id = self.new_run()
        document_id = self.accept(run_id)
        self.add_evidence(run_id, document_id)
        before = self.run_path.read_bytes()

        for _ in range(3):
            self.service().process_audit(self.request())

        self.assertEqual(self.run_path.read_bytes(), before)

    def test_the_response_says_it_contacted_and_repaired_nothing(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)

        response = self.service().process_audit(self.request())

        self.assertIn("contacted no external system", response.message)
        self.assertIn("repaired", response.message)
        self.assertIn("a judgement it cannot make for you", response.message)

    def test_a_clean_response_refuses_to_claim_safety(self) -> None:
        response = self.service().process_audit(self.request())

        self.assertIn("not that the system is safe", response.message)

    def test_the_report_is_derived_not_stored(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)

        self.service().process_audit(self.request())
        files = sorted(path.name for path in self.root.glob("*.json"))

        self.assertEqual(files, ["runs.json"])


class SecurityAgentServiceTests(AuditorFixture):
    def test_one_run_can_be_audited_alone(self) -> None:
        first = self.new_run()
        self.accept(first, "a")
        second = self.new_run()
        self.accept(second, "b")

        response = self.service().process_audit(self.request(research_run_id=second))

        assert response.security_posture is not None
        self.assertEqual(response.security_posture.runs_examined, 1)

    def test_every_run_is_audited_by_default(self) -> None:
        self.accept(self.new_run(), "a")
        self.accept(self.new_run(), "b")

        response = self.service().process_audit(self.request())

        assert response.security_posture is not None
        self.assertEqual(response.security_posture.runs_examined, 2)

    def test_a_blank_run_identifier_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.service().process_audit(self.request(research_run_id="  "))

    def test_an_unknown_run_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.service().process_audit(self.request(research_run_id="run-missing"))


class SecurityAgentEventTests(AuditorFixture):
    def test_auditing_emits_one_bounded_event(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)

        self.service().process_audit(self.request())

        events = self.named(POSTURE_AUDITED)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["external_systems_contacted"], 0)
        self.assertEqual(events[0].payload["records_modified"], 0)
        self.assertEqual(events[0].payload["checks_run"], CHECK_COUNT)

    def test_the_event_reports_scope_even_when_clean(self) -> None:
        self.accept(self.new_run())

        self.service().process_audit(self.request())

        payload = self.named(POSTURE_AUDITED)[0].payload
        self.assertEqual(payload["finding_count"], 0)
        self.assertIsNone(payload["highest_severity"])
        self.assertEqual(payload["sources_examined"], 1)

    def test_no_event_carries_a_url_or_a_question(self) -> None:
        run_id = self.new_run()
        self.accept(run_id)

        self.service().process_audit(self.request())

        payloads = json.dumps(
            [
                event.payload
                for event in self.events
                if event.name.startswith("security_agent")
            ]
        )
        self.assertTrue(payloads)
        self.assertNotIn("example.test", payloads)
        self.assertNotIn(QUESTION, payloads)


class SecurityAgentCompositionTests(AuditorFixture):
    def test_the_engine_routes_the_audit_over_the_run_manager(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()
        self.accept(run_id)

        response = engine.process(self.request())

        service = engine._security_agent_service
        self.assertIsInstance(service, SecurityAgentApplicationService)
        assert service is not None
        self.assertIs(service._run_manager, self.manager)
        assert response.security_posture is not None
        self.assertEqual(response.security_posture.sources_examined, 1)

    def test_the_audit_is_refused_without_run_persistence(self) -> None:
        engine = self.build_engine(with_runs=False)

        response = engine.process(self.request())

        self.assertIsNone(engine._security_agent_service)
        self.assertFalse(response.success)
        self.assertIn("unavailable", response.message)

    def test_an_unknown_run_is_refused_without_raising(self) -> None:
        engine = self.build_engine()

        response = engine.process(self.request(research_run_id="run-missing"))

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
