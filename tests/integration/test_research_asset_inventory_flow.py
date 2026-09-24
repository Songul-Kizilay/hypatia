"""CognitiveEngine routes the three new asset-inventory intents, or refuses.

Mirrors `test_kali_operation_preview_flow.py`'s convention: build a real
`CognitiveEngine`, with and without an `asset_inventory_store`, and prove the
intents route to the service when it is wired and produce the explicit
"Asset inventory is not available" refusal -- never a silent no-op or an
unrelated error -- when it is not.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ResearchAssetInventoryApplicationService import (
    RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
    RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
    RESEARCH_ASSET_RELATION_RECORD_INTENT,
)
from core.Bootstrap import Bootstrap
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchAssetInventoryStore import (
    JsonFileResearchAssetInventoryStore,
)
from research.JsonFileResearchProgramScopeRevisionStore import (
    JsonFileResearchProgramScopeRevisionStore,
)
from research.ResearchAssetKind import ResearchAssetKind
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
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


def build_engine(
    with_store: bool,
    store_path: Path | None = None,
    program_scope_revision_store: object | None = None,
) -> CognitiveEngine:
    event_bus = EventBus()
    memory_manager = MemoryManager(event_bus)
    session_manager = SessionManager(event_bus)
    store = (
        JsonFileResearchAssetInventoryStore(store_path)
        if with_store and store_path is not None
        else None
    )
    return CognitiveEngine(
        KnowledgeEngine(),
        memory_manager,
        Planner(),
        event_bus,
        ResponseComposer(),
        session_manager,
        SessionRenameTransactionService(
            session_manager=session_manager,
            memory_manager=memory_manager,
            event_bus=event_bus,
        ),
        asset_inventory_store=store,
        program_scope_revision_store=program_scope_revision_store,  # type: ignore[arg-type]
    )


class AssetInventoryDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        store_path = Path(self.temporary_directory.name) / "asset_inventory.json"
        self.engine = build_engine(with_store=True, store_path=store_path)

    def test_observation_record_intent_routes_to_the_service(self) -> None:
        response = self.engine.process(
            BrainRequest(
                message="record observation",
                metadata={
                    "intent": RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
                    "program_id": "program-a",
                    "kind": ResearchAssetKind.HOSTNAME,
                    "value": "example.test",
                },
            )
        )

        self.assertTrue(response.success, response.message)
        self.assertIsNotNone(response.research_asset_observation_record)

    def test_relation_record_intent_routes_to_the_service(self) -> None:
        self.engine.process(
            BrainRequest(
                message="record observation",
                metadata={
                    "intent": RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
                    "program_id": "program-a",
                    "kind": ResearchAssetKind.HOSTNAME,
                    "value": "example.test",
                },
            )
        )
        self.engine.process(
            BrainRequest(
                message="record observation",
                metadata={
                    "intent": RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
                    "program_id": "program-a",
                    "kind": ResearchAssetKind.IP_ADDRESS,
                    "value": "93.184.216.34",
                },
            )
        )

        response = self.engine.process(
            BrainRequest(
                message="record relation",
                metadata={
                    "intent": RESEARCH_ASSET_RELATION_RECORD_INTENT,
                    "program_id": "program-a",
                    "source_kind": ResearchAssetKind.HOSTNAME,
                    "source_value": "example.test",
                    "related_kind": ResearchAssetKind.IP_ADDRESS,
                    "related_value": "93.184.216.34",
                    "kind": ResearchAssetRelationKind.RESOLVES_TO,
                },
            )
        )

        self.assertTrue(response.success, response.message)
        self.assertIsNotNone(response.research_asset_relation_record)

    def test_inventory_preview_intent_routes_to_the_service(self) -> None:
        response = self.engine.process(
            BrainRequest(
                message="preview inventory",
                metadata={
                    "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                    "program_id": "program-a",
                },
            )
        )

        self.assertTrue(response.success, response.message)
        self.assertEqual(response.research_asset_inventory, ())


class AssetInventoryUnavailableFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = build_engine(with_store=False)

    def test_observation_record_refuses_explicitly_without_a_store(self) -> None:
        response = self.engine.process(
            BrainRequest(
                message="record observation",
                metadata={
                    "intent": RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
                    "program_id": "program-a",
                    "kind": ResearchAssetKind.HOSTNAME,
                    "value": "example.test",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("Asset inventory is not available", response.message)
        self.assertIsNone(response.research_asset_observation_record)

    def test_relation_record_refuses_explicitly_without_a_store(self) -> None:
        response = self.engine.process(
            BrainRequest(
                message="record relation",
                metadata={
                    "intent": RESEARCH_ASSET_RELATION_RECORD_INTENT,
                    "program_id": "program-a",
                    "source_kind": ResearchAssetKind.HOSTNAME,
                    "source_value": "example.test",
                    "related_kind": ResearchAssetKind.IP_ADDRESS,
                    "related_value": "93.184.216.34",
                    "kind": ResearchAssetRelationKind.RESOLVES_TO,
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("Asset inventory is not available", response.message)
        self.assertIsNone(response.research_asset_relation_record)

    def test_inventory_preview_refuses_explicitly_without_a_store(self) -> None:
        response = self.engine.process(
            BrainRequest(
                message="preview inventory",
                metadata={
                    "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                    "program_id": "program-a",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("Asset inventory is not available", response.message)
        self.assertEqual(response.research_asset_inventory, ())


class BootstrapWiringTests(unittest.TestCase):
    """The shipped composition must actually reach the inventory service.

    Building the engine directly with a store (as the dispatch tests above do)
    proves routing but not wiring: without these, dropping the Bootstrap
    argument would leave the feature permanently unavailable in the real app
    while every other test stayed green.
    """

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def _bootstrap(self) -> Bootstrap:
        return Bootstrap(
            memory_path=self.root / "memory.json",
            session_path=self.root / "sessions.json",
            research_run_path=self.root / "runs.json",
        )

    def test_the_store_lands_beside_the_run_store(self) -> None:
        store = self._bootstrap()._asset_inventory_store()

        self.assertEqual(store._path, self.root / "research_asset_inventory.json")

    def test_a_bootstrap_composed_engine_answers_the_inventory_intents(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()
        self.addCleanup(bootstrap.shutdown)
        engine = bootstrap.container.resolve(CognitiveEngine)

        recorded = engine.process(
            BrainRequest(
                message="record observation",
                metadata={
                    "intent": RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
                    "program_id": "program-a",
                    "kind": ResearchAssetKind.HOSTNAME,
                    "value": "example.test",
                },
            )
        )
        previewed = engine.process(
            BrainRequest(
                message="preview inventory",
                metadata={
                    "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                    "program_id": "program-a",
                },
            )
        )

        self.assertIsNotNone(engine._research_asset_inventory_service)
        self.assertTrue(recorded.success, recorded.message)
        self.assertTrue(previewed.success, previewed.message)
        self.assertNotIn("Asset inventory is not available", previewed.message)
        self.assertEqual(len(previewed.research_asset_inventory), 1)
        self.assertTrue((self.root / "research_asset_inventory.json").is_file())


class PreviewScopeStatusTests(unittest.TestCase):
    """Each entry must carry its own live reading, per asset.

    Asserting only the number of entries would pass an implementation that
    pairs every asset with the first asset's resolution — which is exactly the
    "asset existence confers scope" failure this milestone exists to prevent.
    """

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        revision = ResearchProgramScopeRevision(
            revision_id="revision-1",
            program_id="program-a",
            scope=ResearchTargetScope(allowed_hosts=(TargetHostRule("example.test"),)),
            confirmed_at=datetime.now(UTC) - timedelta(minutes=1),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            execution_policy=DEFAULT_PROGRAM_SCOPE_EXECUTION_POLICY,
        )
        revision_store = JsonFileResearchProgramScopeRevisionStore(
            self.root / "program_scope_revisions.json"
        )
        revision_store.save([revision])
        self.engine = build_engine(
            with_store=True,
            store_path=self.root / "research_asset_inventory.json",
            program_scope_revision_store=revision_store,
        )

    def _observe(self, kind: ResearchAssetKind, value: str) -> None:
        response = self.engine.process(
            BrainRequest(
                message="record observation",
                metadata={
                    "intent": RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
                    "program_id": "program-a",
                    "kind": kind,
                    "value": value,
                },
            )
        )
        self.assertTrue(response.success, response.message)

    def _statuses(self) -> dict[str, object]:
        response = self.engine.process(
            BrainRequest(
                message="preview inventory",
                metadata={
                    "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                    "program_id": "program-a",
                },
            )
        )
        self.assertTrue(response.success, response.message)
        return {
            f"{entry.asset.kind.value}:{entry.asset.canonical_value}": (
                entry.scope.resolution.status if entry.scope.resolution else None
            )
            for entry in response.research_asset_inventory
        }

    def test_each_asset_carries_its_own_status_despite_a_resolves_to_relation(
        self,
    ) -> None:
        self._observe(ResearchAssetKind.HOSTNAME, "example.test")
        self._observe(ResearchAssetKind.IP_ADDRESS, "93.184.216.34")
        related = self.engine.process(
            BrainRequest(
                message="record relation",
                metadata={
                    "intent": RESEARCH_ASSET_RELATION_RECORD_INTENT,
                    "program_id": "program-a",
                    "source_kind": ResearchAssetKind.HOSTNAME,
                    "source_value": "example.test",
                    "related_kind": ResearchAssetKind.IP_ADDRESS,
                    "related_value": "93.184.216.34",
                    "kind": ResearchAssetRelationKind.RESOLVES_TO,
                },
            )
        )
        self.assertTrue(related.success, related.message)

        statuses = self._statuses()

        self.assertEqual(
            statuses["hostname:example.test"],
            ResearchTargetScopeResolutionStatus.IN_SCOPE,
        )
        self.assertEqual(
            statuses["ip_address:93.184.216.34"],
            ResearchTargetScopeResolutionStatus.UNCERTAIN,
        )

    def test_a_suffix_lookalike_never_inherits_the_real_hosts_status(self) -> None:
        self._observe(ResearchAssetKind.HOSTNAME, "example.test")
        self._observe(ResearchAssetKind.HOSTNAME, "attackerexample.test")

        statuses = self._statuses()

        self.assertEqual(
            statuses["hostname:example.test"],
            ResearchTargetScopeResolutionStatus.IN_SCOPE,
        )
        self.assertEqual(
            statuses["hostname:attackerexample.test"],
            ResearchTargetScopeResolutionStatus.UNCERTAIN,
        )


class NoExternalEffectTests(unittest.TestCase):
    """Recording and listing must reach no network and no process.

    The service module's central claim; previously only a docstring.
    """

    def test_recording_and_listing_open_no_socket_and_spawn_no_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            engine = build_engine(
                with_store=True,
                store_path=Path(directory) / "research_asset_inventory.json",
            )
            with (
                patch("socket.socket", side_effect=AssertionError("socket opened")),
                patch(
                    "socket.getaddrinfo",
                    side_effect=AssertionError("name resolved"),
                ),
                patch(
                    "subprocess.Popen",
                    side_effect=AssertionError("process spawned"),
                ),
                patch(
                    "urllib.request.urlopen",
                    side_effect=AssertionError("request issued"),
                ),
            ):
                recorded = engine.process(
                    BrainRequest(
                        message="record observation",
                        metadata={
                            "intent": RESEARCH_ASSET_OBSERVATION_RECORD_INTENT,
                            "program_id": "program-a",
                            "kind": ResearchAssetKind.HOSTNAME,
                            "value": "example.test",
                        },
                    )
                )
                previewed = engine.process(
                    BrainRequest(
                        message="preview inventory",
                        metadata={
                            "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                            "program_id": "program-a",
                        },
                    )
                )

            self.assertTrue(recorded.success, recorded.message)
            self.assertTrue(previewed.success, previewed.message)


if __name__ == "__main__":
    unittest.main()
