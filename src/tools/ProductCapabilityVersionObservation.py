"""One untrusted fact about what version a described capability observed.

An observation is untrusted data, exactly like a Kali operation's process
output: it may one day come from a real tool invocation, but holding one
here starts nothing, runs nothing, and proves nothing by itself. Nothing in
this type can execute the observed text, interpolate it into a shell,
mutate a `ProductCapabilityRecord`, register a capability, or redefine an
expected-version rule -- there is no method on this type that does
anything but hold three bounded strings.

Empty observed text is a legitimate, representable fact (a process that
produced no identifiable version string, or a caller with nothing to
report yet) rather than a construction error: assessment maps it to an
explicit `UNKNOWN` status rather than forcing every caller to avoid ever
constructing an observation for that case.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchKaliOperationExecution import (
    MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
)

MAX_CAPABILITY_IDENTITY_LENGTH = 100
MAX_OBSERVED_VERSION_TEXT_LENGTH = MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS
MAX_PROVENANCE_REFERENCE_LENGTH = 300


@dataclass(frozen=True, slots=True)
class ProductCapabilityVersionObservation:
    """Hold one bounded, untrusted version observation; grant nothing.

    `provenance_reference` is prose naming where the text came from (for
    example "dig -v stdout, 2026-10-07"), mirroring
    `ProductCapabilityRecord.availability_reference`: text to read, never a
    callable, a path, or anything that could be invoked or dereferenced.
    """

    capability_identity: str
    observed_version_text: str
    provenance_reference: str | None = None

    def __post_init__(self) -> None:
        self._require_identity(self.capability_identity)
        self._require_bounded_text(
            self.observed_version_text,
            "observed version text",
            MAX_OBSERVED_VERSION_TEXT_LENGTH,
            allow_empty=True,
        )
        if self.provenance_reference is not None:
            self._require_bounded_text(
                self.provenance_reference,
                "provenance reference",
                MAX_PROVENANCE_REFERENCE_LENGTH,
                allow_empty=False,
            )

    @staticmethod
    def _require_identity(value: object) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(
                "A capability version observation identity cannot be empty."
            )
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ResearchError(
                "A capability version observation identity contains control data."
            )
        if len(value) > MAX_CAPABILITY_IDENTITY_LENGTH:
            raise ResearchError(
                "A capability version observation identity is too long."
            )

    @staticmethod
    def _require_bounded_text(
        value: object, label: str, maximum: int, *, allow_empty: bool
    ) -> None:
        if not isinstance(value, str):
            raise ResearchError(
                f"A capability version observation {label} must be text."
            )
        if not allow_empty and not value.strip():
            raise ResearchError(
                f"A capability version observation {label} cannot be empty."
            )
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ResearchError(
                f"A capability version observation {label} contains control data."
            )
        if len(value) > maximum:
            raise ResearchError(
                f"A capability version observation {label} is too long."
            )
