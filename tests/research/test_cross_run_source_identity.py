"""Cross-run source identity: URL is not document identity or observation.

A document is one immutable content version.  Each run's source record is that
run's own observation of it.  Two runs may share stored content; they never
share provenance, and a run never gains a fetch it did not perform.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import KnowledgeError, ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.JsonFileResearchSourceContentStore import (
    JsonFileResearchSourceContentStore,
)
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceContentRecord import ResearchSourceContentRecord
from research.ResearchSourceContentRestorer import ResearchSourceContentRestorer
from research.ResearchSourceRecord import ResearchSourceRecord

URL = "https://example.test/advisory"
FIRST = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
LATER = FIRST + timedelta(days=3)
TEXT_A = "Version A says the flaw is unpatched."
TEXT_B = "Version B says a patch is available."


def fetched(content: str, fetched_at: datetime = FIRST) -> ResearchSource:
    return ResearchSource(
        url=URL,
        title="Advisory",
        content=content,
        content_type="text/plain",
        fetched_at=fetched_at,
    )


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CrossRunSourceIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.knowledge = KnowledgeEngine()
        self.runs = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json"),
            clock=lambda: LATER + timedelta(days=1),
        )
        self.content = JsonFileResearchSourceContentStore(self.root / "content.json")
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge, self.runs, self.content
        )
        self.run_a = self.runs.create("What does the advisory say?").run_id
        self.run_b = self.runs.create("What does the advisory say now?").run_id

    def chunk_for(self, document_id: str):  # type: ignore[no-untyped-def]
        return next(c for c in self.knowledge.chunks() if c.document_id == document_id)

    def restarted(self) -> tuple[KnowledgeEngine, list[ResearchRun]]:
        runs = JsonFileResearchRunStore(self.root / "runs.json").load()
        knowledge = KnowledgeEngine()
        ResearchSourceContentRestorer(
            JsonFileResearchSourceContentStore(self.root / "content.json"), knowledge
        ).restore(runs)
        return knowledge, runs

    def test_same_url_different_content_keeps_two_versions_and_observations(self):
        first = self.acceptance.accept(fetched(TEXT_A), self.run_a)
        second = self.acceptance.accept(fetched(TEXT_B, LATER), self.run_b)

        self.assertTrue(first.accepted and second.accepted, second)
        self.assertNotEqual(first.document_id, second.document_id)
        self.assertEqual(
            {d.document_id for d in self.knowledge.documents()},
            {first.document_id, second.document_id},
        )
        self.assertEqual(len(self.content.load()), 2)
        source_a = self.runs.get(self.run_a).sources[0]
        source_b = self.runs.get(self.run_b).sources[0]
        self.assertEqual(
            (source_a.document_id, source_a.content_sha256, source_a.fetched_at),
            (first.document_id, sha(TEXT_A), FIRST),
        )
        self.assertEqual(
            (source_b.document_id, source_b.content_sha256, source_b.fetched_at),
            (second.document_id, sha(TEXT_B), LATER),
        )
        # Evidence in each run resolves to the content that run fetched.
        evidence_a = self.runs.add_evidence(
            self.run_a, self.chunk_for(first.document_id), "Run A reading."
        ).evidence[0]
        evidence_b = self.runs.add_evidence(
            self.run_b, self.chunk_for(second.document_id), "Run B reading."
        ).evidence[0]
        self.assertEqual(evidence_a.excerpt, TEXT_A)
        self.assertEqual(evidence_b.excerpt, TEXT_B)

    def test_same_url_same_content_shares_storage_but_not_provenance(self):
        first = self.acceptance.accept(fetched(TEXT_A), self.run_a)
        second = self.acceptance.accept(fetched(TEXT_A, LATER), self.run_b)

        self.assertTrue(second.accepted, second)
        self.assertEqual(first.document_id, second.document_id)
        self.assertEqual(len(self.knowledge.documents()), 1)
        self.assertEqual(len(self.content.load()), 1)
        source_a = self.runs.get(self.run_a).sources[0]
        source_b = self.runs.get(self.run_b).sources[0]
        self.assertEqual(source_a.content_sha256, source_b.content_sha256)
        # Two observations: each run keeps its own fetch and acceptance record.
        self.assertEqual((source_a.fetched_at, source_b.fetched_at), (FIRST, LATER))
        self.assertIsNot(source_a, source_b)

    def test_same_content_in_two_runs_has_distinct_immutable_observation_ids(self):
        """A shared content version cannot stand in for two source observations."""
        self.acceptance.accept(fetched(TEXT_A), self.run_a)
        self.acceptance.accept(fetched(TEXT_A, LATER), self.run_b)

        source_a = self.runs.get(self.run_a).sources[0]
        source_b = self.runs.get(self.run_b).sources[0]

        self.assertEqual(source_a.document_id, source_b.document_id)
        self.assertIsNotNone(source_a.observation_id)
        self.assertIsNotNone(source_b.observation_id)
        self.assertNotEqual(source_a.observation_id, source_b.observation_id)

    def test_observation_id_factory_is_scoped_to_one_run(self):
        manager = ResearchRunManager(
            clock=lambda: LATER,
            observation_id_factory=lambda: "observation-fixed",
        )
        first_run = manager.create("First").run_id
        second_run = manager.create("Second").run_id

        first = manager.add_source(first_run, fetched(TEXT_A), "document-1")
        second = manager.add_source(second_run, fetched(TEXT_A, LATER), "document-1")

        self.assertEqual(first.sources[0].observation_id, "observation-fixed")
        self.assertEqual(second.sources[0].observation_id, "observation-fixed")

    def test_one_run_refuses_duplicate_non_null_observation_id(self):
        source_one = ResearchSourceRecord(
            document_id="document-1",
            url=URL,
            title="First",
            content_type="text/plain",
            fetched_at=FIRST,
            added_at=FIRST,
            observation_id="observation-1",
        )
        source_two = ResearchSourceRecord(
            document_id="document-2",
            url="https://example.test/second",
            title="Second",
            content_type="text/plain",
            fetched_at=LATER,
            added_at=LATER,
            observation_id="observation-1",
        )

        with self.assertRaisesRegex(ResearchError, "duplicate source observations"):
            ResearchRun(
                run_id="run",
                question="Question",
                status=ResearchRunStatus.COLLECTING,
                sources=(source_one, source_two),
                failures=(),
                created_at=FIRST,
                updated_at=LATER,
            )

    def test_a_run_that_did_not_fetch_cannot_use_another_runs_content(self):
        accepted = self.acceptance.accept(fetched(TEXT_A), self.run_a)
        chunk = self.chunk_for(accepted.document_id)
        self.runs.add_evidence(self.run_a, chunk, "Run A reading.")

        with self.assertRaises(ResearchError):
            self.runs.add_evidence(self.run_b, chunk, "Borrowed reading.")

        run_b = self.runs.get(self.run_b)
        self.assertEqual(
            (run_b.sources, run_b.evidence, run_b.assessments, run_b.claims),
            ((), (), (), ()),
        )

    def test_same_run_accepting_the_same_version_twice_is_still_refused(self):
        self.acceptance.accept(fetched(TEXT_A), self.run_a)

        with self.assertRaises(KnowledgeError):
            self.acceptance.accept(fetched(TEXT_A, LATER), self.run_a)

        self.assertEqual(len(self.runs.get(self.run_a).sources), 1)
        self.assertEqual(len(self.content.load()), 1)

    def test_unknown_run_reusing_a_stored_version_fails_without_mutation(self):
        first = self.acceptance.accept(fetched(TEXT_A), self.run_a)

        result = self.acceptance.accept(fetched(TEXT_A, LATER), "missing-run")

        self.assertFalse(result.accepted)
        self.assertIsNotNone(self.knowledge.loaded_document(first.document_id))
        self.assertEqual(len(self.content.load()), 1)

    def test_failed_attach_to_a_shared_version_leaves_the_other_run_intact(self):
        first = self.acceptance.accept(fetched(TEXT_A), self.run_a)

        with patch.object(
            ResearchRunManager, "add_source", side_effect=ResearchError("refused")
        ):
            second = self.acceptance.accept(fetched(TEXT_A, LATER), self.run_b)

        self.assertFalse(second.accepted)
        self.assertIsNotNone(self.knowledge.loaded_document(first.document_id))
        self.assertEqual(len(self.content.load()), 1)
        self.assertEqual(self.runs.get(self.run_b).sources, ())

    def test_restart_restores_each_runs_exact_version(self):
        first = self.acceptance.accept(fetched(TEXT_A), self.run_a)
        second = self.acceptance.accept(fetched(TEXT_B, LATER), self.run_b)
        shared = self.runs.create("A third run").run_id
        self.acceptance.accept(fetched(TEXT_A, LATER), shared)
        evidence_a = self.runs.add_evidence(
            self.run_a, self.chunk_for(first.document_id), "Run A reading."
        ).evidence[0]
        evidence_b = self.runs.add_evidence(
            self.run_b, self.chunk_for(second.document_id), "Run B reading."
        ).evidence[0]

        knowledge, runs = self.restarted()

        self.assertEqual(
            {d.document_id for d in knowledge.documents()},
            {first.document_id, second.document_id},
        )
        self.assertEqual(knowledge.get_chunk(evidence_a.chunk_id).content, TEXT_A)
        self.assertEqual(knowledge.get_chunk(evidence_b.chunk_id).content, TEXT_B)
        by_run = {run.run_id: run for run in runs}
        self.assertEqual(
            [s.content_sha256 for s in by_run[shared].sources], [sha(TEXT_A)]
        )
        self.assertEqual([s.fetched_at for s in by_run[shared].sources], [LATER])
        self.assertEqual(
            by_run[self.run_a].sources[0].observation_id,
            self.runs.get(self.run_a).sources[0].observation_id,
        )

    def test_restore_refuses_stored_content_a_run_did_not_observe(self):
        accepted = self.acceptance.accept(fetched(TEXT_A), self.run_a)
        path = self.root / "runs.json"
        document = json.loads(path.read_text("utf-8"))
        run = next(r for r in document["runs"] if r["run_id"] == self.run_a)
        run["sources"][0]["content_sha256"] = sha(TEXT_B)
        path.write_text(json.dumps(document), encoding="utf-8")
        self.assertTrue(accepted.accepted)

        with self.assertRaisesRegex(ResearchError, "does not match its provenance"):
            self.restarted()


class LegacySourceIdentityTests(unittest.TestCase):
    def test_legacy_url_identity_restores_without_version_meaning(self):
        source = fetched(TEXT_A)
        legacy_id = str(uuid5(NAMESPACE_URL, URL))
        record = ResearchSourceContentRecord.from_source(
            source, legacy_id, FIRST + timedelta(minutes=1)
        )
        legacy_source = ResearchSourceRecord(
            document_id=legacy_id,
            url=URL,
            title=source.title,
            content_type=source.content_type,
            fetched_at=FIRST,
            added_at=FIRST + timedelta(minutes=1),
        )
        run = ResearchRun(
            run_id="legacy-run",
            question="Old question",
            status=ResearchRunManager.__init__.__defaults__
            and __import__(
                "research.ResearchRunStatus", fromlist=["ResearchRunStatus"]
            ).ResearchRunStatus.COLLECTING,
            sources=(legacy_source,),
            failures=(),
            created_at=FIRST,
            updated_at=FIRST + timedelta(minutes=1),
        )

        class Store:
            def load(self) -> list[ResearchSourceContentRecord]:
                return [record]

        knowledge = KnowledgeEngine()
        ResearchSourceContentRestorer(Store(), knowledge).restore(  # type: ignore[arg-type]
            [run]
        )

        self.assertEqual([d.document_id for d in knowledge.documents()], [legacy_id])
        self.assertNotEqual(legacy_id, source.content_version_id())
        self.assertIsNone(run.sources[0].content_sha256)

    def test_schema_14_sources_load_with_unrecorded_content_version(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "runs.json"
        manager = ResearchRunManager(JsonFileResearchRunStore(path))
        run_id = manager.create("Question").run_id
        knowledge = KnowledgeEngine()
        ResearchSourceAcceptanceService(knowledge, manager).accept(
            fetched(TEXT_A), run_id
        )
        document = json.loads(path.read_text("utf-8"))
        document["schema_version"] = 14
        for run in document["runs"]:
            for source in run["sources"]:
                source.pop("content_sha256")
                source.pop("requested_url", None)
                source.pop("discovery_candidate_id", None)
                source.pop("observation_id", None)
                source.pop("revalidation_of_observation_id", None)
                source.pop("revalidation_execution_id", None)
        path.write_text(json.dumps(document), encoding="utf-8")

        loaded = JsonFileResearchRunStore(path).load()

        self.assertIsNone(loaded[0].sources[0].content_sha256)
        self.assertIsNone(loaded[0].sources[0].observation_id)

    def test_schema_17_source_loads_with_unrecorded_observation_identity(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "runs.json"
        manager = ResearchRunManager(JsonFileResearchRunStore(path))
        run_id = manager.create("Question").run_id
        ResearchSourceAcceptanceService(KnowledgeEngine(), manager).accept(
            fetched(TEXT_A), run_id
        )
        document = json.loads(path.read_text("utf-8"))
        document["schema_version"] = 17
        for run in document["runs"]:
            for source in run["sources"]:
                source.pop("observation_id")
                source.pop("revalidation_of_observation_id", None)
                source.pop("revalidation_execution_id", None)
        path.write_text(json.dumps(document), encoding="utf-8")

        [loaded] = JsonFileResearchRunStore(path).load()

        self.assertIsNone(loaded.sources[0].observation_id)


if __name__ == "__main__":
    unittest.main()
