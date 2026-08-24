"""A tool cannot run unless something authorised every effect it declares.

This is the whole point of the milestone. The tool used to prove it reads a
clock and could not hurt anyone, which is deliberate: the harmless tool travels
the exact path a dangerous one will, so the path is proven before anything
powerful exists to travel it.

The gate is central and fail-closed. A tool never decides whether it is
authorised, because a tool that policed itself would be the only thing standing
between a mistake and its consequences, and every future tool would have to get
that right again. Instead the service checks the descriptor's declared effects
against the invocation's grant and refuses before reaching the implementation.

The counting fake exists to prove the negative. Asserting that a refusal
returned the right result would not show the implementation was skipped; only a
tool that records being called can show it was not.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from tools.ToolCapability import ToolCapability
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolEffect import ToolEffect
from tools.ToolExecutionService import ToolExecutionService
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRegistry import ToolRegistry
from tools.ToolResult import ToolResult

READ_LOCAL = frozenset({ToolEffect.READS_LOCAL_STATE})
READ_AND_NETWORK = frozenset({ToolEffect.READS_LOCAL_STATE, ToolEffect.READS_NETWORK})


class CountingTool:
    """Record every invocation, so a refusal can be proven to skip it."""

    def __init__(
        self,
        capability: ToolCapability = ToolCapability.CLOCK_READ,
        effects: frozenset[ToolEffect] = READ_LOCAL,
        succeeds: bool = True,
    ) -> None:
        self._descriptor = ToolDescriptor(
            capability=capability,
            effects=effects,
            summary="A counting test tool.",
        )
        self.calls: list[ToolInvocation] = []
        self._succeeds = succeeds

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        self.calls.append(invocation)
        return ToolResult(
            capability=self._descriptor.capability,
            performed=True,
            detail="counted",
            succeeded=self._succeeds,
        )


class RaisingTool(CountingTool):
    """Fail the way a real tool fails: by raising, not by returning."""

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        self.calls.append(invocation)
        raise ResearchError("the tool broke while doing its one job")


class ToolRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry()

    def test_a_registered_tool_resolves_to_itself(self) -> None:
        tool = CountingTool()
        self.registry.register(tool)

        self.assertIs(self.registry.resolve(ToolCapability.CLOCK_READ), tool)

    def test_registration_is_explicit_and_derived_from_the_descriptor(self) -> None:
        """No decorators, no import-time magic, no separately passed capability."""
        tool = CountingTool(capability=ToolCapability.TEXT_STATISTICS)
        self.registry.register(tool)

        self.assertEqual(
            self.registry.registered_capabilities,
            (ToolCapability.TEXT_STATISTICS,),
        )

    def test_a_duplicate_registration_is_refused(self) -> None:
        self.registry.register(CountingTool())

        with self.assertRaises(ResearchError):
            self.registry.register(CountingTool())

    def test_the_none_capability_can_never_be_resolved(self) -> None:
        with self.assertRaises(ResearchError):
            self.registry.resolve(ToolCapability.NONE)

    def test_an_unknown_capability_resolves_to_nothing(self) -> None:
        self.registry.register(CountingTool())

        self.assertIsNone(self.registry.resolve(ToolCapability.KNOWLEDGE_DOCUMENT_LIST))

    def test_an_unknown_capability_never_falls_back_to_another_tool(self) -> None:
        """The failure mode that would make every other guarantee pointless."""
        tool = CountingTool()
        self.registry.register(tool)

        resolved = self.registry.resolve(ToolCapability.RESEARCH_STATE_SUMMARY)

        self.assertIsNone(resolved)
        self.assertIsNot(resolved, tool)

    def test_resolution_is_deterministic(self) -> None:
        tool = CountingTool()
        self.registry.register(tool)

        for _ in range(5):
            self.assertIs(self.registry.resolve(ToolCapability.CLOCK_READ), tool)

    def test_registered_capabilities_are_reported_in_declared_order(self) -> None:
        self.registry.register(CountingTool(ToolCapability.KNOWLEDGE_DOCUMENT_LIST))
        self.registry.register(CountingTool(ToolCapability.CLOCK_READ))

        self.assertEqual(
            self.registry.registered_capabilities,
            (ToolCapability.CLOCK_READ, ToolCapability.KNOWLEDGE_DOCUMENT_LIST),
        )

    def test_the_registry_refuses_something_that_is_not_a_tool(self) -> None:
        with self.assertRaises(ResearchError):
            self.registry.register("clock")  # type: ignore[arg-type]

    def test_the_registry_performs_no_operation_itself(self) -> None:
        """It resolves capabilities; it does not run them."""
        for forbidden in ("invoke", "execute", "run", "call"):
            with self.subTest(method=forbidden):
                self.assertFalse(hasattr(ToolRegistry, forbidden))


class AuthorizationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry()
        self.service = ToolExecutionService(self.registry)

    def register(self, **kwargs: object) -> CountingTool:
        tool = CountingTool(**kwargs)  # type: ignore[arg-type]
        self.registry.register(tool)
        return tool

    def invoke(
        self,
        authorized: frozenset[ToolEffect],
        capability: ToolCapability = ToolCapability.CLOCK_READ,
    ) -> ToolResult:
        return self.service.execute(
            ToolInvocation(capability=capability, authorized_effects=authorized)
        )

    def test_an_exactly_authorised_tool_runs(self) -> None:
        tool = self.register()

        result = self.invoke(READ_LOCAL)

        self.assertTrue(result.performed)
        self.assertTrue(result.succeeded)
        self.assertEqual(len(tool.calls), 1)

    def test_extra_authorised_effects_do_not_prevent_execution(self) -> None:
        """Least privilege is about the grant being sufficient, not minimal."""
        tool = self.register()

        result = self.invoke(READ_AND_NETWORK)

        self.assertTrue(result.performed)
        self.assertEqual(len(tool.calls), 1)

    def test_one_missing_effect_refuses_the_whole_invocation(self) -> None:
        tool = self.register(effects=READ_AND_NETWORK)

        result = self.invoke(READ_LOCAL)

        self.assertFalse(result.performed)
        self.assertFalse(result.succeeded)
        self.assertEqual(tool.calls, [])

    def test_an_empty_grant_refuses_execution(self) -> None:
        tool = self.register()

        result = self.invoke(frozenset())

        self.assertFalse(result.performed)
        self.assertEqual(tool.calls, [])

    def test_a_refused_invocation_never_reaches_the_implementation(self) -> None:
        """Proven by the tool counting calls, not by inspecting the result."""
        tool = self.register(effects=READ_AND_NETWORK)

        for _ in range(3):
            self.invoke(READ_LOCAL)

        self.assertEqual(tool.calls, [])

    def test_an_unknown_capability_is_refused_before_execution(self) -> None:
        tool = self.register()

        result = self.invoke(READ_LOCAL, ToolCapability.RESEARCH_STATE_SUMMARY)

        self.assertFalse(result.performed)
        self.assertEqual(tool.calls, [])

    def test_the_none_capability_cannot_even_be_expressed(self) -> None:
        """The invocation type refuses it, so it never reaches the service."""
        with self.assertRaises(ResearchError):
            ToolInvocation(
                capability=ToolCapability.NONE,
                authorized_effects=READ_LOCAL,
            )

    def test_a_refusal_can_never_be_reported_as_success(self) -> None:
        self.register(effects=READ_AND_NETWORK)

        result = self.invoke(READ_LOCAL)

        self.assertFalse(result.succeeded)
        with self.assertRaises(ResearchError):
            ToolResult(
                capability=ToolCapability.CLOCK_READ,
                performed=False,
                detail="x",
                succeeded=True,
            )

    def test_a_refusal_names_a_bounded_failure_kind(self) -> None:
        self.register(effects=READ_AND_NETWORK)

        outcome = self.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.CLOCK_READ,
                authorized_effects=READ_LOCAL,
            )
        )

        self.assertIs(outcome.failure_kind, ToolFailureKind.UNAUTHORIZED_EFFECT)
        self.assertFalse(outcome.authorized)

    def test_an_unknown_capability_names_its_own_failure_kind(self) -> None:
        outcome = self.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.CLOCK_READ,
                authorized_effects=READ_LOCAL,
            )
        )

        self.assertIs(outcome.failure_kind, ToolFailureKind.UNKNOWN_CAPABILITY)
        self.assertFalse(outcome.authorized)

    def test_no_detail_string_carries_raw_exception_text(self) -> None:
        tool = RaisingTool()
        self.registry.register(tool)

        outcome = self.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.CLOCK_READ,
                authorized_effects=READ_LOCAL,
            )
        )

        self.assertIs(outcome.failure_kind, ToolFailureKind.TOOL_FAILED)
        self.assertNotIn("broke while doing", outcome.result.detail)
        self.assertEqual(len(tool.calls), 1)

    def test_a_tool_that_runs_and_fails_still_performed(self) -> None:
        """performed and succeeded stay separate, as the result type requires."""
        tool = self.register(succeeds=False)

        result = self.invoke(READ_LOCAL)

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertEqual(len(tool.calls), 1)

    def test_a_cancelled_invocation_never_reaches_the_implementation(self) -> None:
        tool = self.register()
        signal = CancellationSignal()
        signal.cancel()

        outcome = self.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.CLOCK_READ,
                authorized_effects=READ_LOCAL,
            ),
            cancellation_token=signal,
        )

        self.assertIs(outcome.failure_kind, ToolFailureKind.CANCELLED)
        self.assertFalse(outcome.result.performed)
        self.assertEqual(tool.calls, [])

    def test_authorisation_is_per_invocation_and_never_ambient(self) -> None:
        """A grant on one call does not carry into the next."""
        tool = self.register(effects=READ_AND_NETWORK)
        self.invoke(READ_AND_NETWORK)
        self.assertEqual(len(tool.calls), 1)

        self.invoke(READ_LOCAL)

        self.assertEqual(len(tool.calls), 1)

    def test_the_service_offers_no_bypass(self) -> None:
        for forbidden in ("execute_unchecked", "force", "invoke_directly", "trusted"):
            with self.subTest(method=forbidden):
                self.assertFalse(hasattr(ToolExecutionService, forbidden))


if __name__ == "__main__":
    unittest.main()
