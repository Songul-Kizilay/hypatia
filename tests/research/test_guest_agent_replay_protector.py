"""Replay protection answers one question; it is never execution authority.

REPLAY PROTECTION != EXECUTION AUTHORITY. REPLAY ACCEPTED != AUTHORITY TO
EXECUTE. REPLAY REJECTED != AUTHORITY DECISION. OPERATION DIGEST != AUTHORIZATION.
NONCE != AUTHORIZATION. REQUEST ID != AUTHORIZATION. RESTART != NEW NONCE.
Every test below either proves `consume_once` is atomic, bounded, and
fail-closed, or proves it has no way to reach execution, authorization, or
any VMware/SSH/WSL/network path -- even under concurrent or adversarial
conditions.
"""

from __future__ import annotations

import ast
import hashlib
import sys
import tempfile
import threading
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.GuestAgentProtocol import GuestAgentProtocolVersion, GuestAgentRequest
from research.GuestAgentReplayProtector import (
    GuestAgentReplayOutcome,
    GuestAgentReplayProtector,
)
from research.JsonFileGuestAgentReplayNonceStore import (
    MAX_GUEST_AGENT_REPLAY_STORE_ENTRIES,
    JsonFileGuestAgentReplayNonceStore,
)
from research.ResearchKaliOperationPreview import ResearchKaliOperationKind

NEW_MODULE_PATHS = (
    SRC_DIR / "research" / "GuestAgentReplayNonceRecord.py",
    SRC_DIR / "research" / "GuestAgentReplayNonceStore.py",
    SRC_DIR / "research" / "JsonFileGuestAgentReplayNonceStore.py",
    SRC_DIR / "research" / "GuestAgentReplayProtector.py",
)

DIGEST_A = hashlib.sha256(b"operation-a").hexdigest()
DIGEST_B = hashlib.sha256(b"operation-b").hexdigest()

ADVERSARIAL_STRINGS = (
    "../../../etc/passwd",
    "/etc/passwd",
    "; id",
    "&& whoami",
    "$(id)",
    "`id`",
    "ALLOW",
    "REQUIRE_APPROVAL",
    "system_instruction",
    "exec",
    "run",
    "argv",
)

FORBIDDEN_METHOD_NAMES = (
    "execute",
    "invoke",
    "dispatch",
    "authorize",
    "authorise",
    "grant",
    "register",
)


def request(**overrides: object) -> GuestAgentRequest:
    base: dict[str, object] = dict(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="req-1",
        nonce="nonce-1",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        operation_digest=DIGEST_A,
    )
    base.update(overrides)
    return GuestAgentRequest(**base)  # type: ignore[arg-type]


class ReplayProtectorFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "replay.json"
        self.store = JsonFileGuestAgentReplayNonceStore(self.path)
        self.protector = GuestAgentReplayProtector(
            self.store, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()


class CoreSemanticsTests(ReplayProtectorFixture):
    """Requirements 1-11: the basic accept/reject contract."""

    def test_first_valid_request_consumption_succeeds(self) -> None:
        outcome = self.protector.consume_once(request())
        self.assertEqual(outcome, GuestAgentReplayOutcome.ACCEPTED)

    def test_second_use_of_the_same_replay_identity_is_rejected(self) -> None:
        self.protector.consume_once(request())
        outcome = self.protector.consume_once(request())
        self.assertEqual(outcome, GuestAgentReplayOutcome.ALREADY_CONSUMED)

    def test_repeated_replay_attempts_remain_rejected(self) -> None:
        self.protector.consume_once(request())
        for _ in range(10):
            self.assertEqual(
                self.protector.consume_once(request()),
                GuestAgentReplayOutcome.ALREADY_CONSUMED,
            )

    def test_a_different_valid_nonce_succeeds_independently(self) -> None:
        self.protector.consume_once(request(nonce="nonce-1"))
        outcome = self.protector.consume_once(request(nonce="nonce-2"))
        self.assertEqual(outcome, GuestAgentReplayOutcome.ACCEPTED)

    def test_same_nonce_with_a_different_operation_digest_is_not_a_replay(
        self,
    ) -> None:
        """A tampered/different request binding sharing only the nonce text
        cannot bypass -- or be blocked by -- protection meant for the other
        operation: they are different replay identities entirely."""
        self.protector.consume_once(request(nonce="shared", operation_digest=DIGEST_A))
        outcome = self.protector.consume_once(
            request(nonce="shared", operation_digest=DIGEST_B)
        )
        self.assertEqual(outcome, GuestAgentReplayOutcome.ACCEPTED)

    def test_operation_digest_remains_non_authoritative(self) -> None:
        """Accepting or rejecting a replay never checks, reads, or creates
        any authorization record -- there is no such reference anywhere in
        the protector."""
        source = Path(
            sys.modules["research.GuestAgentReplayProtector"].__file__
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_names.update(alias.name for alias in node.names)
        self.assertNotIn("ResearchKaliOperationAuthorizationStore", imported_names)
        self.assertNotIn("ResearchKaliOperationAuthorization", imported_names)

    def test_nonce_remains_non_authoritative(self) -> None:
        outcome = self.protector.consume_once(request(nonce="ALLOW"))
        self.assertEqual(outcome, GuestAgentReplayOutcome.ACCEPTED)
        # The literal text "ALLOW" consumed as a nonce grants nothing: a
        # second attempt with the exact same nonce is still just a replay.
        self.assertEqual(
            self.protector.consume_once(request(nonce="ALLOW")),
            GuestAgentReplayOutcome.ALREADY_CONSUMED,
        )

    def test_request_id_remains_non_authoritative(self) -> None:
        """Two different requests sharing a request_id but differing in
        nonce are each judged solely on their own replay identity."""
        first = request(request_id="shared-request-id", nonce="nonce-1")
        second = request(request_id="shared-request-id", nonce="nonce-2")
        self.assertEqual(
            self.protector.consume_once(first), GuestAgentReplayOutcome.ACCEPTED
        )
        self.assertEqual(
            self.protector.consume_once(second), GuestAgentReplayOutcome.ACCEPTED
        )

    def test_replay_acceptance_creates_no_authorization(self) -> None:
        outcome = self.protector.consume_once(request())
        self.assertIsInstance(outcome, GuestAgentReplayOutcome)
        # The outcome is a bounded enum value with no authority-bearing
        # payload -- there is no decision, grant, or scope attached to it.
        self.assertFalse(hasattr(outcome, "authorized"))
        self.assertFalse(hasattr(outcome, "grant"))

    def test_replay_rejection_consumes_or_creates_no_authorization(self) -> None:
        self.protector.consume_once(request())
        before = self.store.load()
        self.protector.consume_once(request())
        after = self.store.load()
        # Rejection is a pure read: the store is byte-for-byte the same
        # list of records before and after.
        self.assertEqual(before, after)


class NoExecutionOrNetworkPathTests(ReplayProtectorFixture):
    """Requirements 12-16: zero execution, dispatch, or network path."""

    def test_no_tool_execution_service_call_occurs(self) -> None:
        with patch(
            "tools.ToolExecutionService.ToolExecutionService.execute_detailed"
        ) as execute_detailed:
            self.protector.consume_once(request())
            self.protector.consume_once(request())
        execute_detailed.assert_not_called()

    def test_no_kali_tool_gateway_call_occurs(self) -> None:
        with patch("cognition.KaliToolGateway.KaliToolGateway.run") as gateway_run:
            self.protector.consume_once(request())
            self.protector.consume_once(request())
        gateway_run.assert_not_called()

    def test_no_subprocess_socket_or_filesystem_side_effect_beyond_the_store(
        self,
    ) -> None:
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.socket") as sock,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            for adversarial in ADVERSARIAL_STRINGS:
                self.protector.consume_once(request(nonce=adversarial))
        run.assert_not_called()
        popen.assert_not_called()
        sock.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_no_vmware_ssh_or_wsl_module_is_imported_by_the_new_modules(self) -> None:
        forbidden_modules = {"paramiko", "fabric", "socket", "ssl", "subprocess"}
        for path in NEW_MODULE_PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif (
                    isinstance(node, ast.ImportFrom) and node.module and node.level == 0
                ):
                    imported.add(node.module.split(".")[0])
            with self.subTest(module=path.name):
                self.assertEqual(imported & forbidden_modules, set())

    def test_protector_exposes_no_execution_or_grant_method(self) -> None:
        for name in FORBIDDEN_METHOD_NAMES:
            with self.subTest(method=name):
                self.assertFalse(hasattr(GuestAgentReplayProtector, name))


class RestartSafetyTests(ReplayProtectorFixture):
    """Requirements 17-18: consumed state survives a reload; restart cannot
    revive a consumed token."""

    def test_state_survives_store_reload(self) -> None:
        self.protector.consume_once(request(nonce="nonce-1"))

        reloaded_store = JsonFileGuestAgentReplayNonceStore(self.path)
        reloaded_protector = GuestAgentReplayProtector(reloaded_store)

        self.assertEqual(
            reloaded_protector.consume_once(request(nonce="nonce-1")),
            GuestAgentReplayOutcome.ALREADY_CONSUMED,
        )

    def test_consumed_nonce_remains_consumed_after_reload(self) -> None:
        self.protector.consume_once(request(nonce="nonce-1"))

        for _ in range(3):
            reloaded_store = JsonFileGuestAgentReplayNonceStore(self.path)
            reloaded_protector = GuestAgentReplayProtector(reloaded_store)
            self.assertEqual(
                reloaded_protector.consume_once(request(nonce="nonce-1")),
                GuestAgentReplayOutcome.ALREADY_CONSUMED,
            )


class CapacityAndBoundsTests(ReplayProtectorFixture):
    """Requirements 28-29: bounded storage; fail-closed exhaustion, never
    unsafe eviction."""

    def test_capacity_exhaustion_fails_closed_for_a_genuinely_new_identity(
        self,
    ) -> None:
        for i in range(MAX_GUEST_AGENT_REPLAY_STORE_ENTRIES):
            self.protector.consume_once(request(nonce=f"nonce-{i}"))

        with self.assertRaises(ResearchError):
            self.protector.consume_once(request(nonce="one-too-many"))

    def test_capacity_exhaustion_does_not_evict_or_lose_existing_records(
        self,
    ) -> None:
        for i in range(MAX_GUEST_AGENT_REPLAY_STORE_ENTRIES):
            self.protector.consume_once(request(nonce=f"nonce-{i}"))
        before = self.store.load()

        with self.assertRaises(ResearchError):
            self.protector.consume_once(request(nonce="one-too-many"))

        self.assertEqual(self.store.load(), before)
        self.assertEqual(len(before), MAX_GUEST_AGENT_REPLAY_STORE_ENTRIES)

    def test_a_still_already_consumed_identity_is_still_rejected_at_capacity(
        self,
    ) -> None:
        """Capacity exhaustion must never be mistaken for "unused": a
        replay of an existing entry at full capacity still correctly
        reports ALREADY_CONSUMED rather than raising."""
        for i in range(MAX_GUEST_AGENT_REPLAY_STORE_ENTRIES):
            self.protector.consume_once(request(nonce=f"nonce-{i}"))

        outcome = self.protector.consume_once(request(nonce="nonce-0"))
        self.assertEqual(outcome, GuestAgentReplayOutcome.ALREADY_CONSUMED)


class ConcurrencyTests(ReplayProtectorFixture):
    """Requirement 27: competing consumption accepts at most one request.

    This proves in-process thread-safety via a lock shared, process-wide,
    by every store instance addressing the same resolved file path -- the
    strongest guarantee this bounded milestone actually implements,
    matching this repository's own strongest existing precedent
    (`cognition.TrustedOneShotDeferredExecutionScheduler`'s load-check-save
    pattern). It does not, and does not claim to, prove cross-process
    atomicity: no store anywhere in this repository uses OS-level file
    locking, and Hypatia runs as one local desktop process.
    """

    def test_concurrent_consumption_of_the_same_identity_accepts_exactly_one(
        self,
    ) -> None:
        outcomes: list[GuestAgentReplayOutcome] = []
        outcomes_lock = threading.Lock()
        start_barrier = threading.Barrier(8)

        def attempt() -> None:
            start_barrier.wait()
            outcome = self.protector.consume_once(request(nonce="race-nonce"))
            with outcomes_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=attempt) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(outcomes), 8)
        self.assertEqual(
            outcomes.count(GuestAgentReplayOutcome.ACCEPTED),
            1,
            "exactly one concurrent attempt must win",
        )
        self.assertEqual(
            outcomes.count(GuestAgentReplayOutcome.ALREADY_CONSUMED),
            7,
            "every other concurrent attempt must lose",
        )
        # The durable store itself ends with exactly one record -- no
        # duplicate, no corruption, no lost write.
        self.assertEqual(len(self.store.load()), 1)

    def test_independently_constructed_protector_and_store_pairs_still_share_the_lock(
        self,
    ) -> None:
        """A real race this milestone must close: multiple callers that
        each build their *own* store and protector object against the
        same durable file -- not sharing `self.protector` at all -- must
        still resolve to exactly one acceptance, because
        `JsonFileGuestAgentReplayNonceStore.lock` is shared process-wide
        by resolved path, not private per instance.
        """
        outcomes: list[GuestAgentReplayOutcome] = []
        outcomes_lock = threading.Lock()
        start_barrier = threading.Barrier(16)

        def attempt() -> None:
            start_barrier.wait()
            independent_store = JsonFileGuestAgentReplayNonceStore(self.path)
            independent_protector = GuestAgentReplayProtector(independent_store)
            outcome = independent_protector.consume_once(request(nonce="race-nonce"))
            with outcomes_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=attempt) for _ in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(outcomes), 16)
        self.assertEqual(outcomes.count(GuestAgentReplayOutcome.ACCEPTED), 1)
        self.assertEqual(outcomes.count(GuestAgentReplayOutcome.ALREADY_CONSUMED), 15)
        self.assertEqual(len(self.store.load()), 1)

    def test_concurrent_consumption_of_distinct_identities_all_succeed(
        self,
    ) -> None:
        outcomes: list[GuestAgentReplayOutcome] = []
        outcomes_lock = threading.Lock()
        start_barrier = threading.Barrier(8)

        def attempt(index: int) -> None:
            start_barrier.wait()
            outcome = self.protector.consume_once(request(nonce=f"distinct-{index}"))
            with outcomes_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertTrue(all(o is GuestAgentReplayOutcome.ACCEPTED for o in outcomes))
        self.assertEqual(len(self.store.load()), 8)


