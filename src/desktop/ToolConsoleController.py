"""The one desktop module that may reach the Tool Layer.

Everything tool-shaped stops here. The window passes plain strings in and gets
plain data back, so the Tk code cannot name an effect, build an invocation, or
reach a registry — not because it is trusted not to, but because it does not
import anything that would let it. That is what keeps the isolation guard's
permitted list at two modules instead of a package.

Authorization is exact and per invocation. The grant is built from the resolved
tool's own declared effects, so it is never a superset, never inherited from a
previous run, and never assembled from anything the operator typed. There is no
remembered approval, no session grant, and no way to ask for one: `run` takes an
`authorized` flag that a caller must pass as True, and it is not stored
anywhere afterwards.

Nothing here consults a model. The console works with the LLM switched off,
which is deliberate — a control plane that needed a model to explain what it was
about to do would be a control plane whose explanations could be wrong.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from desktop.FilesystemContentPreview import FilesystemContentPreview
from desktop.ToolArgumentKind import ToolArgumentKind
from desktop.ToolArgumentSpec import ToolArgumentSpec
from desktop.ToolConsoleEntry import ToolConsoleEntry
from desktop.ToolRunStatus import ToolRunStatus
from desktop.ToolRunView import ToolRunView
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from tools.ToolCapability import ToolCapability
from tools.ToolExecutionOutcome import ToolExecutionOutcome
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRuntime import ToolRuntime

NOT_AUTHORIZED_DETAIL = (
    "Nothing was requested. Authorize the listed effects to run this."
)
UNKNOWN_CAPABILITY_DETAIL = "That capability is not registered."
UNKNOWN_ARGUMENT_DETAIL = "That argument is not accepted by this capability."
MISSING_ARGUMENT_DETAIL = "A required argument was not supplied."
MALFORMED_ARGUMENT_DETAIL = "An argument was not the shape this capability accepts."

#: What a form needs on top of each tool's own accepted-argument list. The tool
#: remains authoritative about which names exist; a test asserts these match it
#: exactly, so the two cannot drift apart silently.
_ARGUMENTS: dict[ToolCapability, tuple[ToolArgumentSpec, ...]] = {
    ToolCapability.CLOCK_READ: (),
    ToolCapability.TEXT_STATISTICS: (
        ToolArgumentSpec(
            name="text",
            label="Text",
            kind=ToolArgumentKind.TEXT,
            required=True,
            hint="Counted here. Not stored, not sent anywhere.",
        ),
    ),
    ToolCapability.FILESYSTEM_LIST: (
        ToolArgumentSpec(
            name="path",
            label="Folder",
            kind=ToolArgumentKind.RELATIVE_PATH,
            required=True,
            hint="Relative to the configured scope. Use . for the scope itself.",
        ),
        ToolArgumentSpec(
            name="offset",
            label="Start at entry",
            kind=ToolArgumentKind.WHOLE_NUMBER,
            hint="Leave blank for the first page.",
        ),
    ),
    ToolCapability.FILESYSTEM_METADATA: (
        ToolArgumentSpec(
            name="path",
            label="Entry",
            kind=ToolArgumentKind.RELATIVE_PATH,
            required=True,
            hint="One file or folder, relative to the configured scope.",
        ),
    ),
    ToolCapability.FILESYSTEM_READ: (
        ToolArgumentSpec(
            name="path",
            label="Entry",
            kind=ToolArgumentKind.RELATIVE_PATH,
            required=True,
            hint="One local UTF-8 file, relative to the configured scope.",
        ),
        ToolArgumentSpec(
            name="offset",
            label="Byte offset",
            kind=ToolArgumentKind.WHOLE_NUMBER,
            required=True,
            hint="Start at this byte. Use 0 for the beginning.",
        ),
        ToolArgumentSpec(
            name="max_bytes",
            label="Maximum bytes",
            kind=ToolArgumentKind.WHOLE_NUMBER,
            required=True,
            hint="Read at most 65,536 bytes in this one request.",
        ),
    ),
}


class ToolConsoleController:
    """Present registered capabilities and run exactly one when told to."""

    def __init__(self, runtime: ToolRuntime, event_bus: EventBus | None = None) -> None:
        if not isinstance(runtime, ToolRuntime):
            raise ResearchError("A tool console requires a tool runtime.")
        self._runtime = runtime
        self._event_bus = event_bus
        self._events: list[Event] = []
        if event_bus is not None:
            event_bus.subscribe("*", self._record)

    def catalogue(self) -> tuple[ToolConsoleEntry, ...]:
        """Return only what the production registry actually holds.

        Registered capabilities, in the registry's own order. There is no second
        list to fall out of date, and a capability that is not registered does
        not appear — so it cannot be selected, and selecting is the only way in.
        """
        entries: list[ToolConsoleEntry] = []
        for capability in self._runtime.capabilities:
            tool = self._runtime.registry.resolve(capability)
            if tool is None:
                continue
            descriptor = tool.descriptor
            entries.append(
                ToolConsoleEntry(
                    capability=capability.value,
                    description=descriptor.summary,
                    effects=tuple(
                        effect.value for effect in sorted(descriptor.effects)
                    ),
                    read_only=descriptor.read_only,
                    reaches_outside=descriptor.reaches_outside,
                    arguments=_ARGUMENTS.get(capability, ()),
                    scope_label=self._scope_label(capability),
                )
            )
        return tuple(entries)

    def entry(self, capability: str) -> ToolConsoleEntry | None:
        """Return one catalogue entry by its exact capability value."""
        for candidate in self.catalogue():
            if candidate.capability == capability:
                return candidate
        return None

    def run(
        self,
        capability: str,
        arguments: tuple[tuple[str, str], ...] = (),
        *,
        authorized: bool = False,
    ) -> ToolRunView:
        """Run one capability, once, with exactly the effects it declares.

        `authorized` is the operator's action and has no default. It is not
        remembered between calls, not stored on the controller, and not derived
        from anything the caller typed — one press authorizes one run, and the
        next run needs another.
        """
        entry = self.entry(capability)
        if entry is None:
            return self._rejected(
                capability, ToolRunStatus.UNAVAILABLE, UNKNOWN_CAPABILITY_DETAIL
            )
        if not authorized:
            return self._rejected(
                capability, ToolRunStatus.UNAUTHORIZED, NOT_AUTHORIZED_DETAIL
            )
        problem = self._validate(entry, arguments)
        if problem is not None:
            return self._rejected(capability, ToolRunStatus.INVALID_ARGUMENTS, problem)
        resolved = self._capability(capability)
        if resolved is None:
            return self._rejected(
                capability, ToolRunStatus.UNAVAILABLE, UNKNOWN_CAPABILITY_DETAIL
            )
        tool = self._runtime.registry.resolve(resolved)
        if tool is None:
            return self._rejected(
                capability, ToolRunStatus.UNAVAILABLE, UNKNOWN_CAPABILITY_DETAIL
            )
        self._events.clear()
        try:
            invocation = ToolInvocation(
                capability=resolved,
                authorized_effects=frozenset(tool.descriptor.effects),
                arguments=self._supplied(entry, arguments),
            )
        except ResearchError:
            return self._rejected(
                capability,
                ToolRunStatus.INVALID_ARGUMENTS,
                MALFORMED_ARGUMENT_DETAIL,
            )
        return self._view(entry, self._runtime.service.execute_detailed(invocation))

    def validation_problem(
        self,
        capability: str,
        arguments: tuple[tuple[str, str], ...] = (),
    ) -> str | None:
        """Validate a plain form before confirmation without invoking a tool."""
        entry = self.entry(capability)
        if entry is None:
            return UNKNOWN_CAPABILITY_DETAIL
        return self._validate(entry, arguments)

    def _validate(
        self,
        entry: ToolConsoleEntry,
        arguments: tuple[tuple[str, str], ...],
    ) -> str | None:
        """Return why these arguments cannot become an invocation, or None."""
        supplied = dict(arguments)
        for name in supplied:
            if entry.argument(name) is None:
                return UNKNOWN_ARGUMENT_DETAIL
        for spec in entry.arguments:
            value = supplied.get(spec.name, "")
            if spec.missing(value):
                return MISSING_ARGUMENT_DETAIL
            if spec.malformed(value):
                return MALFORMED_ARGUMENT_DETAIL
        return None

    @staticmethod
    def _supplied(
        entry: ToolConsoleEntry,
        arguments: tuple[tuple[str, str], ...],
    ) -> tuple[tuple[str, str], ...]:
        """Drop blank optional values so a tool sees only what was filled in."""
        supplied = dict(arguments)
        return tuple(
            (spec.name, supplied[spec.name])
            for spec in entry.arguments
            if spec.name in supplied and (spec.required or supplied[spec.name].strip())
        )

    def _view(
        self,
        entry: ToolConsoleEntry,
        outcome: ToolExecutionOutcome,
    ) -> ToolRunView:
        """Project one execution outcome, taking every fact from the outcome."""
        content_preview = self._content_preview(outcome)
        return ToolRunView(
            capability=entry.capability,
            status=self._status(outcome),
            performed=outcome.result.performed,
            succeeded=outcome.result.succeeded,
            detail=outcome.result.detail,
            declared_effects=entry.effects,
            authorized_effects=entry.effects if outcome.authorized else (),
            values=outcome.result.values,
            events=tuple(
                event.name for event in self._events if event.name.startswith("tool.")
            ),
            request_id=outcome.request_id,
            content_preview=content_preview,
        )

    @staticmethod
    def _content_preview(
        outcome: ToolExecutionOutcome,
    ) -> FilesystemContentPreview | None:
        """Project content beside central identity, never into generic values."""
        payload = outcome.result.content
        if payload is None:
            return None
        return FilesystemContentPreview(
            request_id=outcome.request_id,
            root_id=payload.root_id,
            resource=payload.resource,
            offset=payload.offset,
            bytes_requested=payload.bytes_requested,
            bytes_returned=payload.bytes_returned,
            truncated=payload.truncated,
            file_size_bytes=payload.file_size_bytes,
            modified_utc=payload.modified_utc,
            bom_stripped=payload.bom_stripped,
            read_at_utc=payload.read_at_utc,
            source_kind=payload.source_kind,
            encoding=payload.encoding,
            taint_label=payload.taint_label,
            instruction_authority=payload.instruction_authority,
            disclosure_class=payload.disclosure_class,
            text=payload.text,
        )

    @staticmethod
    def _status(outcome: ToolExecutionOutcome) -> ToolRunStatus:
        """Map one bounded failure kind onto one bounded operator outcome.

        Every branch tests an enum identity. Nothing here reads `detail`, and
        nothing may start to: the moment a status is decided by what a sentence
        says, the sentence becomes the contract and a reworded message becomes a
        behaviour change.
        """
        if outcome.failure_kind is None:
            return ToolRunStatus.SUCCEEDED
        if outcome.failure_kind is ToolFailureKind.UNKNOWN_CAPABILITY:
            return ToolRunStatus.UNAVAILABLE
        if outcome.failure_kind is ToolFailureKind.UNAUTHORIZED_EFFECT:
            return ToolRunStatus.UNAUTHORIZED
        if outcome.failure_kind is ToolFailureKind.CANCELLED:
            return ToolRunStatus.CANCELLED
        if outcome.failure_kind is ToolFailureKind.EXECUTION_FAILED:
            return ToolRunStatus.EXECUTION_FAILED
        return ToolRunStatus.DECLINED

    def _rejected(
        self,
        capability: str,
        status: ToolRunStatus,
        detail: str,
    ) -> ToolRunView:
        """Report a run the console stopped before anything was requested."""
        entry = self.entry(capability)
        return ToolRunView(
            capability=capability,
            status=status,
            performed=False,
            succeeded=False,
            detail=detail,
            declared_effects=entry.effects if entry is not None else (),
        )

    def _capability(self, capability: str) -> ToolCapability | None:
        """Match a string against registered capabilities and nothing else.

        A lookup over what is registered, never a constructor over what the
        enum happens to contain. An unregistered name resolves to nothing rather
        than to a capability the runtime chose not to provide.
        """
        for candidate in self._runtime.capabilities:
            if candidate.value == capability:
                return candidate
        return None

    def _scope_label(self, capability: ToolCapability) -> str:
        """Return the scope identity for capabilities that have one.

        The identity, never the path. An operator needs to know which scope is
        in force; neither they nor anything downstream needs the absolute
        location to understand that, and telemetry must never see it.
        """
        if capability not in (
            ToolCapability.FILESYSTEM_LIST,
            ToolCapability.FILESYSTEM_METADATA,
            ToolCapability.FILESYSTEM_READ,
        ):
            return ""
        root_id = self._runtime.filesystem_root_id
        return f"Scope: {root_id}" if root_id else ""

    def _record(self, event: Event) -> None:
        """Collect lifecycle events for the audit view of the current run."""
        if event.name.startswith("tool."):
            self._events.append(event)
