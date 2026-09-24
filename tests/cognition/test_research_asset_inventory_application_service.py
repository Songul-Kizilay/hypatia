"""The Bug Bounty asset inventory service: durable writes, live-only scope.

Records only literal operator input; every scope reading is a fresh call
into the unchanged `ResearchTargetScope.resolve_hostname`/`resolve_addresses`
against a caller-supplied *currently active* revision, never cached or
persisted. Restart/reload must never let a stale reading substitute for a
live check, and a `RESOLVES_TO` relation never widens scope.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.ResearchAssetInventoryApplicationService import (
    RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
    RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
    RESEARCH_ASSET_RELATION_RECORD_INTENT,
    ResearchAssetInventoryApplicationService,
)
from core.Exceptions import ResearchError
from research.JsonFileResearchAssetInventoryStore import (
    JsonFileResearchAssetInventoryStore,
)
from research.ResearchAsset import ResearchAsset
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import ResearchAssetObservationRecord
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchAssetRelationKind import ResearchAssetRelationKind
from research.ResearchProgramScopeExecutionPolicy import (
    DEFAULT_PROGRAM_SCOPE_EXECUTION_POLICY,
)
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from research.ResearchTargetScope import ResearchTargetScope, TargetHostRule
from research.ResearchTargetScopeResolutionStatus import (
    ResearchTargetScopeResolutionStatus,
)
from response.ResponseComposer import ResponseComposer

NOW = datetime(2026, 9, 20, 12, tzinfo=UTC)


class InMemoryAssetInventoryStore:
    """A trivial store standing in for the JSON file, for fast unit tests."""

    def __init__(self) -> None:
        from research.JsonFileResearchAssetInventoryStore import (
            ResearchAssetInventoryDocument,
        )

        self._document = ResearchAssetInventoryDocument()

    def load(self):  # type: ignore[no-untyped-def]
        return self._document

    def save(self, document) -> None:  # type: ignore[no-untyped-def]
        self._document = document


class InMemoryScopeRevisionStore:
    def __init__(self, revisions: tuple[ResearchProgramScopeRevision, ...] = ()):
        self._revisions = list(revisions)

    def load(self) -> list[ResearchProgramScopeRevision]:
        return list(self._revisions)

    def save(self, revisions: list[ResearchProgramScopeRevision]) -> None:
        self._revisions = list(revisions)


def make_service(
    store=None,
    program_scope_revision_store=None,
    clock=lambda: NOW,
    id_factory=None,
) -> ResearchAssetInventoryApplicationService:
    ids = id_factory or iter(f"id-{number}" for number in range(1, 1000)).__next__
    return ResearchAssetInventoryApplicationService(
        store if store is not None else InMemoryAssetInventoryStore(),
        ResponseComposer(),
        clock=clock,
        id_factory=ids,
        program_scope_revision_store=program_scope_revision_store,
    )


def revision(
    program_id: str = "program-a",
    scope: ResearchTargetScope | None = None,
    confirmed_at: datetime = NOW - timedelta(minutes=1),
    expires_at: datetime | None = None,
) -> ResearchProgramScopeRevision:
    return ResearchProgramScopeRevision(
        revision_id="revision-1",
        program_id=program_id,
        scope=scope
        or ResearchTargetScope(allowed_hosts=(TargetHostRule("example.test"),)),
        confirmed_at=confirmed_at,
        expires_at=expires_at or (confirmed_at + timedelta(hours=1)),
        execution_policy=DEFAULT_PROGRAM_SCOPE_EXECUTION_POLICY,
    )


class RecordObservationDedupTests(unittest.TestCase):
    def test_two_forms_of_the_same_hostname_collapse_into_one_asset_with_both_kept(
        self,
    ) -> None:
        service = make_service()

        first = service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "EXAMPLE.TEST."
        )
        second = service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )

        [asset] = service.assets_for_program("program-a")
        self.assertEqual(asset.canonical_value, "example.test")
        self.assertEqual(asset.observations, (first, second))

    def test_distinct_values_never_collapse(self) -> None:
        service = make_service()
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "api.example.test"
        )
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "www.example.test"
        )

        assets = service.assets_for_program("program-a")

        self.assertEqual(len(assets), 2)

    def test_duplicate_observation_identity_is_rejected(self) -> None:
        service = make_service(id_factory=lambda: "fixed-id")

        service.record_observation("program-a", ResearchAssetKind.HOSTNAME, "a.test")

        with self.assertRaisesRegex(ResearchError, "identity already exists"):
            service.record_observation(
                "program-a", ResearchAssetKind.HOSTNAME, "b.test"
            )


class RecordRelationTests(unittest.TestCase):
    def _observed_service(self) -> ResearchAssetInventoryApplicationService:
        service = make_service()
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )
        service.record_observation(
            "program-a", ResearchAssetKind.IP_ADDRESS, "93.184.216.34"
        )
        return service

    def test_resolves_to_between_two_observed_assets_succeeds(self) -> None:
        service = self._observed_service()

        relation = service.record_relation(
            "program-a",
            ResearchAssetKind.HOSTNAME,
            "example.test",
            ResearchAssetKind.IP_ADDRESS,
            "93.184.216.34",
            ResearchAssetRelationKind.RESOLVES_TO,
        )

        self.assertEqual(service.relations_for_program("program-a"), (relation,))

    def test_self_relation_is_rejected(self) -> None:
        service = self._observed_service()

        with self.assertRaisesRegex(ResearchError, "relate an asset to itself"):
            service.record_relation(
                "program-a",
                ResearchAssetKind.HOSTNAME,
                "example.test",
                ResearchAssetKind.HOSTNAME,
                "example.test",
                ResearchAssetRelationKind.RESOLVES_TO,
            )

    def test_relation_to_a_never_observed_asset_is_rejected(self) -> None:
        service = self._observed_service()

        with self.assertRaisesRegex(ResearchError, "no recorded observation"):
            service.record_relation(
                "program-a",
                ResearchAssetKind.HOSTNAME,
                "example.test",
                ResearchAssetKind.IP_ADDRESS,
                "192.0.2.1",
                ResearchAssetRelationKind.RESOLVES_TO,
            )

    def test_relation_referencing_a_different_programs_observation_is_rejected(
        self,
    ) -> None:
        service = make_service()
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )
        service.record_observation(
            "program-b", ResearchAssetKind.IP_ADDRESS, "93.184.216.34"
        )

        with self.assertRaisesRegex(ResearchError, "no recorded observation"):
            service.record_relation(
                "program-a",
                ResearchAssetKind.HOSTNAME,
                "example.test",
                ResearchAssetKind.IP_ADDRESS,
                "93.184.216.34",
                ResearchAssetRelationKind.RESOLVES_TO,
            )

    def test_relation_never_moves_either_assets_scope_resolution(self) -> None:
        """A `RESOLVES_TO` relation carries no scope semantics of its own."""
        service = self._observed_service()
        active = revision(
            scope=ResearchTargetScope(allowed_hosts=(TargetHostRule("example.test"),))
        )
        [hostname_asset, address_asset] = sorted(
            service.assets_for_program("program-a"), key=lambda a: a.kind.value
        )
        before = service.current_scope_resolution(address_asset, active)

        service.record_relation(
            "program-a",
            ResearchAssetKind.HOSTNAME,
            "example.test",
            ResearchAssetKind.IP_ADDRESS,
            "93.184.216.34",
            ResearchAssetRelationKind.RESOLVES_TO,
        )
        [_, address_asset_after] = sorted(
            service.assets_for_program("program-a"), key=lambda a: a.kind.value
        )
        after = service.current_scope_resolution(address_asset_after, active)

        self.assertEqual(before, after)
        self.assertEqual(
            after.resolution.status, ResearchTargetScopeResolutionStatus.UNCERTAIN
        )


class ScopeIntegrationTests(unittest.TestCase):
    def _asset(self, service, program_id="program-a"):  # type: ignore[no-untyped-def]
        service.record_observation(
            program_id, ResearchAssetKind.HOSTNAME, "example.test"
        )
        [asset] = service.assets_for_program(program_id)
        return asset

    def test_allowed_host_resolves_in_scope(self) -> None:
        service = make_service()
        asset = self._asset(service)
        active = revision(
            scope=ResearchTargetScope(allowed_hosts=(TargetHostRule("example.test"),))
        )

        view = service.current_scope_resolution(asset, active)

        self.assertTrue(view.has_active_scope_revision)
        self.assertEqual(
            view.resolution.status, ResearchTargetScopeResolutionStatus.IN_SCOPE
        )

    def test_excluded_host_resolves_out_of_scope(self) -> None:
        service = make_service()
        asset = self._asset(service)
        active = revision(
            scope=ResearchTargetScope(
                allowed_hosts=(TargetHostRule("other.test"),),
                excluded_hosts=(TargetHostRule("example.test"),),
            )
        )

        view = service.current_scope_resolution(asset, active)

        self.assertEqual(
            view.resolution.status, ResearchTargetScopeResolutionStatus.OUT_OF_SCOPE
        )

    def test_unaddressed_host_resolves_uncertain(self) -> None:
        service = make_service()
        asset = self._asset(service)
        active = revision(
            scope=ResearchTargetScope(allowed_hosts=(TargetHostRule("other.test"),))
        )

        view = service.current_scope_resolution(asset, active)

        self.assertEqual(
            view.resolution.status, ResearchTargetScopeResolutionStatus.UNCERTAIN
        )

    def test_no_active_revision_yields_no_fabricated_resolution(self) -> None:
        service = make_service()
        asset = self._asset(service)

        view = service.current_scope_resolution(asset, None)

        self.assertFalse(view.has_active_scope_revision)
        self.assertIsNone(view.resolution)

    def test_restart_reload_recomputes_identical_assets_and_never_a_stale_scope(
        self,
    ) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "asset_inventory.json"
        file_store = JsonFileResearchAssetInventoryStore(path)
        service = make_service(store=file_store)
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )

        [asset_before] = service.assets_for_program("program-a")

        reloaded_service = make_service(store=JsonFileResearchAssetInventoryStore(path))
        [asset_after] = reloaded_service.assets_for_program("program-a")

        self.assertEqual(asset_before, asset_after)

        # A restart alone (no active revision supplied) must never resolve to
        # a stored/fabricated `IN_SCOPE` reading -- it is explicitly "no
        # active scope revision", never a fabricated resolution.
        view = reloaded_service.current_scope_resolution(asset_after, None)
        self.assertFalse(view.has_active_scope_revision)
        self.assertIsNone(view.resolution)

    def test_resolution_is_always_freshly_computed_never_read_from_a_stored_field(
        self,
    ) -> None:
        """There is no persisted field a resolution could be read from.

        `ResearchAsset`/`ResearchAssetObservationRecord` carry only identity
        and provenance fields -- structurally, nothing on them could hold a
        cached scope verdict.
        """
        service = make_service()
        asset = self._asset(service)
        observation_fields = {
            field for field in asset.observations[0].__dataclass_fields__
        }
        asset_fields = {field for field in asset.__dataclass_fields__}

        for forbidden in ("scope", "resolution", "in_scope", "status"):
            self.assertNotIn(forbidden, observation_fields)
            self.assertNotIn(forbidden, asset_fields)

    def test_program_scope_revision_from_a_different_program_is_rejected(
        self,
    ) -> None:
        """A reusable scope-view boundary cannot accept another program's policy."""
        service = make_service()
        asset = self._asset(service, program_id="program-a")
        other_program_revision = revision(program_id="program-b")

        with self.assertRaisesRegex(ResearchError, "same program"):
            service.current_scope_resolution(asset, other_program_revision)


