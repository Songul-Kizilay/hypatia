"""Answer exactly one question: has this replay identity already been spent?

REPLAY PROTECTION != EXECUTION AUTHORITY. `GuestAgentReplayProtector.consume_once`
answers only "has this one-time protocol token already been consumed?" It
never answers "may this operation execute?" -- there is no scope, policy,
or `ResearchKaliOperationAuthorizationStore` reference anywhere in this
module, and nothing here dispatches a process, a tool, or a Kali operation.
REPLAY ACCEPTED != AUTHORITY TO EXECUTE; REPLAY REJECTED != AUTHORITY
DECISION. A future dispatcher must still independently check real
execution authority before doing anything -- consuming a replay token is a
prerequisite this milestone defines, never a grant this milestone issues.

Consume-before-effect, not check-then-consume: there is deliberately no
`is_consumed()` paired with a separate `mark_consumed()`. Exactly as
`research.ResearchPlanAuthorizationConsumer`'s own docstring explains for
plan approvals ("Consuming is deliberately part of asking. A separate
verify-then-consume pair would leave a window..."), `consume_once` performs
the check and the durable write as one atomic step, so there is no window
in which a caller could see "not yet consumed" and still have a second
caller see the same answer before either write lands.

Concurrency guarantee, stated precisely: a re-entrant lock (mirroring
`cognition.TrustedOneShotDeferredExecutionScheduler`'s own load-check-save
pattern, the strongest existing precedent for this exact shape of problem
in this repository) makes two concurrent `consume_once` calls *within one
Hypatia process* resolve to exactly one acceptance. That lock is shared
process-wide by every store instance addressing the same resolved file
path (`research.JsonFileGuestAgentReplayNonceStore`'s own `lock`
property), not merely private to whichever `GuestAgentReplayProtector`
object happens to call it -- so building a second protector, or a second
store object, against the same file does not reopen the race a single
shared lock would otherwise close. A store implementation with no such
shared lock to offer
(for example a pure in-memory test double) falls back to one private lock
per protector instance, which is still correct for that store's own
single-instance use. None of this provides cross-process mutual
exclusion: no store in this repository today uses OS-level file locking,
and building one would be new infrastructure beyond this bounded
milestone's scope. Hypatia runs as one local desktop process with no
existing multi-process writer for any durable store, so this is the
honest, repository-consistent guarantee to claim -- not a weaker one
dressed up as stronger, and not an invented cross-process guarantee this
milestone does not actually deliver.

Capacity is bounded and fails closed: once the durable store is at its
entry ceiling, a genuinely new replay identity is refused with a raised
`core.Exceptions.ResearchError` rather than evicting an older, still-valid
consumed record to make room (which would silently reopen replay for
whatever request that record was protecting) and rather than accepting
the new entry past the bound. No time-based expiry exists because no
authoritative lifetime for a `GuestAgentRequest` exists anywhere in the
repository today to expire it against; inventing one here would be a
security timeout with no grounding.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock

from core.Exceptions import ResearchError
from research.GuestAgentProtocol import GuestAgentRequest
from research.GuestAgentReplayNonceRecord import GuestAgentReplayNonceRecord
from research.GuestAgentReplayNonceStore import GuestAgentReplayNonceStore


class GuestAgentReplayOutcome(StrEnum):
    """Name the one bounded bookkeeping fact `consume_once` can report."""

    ACCEPTED = "accepted"
    ALREADY_CONSUMED = "already_consumed"


class GuestAgentReplayProtector:
    """Durably spend one request's replay identity, at most once."""

    def __init__(
        self,
        store: GuestAgentReplayNonceStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        # Reuse the store's own shared, path-keyed lock when it offers one
        # (as `JsonFileGuestAgentReplayNonceStore` does), so every protector
        # and store instance addressing the same durable file still
        # serializes correctly; fall back to a private lock otherwise.
        shared_lock = getattr(store, "lock", None)
        self._lock = shared_lock if shared_lock is not None else RLock()

    def consume_once(self, request: GuestAgentRequest) -> GuestAgentReplayOutcome:
        """Spend `request`'s replay identity, or report it was already spent.

        `ACCEPTED` means a new durable record now exists and this exact
        `(protocol_version, operation_digest, nonce)` triple can never be
        accepted again. `ALREADY_CONSUMED` means nothing was written -- the
        store is left exactly as it was. Neither outcome is, or implies,
        execution authority; both are pure bookkeeping about one-time use.

        Raises `ResearchError` when the durable store itself cannot safely
        proceed (malformed persistence, or the bounded entry ceiling
        reached for a genuinely new identity) -- fail-closed, never a
        silent `ACCEPTED`.
        """
        if not isinstance(request, GuestAgentRequest):
            raise ResearchError("Guest-agent replay consumption requires a request.")
        identity = (
            request.protocol_version.value,
            request.operation_digest,
            request.nonce,
        )
        with self._lock:
            records = self._store.load()
            if any(entry.replay_identity == identity for entry in records):
                return GuestAgentReplayOutcome.ALREADY_CONSUMED
            record = GuestAgentReplayNonceRecord(
                protocol_version=request.protocol_version,
                operation_digest=request.operation_digest,
                nonce=request.nonce,
                request_id=request.request_id,
                consumed_at=self._now(),
            )
            self._store.save([*records, record])
            return GuestAgentReplayOutcome.ACCEPTED

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError("Guest-agent replay clock must be timezone-aware.")
        return value.astimezone(UTC)
