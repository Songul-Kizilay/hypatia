"""An immutable, read-only index of already-described capability schemas.

This mirrors `ProductCapabilityCatalog`'s own shape deliberately, for the same
reason `ProductCapabilityCatalog` mirrors `ToolRegistry`: a table keyed by a
stable identity, built once at construction, with no mutation method, no
heuristic match, and no fallback.

SCHEMA KNOWN != INPUT AUTHORIZED. SCHEMA VALID != EXECUTION AUTHORIZED.
Nothing below ever starts a process, touches the network, selects a target,
grants a credential, or creates, consumes, or widens any authorization. A
lookup returns a schema or `None`; it never returns permission, and no
caller may treat it as any.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from tools.ProductCapabilitySchema import ProductCapabilitySchema


class ProductCapabilitySchemaCatalog:
    """Hold one immutable set of capability schemas, keyed by identity."""

    def __init__(self, schemas: tuple[ProductCapabilitySchema, ...] = ()) -> None:
        if not isinstance(schemas, tuple):
            raise ResearchError(
                "A capability schema catalog requires an immutable sequence."
            )
        by_identity: dict[str, ProductCapabilitySchema] = {}
        for schema in schemas:
            if not isinstance(schema, ProductCapabilitySchema):
                raise ResearchError(
                    "A capability schema catalog accepts only bounded schemas."
                )
            if schema.capability_identity in by_identity:
                raise ResearchError(
                    "That capability identity already has a schema in this catalog."
                )
            by_identity[schema.capability_identity] = schema
        self._by_identity = by_identity
        self._order = tuple(schema.capability_identity for schema in schemas)

    def lookup(self, identity: str) -> ProductCapabilitySchema | None:
        """Return the schema for this identity, or `None`.

        `None` means "no schema described here", never "close enough" and
        never "permitted". A caller deciding what to do about an absent
        schema does that on its own; this method does not decide for it.
        """
        if not isinstance(identity, str) or not identity:
            raise ResearchError("A capability identity must be non-empty text.")
        return self._by_identity.get(identity)

    def described(self, identity: str) -> bool:
        """Return whether this catalog holds a schema for this identity."""
        return isinstance(identity, str) and identity in self._by_identity

    @property
    def identities(self) -> tuple[str, ...]:
        """Return every described identity, in the order schemas were given."""
        return self._order

    def __len__(self) -> int:
        return len(self._order)