class ActiveRevisionLookupIsolationTests(unittest.TestCase):
    def test_preview_never_sees_another_programs_scope_revision(self) -> None:
        scope_store = InMemoryScopeRevisionStore(
            (
                revision(
                    program_id="program-b",
                    scope=ResearchTargetScope(
                        allowed_hosts=(TargetHostRule("example.test"),)
                    ),
                ),
            )
        )
        service = make_service(program_scope_revision_store=scope_store)
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )
        request = BrainRequest(
            message="preview",
            metadata={
                "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                "program_id": "program-a",
            },
        )

        response = service.process_inventory_preview(request)

        [entry] = response.research_asset_inventory
        self.assertFalse(entry.scope.has_active_scope_revision)
        self.assertIsNone(entry.scope.resolution)

    def test_contradictory_active_revision_history_fails_closed(self) -> None:
        scope_store = InMemoryScopeRevisionStore(
            (
                ResearchProgramScopeRevision(
                    revision_id="revision-1",
                    program_id="program-a",
                    scope=ResearchTargetScope(
                        allowed_hosts=(TargetHostRule("example.test"),)
                    ),
                    confirmed_at=NOW - timedelta(minutes=5),
                    expires_at=NOW + timedelta(minutes=55),
                ),
                ResearchProgramScopeRevision(
                    revision_id="revision-2",
                    program_id="program-a",
                    scope=ResearchTargetScope(
                        allowed_hosts=(TargetHostRule("other.test"),)
                    ),
                    confirmed_at=NOW - timedelta(minutes=1),
                    expires_at=NOW + timedelta(minutes=59),
                ),
            )
        )
        service = make_service(program_scope_revision_store=scope_store)
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )
        request = BrainRequest(
            message="preview",
            metadata={
                "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                "program_id": "program-a",
            },
        )

        response = service.process_inventory_preview(request)

        self.assertFalse(response.success)
        self.assertIn("contradictory", response.message)


