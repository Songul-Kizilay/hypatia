"""What kind of network entity one asset observation identifies.

Only the two kinds this codebase can honestly populate today. Recon-result
ingestion producing structured resolved-address or header data would be the
first legitimate reason to extend this vocabulary — not adding `URL`,
`SERVICE`, or `ENDPOINT` members ahead of that, since nothing produces that
structured data yet and a URL asset kind risks conflating with the existing,
conceptually distinct `ResearchSourceRecord.url` citation field.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchAssetKind(StrEnum):
    """Name the kind of value one canonical asset identity holds."""

    HOSTNAME = "hostname"
    IP_ADDRESS = "ip_address"
