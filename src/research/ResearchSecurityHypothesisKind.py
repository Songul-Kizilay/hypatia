"""Broad security-mechanism categories a hypothesis's subject falls under.

Not a per-CVE/per-vulnerability-name enum. A specific vulnerability name (e.g.
"reflected XSS in the search parameter") is future knowledge-layer content,
never a value this vocabulary needs to name. These categories describe which
security *mechanism* a hypothesis is about, broadly enough to survive the
mechanism turning out to be sound, partially sound, or broken.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSecurityHypothesisKind(StrEnum):
    """Name one broad security-mechanism category a hypothesis concerns."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    INPUT_HANDLING = "input_handling"
    SERVER_SIDE_INTERACTION = "server_side_interaction"
    STATE_TRANSITION = "state_transition"
    CONFIGURATION = "configuration"
    INFORMATION_EXPOSURE = "information_exposure"
    UNKNOWN = "unknown"