class BrainIntentTests(unittest.TestCase):
    def test_is_request_predicates_match_only_their_own_intent(self) -> None:
        observation_request = BrainRequest(
            message="record",
            metadata={"intent": RESEARCH_ASSET_OBSERVATION_RECORD_INTENT},
        )
        relation_request = BrainRequest(
            message="record",
            metadata={"intent": RESEARCH_ASSET_RELATION_RECORD_INTENT},
        )
        preview_request = BrainRequest(
            message="preview",
            metadata={"intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT},
        )
        unrelated = BrainRequest(message="chat", metadata={"intent": "message"})

        self.assertTrue(
            ResearchAssetInventoryApplicationService.is_observation_record_request(
                observation_request
            )
        )
        self.assertTrue(
            ResearchAssetInventoryApplicationService.is_relation_record_request(
                relation_request
            )
        )
        self.assertTrue(
            ResearchAssetInventoryApplicationService.is_inventory_preview_request(
                preview_request
            )
        )
        for predicate in (
            ResearchAssetInventoryApplicationService.is_observation_record_request,
            ResearchAssetInventoryApplicationService.is_relation_record_request,
            ResearchAssetInventoryApplicationService.is_inventory_preview_request,
        ):
            self.assertFalse(predicate(unrelated))

    def test_process_observation_record_succeeds_with_full_metadata(self) -> None:
        service = make_service()
        request = BrainRequest(
            message="record",
            metadata={
                "intent": RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
                "program_id": "program-a",
                "kind": ResearchAssetKind.HOSTNAME,
                "value": "EXAMPLE.TEST.",
                "note": "found in scope brief",
            },
        )

        response = service.process_observation_record(request)

        self.assertTrue(response.success, response.message)
        assert response.research_asset_observation_record is not None
        self.assertEqual(
            response.research_asset_observation_record.canonical_value,
            "example.test",
        )

    def test_process_observation_record_rejects_malformed_fields(self) -> None:
        service = make_service()
        base = {
            "intent": RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
            "program_id": "program-a",
            "kind": ResearchAssetKind.HOSTNAME,
            "value": "example.test",
        }
        broken_variants = (
            {**base, "program_id": None},
            {**base, "program_id": 123},
            {**base, "kind": "hostname"},
            {**base, "kind": None},
            {**base, "value": None},
            {**base, "value": 123},
            {**base, "note": 123},
        )
        # A "provenance" key is no longer among the malformed variants: the
        # handler never reads it, so no request value can influence the
        # recorded provenance. ProvenanceIsAlwaysOperatorAuthoredTests pins
        # that the key is ignored rather than honored.
        for metadata in broken_variants:
            with self.subTest(metadata=metadata):
                response = service.process_observation_record(
                    BrainRequest(message="record", metadata=metadata)
                )
                self.assertFalse(response.success)
                self.assertIsNone(response.research_asset_observation_record)

    def test_process_relation_record_succeeds_with_full_metadata(self) -> None:
        service = make_service()
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )
        service.record_observation(
            "program-a", ResearchAssetKind.IP_ADDRESS, "93.184.216.34"
        )
        request = BrainRequest(
            message="record",
            metadata={
                "intent": RESEARCH_ASSET_RELATION_RECORD_INTENT,
                "program_id": "program-a",
                "source_kind": ResearchAssetKind.HOSTNAME,
                "source_value": "example.test",
                "related_kind": ResearchAssetKind.IP_ADDRESS,
                "related_value": "93.184.216.34",
                "kind": ResearchAssetRelationKind.RESOLVES_TO,
                "note": "",
            },
        )

        response = service.process_relation_record(request)

        self.assertTrue(response.success, response.message)
        self.assertIsNotNone(response.research_asset_relation_record)

    def test_process_relation_record_rejects_malformed_fields(self) -> None:
        service = make_service()
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )
        service.record_observation(
            "program-a", ResearchAssetKind.IP_ADDRESS, "93.184.216.34"
        )
        base = {
            "intent": RESEARCH_ASSET_RELATION_RECORD_INTENT,
            "program_id": "program-a",
            "source_kind": ResearchAssetKind.HOSTNAME,
            "source_value": "example.test",
            "related_kind": ResearchAssetKind.IP_ADDRESS,
            "related_value": "93.184.216.34",
            "kind": ResearchAssetRelationKind.RESOLVES_TO,
        }
        broken_variants = (
            {**base, "program_id": None},
            {**base, "source_kind": "hostname"},
            {**base, "related_kind": "ip_address"},
            {**base, "source_value": None},
            {**base, "related_value": None},
            {**base, "kind": "resolves_to"},
        )
        for metadata in broken_variants:
            with self.subTest(metadata=metadata):
                response = service.process_relation_record(
                    BrainRequest(message="record", metadata=metadata)
                )
                self.assertFalse(response.success)
                self.assertIsNone(response.research_asset_relation_record)

    def test_process_inventory_preview_reports_assets_and_relations(self) -> None:
        scope_store = InMemoryScopeRevisionStore((revision(),))
        service = make_service(program_scope_revision_store=scope_store)
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )
        service.record_observation(
            "program-a", ResearchAssetKind.IP_ADDRESS, "93.184.216.34"
        )
        service.record_relation(
            "program-a",
            ResearchAssetKind.HOSTNAME,
            "example.test",
            ResearchAssetKind.IP_ADDRESS,
            "93.184.216.34",
            ResearchAssetRelationKind.RESOLVES_TO,
        )
        request = BrainRequest(
            message="preview",
            metadata={
                "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                "program_id": "program-a",
            },
        )

        response = service.process_inventory_preview(request)

        self.assertTrue(response.success, response.message)
        self.assertEqual(len(response.research_asset_inventory), 2)
        self.assertEqual(len(response.research_asset_relations), 1)
        self.assertIn(
            "recomputed live from active policy, not stored", response.message
        )

    def test_process_inventory_preview_rejects_missing_program_id(self) -> None:
        service = make_service()
        request = BrainRequest(
            message="preview",
            metadata={"intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT},
        )

        response = service.process_inventory_preview(request)

        self.assertFalse(response.success)
        self.assertEqual(response.research_asset_inventory, ())


class ScopeReadingFreshnessTests(unittest.TestCase):
    """The reading must follow the live policy, not the asset's own history.

    A memoized resolution keyed on the asset identity would satisfy every
    tri-state test while breaking the invariant this milestone exists for:
    recording an asset is not authority, and a past reading is never a
    current one. These tests change the policy under a live service and
    across a restart, so a cached reading fails them.
    """

    def _preview(
        self,
        service: ResearchAssetInventoryApplicationService,
        program_id: str = "program-a",
    ):  # type: ignore[no-untyped-def]
        return service.process_inventory_preview(
            BrainRequest(
                message="preview",
                metadata={
                    "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                    "program_id": program_id,
                },
            )
        )

    @staticmethod
    def _status(response):  # type: ignore[no-untyped-def]
        (entry,) = response.research_asset_inventory
        return entry.scope.resolution.status if entry.scope.resolution else None

    def test_a_changed_policy_changes_the_reading_on_the_same_service(self) -> None:
        revisions = InMemoryScopeRevisionStore((revision(),))
        service = make_service(program_scope_revision_store=revisions)
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )

        before = self._preview(service)
        revisions.save(
            [
                revision(
                    scope=ResearchTargetScope(
                        allowed_hosts=(TargetHostRule("other.test"),)
                    )
                )
            ]
        )
        after = self._preview(service)

        self.assertEqual(
            self._status(before), ResearchTargetScopeResolutionStatus.IN_SCOPE
        )
        self.assertEqual(
            self._status(after), ResearchTargetScopeResolutionStatus.UNCERTAIN
        )

    def test_an_explicit_exclusion_added_later_is_honored_immediately(self) -> None:
        revisions = InMemoryScopeRevisionStore((revision(),))
        service = make_service(program_scope_revision_store=revisions)
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )
        self.assertEqual(
            self._status(self._preview(service)),
            ResearchTargetScopeResolutionStatus.IN_SCOPE,
        )

        revisions.save(
            [
                revision(
                    scope=ResearchTargetScope(
                        allowed_hosts=(TargetHostRule("example.test"),),
                        excluded_hosts=(TargetHostRule("example.test"),),
                    )
                )
            ]
        )

        self.assertEqual(
            self._status(self._preview(service)),
            ResearchTargetScopeResolutionStatus.OUT_OF_SCOPE,
        )

    def test_an_expired_revision_stops_producing_a_reading(self) -> None:
        moment = NOW
        revisions = InMemoryScopeRevisionStore((revision(),))
        service = make_service(
            program_scope_revision_store=revisions, clock=lambda: moment
        )
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )
        self.assertEqual(
            self._status(self._preview(service)),
            ResearchTargetScopeResolutionStatus.IN_SCOPE,
        )

        moment = NOW + timedelta(hours=2)
        response = self._preview(service)

        (entry,) = response.research_asset_inventory
        self.assertFalse(entry.scope.has_active_scope_revision)
        self.assertIsNone(entry.scope.resolution)

    def test_a_revoked_revision_does_not_survive_a_restart_as_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "research_asset_inventory.json"
            revisions = InMemoryScopeRevisionStore((revision(),))
            service = make_service(
                store=JsonFileResearchAssetInventoryStore(path),
                program_scope_revision_store=revisions,
            )
            service.record_observation(
                "program-a", ResearchAssetKind.HOSTNAME, "example.test"
            )
            self.assertEqual(
                self._status(self._preview(service)),
                ResearchTargetScopeResolutionStatus.IN_SCOPE,
            )

            revisions.save([revision().revoked(at=NOW)])
            restarted = make_service(
                store=JsonFileResearchAssetInventoryStore(path),
                program_scope_revision_store=revisions,
            )
            response = self._preview(restarted)

            (entry,) = response.research_asset_inventory
            self.assertEqual(entry.asset.canonical_value, "example.test")
            self.assertFalse(entry.scope.has_active_scope_revision)
            self.assertIsNone(entry.scope.resolution)


