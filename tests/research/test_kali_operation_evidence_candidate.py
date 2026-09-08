"""Review-only evidence candidates for Kali operation output."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchKaliOperationExecution import (
    KALI_OPERATION_OUTPUT_TRUST,
    MAX_KALI_OPERATION_EVIDENCE_CANDIDATE_LINES,
    ResearchKaliOperationEvidenceCandidate,
    ResearchKaliOperationProcessResult,
    ResearchKaliOperationRun,
    kali_operation_evidence_candidate_for_run,
)
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
    kali_operation_command_plan,
)

OPERATION_DIGEST = "a" * 64


def command_plan():
    return kali_operation_command_plan(
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        hostname="www.example.test",
        dns_record_type=ResearchDnsRecordType.A,
    )


def kali_run(
    *,
    stdout_lines: tuple[str, ...] = ("192.0.2.10",),
    stderr_lines: tuple[str, ...] = (),
    exit_code: int = 0,
    timed_out: bool = False,
) -> ResearchKaliOperationRun:
    plan = command_plan()
    return ResearchKaliOperationRun(
        authorization_id="kali-auth-1",
        operation_digest=OPERATION_DIGEST,
        program_id="program-a",
        scope_revision_id="scope-rev-1",
        scope_revision_digest="scope-digest-1",
        execution_policy_digest="policy-digest-1",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        command_plan=plan,
        process_result=ResearchKaliOperationProcessResult(
            command_plan=plan,
            exit_code=exit_code,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            timed_out=timed_out,
        ),
    )


class KaliOperationEvidenceCandidateTests(unittest.TestCase):
    def test_candidate_is_derived_from_stdout_without_write_claims(self) -> None:
        candidate = kali_operation_evidence_candidate_for_run(
            kali_run(
                stdout_lines=("192.0.2.10", "192.0.2.11"),
                stderr_lines=("diagnostic",),
            )
        )

        self.assertEqual(candidate.operation_digest, OPERATION_DIGEST)
        self.assertEqual(candidate.candidate_lines, ("192.0.2.10", "192.0.2.11"))
        self.assertEqual(candidate.output_trust, KALI_OPERATION_OUTPUT_TRUST)
        self.assertFalse(candidate.candidate_lines_truncated)
        self.assertFalse(candidate.evidence_recorded)
        self.assertFalse(candidate.claim_created)
        self.assertFalse(candidate.source_accepted)
        self.assertFalse(candidate.memory_written)
        self.assertNotIn("diagnostic", candidate.candidate_lines)

    def test_candidate_lines_are_bounded(self) -> None:
        output = tuple(
            f"192.0.2.{index}"
            for index in range(MAX_KALI_OPERATION_EVIDENCE_CANDIDATE_LINES + 3)
        )

        candidate = kali_operation_evidence_candidate_for_run(
            kali_run(stdout_lines=output)
        )

        self.assertEqual(
            len(candidate.candidate_lines),
            MAX_KALI_OPERATION_EVIDENCE_CANDIDATE_LINES,
        )
        self.assertTrue(candidate.candidate_lines_truncated)

    def test_candidate_does_not_require_successful_exit(self) -> None:
        candidate = kali_operation_evidence_candidate_for_run(
            kali_run(stdout_lines=("partial",), exit_code=1, timed_out=False)
        )

        self.assertEqual(candidate.candidate_lines, ("partial",))
        self.assertEqual(candidate.exit_code, 1)
        self.assertFalse(candidate.timed_out)
        self.assertFalse(candidate.evidence_recorded)

    def test_candidate_rejects_any_write_claim(self) -> None:
        with self.assertRaisesRegex(ResearchError, "must not claim writes"):
            ResearchKaliOperationEvidenceCandidate(
                authorization_id="kali-auth-1",
                operation_digest=OPERATION_DIGEST,
                program_id="program-a",
                scope_revision_id="scope-rev-1",
                scope_revision_digest="scope-digest-1",
                execution_policy_digest="policy-digest-1",
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                command_plan=command_plan(),
                candidate_lines=("192.0.2.10",),
                exit_code=0,
                timed_out=False,
                evidence_recorded=True,
            )


if __name__ == "__main__":
    unittest.main()
