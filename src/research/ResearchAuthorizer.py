"""Who may authorize bounded research work.

Exactly one answer is currently true, so exactly one value exists. A model, a
fetched source, the curiosity engine, the scheduler, a background worker, and a
future policy boundary are all non-authorizers, and none of them is listed here
— an enum member is a capability someone can select, and a value that exists
for symmetry eventually gets used.

This deliberately models no identity. There are no accounts, roles, usernames,
operator identifiers, or authentication providers in Hypatia, so recording
*which* human approved something would be recording a fact the system cannot
actually establish.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchAuthorizer(StrEnum):
    """Name the authority source behind one approval."""

    HUMAN = "human"

    @property
    def is_human(self) -> bool:
        """Return whether a person authorized this.

        Always true today, because nothing else may. Kept explicit so the day
        a second member is proposed, the assertion that this is still the only
        authorizer fails loudly rather than silently becoming untrue.
        """
        return self is ResearchAuthorizer.HUMAN
