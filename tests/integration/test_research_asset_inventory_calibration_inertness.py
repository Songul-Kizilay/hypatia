"""Recording asset inventory data must never move a single calibration result.

The Bug Bounty asset inventory is an entirely separate, program-scoped store
from a research run's evidence/claim record. This is the milestone's central
safety claim, proved the same way v0.3.405's `EvidenceTypeInertnessTests`
proved `evidence_type` inertness: build two otherwise-identical fixtures that
disagree only in how much has been recorded in the asset inventory store, and
require the exact same `ResearchClaimCalibration` object back -- full-object
equality, not a spot check.

Non-vacuousness of the equality assertion itself (proving this test is capable
of catching a real coupling, not just always trivially true) was verified out
of band: `ResearchClaimCalibrator.calibrate` was temporarily edited to accept
and branch on asset-inventory data, this exact differential fixture was
re-run and observed to fail, and the edit was then reverted with `git diff`
confirmed clean. See the milestone report for that transcript; nothing about
that temporary edit is present in this file or committed anywhere.
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

from knowledge.Chunk import Chunk
from research.JsonFileResearchAssetInventoryStore import (
    JsonFileResearchAssetInventoryStore,
    ResearchAssetInventoryDocument,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import (
    ResearchAssetObservationRecord,
    canonicalize_asset_value,
)
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchAssetRelationKind import ResearchAssetRelationKind
from research.ResearchAssetRelationRecord import ResearchAssetRelationRecord
from research.ResearchClaimCalibrator import ResearchClaimCalibrator
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource

QUESTION = "Is admin.example.test in the authorized bug bounty program?"
FETCHED = datetime(2026, 9, 20, tzinfo=UTC)


class AssetInventoryCalibrationInertnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

    def _calibration(self, record_asset_data: bool):
        """Build one calibrated claim; optionally litter an unrelated asset store.

        The run fixture (question, sources, evidence, assessments, claim) is
        byte-identical between the two calls -- fixed IDs and a fixed clock
        guarantee that. The only thing that differs is whether an entirely
        separate `JsonFileResearchAssetInventoryStore` -- sharing this run's
        `run_id` as its `program_id`, the most adversarial coincidence
        possible -- has observations and a relation recorded into it.
        """
        manager = ResearchRunManager(
            clock=lambda: FETCHED,
            id_factory=lambda: "run-1",
            evidence_id_factory=iter(
                f"evidence-{number}" for number in range(1, 3)
            ).__next__,
            assessment_id_factory=iter(
                f"assessment-{number}" for number in range(1, 3)
            ).__next__,
            claim_id_factory=lambda: "claim-1",
        )
        run_id = manager.create(QUESTION).run_id
        evidence_ids = []
        for slug in ("a", "b"):
            document_id = f"document-{slug}"
            manager.add_source(
                run_id,
                ResearchSource(
                    url=f"https://example.test/inertness-{slug}",
                    title=f"Source {slug}",
                    content="admin.example.test appears in the published scope.",
                    content_type="text/plain",
                    fetched_at=FETCHED,
                ),
                document_id,
            )
            manager.add_evidence(
                run_id,
                Chunk(
                    document_id,
                    0,
                    "admin.example.test appears in the published scope.",
                    chunk_id=f"chunk-{slug}",
                ),
                "Directly relevant.",
            )
            evidence_id = manager.get(run_id).evidence[-1].evidence_id
            manager.record_source_assessment(
                run_id,
                document_id,
                [evidence_id],
                "Assessed for the inertness test.",
                None,
                "medium",
                "useful",
                "direct",
                "independent",
                "normal",
            )
            evidence_ids.append(evidence_id)
        manager.record_claim(
            run_id,
            evidence_ids,
            "admin.example.test is in the authorized bug bounty program.",
            "strong_evidence",
            "high",
        )

        if record_asset_data:
            store = JsonFileResearchAssetInventoryStore(
                Path(self.temporary_directory.name) / "asset_inventory.json"
            )
            document = store.load()
            self.assertEqual(document.observations, ())
            self.assertEqual(document.relations, ())
            self._litter_asset_inventory(store, program_id=run_id)

        run = manager.get(run_id)
        [calibration] = ResearchClaimCalibrator().calibrate(run)
        return calibration

    @staticmethod
    def _litter_asset_inventory(
        store: JsonFileResearchAssetInventoryStore, program_id: str
    ) -> None:
        """Record a generous, varied set of observations and one relation.

        Deliberately reuses hostnames/addresses mentioned in the run's own
        source content and question -- if any code path anywhere read this
        store keyed by `program_id`/text overlap, this is the fixture most
        likely to expose it.
        """
        observations = []
        for index, (kind, value) in enumerate(
            (
                (ResearchAssetKind.HOSTNAME, "admin.example.test"),
                (ResearchAssetKind.HOSTNAME, "ADMIN.EXAMPLE.TEST."),
                (ResearchAssetKind.HOSTNAME, "api.example.test"),
                (ResearchAssetKind.IP_ADDRESS, "93.184.216.34"),
                (ResearchAssetKind.IP_ADDRESS, "2606:4700::1111"),
            )
        ):
            observations.append(
                ResearchAssetObservationRecord(
                    observation_id=f"observation-{index}",
                    program_id=program_id,
                    kind=kind,
                    canonical_value=canonicalize_asset_value(kind, value),
                    provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
                    note="Recorded for the inertness fixture.",
                    recorded_at=FETCHED + timedelta(minutes=index),
                )
            )
        relation = ResearchAssetRelationRecord(
            relation_id="relation-1",
            program_id=program_id,
            source_kind=ResearchAssetKind.HOSTNAME,
            source_value="admin.example.test",
            related_kind=ResearchAssetKind.IP_ADDRESS,
            related_value="93.184.216.34",
            kind=ResearchAssetRelationKind.RESOLVES_TO,
            provenance=ResearchAssetProvenanceKind.OPERATOR_AUTHORED,
            note="",
            recorded_at=FETCHED + timedelta(minutes=10),
        )
        document = store.load()
        store.save(
            ResearchAssetInventoryDocument(
                observations=(*document.observations, *observations),
                relations=(*document.relations, relation),
            )
        )

    def test_recording_asset_data_never_changes_the_calibration_result(self) -> None:
        without_assets = self._calibration(record_asset_data=False)
        with_assets = self._calibration(record_asset_data=True)

        self.assertEqual(without_assets, with_assets)

    def test_recording_asset_data_never_changes_the_evidence_support_profile(
        self,
    ) -> None:
        without_assets = self._calibration(record_asset_data=False)
        with_assets = self._calibration(record_asset_data=True)

        self.assertEqual(without_assets.profile, with_assets.profile)
        self.assertEqual(without_assets.verdict, with_assets.verdict)
        self.assertEqual(without_assets.warnings, with_assets.warnings)


if __name__ == "__main__":
    unittest.main()
