"""The conversational model learns what this runtime can do, and nothing more.

Driven through the real Bootstrap wiring with a mocked chat transport: no live
model, network, Ollama or research provider.  Capability awareness is
description only, so these tests also prove that building and sending it
creates no approval, run, fetch, allowance spend or background work.
"""

from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.RuntimeCapabilityProjection import (
    RuntimeCapability,
    RuntimeCapabilityContext,
    RuntimeCapabilityState,
)
from core.Bootstrap import Bootstrap
from llm.HypatiaSystemPrompt import HYPATIA_DEFAULT_SYSTEM_PROMPT
from llm.LLMRuntimeConfig import LLMRuntimeConfig

ENABLED = LLMRuntimeConfig(
    enabled=True,
    base_url="https://api.example.test/v1/chat/completions",
    model="test-model",
)
DISABLED = LLMRuntimeConfig(enabled=False, base_url="", model="")
ANSWER = {"choices": [{"message": {"content": "I can talk with you."}}]}


class RuntimeCapabilitySelfAwarenessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def _engine(
        self,
        *,
        config: LLMRuntimeConfig = ENABLED,
        system_prompt: str | None = None,
    ) -> tuple[CognitiveEngine, Mock]:
        with (
            patch(
                "core.Bootstrap.load_llm_process_environment_settings",
                return_value=(config, "test-api-key"),
            ),
            patch(
                "core.Bootstrap.load_llm_process_system_prompt",
                return_value=system_prompt,
            ),
        ):
            bootstrap = Bootstrap.from_process_environment(
                self.root / "memory.json", self.root / "sessions.json"
            )
            bootstrap.initialize()
        self.addCleanup(bootstrap.shutdown)
        engine = bootstrap.container.resolve(CognitiveEngine)
        transport = Mock(return_value=ANSWER)
        if engine._llm_provider is not None:
            engine._llm_provider._transport = transport  # type: ignore[attr-defined]
        engine._session_manager.create("work-1")
        return engine, transport

    @staticmethod
    def _ask(engine: CognitiveEngine, message: str):  # type: ignore[no-untyped-def]
        return engine.process(
            BrainRequest(message=message, metadata={"session_id": "work-1"})
        )

    def test_the_real_runtime_projects_its_own_wiring(self) -> None:
        engine, _ = self._engine()
        context = engine.runtime_capabilities

        for capability in (
            RuntimeCapability.CONVERSATION,
            RuntimeCapability.SESSIONS,
            RuntimeCapability.MEMORY,
            RuntimeCapability.AUTHORIZED_RESEARCH,
            RuntimeCapability.SOURCE_ACQUISITION,
            RuntimeCapability.EVIDENCE_TRACKING,
            RuntimeCapability.SOURCE_REVALIDATION,
        ):
            self.assertIs(
                context.state_of(capability),
                RuntimeCapabilityState.AVAILABLE,
                capability,
            )
        # No Kali runner is configured in this environment, so none is claimed.
        self.assertIs(
            context.state_of(RuntimeCapability.REVIEWED_KALI_LOOKUPS),
            RuntimeCapabilityState.UNAVAILABLE,
        )
        for capability in (
            RuntimeCapability.CHAT_WEB_BROWSING,
            RuntimeCapability.PENETRATION_TESTING,
            RuntimeCapability.CONTINUOUS_MONITORING,
        ):
            self.assertIs(
                context.state_of(capability), RuntimeCapabilityState.UNAVAILABLE
            )

    def test_chat_receives_the_default_prompt_and_the_capability_context(
        self,
    ) -> None:
        engine, transport = self._engine()

        response = self._ask(engine, "What can you actually do right now?")

        self.assertTrue(response.success)
        messages = transport.call_args.args[2]["messages"]
        self.assertEqual(
            messages[0],
            {
                "role": "system",
                "content": (
                    f"{HYPATIA_DEFAULT_SYSTEM_PROMPT}\n\n"
                    f"{engine.runtime_capabilities.instruction()}"
                ),
            },
        )
        # The capability block is its own trailing section, not a rewrite.
        self.assertTrue(
            messages[0]["content"].startswith(HYPATIA_DEFAULT_SYSTEM_PROMPT)
        )
        self.assertEqual(messages[-1]["role"], "user")
        self.assertNotIn("Hypatia runtime capabilities", messages[-1]["content"])

    def test_capability_awareness_holds_throughout_conversation(self) -> None:
        engine, transport = self._engine()

        for message in (
            "What can you actually do right now?",
            "Can you remember things?",
            "Can you run a pentest?",
            "Neler yapabilirsin?",
        ):
            self._ask(engine, message)

        system_messages = [
            call.args[2]["messages"][0]["content"] for call in transport.call_args_list
        ]
        self.assertEqual(len(system_messages), 4)
        self.assertEqual(len(set(system_messages)), 1)
        self.assertIn("Hypatia runtime capabilities.", system_messages[0])

    def test_a_custom_system_prompt_keeps_runtime_capability_truth(self) -> None:
        engine, transport = self._engine(system_prompt="Custom operator rule.")

        self._ask(engine, "What are your capabilities?")

        content = transport.call_args.args[2]["messages"][0]["content"]
        self.assertTrue(content.startswith("Custom operator rule.\n\n"))
        self.assertNotIn(HYPATIA_DEFAULT_SYSTEM_PROMPT, content)
        self.assertTrue(content.endswith(engine.runtime_capabilities.instruction()))

    def test_the_model_is_told_it_is_not_hypatia_itself(self) -> None:
        engine, transport = self._engine()

        self._ask(engine, "Are you a large language model?")

        content = transport.call_args.args[2]["messages"][0]["content"]
        self.assertIn("Hypatia is an application.", content)
        self.assertIn("Do not describe yourself as a large language model", content)
        self.assertIn("never invent a capability", content)

    def test_capability_awareness_grants_and_starts_nothing(self) -> None:
        engine, transport = self._engine()
        watched = sorted(
            path
            for path in self.root.iterdir()
            if path.name not in {"memory.json", "sessions.json"}
            and not path.name.startswith(".")
        )
        before_files = {path: path.read_bytes() for path in watched if path.is_file()}
        runs_before = engine._research_run_manager.list()
        approvals = engine._plan_authorization_service
        assert approvals is not None
        approvals_before = list(approvals.authorizations())
        threads_before = threading.active_count()

        for _ in range(3):
            engine.runtime_capabilities.instruction()
        self.assertEqual(transport.call_count, 0)
        self._ask(engine, "Please research the latest advisory and revalidate it.")

        self.assertLessEqual(transport.call_count, 1)
        self.assertEqual(engine._research_run_manager.list(), runs_before)
        self.assertEqual(list(approvals.authorizations()), approvals_before)
        self.assertEqual(engine._research_run_manager.source_revalidations(), [])
        self.assertEqual(
            {
                path: path.read_bytes()
                for path in sorted(self.root.iterdir())
                if path.name not in {"memory.json", "sessions.json"}
                and not path.name.startswith(".")
                and path.is_file()
            },
            before_files,
        )
        self.assertLessEqual(threading.active_count(), threads_before)

    def test_a_projection_fault_claims_nothing_and_startup_survives(self) -> None:
        with patch(
            "cognition.CognitiveEngine.project_runtime_capabilities",
            side_effect=RuntimeError("wiring could not be observed"),
        ):
            engine, transport = self._engine()

        self.assertEqual(
            engine.runtime_capabilities, RuntimeCapabilityContext.conservative()
        )
        self.assertTrue(self._ask(engine, "What can you do?").success)
        content = transport.call_args.args[2]["messages"][0]["content"]
        self.assertNotIn("Available now:", content)
        self.assertIn("Not confirmed (do not claim):", content)

    def test_without_a_model_the_deterministic_fallback_is_unchanged(self) -> None:
        engine, transport = self._engine(config=DISABLED)

        response = self._ask(engine, "hello")

        self.assertTrue(response.success)
        transport.assert_not_called()
        self.assertIs(
            engine.runtime_capabilities.state_of(RuntimeCapability.CONVERSATION),
            RuntimeCapabilityState.UNAVAILABLE,
        )


if __name__ == "__main__":
    unittest.main()
