"""Who or what attested one recorded asset observation.

Exactly one answer is currently true, so exactly one value exists. Nothing in
this codebase today ingests a tool result or a passive-discovery feed into an
asset observation — the two existing Kali operation kinds
(`DNS_RECORD_LOOKUP`/`HTTPS_HEADER_LOOKUP`) produce only raw, unparsed text,
not a structured asset fact. An enum member is a capability someone can
select, and a value that exists for symmetry eventually gets used; extending
this vocabulary is explicitly recon-result-ingestion's job, a later
milestone, not this one.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchAssetProvenanceKind(StrEnum):
    """Name the attested source of one asset observation."""

    OPERATOR_AUTHORED = "operator_authored"
