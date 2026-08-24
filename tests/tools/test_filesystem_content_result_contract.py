"""Authorization and isolation for the still-unregistered content channel."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from tools.FilesystemContentPayload import FilesystemContentPayload
from tools.ToolCapability import ToolCapability
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolDisposition import ToolDisposition
from tools.ToolEffect import ToolEffect
from tools.ToolExecutionService import ToolExecutionService
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRegistry import ToolRegistry
from tools.ToolResult import ToolResult
from tools.ToolRuntime import ToolRuntime

ROOT_DIR = Path(__file__).resolve().parents[2]
CONTENT_EFFECT = frozenset({ToolEffect.READS_FILESYSTEM_CONTENT})
METADATA_EFFECT = frozenset({ToolEffect.READS_FILESYSTEM_METADATA})
SENTINEL_CONTENT = "PRIVATE-CONTENT-MUST-NOT-ENTER-TELEMETRY"
SENTINEL_RESOURCE = "private/sentinel-file.txt"


def payload(text: str = SENTINEL_CONTENT) -> FilesystemContentPayload:
    byte_count = len(text.encode("utf-8"))
    moment = datetime(2026, 8, 24, 20, 0, tzinfo=UTC)
    return FilesystemContentPayload(
        root_id="workspace",
        resource=SENTINEL_RESOURCE,
        offset=0,
        bytes_requested=byte_count,
        bytes_returned=byte_count,
        truncated=False,
        file_size_bytes=byte_count,
        modified_utc=moment,
        bom_stripped=False,
        read_at_utc=moment,
        text=text,
    )


def content_result() -> ToolResult:
    return ToolResult(
        capability=ToolCapability.FILESYSTEM_READ,
        performed=True,
        detail="Returned one bounded local file range.",
        content=payload(),
    )


class ReturningContentTool:
    def __init__(
        self,
        effects: frozenset[ToolEffect] = CONTENT_EFFECT,
        *,
        smuggle_invalid_content: bool = False,
    ) -> None:
        self._descriptor = ToolDescriptor(
            capability=ToolCapability.FILESYSTEM_READ,
            effects=effects,
            summary="Returns an already-built test payload.",
        )
        self.calls: list[ToolInvocation] = []
        self._smuggle_invalid_content = smuggle_invalid_content

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        self.calls.append(invocation)
        result = content_result()
        if self._smuggle_invalid_content:
            object.__setattr__(result, "content", SENTINEL_CONTENT)
        return result


class ContentDeclarationTests(unittest.TestCase):
    def test_content_has_a_separate_capability_and_effect(self) -> None:
        self.assertEqual(ToolCapability.FILESYSTEM_READ.value, "filesystem_read")
        self.assertEqual(
            ToolEffect.READS_FILESYSTEM_CONTENT.value,
            "reads_filesystem_content",
        )
        self.assertIsNot(
            ToolEffect.READS_FILESYSTEM_CONTENT,
            ToolEffect.READS_FILESYSTEM_METADATA,
        )
        self.assertFalse(ToolEffect.READS_FILESYSTEM_CONTENT.irreversible)
        self.assertFalse(ToolEffect.READS_FILESYSTEM_CONTENT.observable_outside)

    def test_production_runtime_does_not_register_the_capability(self) -> None:
        runtime = ToolRuntime(None)

        self.assertNotIn(ToolCapability.FILESYSTEM_READ, runtime.capabilities)
        self.assertIsNone(runtime.registry.resolve(ToolCapability.FILESYSTEM_READ))
        outcome = runtime.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.FILESYSTEM_READ,
                authorized_effects=CONTENT_EFFECT,
            )
        )
        self.assertIs(outcome.failure_kind, ToolFailureKind.UNKNOWN_CAPABILITY)
        self.assertFalse(outcome.result.performed)


class ToolResultContentTests(unittest.TestCase):
    def test_successful_filesystem_result_carries_content_separately(self) -> None:
        result = content_result()

        self.assertIsInstance(result.content, FilesystemContentPayload)
        self.assertEqual(result.values, ())
        self.assertEqual(result.lines(), ())
        self.assertNotIn(SENTINEL_CONTENT, repr(result))
        self.assertNotIn(SENTINEL_RESOURCE, repr(result))

    def test_non_content_capabilities_cannot_carry_content(self) -> None:
        with self.assertRaisesRegex(ResearchError, "Only filesystem read"):
            ToolResult(
                capability=ToolCapability.CLOCK_READ,
                performed=True,
                detail="Invalid.",
                content=payload(),
            )

    def test_unsuccessful_results_cannot_carry_content(self) -> None:
        for performed, disposition in (
            (False, ToolDisposition.NOT_REACHED),
            (True, ToolDisposition.DECLINED),
            (True, ToolDisposition.FAILED),
        ):
            with self.subTest(disposition=disposition):
                with self.assertRaisesRegex(ResearchError, "unsuccessful"):
                    ToolResult(
                        capability=ToolCapability.FILESYSTEM_READ,
                        performed=performed,
                        detail="Did not return content.",
                        succeeded=False,
                        disposition=disposition,
                        content=payload(),
                    )

    def test_content_must_be_the_bounded_type_and_not_a_structured_value(self) -> None:
        with self.assertRaisesRegex(ResearchError, "bounded payload"):
            ToolResult(
                capability=ToolCapability.FILESYSTEM_READ,
                performed=True,
                detail="Invalid.",
                content=cast(Any, SENTINEL_CONTENT),
            )
        with self.assertRaisesRegex(ResearchError, "duplicate"):
            ToolResult(
                capability=ToolCapability.FILESYSTEM_READ,
                performed=True,
                detail="Invalid.",
                values=(("content", "not allowed"),),
                content=payload(),
            )

    def test_refusal_decline_and_failure_constructors_return_no_content(self) -> None:
        results = (
            ToolResult.refused(ToolCapability.FILESYSTEM_READ, "Not reached."),
            ToolResult.declined(ToolCapability.FILESYSTEM_READ, "Declined."),
            ToolResult.failed(ToolCapability.FILESYSTEM_READ, "Failed."),
        )

        self.assertTrue(all(result.content is None for result in results))

    def test_existing_structured_results_remain_unchanged(self) -> None:
        result = ToolResult(
            capability=ToolCapability.CLOCK_READ,
            performed=True,
            detail="Read the clock.",
            values=(("utc", "2026-08-24T20:00:00Z"),),
        )

        self.assertIsNone(result.content)
        self.assertEqual(result.lines(), ("utc: 2026-08-24T20:00:00Z",))


class ContentExecutionBoundaryTests(unittest.TestCase):
    def service(
        self,
        tool: ReturningContentTool,
        *,
        event_bus: EventBus | None = None,
    ) -> ToolExecutionService:
        registry = ToolRegistry()
        registry.register(tool)
        return ToolExecutionService(
            registry,
            event_bus=event_bus,
            id_factory=lambda: "content-request-1",
        )

    @staticmethod
    def invocation(
        authorized: frozenset[ToolEffect],
    ) -> ToolInvocation:
        return ToolInvocation(
            capability=ToolCapability.FILESYSTEM_READ,
            authorized_effects=authorized,
        )

    def test_explicit_content_effect_allows_the_bounded_result(self) -> None:
        tool = ReturningContentTool()

        outcome = self.service(tool).execute_detailed(self.invocation(CONTENT_EFFECT))

        self.assertTrue(outcome.result.succeeded)
        self.assertIsNotNone(outcome.result.content)
        self.assertEqual(len(tool.calls), 1)

    def test_metadata_grant_does_not_reach_a_content_declaring_tool(self) -> None:
        tool = ReturningContentTool()

        outcome = self.service(tool).execute_detailed(self.invocation(METADATA_EFFECT))

        self.assertIs(outcome.failure_kind, ToolFailureKind.UNAUTHORIZED_EFFECT)
        self.assertEqual(tool.calls, [])
        self.assertIsNone(outcome.result.content)

    def test_central_boundary_rejects_content_from_a_descriptor_without_effect(
        self,
    ) -> None:
        tool = ReturningContentTool(METADATA_EFFECT)
        grant = frozenset(
            {
                ToolEffect.READS_FILESYSTEM_METADATA,
                ToolEffect.READS_FILESYSTEM_CONTENT,
            }
        )

        with self.assertRaisesRegex(ResearchError, "explicit content authority"):
            self.service(tool).execute_detailed(self.invocation(grant))

        self.assertEqual(len(tool.calls), 1)

    def test_central_boundary_revalidates_the_payload_type(self) -> None:
        tool = ReturningContentTool(smuggle_invalid_content=True)

        with self.assertRaisesRegex(ResearchError, "invalid content payload"):
            self.service(tool).execute_detailed(self.invocation(CONTENT_EFFECT))

        self.assertEqual(len(tool.calls), 1)

    def test_lifecycle_events_never_copy_content_or_its_resource(self) -> None:
        event_bus = EventBus()
        events: list[Event] = []
        event_bus.subscribe("*", events.append)
        tool = ReturningContentTool()

        outcome = self.service(tool, event_bus=event_bus).execute_detailed(
            self.invocation(CONTENT_EFFECT)
        )
        rendered = str([event.payload for event in events])

        self.assertTrue(outcome.result.succeeded)
        self.assertNotIn(SENTINEL_CONTENT, rendered)
        self.assertNotIn(SENTINEL_RESOURCE, rendered)
        for event in events:
            self.assertNotIn("content", event.payload)
            self.assertNotIn("content_bytes", event.payload)


class ContentChannelIsolationTests(unittest.TestCase):
    def test_only_result_boundary_modules_import_the_payload(self) -> None:
        offenders = []
        for path in (ROOT_DIR / "src").rglob("*.py"):
            if path.name == "FilesystemContentPayload.py":
                continue
            if "FilesystemContentPayload" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(ROOT_DIR).as_posix())

        self.assertEqual(
            sorted(offenders),
            [
                "src/tools/ToolExecutionService.py",
                "src/tools/ToolResult.py",
            ],
        )

    def test_result_channel_adds_no_filesystem_read_or_runtime_registration(
        self,
    ) -> None:
        source = "\n".join(
            (ROOT_DIR / relative).read_text(encoding="utf-8")
            for relative in (
                "src/tools/ToolCapability.py",
                "src/tools/ToolEffect.py",
                "src/tools/ToolResult.py",
                "src/tools/ToolExecutionService.py",
            )
        )
        runtime_source = (ROOT_DIR / "src" / "tools" / "ToolRuntime.py").read_text(
            encoding="utf-8"
        )

        for forbidden in (
            "open(",
            "os.read",
            "ReadFile",
            "NtReadFile",
            "subprocess",
            "LLMProvider",
            "MemoryManager",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertNotIn("FilesystemContentPayload", runtime_source)
        self.assertNotIn("FILESYSTEM_READ", runtime_source)


if __name__ == "__main__":
    unittest.main()
