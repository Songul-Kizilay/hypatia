"""Who or what attested one recorded asset observation or relation.

Two answers are currently true. `OPERATOR_AUTHORED` is a human's direct
attestation. `KALI_OPERATION_RESULT` names the one real automated producer
that exists today: a completed, authorization-gated
`ResearchKaliOperationRun` whose `DNS_RECORD_LOOKUP` result has been parsed by
`research.ResearchDnsLookupResultParser` into structured hostname/address
facts. Every record stamped `KALI_OPERATION_RESULT` must carry the exact
`operation_digest` of the run that produced it — provenance is never inferred
from text, order or timing, only from that explicit binding. No other
producer exists yet; extending this vocabulary further remains a later
milestone's job.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchAssetProvenanceKind(StrEnum):
    """Name the attested source of one asset observation or relation."""

    OPERATOR_AUTHORED = "operator_authored"
    KALI_OPERATION_RESULT = "kali_operation_result"
