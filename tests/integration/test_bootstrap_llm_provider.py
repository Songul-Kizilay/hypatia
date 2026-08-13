from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.LLMConversationHistoryBuilder import (
    build_llm_conversation_history,
)
from core.Bootstrap import Bootstrap
from llm.HypatiaSystemPrompt import HYPATIA_DEFAULT_SYSTEM_PROMPT
from llm.LLMConversationMessage import LLMConversationMessage
from llm.LLMProvider import LLMProvider
from llm.LLMRuntimeConfig import LLMRuntimeConfig
from llm.OpenAICompatibleProvider import OpenAICompatibleProvider
from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCandidate import LearnedMemoryCandidateBatch
from memory.LearnedMemoryCandidatePrompt import (
    build_learned_memory_candidate_prompt,
)
from memory.LearnedMemoryStore import (
    load_latest_learned_memory,
    load_learned_memories,
)
from memory.LLMLearnedMemoryCandidateExtractor import (
    LLMLearnedMemoryCandidateExtractor,
)
from memory.NoOpLearnedMemoryCandidateExtractor import (
    NoOpLearnedMemoryCandidateExtractor,
)


class FakeLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.generate_calls = 0

    def generate(self, prompt: str) -> str:
        self.generate_calls += 1
        return "unused"


class RecordingLLMProvider(LLMProvider):
    def __init__(self, responses: list[str]) -> None:
        self._responses = iter(responses)
        self.calls: list[tuple[str, tuple[LLMConversationMessage, ...]]] = []

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
    ) -> str:
        self.calls.append((prompt, history))
        return next(self._responses)


class RecordingCandidateExtractor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def extract(self, source_text: str) -> LearnedMemoryCandidateBatch:
        self.calls.append(source_text)
        return LearnedMemoryCandidateBatch(
            source_text=source_text,
            candidates=(),
        )


