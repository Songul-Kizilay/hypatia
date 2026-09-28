"""What kind of entity one validation recipe is attached to.

A validation recipe names its subject by (`subject_kind`, `subject_id`)
rather than embedding a hypothesis or finding reference field for each,
mirroring how `ResearchSecurityFindingEvidenceLinkRecord.evidence_kind`
names its evidence's kind alongside a single `evidence_id` rather than
carrying one optional ID field per possible evidence source. Only these two
kinds have an honest producer today: item 9 (Validation recipes) sits
directly on top of items 6/7 (Security Hypothesis, Finding lifecycle), the
only two record kinds a Bug Bounty operator currently reasons about.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSecurityValidationRecipeSubjectKind(StrEnum):
    """Name whether a validation recipe's subject is a hypothesis or a finding."""

    HYPOTHESIS = "hypothesis"
    FINDING = "finding"