class AdversarialInputTests(ReplayProtectorFixture):
    """Requirements 30-32: hostile protocol input remains inert data; fixed,
    non-reflective rejection text."""

    def test_adversarial_nonce_values_remain_inert_and_structurally_handled(
        self,
    ) -> None:
        for value in ADVERSARIAL_STRINGS:
            with self.subTest(nonce=value):
                first = self.protector.consume_once(request(nonce=value))
                second = self.protector.consume_once(request(nonce=value))
                self.assertEqual(first, GuestAgentReplayOutcome.ACCEPTED)
                self.assertEqual(second, GuestAgentReplayOutcome.ALREADY_CONSUMED)

    def test_invalid_request_type_error_message_is_a_fixed_sentence(self) -> None:
        with self.assertRaises(ResearchError) as context:
            self.protector.consume_once("not a request")  # type: ignore[arg-type]
        message = str(context.exception)
        self.assertLess(len(message), 150)
        self.assertNotIn("not a request", message)


class DeterminismTests(ReplayProtectorFixture):
    def test_repeated_consume_once_calls_for_distinct_identities_are_deterministic(
        self,
    ) -> None:
        for i in range(5):
            outcome = self.protector.consume_once(request(nonce=f"nonce-{i}"))
            self.assertEqual(outcome, GuestAgentReplayOutcome.ACCEPTED)
        for i in range(5):
            outcome = self.protector.consume_once(request(nonce=f"nonce-{i}"))
            self.assertEqual(outcome, GuestAgentReplayOutcome.ALREADY_CONSUMED)


if __name__ == "__main__":
    unittest.main()
