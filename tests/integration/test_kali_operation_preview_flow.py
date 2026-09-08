"""CognitiveEngine can show a Kali operation preview without execution."""

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
from cognition.KaliOperationFakeRunnerApplicationService import (
    KALI_OPERATION_FAKE_RUN_INTENT,
)
from cognition.KaliOperationPreviewApplicationService import (
    KALI_OPERATION_PREVIEW_INTENT,
)
from cognition.KaliOperationRunApplicationService import KALI_OPERATION_RUN_INTENT
from cognition.KaliRuntimeReadinessApplicationService import (
    KALI_RUNTIME_READINESS_INTENT,
)
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchKaliOperationAuthorizationStore import (
    JsonFileResearchKaliOperationAuthorizationStore,
)
from research.JsonFileResearchProgramScopeRevisionStore import (
    JsonFileResearchProgramScopeRevisionStore,
)
from research.ResearchKaliOperationExecution import (
    ResearchKaliOperationProcessResult,
)
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


class KaliOperationPreviewFlowTests(unittest.TestCase):
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
        self.revision = ResearchProgramScopeRevision(
            "scope-revision-1",
            "program-a",
            ResearchTargetScope(
                allowed_hosts=(
                    TargetHostRule("example.test"),
                    TargetHostRule("example.test", True),
                )
            ),
            now - timedelta(minutes=1),
            now + timedelta(minutes=30),
            execution_policy=ResearchProgramScopeExecutionPolicy(
                permitted_check_classes=(
                    ResearchProgramScopeCheckClass.PUBLIC_HTTPS_CONTENT,
                    ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP,
                ),
                permitted_ports=(53, 443),
            ),
        )
        self.scope_store.save([self.revision])
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
        )

    def test_structured_runtime_readiness_routes_without_execution(self) -> None:
        class ReadyProbe:
            def readiness(
                self,
                requirement: ResearchKaliRuntimeRequirement,
            ) -> ResearchKaliRuntimeReadiness:
                return ResearchKaliRuntimeReadiness(
                    requirement=requirement,
                    state=ResearchKaliRuntimeReadinessState.READY,
                    reason="Fake WSL/Kali runtime is ready.",
                    observed_distribution=requirement.distribution,
                    observed_executable_path=requirement.executable_path,
                    observed_version=f"{requirement.version_prefix}18.36",
                )

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
            program_scope_revision_store=self.scope_store,
            kali_operation_authorization_store=self.authorization_store,
            kali_runtime_probe=ReadyProbe(),
        )

        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            response = engine.process(
                BrainRequest(
                    message="check Kali runtime",
                    metadata={
                        "intent": KALI_RUNTIME_READINESS_INTENT,
                        "operator_opt_in": True,
                    },
                )
            )

        self.assertTrue(response.success, response.message)
        self.assertEqual(response.intent, KALI_RUNTIME_READINESS_INTENT)
        self.assertIsNotNone(response.kali_runtime_readiness)
        self.assertIn("Distribution required: kali-linux", response.message)
        self.assertIn("Executable required: /usr/bin/dig", response.message)
        self.assertIn("Execution: not started", response.message)
        getaddrinfo.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

    def test_structured_preview_routes_without_dns_process_or_write(self) -> None:
        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.Popen") as popen,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="preview Kali DNS operation",
                    metadata={
                        "intent": KALI_OPERATION_PREVIEW_INTENT,
                        "program_id": "program-a",
                        "scope_revision_id": self.revision.revision_id,
                        "scope_revision_digest": self.revision.revision_digest,
                        "kali_operation_kind": (
                            ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                        ),
                        "hostname": "www.example.test",
                        "dns_record_type": ResearchDnsRecordType.A.value,
                    },
                )
            )

        self.assertTrue(response.success, response.message)
        self.assertEqual(response.intent, KALI_OPERATION_PREVIEW_INTENT)
        self.assertIsNotNone(response.kali_operation_preview)
        self.assertIn("Command plan: reviewed argv only", response.message)
        self.assertIn("argv[0]: /usr/bin/dig", response.message)
        self.assertIn("Execution: not started", response.message)
        self.assertEqual(len(self.scope_store.load()), 1)
        getaddrinfo.assert_not_called()
        popen.assert_not_called()

    def test_structured_authorization_routes_without_execution(self) -> None:
        preview = self.engine.process(
            BrainRequest(
                message="preview Kali DNS operation",
                metadata={
                    "intent": KALI_OPERATION_PREVIEW_INTENT,
                    "program_id": "program-a",
                    "scope_revision_id": self.revision.revision_id,
                    "scope_revision_digest": self.revision.revision_digest,
                    "kali_operation_kind": (
                        ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                    ),
                    "hostname": "www.example.test",
                    "dns_record_type": ResearchDnsRecordType.A.value,
                },
            )
        ).kali_operation_preview
        assert preview is not None

        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.Popen") as popen,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="authorize Kali DNS operation",
                    metadata={
                        "intent": KALI_OPERATION_AUTHORIZATION_INTENT,
                        "program_id": "program-a",
                        "scope_revision_id": self.revision.revision_id,
                        "scope_revision_digest": self.revision.revision_digest,
                        "kali_operation_kind": (
                            ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                        ),
                        "hostname": "www.example.test",
                        "dns_record_type": ResearchDnsRecordType.A.value,
                        "operation_digest": preview.operation_digest,
                    },
                )
            )

        self.assertTrue(response.success, response.message)
        self.assertEqual(response.intent, KALI_OPERATION_AUTHORIZATION_INTENT)
        self.assertIsNotNone(response.kali_operation_authorization)
        self.assertIn("Execution: not started", response.message)
        self.assertIn("Command plan: bound by operation digest", response.message)
        getaddrinfo.assert_not_called()
        popen.assert_not_called()

    def test_structured_fake_run_routes_without_real_execution(self) -> None:
        preview = self.engine.process(
            BrainRequest(
                message="preview Kali DNS operation",
                metadata={
                    "intent": KALI_OPERATION_PREVIEW_INTENT,
                    "program_id": "program-a",
                    "scope_revision_id": self.revision.revision_id,
                    "scope_revision_digest": self.revision.revision_digest,
                    "kali_operation_kind": (
                        ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                    ),
                    "hostname": "www.example.test",
                    "dns_record_type": ResearchDnsRecordType.A.value,
                },
            )
        ).kali_operation_preview
        assert preview is not None
        authorization = self.engine.process(
            BrainRequest(
                message="authorize Kali DNS operation",
                metadata={
                    "intent": KALI_OPERATION_AUTHORIZATION_INTENT,
                    "program_id": "program-a",
                    "scope_revision_id": self.revision.revision_id,
                    "scope_revision_digest": self.revision.revision_digest,
                    "kali_operation_kind": (
                        ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                    ),
                    "hostname": "www.example.test",
                    "dns_record_type": ResearchDnsRecordType.A.value,
                    "operation_digest": preview.operation_digest,
                },
            )
        ).kali_operation_authorization
        assert authorization is not None

        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="fake run Kali DNS operation",
                    metadata={
                        "intent": KALI_OPERATION_FAKE_RUN_INTENT,
                        "program_id": "program-a",
                        "scope_revision_id": self.revision.revision_id,
                        "scope_revision_digest": self.revision.revision_digest,
                        "kali_operation_kind": (
                            ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                        ),
                        "hostname": "www.example.test",
                        "dns_record_type": ResearchDnsRecordType.A.value,
                        "operation_digest": preview.operation_digest,
                        "authorization_id": authorization.authorization_id,
                    },
                )
            )

        self.assertTrue(response.success, response.message)
        self.assertEqual(response.intent, KALI_OPERATION_FAKE_RUN_INTENT)
        self.assertIsNotNone(response.kali_operation_fake_run)
        self.assertIn("Execution: simulated only", response.message)
        self.assertIn("Process: not created", response.message)
        getaddrinfo.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

    def test_structured_preview_refuses_when_scope_store_is_absent(self) -> None:
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
        response = engine.process(
            BrainRequest(
                message="preview Kali DNS operation",
                metadata={"intent": KALI_OPERATION_PREVIEW_INTENT},
            )
        )

        self.assertFalse(response.success)
        self.assertIn("scope revisions are unavailable", response.message)
        self.assertIsNone(response.kali_operation_preview)

    def test_structured_authorization_refuses_when_scope_store_is_absent(self) -> None:
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
        response = engine.process(
            BrainRequest(
                message="authorize Kali DNS operation",
                metadata={"intent": KALI_OPERATION_AUTHORIZATION_INTENT},
            )
        )

        self.assertFalse(response.success)
        self.assertIn("scope revisions are unavailable", response.message)
        self.assertIsNone(response.kali_operation_authorization)

    def test_operation_run_route_is_unavailable_without_process_adapter(
        self,
    ) -> None:
        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="run Kali DNS operation",
                    metadata={
                        "intent": KALI_OPERATION_RUN_INTENT,
                        "operator_opt_in": True,
                        "program_id": "program-a",
                        "scope_revision_id": self.revision.revision_id,
                        "scope_revision_digest": self.revision.revision_digest,
                        "kali_operation_kind": (
                            ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                        ),
                        "hostname": "www.example.test",
                        "dns_record_type": ResearchDnsRecordType.A.value,
                        "operation_digest": "0" * 64,
                        "authorization_id": "kali-auth-1",
                    },
                )
            )

        self.assertFalse(response.success)
        self.assertEqual(response.intent, KALI_OPERATION_RUN_INTENT)
        self.assertIsNone(response.kali_operation_run)
        self.assertIn("runner is unavailable", response.message)
        getaddrinfo.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

    def test_operation_run_routes_only_with_injected_runtime_and_adapter(
        self,
    ) -> None:
        class ReadyProbe:
            def readiness(
                self,
                requirement: ResearchKaliRuntimeRequirement,
            ) -> ResearchKaliRuntimeReadiness:
                return ResearchKaliRuntimeReadiness(
                    requirement=requirement,
                    state=ResearchKaliRuntimeReadinessState.READY,
                    reason="Fake WSL/Kali runtime is ready.",
                    observed_distribution=requirement.distribution,
                    observed_executable_path=requirement.executable_path,
                    observed_version=f"{requirement.version_prefix}18.36",
                )

        class Adapter:
            def run(self, command_plan, *, timeout_seconds: float):
                return ResearchKaliOperationProcessResult(
                    command_plan=command_plan,
                    exit_code=0,
                    stdout_lines=("192.0.2.10",),
                )

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
            program_scope_revision_store=self.scope_store,
            kali_operation_authorization_store=self.authorization_store,
            kali_runtime_probe=ReadyProbe(),
            kali_operation_process_adapter=Adapter(),
        )
        preview = engine.process(
            BrainRequest(
                message="preview Kali DNS operation",
                metadata={
                    "intent": KALI_OPERATION_PREVIEW_INTENT,
                    "program_id": "program-a",
                    "scope_revision_id": self.revision.revision_id,
                    "scope_revision_digest": self.revision.revision_digest,
                    "kali_operation_kind": (
                        ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                    ),
                    "hostname": "www.example.test",
                    "dns_record_type": ResearchDnsRecordType.A.value,
                },
            )
        ).kali_operation_preview
        assert preview is not None
        authorization = engine.process(
            BrainRequest(
                message="authorize Kali DNS operation",
                metadata={
                    "intent": KALI_OPERATION_AUTHORIZATION_INTENT,
                    "program_id": "program-a",
                    "scope_revision_id": self.revision.revision_id,
                    "scope_revision_digest": self.revision.revision_digest,
                    "kali_operation_kind": (
                        ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                    ),
                    "hostname": "www.example.test",
                    "dns_record_type": ResearchDnsRecordType.A.value,
                    "operation_digest": preview.operation_digest,
                },
            )
        ).kali_operation_authorization
        assert authorization is not None

        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            response = engine.process(
                BrainRequest(
                    message="run Kali DNS operation",
                    metadata={
                        "intent": KALI_OPERATION_RUN_INTENT,
                        "operator_opt_in": True,
                        "program_id": "program-a",
                        "scope_revision_id": self.revision.revision_id,
                        "scope_revision_digest": self.revision.revision_digest,
                        "kali_operation_kind": (
                            ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                        ),
                        "hostname": "www.example.test",
                        "dns_record_type": ResearchDnsRecordType.A.value,
                        "operation_digest": preview.operation_digest,
                        "authorization_id": authorization.authorization_id,
                    },
                )
            )

        self.assertTrue(response.success, response.message)
        self.assertEqual(response.intent, KALI_OPERATION_RUN_INTENT)
        self.assertIsNotNone(response.kali_operation_run)
        self.assertEqual(self.authorization_store.load(), [])
        self.assertIn("Authorization ID consumed", response.message)
        self.assertIn("Evidence: not recorded", response.message)
        getaddrinfo.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
