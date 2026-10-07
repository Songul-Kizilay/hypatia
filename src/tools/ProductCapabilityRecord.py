"""One descriptive fact sheet about a capability that already exists.

This module declares no authority and starts no process. It exists so
Hypatia can describe what it already does -- a local tool wired through
`ToolRegistry`, or a Kali operation wired through `KaliToolGateway` -- in one
uniform shape, without touching either's own execution path.

A record is a *description*, never a decision. Nothing here is checked
before a tool invocation or a Kali dispatch; those gates already exist
(`ToolExecutionService.execute_detailed`, `KaliToolGateway.run`) and remain
exactly as authoritative as before this module existed. A caller that wants
to know whether a capability is REGISTERED reads this. A caller that wants
to know whether a capability may be USED still goes through the real gate,
every time, as it always did.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError

MAX_IDENTITY_LENGTH = 100
MAX_DISPLAY_NAME_LENGTH = 150
MAX_VERSION_LENGTH = 50
MAX_AVAILABILITY_REFERENCE_LENGTH = 300
MAX_TIMEOUT_SECONDS = 3600.0


class ProductCapabilityCategory(StrEnum):
    """Name which existing family a described capability belongs to.

    Exactly two values exist because exactly two independent execution
    families exist in the repository today: the generic local `Tool` layer
    (`ToolRegistry`/`ToolExecutionService`) and the Kali operation authority
    chain (`KaliToolGateway`). Adding a third value here is a decision about
    a third family existing, not a decision this module may make alone.
    """

    LOCAL_TOOL = "local_tool"
    KALI_OPERATION = "kali_operation"


@dataclass(frozen=True, slots=True)
class ProductCapabilityRecord:
    """Describe one already-existing capability; grant nothing.

    Every field is either read directly from an existing authoritative
    source (a real `ToolDescriptor`'s effects, a real Kali runtime
    constant) or is a plainly-absent `None`/`False` when no authoritative
    fact exists yet -- never a guessed or rounded value. `availability_reference`
    names, in prose, which already-existing readiness/composition check
    decides whether this capability can currently be reached; it is text to
    read, not a callable to invoke, so holding a record can never become a
    way to check or grant readiness.
    """

    identity: str
    display_name: str
    category: ProductCapabilityCategory
    requires_network: bool
    requires_credentials: bool
    target_scope_relevant: bool
    destructive: bool
    version: str | None = None
    timeout_seconds: float | None = None
    retry_count: int | None = None
    availability_reference: str | None = None

    def __post_init__(self) -> None:
        self._require_text(self.identity, "identity", MAX_IDENTITY_LENGTH)
        self._require_text(self.display_name, "display name", MAX_DISPLAY_NAME_LENGTH)
        if not isinstance(self.category, ProductCapabilityCategory):
            raise ResearchError("A capability record category must be bounded.")
        for value, label in (
            (self.requires_network, "requires-network flag"),
            (self.requires_credentials, "requires-credentials flag"),
            (self.target_scope_relevant, "target-scope-relevant flag"),
            (self.destructive, "destructive flag"),
        ):
            if not isinstance(value, bool):
                raise ResearchError(f"A capability record {label} must be boolean.")
        if self.version is not None:
            self._require_text(self.version, "version", MAX_VERSION_LENGTH)
        if self.timeout_seconds is not None:
            if (
                isinstance(self.timeout_seconds, bool)
                or not isinstance(self.timeout_seconds, int | float)
                or not 0 < self.timeout_seconds <= MAX_TIMEOUT_SECONDS
            ):
                raise ResearchError("A capability record timeout is invalid.")
        if self.retry_count is not None:
            if isinstance(self.retry_count, bool) or not isinstance(
                self.retry_count, int
            ):
                raise ResearchError(
                    "A capability record retry count must be a whole number."
                )
            if self.retry_count < 0:
                raise ResearchError(
                    "A capability record retry count cannot be negative."
                )
        if self.availability_reference is not None:
            self._require_text(
                self.availability_reference,
                "availability reference",
                MAX_AVAILABILITY_REFERENCE_LENGTH,
            )

    @staticmethod
    def _require_text(value: object, label: str, maximum: int) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"A capability record {label} cannot be empty.")
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ResearchError(f"A capability record {label} contains control data.")
        if len(value) > maximum:
            raise ResearchError(f"A capability record {label} is too long.")
