"""End-to-end: a completed DNS lookup run can be ingested into the inventory.

Exercises the full pipeline a real desktop session would drive: preview ->
authorize -> run (the existing, unchanged Kali operation flow) -> DNS
ingestion preview -> DNS ingestion record, all through one `CognitiveEngine`,
proving the new ingestion intents wire exactly like every other intent in
this file and that ingestion itself never opens a socket or spawns a process.
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
from cognition.KaliOperationAuthorizationApplicationService import (
    KALI_OPERATION_AUTHORIZATION_INTENT,
)
from cognition.KaliOperationPreviewApplicationService import (
    KALI_OPERATION_PREVIEW_INTENT,
)
from cognition.KaliOperationRunApplicationService import KALI_OPERATION_RUN_INTENT
from cognition.ResearchAssetInventoryApplicationService import (
    RESEARCH_ASSET_DNS_INGESTION_PREVIEW_INTENT,
    RESEARCH_ASSET_DNS_INGESTION_RECORD_INTENT,
    RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
)
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchAssetInventoryStore import (
    JsonFileResearchAssetInventoryStore,
)
from research.JsonFileResearchKaliOperationAuthorizationStore import (
    JsonFileResearchKaliOperationAuthorizationStore,
)
from research.JsonFileResearchProgramScopeRevisionStore import (
    JsonFileResearchProgramScopeRevisionStore,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchKaliOperationExecution import ResearchKaliOperationProcessResult
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
)
from research.ResearchKaliRuntimeEnvironment import (
    ResearchKaliRuntimeReadiness,
    ResearchKaliRuntimeReadinessState,
    ResearchKaliRuntimeRequirement,
)
from research.ResearchProgramScopeExecutionPolicy import (
    ResearchProgramScopeCheckClass,
    ResearchProgramScopeExecutionPolicy,
)
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from research.ResearchTargetScope import ResearchTargetScope, TargetHostRule
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class _ReadyProbe:
    def readiness(
        self, requirement: ResearchKaliRuntimeRequirement
    ) -> ResearchKaliRuntimeReadiness:
        return ResearchKaliRuntimeReadiness(
            requirement=requirement,
            state=ResearchKaliRuntimeReadinessState.READY,
            reason="Fake WSL/Kali runtime is ready.",
            observed_distribution=requirement.distribution,
            observed_executable_path=requirement.executable_path,
            observed_version=f"{requirement.version_prefix}18.36",
        )


class _ConfigurableAdapter:
    """Returns whatever the current test configured, never a real process."""

    def __init__(self, state: dict[str, object]) -> None:
        self._state = state

    def run(self, command_plan, *, timeout_seconds: float):
        return ResearchKaliOperationProcessResult(
            command_plan=command_plan,
            exit_code=self._state.get("exit_code", 0),  # type: ignore[arg-type]
            stdout_lines=self._state.get("stdout_lines", ()),  # type: ignore[arg-type]
            timed_out=self._state.get("timed_out", False),  # type: ignore[arg-type]
        )


class ResearchAssetDnsIngestionFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        now = datetime.now(UTC)
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.session_manager = SessionManager(self.event_bus)
        self.session_manager.create("work")
        self.scope_store = JsonFileResearchProgramScopeRevisionStore(
            self.root / "scopes.json"
        )
        self.authorization_store = JsonFileResearchKaliOperationAuthorizationStore(
            self.root / "kali-operation-authorizations.json"
        )
        self.asset_inventory_store = JsonFileResearchAssetInventoryStore(
            self.root / "asset-inventory.json"
        )
        self.revision = ResearchProgramScopeRevision(
            "scope-revision-1",
            "program-a",
            ResearchTargetScope(allowed_hosts=(TargetHostRule("example.test", True),)),
            now - timedelta(minutes=1),
            now + timedelta(minutes=30),
            execution_policy=ResearchProgramScopeExecutionPolicy(
                permitted_check_classes=(
                    ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP,
                ),
                permitted_ports=(53,),
            ),
        )
        self.scope_store.save([self.revision])
        self.other_revision = ResearchProgramScopeRevision(
            "scope-revision-b",
            "program-b",
            ResearchTargetScope(allowed_hosts=(TargetHostRule("other.test"),)),
            now - timedelta(minutes=1),
            now + timedelta(minutes=30),
            execution_policy=ResearchProgramScopeExecutionPolicy(
                permitted_check_classes=(
                    ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP,
                ),
                permitted_ports=(53,),
            ),
        )
        self.scope_store.save([self.revision, self.other_revision])
        self.adapter_state: dict[str, object] = {
            "stdout_lines": ("93.184.216.34",),
            "exit_code": 0,
            "timed_out": False,
        }
        self.engine = CognitiveEngine(
            KnowledgeEngine(),
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            SessionRenameTransactionService(
                session_manager=self.session_manager,
                memory_manager=self.memory_manager,
                event_bus=self.event_bus,
            ),
            program_scope_revision_store=self.scope_store,
            kali_operation_authorization_store=self.authorization_store,
            kali_runtime_probe=_ReadyProbe(),
            kali_operation_process_adapter=_ConfigurableAdapter(self.adapter_state),
            asset_inventory_store=self.asset_inventory_store,
        )

    def _run_dns_operation(
        self,
        *,
        hostname: str = "www.example.test",
        record_type: ResearchDnsRecordType = ResearchDnsRecordType.A,
        program_id: str = "program-a",
        revision: ResearchProgramScopeRevision | None = None,
    ):
        active = revision or self.revision
        preview = self.engine.process(
            BrainRequest(
                message="preview Kali DNS operation",
                metadata={
                    "intent": KALI_OPERATION_PREVIEW_INTENT,
                    "program_id": program_id,
                    "scope_revision_id": active.revision_id,
                    "scope_revision_digest": active.revision_digest,
                    "kali_operation_kind": (
                        ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                    ),
                    "hostname": hostname,
                    "dns_record_type": record_type.value,
                },
            )
        ).kali_operation_preview
        assert preview is not None
        authorization = self.engine.process(
            BrainRequest(
                message="authorize Kali DNS operation",
                metadata={
                    "intent": KALI_OPERATION_AUTHORIZATION_INTENT,
                    "program_id": program_id,
                    "scope_revision_id": active.revision_id,
                    "scope_revision_digest": active.revision_digest,
                    "kali_operation_kind": (
                        ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                    ),
                    "hostname": hostname,
                    "dns_record_type": record_type.value,
                    "operation_digest": preview.operation_digest,
                },
            )
        ).kali_operation_authorization
        assert authorization is not None
        response = self.engine.process(
            BrainRequest(
                message="run Kali DNS operation",
                metadata={
                    "intent": KALI_OPERATION_RUN_INTENT,
                    "operator_opt_in": True,
                    "program_id": program_id,
                    "scope_revision_id": active.revision_id,
                    "scope_revision_digest": active.revision_digest,
                    "kali_operation_kind": (
                        ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                    ),
                    "hostname": hostname,
                    "dns_record_type": record_type.value,
                    "operation_digest": preview.operation_digest,
                    "authorization_id": authorization.authorization_id,
                },
            )
        )
        assert response.kali_operation_run is not None
        return response.kali_operation_run

    def test_preview_then_record_creates_hostname_address_and_relation(self) -> None:
        run = self._run_dns_operation()

        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.Popen") as popen,
        ):
            preview_response = self.engine.process(
                BrainRequest(
                    message="preview DNS ingestion",
                    metadata={
                        "intent": RESEARCH_ASSET_DNS_INGESTION_PREVIEW_INTENT,
                        "kali_operation_run": run,
                    },
                )
            )
        self.assertTrue(preview_response.success, preview_response.message)
        preview = preview_response.research_asset_dns_ingestion_preview
        assert preview is not None
        self.assertFalse(preview.hostname_asset.already_known)
        self.assertFalse(preview.observations_recorded)
        self.assertFalse(preview.relations_recorded)
        getaddrinfo.assert_not_called()
        popen.assert_not_called()
        # A preview must never write anything.
        self.assertEqual(self.asset_inventory_store.load().observations, ())

        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.Popen") as popen,
        ):
            record_response = self.engine.process(
                BrainRequest(
                    message="record DNS ingestion",
                    metadata={
                        "intent": RESEARCH_ASSET_DNS_INGESTION_RECORD_INTENT,
                        "kali_operation_run": run,
                    },
                )
            )
        self.assertTrue(record_response.success, record_response.message)
        result = record_response.research_asset_dns_ingestion_result
        assert result is not None
        self.assertEqual(
            result.hostname_observation.canonical_value, "www.example.test"
        )
        [address] = result.address_observations
        self.assertEqual(address.canonical_value, "93.184.216.34")
        [relation] = result.relations
        self.assertEqual(relation.related_value, "93.184.216.34")
        self.assertIs(
            result.hostname_observation.provenance,
            ResearchAssetProvenanceKind.KALI_OPERATION_RESULT,
        )
        self.assertEqual(
            result.hostname_observation.source_operation_digest, run.operation_digest
        )
        getaddrinfo.assert_not_called()
        popen.assert_not_called()

    def test_ingested_hostname_resolves_in_scope_like_an_operator_authored_one(
        self,
    ) -> None:
        run = self._run_dns_operation()
        self.engine.process(
            BrainRequest(
                message="record DNS ingestion",
                metadata={
                    "intent": RESEARCH_ASSET_DNS_INGESTION_RECORD_INTENT,
                    "kali_operation_run": run,
                },
            )
        )

        inventory = self.engine.process(
            BrainRequest(
                message="preview inventory",
                metadata={
                    "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                    "program_id": "program-a",
                },
            )
        )

        self.assertTrue(inventory.success, inventory.message)
        hostname_entry = next(
            entry
            for entry in inventory.research_asset_inventory
            if entry.asset.kind is ResearchAssetKind.HOSTNAME
        )
        self.assertTrue(hostname_entry.scope.has_active_scope_revision)
        assert hostname_entry.scope.resolution is not None
        self.assertEqual(hostname_entry.scope.resolution.status.value, "in_scope")

    def test_recording_the_same_run_twice_never_duplicates_the_canonical_asset(
        self,
    ) -> None:
        run = self._run_dns_operation()
        for _ in range(2):
            response = self.engine.process(
                BrainRequest(
                    message="record DNS ingestion",
                    metadata={
                        "intent": RESEARCH_ASSET_DNS_INGESTION_RECORD_INTENT,
                        "kali_operation_run": run,
                    },
                )
            )
            self.assertTrue(response.success, response.message)

        inventory = self.engine.process(
            BrainRequest(
                message="preview inventory",
                metadata={
                    "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                    "program_id": "program-a",
                },
            )
        )
        self.assertEqual(len(inventory.research_asset_inventory), 2)
        hostname_entry = next(
            entry
            for entry in inventory.research_asset_inventory
            if entry.asset.kind is ResearchAssetKind.HOSTNAME
        )
        self.assertEqual(len(hostname_entry.asset.observations), 2)
        self.assertEqual(len(inventory.research_asset_relations), 2)

    def test_a_run_bound_to_program_a_never_writes_into_program_b(self) -> None:
        run = self._run_dns_operation(program_id="program-a")

        self.engine.process(
            BrainRequest(
                message="record DNS ingestion",
                metadata={
                    "intent": RESEARCH_ASSET_DNS_INGESTION_RECORD_INTENT,
                    "kali_operation_run": run,
                },
            )
        )

        program_b_inventory = self.engine.process(
            BrainRequest(
                message="preview inventory",
                metadata={
                    "intent": RESEARCH_ASSET_INVENTORY_PREVIEW_INTENT,
                    "program_id": "program-b",
                },
            )
        )
        self.assertEqual(program_b_inventory.research_asset_inventory, ())

    def test_a_cname_run_is_rejected_with_zero_writes(self) -> None:
        run = self._run_dns_operation(record_type=ResearchDnsRecordType.CNAME)

        response = self.engine.process(
            BrainRequest(
                message="record DNS ingestion",
                metadata={
                    "intent": RESEARCH_ASSET_DNS_INGESTION_RECORD_INTENT,
                    "kali_operation_run": run,
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIsNone(response.research_asset_dns_ingestion_result)
        self.assertEqual(self.asset_inventory_store.load().observations, ())

    def test_a_failed_run_records_only_the_hostname_with_zero_addresses(self) -> None:
        self.adapter_state["exit_code"] = 1
        run = self._run_dns_operation()

        response = self.engine.process(
            BrainRequest(
                message="record DNS ingestion",
                metadata={
                    "intent": RESEARCH_ASSET_DNS_INGESTION_RECORD_INTENT,
                    "kali_operation_run": run,
                },
            )
        )

        self.assertTrue(response.success, response.message)
        result = response.research_asset_dns_ingestion_result
        assert result is not None
        self.assertEqual(result.address_observations, ())
        self.assertEqual(result.relations, ())
        [row] = result.rejected_rows
        self.assertIn("did not complete successfully", row.reason)

    def test_an_adversarial_output_line_stays_inert_end_to_end(self) -> None:
        self.adapter_state["stdout_lines"] = (
            "93.184.216.34",
            "; rm -rf / #",
        )
        run = self._run_dns_operation()

        response = self.engine.process(
            BrainRequest(
                message="record DNS ingestion",
                metadata={
                    "intent": RESEARCH_ASSET_DNS_INGESTION_RECORD_INTENT,
                    "kali_operation_run": run,
                },
            )
        )

        self.assertTrue(response.success, response.message)
        result = response.research_asset_dns_ingestion_result
        assert result is not None
        [address] = result.address_observations
        self.assertEqual(address.canonical_value, "93.184.216.34")
        [row] = result.rejected_rows
        self.assertEqual(row.raw_line, "; rm -rf / #")
        self.assertIn("; rm -rf / #", response.message)
        # The adversarial text never became a program-id, a scope change, or
        # a second observation -- only one address and one rejected row.
        self.assertEqual(len(result.address_observations), 1)

    def test_dns_ingestion_intents_are_unavailable_without_an_asset_inventory_store(
        self,
    ) -> None:
        engine = CognitiveEngine(
            KnowledgeEngine(),
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            SessionRenameTransactionService(
                session_manager=self.session_manager,
                memory_manager=self.memory_manager,
                event_bus=self.event_bus,
            ),
        )

        preview_response = engine.process(
            BrainRequest(
                message="preview DNS ingestion",
                metadata={"intent": RESEARCH_ASSET_DNS_INGESTION_PREVIEW_INTENT},
            )
        )
        record_response = engine.process(
            BrainRequest(
                message="record DNS ingestion",
                metadata={"intent": RESEARCH_ASSET_DNS_INGESTION_RECORD_INTENT},
            )
        )

        self.assertFalse(preview_response.success)
        self.assertIn("not available", preview_response.message)
        self.assertFalse(record_response.success)
        self.assertIn("not available", record_response.message)


if __name__ == "__main__":
    unittest.main()
