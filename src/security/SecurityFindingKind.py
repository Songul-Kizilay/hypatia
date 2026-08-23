"""What the security agent checks, and how seriously to take each answer.

The agent audits Hypatia, not the world. Every kind here names a property of
this system's own persisted state, checkable without touching a network or
naming anyone else's infrastructure.

That scope is deliberate. An agent that probed external systems would need
authorisation this software has no way to establish, and the architecture
deliberately has nowhere to record a target. What it can do honestly is keep
checking that the boundaries the rest of the system relies on actually hold in
the data, rather than only in the tests that were written when the code was.

The checks are chosen to cover what the domain types do *not* already guarantee.
`ResearchRun` enforces referential integrity itself — evidence must cite an
accepted source, claims must cite recorded evidence — so auditing those again
would be theatre. What no type checks is the shape of a persisted source URL, or
whether two accepted sources are quietly the same page, and those are exactly
the gaps a hand-edited file or a bad migration would open. The two taint checks
are the exception: `ResearchSourceRecord` does validate them at construction, and
they are kept as defence in depth for state that reached the store another way.

Severity is a bounded label rather than a number. A score would get summed,
averaged, and reported as a security posture, which is precisely the false
precision this project avoids everywhere else.
"""

from __future__ import annotations

from enum import StrEnum


class SecurityFindingSeverity(StrEnum):
    """Name how seriously one finding should be taken."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        """Return the report order, higher meaning more serious."""
        return {"info": 0, "low": 1, "medium": 2, "high": 3}[self.value]

    @property
    def needs_action(self) -> bool:
        """Return whether someone should look at this before moving on."""
        return self in (
            SecurityFindingSeverity.MEDIUM,
            SecurityFindingSeverity.HIGH,
        )


class SecurityFindingKind(StrEnum):
    """Name one bounded property of Hypatia's own state that was checked."""

    NON_HTTPS_SOURCE = "non_https_source"
    NON_PUBLIC_SOURCE = "non_public_source"
    CREDENTIALS_IN_SOURCE_URL = "credentials_in_source_url"
    DUPLICATE_SOURCE_URL = "duplicate_source_url"
    UNSUPPORTED_CONTENT_TYPE = "unsupported_content_type"
    IMPLAUSIBLE_PROVENANCE = "implausible_provenance"
    UNLABELLED_SOURCE = "unlabelled_source"
    SOURCE_CLAIMS_INSTRUCTION_AUTHORITY = "source_claims_instruction_authority"

    @property
    def severity(self) -> SecurityFindingSeverity:
        """Return the declared severity for this kind of finding."""
        return _SEVERITIES[self]

    @property
    def concerns_acquisition(self) -> bool:
        """Return whether this finding is about how a source was obtained."""
        return self in (
            SecurityFindingKind.NON_HTTPS_SOURCE,
            SecurityFindingKind.NON_PUBLIC_SOURCE,
            SecurityFindingKind.CREDENTIALS_IN_SOURCE_URL,
            SecurityFindingKind.UNSUPPORTED_CONTENT_TYPE,
        )

    @property
    def covered_by_a_type(self) -> bool:
        """Return whether a domain type already refuses this at construction.

        Where it does, the check here is defence in depth against state that
        reached the store some other way, not the primary guarantee.
        """
        return self in (
            SecurityFindingKind.UNLABELLED_SOURCE,
            SecurityFindingKind.SOURCE_CLAIMS_INSTRUCTION_AUTHORITY,
        )


_SEVERITIES: dict[SecurityFindingKind, SecurityFindingSeverity] = {
    SecurityFindingKind.SOURCE_CLAIMS_INSTRUCTION_AUTHORITY: (
        SecurityFindingSeverity.HIGH
    ),
    SecurityFindingKind.UNLABELLED_SOURCE: SecurityFindingSeverity.HIGH,
    SecurityFindingKind.NON_PUBLIC_SOURCE: SecurityFindingSeverity.HIGH,
    SecurityFindingKind.CREDENTIALS_IN_SOURCE_URL: SecurityFindingSeverity.HIGH,
    SecurityFindingKind.NON_HTTPS_SOURCE: SecurityFindingSeverity.MEDIUM,
    SecurityFindingKind.DUPLICATE_SOURCE_URL: SecurityFindingSeverity.MEDIUM,
    SecurityFindingKind.UNSUPPORTED_CONTENT_TYPE: SecurityFindingSeverity.LOW,
    SecurityFindingKind.IMPLAUSIBLE_PROVENANCE: SecurityFindingSeverity.LOW,
}


def severity_for(kind: SecurityFindingKind) -> SecurityFindingSeverity:
    """Return the declared severity, refusing an unclassified kind."""
    if kind not in _SEVERITIES:
        raise ValueError(f"Security finding kind {kind} declares no severity.")
    return _SEVERITIES[kind]
