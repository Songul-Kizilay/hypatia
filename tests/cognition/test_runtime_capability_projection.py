"""Runtime capability projection: descriptive truth derived only from wiring."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from cognition.RuntimeCapabilityProjection import (
    RuntimeCapability,
    RuntimeCapabilityContext,
    RuntimeCapabilityEvidence,
    RuntimeCapabilityState,
    project_runtime_capabilities,
)
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap

AVAILABLE = RuntimeCapabilityState.AVAILABLE
SIMULATED = RuntimeCapabilityState.SIMULATED
UNAVAILABLE = RuntimeCapabilityState.UNAVAILABLE
UNKNOWN = RuntimeCapabilityState.UNKNOWN

FULL_RESEARCH = frozenset(
    {
        Cap.LOCAL_KNOWLEDGE_SEARCH,
        Cap.SOURCE_DISCOVERY,
        Cap.SOURCE_FETCH,
        Cap.SOURCE_ACCEPT,
        Cap.SOURCE_REVALIDATION,
        Cap.EVIDENCE_RECORDING,
        Cap.CLAIM_CREATION,
        Cap.CLAIM_CONTRADICTION,
    }
)
NEVER_WIRED = (
    RuntimeCapability.CHAT_WEB_BROWSING,
    RuntimeCapability.PENETRATION_TESTING,
    RuntimeCapability.CONTINUOUS_MONITORING,
    RuntimeCapability.DEVICE_AND_MEDIA_CONTROL,
    RuntimeCapability.SYSTEM_ADMINISTRATION,
)


def wired(**overrides: object) -> RuntimeCapabilityEvidence:
    values: dict[str, object] = {
        "conversation_model": True,
        "sessions": True,
        "memory": True,
        "local_knowledge": True,
        "research_approvals": True,
        "research_operations": FULL_RESEARCH,
        "security_self_audit": True,
        "kali_operation_kinds": (),
    }
    values.update(overrides)
    return RuntimeCapabilityEvidence(**values)  # type: ignore[arg-type]


class RuntimeProjectionTests(unittest.TestCase):
    def test_wired_services_project_to_available_capabilities(self) -> None:
        context = project_runtime_capabilities(wired())

        for capability in (
            RuntimeCapability.CONVERSATION,
            RuntimeCapability.SESSIONS,
            RuntimeCapability.MEMORY,
            RuntimeCapability.LOCAL_KNOWLEDGE,
            RuntimeCapability.AUTHORIZED_RESEARCH,
            RuntimeCapability.SOURCE_DISCOVERY,
            RuntimeCapability.SOURCE_ACQUISITION,
            RuntimeCapability.EVIDENCE_TRACKING,
            RuntimeCapability.SOURCE_REVALIDATION,
            RuntimeCapability.SECURITY_SELF_AUDIT,
        ):
            self.assertIs(context.state_of(capability), AVAILABLE, capability)
        self.assertIs(
            context.state_of(RuntimeCapability.REVIEWED_KALI_LOOKUPS), UNAVAILABLE
        )

    def test_projection_is_deterministic_and_ordered(self) -> None:
        first = project_runtime_capabilities(wired())
        second = project_runtime_capabilities(wired())

        self.assertEqual(first, second)
        self.assertEqual(first.instruction(), second.instruction())
        self.assertEqual(
            [capability for capability, _ in first.states], list(RuntimeCapability)
        )

    def test_unwired_capabilities_are_not_available(self) -> None:
        without_fetcher = project_runtime_capabilities(
            wired(
                research_operations=FULL_RESEARCH
                - {Cap.SOURCE_FETCH, Cap.SOURCE_ACCEPT, Cap.SOURCE_REVALIDATION}
            )
        )
        self.assertIs(
            without_fetcher.state_of(RuntimeCapability.SOURCE_ACQUISITION), UNAVAILABLE
        )
        self.assertIs(
            without_fetcher.state_of(RuntimeCapability.SOURCE_REVALIDATION),
            UNAVAILABLE,
        )
        no_model = project_runtime_capabilities(wired(conversation_model=False))
        self.assertIs(no_model.state_of(RuntimeCapability.CONVERSATION), UNAVAILABLE)

    def test_research_operations_without_approval_are_not_research(self) -> None:
        context = project_runtime_capabilities(wired(research_approvals=False))

        for capability in (
            RuntimeCapability.AUTHORIZED_RESEARCH,
            RuntimeCapability.SOURCE_DISCOVERY,
            RuntimeCapability.SOURCE_ACQUISITION,
            RuntimeCapability.EVIDENCE_TRACKING,
            RuntimeCapability.SOURCE_REVALIDATION,
        ):
            self.assertIs(context.state_of(capability), UNAVAILABLE, capability)

    def test_local_search_alone_is_not_research(self) -> None:
        context = project_runtime_capabilities(
            wired(research_operations=frozenset({Cap.LOCAL_KNOWLEDGE_SEARCH}))
        )

        self.assertIs(
            context.state_of(RuntimeCapability.AUTHORIZED_RESEARCH), UNAVAILABLE
        )

    def test_security_ambitions_are_never_available(self) -> None:
        context = project_runtime_capabilities(
            wired(kali_operation_kinds=("dns_record_lookup", "https_header_lookup"))
        )

        for capability in NEVER_WIRED:
            self.assertIs(context.state_of(capability), UNAVAILABLE, capability)
        text = context.instruction()
        self.assertIn(
            "Kali lookups, each individually previewed and authorized, limited to: "
            "dns record lookup, https header lookup",
            text,
        )
        available = text.split("Available now:")[1].split(
            "Not implemented in Hypatia:"
        )[0]
        for forbidden in ("penetration", "scanning", "exploit", "monitoring"):
            self.assertNotIn(forbidden, available)

    def test_kali_simulation_alone_is_simulated_not_available(self) -> None:
        context = project_runtime_capabilities(
            wired(kali_operation_kinds=(), kali_simulation_available=True)
        )

        self.assertIs(
            context.state_of(RuntimeCapability.REVIEWED_KALI_LOOKUPS), SIMULATED
        )
        text = context.instruction()
        self.assertIn("Simulated only, no real action performed:", text)
        self.assertIn(
            "it performs no real DNS or HTTPS request",
            text,
        )
        available = text.split("Available now:")[1].split(
            "Simulated only, no real action performed:"
        )[0]
        self.assertNotIn("Kali", available)

    def test_a_real_runner_always_outranks_the_simulation_fact(self) -> None:
        """Both facts can be true at once; the real one must still win."""
        context = project_runtime_capabilities(
            wired(
                kali_operation_kinds=("dns_record_lookup",),
                kali_simulation_available=True,
            )
        )

        self.assertIs(
            context.state_of(RuntimeCapability.REVIEWED_KALI_LOOKUPS), AVAILABLE
        )
        self.assertNotIn("Simulated only", context.instruction())

    def test_neither_real_nor_simulated_kali_is_unavailable_not_simulated(
        self,
    ) -> None:
        context = project_runtime_capabilities(
            wired(kali_operation_kinds=(), kali_simulation_available=False)
        )

        self.assertIs(
            context.state_of(RuntimeCapability.REVIEWED_KALI_LOOKUPS), UNAVAILABLE
        )
        self.assertNotIn("Simulated only", context.instruction())

    def test_not_implemented_and_not_enabled_are_reported_separately(self) -> None:
        context = project_runtime_capabilities(wired(memory=False))

        text = context.instruction()
        self.assertIn("Not implemented in Hypatia:", text)
        self.assertIn("Not enabled in this configuration:", text)
        not_enabled = text.split("Not enabled in this configuration:")[1].split(
            "Not confirmed"
        )[0]
        self.assertIn("remembering facts", not_enabled)
        not_implemented = text.split("Not implemented in Hypatia:")[1].split(
            "Not enabled in this configuration:"
        )[0]
        self.assertIn("penetration", not_implemented)


class NoRoadmapInferenceTests(unittest.TestCase):
    def test_planned_module_folders_make_nothing_available(self) -> None:
        planned = [
            name
            for name in ("security", "vision", "voice", "robotics", "home")
            if (SRC_DIR / name).is_dir()
        ]
        self.assertTrue(planned, "the repository still has planned module folders")

        context = project_runtime_capabilities(RuntimeCapabilityEvidence())

        self.assertNotIn(AVAILABLE, [state for _, state in context.states])
        self.assertNotIn("Available now:", context.instruction())

    def test_projection_reads_no_files_docs_or_module_layout(self) -> None:
        source = (SRC_DIR / "cognition" / "RuntimeCapabilityProjection.py").read_text(
            encoding="utf-8"
        )
        imported = {
            node.module if isinstance(node, ast.ImportFrom) else alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in node.names
        }

        self.assertEqual(
            imported,
            {
                "__future__",
                "dataclasses",
                "enum",
                "research.ResearchPlanStepCapability",
            },
        )
        for token in ("open(", "Path(", "os.", "importlib", "listdir", "glob"):
            self.assertNotIn(token, source)


class ConservativeUnknownTests(unittest.TestCase):
    def test_non_boolean_evidence_stays_unknown(self) -> None:
        context = project_runtime_capabilities(
            wired(sessions=None, memory="yes", conversation_model=1)
        )

        for capability in (
            RuntimeCapability.SESSIONS,
            RuntimeCapability.MEMORY,
            RuntimeCapability.CONVERSATION,
        ):
            self.assertIs(context.state_of(capability), UNKNOWN, capability)
        self.assertIn("Not confirmed (do not claim):", context.instruction())

    def test_non_boolean_kali_simulation_fact_stays_unknown(self) -> None:
        context = project_runtime_capabilities(
            wired(kali_operation_kinds=(), kali_simulation_available="maybe")
        )

        self.assertIs(
            context.state_of(RuntimeCapability.REVIEWED_KALI_LOOKUPS), UNKNOWN
        )

    def test_malformed_evidence_falls_back_to_claiming_nothing(self) -> None:
        for evidence in (
            None,
            wired(research_operations={"source_fetch"}),
            wired(research_operations=frozenset({"source_fetch"})),
            wired(kali_operation_kinds=["dns_record_lookup"]),
        ):
            with self.subTest(evidence=evidence):
                context = project_runtime_capabilities(evidence)  # type: ignore[arg-type]
                self.assertEqual(context, RuntimeCapabilityContext.conservative())
                self.assertNotIn(AVAILABLE, [state for _, state in context.states])

    def test_an_unrecorded_capability_is_unknown_not_available(self) -> None:
        self.assertIs(
            RuntimeCapabilityContext(()).state_of(RuntimeCapability.CONVERSATION),
            UNKNOWN,
        )

    def test_version_is_carried_through_as_a_plain_string(self) -> None:
        context = project_runtime_capabilities(
            wired(hypatia_version="0.3.437 (Genesis)")
        )

        self.assertEqual(context.hypatia_version, "0.3.437 (Genesis)")

    def test_version_is_omitted_when_not_supplied(self) -> None:
        context = project_runtime_capabilities(wired())

        self.assertEqual(context.hypatia_version, "")

    def test_non_string_version_is_not_stated(self) -> None:
        context = project_runtime_capabilities(wired(hypatia_version=436))

        self.assertEqual(context.hypatia_version, "")


class InstructionContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = project_runtime_capabilities(wired()).instruction()

    def test_hypatia_is_distinguished_from_the_underlying_model(self) -> None:
        self.assertIn("Hypatia is an application.", self.text)
        self.assertIn("language component", self.text)
        self.assertIn("Do not describe yourself as a large language model", self.text)
        self.assertIn(
            "do not present generic model skills such as writing, coding or "
            "translation as Hypatia capabilities",
            self.text,
        )

    def test_small_models_are_told_not_to_invent_capabilities(self) -> None:
        self.assertIn(
            "Describe only the capabilities listed as available or simulated.",
            self.text,
        )
        self.assertIn("say Hypatia cannot do it; never invent a capability", self.text)

    def test_a_simulated_result_must_never_be_described_as_real(self) -> None:
        self.assertIn(
            "A capability listed as simulated performs no real action", self.text
        )
        self.assertIn("never describe a simulated result as a real one", self.text)

    def test_description_is_not_authority_and_chat_is_not_research(self) -> None:
        self.assertIn("it grants no permission and starts nothing", self.text)
        self.assertIn(
            "never say you researched, browsed, fetched, verified or revalidated "
            "anything in this chat",
            self.text,
        )
        self.assertIn(
            "only through a research plan the user explicitly approves", self.text
        )

    def test_revalidation_is_described_as_bounded_and_not_automatic(self) -> None:
        self.assertIn(
            "one explicitly approved re-fetch of a recorded source, using a normal "
            "source slot and budget; never automatic",
            self.text,
        )
        self.assertNotIn("fresh", self.text.casefold())

    def test_context_is_bounded_and_free_of_internals(self) -> None:
        self.assertLess(len(self.text.split()), 300)
        for internal in ("src", ".py", "Engine", "Service", "Manager", "_", "http"):
            self.assertNotIn(internal, self.text)


class VersionInstructionTests(unittest.TestCase):
    def test_version_is_stated_as_a_plain_fact_when_provided(self) -> None:
        text = project_runtime_capabilities(
            wired(hypatia_version="0.3.437 (Genesis)")
        ).instruction()

        self.assertIn("Hypatia version: 0.3.437 (Genesis).", text)

    def test_version_line_is_absent_when_not_provided(self) -> None:
        text = project_runtime_capabilities(wired()).instruction()

        self.assertNotIn("Hypatia version:", text)


if __name__ == "__main__":
    unittest.main()
