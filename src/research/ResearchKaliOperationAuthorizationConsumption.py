"""Shared, single-source-of-truth exact-authorization matching.

Extracted from `cognition.KaliToolGateway`'s own inline `AUTHORIZATION`-stage
logic -- byte/semantics-identical, same raised messages, same comparisons,
same exact-equality discipline -- so the existing WSL/VMware dispatch gate
and the Guest-Agent host authorization handoff foundation
(`research.GuestAgentHostAuthorizationHandoff`) both enforce exactly the
same authority meaning. Duplicating this logic a second time would create
two independently-evolving copies of "does this authorization exactly
match this preview," which could silently drift apart; this module exists
so there is exactly one.

AUTHORIZATION RECORD PRESENT != AUTHORIZATION CONSUMED. AUTHORIZATION VALID
!= AUTHORIZATION CONSUMED. Neither function here grants anything by
existing. `find_exact_kali_operation_authorization` is a pure, read-only
decision over an already-loaded list -- it touches no store and performs
no durable write. `authorizations_excluding` is a pure list filter. The one
real durable consumption event is always a caller's own
`authorization_store.save(...)` call with the list `authorizations_excluding`
returns; this module never calls `save` itself, so it can never be the
place where "consumed" silently becomes true without a caller's own
persistence step actually running.
"""

from __future__ import annotations

from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchKaliOperationAuthorization import (
    ResearchKaliOperationAuthorization,
)
from research.ResearchKaliOperationPreview import ResearchKaliOperationPreview


def find_exact_kali_operation_authorization(
    authorizations: list[ResearchKaliOperationAuthorization],
    authorization_id: str,
    preview: ResearchKaliOperationPreview,
    *,
    now: datetime,
) -> ResearchKaliOperationAuthorization:
    """Return the one authorization that exactly, currently authorizes `preview`.

    Raises `core.Exceptions.ResearchError` -- with the exact wording
    `cognition.KaliToolGateway` already raised for this stage before this
    extraction -- when zero or more than one record names
    `authorization_id`, when the one match has expired as of `now`, or
    when any binding fact (operation digest, program ID, scope revision
    ID, scope revision digest, execution policy digest) does not exactly
    equal the already-validated preview's own value. Every comparison here
    is exact equality only -- never a prefix, substring, or case-
    insensitive match.
    """
    matches = tuple(
        authorization
        for authorization in authorizations
        if authorization.authorization_id == authorization_id
    )
    if len(matches) != 1:
        raise ResearchError("Kali operation run requires one recorded authorization.")
    authorization = matches[0]
    if authorization.has_expired_at(now):
        raise ResearchError("Kali operation run authorization has expired.")
    if authorization.operation_digest != preview.operation_digest:
        raise ResearchError("Kali operation run authorization digest does not match.")
    if (
        authorization.program_id != preview.program_id
        or authorization.scope_revision_id != preview.scope_revision_id
        or authorization.scope_revision_digest != preview.scope_revision_digest
        or authorization.execution_policy_digest != preview.execution_policy_digest
    ):
        raise ResearchError("Kali operation run authorization binding is stale.")
    return authorization


def authorizations_excluding(
    authorizations: list[ResearchKaliOperationAuthorization],
    authorization: ResearchKaliOperationAuthorization,
) -> list[ResearchKaliOperationAuthorization]:
    """Return every authorization except the one exact matched record.

    A pure filter: the input list is never mutated, and no other record's
    identity, order, or presence is affected.
    """
    return [
        entry
        for entry in authorizations
        if entry.authorization_id != authorization.authorization_id
    ]
