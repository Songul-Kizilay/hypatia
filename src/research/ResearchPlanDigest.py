"""Content-derived identity for one exact research plan.

An approval must identify exactly what was approved before it can authorize
anything. `plan_id` cannot do that: it is a fresh UUID minted on every preview,
so two identical plans carry different identities and one plan previewed twice
carries two. Binding an approval to it would certify nothing about content.

`plan_digest` is the other identity. It covers everything that changes what
would be attempted and nothing that does not, so an unchanged plan digests
identically in another process and any edit produces a different value.

Two properties do the real work.

The encoding is length-prefixed rather than delimited. Every token declares its
own byte length, so no authored text can imitate a separator: a question
containing a colon, a newline, or the exact bytes of another field's encoding
still cannot make one plan encode as another. Naive joining with a separator
would leave exactly that hole, and it is the classic way a hash of structured
data stops meaning anything.

The encoder walks dataclass fields rather than naming them. A field added to
`ResearchPlanStep` or to any authorization it carries therefore enters the
digest automatically. Hand-listing the fields would mean a later field silently
falls outside the approved content — the failure being prevented here — and it
would fail quietly, which is worse.

An unknown value type raises rather than being coerced to text, for the same
reason: a type nobody considered must stop the digest, not be guessed at.
"""

from __future__ import annotations

import hashlib
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum

from core.Exceptions import ResearchError
from research.ResearchPlan import ResearchPlan

#: Included in the hashed payload so a future encoding change cannot silently
#: produce the same digest for a plan it would now describe differently.
CANONICAL_SCHEMA = "hypatia:research-plan-digest:v1"

#: Instance bookkeeping, deliberately outside the approved content. `plan_id`
#: is random per preview and `created_at` is the moment of previewing; neither
#: changes what the plan would attempt, and including either would make every
#: preview of one plan a different plan.
UNDIGESTED_PLAN_FIELDS = frozenset({"plan_id", "created_at"})

#: A digest is rendered as lowercase SHA-256 hex.
PLAN_DIGEST_CHARACTERS = 64


def plan_digest(plan: ResearchPlan) -> str:
    """Return the content identity of one validated plan."""
    return hashlib.sha256(canonical_plan_bytes(plan)).hexdigest()


def canonical_plan_bytes(plan: ResearchPlan) -> bytes:
    """Return the exact bytes a plan's digest is taken over.

    Separated from the digest so the encoding can be inspected and tested
    directly. A digest nobody can look inside is a digest nobody can review.
    """
    if not isinstance(plan, ResearchPlan):
        raise ResearchError("A research plan digest requires a validated plan.")
    payload = _encode(CANONICAL_SCHEMA) + _encode_dataclass(
        plan,
        skip=UNDIGESTED_PLAN_FIELDS,
    )
    return _token(b"p", payload)


def is_plan_digest(value: object) -> bool:
    """Return whether this is a well-formed digest value."""
    return (
        isinstance(value, str)
        and len(value) == PLAN_DIGEST_CHARACTERS
        and all(character in "0123456789abcdef" for character in value)
    )


def _token(tag: bytes, payload: bytes) -> bytes:
    """Frame one value so its own bytes can never be read as structure."""
    return tag + b":" + str(len(payload)).encode("ascii") + b":" + payload


def _encode(value: object) -> bytes:
    # Order matters. bool is an int and StrEnum is a str, so the narrower type
    # is tested first or it would be encoded as the wider one and two different
    # values could collide.
    if value is None:
        return _token(b"n", b"")
    if isinstance(value, bool):
        return _token(b"b", b"1" if value else b"0")
    if isinstance(value, Enum):
        return _token(
            b"e",
            _encode(type(value).__name__) + _encode(value.value),
        )
    if isinstance(value, str):
        return _token(b"s", value.encode("utf-8"))
    if isinstance(value, int):
        return _token(b"i", str(value).encode("ascii"))
    if isinstance(value, float):
        return _token(b"f", repr(value).encode("ascii"))
    if isinstance(value, tuple):
        return _token(b"t", b"".join(_encode(item) for item in value))
    if isinstance(value, frozenset):
        # Sorted by encoding so an unordered set has one canonical form.
        return _token(b"q", b"".join(sorted(_encode(item) for item in value)))
    if isinstance(value, datetime):
        return _token(b"m", value.isoformat().encode("utf-8"))
    if is_dataclass(value) and not isinstance(value, type):
        return _encode_dataclass(value, skip=frozenset())
    raise ResearchError(
        f"A research plan contains a value of unencodable type "
        f"'{type(value).__name__}'."
    )


def _encode_dataclass(value: object, *, skip: frozenset[str]) -> bytes:
    """Encode every declared field in declaration order, minus the skipped."""
    payload = _encode(type(value).__name__)
    for field in fields(value):  # type: ignore[arg-type]
        if field.name in skip:
            continue
        payload += _encode(field.name) + _encode(getattr(value, field.name))
    return _token(b"d", payload)
