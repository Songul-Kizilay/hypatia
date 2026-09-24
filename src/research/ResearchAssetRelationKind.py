"""How one recorded asset relates to another — a citation, never an inference.

Exactly one directional relationship exists today: a hostname resolving to an
address, as the operator recorded it. This carries no scope semantics of its
own — recording a `RESOLVES_TO` relation between two assets never widens,
implies, or substitutes for a scope decision about either one. Other
relationship kinds (subdomain enumeration, service exposure, hosting,
redirect chains) each need their own asset-kind prerequisite this milestone
does not build, so they are deliberately absent rather than added for
symmetry.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchAssetRelationKind(StrEnum):
    """Name the kind of directional relationship between two assets."""

    RESOLVES_TO = "resolves_to"
