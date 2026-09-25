"""Operator-attested authentication state for historical research evidence.

These values describe how an operator says evidence was collected. They are
never a login instruction, credential, permission, or proof that a session is
still live.
"""

from enum import StrEnum


class ResearchAuthenticationState(StrEnum):
    UNAUTHENTICATED = "unauthenticated"
    AUTHENTICATED = "authenticated"
