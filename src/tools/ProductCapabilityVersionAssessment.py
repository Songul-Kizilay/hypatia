"""Compare one authoritative version rule against one untrusted observation.

VERSION COMPATIBILITY != EXECUTION AUTHORITY. This module answers exactly
one question -- "does this observed text match this capability's existing
expected-version rule?" -- and nothing downstream may read the answer as
anything else. A `MATCH` is not permission to run anything; a `DRIFT` is
not authority to repair anything; an assessment never authorizes,
creates, consumes, or widens any authorization, dispatches a process,
touches the network, or mutates a `ProductCapabilityRecord` or
`ProductCapabilityCatalog`.

The comparison itself reuses the one version-check semantic that already
exists in this repository (`WslKaliRuntimeProbe.readiness`,
`SshVMwareKaliGuestReadinessProbe.readiness`): plain substring containment
of a trusted, code-owned expected prefix inside observed text. There is no
SemVer parser, no `>=`/`<=` comparison and no package-manager equivalence
anywhere in Hypatia today, so none is invented here -- preserving an
authoritative prefix rule's actual, narrower semantic is the honest
choice, not a limitation to work around.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError
from tools.ProductCapabilityRecord import ProductCapabilityRecord
from tools.ProductCapabilityVersionObservation import (
    ProductCapabilityVersionObservation,
)

MAX_REASON_LENGTH = 200


class ProductCapabilityVersionAssessmentStatus(StrEnum):
    """Name one closed, explicit outcome of comparing an observation to a rule."""

    MATCH = "match"
    DRIFT = "drift"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


_REASON_NOT_APPLICABLE = (
    "This capability has no authoritative expected-version rule to assess against."
)
_REASON_UNKNOWN_NO_OBSERVATION = "No observed version text was supplied."
_REASON_MATCH = "Observed version text contains the expected version prefix."
_REASON_DRIFT = "Observed version text does not contain the expected version prefix."


@dataclass(frozen=True, slots=True)
class ProductCapabilityVersionAssessment:
    """A deterministic, descriptive fact; never anything an execution path
    may treat as a decision.

    `reason` is always one of a small fixed set of code-owned sentences --
    never text built from the untrusted observation -- so this record can
    be logged or displayed without ever repeating adversarial content back
    as though it were an authoritative explanation.
    """

    capability_identity: str
    expected_version_reference: str | None
    observed_version_text: str
    status: ProductCapabilityVersionAssessmentStatus
    reason: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.capability_identity, str)
            or not self.capability_identity
        ):
            raise ResearchError("A capability version assessment identity is invalid.")
        if self.expected_version_reference is not None and (
            not isinstance(self.expected_version_reference, str)
            or not self.expected_version_reference
        ):
            raise ResearchError(
                "A capability version assessment expected-version reference is invalid."
            )
        if not isinstance(self.observed_version_text, str):
            raise ResearchError(
                "A capability version assessment observed text must be text."
            )
        if not isinstance(self.status, ProductCapabilityVersionAssessmentStatus):
            raise ResearchError("A capability version assessment status is invalid.")
        if (
            not isinstance(self.reason, str)
            or not self.reason.strip()
            or len(self.reason) > MAX_REASON_LENGTH
        ):
            raise ResearchError("A capability version assessment reason is invalid.")
        if self.status is ProductCapabilityVersionAssessmentStatus.NOT_APPLICABLE and (
            self.expected_version_reference is not None
        ):
            raise ResearchError(
                "A not-applicable assessment cannot name an expected-version reference."
            )
        if (
            self.status
            in (
                ProductCapabilityVersionAssessmentStatus.MATCH,
                ProductCapabilityVersionAssessmentStatus.DRIFT,
                ProductCapabilityVersionAssessmentStatus.UNKNOWN,
            )
            and self.expected_version_reference is None
        ):
            raise ResearchError(
                "A match, drift or unknown assessment requires an "
                "expected-version reference -- only NOT_APPLICABLE may omit "
                "one, since only it means no rule exists to compare against."
            )


def assess_capability_version(
    record: ProductCapabilityRecord,
    observation: ProductCapabilityVersionObservation,
) -> ProductCapabilityVersionAssessment:
    """Compare one record's existing version rule to one untrusted observation.

    This is a pure function: no process, no network, no store, no side
    effect of any kind. The only inputs are an already-authoritative
    `ProductCapabilityRecord` and an already-bounded
    `ProductCapabilityVersionObservation`; the only output is a bounded,
    immutable fact. Calling it twice with the same inputs always returns
    an equal result, and calling it a second time never consumes, revokes,
    or otherwise changes anything either input holds.
    """
    if not isinstance(record, ProductCapabilityRecord):
        raise ResearchError(
            "A capability version assessment requires a bounded record."
        )
    if not isinstance(observation, ProductCapabilityVersionObservation):
        raise ResearchError(
            "A capability version assessment requires a bounded observation."
        )
    if record.identity != observation.capability_identity:
        raise ResearchError(
            "A capability version assessment requires the observation to name "
            "the exact record it is being assessed against."
        )

    if record.version is None:
        return ProductCapabilityVersionAssessment(
            capability_identity=record.identity,
            expected_version_reference=None,
            observed_version_text=observation.observed_version_text,
            status=ProductCapabilityVersionAssessmentStatus.NOT_APPLICABLE,
            reason=_REASON_NOT_APPLICABLE,
        )

    if not observation.observed_version_text.strip():
        return ProductCapabilityVersionAssessment(
            capability_identity=record.identity,
            expected_version_reference=record.version,
            observed_version_text=observation.observed_version_text,
            status=ProductCapabilityVersionAssessmentStatus.UNKNOWN,
            reason=_REASON_UNKNOWN_NO_OBSERVATION,
        )

    if record.version in observation.observed_version_text:
        return ProductCapabilityVersionAssessment(
            capability_identity=record.identity,
            expected_version_reference=record.version,
            observed_version_text=observation.observed_version_text,
            status=ProductCapabilityVersionAssessmentStatus.MATCH,
            reason=_REASON_MATCH,
        )

    return ProductCapabilityVersionAssessment(
        capability_identity=record.identity,
        expected_version_reference=record.version,
        observed_version_text=observation.observed_version_text,
        status=ProductCapabilityVersionAssessmentStatus.DRIFT,
        reason=_REASON_DRIFT,
    )