class BootstrapLLMProviderTests(unittest.TestCase):
    def test_bootstrap_composes_real_llm_learning_extractor_end_to_end(
        self,
    ) -> None:
        conversation_provider = RecordingLLMProvider(["Normal answer."])
        extraction_provider = RecordingLLMProvider(
            [
                '{"candidates":[{"kind":"preference",'
                '"key":"preferred_language","value":"Python"}]}'
            ]
        )
        extractor = LLMLearnedMemoryCandidateExtractor(extraction_provider)
        source_text = "  I prefer Python for new projects.  "
        expected_memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_provider=conversation_provider,
                learned_memory_candidate_extractor=extractor,
            )
            bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)
            response = cognitive_engine.process(BrainRequest(message=source_text))
            learned_memories = load_learned_memories(cognitive_engine._memory_manager)
            latest = load_latest_learned_memory(
                cognitive_engine._memory_manager,
                kind="preference",
                key="preferred_language",
            )
            records = tuple(cognitive_engine._memory_manager.all())

        self.assertIs(
            cognitive_engine._learned_memory_candidate_extractor,
            extractor,
        )
        self.assertEqual(conversation_provider.calls, [(source_text, ())])
        self.assertEqual(
            extraction_provider.calls,
            [(build_learned_memory_candidate_prompt(source_text), ())],
        )
        self.assertTrue(response.success)
        self.assertEqual(response.message, "Normal answer.")
        self.assertEqual(learned_memories, (expected_memory,))
        self.assertEqual(latest, expected_memory)
        self.assertEqual(len(records), 2)

        learned_records = tuple(
            record for record in records if "learned" in record.tags
        )
        self.assertEqual(len(learned_records), 1)
        self.assertEqual(learned_records[0].content, "Python")
        self.assertEqual(learned_records[0].tags, {"learned", "preference"})
        self.assertEqual(
            learned_records[0].metadata,
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Python",
            },
        )
        self.assertNotIn("source_text", learned_records[0].metadata)

        conversation_records = tuple(
            record
            for record in records
            if {"brain", "conversation"}.issubset(record.tags)
        )
        self.assertEqual(len(conversation_records), 1)
        self.assertEqual(
            conversation_records[0].metadata["user_message"],
            source_text,
        )
        self.assertEqual(
            conversation_records[0].metadata["assistant_message"],
            "Normal answer.",
        )
        self.assertEqual(
            build_llm_conversation_history(
                records,
                conversation_records[0].metadata["session_id"],
                max_turns=8,
            ),
            (
                LLMConversationMessage(role="user", content=source_text),
                LLMConversationMessage(
                    role="assistant",
                    content="Normal answer.",
                ),
            ),
        )

    def test_bootstrap_passes_explicit_learning_extractor_unchanged(self) -> None:
        provider = RecordingLLMProvider(["Exact assistant response."])
        extractor = RecordingCandidateExtractor()
        source_text = "  Remember this exact source.  "

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_provider=provider,
                learned_memory_candidate_extractor=extractor,
            )
            bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)
            self.assertEqual(extractor.calls, [])
            response = cognitive_engine.process(BrainRequest(message=source_text))
            records = tuple(cognitive_engine._memory_manager.all())

        self.assertIs(
            cognitive_engine._learned_memory_candidate_extractor,
            extractor,
        )
        self.assertEqual(extractor.calls, [source_text])
        self.assertEqual(provider.calls, [(source_text, ())])
        self.assertTrue(response.success)
        self.assertEqual(response.message, "Exact assistant response.")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].tags, {"brain", "conversation"})
        self.assertEqual(records[0].metadata["user_message"], source_text)
        self.assertEqual(
            records[0].metadata["assistant_message"],
            "Exact assistant response.",
        )

    def test_bootstrap_without_learning_extractor_preserves_noop_default(
        self,
    ) -> None:
        provider = RecordingLLMProvider(["Default assistant response."])

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_provider=provider,
            )
            bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)
            response = cognitive_engine.process(
                BrainRequest(message="Default behavior.")
            )

        self.assertIsInstance(
            cognitive_engine._learned_memory_candidate_extractor,
            NoOpLearnedMemoryCandidateExtractor,
        )
        self.assertEqual(provider.calls, [("Default behavior.", ())])
        self.assertTrue(response.success)
        self.assertEqual(response.message, "Default assistant response.")

    def test_invalid_process_history_cap_fails_before_provider_activation(
        self,
    ) -> None:
        enabled_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )
        expected_message = "HYPATIA_LLM_HISTORY_MAX_TURNS must be a positive integer."

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(enabled_config, "test-api-key"),
                ),
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value=None,
                ),
                patch(
                    "core.Bootstrap.load_llm_process_history_max_turns",
                    side_effect=ValueError(expected_message),
                ),
                patch("core.Bootstrap.activate_llm") as activate_llm,
            ):
                with self.assertRaises(ValueError) as error:
                    Bootstrap.from_process_environment(
                        temporary_path / "memory.json",
                        temporary_path / "sessions.json",
                    )

        self.assertEqual(str(error.exception), expected_message)
        activate_llm.assert_not_called()

    def test_process_history_cap_affects_composed_conversation_behavior(
        self,
    ) -> None:
        enabled_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )
        provider = RecordingLLMProvider(
            ["Assistant 1", "Assistant 2", "Assistant 3", "Assistant 4"]
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(enabled_config, "test-api-key"),
                ),
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value=None,
                ),
                patch(
                    "core.Bootstrap.load_llm_process_history_max_turns",
                    return_value=2,
                ),
                patch(
                    "core.Bootstrap.activate_llm",
                    return_value=provider,
                ),
            ):
                bootstrap = Bootstrap.from_process_environment(
                    temporary_path / "memory.json",
                    temporary_path / "sessions.json",
                )
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)
            for turn in range(1, 5):
                cognitive_engine.process(BrainRequest(message=f"User {turn}"))

        self.assertEqual(
            provider.calls[-1],
            (
                "User 4",
                (
                    LLMConversationMessage(role="user", content="User 2"),
                    LLMConversationMessage(
                        role="assistant",
                        content="Assistant 2",
                    ),
                    LLMConversationMessage(role="user", content="User 3"),
                    LLMConversationMessage(
                        role="assistant",
                        content="Assistant 3",
                    ),
                ),
            ),
        )

    def test_process_history_cap_reaches_cognitive_engine_unchanged(self) -> None:
        disabled_config = LLMRuntimeConfig(enabled=False, base_url="", model="")

        for loaded_value, expected_value in ((3, 3), (None, 8)):
            with self.subTest(loaded_value=loaded_value):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    temporary_path = Path(temporary_directory)

                    with (
                        patch(
                            "core.Bootstrap.load_llm_process_environment_settings",
                            return_value=(disabled_config, None),
                        ),
                        patch(
                            "core.Bootstrap.load_llm_process_system_prompt",
                            return_value=None,
                        ),
                        patch(
                            "core.Bootstrap.load_llm_process_history_max_turns",
                            return_value=loaded_value,
                        ) as history_loader,
                    ):
                        bootstrap = Bootstrap.from_process_environment(
                            temporary_path / "memory.json",
                            temporary_path / "sessions.json",
                        )
                        bootstrap.initialize()

                    cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

                history_loader.assert_called_once_with()
                self.assertEqual(
                    cognitive_engine._llm_history_max_turns,
                    expected_value,
                )

    def test_process_environment_factory_activates_and_passes_provider_to_cognition(
        self,
    ) -> None:
        sentinel_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )
        sentinel_provider = Mock(spec=LLMProvider)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            memory_path = temporary_path / "memory.json"
            session_path = temporary_path / "sessions.json"

            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(sentinel_config, "test-api-key"),
                ) as settings_loader,
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value="  Custom prompt.  ",
                ) as system_prompt_loader,
                patch(
                    "core.Bootstrap.activate_llm",
                    return_value=sentinel_provider,
                ) as activate_llm,
            ):
                bootstrap = Bootstrap.from_process_environment(
                    memory_path,
                    session_path,
                )
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        settings_loader.assert_called_once_with()
        system_prompt_loader.assert_called_once_with()
        activate_llm.assert_called_once_with(
            sentinel_config,
            "test-api-key",
            system_prompt="  Custom prompt.  ",
        )
        self.assertIs(cognitive_engine._llm_provider, sentinel_provider)
        sentinel_provider.generate.assert_not_called()

    def test_process_environment_factory_uses_default_system_prompt_when_absent(
        self,
    ) -> None:
        sentinel_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )
        sentinel_provider = Mock(spec=LLMProvider)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)

            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(sentinel_config, "test-api-key"),
                ) as settings_loader,
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value=None,
                ) as system_prompt_loader,
                patch(
                    "core.Bootstrap.activate_llm",
                    return_value=sentinel_provider,
                ) as activate_llm,
            ):
                bootstrap = Bootstrap.from_process_environment(
                    temporary_path / "memory.json",
                    temporary_path / "sessions.json",
                )
                bootstrap.initialize()

        settings_loader.assert_called_once_with()
        system_prompt_loader.assert_called_once_with()
        self.assertEqual(
            bootstrap._llm_system_prompt,
            HYPATIA_DEFAULT_SYSTEM_PROMPT,
        )
        activate_llm.assert_called_once_with(
            sentinel_config,
            "test-api-key",
            system_prompt=HYPATIA_DEFAULT_SYSTEM_PROMPT,
        )

    def test_default_system_prompt_reaches_the_composed_provider(self) -> None:
        sentinel_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)

            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(sentinel_config, "test-api-key"),
                ),
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value=None,
                ),
            ):
                bootstrap = Bootstrap.from_process_environment(
                    temporary_path / "memory.json",
                    temporary_path / "sessions.json",
                )
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        provider = cognitive_engine._llm_provider
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(
            provider._system_prompt,
            HYPATIA_DEFAULT_SYSTEM_PROMPT,
        )

    def test_default_system_prompt_precedes_unchanged_turkish_user_prompt(
        self,
    ) -> None:
        sentinel_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)

            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(sentinel_config, "test-api-key"),
                ),
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value=None,
                ),
            ):
                bootstrap = Bootstrap.from_process_environment(
                    temporary_path / "memory.json",
                    temporary_path / "sessions.json",
                )
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        provider = cognitive_engine._llm_provider
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        transport = Mock(
            return_value={
                "choices": [{"message": {"content": "Merhaba!"}}],
            }
        )
        provider._transport = transport

        result = provider.generate("Merhaba Hypatia, bugün nasılsın?")

        self.assertEqual(result, "Merhaba!")
        transport.assert_called_once_with(
            "https://api.example.test/v1/chat/completions",
            {"Authorization": "Bearer test-api-key"},
            {
                "model": "test-model",
                "messages": [
                    {
                        "role": "system",
                        "content": HYPATIA_DEFAULT_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": "Merhaba Hypatia, bugün nasılsın?",
                    },
                ],
            },
        )

    def test_default_system_prompt_precedes_unchanged_english_user_prompt(
        self,
    ) -> None:
        sentinel_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)

            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(sentinel_config, "test-api-key"),
                ),
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value=None,
                ),
            ):
                bootstrap = Bootstrap.from_process_environment(
                    temporary_path / "memory.json",
                    temporary_path / "sessions.json",
                )
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        provider = cognitive_engine._llm_provider
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        transport = Mock(
            return_value={
                "choices": [{"message": {"content": "Hello!"}}],
            }
        )
        provider._transport = transport

        result = provider.generate("Hello Hypatia, how are you today?")

        self.assertEqual(result, "Hello!")
        transport.assert_called_once_with(
            "https://api.example.test/v1/chat/completions",
            {"Authorization": "Bearer test-api-key"},
            {
                "model": "test-model",
                "messages": [
                    {
                        "role": "system",
                        "content": HYPATIA_DEFAULT_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": "Hello Hypatia, how are you today?",
                    },
                ],
            },
        )

    def test_invalid_llm_response_does_not_persist_conversation_memory(
        self,
    ) -> None:
        enabled_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(enabled_config, "test-api-key"),
                ),
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value=None,
                ),
            ):
                bootstrap = Bootstrap.from_process_environment(
                    temporary_path / "memory.json",
                    temporary_path / "sessions.json",
                )
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)
            cognitive_engine._session_manager.create("work-1")
            cognitive_engine._memory_manager.add(
                "User: Prior successful turn.\nHypatia: Prior answer.",
                metadata={
                    "session_id": "work-1",
                    "user_message": "Prior successful turn.",
                    "assistant_message": "Prior answer.",
                },
                tags={"brain", "conversation"},
            )
            memory_before = cognitive_engine._memory_manager.snapshot()

            provider = cognitive_engine._llm_provider
            self.assertIsInstance(provider, OpenAICompatibleProvider)
            transport = Mock(
                side_effect=[
                    {"choices": [{"message": {"content": None}}]},
                    {"choices": [{"message": {"content": "Recovered answer."}}]},
                    {"choices": [{"message": {"content": "Continued answer."}}]},
                ]
            )
            provider._transport = transport

            response = cognitive_engine.process(
                BrainRequest(
                    message="Remember this failed turn.",
                    metadata={"session_id": "work-1"},
                )
            )

            self.assertFalse(response.success)
            self.assertEqual(response.message, "LLM response invalid.")
            transport.assert_called_once()
            self.assertEqual(
                cognitive_engine._memory_manager.snapshot(),
                memory_before,
            )
            self.assertNotIn(
                "Remember this failed turn.",
                {
                    record.metadata.get("user_message")
                    for record in cognitive_engine._memory_manager.all()
                    if {"brain", "conversation"}.issubset(record.tags)
                },
            )

            recovery_response = cognitive_engine.process(
                BrainRequest(
                    message="What do you remember?",
                    metadata={"session_id": "work-1"},
                )
            )

            self.assertTrue(recovery_response.success)
            self.assertEqual(recovery_response.message, "Recovered answer.")
            self.assertEqual(transport.call_count, 2)
            self.assertEqual(
                transport.call_args_list[1].args[2]["messages"],
                [
                    {
                        "role": "system",
                        "content": HYPATIA_DEFAULT_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": "Prior successful turn.",
                    },
                    {
                        "role": "assistant",
                        "content": "Prior answer.",
                    },
                    {
                        "role": "user",
                        "content": "What do you remember?",
                    },
                ],
            )

            continuation_response = cognitive_engine.process(
                BrainRequest(
                    message="Continue please.",
                    metadata={"session_id": "work-1"},
                )
            )

            self.assertTrue(continuation_response.success)
            self.assertEqual(continuation_response.message, "Continued answer.")
            self.assertEqual(transport.call_count, 3)
            self.assertEqual(
                transport.call_args_list[2].args[2]["messages"],
                [
                    {
                        "role": "system",
                        "content": HYPATIA_DEFAULT_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": "Prior successful turn.",
                    },
                    {
                        "role": "assistant",
                        "content": "Prior answer.",
                    },
                    {
                        "role": "user",
                        "content": "What do you remember?",
                    },
                    {
                        "role": "assistant",
                        "content": "Recovered answer.",
                    },
                    {
                        "role": "user",
                        "content": "Continue please.",
                    },
                ],
            )

    def test_process_environment_factory_preserves_loaded_settings(self) -> None:
        sentinel_config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            memory_path = temporary_path / "memory.json"
            session_path = temporary_path / "sessions.json"

            with (
                patch(
                    "core.Bootstrap.load_llm_process_environment_settings",
                    return_value=(sentinel_config, "test-api-key"),
                ) as settings_loader,
                patch(
                    "core.Bootstrap.load_llm_process_system_prompt",
                    return_value="You are Hypatia.",
                ) as system_prompt_loader,
                patch("core.Bootstrap.activate_llm") as activate_llm,
            ):
                bootstrap = Bootstrap.from_process_environment(
                    memory_path,
                    session_path,
                )

        settings_loader.assert_called_once_with()
        system_prompt_loader.assert_called_once_with()
        self.assertIs(bootstrap._llm_config, sentinel_config)
        self.assertEqual(bootstrap._llm_api_key, "test-api-key")
        self.assertEqual(bootstrap._llm_system_prompt, "You are Hypatia.")
        self.assertIs(bootstrap._memory_path, memory_path)
        self.assertIs(bootstrap._session_path, session_path)
        activate_llm.assert_not_called()

    def test_bootstrap_passes_the_supplied_provider_to_cognitive_engine(self) -> None:
        provider = FakeLLMProvider()

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_provider=provider,
            )
            bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        self.assertIs(cognitive_engine._llm_provider, provider)
        self.assertEqual(provider.generate_calls, 0)

    def test_disabled_config_keeps_the_cognitive_engine_provider_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=LLMRuntimeConfig(
                    enabled=False,
                    base_url="https://api.example.test/v1/chat/completions",
                    model="test-model",
                ),
            )

            with patch("llm.LLMRuntimeActivator.activate_llm") as activate_llm:
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        self.assertIsNone(cognitive_engine._llm_provider)
        activate_llm.assert_not_called()

    def test_enabled_config_activates_and_passes_the_provider_to_cognition(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )
        sentinel_provider = Mock(spec=LLMProvider)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="test-api-key",
            )

            with patch(
                "core.Bootstrap.activate_llm",
                return_value=sentinel_provider,
            ) as activate_llm:
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        activate_llm.assert_called_once_with(
            config,
            "test-api-key",
            system_prompt=None,
        )
        self.assertIs(cognitive_engine._llm_provider, sentinel_provider)
        sentinel_provider.generate.assert_not_called()

    def test_enabled_config_forwards_system_prompt_unchanged(self) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )
        sentinel_provider = Mock(spec=LLMProvider)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="test-api-key",
                llm_system_prompt="You are Hypatia.",
            )

            with patch(
                "core.Bootstrap.activate_llm",
                return_value=sentinel_provider,
            ) as activate_llm:
                bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        activate_llm.assert_called_once_with(
            config,
            "test-api-key",
            system_prompt="You are Hypatia.",
        )
        self.assertIs(cognitive_engine._llm_provider, sentinel_provider)
        sentinel_provider.generate.assert_not_called()

    def test_enabled_config_without_an_api_key_fails_before_activation(self) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
            )

            with patch("core.Bootstrap.activate_llm") as activate_llm:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^LLM API key is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()

    def test_enabled_config_with_an_empty_api_key_fails_before_activation(self) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="",
            )

            with patch("core.Bootstrap.activate_llm") as activate_llm:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^LLM API key is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()

    def test_enabled_config_with_a_whitespace_only_api_key_fails_before_activation(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="   ",
            )

            with patch("core.Bootstrap.activate_llm") as activate_llm:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^LLM API key is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()

    def test_enabled_config_with_an_empty_base_url_fails_before_activation(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="test-api-key",
            )

            with patch("core.Bootstrap.activate_llm") as activate_llm:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^LLM base URL is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()

    def test_enabled_config_with_a_whitespace_only_base_url_fails_before_activation(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="   ",
            model="test-model",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="test-api-key",
            )

            with patch("core.Bootstrap.activate_llm") as activate_llm:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^LLM base URL is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()

    def test_enabled_config_with_an_empty_model_fails_before_activation(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="test-api-key",
            )

            with patch("core.Bootstrap.activate_llm") as activate_llm:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^LLM model is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()

    def test_enabled_config_with_a_whitespace_only_model_fails_before_activation(
        self,
    ) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="   ",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_config=config,
                llm_api_key="test-api-key",
            )

            with patch("core.Bootstrap.activate_llm") as activate_llm:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^LLM model is required when LLM is enabled\\.$",
                ):
                    bootstrap.initialize()

        activate_llm.assert_not_called()
