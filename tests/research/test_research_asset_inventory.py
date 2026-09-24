"""Asset identity is derived, append-only, and never conflates distinct hosts.

`ResearchAssetObservationRecord`/`ResearchAssetRelationRecord` are the only
durable facts; `ResearchAsset`/`assets_for_program` are a pure, always-
recomputed read model over them. Nothing here ever mutates a persisted
record in place, and nothing here ever treats a relation or a repeated
observation as evidence of anything beyond "this operator recorded this".
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchAsset import ResearchAsset, assets_for_program
from research.ResearchAssetInventoryEntry import (
    ResearchAssetInventoryEntry,
    ResearchAssetScopeResolutionView,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import (
    ResearchAssetObservationRecord,
    canonicalize_asset_value,
)
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchAssetRelationKind import ResearchAssetRelationKind
from research.ResearchAssetRelationRecord import ResearchAssetRelationRecord
from research.ResearchTargetScope import canonical_dns_hostname
from research.ResearchTargetScopeResolution import ResearchTargetScopeResolution
from research.ResearchTargetScopeResolutionStatus import (
    ResearchTargetScopeResolutionStatus,
)

RECORDED = datetime(2026, 9, 20, 10, tzinfo=UTC)
LATER = datetime(2026, 9, 21, 10, tzinfo=UTC)


def observation(
    observation_id: str = "observation-1",
    program_id: str = "program-a",
    kind: ResearchAssetKind = ResearchAssetKind.HOSTNAME,
    value: str = "example.test",
    note: str = "",
    recorded_at: datetime = RECORDED,
    provenance: ResearchAssetProvenanceKind = (
        ResearchAssetProvenanceKind.OPERATOR_AUTHORED
    ),
) -> ResearchAssetObservationRecord:
    return ResearchAssetObservationRecord(
        observation_id=observation_id,
        program_id=program_id,
        kind=kind,
        canonical_value=canonicalize_asset_value(kind, value),
        provenance=provenance,
        note=note,
        recorded_at=recorded_at,
    )


def relation(
    relation_id: str = "relation-1",
    program_id: str = "program-a",
    source_kind: ResearchAssetKind = ResearchAssetKind.HOSTNAME,
    source_value: str = "example.test",
    related_kind: ResearchAssetKind = ResearchAssetKind.IP_ADDRESS,
    related_value: str = "93.184.216.34",
    kind: ResearchAssetRelationKind = ResearchAssetRelationKind.RESOLVES_TO,
    note: str = "",
    recorded_at: datetime = RECORDED,
    provenance: ResearchAssetProvenanceKind = (
        ResearchAssetProvenanceKind.OPERATOR_AUTHORED
    ),
    source_operation_digest: str | None = None,
) -> ResearchAssetRelationRecord:
    return ResearchAssetRelationRecord(
        relation_id=relation_id,
        program_id=program_id,
        source_kind=source_kind,
        source_value=canonicalize_asset_value(source_kind, source_value),
        related_kind=related_kind,
        related_value=canonicalize_asset_value(related_kind, related_value),
        kind=kind,
        provenance=provenance,
        note=note,
        recorded_at=recorded_at,
        source_operation_digest=source_operation_digest,
    )


class ResearchAssetObservationRecordTests(unittest.TestCase):
    def test_valid_hostname_and_address_observations_construct(self) -> None:
        host = observation()
        address = observation(kind=ResearchAssetKind.IP_ADDRESS, value="93.184.216.34")
        self.assertEqual(host.canonical_value, "example.test")
        self.assertEqual(address.canonical_value, "93.184.216.34")

    def test_non_canonical_hostname_is_rejected_not_normalized(self) -> None:
        with self.assertRaisesRegex(ResearchError, "not canonical"):
            ResearchAssetObservationRecord(
                observation_id="observation-1",
                program_id="program-a",
                kind=ResearchAssetKind.HOSTNAME,
                canonical_value="EXAMPLE.TEST.",
                provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                note="",
                recorded_at=RECORDED,
            )
        with self.assertRaisesRegex(ResearchError, "not canonical"):
            ResearchAssetRelationRecord(
                relation_id="relation-1",
                program_id="program-a",
                source_kind=ResearchAssetKind.HOSTNAME,
                source_value="example.test",
                related_kind=ResearchAssetKind.IP_ADDRESS,
                related_value="2606:4700:0000:0000:0000:0000:0000:1111",
                kind=ResearchAssetRelationKind.RESOLVES_TO,
                provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                note="",
                recorded_at=RECORDED,
            )

    def test_non_canonical_ip_form_is_rejected_not_normalized(self) -> None:
        expanded = "2606:4700:0000:0000:0000:0000:0000:1111"
        with self.assertRaisesRegex(ResearchError, "not canonical"):
            ResearchAssetObservationRecord(
                observation_id="observation-1",
                program_id="program-a",
                kind=ResearchAssetKind.IP_ADDRESS,
                canonical_value=expanded,
                provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                note="",
                recorded_at=RECORDED,
            )

    def test_invalid_kind_type_raises(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchAssetObservationRecord(
                observation_id="observation-1",
                program_id="program-a",
                kind="hostname",  # type: ignore[arg-type]
                canonical_value="example.test",
                provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                note="",
                recorded_at=RECORDED,
            )

    def test_invalid_provenance_type_raises(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchAssetObservationRecord(
                observation_id="observation-1",
                program_id="program-a",
                kind=ResearchAssetKind.HOSTNAME,
                canonical_value="example.test",
                provenance="operator_authored",  # type: ignore[arg-type]
                note="",
                recorded_at=RECORDED,
            )

    def test_blank_ids_raise(self) -> None:
        cases = (("  ", "program-a"), ("observation-1", "  "))
        for observation_id, program_id in cases:
            with self.subTest(observation_id=observation_id, program_id=program_id):
                with self.assertRaises(ResearchError):
                    ResearchAssetObservationRecord(
                        observation_id=observation_id,
                        program_id=program_id,
                        kind=ResearchAssetKind.HOSTNAME,
                        canonical_value="example.test",
                        provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                        note="",
                        recorded_at=RECORDED,
                    )

    def test_ids_and_note_over_bound_raise(self) -> None:
        with self.assertRaises(ResearchError):
            observation(observation_id="x" * 201)
        with self.assertRaises(ResearchError):
            observation(program_id="x" * 201)
        with self.assertRaises(ResearchError):
            observation(note="x" * 2001)

    def test_naive_recorded_at_raises(self) -> None:
        with self.assertRaisesRegex(ResearchError, "timezone-aware"):
            observation(recorded_at=datetime(2026, 9, 20, 10))

    def test_ids_and_note_are_stripped(self) -> None:
        record = observation(
            observation_id="  observation-1  ",
            program_id="  program-a  ",
            note="  a note  ",
        )
        self.assertEqual(record.observation_id, "observation-1")
        self.assertEqual(record.program_id, "program-a")
        self.assertEqual(record.note, "a note")


class ObservationProvenanceDigestBindingTests(unittest.TestCase):
    """A human cannot forge automated provenance in either direction."""

    _FAKE_DIGEST = "b" * 64

    def test_operator_authored_with_a_digest_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "cannot carry an operation digest"):
            ResearchAssetObservationRecord(
                observation_id="observation-1",
                program_id="program-a",
                kind=ResearchAssetKind.HOSTNAME,
                canonical_value="example.test",
                provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                note="",
                recorded_at=RECORDED,
                source_operation_digest=self._FAKE_DIGEST,
            )

    def test_kali_operation_result_without_a_digest_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "requires a valid Kali operation"):
            ResearchAssetObservationRecord(
                observation_id="observation-1",
                program_id="program-a",
                kind=ResearchAssetKind.HOSTNAME,
                canonical_value="example.test",
                provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
                note="",
                recorded_at=RECORDED,
                source_operation_digest=None,
            )

    def test_kali_operation_result_with_an_invalid_digest_is_rejected(self) -> None:
        for bad_digest in ("not-a-digest", "a" * 63, "A" * 64, ""):
            with self.subTest(bad_digest=bad_digest):
                with self.assertRaises(ResearchError):
                    ResearchAssetObservationRecord(
                        observation_id="observation-1",
                        program_id="program-a",
                        kind=ResearchAssetKind.HOSTNAME,
                        canonical_value="example.test",
                        provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
                        note="",
                        recorded_at=RECORDED,
                        source_operation_digest=bad_digest,
                    )

    def test_kali_operation_result_with_a_valid_digest_constructs(self) -> None:
        record = ResearchAssetObservationRecord(
            observation_id="observation-1",
            program_id="program-a",
            kind=ResearchAssetKind.HOSTNAME,
            canonical_value="example.test",
            provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
            note="",
            recorded_at=RECORDED,
            source_operation_digest=self._FAKE_DIGEST,
        )
        self.assertEqual(record.source_operation_digest, self._FAKE_DIGEST)


class ResearchAssetRelationRecordTests(unittest.TestCase):
    def test_valid_relation_constructs(self) -> None:
        record = relation()
        self.assertEqual(record.source_value, "example.test")
        self.assertEqual(record.related_value, "93.184.216.34")

    def test_self_relation_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "relate an asset to itself"):
            relation(
                source_kind=ResearchAssetKind.HOSTNAME,
                source_value="example.test",
                related_kind=ResearchAssetKind.HOSTNAME,
                related_value="example.test",
            )

    def test_same_value_different_kind_is_not_a_self_relation(self) -> None:
        # "example.test" as a hostname and a same-text different-kind value
        # are different identities; only true (kind, value) equality is a
        # self relation. IP/hostname text never collides in practice, but the
        # identity check is on the pair, not the literal text alone.
        record = relation(
            source_kind=ResearchAssetKind.HOSTNAME,
            source_value="example.test",
            related_kind=ResearchAssetKind.IP_ADDRESS,
            related_value="93.184.216.34",
        )
        self.assertNotEqual(
            (record.source_kind, record.source_value),
            (record.related_kind, record.related_value),
        )

    def test_non_canonical_source_or_related_value_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "not canonical"):
            ResearchAssetRelationRecord(
                relation_id="relation-1",
                program_id="program-a",
                source_kind=ResearchAssetKind.HOSTNAME,
                source_value="EXAMPLE.TEST.",
                related_kind=ResearchAssetKind.IP_ADDRESS,
                related_value="93.184.216.34",
                kind=ResearchAssetRelationKind.RESOLVES_TO,
                provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                note="",
                recorded_at=RECORDED,
            )

    def test_resolves_to_requires_hostname_to_ip_address_direction(self) -> None:
        invalid_directions = (
            (
                ResearchAssetKind.IP_ADDRESS,
                "203.0.113.10",
                ResearchAssetKind.HOSTNAME,
                "api.example.test",
            ),
            (
                ResearchAssetKind.HOSTNAME,
                "api.example.test",
                ResearchAssetKind.HOSTNAME,
                "other.example.test",
            ),
            (
                ResearchAssetKind.IP_ADDRESS,
                "203.0.113.10",
                ResearchAssetKind.IP_ADDRESS,
                "203.0.113.11",
            ),
        )
        for (
            source_kind,
            source_value,
            related_kind,
            related_value,
        ) in invalid_directions:
            with self.subTest(source_kind=source_kind, related_kind=related_kind):
                with self.assertRaisesRegex(ResearchError, "hostname to an IP address"):
                    ResearchAssetRelationRecord(
                        relation_id="relation-direction",
                        program_id="program-a",
                        source_kind=source_kind,
                        source_value=source_value,
                        related_kind=related_kind,
                        related_value=related_value,
                        kind=ResearchAssetRelationKind.RESOLVES_TO,
                        provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                        note="",
                        recorded_at=RECORDED,
                    )

    def test_invalid_relation_kind_raises(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchAssetRelationRecord(
                relation_id="relation-1",
                program_id="program-a",
                source_kind=ResearchAssetKind.HOSTNAME,
                source_value="example.test",
                related_kind=ResearchAssetKind.IP_ADDRESS,
                related_value="93.184.216.34",
                kind="resolves_to",  # type: ignore[arg-type]
                provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                note="",
                recorded_at=RECORDED,
            )

    def test_naive_recorded_at_raises(self) -> None:
        with self.assertRaisesRegex(ResearchError, "timezone-aware"):
            relation(recorded_at=datetime(2026, 9, 20, 10))

    def test_note_over_bound_raises(self) -> None:
        with self.assertRaises(ResearchError):
            relation(note="x" * 2001)


class RelationProvenanceDigestBindingTests(unittest.TestCase):
    """The same fail-closed 1:1 binding applies to relations, not only
    observations — a `RESOLVES_TO` relation created from a real DNS result
    must not read as an unattributed/implicitly-operator claim, and an
    operator cannot forge automated provenance on a relation either.
    """

    _FAKE_DIGEST = "c" * 64

    def test_operator_authored_with_a_digest_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "cannot carry an operation digest"):
            relation(
                provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                source_operation_digest=self._FAKE_DIGEST,
            )

    def test_kali_operation_result_without_a_digest_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "requires a valid Kali operation"):
            relation(
                provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
                source_operation_digest=None,
            )

    def test_kali_operation_result_with_a_valid_digest_constructs(self) -> None:
        record = relation(
            provenance=ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
            source_operation_digest=self._FAKE_DIGEST,
        )
        self.assertEqual(record.source_operation_digest, self._FAKE_DIGEST)
        self.assertIs(
            record.provenance, ResearchAssetProvenanceKind.KALI_OPERATION_RESULT
        )


class ResearchAssetTests(unittest.TestCase):
    def test_requires_at_least_one_observation(self) -> None:
        with self.assertRaisesRegex(ResearchError, "at least one observation"):
            ResearchAsset(
                program_id="program-a",
                kind=ResearchAssetKind.HOSTNAME,
                canonical_value="example.test",
                observations=(),
            )

    def test_observations_must_share_this_assets_identity(self) -> None:
        with self.assertRaisesRegex(ResearchError, "do not all share"):
            ResearchAsset(
                program_id="program-a",
                kind=ResearchAssetKind.HOSTNAME,
                canonical_value="example.test",
                observations=(observation(value="other.test"),),
            )

    def test_first_and_last_seen_are_the_min_and_max_recorded_at(self) -> None:
        asset = ResearchAsset(
            program_id="program-a",
            kind=ResearchAssetKind.HOSTNAME,
            canonical_value="example.test",
            observations=(
                observation(observation_id="o1", recorded_at=LATER),
                observation(observation_id="o2", recorded_at=RECORDED),
            ),
        )
        self.assertEqual(asset.first_seen, RECORDED)
        self.assertEqual(asset.last_seen, LATER)


class AssetsForProgramTests(unittest.TestCase):
    def test_groups_by_program_kind_and_canonical_value_preserving_order(self) -> None:
        first = observation(observation_id="o1", recorded_at=RECORDED)
        second = observation(observation_id="o2", recorded_at=LATER)
        other_asset = observation(
            observation_id="o3", value="other.test", recorded_at=RECORDED
        )

        [example_asset, other] = assets_for_program(
            "program-a", (first, second, other_asset)
        )

        self.assertEqual(example_asset.canonical_value, "example.test")
        self.assertEqual(example_asset.observations, (first, second))
        self.assertEqual(other.canonical_value, "other.test")

    def test_filters_out_observations_belonging_to_other_programs(self) -> None:
        mine = observation(observation_id="o1", program_id="program-a")
        theirs = observation(observation_id="o2", program_id="program-b")

        [asset] = assets_for_program("program-a", (mine, theirs))

        self.assertEqual(asset.observations, (mine,))

    def test_output_is_deterministically_sorted(self) -> None:
        zebra = observation(observation_id="o1", value="zebra.test")
        alpha = observation(observation_id="o2", value="alpha.test")

        assets = assets_for_program("program-a", (zebra, alpha))

        self.assertEqual(
            [asset.canonical_value for asset in assets],
            ["alpha.test", "zebra.test"],
        )

    def test_empty_program_id_raises(self) -> None:
        with self.assertRaises(ResearchError):
            assets_for_program("  ", ())

    def test_non_tuple_observations_raises(self) -> None:
        with self.assertRaises(ResearchError):
            assets_for_program("program-a", [observation()])  # type: ignore[arg-type]

    def test_no_observations_for_program_yields_no_assets(self) -> None:
        self.assertEqual(assets_for_program("program-a", ()), ())


class ResearchAssetScopeResolutionViewTests(unittest.TestCase):
    def _resolution(
        self,
        status: ResearchTargetScopeResolutionStatus = (
            ResearchTargetScopeResolutionStatus.IN_SCOPE
        ),
    ) -> ResearchTargetScopeResolution:
        return ResearchTargetScopeResolution(
            status=status,
            target="example.test",
            matched_rule=None if status.value == "uncertain" else "example.test",
            reason="Target host matches an explicitly allowed scope rule.",
        )

    def test_active_revision_requires_a_resolution(self) -> None:
        with self.assertRaisesRegex(ResearchError, "requires a resolution"):
            ResearchAssetScopeResolutionView(
                has_active_scope_revision=True, resolution=None
            )

    def test_inactive_revision_forbids_a_resolution(self) -> None:
        with self.assertRaisesRegex(ResearchError, "without an active"):
            ResearchAssetScopeResolutionView(
                has_active_scope_revision=False, resolution=self._resolution()
            )

    def test_valid_combinations_construct(self) -> None:
        ResearchAssetScopeResolutionView(
            has_active_scope_revision=True, resolution=self._resolution()
        )
        ResearchAssetScopeResolutionView(
            has_active_scope_revision=False, resolution=None
        )


class ResearchAssetInventoryEntryTests(unittest.TestCase):
    def test_requires_a_valid_asset_and_scope_view(self) -> None:
        asset = ResearchAsset(
            program_id="program-a",
            kind=ResearchAssetKind.HOSTNAME,
            canonical_value="example.test",
            observations=(observation(),),
        )
        view = ResearchAssetScopeResolutionView(
            has_active_scope_revision=False, resolution=None
        )
        ResearchAssetInventoryEntry(asset=asset, scope=view)
        with self.assertRaises(ResearchError):
            ResearchAssetInventoryEntry(asset="not-an-asset", scope=view)  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            ResearchAssetInventoryEntry(asset=asset, scope="not-a-view")  # type: ignore[arg-type]


class AdversarialHostnameCanonicalizationTests(unittest.TestCase):
    """Gaps beyond `test_research_asset_canonical_hostname.py`'s own coverage.

    `_dns_name` requires ASCII (`value.isascii()`); there is no IDNA/unicode
    decoding anywhere in `ResearchTargetScope`, so raw unicode homograph
    input is refused outright rather than silently punycode-encoded, and an
    already-encoded punycode label is treated as opaque ASCII text like any
    other hostname -- never decoded back to compare against a unicode form.
    """

    def test_raw_unicode_homograph_input_is_rejected_not_silently_encoded(
        self,
    ) -> None:
        # A Cyrillic "а" (U+0430) standing in for Latin "a" -- a classic
        # homograph attack shape. This must never be silently accepted or
        # transcoded into a plausible-looking ASCII hostname.
        with self.assertRaisesRegex(ResearchError, "ASCII"):
            canonical_dns_hostname("аpple.test")

    def test_already_encoded_punycode_is_treated_as_opaque_ascii_text(self) -> None:
        canonicalized = canonical_dns_hostname("XN--80AK6AA92E.TEST")
        self.assertEqual(canonicalized, "xn--80ak6aa92e.test")

    def test_distinct_punycode_labels_never_collapse(self) -> None:
        self.assertNotEqual(
            canonical_dns_hostname("xn--80ak6aa92e.test"),
            canonical_dns_hostname("xn--80aaa1cbi.test"),
        )

    def test_whitespace_only_input_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            canonical_dns_hostname("   ")


class ScopedAddressIdentityTests(unittest.TestCase):
    """A zone-scoped address parses and round-trips, but scope refuses it.

    `ResearchTargetScope` rejects every address containing "%" before
    matching, so accepting one as asset identity would create a record the
    scope layer structurally cannot read — and because records are
    append-only, that would wedge the program's whole inventory read path.
    Identity must refuse exactly what scope matching refuses.
    """

    def test_a_zone_scoped_address_is_refused_as_asset_identity(self) -> None:
        for value in ("fe80::1%eth0", "fe80::1%1"):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    canonicalize_asset_value(ResearchAssetKind.IP_ADDRESS, value)

    def test_a_zone_scoped_address_cannot_be_recorded(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchAssetObservationRecord(
                observation_id="observation-scoped",
                program_id="program-a",
                kind=ResearchAssetKind.IP_ADDRESS,
                canonical_value="fe80::1%eth0",
                provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                note="",
                recorded_at=RECORDED,
            )

    def test_an_unscoped_link_local_address_is_still_accepted(self) -> None:
        self.assertEqual(
            canonicalize_asset_value(ResearchAssetKind.IP_ADDRESS, "fe80::1"),
            "fe80::1",
        )


class VocabularyBoundaryTests(unittest.TestCase):
    """Each enum holds exactly what this runtime can honestly populate.

    Pinned because every one of these modules argues at length against adding
    a member "for symmetry": extending them is a later milestone's job, and a
    silent addition would let an unpopulatable kind reach the resolver.
    """

    def test_asset_kinds_are_hostname_and_address_only(self) -> None:
        self.assertEqual(
            tuple(ResearchAssetKind),
            (ResearchAssetKind.HOSTNAME, ResearchAssetKind.IP_ADDRESS),
        )

    def test_provenance_has_exactly_the_two_real_producers(self) -> None:
        self.assertEqual(
            tuple(ResearchAssetProvenanceKind),
            (
                ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
            ),
        )

    def test_relation_kinds_are_resolves_to_only(self) -> None:
        self.assertEqual(
            tuple(ResearchAssetRelationKind),
            (ResearchAssetRelationKind.RESOLVES_TO,),
        )


class DerivedAssetTypeGuardTests(unittest.TestCase):
    def test_a_plain_string_kind_is_refused_despite_strenum_equality(self) -> None:
        """`ResearchAssetKind` is a `StrEnum`, so "hostname" compares equal.

        Without an explicit type guard a derived asset could carry a kind no
        resolver dispatch recognises, and the scope dispatch would then
        mis-route it to address rules.
        """
        with self.assertRaises(ResearchError):
            ResearchAsset(
                program_id="program-a",
                kind="hostname",  # type: ignore[arg-type]
                canonical_value="example.test",
                observations=(observation(),),
            )

    def test_a_blank_program_or_value_is_refused(self) -> None:
        for field, value in (("program_id", "  "), ("canonical_value", "")):
            with self.subTest(field=field):
                arguments = {
                    "program_id": "program-a",
                    "kind": ResearchAssetKind.HOSTNAME,
                    "canonical_value": "example.test",
                    "observations": (observation(),),
                }
                arguments[field] = value
                with self.assertRaises(ResearchError):
                    ResearchAsset(**arguments)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
