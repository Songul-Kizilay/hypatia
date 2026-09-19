"""HTTPS header lookups bind their argv and digest to one resolved address."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
    ResearchKaliOperationPreview,
    kali_operation_command_plan,
    kali_operation_preview_document,
)
from research.ResearchProgramScopeExecutionPolicy import (
    ResearchProgramScopeCheckClass,
)

NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)


def preview(
    *,
    operation_kind: ResearchKaliOperationKind = (
        ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP
    ),
    dns_record_type: ResearchDnsRecordType | None = None,
    resolved_address: str | None = "93.184.216.34",
) -> ResearchKaliOperationPreview:
    return ResearchKaliOperationPreview(
        program_id="program-a",
        scope_revision_id="scope-revision-1",
        scope_revision_digest="scope-digest-1",
        execution_policy_digest="policy-digest-1",
        operation_kind=operation_kind,
        check_class=(
            ResearchProgramScopeCheckClass.PUBLIC_HTTPS_CONTENT
            if operation_kind is ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP
            else ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP
        ),
        hostname="www.example.test",
        dns_record_type=dns_record_type,
        resolved_address=resolved_address,
        permitted_ports=(443,),
        max_request_count=1,
        max_requests_per_minute=1,
        max_seconds=10.0,
        created_at=NOW,
    )


class KaliOperationCommandPlanResolvedAddressTests(unittest.TestCase):
    def test_https_header_lookup_pins_curl_to_the_resolved_address(self) -> None:
        plan = kali_operation_command_plan(
            operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
            hostname="www.example.test",
            resolved_address="93.184.216.34",
        )

        self.assertEqual(
            plan.argv,
            (
                "/usr/bin/curl",
                "--head",
                "--silent",
                "--show-error",
                "--max-time",
                "10",
                "--proto",
                "=https",
                "--resolve",
                "www.example.test:443:93.184.216.34",
                "https://www.example.test/",
            ),
        )

    def test_https_header_lookup_brackets_an_ipv6_resolved_address(self) -> None:
        plan = kali_operation_command_plan(
            operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
            hostname="www.example.test",
            resolved_address="2606:2800:220:1:248:1893:25c8:1946",
        )

        self.assertIn(
            "www.example.test:443:[2606:2800:220:1:248:1893:25c8:1946]",
            plan.argv,
        )

    def test_https_header_lookup_requires_a_resolved_address(self) -> None:
        for bad_address in (None, "", "not-an-ip-address"):
            with self.subTest(bad_address=bad_address):
                with self.assertRaisesRegex(
                    ResearchError, "resolved address is invalid"
                ):
                    kali_operation_command_plan(
                        operation_kind=(ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP),
                        hostname="www.example.test",
                        resolved_address=bad_address,
                    )

    def test_dns_lookup_rejects_a_resolved_address(self) -> None:
        with self.assertRaisesRegex(
            ResearchError, "resolved address is not applicable"
        ):
            kali_operation_command_plan(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                hostname="www.example.test",
                dns_record_type=ResearchDnsRecordType.A,
                resolved_address="93.184.216.34",
            )


class ResearchKaliOperationPreviewResolvedAddressTests(unittest.TestCase):
    def test_https_header_lookup_preview_requires_a_valid_resolved_address(
        self,
    ) -> None:
        for bad_address in (None, "", "not-an-ip-address"):
            with self.subTest(bad_address=bad_address):
                with self.assertRaisesRegex(
                    ResearchError, "resolved address is invalid"
                ):
                    preview(resolved_address=bad_address)

    def test_dns_lookup_preview_rejects_a_resolved_address(self) -> None:
        with self.assertRaisesRegex(
            ResearchError, "resolved address is not applicable"
        ):
            preview(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                dns_record_type=ResearchDnsRecordType.A,
                resolved_address="93.184.216.34",
            )

    def test_dns_lookup_preview_allows_no_resolved_address(self) -> None:
        result = preview(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            dns_record_type=ResearchDnsRecordType.A,
            resolved_address=None,
        )
        self.assertIsNone(result.resolved_address)

    def test_a_different_resolved_address_changes_the_operation_digest(self) -> None:
        first = preview(resolved_address="93.184.216.34")
        second = preview(resolved_address="8.8.8.8")

        self.assertNotEqual(first.operation_digest, second.operation_digest)

    def test_resolved_address_is_part_of_the_preview_document(self) -> None:
        document = kali_operation_preview_document(preview())

        self.assertEqual(document["resolved_address"], "93.184.216.34")


if __name__ == "__main__":
    unittest.main()
