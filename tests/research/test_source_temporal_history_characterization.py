"""Characterize the read-only temporal-history contract before implementation."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.Exceptions import ResearchError
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceRevalidationOutcome import ResearchSourceRevalidationOutcome
from research.ResearchSourceTemporalHistory import (
    ResearchSourceTemporalHistoryShape,
    temporal_history_for,
)

RESOURCE = "https://example.test/advisory"
FIRST = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


class SourceTemporalHistoryCharacterizationTests(unittest.TestCase):
    def test_one_observation_does_not_establish_external_state(self) -> None:
        history = temporal_history_for(
            RESOURCE,
            observations=(("run-a", "observation-a", FIRST),),
            relations=(),
        )

        self.assertEqual(history.shape, ResearchSourceTemporalHistoryShape.SINGLE)
        self.assertEqual(history.latest_recorded_observation_id, "observation-a")
        self.assertEqual(history.relation_ids, ())
        self.assertIn("external_state_unknown", history.limitations)

    def test_linear_history_preserves_each_exact_relation_outcome(self) -> None:
        history = temporal_history_for(
            RESOURCE,
            observations=(
                ("run-a", "observation-a", FIRST),
                ("run-b", "observation-b", FIRST + timedelta(minutes=1)),
                ("run-c", "observation-c", FIRST + timedelta(minutes=2)),
            ),
            relations=(
                (
                    "relation-ab",
                    "run-a",
                    "observation-a",
                    "run-b",
                    "observation-b",
                    ResearchSourceRevalidationOutcome.CONTENT_UNCHANGED,
                ),
                (
                    "relation-bc",
                    "run-b",
                    "observation-b",
                    "run-c",
                    "observation-c",
                    ResearchSourceRevalidationOutcome.CONTENT_CHANGED,
                ),
            ),
        )

        self.assertEqual(history.shape, ResearchSourceTemporalHistoryShape.LINEAR)
        self.assertEqual(history.latest_recorded_observation_id, "observation-c")
        self.assertEqual(
            [(edge.relation_id, edge.outcome) for edge in history.relations],
            [
                ("relation-ab", ResearchSourceRevalidationOutcome.CONTENT_UNCHANGED),
                ("relation-bc", ResearchSourceRevalidationOutcome.CONTENT_CHANGED),
            ],
        )

    def test_branch_and_equal_timestamps_remain_ambiguous(self) -> None:
        history = temporal_history_for(
            RESOURCE,
            observations=(
                ("run-a", "observation-a", FIRST),
                ("run-b", "observation-b", FIRST + timedelta(minutes=1)),
                ("run-c", "observation-c", FIRST + timedelta(minutes=1)),
            ),
            relations=(
                (
                    "relation-ab",
                    "run-a",
                    "observation-a",
                    "run-b",
                    "observation-b",
                    ResearchSourceRevalidationOutcome.CONTENT_UNCHANGED,
                ),
                (
                    "relation-ac",
                    "run-a",
                    "observation-a",
                    "run-c",
                    "observation-c",
                    ResearchSourceRevalidationOutcome.CONTENT_CHANGED,
                ),
            ),
        )

        self.assertEqual(history.shape, ResearchSourceTemporalHistoryShape.BRANCHED)
        self.assertIsNone(history.latest_recorded_observation_id)
        self.assertIn("latest_observation_time_ambiguous", history.limitations)

    def test_disconnected_history_does_not_fabricate_a_relation(self) -> None:
        history = temporal_history_for(
            RESOURCE,
            observations=(
                ("run-a", "observation-a", FIRST),
                ("run-b", "observation-b", FIRST + timedelta(minutes=1)),
            ),
            relations=(),
        )

        self.assertEqual(history.shape, ResearchSourceTemporalHistoryShape.DISCONNECTED)
        self.assertEqual(history.relations, ())
        self.assertIn("explicit_relation_history_incomplete", history.limitations)

    def test_incomplete_observation_identity_never_invents_chronology(self) -> None:
        history = temporal_history_for(
            RESOURCE,
            observations=(("run-a", "observation-a", FIRST),),
            relations=(),
            incomplete_limitations=("canonical_observation_identity_unrecorded",),
        )

        self.assertEqual(history.shape, ResearchSourceTemporalHistoryShape.INCOMPLETE)
        self.assertIsNone(history.latest_recorded_observation_id)
        self.assertIn("canonical_observation_identity_unrecorded", history.limitations)

    def test_dangling_or_malformed_relations_fail_closed(self) -> None:
        observations = (
            ("run-a", "observation-a", FIRST),
            ("run-b", "observation-b", FIRST + timedelta(minutes=1)),
        )
        cases = (
            (
                "dangling",
                (
                    "relation-a",
                    "run-a",
                    "observation-a",
                    "run-c",
                    "observation-c",
                    ResearchSourceRevalidationOutcome.CONTENT_UNCHANGED,
                ),
            ),
            (
                "self",
                (
                    "relation-a",
                    "run-a",
                    "observation-a",
                    "run-a",
                    "observation-a",
                    ResearchSourceRevalidationOutcome.CONTENT_UNCHANGED,
                ),
            ),
        )
        for label, relation in cases:
            with self.subTest(label=label):
                with self.assertRaisesRegex(ResearchError, "Temporal history"):
                    temporal_history_for(
                        RESOURCE, observations=observations, relations=(relation,)
                    )

    def test_projection_is_deterministic_without_relation_insertion_order(self) -> None:
        observations = (
            ("run-a", "observation-a", FIRST),
            ("run-b", "observation-b", FIRST + timedelta(minutes=1)),
            ("run-c", "observation-c", FIRST + timedelta(minutes=2)),
        )
        relations = (
            (
                "relation-bc",
                "run-b",
                "observation-b",
                "run-c",
                "observation-c",
                ResearchSourceRevalidationOutcome.CONTENT_CHANGED,
            ),
            (
                "relation-ab",
                "run-a",
                "observation-a",
                "run-b",
                "observation-b",
                ResearchSourceRevalidationOutcome.CONTENT_UNCHANGED,
            ),
        )

        first = temporal_history_for(
            RESOURCE, observations=observations, relations=relations
        )
        second = temporal_history_for(
            RESOURCE, observations=observations, relations=tuple(reversed(relations))
        )

        self.assertEqual(first, second)
        self.assertEqual(first.relation_ids, ("relation-ab", "relation-bc"))

    def test_manager_projection_survives_restart_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.json"
            manager = ResearchRunManager(
                JsonFileResearchRunStore(path),
                clock=lambda: FIRST,
                observation_id_factory=iter(
                    ("observation-a", "observation-b", "observation-other")
                ).__next__,
                revalidation_id_factory=lambda: "relation-ab",
            )
            first_run = manager.create("first")
            second_run = manager.create("second")
            for run, content, document, observed_at in (
                (first_run, "first content", "document-a", FIRST),
                (
                    second_run,
                    "second content",
                    "document-b",
                    FIRST + timedelta(minutes=1),
                ),
            ):
                manager.add_source(
                    run.run_id,
                    ResearchSource(
                        url=RESOURCE,
                        title="Advisory",
                        content=content,
                        content_type="text/plain",
                        fetched_at=observed_at,
                    ),
                    document,
                    requested_url=RESOURCE,
                )
            manager.record_source_revalidation(
                first_run.run_id, "observation-a", second_run.run_id, "observation-b"
            )
            manager.add_source(
                first_run.run_id,
                ResearchSource(
                    url="https://other.example.test/advisory",
                    title="Other advisory",
                    content="other content",
                    content_type="text/plain",
                    fetched_at=FIRST + timedelta(minutes=2),
                ),
                "document-other",
                requested_url="https://other.example.test/advisory",
            )
            persisted_before = path.read_text(encoding="utf-8")
            runs_before = tuple(manager.list())
            expected = manager.temporal_history(RESOURCE)
            self.assertEqual(path.read_text(encoding="utf-8"), persisted_before)
            self.assertEqual(tuple(manager.list()), runs_before)
            self.assertEqual(
                expected.observation_ids, ("observation-a", "observation-b")
            )

            restored = ResearchRunManager(
                JsonFileResearchRunStore(path), clock=lambda: FIRST
            )
            restored.load()

            self.assertEqual(restored.temporal_history(RESOURCE), expected)

    def test_legacy_identity_gap_is_rendered_as_incomplete_without_linking_it(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.json"
            manager = ResearchRunManager(
                JsonFileResearchRunStore(path),
                clock=lambda: FIRST,
                observation_id_factory=lambda: "observation-a",
            )
            run = manager.create("legacy")
            manager.add_source(
                run.run_id,
                ResearchSource(
                    url=RESOURCE,
                    title="Advisory",
                    content="recorded content",
                    content_type="text/plain",
                    fetched_at=FIRST,
                ),
                "document-a",
                requested_url=RESOURCE,
            )
            document = json.loads(path.read_text(encoding="utf-8"))
            document["schema_version"] = 17
            document.pop("source_revalidations")
            document["runs"][0]["sources"][0].pop("observation_id")
            path.write_text(json.dumps(document), encoding="utf-8")
            restored = ResearchRunManager(
                JsonFileResearchRunStore(path), clock=lambda: FIRST
            )
            restored.load()

            history = restored.temporal_history(RESOURCE)

        self.assertEqual(history.shape, ResearchSourceTemporalHistoryShape.INCOMPLETE)
        self.assertEqual(history.observation_ids, ())
        self.assertEqual(history.relations, ())

    def test_unrecorded_requested_resource_is_excluded_without_a_guess(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = ResearchRunManager(
                JsonFileResearchRunStore(Path(directory) / "runs.json"),
                clock=lambda: FIRST,
                observation_id_factory=lambda: "observation-a",
            )
            run = manager.create("legacy resource")
            manager.add_source(
                run.run_id,
                ResearchSource(
                    url=RESOURCE,
                    title="Advisory",
                    content="recorded content",
                    content_type="text/plain",
                    fetched_at=FIRST,
                ),
                "document-a",
            )

            with self.assertRaisesRegex(ResearchError, "at least one observation"):
                manager.temporal_history(RESOURCE)
