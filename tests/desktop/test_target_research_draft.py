"""Desktop scope parsing cannot silently expand authored target boundaries."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from desktop.TargetResearchDraft import (
    MAX_TARGET_FORM_FIELD_CHARACTERS,
    TargetResearchDraft,
)
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput


def fields(**changes: str) -> dict[str, str]:
    return {
        "program_id": "program-a",
        "allowed_hosts": "example.test\n*.example.test",
        "excluded_hosts": "pay.example.test\n*.pay.example.test",
        "allowed_networks": "93.184.216.0/24\n2606:4700::/32",
        "excluded_networks": "93.184.216.35/32\n2606:4700:4700::1111/128",
        "source_urls": "https://example.test/docs\nhttps://api.example.test/",
        "action": "source_fetch",
        **changes,
    }


class TargetResearchDraftTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dns = patch(
            "socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")
        ).start()
        self.socket = patch(
            "socket.create_connection", side_effect=AssertionError("network forbidden")
        ).start()
        self.addCleanup(patch.stopall)

    def tearDown(self) -> None:
        self.dns.assert_not_called()
        self.socket.assert_not_called()

    def test_normalized_ordered_fields_round_trip_and_form_valid_canonical_plan(
        self,
    ) -> None:
        draft = TargetResearchDraft.from_fields(
            **fields(
                program_id="  program-a  ",
                allowed_hosts=" EXAMPLE.TEST. \r\n\r\n*.example.test\r\n",
                source_urls=" HTTPS://EXAMPLE.TEST.:443\r\n\nhttps://api.example.test/docs?q=one%20two\n",
            )
        )
        self.assertEqual(draft.binding.program_id, "program-a")
        self.assertEqual(draft.binding.scope.allowed_hosts[0].host, "example.test")
        self.assertFalse(draft.binding.scope.allowed_hosts[0].subdomains_only)
        self.assertTrue(draft.binding.scope.allowed_hosts[1].subdomains_only)
        self.assertEqual(
            tuple(step.authorized_source_url for step in draft.steps),
            (
                "https://example.test:443/",
                "https://api.example.test/docs?q=one%20two",
            ),
        )
        self.assertEqual(TargetResearchDraft.from_fields(**draft.to_fields()), draft)
        preview = ResearchPlanDraftService().preview(
            "Inspect explicit target documentation",
            draft.steps,
            target_binding=draft.binding,
        )
        self.assertTrue(preview.allowed, preview.reason)
        self.assertEqual(preview.plan.target_binding, draft.binding)
        self.assertEqual(
            tuple(step.authorized_source_url for step in preview.plan.steps),
            tuple(step.authorized_source_url for step in draft.steps),
        )

    def test_fetch_and_accept_are_explicit_and_no_other_actions_are_inferred(
        self,
    ) -> None:
        for action in ("source_fetch", "source_accept"):
            draft = TargetResearchDraft.from_fields(**fields(action=action))
            self.assertTrue(all(step.capability == action for step in draft.steps))
            self.assertEqual(draft.to_fields()["action"], action)
        for action in (
            "",
            "source_discovery",
            "scan",
            "SOURCE_FETCH",
            " source_fetch ",
        ):
            with self.subTest(action=action), self.assertRaises(ResearchError):
                TargetResearchDraft.from_fields(**fields(action=action))

    def test_binding_and_steps_are_immutable(self) -> None:
        draft = TargetResearchDraft.from_fields(**fields())
        self.assertIsInstance(draft.steps, tuple)
        with self.assertRaises(FrozenInstanceError):
            draft.binding = draft.binding  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            draft.steps[0].authorized_source_url = "https://other.test/"  # type: ignore[misc]
        edited = draft.to_fields()
        edited["allowed_hosts"] = "other.test"
        self.assertEqual(draft.binding.scope.allowed_hosts[0].host, "example.test")

    def test_host_rows_never_ignore_unsupported_scope_syntax(self) -> None:
        for value in (
            "https://example.test",
            "example.test:443",
            "example.test/admin",
            "example.test,other.test",
            "example.test # note",
            "# comment",
            "*.example.test except /admin",
            "*example.test",
            "*.*.example.test",
            "example.test.*",
            "example.test..",
            "example.test\t",
            "example.test\vother.test",
            "127.0.0.1",
            "éxample.test",
            "a" * 254,
        ):
            for key in ("allowed_hosts", "excluded_hosts"):
                with (
                    self.subTest(key=key, value=value),
                    self.assertRaises(ResearchError),
                ):
                    TargetResearchDraft.from_fields(**fields(**{key: value}))

    def test_network_rows_require_strict_cidrs(self) -> None:
        for value in (
            "93.184.216.34",
            "93.184.216.35/24",
            "93.184.216.0/24 # note",
            "93.184.216.0/24,8.8.8.0/24",
            "https://93.184.216.34/32",
            "::1/129",
        ):
            for key in ("allowed_networks", "excluded_networks"):
                with (
                    self.subTest(key=key, value=value),
                    self.assertRaises(ResearchError),
                ):
                    TargetResearchDraft.from_fields(**fields(**{key: value}))

    def test_wildcard_does_not_imply_apex_and_exclusions_win(self) -> None:
        for url in (
            "https://example.test/",
            "https://pay.example.test/",
            "https://deep.pay.example.test/",
            "https://other.test/",
        ):
            with self.subTest(url=url), self.assertRaises(ResearchError):
                TargetResearchDraft.from_fields(
                    **fields(allowed_hosts="*.example.test", source_urls=url)
                )
        draft = TargetResearchDraft.from_fields(
            **fields(
                allowed_hosts="*.example.test",
                source_urls="https://deep.api.example.test/",
            )
        )
        self.assertEqual(len(draft.steps), 1)

    def test_literal_ips_require_public_addresses_and_their_own_scope(self) -> None:
        for url in (
            "https://93.184.216.35/",
            "https://8.8.8.8/",
            "https://[2606:4700:4700::1111]/",
        ):
            with self.subTest(url=url), self.assertRaises(ResearchError):
                TargetResearchDraft.from_fields(**fields(source_urls=url))
        for literal, network in (
            ("127.0.0.1", "127.0.0.0/8"),
            ("10.0.0.1", "10.0.0.0/8"),
            ("169.254.169.254", "169.254.0.0/16"),
            ("[::1]", "::1/128"),
            ("224.0.0.1", "224.0.0.0/4"),
        ):
            with self.subTest(literal=literal), self.assertRaises(ResearchError):
                TargetResearchDraft.from_fields(
                    **fields(
                        allowed_hosts="",
                        allowed_networks=network,
                        source_urls=f"https://{literal}/",
                    )
                )
        draft = TargetResearchDraft.from_fields(
            **fields(
                allowed_hosts="",
                source_urls="https://93.184.216.34/\nhttps://[2606:4700:4700:0:0:0:0:1001]/",
            )
        )
        self.assertEqual(
            draft.steps[1].authorized_source_url, "https://[2606:4700:4700::1001]/"
        )

    def test_url_syntax_is_https_443_and_cannot_hide_authority(self) -> None:
        for url in (
            "http://example.test",
            "https://example.test:444/",
            "https://example.test:/",
            "https://user@example.test/",
            "https://example.test\\@other.test/",
            "https://example.test/with space",
            "https://éxample.test/",
            "https://example.test/#ignored",
            "https://[::1",
            "https://",
            "example.test",
            "https://example.test\x00/",
            "https://example.test\r/",
            "https://example.test/ # comment",
        ):
            with self.subTest(url=url), self.assertRaises(ResearchError):
                TargetResearchDraft.from_fields(**fields(source_urls=url))

    def test_missing_program_allowlist_or_sources_are_rejected(self) -> None:
        for changes in (
            {"program_id": " "},
            {"program_id": "p" * 201},
            {"program_id": "p\nq"},
            {"allowed_hosts": "", "allowed_networks": ""},
            {"source_urls": " \n\n"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ResearchError):
                TargetResearchDraft.from_fields(**fields(**changes))

    def test_all_form_fields_are_typed_and_bounded_before_parsing(self) -> None:
        for key in fields():
            for value in (None, [], 42, " " * (MAX_TARGET_FORM_FIELD_CHARACTERS + 1)):
                with (
                    self.subTest(key=key, value_type=type(value)),
                    self.assertRaises(ResearchError),
                ):
                    TargetResearchDraft.from_fields(**{**fields(), key: value})

    def test_aggregate_rule_limit_and_source_count_limits_are_enforced(self) -> None:
        draft = TargetResearchDraft.from_fields(
            **fields(
                allowed_hosts="\n".join(["example.test"] * 100),
                excluded_hosts="",
                allowed_networks="",
                excluded_networks="",
                source_urls="https://example.test/",
            )
        )
        self.assertEqual(len(draft.binding.scope.allowed_hosts), 100)
        for changes in (
            {"allowed_hosts": "\n".join(["example.test"] * 101)},
            {"excluded_hosts": "\n".join(["blocked.example.test"] * 96)},
            {"source_urls": "\n".join(["https://example.test/"] * 21)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ResearchError):
                TargetResearchDraft.from_fields(**fields(**changes))
        draft = TargetResearchDraft.from_fields(
            **fields(source_urls="\n".join(["https://example.test/"] * 20))
        )
        self.assertEqual(len(draft.steps), 20)

    def test_each_url_has_its_own_2048_character_bound(self) -> None:
        prefix = "https://example.test/"
        url = prefix + "a" * (2048 - len(prefix))
        draft = TargetResearchDraft.from_fields(**fields(source_urls=url))
        self.assertEqual(len(draft.steps[0].authorized_source_url), 2048)
        self.assertTrue(
            ResearchPlanDraftService()
            .preview("Inspect", draft.steps, target_binding=draft.binding)
            .allowed
        )
        with self.assertRaises(ResearchError):
            TargetResearchDraft.from_fields(**fields(source_urls=url + "a"))

    def test_direct_constructor_requires_valid_immutable_canonical_steps(self) -> None:
        draft = TargetResearchDraft.from_fields(**fields())
        for steps in (
            [],
            (),
            ("not a step",),
            (ResearchPlanStepDraftInput("Scan", capability="scan"),),
        ):
            with self.subTest(steps=steps), self.assertRaises(ResearchError):
                TargetResearchDraft(draft.binding, steps)  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            replace(
                draft,
                steps=(
                    replace(
                        draft.steps[0], authorized_source_url="https://other.test/"
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
