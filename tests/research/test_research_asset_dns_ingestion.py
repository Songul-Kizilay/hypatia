"""Fail-closed invariants for the DNS ingestion preview/result value types."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchAssetDnsIngestion import (
    ResearchAssetDnsIngestionAddressPreview,
    ResearchAssetDnsIngestionAssetPreview,
    ResearchAssetDnsIngestionPreview,
    ResearchAssetDnsIngestionResult,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import ResearchAssetObservationRecord
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchAssetRelationKind import ResearchAssetRelationKind
from research.ResearchAssetRelationRecord import ResearchAssetRelationRecord
from research.ResearchDnsLookupResultParser import ResearchDnsLookupRejectedRow
from research.ResearchKaliOperationPreview import ResearchDnsRecordType

RECORDED = datetime(2026, 9, 24, 10, tzinfo=UTC)
OPERATION_DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64


def hostname_observation(
    program_id: str = "program-a",
    digest: str = OPERATION_DIGEST,
) -> ResearchAssetObservationRecord:
    return ResearchAssetObservationRecord(
        observation_id="hostname-observation",
        program_id=program_id,
        kind=ResearchAssetKind.HOSTNAME,
        canonical_value="www.example.test",
        provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
        note="",
        recorded_at=RECORDED,
        source_operation_digest=digest,
    )


def address_observation(
    canonical_value: str = "93.184.216.34",
    program_id: str = "program-a",
    digest: str = OPERATION_DIGEST,
) -> ResearchAssetObservationRecord:
    return ResearchAssetObservationRecord(
        observation_id=f"address-observation-{canonical_value}",
        program_id=program_id,
        kind=ResearchAssetKind.IP_ADDRESS,
        canonical_value=canonical_value,
        provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
        note="",
        recorded_at=RECORDED,
        source_operation_digest=digest,
    )


def resolves_to_relation(
    related_value: str = "93.184.216.34",
    program_id: str = "program-a",
    digest: str = OPERATION_DIGEST,
) -> ResearchAssetRelationRecord:
    return ResearchAssetRelationRecord(
        relation_id=f"relation-{related_value}",
        program_id=program_id,
        source_kind=ResearchAssetKind.HOSTNAME,
        source_value="www.example.test",
        related_kind=ResearchAssetKind.IP_ADDRESS,
        related_value=related_value,
        kind=ResearchAssetRelationKind.RESOLVES_TO,
        provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
        note="",
        recorded_at=RECORDED,
        source_operation_digest=digest,
    )


class ResearchAssetDnsIngestionAssetPreviewTests(unittest.TestCase):
    def test_valid_preview_constructs(self) -> None:
        preview = ResearchAssetDnsIngestionAssetPreview(
            kind=ResearchAssetKind.HOSTNAME,
            canonical_value="www.example.test",
            already_known=False,
        )
        self.assertFalse(preview.already_known)

    def test_empty_canonical_value_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchAssetDnsIngestionAssetPreview(
                kind=ResearchAssetKind.HOSTNAME,
                canonical_value="",
                already_known=False,
            )


class ResearchAssetDnsIngestionAddressPreviewTests(unittest.TestCase):
    def test_a_hostname_asset_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchAssetDnsIngestionAddressPreview(
                asset=ResearchAssetDnsIngestionAssetPreview(
                    kind=ResearchAssetKind.HOSTNAME,
                    canonical_value="www.example.test",
                    already_known=False,
                ),
                resolves_to_relation_already_known=False,
            )

    def test_a_valid_address_preview_constructs(self) -> None:
        preview = ResearchAssetDnsIngestionAddressPreview(
            asset=ResearchAssetDnsIngestionAssetPreview(
                kind=ResearchAssetKind.IP_ADDRESS,
                canonical_value="93.184.216.34",
                already_known=True,
            ),
            resolves_to_relation_already_known=True,
        )
        self.assertTrue(preview.resolves_to_relation_already_known)


def _preview(
    address_assets: tuple[ResearchAssetDnsIngestionAddressPreview, ...] = (),
    rejected_rows: tuple[ResearchDnsLookupRejectedRow, ...] = (),
    **overrides: object,
) -> ResearchAssetDnsIngestionPreview:
    arguments: dict[str, object] = {
        "program_id": "program-a",
        "operation_digest": OPERATION_DIGEST,
        "hostname_asset": ResearchAssetDnsIngestionAssetPreview(
            kind=ResearchAssetKind.HOSTNAME,
            canonical_value="www.example.test",
            already_known=False,
        ),
        "record_type": ResearchDnsRecordType.A,
        "address_assets": address_assets,
        "rejected_rows": rejected_rows,
    }
    arguments.update(overrides)
    return ResearchAssetDnsIngestionPreview(**arguments)  # type: ignore[arg-type]


class ResearchAssetDnsIngestionPreviewTests(unittest.TestCase):
    def test_a_valid_preview_constructs_and_never_claims_writes(self) -> None:
        preview = _preview()
        self.assertFalse(preview.observations_recorded)
        self.assertFalse(preview.relations_recorded)

    def test_claiming_observations_recorded_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "must not claim writes"):
            _preview(observations_recorded=True)

    def test_claiming_relations_recorded_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "must not claim writes"):
            _preview(relations_recorded=True)

    def test_an_invalid_operation_digest_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _preview(operation_digest="not-a-digest")

    def test_an_address_kind_hostname_asset_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _preview(
                hostname_asset=ResearchAssetDnsIngestionAssetPreview(
                    kind=ResearchAssetKind.IP_ADDRESS,
                    canonical_value="93.184.216.34",
                    already_known=False,
                )
            )


def _result(
    address_observations: tuple[ResearchAssetObservationRecord, ...] = (
        address_observation(),
    ),
    relations: tuple[ResearchAssetRelationRecord, ...] = (resolves_to_relation(),),
    **overrides: object,
) -> ResearchAssetDnsIngestionResult:
    arguments: dict[str, object] = {
        "program_id": "program-a",
        "operation_digest": OPERATION_DIGEST,
        "hostname_observation": hostname_observation(),
        "address_observations": address_observations,
        "relations": relations,
        "rejected_rows": (),
    }
    arguments.update(overrides)
    return ResearchAssetDnsIngestionResult(**arguments)  # type: ignore[arg-type]


class ResearchAssetDnsIngestionResultTests(unittest.TestCase):
    def test_a_valid_result_constructs(self) -> None:
        result = _result()
        self.assertEqual(
            result.hostname_observation.canonical_value, "www.example.test"
        )
        [address] = result.address_observations
        self.assertEqual(address.canonical_value, "93.184.216.34")
        [relation] = result.relations
        self.assertEqual(relation.related_value, "93.184.216.34")

    def test_zero_addresses_is_a_valid_result(self) -> None:
        result = _result(address_observations=(), relations=())
        self.assertEqual(result.address_observations, ())
        self.assertEqual(result.relations, ())

    def test_an_operator_authored_hostname_observation_is_rejected(self) -> None:
        forged = ResearchAssetObservationRecord(
            observation_id="hostname-observation",
            program_id="program-a",
            kind=ResearchAssetKind.HOSTNAME,
            canonical_value="www.example.test",
            provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
            note="",
            recorded_at=RECORDED,
        )
        with self.assertRaisesRegex(ResearchError, "not bound to this operation"):
            _result(hostname_observation=forged)

    def test_a_hostname_observation_bound_to_a_different_digest_is_rejected(
        self,
    ) -> None:
        with self.assertRaisesRegex(ResearchError, "not bound to this operation"):
            _result(hostname_observation=hostname_observation(digest=OTHER_DIGEST))

    def test_a_hostname_observation_from_a_different_program_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "different program"):
            _result(hostname_observation=hostname_observation(program_id="program-b"))

    def test_an_address_observation_of_the_wrong_kind_is_rejected(self) -> None:
        wrong_kind = ResearchAssetObservationRecord(
            observation_id="wrong-kind",
            program_id="program-a",
            kind=ResearchAssetKind.HOSTNAME,
            canonical_value="other.example.test",
            provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
            note="",
            recorded_at=RECORDED,
            source_operation_digest=OPERATION_DIGEST,
        )
        with self.assertRaises(ResearchError):
            _result(
                address_observations=(wrong_kind,), relations=(resolves_to_relation(),)
            )

    def test_relation_count_must_match_address_observation_count(self) -> None:
        with self.assertRaisesRegex(ResearchError, "one relation per accepted address"):
            _result(
                address_observations=(address_observation(),),
                relations=(),
            )

    def test_a_relation_targeting_an_unlisted_address_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "ingested address"):
            _result(
                address_observations=(address_observation(),),
                relations=(resolves_to_relation(related_value="203.0.113.9"),),
            )

    def test_a_relation_not_sourcing_the_hostname_is_rejected(self) -> None:
        wrong_source = ResearchAssetRelationRecord(
            relation_id="relation-wrong-source",
            program_id="program-a",
            source_kind=ResearchAssetKind.HOSTNAME,
            source_value="other.example.test",
            related_kind=ResearchAssetKind.IP_ADDRESS,
            related_value="93.184.216.34",
            kind=ResearchAssetRelationKind.RESOLVES_TO,
            provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
            note="",
            recorded_at=RECORDED,
            source_operation_digest=OPERATION_DIGEST,
        )
        with self.assertRaisesRegex(ResearchError, "queried hostname"):
            _result(relations=(wrong_source,))

    def test_a_relation_bound_to_a_different_digest_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "not bound to this operation"):
            _result(relations=(resolves_to_relation(digest=OTHER_DIGEST),))


if __name__ == "__main__":
    unittest.main()
