"""Persistence tests for the atomic, append-only asset inventory JSON store."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from core.Exceptions import ResearchError
from research.JsonFileResearchAssetInventoryStore import (
    MAX_ASSET_INVENTORY_STORE_BYTES,
    MAX_ASSET_OBSERVATIONS,
    MAX_ASSET_RELATIONS,
    JsonFileResearchAssetInventoryStore,
    ResearchAssetInventoryDocument,
    _BoundedUtf8Writer,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import (
    ResearchAssetObservationRecord,
    canonicalize_asset_value,
)
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchAssetRelationKind import ResearchAssetRelationKind
from research.ResearchAssetRelationRecord import ResearchAssetRelationRecord

RECORDED = datetime(2026, 9, 20, 10, tzinfo=UTC)


def observation(
    observation_id: str = "observation-1",
    program_id: str = "program-a",
    kind: ResearchAssetKind = ResearchAssetKind.HOSTNAME,
    value: str = "example.test",
) -> ResearchAssetObservationRecord:
    return ResearchAssetObservationRecord(
        observation_id=observation_id,
        program_id=program_id,
        kind=kind,
        canonical_value=canonicalize_asset_value(kind, value),
        provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
        note="a note",
        recorded_at=RECORDED,
    )


def relation(
    relation_id: str = "relation-1",
    program_id: str = "program-a",
) -> ResearchAssetRelationRecord:
    return ResearchAssetRelationRecord(
        relation_id=relation_id,
        program_id=program_id,
        source_kind=ResearchAssetKind.HOSTNAME,
        source_value="example.test",
        related_kind=ResearchAssetKind.IP_ADDRESS,
        related_value="93.184.216.34",
        kind=ResearchAssetRelationKind.RESOLVES_TO,
        note="",
        recorded_at=RECORDED,
    )


class ResearchAssetInventoryDocumentTests(unittest.TestCase):
    def test_default_document_is_empty(self) -> None:
        document = ResearchAssetInventoryDocument()
        self.assertEqual(document.observations, ())
        self.assertEqual(document.relations, ())

    def test_duplicate_observation_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "duplicate observation IDs"):
            ResearchAssetInventoryDocument(
                observations=(
                    observation(observation_id="o1"),
                    observation(observation_id="o1", value="other.test"),
                )
            )

    def test_duplicate_relation_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "duplicate relation IDs"):
            ResearchAssetInventoryDocument(
                relations=(relation(relation_id="r1"), relation(relation_id="r1"))
            )

    def test_relation_must_reference_observed_assets_in_its_program(self) -> None:
        with self.assertRaisesRegex(ResearchError, "must reference observed assets"):
            ResearchAssetInventoryDocument(relations=(relation(),))

        hostname = observation(
            observation_id="hostname",
            kind=ResearchAssetKind.HOSTNAME,
            value="example.test",
        )
        other_program_address = observation(
            observation_id="address-other-program",
            program_id="program-b",
            kind=ResearchAssetKind.IP_ADDRESS,
            value="93.184.216.34",
        )
        with self.assertRaisesRegex(ResearchError, "must reference observed assets"):
            ResearchAssetInventoryDocument(
                observations=(hostname, other_program_address),
                relations=(relation(),),
            )

    def test_non_tuple_or_wrong_typed_members_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchAssetInventoryDocument(observations=[observation()])  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            ResearchAssetInventoryDocument(observations=("not-a-record",))  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            ResearchAssetInventoryDocument(relations=[relation()])  # type: ignore[arg-type]

    def test_bounded_counts_are_enforced(self) -> None:
        with patch(
            "research.JsonFileResearchAssetInventoryStore.MAX_ASSET_OBSERVATIONS", 1
        ):
            with self.assertRaisesRegex(ResearchError, "too many observations"):
                ResearchAssetInventoryDocument(
                    observations=(
                        observation(observation_id="o1"),
                        observation(observation_id="o2", value="other.test"),
                    )
                )
        with patch(
            "research.JsonFileResearchAssetInventoryStore.MAX_ASSET_RELATIONS", 1
        ):
            with self.assertRaisesRegex(ResearchError, "too many relations"):
                ResearchAssetInventoryDocument(
                    relations=(
                        relation(relation_id="r1"),
                        relation(relation_id="r2"),
                    )
                )


class JsonFileResearchAssetInventoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "asset_inventory.json"
        self.store = JsonFileResearchAssetInventoryStore(self.path)

    def test_loading_an_absent_file_returns_an_empty_document(self) -> None:
        document = self.store.load()

        self.assertEqual(document, ResearchAssetInventoryDocument())
        self.assertFalse(self.path.exists())

    def test_round_trip_preserves_observations_and_relations_of_every_kind(
        self,
    ) -> None:
        first = observation(observation_id="o1", value="example.test")
        second = observation(
            observation_id="o2",
            kind=ResearchAssetKind.IP_ADDRESS,
            value="93.184.216.34",
        )
        third = observation(
            observation_id="o3",
            kind=ResearchAssetKind.IP_ADDRESS,
            value="2606:4700::1111",
        )
        link = relation()
        document = ResearchAssetInventoryDocument(
            observations=(first, second, third), relations=(link,)
        )

        self.store.save(document)
        reloaded = self.store.load()

        self.assertEqual(reloaded, document)

    def test_saving_twice_appends_to_the_existing_document(self) -> None:
        original = ResearchAssetInventoryDocument(observations=(observation(),))
        self.store.save(original)
        appended = ResearchAssetInventoryDocument(
            observations=(
                *original.observations,
                observation(observation_id="o2", value="other.test"),
            )
        )

        self.store.save(appended)

        self.assertEqual(self.store.load(), appended)

    def test_save_rejects_removal_or_replacement_of_existing_records(self) -> None:
        original = ResearchAssetInventoryDocument(observations=(observation(),))
        self.store.save(original)
        replacement = ResearchAssetInventoryDocument(
            observations=(observation(observation_id="o2", value="other.test"),)
        )

        with self.assertRaisesRegex(ResearchError, "append-only"):
            self.store.save(replacement)

        self.assertEqual(self.store.load(), original)

    def test_save_rejects_anything_other_than_a_document(self) -> None:
        with self.assertRaises(ResearchError):
            self.store.save({"observations": [], "relations": []})  # type: ignore[arg-type]

    def test_no_temporary_file_is_left_behind_after_a_clean_save(self) -> None:
        self.store.save(ResearchAssetInventoryDocument(observations=(observation(),)))

        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    # -- malformed persisted content fails closed ---------------------------

    def _write_raw(self, payload: object) -> None:
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def test_non_dict_document_is_rejected(self) -> None:
        self._write_raw([])
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_wrong_field_set_is_rejected(self) -> None:
        for payload in (
            {"schema_version": 1, "observations": []},
            {
                "schema_version": 1,
                "observations": [],
                "relations": [],
                "extra": "field",
            },
        ):
            with self.subTest(payload=payload):
                self._write_raw(payload)
                with self.assertRaises(ResearchError):
                    self.store.load()

    def test_unsupported_schema_version_is_rejected(self) -> None:
        self._write_raw({"schema_version": 2, "observations": [], "relations": []})

        with self.assertRaisesRegex(ResearchError, "schema version"):
            self.store.load()

    def test_non_list_observations_or_relations_are_rejected(self) -> None:
        self._write_raw(
            {"schema_version": 1, "observations": "not-a-list", "relations": []}
        )
        with self.assertRaisesRegex(ResearchError, "must be a list"):
            self.store.load()
        self._write_raw(
            {"schema_version": 1, "observations": [], "relations": "not-a-list"}
        )
        with self.assertRaisesRegex(ResearchError, "must be a list"):
            self.store.load()

    def test_observation_document_with_wrong_field_set_is_rejected(self) -> None:
        self._write_raw(
            {
                "schema_version": 1,
                "observations": [
                    {
                        "observation_id": "o1",
                        "program_id": "program-a",
                        "kind": "hostname",
                        "canonical_value": "example.test",
                        "provenance": "operator_authored",
                        "note": "",
                        # missing recorded_at
                    }
                ],
                "relations": [],
            }
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_relation_document_with_wrong_field_set_is_rejected(self) -> None:
        self._write_raw(
            {
                "schema_version": 1,
                "observations": [],
                "relations": [
                    {
                        "relation_id": "r1",
                        "program_id": "program-a",
                        "source_kind": "hostname",
                        "source_value": "example.test",
                        "related_kind": "ip_address",
                        "related_value": "93.184.216.34",
                        "kind": "resolves_to",
                        "note": "",
                        # missing recorded_at
                    }
                ],
            }
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_duplicate_observation_id_in_persisted_content_is_rejected(self) -> None:
        record = {
            "observation_id": "o1",
            "program_id": "program-a",
            "kind": "hostname",
            "canonical_value": "example.test",
            "provenance": "operator_authored",
            "note": "",
            "recorded_at": RECORDED.isoformat(),
        }
        self._write_raw(
            {
                "schema_version": 1,
                "observations": [record, dict(record)],
                "relations": [],
            }
        )
        with self.assertRaisesRegex(ResearchError, "duplicate observation IDs"):
            self.store.load()

    def test_too_many_persisted_observations_is_rejected(self) -> None:
        record = {
            "observation_id": "o1",
            "program_id": "program-a",
            "kind": "hostname",
            "canonical_value": "example.test",
            "provenance": "operator_authored",
            "note": "",
            "recorded_at": RECORDED.isoformat(),
        }
        with patch(
            "research.JsonFileResearchAssetInventoryStore.MAX_ASSET_OBSERVATIONS", 1
        ):
            self._write_raw(
                {
                    "schema_version": 1,
                    "observations": [record, record],
                    "relations": [],
                }
            )
            with self.assertRaisesRegex(ResearchError, "too many observations"):
                self.store.load()

    def test_naive_timestamp_in_persisted_content_is_rejected(self) -> None:
        self._write_raw(
            {
                "schema_version": 1,
                "observations": [
                    {
                        "observation_id": "o1",
                        "program_id": "program-a",
                        "kind": "hostname",
                        "canonical_value": "example.test",
                        "provenance": "operator_authored",
                        "note": "",
                        "recorded_at": "2026-09-20T10:00:00",
                    }
                ],
                "relations": [],
            }
        )
        with self.assertRaisesRegex(ResearchError, "timezone-aware"):
            self.store.load()

    def test_invalid_kind_or_provenance_values_are_rejected(self) -> None:
        base = {
            "observation_id": "o1",
            "program_id": "program-a",
            "kind": "hostname",
            "canonical_value": "example.test",
            "provenance": "operator_authored",
            "note": "",
            "recorded_at": RECORDED.isoformat(),
        }
        for field, value in (("kind", "url"), ("provenance", "passive_discovery")):
            with self.subTest(field=field):
                broken = dict(base, **{field: value})
                self._write_raw(
                    {"schema_version": 1, "observations": [broken], "relations": []}
                )
                with self.assertRaises(ResearchError):
                    self.store.load()

    def test_oversized_store_is_rejected(self) -> None:
        self.store.save(ResearchAssetInventoryDocument(observations=(observation(),)))
        with patch(
            "research.JsonFileResearchAssetInventoryStore."
            "MAX_ASSET_INVENTORY_STORE_BYTES",
            1,
        ):
            with self.assertRaisesRegex(ResearchError, "too large"):
                self.store.load()

    # -- fault injection on the write path -----------------------------------

    def test_oversized_save_preserves_previous_snapshot_and_temp_file(self) -> None:
        original = ResearchAssetInventoryDocument(observations=(observation(),))
        self.store.save(original)
        original_bytes = self.path.read_bytes()

        with patch(
            "research.JsonFileResearchAssetInventoryStore."
            "MAX_ASSET_INVENTORY_STORE_BYTES",
            1,
        ):
            with self.assertRaisesRegex(ResearchError, "too large"):
                self.store.save(ResearchAssetInventoryDocument())

        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_failed_atomic_replace_preserves_previous_snapshot_and_cleans_temp(
        self,
    ) -> None:
        original = ResearchAssetInventoryDocument(observations=(observation(),))
        self.store.save(original)
        original_document = self.path.read_text(encoding="utf-8")
        replacement = ResearchAssetInventoryDocument(
            observations=(
                *original.observations,
                observation(observation_id="o2", value="other.test"),
            )
        )

        with patch(
            "research.JsonFileResearchAssetInventoryStore.os.replace",
            side_effect=OSError("replace unavailable"),
        ):
            with self.assertRaisesRegex(ResearchError, "Unable to write"):
                self.store.save(replacement)

        self.assertEqual(self.path.read_text(encoding="utf-8"), original_document)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_partial_write_failure_preserves_previous_snapshot_byte_for_byte(
        self,
    ) -> None:
        original = ResearchAssetInventoryDocument(observations=(observation(),))
        self.store.save(original)
        original_bytes = self.path.read_bytes()
        real_write = _BoundedUtf8Writer.write
        call_count = {"calls": 0}

        def flaky_write(self: _BoundedUtf8Writer, value: str) -> int:
            call_count["calls"] += 1
            if call_count["calls"] == 1:
                return real_write(self, value)
            raise OSError("simulated mid-write failure")

        replacement = ResearchAssetInventoryDocument(
            observations=(
                *original.observations,
                observation(observation_id="o2", value="other.test"),
            )
        )
        with patch.object(
            _BoundedUtf8Writer, "write", autospec=True, side_effect=flaky_write
        ):
            with self.assertRaises(ResearchError):
                self.store.save(replacement)

        self.assertGreaterEqual(
            call_count["calls"],
            2,
            "the failure must occur after a real write, not before one",
        )
        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    # -- a persisted non-canonical value must never be normalized on load ---

    def _document_with(self, **overrides: object) -> dict[str, object]:
        record = {
            "observation_id": "observation-1",
            "program_id": "program-a",
            "kind": "hostname",
            "canonical_value": "example.test",
            "provenance": "operator_authored",
            "note": "",
            "recorded_at": RECORDED.isoformat(),
        }
        record.update(overrides)
        return {"schema_version": 1, "observations": [record], "relations": []}

    def test_a_persisted_non_canonical_observation_value_fails_closed(self) -> None:
        """Loading must refuse it, never silently canonicalize it.

        Normalizing on load would merge two distinct persisted records into
        one asset — the forbidden silent-normalization shape. This pins the
        refusal so a later "helpful" parser change cannot pass unnoticed.
        """
        for value, kind in (
            ("EXAMPLE.TEST.", "hostname"),
            ("  example.test", "hostname"),
            ("2606:4700:0000:0000:0000:0000:0000:1111", "ip_address"),
            ("93.184.216.034", "ip_address"),
        ):
            with self.subTest(value=value):
                self._write_raw(self._document_with(canonical_value=value, kind=kind))
                with self.assertRaises(ResearchError):
                    self.store.load()

    def test_a_persisted_non_canonical_relation_endpoint_fails_closed(self) -> None:
        payload = {
            "schema_version": 1,
            "observations": [],
            "relations": [
                {
                    "relation_id": "relation-1",
                    "program_id": "program-a",
                    "source_kind": "hostname",
                    "source_value": "EXAMPLE.TEST.",
                    "related_kind": "ip_address",
                    "related_value": "93.184.216.34",
                    "kind": "resolves_to",
                    "note": "",
                    "recorded_at": RECORDED.isoformat(),
                }
            ],
        }

        self._write_raw(payload)

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_a_persisted_duplicate_relation_identity_is_rejected(self) -> None:
        first = relation(relation_id="relation-1")
        self.store.save(
            ResearchAssetInventoryDocument(
                observations=(
                    observation(observation_id="observation-1"),
                    observation(
                        observation_id="observation-2",
                        kind=ResearchAssetKind.IP_ADDRESS,
                        value="93.184.216.34",
                    ),
                ),
                relations=(first,),
            )
        )
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["relations"].append(dict(document["relations"][0]))

        self._write_raw(document)

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_the_on_disk_document_declares_schema_version_one(self) -> None:
        self.store.save(ResearchAssetInventoryDocument(observations=(observation(),)))

        document = json.loads(self.path.read_text(encoding="utf-8"))

        self.assertEqual(document["schema_version"], 1)

    def test_the_declared_ceilings_are_the_reviewed_values(self) -> None:
        """Pin the real limits; every other test patches them down to 1."""
        self.assertEqual(MAX_ASSET_OBSERVATIONS, 5_000)
        self.assertEqual(MAX_ASSET_RELATIONS, 5_000)
        self.assertEqual(MAX_ASSET_INVENTORY_STORE_BYTES, 4 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
