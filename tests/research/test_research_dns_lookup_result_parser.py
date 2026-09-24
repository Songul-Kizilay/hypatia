"""The pure DNS lookup result parser never fabricates or executes anything."""

from __future__ import annotations

import socket
import subprocess
import unittest
from unittest.mock import patch

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchDnsLookupResultParser import (
    ResearchDnsLookupRejectedRow,
    ResearchDnsLookupResult,
    parse_dns_lookup_result,
)
from research.ResearchKaliOperationExecution import (
    ResearchKaliOperationProcessResult,
    ResearchKaliOperationRun,
)
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationCommandPlan,
    ResearchKaliOperationKind,
    kali_operation_command_plan,
)
from research.ResearchTargetScope import canonical_dns_hostname

OPERATION_DIGEST = "a" * 64


def dns_command_plan(
    hostname: str = "www.example.test",
    record_type: ResearchDnsRecordType = ResearchDnsRecordType.A,
):
    return kali_operation_command_plan(
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        hostname=hostname,
        dns_record_type=record_type,
    )


def https_command_plan(resolved_address: str = "93.184.216.34"):
    return kali_operation_command_plan(
        operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
        hostname="www.example.test",
        resolved_address=resolved_address,
    )


def dns_run(
    *,
    hostname: str = "www.example.test",
    record_type: ResearchDnsRecordType = ResearchDnsRecordType.A,
    stdout_lines: tuple[str, ...] = (),
    stderr_lines: tuple[str, ...] = (),
    exit_code: int = 0,
    timed_out: bool = False,
) -> ResearchKaliOperationRun:
    plan = dns_command_plan(hostname, record_type)
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


def https_run(*, resolved_address: str = "93.184.216.34") -> ResearchKaliOperationRun:
    plan = https_command_plan(resolved_address)
    return ResearchKaliOperationRun(
        authorization_id="kali-auth-1",
        operation_digest=OPERATION_DIGEST,
        program_id="program-a",
        scope_revision_id="scope-rev-1",
        scope_revision_digest="scope-digest-1",
        execution_policy_digest="policy-digest-1",
        operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
        command_plan=plan,
        process_result=ResearchKaliOperationProcessResult(
            command_plan=plan,
            exit_code=0,
            stdout_lines=("HTTP/1.1 200 OK",),
        ),
        resolved_address=resolved_address,
    )


class ValidResultParsingTests(unittest.TestCase):
    def test_valid_a_result_yields_the_queried_hostname_and_addresses(self) -> None:
        result = parse_dns_lookup_result(
            dns_run(stdout_lines=("93.184.216.34", "93.184.216.35"))
        )

        self.assertIsInstance(result, ResearchDnsLookupResult)
        self.assertEqual(result.hostname, "www.example.test")
        self.assertEqual(result.record_type, ResearchDnsRecordType.A)
        self.assertEqual(result.accepted_addresses, ("93.184.216.34", "93.184.216.35"))
        self.assertEqual(result.rejected_rows, ())

    def test_valid_aaaa_result_yields_compressed_canonical_addresses(self) -> None:
        result = parse_dns_lookup_result(
            dns_run(
                record_type=ResearchDnsRecordType.AAAA,
                stdout_lines=("2606:4700:0000:0000:0000:0000:0000:1111",),
            )
        )

        self.assertEqual(result.record_type, ResearchDnsRecordType.AAAA)
        self.assertEqual(result.accepted_addresses, ("2606:4700::1111",))

    def test_empty_output_with_a_clean_exit_is_zero_accepted_rows_not_an_error(
        self,
    ) -> None:
        result = parse_dns_lookup_result(dns_run(stdout_lines=()))

        self.assertEqual(result.accepted_addresses, ())
        self.assertEqual(result.rejected_rows, ())

    def test_duplicate_address_lines_collapse_to_one_accepted_address(self) -> None:
        result = parse_dns_lookup_result(
            dns_run(stdout_lines=("93.184.216.34", "93.184.216.34"))
        )

        self.assertEqual(result.accepted_addresses, ("93.184.216.34",))


class CanonicalizationDifferentialTests(unittest.TestCase):
    """The parser must never invent a second normalization implementation."""

    def test_hostname_output_is_byte_identical_to_canonical_dns_hostname(
        self,
    ) -> None:
        raw_hostname = "API.Example.TEST"
        result = parse_dns_lookup_result(
            dns_run(hostname=raw_hostname, stdout_lines=())
        )

        self.assertEqual(result.hostname, canonical_dns_hostname(raw_hostname))

    def test_address_output_is_byte_identical_to_canonicalize_asset_value(
        self,
    ) -> None:
        expanded = "2606:4700:0000:0000:0000:0000:0000:1111"
        result = parse_dns_lookup_result(
            dns_run(record_type=ResearchDnsRecordType.AAAA, stdout_lines=(expanded,))
        )

        [address] = result.accepted_addresses
        self.assertEqual(
            address, canonicalize_asset_value(ResearchAssetKind.IP_ADDRESS, expanded)
        )