class RestartDeterminismTests(unittest.TestCase):
    def test_reload_preserves_every_asset_and_observation_order(self) -> None:
        """Two observations of one identity plus a second asset, reloaded.

        The thin single-observation fixture cannot catch an ordering or
        grouping regression introduced by the JSON round-trip.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "research_asset_inventory.json"
            service = make_service(store=JsonFileResearchAssetInventoryStore(path))
            first = service.record_observation(
                "program-a", ResearchAssetKind.HOSTNAME, "EXAMPLE.TEST."
            )
            second = service.record_observation(
                "program-a", ResearchAssetKind.HOSTNAME, "example.test", "second look"
            )
            third = service.record_observation(
                "program-a", ResearchAssetKind.IP_ADDRESS, "93.184.216.34"
            )
            before = service.assets_for_program("program-a")

            reloaded = make_service(
                store=JsonFileResearchAssetInventoryStore(path)
            ).assets_for_program("program-a")

            self.assertEqual(reloaded, before)
            hostname_asset = next(
                asset for asset in reloaded if asset.kind is ResearchAssetKind.HOSTNAME
            )
            address_asset = next(
                asset
                for asset in reloaded
                if asset.kind is ResearchAssetKind.IP_ADDRESS
            )
            self.assertEqual(hostname_asset.observations, (first, second))
            self.assertEqual(address_asset.observations, (third,))


class RefusalLeavesNothingPersistedTests(unittest.TestCase):
    """Every refused write must leave the log exactly as it was."""

    def setUp(self) -> None:
        self.service = make_service()
        self.service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )
        self.service.record_observation(
            "program-a", ResearchAssetKind.IP_ADDRESS, "93.184.216.34"
        )
        self.assets_before = self.service.assets_for_program("program-a")

    def _assert_nothing_changed(self) -> None:
        self.assertEqual(
            self.service.assets_for_program("program-a"), self.assets_before
        )
        self.assertEqual(self.service.relations_for_program("program-a"), ())

    def test_a_self_relation_refusal_persists_nothing(self) -> None:
        with self.assertRaises(ResearchError):
            self.service.record_relation(
                "program-a",
                ResearchAssetKind.HOSTNAME,
                "example.test",
                ResearchAssetKind.HOSTNAME,
                "example.test",
                ResearchAssetRelationKind.RESOLVES_TO,
            )

        self._assert_nothing_changed()

    def test_an_unobserved_endpoint_refusal_persists_nothing(self) -> None:
        with self.assertRaises(ResearchError):
            self.service.record_relation(
                "program-a",
                ResearchAssetKind.HOSTNAME,
                "example.test",
                ResearchAssetKind.IP_ADDRESS,
                "203.0.113.9",
                ResearchAssetRelationKind.RESOLVES_TO,
            )

        self._assert_nothing_changed()

    def test_a_cross_program_relation_refusal_persists_nothing(self) -> None:
        with self.assertRaises(ResearchError):
            self.service.record_relation(
                "program-b",
                ResearchAssetKind.HOSTNAME,
                "example.test",
                ResearchAssetKind.IP_ADDRESS,
                "93.184.216.34",
                ResearchAssetRelationKind.RESOLVES_TO,
            )

        self._assert_nothing_changed()
        self.assertEqual(self.service.assets_for_program("program-b"), ())

    def test_a_malformed_observation_refusal_persists_nothing(self) -> None:
        with self.assertRaises(ResearchError):
            self.service.record_observation(
                "program-a", ResearchAssetKind.HOSTNAME, "not a host!!"
            )

        self._assert_nothing_changed()

    def test_a_duplicate_relation_identity_is_refused(self) -> None:
        # Distinct observation IDs, then the same relation ID twice, so the
        # refusal under test is the relation-identity one and not the
        # observation-identity one.
        identities = iter(("obs-1", "obs-2", "rel-1", "rel-1")).__next__
        service = make_service(id_factory=identities)
        service.record_observation(
            "program-a", ResearchAssetKind.HOSTNAME, "example.test"
        )
        service.record_observation(
            "program-a", ResearchAssetKind.IP_ADDRESS, "93.184.216.34"
        )
        arguments = (
            "program-a",
            ResearchAssetKind.HOSTNAME,
            "example.test",
            ResearchAssetKind.IP_ADDRESS,
            "93.184.216.34",
            ResearchAssetRelationKind.RESOLVES_TO,
        )
        service.record_relation(*arguments)

        with self.assertRaises(ResearchError):
            service.record_relation(*arguments)

        self.assertEqual(len(service.relations_for_program("program-a")), 1)


class ProvenanceIsAlwaysOperatorAuthoredTests(unittest.TestCase):
    def test_request_metadata_cannot_choose_the_recorded_provenance(self) -> None:
        """Provenance is attested by the path, never by the request.

        Reading it from metadata would be a ready-made provenance-forging
        seam the moment a second provenance kind exists.
        """
        service = make_service()
        request = BrainRequest(
            message="record",
            metadata={
                "intent": RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
                "program_id": "program-a",
                "kind": ResearchAssetKind.HOSTNAME,
                "value": "example.test",
                "provenance": "tool_attested",
            },
        )

        response = service.process_observation_record(request)

        self.assertTrue(response.success, response.message)
        record = response.research_asset_observation_record
        assert record is not None
        self.assertIs(record.provenance, ResearchAssetProvenanceKind.OPERATOR_AUTHORED)


class UnresolvableKindFailsClosedTests(unittest.TestCase):
    def test_an_asset_kind_with_no_resolver_branch_raises(self) -> None:
        """A future asset kind must not inherit address-rule resolution."""
        asset = ResearchAsset(
            program_id="program-a",
            kind=ResearchAssetKind.HOSTNAME,
            canonical_value="example.test",
            observations=(
                ResearchAssetObservationRecord(
                    observation_id="observation-1",
                    program_id="program-a",
                    kind=ResearchAssetKind.HOSTNAME,
                    canonical_value="example.test",
                    provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                    note="",
                    recorded_at=NOW,
                ),
            ),
        )
        unknown = object.__new__(ResearchAsset)
        object.__setattr__(unknown, "program_id", asset.program_id)
        object.__setattr__(unknown, "kind", "future_kind")
        object.__setattr__(unknown, "canonical_value", asset.canonical_value)
        object.__setattr__(unknown, "observations", asset.observations)

        with self.assertRaisesRegex(ResearchError, "not resolvable against scope"):
            ResearchAssetInventoryApplicationService.current_scope_resolution(
                unknown, revision()
            )


if __name__ == "__main__":
    unittest.main()
