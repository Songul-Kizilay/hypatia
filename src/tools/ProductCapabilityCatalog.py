"""An immutable, read-only index of already-described product capabilities.

This mirrors `ToolRegistry`'s own shape deliberately: a table keyed by a
stable identity, built once at construction, with no mutation method, no
heuristic match, and no fallback. The resemblance is intentional -- it is
the same lesson applied one layer up. A catalog that quietly substituted a
near match, or that could be edited after construction, would make every
description it holds describe the wrong thing while remaining technically
present.

CAPABILITY REGISTERED != CAPABILITY PERMITTED. Nothing below ever starts a
process, touches the network, selects a target, grants a credential, or
creates, consumes, or widens any authorization. A lookup returns a
description or `None`; it never returns permission, and no caller may
treat it as any.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from tools.ProductCapabilityRecord import ProductCapabilityRecord


class ProductCapabilityCatalog:
    """Hold one immutable set of capability descriptions, keyed by identity."""

    def __init__(self, records: tuple[ProductCapabilityRecord, ...] = ()) -> None:
        if not isinstance(records, tuple):
            raise ResearchError("A capability catalog requires an immutable sequence.")
        by_identity: dict[str, ProductCapabilityRecord] = {}
        for record in records:
            if not isinstance(record, ProductCapabilityRecord):
                raise ResearchError(
                    "A capability catalog accepts only bounded records."
                )
            if record.identity in by_identity:
                raise ResearchError(
                    "That capability identity is already present in this catalog."
                )
            by_identity[record.identity] = record
        self._by_identity = by_identity
        self._order = tuple(record.identity for record in records)

    def lookup(self, identity: str) -> ProductCapabilityRecord | None:
        """Return the description for this identity, or `None`.

        `None` means "not described here", never "close enough" and never
        "permitted". A caller deciding what to do about an absent
        description does that on its own; this method does not decide for
        it, and returning a description for a present one is still only a
        description.
        """
        if not isinstance(identity, str) or not identity:
            raise ResearchError("A capability identity must be non-empty text.")
        return self._by_identity.get(identity)

    def described(self, identity: str) -> bool:
        """Return whether this catalog holds a description for this identity."""
        return isinstance(identity, str) and identity in self._by_identity

    @property
    def identities(self) -> tuple[str, ...]:
        """Return every described identity, in the order records were given."""
        return self._order

    def __len__(self) -> int:
        return len(self._order)