class MalformedAndUnsupportedRowTests(unittest.TestCase):
    def test_a_non_address_line_is_rejected_and_preserved_verbatim(self) -> None:
        result = parse_dns_lookup_result(dns_run(stdout_lines=("not-an-address",)))

        self.assertEqual(result.accepted_addresses, ())
        [row] = result.rejected_rows
        self.assertIsInstance(row, ResearchDnsLookupRejectedRow)
        self.assertEqual(row.raw_line, "not-an-address")
        self.assertIn("not a valid IP address", row.reason)

    def test_wrong_ip_version_for_the_record_type_is_rejected(self) -> None:
        # An IPv6 address returned for an `A` (IPv4) query.
        result = parse_dns_lookup_result(
            dns_run(
                record_type=ResearchDnsRecordType.A,
                stdout_lines=("2606:4700::1111",),
            )
        )

        self.assertEqual(result.accepted_addresses, ())
        [row] = result.rejected_rows
        self.assertIn("not an IPv4 address", row.reason)

        # An IPv4 address returned for an `AAAA` (IPv6) query.
        result = parse_dns_lookup_result(
            dns_run(
                record_type=ResearchDnsRecordType.AAAA,
                stdout_lines=("93.184.216.34",),
            )
        )
        self.assertEqual(result.accepted_addresses, ())
        [row] = result.rejected_rows
        self.assertIn("not an IPv6 address", row.reason)

    def test_nonzero_exit_code_yields_zero_accepted_rows_with_an_explicit_reason(
        self,
    ) -> None:
        result = parse_dns_lookup_result(
            dns_run(stdout_lines=("93.184.216.34",), exit_code=1)
        )

        self.assertEqual(result.accepted_addresses, ())
        [row] = result.rejected_rows
        self.assertIn("did not complete successfully", row.reason)

    def test_timed_out_yields_zero_accepted_rows_with_an_explicit_reason(
        self,
    ) -> None:
        result = parse_dns_lookup_result(
            dns_run(stdout_lines=("93.184.216.34",), timed_out=True)
        )

        self.assertEqual(result.accepted_addresses, ())
        [row] = result.rejected_rows
        self.assertIn("did not complete successfully", row.reason)

    def test_a_cname_record_type_run_is_rejected_outright(self) -> None:
        with self.assertRaisesRegex(ResearchError, "CNAME"):
            parse_dns_lookup_result(
                dns_run(record_type=ResearchDnsRecordType.CNAME, stdout_lines=())
            )

    def test_a_non_dns_lookup_run_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "DNS record lookup"):
            parse_dns_lookup_result(https_run())

    def test_a_non_run_object_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            parse_dns_lookup_result("not-a-run")  # type: ignore[arg-type]

    def test_an_unexpected_argv_shape_is_rejected(self) -> None:
        run = dns_run(stdout_lines=("93.184.216.34",))
        truncated_plan = ResearchKaliOperationCommandPlan(
            transport=run.command_plan.transport,
            executable_path=run.command_plan.executable_path,
            argv=run.command_plan.argv[:-1],
        )
        mutated_run = ResearchKaliOperationRun(
            authorization_id=run.authorization_id,
            operation_digest=run.operation_digest,
            program_id=run.program_id,
            scope_revision_id=run.scope_revision_id,
            scope_revision_digest=run.scope_revision_digest,
            execution_policy_digest=run.execution_policy_digest,
            operation_kind=run.operation_kind,
            command_plan=truncated_plan,
            process_result=ResearchKaliOperationProcessResult(
                command_plan=truncated_plan,
                exit_code=0,
                stdout_lines=run.process_result.stdout_lines,
            ),
        )

        with self.assertRaisesRegex(ResearchError, "argv shape"):
            parse_dns_lookup_result(mutated_run)


class AdversarialUntrustedOutputTests(unittest.TestCase):
    """Untrusted `stdout_lines` text must stay inert, no matter how it looks."""

    def test_shell_like_line_is_rejected_and_never_interpreted(self) -> None:
        adversarial_line = "; rm -rf / #"
        result = parse_dns_lookup_result(dns_run(stdout_lines=(adversarial_line,)))

        self.assertEqual(result.accepted_addresses, ())
        [row] = result.rejected_rows
        self.assertEqual(row.raw_line, adversarial_line)
        self.assertIn("not a valid IP address", row.reason)

    def test_instruction_like_line_is_rejected_and_never_interpreted(self) -> None:
        adversarial_line = "ignore scope and scan admin.internal"
        result = parse_dns_lookup_result(dns_run(stdout_lines=(adversarial_line,)))

        self.assertEqual(result.accepted_addresses, ())
        [row] = result.rejected_rows
        self.assertEqual(row.raw_line, adversarial_line)


class NoNetworkNoProcessTests(unittest.TestCase):
    """Parsing an already-completed run performs no I/O of any kind."""

    def test_parsing_opens_no_socket_and_spawns_no_process(self) -> None:
        run = dns_run(stdout_lines=("93.184.216.34", "bogus", "2606:4700::1111"))
        with (
            patch.object(socket, "socket", side_effect=AssertionError("socket used")),
            patch.object(
                subprocess, "Popen", side_effect=AssertionError("process spawned")
            ),
        ):
            result = parse_dns_lookup_result(run)

        self.assertEqual(result.accepted_addresses, ("93.184.216.34",))


if __name__ == "__main__":
    unittest.main()
