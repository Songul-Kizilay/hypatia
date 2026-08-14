"""Unit tests for the first CognitiveEngine implementation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import planner
import response

source_planner_dir = str(SRC_DIR / "planner")
if source_planner_dir not in planner.__path__:
    planner.__path__.append(source_planner_dir)

source_response_dir = str(SRC_DIR / "response")
if source_response_dir not in response.__path__:
    response.__path__.append(source_response_dir)

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine as ProductionCognitiveEngine
from core.Exceptions import (
    KnowledgeError,
    MemoryError,
    PlannerError,
    SessionDeleteEventError,
)
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from llm.LLMConversationMessage import LLMConversationMessage
from llm.LLMProvider import LLMError
from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCandidate import (
    LearnedMemoryCandidate,
    LearnedMemoryCandidateBatch,
)
from memory.LearnedMemoryCandidateExtractionError import (
    LearnedMemoryCandidateExtractionError,
)
from memory.LearnedMemoryCandidateExtractor import LearnedMemoryCandidateExtractor
from memory.LearnedMemoryContext import (
    build_learned_memory_augmented_prompt,
    build_learned_memory_context,
    load_bounded_learned_memory_context,
    load_learned_memory_context,
)
from memory.LearnedMemorySelector import LearnedMemorySelector
from memory.LearnedMemoryStore import (
    append_learned_memory,
    load_latest_learned_memory,
    load_learned_memories,
)
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord
from memory.NoOpLearnedMemoryCandidateExtractor import (
    NoOpLearnedMemoryCandidateExtractor,
)
from memory.SessionMemoryPolicy import SessionMemoryPolicy
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.SessionDeleteExecutionResult import SessionDeleteExecutionResult
from session.SessionDeleteService import SessionDeleteService
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService
from session.SessionStore import SessionStore


class StubSessionRenameService:
    """Fails tests that accidentally route an unrelated request to rename."""

    def rename(self, source_session_id: str, target_session_id: str) -> object:
        raise AssertionError("Session rename service must not be called in this test.")


class CognitiveEngine(ProductionCognitiveEngine):
    """Test harness that supplies the required rename dependency when omitted."""

    def __init__(self, *args: object) -> None:
        if len(args) == 6:
            super().__init__(*args, StubSessionRenameService())  # type: ignore[arg-type]
            return
        super().__init__(*args)  # type: ignore[arg-type]


class FailingKnowledgeEngine:
    """Minimal failure double for KnowledgeError handling coverage."""

    def search(self, query: str) -> list[object]:
        raise KnowledgeError("Knowledge is unavailable.")


class FailingMemoryManager:
    """Minimal failure double that preserves search response behavior."""

    def add(self, *args: object, **kwargs: object) -> None:
        raise MemoryError("Memory is unavailable.")


class RecallSearchMustNotRunMemoryManager:
    """Minimal double that fails if invalid recall attempts a memory search."""

    def search(self, *args: object, **kwargs: object) -> list[MemoryRecord]:
        raise AssertionError("Recall search must not run.")


class RecentConversationsMustNotReadMemoryManager:
    """Minimal double that fails when an invalid request reads memory."""

    def all(self) -> list[MemoryRecord]:
        raise AssertionError("Recent conversations must not read memory.")


class KnowledgeSearchMustNotRun:
    """Minimal double that fails when conversation search reaches knowledge."""

    def search(self, query: str) -> list[object]:
        raise AssertionError("Knowledge search must not run.")


class RecordingConversationSearchMemoryManager:
    """Minimal double that preserves a caller-provided relevance order."""

    def __init__(self, records: list[MemoryRecord]) -> None:
        self.records = records
        self.calls: list[tuple[str, int | None]] = []

    def search(self, query: str, *, limit: int | None) -> list[MemoryRecord]:
        self.calls.append((query, limit))
        return list(self.records)


class SessionSearchMustNotReadMemoryManager:
    """Minimal double that fails if invalid session search reads memory."""

    def all(self) -> list[MemoryRecord]:
        raise AssertionError("Session search must not read all memory records.")

    def search(self, *args: object, **kwargs: object) -> list[MemoryRecord]:
        raise AssertionError("Invalid session search must not run.")


class SessionActivityMustNotReadMemoryManager:
    """Minimal double that fails if invalid session activity reads memory."""

    def all(self) -> list[MemoryRecord]:
        raise AssertionError(
            "Invalid session activity must not read all memory records."
        )

    def search(self, *args: object, **kwargs: object) -> list[MemoryRecord]:
        raise AssertionError("Invalid session activity must not run a memory search.")


class RecordingSessionOverviewMemoryManager:
    """Minimal double that records read-only session overview access."""

    def __init__(self, records: list[MemoryRecord]) -> None:
        self.records = records
        self.all_calls = 0

    def all(self) -> list[MemoryRecord]:
        self.all_calls += 1
        return list(self.records)


class SessionOverviewMustNotResolveEngine(CognitiveEngine):
    """Fails the test if session overview attempts request-level resolution."""

    def _resolve_session_id(self, request: BrainRequest) -> str:
        raise AssertionError("Session overview must not resolve a session ID.")


class SessionDetailsMustNotResolveEngine(CognitiveEngine):
    """Fails the test if session details attempts request-level resolution."""

    def _resolve_session_id(self, request: BrainRequest) -> str:
        raise AssertionError("Session details must not resolve a session ID.")


class SessionRecentMustNotResolveEngine(CognitiveEngine):
    """Fails the test if session recent attempts request-level resolution."""

    def _resolve_session_id(self, request: BrainRequest) -> str:
        raise AssertionError("Session recent must not resolve a session ID.")


class SessionSearchMustNotResolveEngine(CognitiveEngine):
    """Fails the test if session search attempts request-level resolution."""

    def _resolve_session_id(self, request: BrainRequest) -> str:
        raise AssertionError("Session search must not resolve a session ID.")


class SessionActivityMustNotResolveEngine(CognitiveEngine):
    """Fails the test if session activity attempts request-level resolution."""

    def _resolve_session_id(self, request: BrainRequest) -> str:
        raise AssertionError("Session activity must not resolve a session ID.")


class FailingPlanner:
    """Minimal failure double for PlannerError handling coverage."""

    def create_plan(self, goal: str) -> None:
        raise PlannerError("Planner is unavailable.")


class RecordingLLMProvider:
    """Records accidental LLM calls from the existing conversation flow."""

    def __init__(self, response: str) -> None:
        self.calls: list[tuple[str, tuple[LLMConversationMessage, ...]]] = []
        self.response = response

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
    ) -> str:
        self.calls.append((prompt, history))
        return self.response


class FailingLLMProvider:
    """Raises the provider boundary's controlled generation error."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[LLMConversationMessage, ...]]] = []

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
    ) -> str:
        self.calls.append((prompt, history))
        raise LLMError("Generation unavailable.")


class RecordingCandidateExtractor:
    """Records accidental extraction calls without producing candidates."""

    def __init__(
        self,
        batch: LearnedMemoryCandidateBatch | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.batch = batch

    def extract(self, source_text: str) -> LearnedMemoryCandidateBatch:
        self.calls.append(source_text)
        if self.batch is not None:
            return self.batch
        return LearnedMemoryCandidateBatch(
            source_text=source_text,
            candidates=(),
        )


class RecordingLearnedMemorySelector:
    """Records exact request-specific learned-memory selection inputs."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[LearnedMemory, ...]]] = []

    def select(
        self,
        *,
        source_text: str,
        memories: tuple[LearnedMemory, ...],
    ) -> tuple[LearnedMemory, ...]:
        self.calls.append((source_text, memories))
        return memories


class RecordingCandidateSequenceExtractor:
    """Returns caller-supplied candidate batches in exact call order."""

    def __init__(self, batches: tuple[LearnedMemoryCandidateBatch, ...]) -> None:
        self.calls: list[str] = []
        self.batches = batches

    def extract(self, source_text: str) -> LearnedMemoryCandidateBatch:
        batch = self.batches[len(self.calls)]
        self.calls.append(source_text)
        return batch


class FailingCandidateExtractor:
    """Records extraction calls before raising a caller-supplied error."""

    def __init__(self, error: Exception) -> None:
        self.calls: list[str] = []
        self.error = error

    def extract(self, source_text: str) -> LearnedMemoryCandidateBatch:
        self.calls.append(source_text)
        raise self.error


class CognitiveEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        path = Path(self.temporary_directory.name) / "knowledge.md"
        path.write_text("Hypatia\n\nKnowledge\n\nHypatia", encoding="utf-8")
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(path)
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.planner = Planner()
        self.response_composer = ResponseComposer()
        self.session_manager = SessionManager(self.event_bus)
        self.session_manager.create("work-1")
        self.session_manager.create("personal")
        self.session_rename_service = SessionRenameTransactionService(
            session_manager=self.session_manager,
            memory_manager=self.memory_manager,
            event_bus=self.event_bus,
        )
        self.engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_search_intent_returns_a_successful_response(self) -> None:
        response = self.engine.process(BrainRequest(message="search hypatia"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "search")

    def test_session_delete_service_uses_the_engine_manager_boundaries(self) -> None:
        service = self.engine._session_delete_service

        self.assertIsInstance(service, SessionDeleteService)
        self.assertIs(service._session_manager, self.session_manager)
        self.assertIs(service._memory_manager, self.memory_manager)

    def test_defaults_learning_candidate_extractor_to_no_op(self) -> None:
        self.assertIsInstance(
            self.engine._learned_memory_candidate_extractor,
            NoOpLearnedMemoryCandidateExtractor,
        )

    def test_preserves_explicit_learning_candidate_extractor_without_calling_it(
        self,
    ) -> None:
        recording_extractor = RecordingCandidateExtractor()
        extractor: LearnedMemoryCandidateExtractor = recording_extractor
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            learned_memory_candidate_extractor=extractor,
        )

        response = engine.process(BrainRequest(message="Hello"))

        self.assertTrue(response.success)
        self.assertIs(engine._learned_memory_candidate_extractor, extractor)
        self.assertEqual(recording_extractor.calls, [])

    def test_session_manager_is_a_required_cognitive_engine_dependency(self) -> None:
        with self.assertRaises(TypeError):
            ProductionCognitiveEngine(  # type: ignore[call-arg]
                self.knowledge_engine,
                self.memory_manager,
                self.planner,
                self.event_bus,
                self.response_composer,
            )

    def test_session_rename_service_is_a_required_cognitive_engine_dependency(
        self,
    ) -> None:
        with self.assertRaises(TypeError):
            ProductionCognitiveEngine(  # type: ignore[call-arg]
                self.knowledge_engine,
                self.memory_manager,
                self.planner,
                self.event_bus,
                self.response_composer,
                self.session_manager,
            )

    def test_message_uses_an_injected_llm_provider(self) -> None:
        llm_provider = RecordingLLMProvider("Nice to meet you.")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
        )
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        request = BrainRequest(
            message="  My name is Songül.  ",
            request_id="request-123",
        )

        response = engine.process(request)

        self.assertTrue(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "message")
        self.assertEqual(response.message, "Nice to meet you.")
        self.assertEqual(
            llm_provider.calls,
            [("  My name is Songül.  ", ())],
        )
        record = self.memory_manager.all()[0]
        self.assertEqual(
            record.content,
            "User:   My name is Songül.  \nHypatia: Nice to meet you.",
        )
        self.assertEqual(
            record.metadata,
            {
                "request_id": "request-123",
                "intent": "message",
                "session_id": "default",
                "user_message": "  My name is Songül.  ",
                "assistant_message": "Nice to meet you.",
            },
        )
        self.assertEqual(record.tags, frozenset({"brain", "conversation"}))
        self.assertEqual(
            events,
            [
                "brain.request.received",
                "brain.intent.detected",
                "memory.record.added",
                "brain.response.ready",
            ],
        )

    def test_message_augments_only_provider_prompt_with_learned_memory(
        self,
    ) -> None:
        message = "  What language do I prefer?  "
        provider_response = "You prefer Rust."
        llm_provider = RecordingLLMProvider(provider_response)
        recording_extractor = RecordingCandidateExtractor()
        learned_memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        self.memory_manager.add(
            "User: Earlier question\nHypatia: Earlier answer",
            metadata={
                "session_id": "default",
                "user_message": "Earlier question",
                "assistant_message": "Earlier answer",
            },
            tags={"brain", "conversation"},
        )
        learned_record = append_learned_memory(
            self.memory_manager,
            learned_memory,
        )
        learned_context = load_learned_memory_context(self.memory_manager)
        expected_prompt = build_learned_memory_augmented_prompt(
            user_message=message,
            learned_memory_context=learned_context,
        )
        expected_history = (
            LLMConversationMessage(role="user", content="Earlier question"),
            LLMConversationMessage(role="assistant", content="Earlier answer"),
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
        )

        with (
            patch(
                "cognition.CognitiveEngine.load_learned_memory_context",
                wraps=load_learned_memory_context,
            ) as load_context,
            patch(
                "cognition.CognitiveEngine.load_bounded_learned_memory_context",
                wraps=load_bounded_learned_memory_context,
            ) as load_bounded_context,
            patch(
                "cognition.CognitiveEngine.build_learned_memory_augmented_prompt",
                wraps=build_learned_memory_augmented_prompt,
            ) as build_prompt,
        ):
            response = engine.process(BrainRequest(message=message))

        self.assertTrue(response.success)
        self.assertEqual(response.message, provider_response)
        load_context.assert_called_once_with(self.memory_manager)
        load_bounded_context.assert_not_called()
        build_prompt.assert_called_once_with(
            user_message=message,
            learned_memory_context=learned_context,
        )
        self.assertEqual(llm_provider.calls, [(expected_prompt, expected_history)])
        self.assertEqual(recording_extractor.calls, [message])
        self.assertEqual(load_learned_memories(self.memory_manager), (learned_memory,))
        records = self.memory_manager.all()
        self.assertIs(
            next(record for record in records if "learned" in record.tags),
            learned_record,
        )
        conversation_records = tuple(
            record for record in records if "conversation" in record.tags
        )
        self.assertEqual(len(conversation_records), 2)
        self.assertEqual(conversation_records[-1].metadata["user_message"], message)
        self.assertNotIn(expected_prompt, conversation_records[-1].content)

    def test_explicit_limit_uses_only_exact_bounded_context_for_provider(self) -> None:
        message = "  What language do I prefer?  "
        bounded_context = "".join(("bounded", "-context"))
        provider_prompt = "".join(("provider", "-prompt"))
        provider_response = "You prefer Rust."
        llm_provider = RecordingLLMProvider(provider_response)
        recording_extractor = RecordingCandidateExtractor()
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
            learned_memory_context_limit=2,
        )

        with (
            patch(
                "cognition.CognitiveEngine.load_learned_memory_context",
            ) as load_context,
            patch(
                "cognition.CognitiveEngine.load_bounded_learned_memory_context",
                return_value=bounded_context,
            ) as load_bounded_context,
            patch(
                "cognition.CognitiveEngine.build_learned_memory_augmented_prompt",
                return_value=provider_prompt,
            ) as build_prompt,
        ):
            response = engine.process(BrainRequest(message=message))

        load_context.assert_not_called()
        load_bounded_context.assert_called_once_with(self.memory_manager, 2)
        build_prompt.assert_called_once_with(
            user_message=message,
            learned_memory_context=bounded_context,
        )
        self.assertEqual(llm_provider.calls, [(provider_prompt, ())])
        self.assertEqual(recording_extractor.calls, [message])
        self.assertEqual(response.message, provider_response)
        conversation_record = self.memory_manager.all()[-1]
        self.assertEqual(conversation_record.metadata["user_message"], message)
        self.assertEqual(
            conversation_record.content,
            f"User: {message}\nHypatia: {provider_response}",
        )

    def test_explicit_selector_uses_only_exact_selected_context_for_provider(
        self,
    ) -> None:
        message = "  What language do I prefer?  "
        selected_context = "selected-context"
        provider_prompt = "provider-prompt"
        provider_response = "You prefer Rust."
        llm_provider = RecordingLLMProvider(provider_response)
        recording_extractor = RecordingCandidateExtractor()
        selector: LearnedMemorySelector = RecordingLearnedMemorySelector()
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
            learned_memory_selector=selector,
        )

        with (
            patch(
                "cognition.CognitiveEngine.load_learned_memory_context",
            ) as load_context,
            patch(
                "cognition.CognitiveEngine.load_bounded_learned_memory_context",
            ) as load_bounded_context,
            patch(
                "cognition.CognitiveEngine.load_current_selected_learned_memory_context",
                return_value=selected_context,
            ) as load_selected_context,
            patch(
                "cognition.CognitiveEngine."
                "load_current_selected_bounded_learned_memory_context",
            ) as load_selected_bounded_context,
            patch(
                "cognition.CognitiveEngine.build_learned_memory_augmented_prompt",
                return_value=provider_prompt,
            ) as build_prompt,
        ):
            response = engine.process(BrainRequest(message=message))

        load_context.assert_not_called()
        load_bounded_context.assert_not_called()
        load_selected_context.assert_called_once_with(
            memory_manager=self.memory_manager,
            source_text=message,
            selector=selector,
        )
        load_selected_bounded_context.assert_not_called()
        build_prompt.assert_called_once_with(
            user_message=message,
            learned_memory_context=selected_context,
        )
        self.assertEqual(llm_provider.calls, [(provider_prompt, ())])
        self.assertEqual(recording_extractor.calls, [message])
        self.assertEqual(response.message, provider_response)
        conversation_record = self.memory_manager.all()[-1]
        self.assertEqual(conversation_record.metadata["user_message"], message)

    def test_explicit_selector_and_limit_use_only_exact_selected_bounded_context(
        self,
    ) -> None:
        message = "  What language do I prefer?  "
        selected_context = "selected-bounded-context"
        provider_prompt = "provider-prompt"
        provider_response = "You prefer Rust."
        llm_provider = RecordingLLMProvider(provider_response)
        recording_extractor = RecordingCandidateExtractor()
        selector: LearnedMemorySelector = RecordingLearnedMemorySelector()
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
            learned_memory_context_limit=2,
            learned_memory_selector=selector,
        )

        with (
            patch(
                "cognition.CognitiveEngine.load_learned_memory_context",
            ) as load_context,
            patch(
                "cognition.CognitiveEngine.load_bounded_learned_memory_context",
            ) as load_bounded_context,
            patch(
                "cognition.CognitiveEngine.load_current_selected_learned_memory_context",
            ) as load_selected_context,
            patch(
                "cognition.CognitiveEngine."
                "load_current_selected_bounded_learned_memory_context",
                return_value=selected_context,
            ) as load_selected_bounded_context,
            patch(
                "cognition.CognitiveEngine.build_learned_memory_augmented_prompt",
                return_value=provider_prompt,
            ) as build_prompt,
        ):
            response = engine.process(BrainRequest(message=message))

        load_context.assert_not_called()
        load_bounded_context.assert_not_called()
        load_selected_context.assert_not_called()
        load_selected_bounded_context.assert_called_once_with(
            memory_manager=self.memory_manager,
            source_text=message,
            selector=selector,
            limit=2,
        )
        build_prompt.assert_called_once_with(
            user_message=message,
            learned_memory_context=selected_context,
        )
        self.assertEqual(llm_provider.calls, [(provider_prompt, ())])
        self.assertEqual(recording_extractor.calls, [message])
        self.assertEqual(response.message, provider_response)
        conversation_record = self.memory_manager.all()[-1]
        self.assertEqual(conversation_record.metadata["user_message"], message)

    def test_zero_learned_memory_context_limit_is_forwarded_exactly(self) -> None:
        llm_provider = RecordingLLMProvider("No context needed.")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_context_limit=0,
        )

        with (
            patch(
                "cognition.CognitiveEngine.load_learned_memory_context",
            ) as load_context,
            patch(
                "cognition.CognitiveEngine.load_bounded_learned_memory_context",
                return_value="",
            ) as load_bounded_context,
        ):
            response = engine.process(BrainRequest(message="Explain bounded memory"))

        load_context.assert_not_called()
        load_bounded_context.assert_called_once_with(self.memory_manager, 0)
        self.assertTrue(response.success)
        self.assertEqual(llm_provider.calls, [("Explain bounded memory", ())])

    def test_negative_learned_memory_context_limit_reaches_bounded_loader(
        self,
    ) -> None:
        llm_provider = RecordingLLMProvider("Must not run.")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_context_limit=-1,
        )

        with (
            patch(
                "cognition.CognitiveEngine.load_learned_memory_context",
            ) as load_context,
            patch(
                "cognition.CognitiveEngine.load_bounded_learned_memory_context",
                side_effect=ValueError("Learned memory limit must be non-negative."),
            ) as load_bounded_context,
            self.assertRaisesRegex(
                ValueError,
                r"^Learned memory limit must be non-negative\.$",
            ),
        ):
            engine.process(BrainRequest(message="Explain bounded memory"))

        load_context.assert_not_called()
        load_bounded_context.assert_called_once_with(self.memory_manager, -1)
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(self.memory_manager.all(), [])

    def test_successful_llm_message_invokes_candidate_extractor_once(self) -> None:
        llm_provider = RecordingLLMProvider("I will remember that later.")
        recording_extractor = RecordingCandidateExtractor()
        message = "  Ben kahveyi şekersiz içerim.  "
        candidate = LearnedMemoryCandidate(
            memory=LearnedMemory(
                kind="preference",
                key="preferred_language",
                value="Python",
            ),
            source_text=message,
        )
        batch = LearnedMemoryCandidateBatch(
            source_text=message,
            candidates=(candidate,),
        )
        recording_extractor.batch = batch
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
        )

        with patch(
            "cognition.CognitiveEngine.persist_learned_memory_candidate_batch"
        ) as persist:
            response = engine.process(BrainRequest(message=message))

        self.assertTrue(response.success)
        self.assertEqual(response.message, "I will remember that later.")
        self.assertEqual(recording_extractor.calls, [message])
        persist.assert_called_once_with(self.memory_manager, batch)
        self.assertEqual(llm_provider.calls, [(message, ())])

    def test_learning_failure_preserves_successful_conversation_and_history(
        self,
    ) -> None:
        llm_provider = RecordingLLMProvider("The conversation succeeded.")
        extraction_error = LearnedMemoryCandidateExtractionError(
            "Learned memory candidate extraction failed."
        )
        extractor = FailingCandidateExtractor(extraction_error)
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=extractor,
        )
        first_message = "  Remember this exact text.  "
        second_message = "What did we discuss?"

        with patch(
            "cognition.CognitiveEngine.persist_learned_memory_candidate_batch"
        ) as persist:
            first_response = engine.process(BrainRequest(message=first_message))

            self.assertTrue(first_response.success)
            self.assertEqual(first_response.message, "The conversation succeeded.")
            self.assertEqual(extractor.calls, [first_message])
            persist.assert_not_called()
            first_records = tuple(self.memory_manager.all())
            self.assertEqual(len(first_records), 1)
            self.assertEqual(
                first_records[0].tags, frozenset({"brain", "conversation"})
            )
            self.assertEqual(
                first_records[0].metadata,
                {
                    "request_id": first_response.request_id,
                    "intent": "message",
                    "session_id": "default",
                    "user_message": first_message,
                    "assistant_message": "The conversation succeeded.",
                },
            )

            second_response = engine.process(BrainRequest(message=second_message))

        self.assertTrue(second_response.success)
        self.assertEqual(extractor.calls, [first_message, second_message])
        persist.assert_not_called()
        records = tuple(self.memory_manager.all())
        self.assertEqual(len(records), 2)
        self.assertTrue(
            all(
                record.tags == frozenset({"brain", "conversation"})
                for record in records
            )
        )
        first_turn = (
            LLMConversationMessage(role="user", content=first_message),
            LLMConversationMessage(
                role="assistant",
                content="The conversation succeeded.",
            ),
        )
        self.assertEqual(
            llm_provider.calls,
            [
                (first_message, ()),
                (second_message, first_turn),
            ],
        )
        self.assertEqual(load_learned_memories(self.memory_manager), ())

    def test_unrelated_extraction_error_escapes_unchanged(self) -> None:
        llm_provider = RecordingLLMProvider("The conversation succeeded.")
        unexpected_error = RuntimeError("unexpected")
        extractor = FailingCandidateExtractor(unexpected_error)
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=extractor,
        )

        with self.assertRaises(RuntimeError) as context:
            engine.process(BrainRequest(message="exact message"))

        self.assertIs(context.exception, unexpected_error)
        self.assertEqual(extractor.calls, ["exact message"])

    def test_successful_llm_message_persists_extracted_learned_memory(self) -> None:
        llm_provider = RecordingLLMProvider("I will remember that.")
        message = "  Ben Python tercih ediyorum.  "
        learned_memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        candidate = LearnedMemoryCandidate(
            memory=learned_memory,
            source_text=message,
        )
        batch = LearnedMemoryCandidateBatch(
            source_text=message,
            candidates=(candidate,),
        )
        recording_extractor = RecordingCandidateExtractor(batch)
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
        )

        response = engine.process(BrainRequest(message=message))

        self.assertTrue(response.success)
        self.assertEqual(response.message, "I will remember that.")
        self.assertEqual(recording_extractor.calls, [message])
        self.assertEqual(load_learned_memories(self.memory_manager), (learned_memory,))
        self.assertEqual(
            load_latest_learned_memory(
                self.memory_manager,
                kind="preference",
                key="preferred_language",
            ),
            learned_memory,
        )
        records = self.memory_manager.all()
        learned_records = tuple(
            record for record in records if "learned" in record.tags
        )
        conversation_records = tuple(
            record for record in records if "conversation" in record.tags
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(len(learned_records), 1)
        self.assertEqual(len(conversation_records), 1)
        learned_record = learned_records[0]
        self.assertEqual(learned_record.content, "Python")
        self.assertEqual(learned_record.tags, frozenset({"learned", "preference"}))
        self.assertEqual(
            learned_record.metadata,
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Python",
            },
        )
        conversation_record = conversation_records[0]
        self.assertEqual(
            conversation_record.content,
            "User:   Ben Python tercih ediyorum.  \nHypatia: I will remember that.",
        )
        self.assertEqual(
            conversation_record.tags,
            frozenset({"brain", "conversation"}),
        )
        self.assertNotIn("source_text", learned_record.metadata)
        self.assertEqual(llm_provider.calls, [(message, ())])

    def test_successful_llm_message_persists_multiple_learned_candidates(self) -> None:
        llm_provider = RecordingLLMProvider("I will remember both.")
        message = "  Python tercih ediyorum ve Rust öğrenmek istiyorum.  "
        python_preference = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        rust_goal = LearnedMemory(
            kind="goal",
            key="current_learning_goal",
            value="Rust",
        )
        python_candidate = LearnedMemoryCandidate(
            memory=python_preference,
            source_text=message,
        )
        rust_candidate = LearnedMemoryCandidate(
            memory=rust_goal,
            source_text=message,
        )
        recording_extractor = RecordingCandidateExtractor(
            LearnedMemoryCandidateBatch(
                source_text=message,
                candidates=(python_candidate, rust_candidate),
            )
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
        )

        response = engine.process(BrainRequest(message=message))

        self.assertTrue(response.success)
        self.assertEqual(response.message, "I will remember both.")
        self.assertEqual(recording_extractor.calls, [message])
        self.assertEqual(
            load_learned_memories(self.memory_manager),
            (python_preference, rust_goal),
        )
        self.assertEqual(
            load_latest_learned_memory(
                self.memory_manager,
                kind="preference",
                key="preferred_language",
            ),
            python_preference,
        )
        self.assertEqual(
            load_latest_learned_memory(
                self.memory_manager,
                kind="goal",
                key="current_learning_goal",
            ),
            rust_goal,
        )
        records = self.memory_manager.all()
        learned_records = tuple(
            record for record in records if "learned" in record.tags
        )
        conversation_records = tuple(
            record for record in records if "conversation" in record.tags
        )
        self.assertEqual(len(learned_records), 2)
        self.assertEqual(len(conversation_records), 1)
        self.assertEqual(
            tuple(record.content for record in learned_records),
            ("Python", "Rust"),
        )
        self.assertEqual(
            learned_records[0].tags,
            frozenset({"learned", "preference"}),
        )
        self.assertEqual(
            learned_records[0].metadata,
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Python",
            },
        )
        self.assertEqual(
            learned_records[1].tags,
            frozenset({"learned", "goal"}),
        )
        self.assertEqual(
            learned_records[1].metadata,
            {
                "kind": "goal",
                "key": "current_learning_goal",
                "value": "Rust",
            },
        )
        self.assertNotIn("source_text", learned_records[0].metadata)
        self.assertNotIn("source_text", learned_records[1].metadata)
        self.assertEqual(
            conversation_records[0].content,
            "User:   Python tercih ediyorum ve Rust öğrenmek istiyorum.  \n"
            "Hypatia: I will remember both.",
        )
        self.assertEqual(
            conversation_records[0].tags,
            frozenset({"brain", "conversation"}),
        )
        self.assertEqual(llm_provider.calls, [(message, ())])

    def test_same_batch_exact_duplicate_candidate_is_a_no_op(self) -> None:
        llm_provider = RecordingLLMProvider("I will remember that.")
        message = "  Ben Python tercih ediyorum.  "
        learned_memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        first_candidate = LearnedMemoryCandidate(
            memory=learned_memory,
            source_text=message,
        )
        duplicate_candidate = LearnedMemoryCandidate(
            memory=learned_memory,
            source_text=message,
        )
        self.assertIsNot(first_candidate, duplicate_candidate)
        self.assertIs(first_candidate.memory, duplicate_candidate.memory)
        recording_extractor = RecordingCandidateExtractor(
            LearnedMemoryCandidateBatch(
                source_text=message,
                candidates=(first_candidate, duplicate_candidate),
            )
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
        )

        response = engine.process(BrainRequest(message=message))

        self.assertTrue(response.success)
        self.assertEqual(response.message, "I will remember that.")
        self.assertEqual(recording_extractor.calls, [message])
        self.assertEqual(load_learned_memories(self.memory_manager), (learned_memory,))
        self.assertEqual(
            load_latest_learned_memory(
                self.memory_manager,
                kind="preference",
                key="preferred_language",
            ),
            learned_memory,
        )
        records = self.memory_manager.all()
        learned_records = tuple(
            record for record in records if "learned" in record.tags
        )
        conversation_records = tuple(
            record for record in records if "conversation" in record.tags
        )
        self.assertEqual(len(learned_records), 1)
        self.assertEqual(len(conversation_records), 1)
        learned_record = learned_records[0]
        self.assertIs(
            next(
                record
                for record in self.memory_manager.all()
                if "learned" in record.tags
            ),
            learned_record,
        )
        self.assertEqual(learned_record.content, "Python")
        self.assertEqual(
            learned_record.tags,
            frozenset({"learned", "preference"}),
        )
        self.assertEqual(
            learned_record.metadata,
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Python",
            },
        )
        self.assertNotIn("source_text", learned_record.metadata)
        self.assertEqual(
            conversation_records[0].content,
            "User:   Ben Python tercih ediyorum.  \n" "Hypatia: I will remember that.",
        )
        self.assertEqual(
            conversation_records[0].tags,
            frozenset({"brain", "conversation"}),
        )
        self.assertEqual(llm_provider.calls, [(message, ())])

    def test_same_batch_changed_candidate_appends_a_correction(self) -> None:
        llm_provider = RecordingLLMProvider("I will remember that.")
        message = "  Önce Python, sonra Rust tercih ediyorum.  "
        python_memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        rust_memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        recording_extractor = RecordingCandidateExtractor(
            LearnedMemoryCandidateBatch(
                source_text=message,
                candidates=(
                    LearnedMemoryCandidate(
                        memory=python_memory,
                        source_text=message,
                    ),
                    LearnedMemoryCandidate(
                        memory=rust_memory,
                        source_text=message,
                    ),
                ),
            )
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
        )

        response = engine.process(BrainRequest(message=message))

        self.assertTrue(response.success)
        self.assertEqual(response.message, "I will remember that.")
        self.assertEqual(recording_extractor.calls, [message])
        self.assertEqual(
            load_learned_memories(self.memory_manager),
            (python_memory, rust_memory),
        )
        self.assertEqual(
            load_latest_learned_memory(
                self.memory_manager,
                kind="preference",
                key="preferred_language",
            ),
            rust_memory,
        )
        records = self.memory_manager.all()
        learned_records = tuple(
            record for record in records if "learned" in record.tags
        )
        conversation_records = tuple(
            record for record in records if "conversation" in record.tags
        )
        self.assertEqual(len(learned_records), 2)
        self.assertEqual(len(conversation_records), 1)
        python_record, rust_record = learned_records
        self.assertIs(learned_records[0], python_record)
        self.assertEqual(python_record.content, "Python")
        self.assertEqual(
            python_record.tags,
            frozenset({"learned", "preference"}),
        )
        self.assertEqual(
            python_record.metadata,
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Python",
            },
        )
        self.assertEqual(rust_record.content, "Rust")
        self.assertEqual(
            rust_record.tags,
            frozenset({"learned", "preference"}),
        )
        self.assertEqual(
            rust_record.metadata,
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Rust",
            },
        )
        self.assertNotIn("source_text", python_record.metadata)
        self.assertNotIn("source_text", rust_record.metadata)
        self.assertEqual(
            conversation_records[0].content,
            "User:   Önce Python, sonra Rust tercih ediyorum.  \n"
            "Hypatia: I will remember that.",
        )
        self.assertEqual(
            conversation_records[0].tags,
            frozenset({"brain", "conversation"}),
        )
        self.assertEqual(llm_provider.calls, [(message, ())])

    def test_repeated_exact_candidate_is_a_learned_memory_no_op(self) -> None:
        llm_provider = RecordingLLMProvider("I will remember that.")
        first_message = "  Ben Python tercih ediyorum.  "
        second_message = "  Python tercihimi hatırla.  "
        learned_memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        candidate = LearnedMemoryCandidate(
            memory=learned_memory,
            source_text=first_message,
        )
        batch = LearnedMemoryCandidateBatch(
            source_text=first_message,
            candidates=(candidate,),
        )
        recording_extractor = RecordingCandidateExtractor(batch)
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
        )

        first_response = engine.process(BrainRequest(message=first_message))
        first_learned_record = next(
            record for record in self.memory_manager.all() if "learned" in record.tags
        )
        second_response = engine.process(BrainRequest(message=second_message))

        self.assertTrue(first_response.success)
        self.assertTrue(second_response.success)
        self.assertEqual(first_response.message, "I will remember that.")
        self.assertEqual(second_response.message, "I will remember that.")
        self.assertEqual(recording_extractor.calls, [first_message, second_message])
        self.assertEqual(load_learned_memories(self.memory_manager), (learned_memory,))
        self.assertEqual(
            load_latest_learned_memory(
                self.memory_manager,
                kind="preference",
                key="preferred_language",
            ),
            learned_memory,
        )
        records = self.memory_manager.all()
        learned_records = tuple(
            record for record in records if "learned" in record.tags
        )
        conversation_records = tuple(
            record for record in records if "conversation" in record.tags
        )
        self.assertEqual(len(learned_records), 1)
        self.assertEqual(len(conversation_records), 2)
        self.assertIs(learned_records[0], first_learned_record)
        self.assertEqual(first_learned_record.content, "Python")
        self.assertEqual(
            first_learned_record.tags,
            frozenset({"learned", "preference"}),
        )
        self.assertEqual(
            first_learned_record.metadata,
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Python",
            },
        )
        self.assertEqual(
            tuple(record.content for record in conversation_records),
            (
                "User:   Ben Python tercih ediyorum.  \n"
                "Hypatia: I will remember that.",
                "User:   Python tercihimi hatırla.  \n"
                "Hypatia: I will remember that.",
            ),
        )
        self.assertEqual(
            llm_provider.calls,
            [
                (first_message, ()),
                (
                    build_learned_memory_augmented_prompt(
                        user_message=second_message,
                        learned_memory_context=build_learned_memory_context(
                            (learned_memory,)
                        ),
                    ),
                    (
                        LLMConversationMessage(role="user", content=first_message),
                        LLMConversationMessage(
                            role="assistant",
                            content="I will remember that.",
                        ),
                    ),
                ),
            ],
        )

    def test_changed_candidate_appends_a_learned_memory_correction(self) -> None:
        llm_provider = RecordingLLMProvider("I will remember that.")
        first_message = "  Ben Python tercih ediyorum.  "
        second_message = "  Artık Rust tercih ediyorum.  "
        python_memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        rust_memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        python_candidate = LearnedMemoryCandidate(
            memory=python_memory,
            source_text=first_message,
        )
        rust_candidate = LearnedMemoryCandidate(
            memory=rust_memory,
            source_text=second_message,
        )
        recording_extractor = RecordingCandidateSequenceExtractor(
            (
                LearnedMemoryCandidateBatch(
                    source_text=first_message,
                    candidates=(python_candidate,),
                ),
                LearnedMemoryCandidateBatch(
                    source_text=second_message,
                    candidates=(rust_candidate,),
                ),
            )
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
        )

        first_response = engine.process(BrainRequest(message=first_message))
        python_record = next(
            record for record in self.memory_manager.all() if "learned" in record.tags
        )
        second_response = engine.process(BrainRequest(message=second_message))

        self.assertTrue(first_response.success)
        self.assertTrue(second_response.success)
        self.assertEqual(first_response.message, "I will remember that.")
        self.assertEqual(second_response.message, "I will remember that.")
        self.assertEqual(recording_extractor.calls, [first_message, second_message])
        self.assertEqual(
            load_learned_memories(self.memory_manager),
            (python_memory, rust_memory),
        )
        self.assertEqual(
            load_latest_learned_memory(
                self.memory_manager,
                kind="preference",
                key="preferred_language",
            ),
            rust_memory,
        )
        records = self.memory_manager.all()
        learned_records = tuple(
            record for record in records if "learned" in record.tags
        )
        conversation_records = tuple(
            record for record in records if "conversation" in record.tags
        )
        self.assertEqual(len(learned_records), 2)
        self.assertEqual(len(conversation_records), 2)
        self.assertIs(learned_records[0], python_record)
        self.assertEqual(python_record.content, "Python")
        self.assertEqual(python_record.tags, frozenset({"learned", "preference"}))
        self.assertEqual(
            python_record.metadata,
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Python",
            },
        )
        rust_record = learned_records[1]
        self.assertIsNot(rust_record, python_record)
        self.assertEqual(rust_record.content, "Rust")
        self.assertEqual(rust_record.tags, frozenset({"learned", "preference"}))
        self.assertEqual(
            rust_record.metadata,
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Rust",
            },
        )
        self.assertNotIn("source_text", python_record.metadata)
        self.assertNotIn("source_text", rust_record.metadata)
        self.assertEqual(
            tuple(record.content for record in conversation_records),
            (
                "User:   Ben Python tercih ediyorum.  \n"
                "Hypatia: I will remember that.",
                "User:   Artık Rust tercih ediyorum.  \n"
                "Hypatia: I will remember that.",
            ),
        )
        self.assertEqual(
            llm_provider.calls,
            [
                (first_message, ()),
                (
                    build_learned_memory_augmented_prompt(
                        user_message=second_message,
                        learned_memory_context=build_learned_memory_context(
                            (python_memory,)
                        ),
                    ),
                    (
                        LLMConversationMessage(role="user", content=first_message),
                        LLMConversationMessage(
                            role="assistant",
                            content="I will remember that.",
                        ),
                    ),
                ),
            ],
        )

    def test_repeated_corrected_candidate_is_a_learned_memory_no_op(self) -> None:
        llm_provider = RecordingLLMProvider("I will remember that.")
        first_message = "  Ben Python tercih ediyorum.  "
        second_message = "  Artık Rust tercih ediyorum.  "
        third_message = "  Rust tercihimi hatırla.  "
        python_memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        rust_memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        python_candidate = LearnedMemoryCandidate(
            memory=python_memory,
            source_text=first_message,
        )
        first_rust_candidate = LearnedMemoryCandidate(
            memory=rust_memory,
            source_text=second_message,
        )
        repeated_rust_candidate = LearnedMemoryCandidate(
            memory=rust_memory,
            source_text=third_message,
        )
        recording_extractor = RecordingCandidateSequenceExtractor(
            (
                LearnedMemoryCandidateBatch(
                    source_text=first_message,
                    candidates=(python_candidate,),
                ),
                LearnedMemoryCandidateBatch(
                    source_text=second_message,
                    candidates=(first_rust_candidate,),
                ),
                LearnedMemoryCandidateBatch(
                    source_text=third_message,
                    candidates=(repeated_rust_candidate,),
                ),
            )
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
        )

        first_response = engine.process(BrainRequest(message=first_message))
        python_record = next(
            record for record in self.memory_manager.all() if "learned" in record.tags
        )
        second_response = engine.process(BrainRequest(message=second_message))
        rust_record = tuple(
            record for record in self.memory_manager.all() if "learned" in record.tags
        )[1]
        third_response = engine.process(BrainRequest(message=third_message))

        self.assertTrue(first_response.success)
        self.assertTrue(second_response.success)
        self.assertTrue(third_response.success)
        self.assertEqual(first_response.message, "I will remember that.")
        self.assertEqual(second_response.message, "I will remember that.")
        self.assertEqual(third_response.message, "I will remember that.")
        self.assertEqual(
            recording_extractor.calls,
            [first_message, second_message, third_message],
        )
        self.assertEqual(
            load_learned_memories(self.memory_manager),
            (python_memory, rust_memory),
        )
        self.assertEqual(
            load_latest_learned_memory(
                self.memory_manager,
                kind="preference",
                key="preferred_language",
            ),
            rust_memory,
        )
        records = self.memory_manager.all()
        learned_records = tuple(
            record for record in records if "learned" in record.tags
        )
        conversation_records = tuple(
            record for record in records if "conversation" in record.tags
        )
        self.assertEqual(len(learned_records), 2)
        self.assertEqual(len(conversation_records), 3)
        self.assertIs(learned_records[0], python_record)
        self.assertIs(learned_records[1], rust_record)
        self.assertEqual(python_record.content, "Python")
        self.assertEqual(python_record.tags, frozenset({"learned", "preference"}))
        self.assertEqual(
            python_record.metadata,
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Python",
            },
        )
        self.assertEqual(rust_record.content, "Rust")
        self.assertEqual(rust_record.tags, frozenset({"learned", "preference"}))
        self.assertEqual(
            rust_record.metadata,
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Rust",
            },
        )
        self.assertNotIn("source_text", python_record.metadata)
        self.assertNotIn("source_text", rust_record.metadata)
        self.assertEqual(
            tuple(record.content for record in conversation_records),
            (
                "User:   Ben Python tercih ediyorum.  \n"
                "Hypatia: I will remember that.",
                "User:   Artık Rust tercih ediyorum.  \n"
                "Hypatia: I will remember that.",
                "User:   Rust tercihimi hatırla.  \n" "Hypatia: I will remember that.",
            ),
        )
        first_turn = (
            LLMConversationMessage(role="user", content=first_message),
            LLMConversationMessage(
                role="assistant",
                content="I will remember that.",
            ),
        )
        second_turn = (
            LLMConversationMessage(role="user", content=second_message),
            LLMConversationMessage(
                role="assistant",
                content="I will remember that.",
            ),
        )
        self.assertEqual(
            llm_provider.calls,
            [
                (first_message, ()),
                (
                    build_learned_memory_augmented_prompt(
                        user_message=second_message,
                        learned_memory_context=build_learned_memory_context(
                            (python_memory,)
                        ),
                    ),
                    first_turn,
                ),
                (
                    build_learned_memory_augmented_prompt(
                        user_message=third_message,
                        learned_memory_context=build_learned_memory_context(
                            (rust_memory,)
                        ),
                    ),
                    first_turn + second_turn,
                ),
            ],
        )

    def test_failed_llm_message_does_not_invoke_candidate_extractor(self) -> None:
        llm_provider = FailingLLMProvider()
        recording_extractor = RecordingCandidateExtractor()
        message = "  Ben kahveyi şekersiz içerim.  "
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=recording_extractor,
        )

        with patch(
            "cognition.CognitiveEngine.persist_learned_memory_candidate_batch"
        ) as persist:
            response = engine.process(BrainRequest(message=message))

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Generation unavailable.")
        self.assertEqual(recording_extractor.calls, [])
        persist.assert_not_called()
        self.assertEqual(llm_provider.calls, [(message, ())])

    def test_message_passes_existing_same_session_conversation_history(self) -> None:
        llm_provider = RecordingLLMProvider("Nice to meet you.")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
        )
        engine.process(
            BrainRequest(
                message="My name is Songül.",
                metadata={"session_id": "work-1"},
            )
        )
        self.memory_manager.add(
            "User: Other session\nHypatia: Other response",
            metadata={
                "session_id": "personal",
                "user_message": "Other session",
                "assistant_message": "Other response",
            },
            tags={"brain", "conversation"},
        )

        engine.process(
            BrainRequest(
                message="What is my name?",
                metadata={"session_id": "work-1"},
            )
        )

        self.assertEqual(
            llm_provider.calls,
            [
                ("My name is Songül.", ()),
                (
                    "What is my name?",
                    (
                        LLMConversationMessage(
                            role="user",
                            content="My name is Songül.",
                        ),
                        LLMConversationMessage(
                            role="assistant",
                            content="Nice to meet you.",
                        ),
                    ),
                ),
            ],
        )

    def test_message_limits_history_to_the_most_recent_eight_turns(self) -> None:
        for turn in range(1, 10):
            self.memory_manager.add(
                f"User: User turn {turn}\nHypatia: Assistant turn {turn}",
                metadata={
                    "session_id": "work-1",
                    "user_message": f"User turn {turn}",
                    "assistant_message": f"Assistant turn {turn}",
                },
                tags={"brain", "conversation"},
            )
        self.memory_manager.add(
            "User: Other session\nHypatia: Other response",
            metadata={
                "session_id": "personal",
                "user_message": "Other session",
                "assistant_message": "Other response",
            },
            tags={"brain", "conversation"},
        )
        llm_provider = RecordingLLMProvider("Current response")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
        )

        engine.process(
            BrainRequest(
                message="Current prompt",
                metadata={"session_id": "work-1"},
            )
        )

        expected_history = tuple(
            message
            for turn in range(2, 10)
            for message in (
                LLMConversationMessage(
                    role="user",
                    content=f"User turn {turn}",
                ),
                LLMConversationMessage(
                    role="assistant",
                    content=f"Assistant turn {turn}",
                ),
            )
        )
        self.assertEqual(
            llm_provider.calls,
            [("Current prompt", expected_history)],
        )
        self.assertEqual(len(expected_history), 16)

    def test_message_uses_the_configured_history_turn_limit(self) -> None:
        for turn in range(1, 4):
            self.memory_manager.add(
                f"User: User turn {turn}\nHypatia: Assistant turn {turn}",
                metadata={
                    "session_id": "work-1",
                    "user_message": f"User turn {turn}",
                    "assistant_message": f"Assistant turn {turn}",
                },
                tags={"brain", "conversation"},
            )
        llm_provider = RecordingLLMProvider("Current response")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            llm_history_max_turns=2,
        )

        engine.process(
            BrainRequest(
                message="Current prompt",
                metadata={"session_id": "work-1"},
            )
        )

        self.assertEqual(
            llm_provider.calls,
            [
                (
                    "Current prompt",
                    (
                        LLMConversationMessage(role="user", content="User turn 2"),
                        LLMConversationMessage(
                            role="assistant",
                            content="Assistant turn 2",
                        ),
                        LLMConversationMessage(role="user", content="User turn 3"),
                        LLMConversationMessage(
                            role="assistant",
                            content="Assistant turn 3",
                        ),
                    ),
                )
            ],
        )

    def test_constructor_rejects_invalid_history_turn_limits(self) -> None:
        expected_message = "llm_history_max_turns must be a positive integer or None."

        for value in (0, -1, True, False):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as raised:
                    ProductionCognitiveEngine(
                        self.knowledge_engine,
                        self.memory_manager,
                        self.planner,
                        self.event_bus,
                        self.response_composer,
                        self.session_manager,
                        self.session_rename_service,
                        llm_history_max_turns=value,
                    )
                self.assertEqual(str(raised.exception), expected_message)

    def test_message_without_an_llm_provider_uses_the_deterministic_response(
        self,
    ) -> None:
        response = self.engine.process(BrainRequest(message="Tell me something."))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "message")
        self.assertEqual(
            response.message,
            "I received your message: Tell me something.",
        )

    def test_message_maps_an_llm_generation_failure_without_memory(self) -> None:
        llm_provider = FailingLLMProvider()
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
        )
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        request = BrainRequest(
            message="Tell me something.",
            request_id="request-123",
        )

        response = engine.process(request)

        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "message")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "Generation unavailable.")
        self.assertEqual(llm_provider.calls, [("Tell me something.", ())])
        self.assertEqual(self.memory_manager.all(), [])
        self.assertEqual(
            events,
            [
                "brain.request.received",
                "brain.intent.detected",
                "brain.response.ready",
            ],
        )

    def test_search_response_reports_matching_chunk_count(self) -> None:
        response = self.engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(response.message, "I found 2 matching knowledge chunks.")

    def test_search_response_contains_knowledge_results(self) -> None:
        response = self.engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(
            [chunk.content for chunk in response.knowledge_results],
            ["Hypatia", "Hypatia"],
        )

    def test_search_response_keeps_result_citations_in_result_order(self) -> None:
        response = self.engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(
            [citation.chunk_id for citation in response.knowledge_citations],
            [chunk.chunk_id for chunk in response.knowledge_results],
        )

    def test_explicit_knowledge_context_is_bounded_cited_and_not_remembered(
        self,
    ) -> None:
        extra_path = Path(self.temporary_directory.name) / "extra.md"
        extra_path.write_text(
            "Hypatia\n\nHypatia\n\nHypatia",
            encoding="utf-8",
        )
        self.knowledge_engine.load(extra_path)

        response = self.engine.process(
            BrainRequest(message="knowledge context hypatia")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_context")
        self.assertEqual(len(response.knowledge_results), 3)
        self.assertEqual(len(response.knowledge_citations), 3)
        self.assertIn("Knowledge context:", response.message)
        self.assertIn(
            str(Path(self.temporary_directory.name) / "knowledge.md"), response.message
        )
        self.assertEqual(self.memory_manager.all(), [])

    def test_empty_explicit_knowledge_context_returns_a_controlled_failure(
        self,
    ) -> None:
        response = self.engine.process(BrainRequest(message="knowledge context"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "knowledge_context")
        self.assertEqual(response.message, "A knowledge context query is required.")
        self.assertEqual(self.memory_manager.all(), [])

    def test_explicit_knowledge_graph_is_bounded_cited_and_not_remembered(
        self,
    ) -> None:
        extra_path = Path(self.temporary_directory.name) / "extra.md"
        extra_path.write_text(
            "Hypatia\n\nHypatia\n\nHypatia",
            encoding="utf-8",
        )
        self.knowledge_engine.load(extra_path)

        response = self.engine.process(BrainRequest(message="knowledge graph hypatia"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_graph")
        self.assertEqual(len(response.knowledge_results), 3)
        self.assertEqual(len(response.knowledge_citations), 3)
        self.assertIn("Knowledge graph:", response.message)
        self.assertIn("--contains-->", response.message)
        self.assertEqual(self.memory_manager.all(), [])

    def test_empty_explicit_knowledge_graph_returns_a_controlled_failure(
        self,
    ) -> None:
        response = self.engine.process(BrainRequest(message="knowledge graph"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "knowledge_graph")
        self.assertEqual(response.message, "A knowledge graph query is required.")
        self.assertEqual(self.memory_manager.all(), [])

    def test_list_knowledge_exposes_document_ids_without_remembering_the_request(
        self,
    ) -> None:
        response = self.engine.process(BrainRequest(message="list knowledge"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_list")
        self.assertEqual(len(response.knowledge_documents), 1)
        self.assertEqual(response.knowledge_documents[0].title, "knowledge")
        self.assertIn("Knowledge sources:", response.message)
        self.assertIn(response.knowledge_documents[0].document_id, response.message)
        self.assertEqual(self.memory_manager.all(), [])

    def test_list_knowledge_without_sources_is_a_successful_empty_catalog(self) -> None:
        empty_engine = ProductionCognitiveEngine(
            KnowledgeEngine(),
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
        )

        response = empty_engine.process(BrainRequest(message="list knowledge"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_list")
        self.assertEqual(response.message, "No local knowledge sources are loaded.")
        self.assertEqual(self.memory_manager.all(), [])

    def test_knowledge_relation_preview_is_validated_and_not_remembered(self) -> None:
        extra_path = Path(self.temporary_directory.name) / "extra.md"
        extra_path.write_text("Extra", encoding="utf-8")
        self.knowledge_engine.load(extra_path)
        source_id, target_id = [
            document.document_id for document in self.knowledge_engine.documents()
        ]

        response = self.engine.process(
            BrainRequest(
                message=("preview knowledge relation " f"{source_id} -- {target_id}")
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_relation_preview")
        self.assertIsNotNone(response.knowledge_relation_preview)
        self.assertIn("Relation: related_to", response.message)
        self.assertIn("Changes: ready", response.message)
        self.assertEqual(self.memory_manager.all(), [])

    def test_knowledge_relation_preview_rejects_bad_format_without_remembering(
        self,
    ) -> None:
        response = self.engine.process(
            BrainRequest(message="preview knowledge relation")
        )

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "knowledge_relation_preview")
        self.assertIn("Knowledge relation preview format:", response.message)
        self.assertEqual(self.memory_manager.all(), [])

    def test_knowledge_relation_apply_changes_only_the_local_derived_graph(
        self,
    ) -> None:
        extra_path = Path(self.temporary_directory.name) / "extra.md"
        extra_path.write_text("Extra", encoding="utf-8")
        self.knowledge_engine.load(extra_path)
        source_id, target_id = [
            document.document_id for document in self.knowledge_engine.documents()
        ]

        response = self.engine.process(
            BrainRequest(
                message=("apply knowledge relation " f"{source_id} -- {target_id}")
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_relation_apply")
        self.assertIsNotNone(response.knowledge_relation_application)
        self.assertIn("Graph state: updated (memory only)", response.message)
        self.assertEqual(self.memory_manager.all(), [])
        duplicate = self.engine.process(
            BrainRequest(
                message=("apply knowledge relation " f"{source_id} -- {target_id}")
            )
        )
        self.assertFalse(duplicate.success)
        self.assertIn("Knowledge graph relation is already applied.", duplicate.message)
        self.assertEqual(self.memory_manager.all(), [])

    def test_ask_knowledge_sends_only_cited_local_context_to_the_llm(self) -> None:
        llm_provider = RecordingLLMProvider("Hypatia is in the local notes.")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
        )

        response = engine.process(BrainRequest(message="ask knowledge hypatia"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "ask_knowledge")
        self.assertEqual(response.message, "Hypatia is in the local notes.")
        self.assertEqual(len(response.knowledge_results), 2)
        self.assertEqual(len(response.knowledge_citations), 2)
        self.assertEqual(len(llm_provider.calls), 1)
        prompt, history = llm_provider.calls[0]
        self.assertIn("Answer the user using only the local context below.", prompt)
        self.assertIn("User question: hypatia", prompt)
        self.assertIn(str(Path(self.temporary_directory.name) / "knowledge.md"), prompt)
        self.assertEqual(history, ())
        self.assertEqual(self.memory_manager.all(), [])

    def test_ask_knowledge_requires_an_llm_without_mutating_memory(self) -> None:
        response = self.engine.process(BrainRequest(message="ask knowledge hypatia"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "ask_knowledge")
        self.assertEqual(
            response.message,
            "A language-model runtime is required for ask knowledge.",
        )
        self.assertEqual(self.memory_manager.all(), [])

    def test_empty_ask_knowledge_returns_a_controlled_failure(self) -> None:
        response = self.engine.process(BrainRequest(message="ask knowledge"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "ask_knowledge")
        self.assertEqual(response.message, "An ask knowledge query is required.")
        self.assertEqual(self.memory_manager.all(), [])

    def test_successful_search_is_saved_to_memory(self) -> None:
        self.engine.process(BrainRequest(message="search hypatia"))

        records = self.memory_manager.all()

        self.assertEqual(len(records), 1)

    def test_successful_search_memory_has_expected_content(self) -> None:
        self.engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(
            self.memory_manager.all()[0].content,
            "User: search hypatia\nHypatia: I found 2 matching knowledge chunks.",
        )

    def test_successful_search_memory_has_expected_tags(self) -> None:
        self.engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(
            self.memory_manager.all()[0].tags,
            frozenset({"cognition", "knowledge-search", "conversation"}),
        )

    def test_successful_search_memory_has_expected_metadata(self) -> None:
        response = self.engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(
            dict(self.memory_manager.all()[0].metadata),
            {
                "intent": "search",
                "query": "hypatia",
                "result_count": 2,
                "success": response.success,
            },
        )

    def test_declared_search_intent_uses_request_message_as_query(self) -> None:
        request = BrainRequest(message="hypatia", metadata={"intent": "search"})

        response = self.engine.process(request)

        self.assertEqual(len(response.knowledge_results), 2)

    def test_empty_search_query_returns_controlled_response(self) -> None:
        response = self.engine.process(BrainRequest(message="search "))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "search")
        self.assertEqual(response.message, "A search query is required.")

    def test_session_rename_executes_without_conversation_side_effects(self) -> None:
        self.memory_manager.add("Work", metadata={"session_id": "work-1"})
        self.session_manager.set_active("work-1")
        events: list[Event] = []
        self.event_bus.subscribe("*", events.append)

        response = self.engine.process(
            BrainRequest(message="  RENAME SESSION work-1 -- Work Archive  ")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_rename")
        self.assertEqual(
            response.message,
            "Rename complete:\n"
            "Source: work-1\n"
            "Target: Work Archive\n"
            "Memory records updated: 1\n"
            "Active session changed: yes\n"
            "Status: committed",
        )
        self.assertTrue(self.session_manager.exists("Work Archive"))
        self.assertFalse(self.session_manager.exists("work-1"))
        self.assertEqual(
            self.memory_manager.snapshot()[0].metadata["session_id"],
            "Work Archive",
        )
        self.assertEqual([event.name for event in events], ["session.renamed"])

    def test_session_rename_reports_zero_memory_for_a_non_active_session(self) -> None:
        response = self.engine.process(
            BrainRequest(message="rename session work-1 -- Work Archive")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_rename")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Rename complete:\n"
            "Source: work-1\n"
            "Target: Work Archive\n"
            "Memory records updated: 0\n"
            "Active session changed: no\n"
            "Status: committed",
        )
        self.assertEqual(self.session_manager.get_active().session_id, "default")

    def test_session_rename_parser_and_domain_failures_are_controlled(self) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        for message, expected in (
            ("rename session work", "Session rename separator is required: --"),
            ("rename session -- work", "Session source ID must not be empty."),
            ("rename session work --", "Session target ID must not be empty."),
            ("rename session missing -- other", "Unknown session: missing"),
            ("rename session work-1 -- personal", "Session already exists: personal"),
            ("rename session default -- other", "Default session cannot be renamed."),
            (
                "rename session work-1 -- work-1",
                "Session source and target must be different.",
            ),
        ):
            with self.subTest(message=message):
                response = self.engine.process(BrainRequest(message=message))
                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_rename")
                self.assertEqual(response.memory_count, 0)
                self.assertEqual(
                    response.message, f"Rename failed:\nReason: {expected}"
                )

        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_rename_maps_memory_failure_without_composing(self) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.engine._session_rename_service,
                "rename",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "session_renamed",
                wraps=self.response_composer.session_renamed,
            ) as session_renamed,
            patch.object(
                self.response_composer,
                "session_rename_preview",
                wraps=self.response_composer.session_rename_preview,
            ) as session_rename_preview,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="rename session work-1 -- Work Archive",
                    request_id="request-123",
                )
            )

        session_renamed.assert_not_called()
        session_rename_preview.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_rename")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Rename failed:\nReason: Memory snapshot changed.",
        )
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_rename_maps_runtime_failure_without_composing(self) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.engine._session_rename_service,
                "rename",
                side_effect=RuntimeError("Session store unavailable."),
            ),
            patch.object(
                self.response_composer,
                "session_renamed",
                wraps=self.response_composer.session_renamed,
            ) as session_renamed,
            patch.object(
                self.response_composer,
                "session_rename_preview",
                wraps=self.response_composer.session_rename_preview,
            ) as session_rename_preview,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="rename session work-1 -- Work Archive",
                    request_id="request-123",
                )
            )

        session_renamed.assert_not_called()
        session_rename_preview.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_rename")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Rename failed:\nReason: Session store unavailable.",
        )
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_rename_preview_has_no_conversation_or_session_side_effects(
        self,
    ) -> None:
        self.memory_manager.add("Work", metadata={"session_id": "work-1"})
        events: list[Event] = []
        self.event_bus.subscribe("*", events.append)
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        memory_id = memory_before[0].memory_id

        response = self.engine.process(
            BrainRequest(message="PREVIEW RENAME SESSION work-1 -- Work Archive")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_rename_preview")
        self.assertEqual(
            response.message,
            "Rename preview:\n"
            "Source: work-1\n"
            "Target: Work Archive\n"
            "Affected memories: 1\n"
            "Memory IDs:\n"
            f"- {memory_id}\n"
            "Changes: ready",
        )
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_rename_preview_parser_and_domain_failures_are_controlled(
        self,
    ) -> None:
        self.session_manager.create("archive")

        for message, expected in (
            (
                "preview rename session work-1",
                "Session rename separator is required: --",
            ),
            (
                "preview rename session -- work-1",
                "Session source ID must not be empty.",
            ),
            (
                "preview rename session work-1 --",
                "Session target ID must not be empty.",
            ),
            (
                "preview rename session missing -- other",
                "Unknown session: missing",
            ),
            (
                "preview rename session default -- other",
                "Default session cannot be renamed.",
            ),
            (
                "preview rename session work-1 -- work-1",
                "Session source and target must be different.",
            ),
            (
                "preview rename session work-1 -- archive",
                "Session already exists: archive",
            ),
        ):
            with self.subTest(message=message):
                response = self.engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_rename_preview")
                self.assertEqual(response.memory_count, 0)
                self.assertEqual(response.message, expected)

    def test_session_rename_preview_maps_memory_failure_without_composing(
        self,
    ) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.engine._session_rename_service,
                "preview",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "session_rename_preview",
                wraps=self.response_composer.session_rename_preview,
            ) as session_rename_preview,
            patch.object(
                self.response_composer,
                "session_renamed",
                wraps=self.response_composer.session_renamed,
            ) as session_renamed,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="preview rename session work-1 -- Work Archive",
                    request_id="request-123",
                )
            )

        session_rename_preview.assert_not_called()
        session_renamed.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_rename_preview")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Memory snapshot changed.",
        )
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_rename_preview_maps_runtime_failure_without_composing(
        self,
    ) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.engine._session_rename_service,
                "preview",
                side_effect=RuntimeError("Session store unavailable."),
            ),
            patch.object(
                self.response_composer,
                "session_rename_preview",
                wraps=self.response_composer.session_rename_preview,
            ) as session_rename_preview,
            patch.object(
                self.response_composer,
                "session_renamed",
                wraps=self.response_composer.session_renamed,
            ) as session_renamed,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="preview rename session work-1 -- Work Archive",
                    request_id="request-123",
                )
            )

        session_rename_preview.assert_not_called()
        session_renamed.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_rename_preview")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "Session store unavailable.")
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_rename_help_has_no_rename_or_conversation_side_effects(
        self,
    ) -> None:
        events: list[Event] = []
        self.event_bus.subscribe("*", events.append)
        memory_before = self.memory_manager.snapshot()
        sessions_before = self.session_manager.snapshot()

        with (
            patch.object(
                self.session_rename_service,
                "rename",
                side_effect=AssertionError("Rename service must not be called."),
            ),
            patch.object(
                self.session_rename_service,
                "preview",
                side_effect=AssertionError("Preview service must not be called."),
            ),
        ):
            request = BrainRequest(message="help rename session")
            response = self.engine.process(request)

        self.assertTrue(response.success)
        self.assertEqual(
            response.message,
            "Rename session:\n"
            "rename session <source> -- <target>\n"
            "\n"
            "Preview:\n"
            "preview rename session <source> -- <target>\n"
            "\n"
            "Check target:\n"
            "check rename target <target>\n"
            "\n"
            "Example:\n"
            "rename session work -- archive",
        )
        self.assertFalse(response.message.endswith("\n"))
        self.assertEqual(response.intent, "session_rename_help")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, request.request_id)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(events, [])
        self.assertTrue(
            self.engine.process(
                BrainRequest(message="preview rename session work-1 -- archive")
            ).success
        )
        self.assertTrue(
            self.engine.process(
                BrainRequest(message="rename session work-1 -- archive")
            ).success
        )

    def test_session_help_has_no_runtime_side_effects(self) -> None:
        events: list[Event] = []
        self.event_bus.subscribe("*", events.append)
        memory_before = self.memory_manager.snapshot()
        sessions_before = self.session_manager.snapshot()

        with (
            patch.object(
                self.session_manager,
                "list",
                side_effect=AssertionError("Session reads must not be called."),
            ),
            patch.object(
                self.session_manager,
                "get_active",
                side_effect=AssertionError("Session reads must not be called."),
            ),
            patch.object(
                self.session_manager,
                "exists",
                side_effect=AssertionError("Session reads must not be called."),
            ),
            patch.object(
                self.session_rename_service,
                "rename",
                side_effect=AssertionError("Rename service must not be called."),
            ),
            patch.object(
                self.session_rename_service,
                "preview",
                side_effect=AssertionError("Preview service must not be called."),
            ),
            patch.object(
                self.memory_manager,
                "add",
                side_effect=AssertionError("Memory writes must not be called."),
            ),
            patch.object(
                self.memory_manager,
                "all",
                side_effect=AssertionError("Memory reads must not be called."),
            ),
            patch.object(
                self.planner,
                "create_plan",
                side_effect=AssertionError("Planner must not be called."),
            ),
            patch.object(
                self.knowledge_engine,
                "search",
                side_effect=AssertionError("Knowledge engine must not be called."),
            ),
        ):
            request = BrainRequest(message="help sessions")
            response = self.engine.process(request)

        self.assertEqual(response.intent, "session_help")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Session commands:\n"
            "create session <session_id>\n"
            "list sessions\n"
            "use session <session_id>\n"
            "active session\n"
            "session overview\n"
            "session details <session_id>\n"
            "session recent <session_id>\n"
            "session activity <session_id>\n"
            "session search <session_id> <query>\n"
            "list renameable sessions\n"
            "check rename target <target>\n"
            "preview rename session <source> -- <target>\n"
            "rename session <source> -- <target>\n"
            "help rename session",
        )
        self.assertFalse(response.message.endswith("\n"))
        self.assertEqual(response.request_id, request.request_id)
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])
        self.assertTrue(
            self.engine.process(BrainRequest(message="active session")).success
        )
        self.assertTrue(
            self.engine.process(
                BrainRequest(message="check rename target archive")
            ).success
        )
        self.assertTrue(
            self.engine.process(
                BrainRequest(message="preview rename session work-1 -- archive")
            ).success
        )
        self.assertTrue(
            self.engine.process(
                BrainRequest(message="rename session work-1 -- archive")
            ).success
        )

    def test_session_rename_candidates_are_read_only_and_preserve_order(self) -> None:
        self.session_manager.create("archive")
        self.session_manager.set_active("archive")
        self.memory_manager.add("Conversation", metadata={"session_id": "archive"})
        events: list[Event] = []
        self.event_bus.subscribe("*", events.append)
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()

        with (
            patch.object(
                self.session_rename_service,
                "rename",
                side_effect=AssertionError("Rename service must not be called."),
            ),
            patch.object(
                self.session_rename_service,
                "preview",
                side_effect=AssertionError("Preview service must not be called."),
            ),
        ):
            response = self.engine.process(
                BrainRequest(message="list renameable sessions")
            )

        self.assertEqual(
            response.message,
            "Renameable sessions:\nwork-1\npersonal\narchive (active)",
        )
        self.assertEqual(response.intent, "session_rename_candidates")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])
        self.assertTrue(
            self.engine.process(
                BrainRequest(message="preview rename session work-1 -- renamed")
            ).success
        )
        self.assertTrue(
            self.engine.process(
                BrainRequest(message="rename session work-1 -- renamed")
            ).success
        )

    def test_session_rename_candidates_excludes_default_without_active_suffix(
        self,
    ) -> None:
        empty_engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            SessionManager(self.event_bus),
            self.session_rename_service,
        )

        response = empty_engine.process(
            BrainRequest(message="list renameable sessions")
        )

        self.assertEqual(response.message, "No renameable sessions.")
        self.assertEqual(response.intent, "session_rename_candidates")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)

    def test_session_active_is_read_only_for_default_and_selected_sessions(
        self,
    ) -> None:
        events: list[Event] = []
        self.event_bus.subscribe("*", events.append)
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()

        with (
            patch.object(
                self.session_rename_service,
                "rename",
                side_effect=AssertionError("Rename service must not be called."),
            ),
            patch.object(
                self.session_rename_service,
                "preview",
                side_effect=AssertionError("Preview service must not be called."),
            ),
            patch.object(
                self.memory_manager,
                "add",
                side_effect=AssertionError("Memory writes must not be called."),
            ),
        ):
            default_response = self.engine.process(
                BrainRequest(message="active session")
            )

        self.assertEqual(default_response.message, "Active session: default")
        self.assertEqual(default_response.intent, "session_active")
        self.assertTrue(default_response.success)
        self.assertEqual(default_response.memory_count, 0)
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

        self.session_manager.set_active("work-1")
        events.clear()
        active_sessions_before = self.session_manager.snapshot()
        active_memory_before = self.memory_manager.snapshot()
        active_response = self.engine.process(BrainRequest(message="active session"))

        self.assertEqual(active_response.message, "Active session: work-1")
        self.assertEqual(active_response.intent, "session_active")
        self.assertTrue(active_response.success)
        self.assertEqual(active_response.memory_count, 0)
        self.assertEqual(self.session_manager.snapshot(), active_sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), active_memory_before)
        self.assertEqual(events, [])
        self.assertTrue(
            self.engine.process(BrainRequest(message="use session personal")).success
        )
        self.assertTrue(
            self.engine.process(
                BrainRequest(message="preview rename session work-1 -- archive")
            ).success
        )
        self.assertTrue(
            self.engine.process(
                BrainRequest(message="rename session work-1 -- archive")
            ).success
        )

    def test_session_rename_target_check_is_read_only_and_preserves_target_case(
        self,
    ) -> None:
        self.session_manager.create("archive")
        events: list[Event] = []
        self.event_bus.subscribe("*", events.append)
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()

        with (
            patch.object(
                self.session_rename_service,
                "rename",
                side_effect=AssertionError("Rename service must not be called."),
            ),
            patch.object(
                self.session_rename_service,
                "preview",
                side_effect=AssertionError("Preview service must not be called."),
            ),
            patch.object(
                self.memory_manager,
                "add",
                side_effect=AssertionError("Memory writes must not be called."),
            ),
        ):
            available = self.engine.process(
                BrainRequest(message="check rename target Work Archive")
            )
            unavailable = self.engine.process(
                BrainRequest(message="check rename target archive")
            )
            default_target = self.engine.process(
                BrainRequest(message="check rename target default")
            )
            failure = self.engine.process(BrainRequest(message="check rename target"))

        self.assertEqual(
            available.message,
            "Session rename target available: Work Archive",
        )
        self.assertTrue(available.success)
        self.assertEqual(
            unavailable.message,
            "Session rename target unavailable: archive",
        )
        self.assertTrue(unavailable.success)
        self.assertEqual(
            default_target.message,
            "Session rename target unavailable: default",
        )
        self.assertTrue(default_target.success)
        self.assertEqual(failure.message, "Session target ID must not be empty.")
        self.assertFalse(failure.success)
        for check_response in (available, unavailable, default_target, failure):
            self.assertEqual(check_response.intent, "session_rename_target_check")
            self.assertEqual(check_response.memory_count, 0)
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])
        self.assertTrue(
            self.engine.process(
                BrainRequest(message="preview rename session work-1 -- renamed")
            ).success
        )
        self.assertTrue(
            self.engine.process(
                BrainRequest(message="rename session work-1 -- renamed")
            ).success
        )

    def test_empty_search_query_is_saved_to_memory(self) -> None:
        self.engine.process(BrainRequest(message="search "))

        self.assertEqual(
            self.memory_manager.all()[0].content,
            "User: search \nHypatia: A search query is required.",
        )
        self.assertEqual(
            dict(self.memory_manager.all()[0].metadata),
            {
                "intent": "search",
                "query": "",
                "result_count": 0,
                "success": False,
            },
        )

    def test_search_with_no_results_returns_empty_result_list(self) -> None:
        response = self.engine.process(BrainRequest(message="search missing"))

        self.assertTrue(response.success)
        self.assertEqual(response.knowledge_results, [])
        self.assertEqual(response.message, "I found 0 matching knowledge chunks.")

    def test_greeting_is_processed_as_a_conversation(self) -> None:
        response = self.engine.process(BrainRequest(message="hello"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "greeting")
        self.assertEqual(response.message, "Hello! I am Hypatia.")

    def test_message_is_processed_as_a_conversation(self) -> None:
        response = self.engine.process(BrainRequest(message="how are you"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "message")
        self.assertEqual(response.message, "I received your message: how are you")
        self.assertEqual(len(self.memory_manager.all()), 1)

    def test_conversation_without_a_session_id_uses_the_default_session(self) -> None:
        self.engine.process(BrainRequest(message="hello"))

        self.assertEqual(
            self.memory_manager.all()[0].metadata["session_id"],
            "default",
        )

    def test_none_empty_and_whitespace_session_ids_use_the_default_session(
        self,
    ) -> None:
        for session_id in (None, "", "   "):
            with self.subTest(session_id=session_id):
                self.memory_manager.clear()
                self.engine.process(
                    BrainRequest(message="hello", metadata={"session_id": session_id})
                )

                self.assertEqual(
                    self.memory_manager.all()[0].metadata["session_id"],
                    "default",
                )

    def test_conversation_normalizes_a_string_session_id_without_mutating_request(
        self,
    ) -> None:
        metadata = {"session_id": "  work-1  "}
        request = BrainRequest(message="hello", metadata=metadata)

        self.engine.process(request)

        self.assertEqual(self.memory_manager.all()[0].metadata["session_id"], "work-1")
        self.assertEqual(metadata, {"session_id": "  work-1  "})

    def test_non_string_session_id_returns_a_controlled_failure_without_side_effects(
        self,
    ) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = self.engine.process(
            BrainRequest(message="hello", metadata={"session_id": 123})
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "session_id must be a string.")
        self.assertEqual(self.memory_manager.count(), 0)
        self.assertEqual(events, [])

    def test_create_session_uses_the_registry_without_conversation_side_effects(
        self,
    ) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = self.engine.process(BrainRequest(message="create session Work-2"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_create")
        self.assertEqual(
            response.message,
            "Session created:\nID: Work-2\nStatus: ready",
        )
        self.assertTrue(self.session_manager.exists("Work-2"))
        self.assertEqual(self.memory_manager.count(), 0)
        self.assertEqual(events, ["session.created"])

    def test_duplicate_session_create_is_idempotent_without_side_effects(
        self,
    ) -> None:
        self.session_manager.create("work-2")
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = self.engine.process(BrainRequest(message="create session work-2"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_create")
        self.assertEqual(response.message, "Session already exists: work-2")
        self.assertEqual(self.memory_manager.count(), 0)
        self.assertEqual(events, [])

    def test_list_sessions_preserves_order_and_marks_the_active_session(self) -> None:
        response = self.engine.process(BrainRequest(message="list sessions"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_list")
        self.assertEqual(
            response.message,
            "Sessions:\n1. default (active)\n2. work-1\n3. personal",
        )
        self.assertEqual(self.memory_manager.count(), 0)

    def test_use_session_activates_an_existing_session_without_memory_writes(
        self,
    ) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = self.engine.process(BrainRequest(message="use session work-1"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_use")
        self.assertEqual(response.message, "Active session: work-1")
        self.assertEqual(self.session_manager.get_active().session_id, "work-1")
        self.assertEqual(self.memory_manager.count(), 0)
        self.assertEqual(events, ["session.activated"])

    def test_use_active_session_is_a_no_op_without_memory_writes_or_events(
        self,
    ) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        before = self.session_manager.snapshot()

        response = self.engine.process(BrainRequest(message="use session default"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_use")
        self.assertEqual(response.message, "Active session: default")
        self.assertEqual(self.session_manager.snapshot(), before)
        self.assertEqual(self.memory_manager.count(), 0)
        self.assertEqual(events, [])

    def test_use_unknown_session_returns_a_controlled_failure(self) -> None:
        response = self.engine.process(BrainRequest(message="use session unknown"))

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Unknown session: unknown")
        self.assertEqual(self.session_manager.get_active().session_id, "default")
        self.assertEqual(self.memory_manager.count(), 0)

    def test_session_delete_preview_is_read_only_and_reports_policy_decision(
        self,
    ) -> None:
        self.memory_manager.add(
            "Work",
            metadata={"session_id": "work-1"},
            tags={"brain", "conversation"},
        )
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        response = self.engine.process(
            BrainRequest(message="preview delete session work-1")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_delete_preview")
        self.assertEqual(
            response.message,
            "Delete preview:\nSession: work-1\nDecision: PENDING_MEMORY_POLICY\n"
            "Reason: session has attached memories",
        )
        self.assertEqual(response.memory_count, 1)
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_delete_preview_maps_memory_failure_without_composing(
        self,
    ) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.engine._session_delete_preview_service,
                "preview",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "session_delete_preview",
                wraps=self.response_composer.session_delete_preview,
            ) as session_delete_preview,
            patch.object(
                self.response_composer,
                "session_deleted",
                wraps=self.response_composer.session_deleted,
            ) as session_deleted,
            patch.object(
                self.response_composer,
                "session_delete_event_failure",
                wraps=self.response_composer.session_delete_event_failure,
            ) as session_delete_event_failure,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="preview delete session personal",
                    request_id="request-123",
                )
            )

        session_delete_preview.assert_not_called()
        session_deleted.assert_not_called()
        session_delete_event_failure.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_delete_preview")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Delete preview failed:\nReason: Memory snapshot changed.",
        )
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_delete_preview_maps_runtime_failure_without_composing(
        self,
    ) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.engine._session_delete_preview_service,
                "preview",
                side_effect=RuntimeError("Session store unavailable."),
            ),
            patch.object(
                self.response_composer,
                "session_delete_preview",
                wraps=self.response_composer.session_delete_preview,
            ) as session_delete_preview,
            patch.object(
                self.response_composer,
                "session_deleted",
                wraps=self.response_composer.session_deleted,
            ) as session_deleted,
            patch.object(
                self.response_composer,
                "session_delete_event_failure",
                wraps=self.response_composer.session_delete_event_failure,
            ) as session_delete_event_failure,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="preview delete session personal",
                    request_id="request-123",
                )
            )

        session_delete_preview.assert_not_called()
        session_deleted.assert_not_called()
        session_delete_event_failure.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_delete_preview")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Delete preview failed:\nReason: Session store unavailable.",
        )
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_delete_returns_a_committed_delete_response(self) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = self.engine.process(
            BrainRequest(message="delete session personal", request_id="request-123")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_delete")
        self.assertEqual(
            response.message,
            "Session deleted:\nID: personal\nMemory records removed: 0\n"
            "Status: committed",
        )
        self.assertEqual(response.memory_count, 0)
        self.assertFalse(self.session_manager.exists("personal"))
        self.assertEqual(self.memory_manager.count(), 0)
        self.assertEqual(events, ["session.deleted"])

    def test_session_delete_rejects_an_uncommitted_result_before_composing(
        self,
    ) -> None:
        result = SessionDeleteExecutionResult(
            session_id="personal",
            memory_records_removed=0,
            committed=False,
        )

        with (
            patch.object(
                self.engine._session_delete_service,
                "delete",
                return_value=result,
            ),
            patch.object(
                self.response_composer,
                "session_deleted",
                wraps=self.response_composer.session_deleted,
            ) as session_deleted,
            self.assertRaisesRegex(
                ValueError,
                "Session delete result must be committed.",
            ),
        ):
            self.engine.process(BrainRequest(message="delete session personal"))

        session_deleted.assert_not_called()

    def test_session_delete_maps_pre_commit_domain_errors_without_side_effects(
        self,
    ) -> None:
        for message, expected_reason in (
            ("delete session missing", "Unknown session: missing"),
            ("delete session default", "default session cannot be deleted"),
        ):
            with self.subTest(message=message):
                sessions_before = self.session_manager.snapshot()
                memory_before = self.memory_manager.snapshot()
                events: list[object] = []
                self.event_bus.subscribe("*", events.append)

                response = self.engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_delete")
                self.assertEqual(
                    response.message,
                    f"Delete failed:\nReason: {expected_reason}",
                )
                self.assertEqual(response.memory_count, 0)
                self.assertEqual(self.session_manager.snapshot(), sessions_before)
                self.assertEqual(self.memory_manager.snapshot(), memory_before)
                self.assertEqual(events, [])

    def test_session_delete_composes_committed_event_failure_warning(
        self,
    ) -> None:
        error = SessionDeleteEventError(
            SessionDeleteExecutionResult(
                session_id="personal",
                memory_records_removed=0,
                committed=True,
            ),
            RuntimeError("event bus unavailable"),
        )

        with (
            patch.object(
                self.engine._session_delete_service,
                "delete",
                side_effect=error,
            ),
            patch.object(
                self.response_composer,
                "session_delete_failure",
                wraps=self.response_composer.session_delete_failure,
            ) as session_delete_failure,
            patch.object(
                self.response_composer,
                "session_deleted",
                wraps=self.response_composer.session_deleted,
            ) as session_deleted,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="delete session personal",
                    request_id="request-123",
                )
            )

        session_delete_failure.assert_not_called()
        session_deleted.assert_not_called()
        self.assertTrue(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_delete")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Session deleted:\nID: personal\nMemory records removed: 0\n"
            "Status: committed\nWarning: lifecycle event publication failed",
        )

    def test_session_delete_rejects_an_uncommitted_event_failure_result(
        self,
    ) -> None:
        error = SessionDeleteEventError(
            SessionDeleteExecutionResult(
                session_id="personal",
                memory_records_removed=0,
                committed=False,
            ),
            RuntimeError("event bus unavailable"),
        )

        with patch.object(
            self.engine._session_delete_service,
            "delete",
            side_effect=error,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Session delete event failure result must be committed.",
            ):
                self.engine.process(BrainRequest(message="delete session personal"))

    def test_session_delete_maps_memory_concurrency_failure_without_composing(
        self,
    ) -> None:
        with (
            patch.object(
                self.engine._session_delete_service,
                "delete",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "session_deleted",
                wraps=self.response_composer.session_deleted,
            ) as session_deleted,
            patch.object(
                self.response_composer,
                "session_delete_event_failure",
                wraps=self.response_composer.session_delete_event_failure,
            ) as session_delete_event_failure,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="delete session personal", request_id="request-123"
                )
            )

        session_deleted.assert_not_called()
        session_delete_event_failure.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_delete")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Delete failed:\nReason: Memory snapshot changed.",
        )
        self.assertTrue(self.session_manager.exists("personal"))
        self.assertEqual(self.memory_manager.count(), 0)

    def test_session_delete_maps_transaction_guard_value_error_without_composing(
        self,
    ) -> None:
        error = ValueError(
            "Session delete transaction is no longer allowed: "
            "active session cannot be deleted."
        )

        with (
            patch.object(
                self.engine._session_delete_service,
                "delete",
                side_effect=error,
            ),
            patch.object(
                self.response_composer,
                "session_deleted",
                wraps=self.response_composer.session_deleted,
            ) as session_deleted,
            patch.object(
                self.response_composer,
                "session_delete_event_failure",
                wraps=self.response_composer.session_delete_event_failure,
            ) as session_delete_event_failure,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="delete session personal", request_id="request-123"
                )
            )

        session_deleted.assert_not_called()
        session_delete_event_failure.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_delete")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Delete failed:\nReason: Session delete transaction is no longer "
            "allowed: active session cannot be deleted.",
        )
        self.assertTrue(self.session_manager.exists("personal"))
        self.assertEqual(self.memory_manager.count(), 0)

    def test_session_delete_maps_persistence_runtime_error_without_composing(
        self,
    ) -> None:
        with (
            patch.object(
                self.engine._session_delete_service,
                "delete",
                side_effect=RuntimeError("Session registry persistence failed."),
            ),
            patch.object(
                self.response_composer,
                "session_deleted",
                wraps=self.response_composer.session_deleted,
            ) as session_deleted,
            patch.object(
                self.response_composer,
                "session_delete_event_failure",
                wraps=self.response_composer.session_delete_event_failure,
            ) as session_delete_event_failure,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="delete session personal", request_id="request-123"
                )
            )

        session_deleted.assert_not_called()
        session_delete_event_failure.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_delete")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Delete failed:\nReason: Session registry persistence failed.",
        )
        self.assertTrue(self.session_manager.exists("personal"))
        self.assertEqual(self.memory_manager.count(), 0)

    def test_session_delete_maps_real_persistence_failure_without_composing(
        self,
    ) -> None:
        class FailingSessionStore:
            def save(self, snapshot: object) -> None:
                raise RuntimeError("session store unavailable")

        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)
        self.session_manager._store = cast(SessionStore, FailingSessionStore())

        with (
            patch.object(
                self.response_composer,
                "session_deleted",
                wraps=self.response_composer.session_deleted,
            ) as session_deleted,
            patch.object(
                self.response_composer,
                "session_delete_event_failure",
                wraps=self.response_composer.session_delete_event_failure,
            ) as session_delete_event_failure,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="delete session personal", request_id="request-123"
                )
            )

        session_deleted.assert_not_called()
        session_delete_event_failure.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_delete")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Delete failed:\nReason: session store unavailable",
        )
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_overview_counts_only_registered_normal_conversations(
        self,
    ) -> None:
        records: tuple[tuple[str, Mapping[str, object], set[str]], ...] = (
            ("Legacy default", {}, {"brain", "conversation"}),
            (
                "Default with extra tag",
                {"session_id": "default"},
                {"brain", "conversation", "extra"},
            ),
            ("Work conversation", {"session_id": "work-1"}, {"brain", "conversation"}),
            (
                "Personal conversation",
                {"session_id": "personal"},
                {"brain", "conversation"},
            ),
            ("None session", {"session_id": None}, {"brain", "conversation"}),
            ("Numeric session", {"session_id": 123}, {"brain", "conversation"}),
            ("Orphan session", {"session_id": "orphan"}, {"brain", "conversation"}),
            ("Brain only", {"session_id": "default"}, {"brain"}),
            ("Conversation only", {"session_id": "default"}, {"conversation"}),
            ("Plan record", {"session_id": "default"}, {"brain", "plan"}),
            (
                "Knowledge search record",
                {"session_id": "default"},
                {"conversation", "knowledge-search"},
            ),
        )
        for content, metadata, tags in records:
            self.memory_manager.add(content, metadata=metadata, tags=tags)
        self.session_manager.set_active("work-1")
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        memory_count = self.memory_manager.count()

        for metadata in (
            {},
            {"session_id": "personal"},
            {"session_id": 123},
            {"session_id": None},
            {"session_id": ""},
        ):
            with self.subTest(metadata=metadata):
                response = self.engine.process(
                    BrainRequest(message="session overview", metadata=metadata)
                )

                self.assertTrue(response.success)
                self.assertEqual(response.intent, "session_overview")
                self.assertEqual(
                    response.message,
                    "Sessions:\n"
                    "1. default — 2 conversations\n"
                    "2. work-1 — 1 conversation [active]\n"
                    "3. personal — 1 conversation",
                )
                self.assertEqual(response.memory_count, 4)
                self.assertEqual(self.memory_manager.count(), memory_count)
                self.assertEqual(self.session_manager.get_active().session_id, "work-1")

        self.assertEqual(events, [])

    def test_session_overview_reads_memory_once_without_resolving_request_session(
        self,
    ) -> None:
        memory_manager = RecordingSessionOverviewMemoryManager(
            [
                MemoryRecord(
                    memory_id="default-record",
                    content="Legacy default",
                    tags=frozenset({"brain", "conversation"}),
                )
            ]
        )
        engine = SessionOverviewMustNotResolveEngine(
            self.knowledge_engine,
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="session overview", metadata={"session_id": 123})
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_overview")
        self.assertEqual(memory_manager.all_calls, 1)
        self.assertIn("1. default — 1 conversation [active]", response.message)

    def test_session_overview_delegates_record_matching_to_the_shared_policy(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="default-record",
            content="Legacy default",
            tags=frozenset({"brain", "conversation"}),
        )
        memory_manager = RecordingSessionOverviewMemoryManager([record])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        with patch.object(
            SessionMemoryPolicy,
            "matches",
            wraps=SessionMemoryPolicy.matches,
        ) as matches:
            response = engine.process(BrainRequest(message="session overview"))

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.all_calls, 1)
        matches.assert_called_once_with(record, "default")

    def test_session_overview_maps_memory_failure_without_composing(self) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.memory_manager,
                "all",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "session_overview",
                wraps=self.response_composer.session_overview,
            ) as session_overview,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="session overview",
                    request_id="request-123",
                )
            )

        session_overview.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_overview")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "Memory snapshot changed.")
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_details_counts_only_target_normal_conversations(self) -> None:
        records = (
            (
                "Target conversation",
                {"session_id": "work-1"},
                {"brain", "conversation"},
            ),
            (
                "Target with extra tag",
                {"session_id": "work-1"},
                {"brain", "conversation", "extra"},
            ),
            ("Other session", {"session_id": "personal"}, {"brain", "conversation"}),
            ("None session", {"session_id": None}, {"brain", "conversation"}),
            ("Orphan session", {"session_id": "orphan"}, {"brain", "conversation"}),
            (
                "Search record",
                {"session_id": "work-1"},
                {"cognition", "knowledge-search", "conversation"},
            ),
            ("Plan record", {"session_id": "work-1"}, {"brain", "plan"}),
        )
        for content, metadata, tags in records:
            self.memory_manager.add(content, metadata=metadata, tags=tags)
        self.session_manager.set_active("personal")
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        memory_count = self.memory_manager.count()

        response = self.engine.process(
            BrainRequest(
                message="session details work-1",
                metadata={"session_id": 123},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_details")
        self.assertIn("Session: work-1", response.message)
        self.assertIn("Status: inactive", response.message)
        self.assertIn("Conversations: 2 conversations", response.message)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(self.session_manager.get_active().session_id, "personal")
        self.assertEqual(events, [])

    def test_session_details_treats_only_missing_session_metadata_as_default(
        self,
    ) -> None:
        self.memory_manager.add(
            "Legacy default",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null default",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="session details default"))

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Conversations: 1 conversation", response.message)

    def test_session_details_reads_memory_once_without_resolving_request_session(
        self,
    ) -> None:
        memory_manager = RecordingSessionOverviewMemoryManager(
            [
                MemoryRecord(
                    memory_id="work-record",
                    content="Work conversation",
                    metadata={"session_id": "work-1"},
                    tags=frozenset({"brain", "conversation"}),
                )
            ]
        )
        engine = SessionDetailsMustNotResolveEngine(
            self.knowledge_engine,
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(
                message="SESSION DETAILS work-1",
                metadata={"session_id": 123},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_details")
        self.assertEqual(memory_manager.all_calls, 1)
        self.assertIn("Session: work-1", response.message)

    def test_session_details_empty_and_unknown_ids_do_not_read_memory(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            RecentConversationsMustNotReadMemoryManager(),
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for message, expected in (
            ("session details", "Session ID must not be empty."),
            ("session details unknown", "Unknown session: unknown"),
        ):
            with self.subTest(message=message):
                response = engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_details")
                self.assertEqual(response.message, expected)

    def test_session_details_maps_memory_failure_without_composing(self) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.memory_manager,
                "all",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "session_details",
                wraps=self.response_composer.session_details,
            ) as session_details,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="session details personal",
                    request_id="request-123",
                )
            )

        session_details.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_details")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "Memory snapshot changed.")
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_details_delegates_record_matching_to_the_shared_policy(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="work-record",
            content="Work conversation",
            metadata={"session_id": "work-1"},
            tags=frozenset({"brain", "conversation"}),
        )
        memory_manager = RecordingSessionOverviewMemoryManager([record])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        with patch.object(
            SessionMemoryPolicy,
            "matches",
            wraps=SessionMemoryPolicy.matches,
        ) as matches:
            response = engine.process(BrainRequest(message="session details work-1"))

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.all_calls, 1)
        matches.assert_called_once_with(record, "work-1")

    def test_session_activity_aggregates_only_target_conversations(self) -> None:
        self.session_manager.create("Work Research")
        self.session_manager.set_active("personal")
        records = [
            MemoryRecord(
                memory_id="middle",
                content="Middle activity",
                metadata={"session_id": "Work Research"},
                tags=frozenset({"brain", "conversation"}),
                created_at=datetime(2026, 8, 5, 10, 0, tzinfo=UTC),
            ),
            MemoryRecord(
                memory_id="newest",
                content="Newest activity",
                metadata={"session_id": "Work Research"},
                tags=frozenset({"brain", "conversation", "extra"}),
                created_at=datetime(2026, 8, 6, 10, 0, tzinfo=UTC),
            ),
            MemoryRecord(
                memory_id="oldest",
                content="Oldest activity",
                metadata={"session_id": "Work Research"},
                tags=frozenset({"brain", "conversation"}),
                created_at=datetime(2026, 8, 4, 10, 0, tzinfo=UTC),
            ),
            MemoryRecord(
                memory_id="other",
                content="Other session",
                metadata={"session_id": "personal"},
                tags=frozenset({"brain", "conversation"}),
            ),
            MemoryRecord(
                memory_id="none",
                content="None session",
                metadata={"session_id": None},
                tags=frozenset({"brain", "conversation"}),
            ),
            MemoryRecord(
                memory_id="orphan",
                content="Orphan session",
                metadata={"session_id": "orphan"},
                tags=frozenset({"brain", "conversation"}),
            ),
            MemoryRecord(
                memory_id="search",
                content="Knowledge record",
                metadata={"session_id": "Work Research"},
                tags=frozenset({"cognition", "knowledge-search", "conversation"}),
            ),
        ]
        memory_manager = RecordingSessionOverviewMemoryManager(records)
        engine = SessionActivityMustNotResolveEngine(
            self.knowledge_engine,
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(
                message="SESSION ACTIVITY Work Research",
                metadata={"session_id": 123, "intent": "search"},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_activity")
        self.assertEqual(memory_manager.all_calls, 1)
        self.assertEqual(response.memory_count, 3)
        self.assertIn("Session: Work Research", response.message)
        self.assertIn("First activity: 2026-08-04T10:00:00+00:00", response.message)
        self.assertIn("Last activity: 2026-08-06T10:00:00+00:00", response.message)
        self.assertEqual(self.session_manager.get_active().session_id, "personal")

    def test_session_activity_maps_memory_failure_without_composing(self) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.memory_manager,
                "all",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "session_activity",
                wraps=self.response_composer.session_activity,
            ) as session_activity,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="session activity personal",
                    request_id="request-123",
                )
            )

        session_activity.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_activity")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "Memory snapshot changed.")
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_activity_treats_only_missing_metadata_as_default(self) -> None:
        self.memory_manager.add("Legacy default", tags={"brain", "conversation"})
        self.memory_manager.add(
            "Explicit default",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null default",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        memory_count = self.memory_manager.count()

        response = self.engine.process(BrainRequest(message="session activity default"))

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(events, [])

    def test_session_activity_empty_and_unknown_ids_do_not_read_memory(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            SessionActivityMustNotReadMemoryManager(),
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for message, expected in (
            ("session activity", "Session ID must not be empty."),
            ("session activity unknown", "Unknown session: unknown"),
        ):
            with self.subTest(message=message):
                response = engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_activity")
                self.assertEqual(response.message, expected)

    def test_session_activity_empty_registered_session_is_successful(self) -> None:
        self.session_manager.create("empty-session")
        memory_manager = RecordingSessionOverviewMemoryManager([])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="session activity empty-session")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_activity")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(memory_manager.all_calls, 1)
        self.assertIn("First activity: none", response.message)
        self.assertIn("Last activity: none", response.message)

    def test_session_activity_delegates_record_matching_to_the_shared_policy(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="work-record",
            content="Work conversation",
            metadata={"session_id": "work"},
            tags=frozenset({"brain", "conversation"}),
            created_at=datetime.now(UTC),
        )
        self.session_manager.create("work")
        memory_manager = RecordingSessionOverviewMemoryManager([record])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        with patch.object(
            SessionMemoryPolicy,
            "matches",
            wraps=SessionMemoryPolicy.matches,
        ) as matches:
            response = engine.process(BrainRequest(message="session activity work"))

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.all_calls, 1)
        matches.assert_called_once_with(record, "work")

    def test_session_recent_uses_the_complete_suffix_and_filters_before_limiting(
        self,
    ) -> None:
        self.session_manager.create("work research")
        now = datetime.now(UTC)
        records = [
            MemoryRecord(
                memory_id=f"target-{index}",
                content=f"Target conversation {index}",
                metadata={"session_id": "work research"},
                tags=frozenset({"brain", "conversation"}),
                created_at=now + timedelta(seconds=index),
            )
            for index in range(6)
        ]
        records.extend(
            [
                MemoryRecord(
                    memory_id="other-session",
                    content="Other session",
                    metadata={"session_id": "work-1"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(minutes=1),
                ),
                MemoryRecord(
                    memory_id="search-record",
                    content="Search record",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"cognition", "knowledge-search", "conversation"}),
                    created_at=now + timedelta(minutes=2),
                ),
                MemoryRecord(
                    memory_id="null-record",
                    content="Null record",
                    metadata={"session_id": None},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(minutes=3),
                ),
            ]
        )
        memory_manager = RecordingSessionOverviewMemoryManager(records)
        engine = SessionRecentMustNotResolveEngine(
            self.knowledge_engine,
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(
                message="SESSION RECENT work research",
                metadata={"session_id": 123},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_recent")
        self.assertEqual(memory_manager.all_calls, 1)
        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. Target conversation 5", response.message)
        self.assertIn("5. Target conversation 1", response.message)
        self.assertNotIn("Target conversation 0", response.message)
        self.assertNotIn("Other session", response.message)
        self.assertNotIn("Search record", response.message)
        self.assertNotIn("Null record", response.message)

    def test_session_recent_treats_only_missing_session_metadata_as_default(
        self,
    ) -> None:
        self.memory_manager.add(
            "Legacy default",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null default",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="session recent default"))

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Legacy default", response.message)
        self.assertNotIn("Null default", response.message)

    def test_session_recent_maps_memory_failure_without_composing(self) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.memory_manager,
                "all",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "session_recent",
                wraps=self.response_composer.session_recent,
            ) as session_recent,
            patch.object(
                self.response_composer,
                "session_recent_empty",
                wraps=self.response_composer.session_recent_empty,
            ) as session_recent_empty,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="session recent personal",
                    request_id="request-123",
                )
            )

        session_recent.assert_not_called()
        session_recent_empty.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_recent")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "Memory snapshot changed.")
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_recent_delegates_record_matching_to_the_shared_policy(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="work-record",
            content="Work conversation",
            metadata={"session_id": "work"},
            tags=frozenset({"brain", "conversation"}),
            created_at=datetime.now(UTC),
        )
        self.session_manager.create("work")
        memory_manager = RecordingSessionOverviewMemoryManager([record])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        with patch.object(
            SessionMemoryPolicy,
            "matches",
            wraps=SessionMemoryPolicy.matches,
        ) as matches:
            response = engine.process(BrainRequest(message="session recent work"))

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.all_calls, 1)
        matches.assert_called_once_with(record, "work")

    def test_session_recent_empty_and_unknown_ids_do_not_read_memory(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            RecentConversationsMustNotReadMemoryManager(),
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for message, expected in (
            ("session recent", "Session ID must not be empty."),
            ("session recent unknown", "Unknown session: unknown"),
        ):
            with self.subTest(message=message):
                response = engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_recent")
                self.assertEqual(response.message, expected)

    def test_session_search_filters_after_relevance_order_without_resolving_request(
        self,
    ) -> None:
        self.session_manager.create("work research")
        records = [
            MemoryRecord(
                memory_id=f"target-{index}",
                content=f"Target relevance {index}",
                metadata={"session_id": "work research"},
                tags=frozenset({"brain", "conversation"}),
                created_at=datetime(2026, 8, 5, 10 - index, tzinfo=UTC),
            )
            for index in range(6)
        ]
        records.extend(
            [
                MemoryRecord(
                    memory_id="other-session",
                    content="Other relevance",
                    metadata={"session_id": "work-1"},
                    tags=frozenset({"brain", "conversation"}),
                ),
                MemoryRecord(
                    memory_id="knowledge-record",
                    content="Knowledge relevance",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"cognition", "knowledge-search", "conversation"}),
                ),
                MemoryRecord(
                    memory_id="null-record",
                    content="Null relevance",
                    metadata={"session_id": None},
                    tags=frozenset({"brain", "conversation"}),
                ),
            ]
        )
        memory_manager = RecordingConversationSearchMemoryManager(records)
        engine = SessionSearchMustNotResolveEngine(
            KnowledgeSearchMustNotRun(),
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(
                message="SESSION SEARCH work research -- Persistence Contract",
                metadata={"session_id": 123, "intent": "search"},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_search")
        self.assertEqual(memory_manager.calls, [("Persistence Contract", None)])
        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. Target relevance 0", response.message)
        self.assertIn("5. Target relevance 4", response.message)
        self.assertNotIn("Target relevance 5", response.message)
        self.assertNotIn("Other relevance", response.message)
        self.assertNotIn("Knowledge relevance", response.message)
        self.assertNotIn("Null relevance", response.message)

    def test_session_search_default_target_treats_only_missing_metadata_as_legacy(
        self,
    ) -> None:
        self.memory_manager.add("Legacy match", tags={"brain", "conversation"})
        self.memory_manager.add(
            "Explicit default match",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null match",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(
            BrainRequest(message="session search default -- match")
        )

        self.assertEqual(response.memory_count, 2)
        self.assertIn("Legacy match", response.message)
        self.assertIn("Explicit default match", response.message)
        self.assertNotIn("Null match", response.message)

    def test_session_search_maps_memory_failure_without_composing(self) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.memory_manager,
                "search",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "session_search_results",
                wraps=self.response_composer.session_search_results,
            ) as session_search_results,
            patch.object(
                self.response_composer,
                "session_search_empty",
                wraps=self.response_composer.session_search_empty,
            ) as session_search_empty,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="session search personal -- project",
                    request_id="request-123",
                )
            )

        session_search_results.assert_not_called()
        session_search_empty.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "session_search")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "Memory snapshot changed.")
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_session_search_delegates_record_matching_to_the_shared_policy(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="work-record",
            content="Work conversation",
            metadata={"session_id": "work"},
            tags=frozenset({"brain", "conversation"}),
            created_at=datetime.now(UTC),
        )
        self.session_manager.create("work")
        memory_manager = RecordingConversationSearchMemoryManager([record])
        engine = CognitiveEngine(
            self.knowledge_engine,
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        with patch.object(
            SessionMemoryPolicy,
            "matches",
            wraps=SessionMemoryPolicy.matches,
        ) as matches:
            response = engine.process(
                BrainRequest(message="session search work -- conversation")
            )

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.calls, [("conversation", None)])
        matches.assert_called_once_with(record, "work")

    def test_session_search_failures_do_not_read_memory(self) -> None:
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),
            SessionSearchMustNotReadMemoryManager(),
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for message, expected in (
            ("session search work-1", "Search query separator is required: --"),
            ("session search -- persistence", "Session ID must not be empty."),
            ("session search work-1 --", "Search query must not be empty."),
            ("session search unknown -- persistence", "Unknown session: unknown"),
        ):
            with self.subTest(message=message):
                response = engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "session_search")
                self.assertEqual(response.message, expected)

    def test_active_session_is_used_when_conversation_has_no_session_override(
        self,
    ) -> None:
        self.session_manager.set_active("work-1")

        self.engine.process(BrainRequest(message="hello"))

        self.assertEqual(
            self.memory_manager.all()[0].metadata["session_id"],
            "work-1",
        )

    def test_blank_session_override_uses_the_active_session(self) -> None:
        self.session_manager.set_active("work-1")

        self.engine.process(BrainRequest(message="hello", metadata={"session_id": ""}))

        self.assertEqual(
            self.memory_manager.all()[0].metadata["session_id"],
            "work-1",
        )

    def test_request_session_override_does_not_change_the_active_session(self) -> None:
        self.session_manager.set_active("work-1")

        self.engine.process(
            BrainRequest(message="hello", metadata={"session_id": "default"})
        )

        self.assertEqual(
            self.memory_manager.all()[0].metadata["session_id"],
            "default",
        )
        self.assertEqual(self.session_manager.get_active().session_id, "work-1")

    def test_unknown_session_override_prevents_conversation_side_effects(self) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = self.engine.process(
            BrainRequest(message="hello", metadata={"session_id": "unknown"})
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Unknown session: unknown")
        self.assertEqual(self.memory_manager.count(), 0)
        self.assertEqual(events, [])

    def test_knowledge_error_returns_unsuccessful_response(self) -> None:
        memory_manager = MemoryManager()
        engine = CognitiveEngine(
            FailingKnowledgeEngine(),
            memory_manager,
            Planner(),
            EventBus(),
            ResponseComposer(),
            SessionManager(),
        )

        response = engine.process(BrainRequest(message="search hypatia"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "search")
        self.assertEqual(response.knowledge_results, [])

    def test_knowledge_error_response_is_saved_to_memory(self) -> None:
        memory_manager = MemoryManager()
        engine = CognitiveEngine(
            FailingKnowledgeEngine(),
            memory_manager,
            Planner(),
            EventBus(),
            ResponseComposer(),
            SessionManager(),
        )

        engine.process(BrainRequest(message="search hypatia"))

        self.assertEqual(
            memory_manager.all()[0].content,
            "User: search hypatia"
            "\nHypatia: Knowledge search failed: Knowledge is unavailable.",
        )

    def test_memory_error_does_not_prevent_a_successful_search_response(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            FailingMemoryManager(),
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(BrainRequest(message="search hypatia"))

        self.assertTrue(response.success)
        self.assertEqual(len(response.knowledge_results), 2)

    def test_plan_intent_returns_a_formatted_plan_response(self) -> None:
        response = self.engine.process(
            BrainRequest(message="plan Read a PDF and summarize it")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "plan")
        self.assertEqual(
            response.message,
            "Plan created for: Read a PDF and summarize it\n\n"
            "1. Locate file\n"
            "2. Read document\n"
            "3. Extract text\n"
            "4. Summarize\n"
            "5. Return response",
        )

    def test_planner_error_returns_controlled_response(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            FailingPlanner(),
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(BrainRequest(message="plan learn SQL injection"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "plan")
        self.assertEqual(response.message, "Planning failed: Planner is unavailable.")

    def test_recall_returns_matching_conversation_records(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Cats are animals.",
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "recall")
        self.assertEqual(response.memory_count, 1)
        self.assertIn("1. User: cats\nHypatia: Cats are animals.", response.message)

    def test_recall_matching_is_case_insensitive(self) -> None:
        self.memory_manager.add(
            "User: Cats\nHypatia: Cats are animals.",
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="recall CATS"))

        self.assertEqual(response.memory_count, 1)

    def test_recall_excludes_knowledge_search_records(self) -> None:
        self.memory_manager.add(
            "User: search cats\nHypatia: I found 1 matching knowledge chunks.",
            tags={"cognition", "knowledge-search", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Cats are animals.",
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertEqual(response.memory_count, 1)
        self.assertNotIn("search cats", response.message)
        self.assertIn("Cats are animals.", response.message)

    def test_recall_returns_at_most_the_first_five_matching_records(self) -> None:
        for index in range(6):
            self.memory_manager.add(
                f"User: cats {index}\nHypatia: response {index}",
                tags={"brain", "conversation"},
            )

        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. User: cats 0", response.message)
        self.assertIn("5. User: cats 4", response.message)
        self.assertNotIn("cats 5", response.message)

    def test_recall_with_no_matches_returns_a_successful_empty_response(self) -> None:
        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "No matching conversation records found.")

    def test_recall_maps_memory_failure_without_composing(self) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.memory_manager,
                "search",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "recall_success",
                wraps=self.response_composer.recall_success,
            ) as recall_success,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="recall project",
                    request_id="request-123",
                )
            )

        recall_success.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "recall")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "Memory snapshot changed.")
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_empty_recall_returns_a_controlled_failure(self) -> None:
        response = self.engine.process(BrainRequest(message="recall"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "recall")
        self.assertEqual(response.message, "A recall query is required.")

    def test_recall_does_not_create_a_new_memory_record(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Cats are animals.",
            tags={"brain", "conversation"},
        )

        self.engine.process(BrainRequest(message="recall cats"))

        self.assertEqual(self.memory_manager.count(), 1)

    def test_declared_recall_intent_uses_request_message_as_query(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Cats are animals.",
            tags={"brain", "conversation"},
        )

        response = self.engine.process(
            BrainRequest(message="cats", metadata={"intent": "recall"})
        )

        self.assertEqual(response.intent, "recall")
        self.assertEqual(response.memory_count, 1)

    def test_recall_word_inside_a_sentence_remains_a_message(self) -> None:
        response = self.engine.process(BrainRequest(message="please recall cats"))

        self.assertEqual(response.intent, "message")
        self.assertEqual(
            response.message,
            "I received your message: please recall cats",
        )

    def test_default_session_recall_includes_legacy_records(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Legacy conversation.",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Default conversation.",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertEqual(response.memory_count, 2)
        self.assertIn("Legacy conversation.", response.message)
        self.assertIn("Default conversation.", response.message)

    def test_active_session_is_used_when_recall_has_no_session_override(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Default conversation.",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Work conversation.",
            metadata={"session_id": "work-1"},
            tags={"brain", "conversation"},
        )
        self.session_manager.set_active("work-1")

        response = self.engine.process(BrainRequest(message="recall cats"))

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Work conversation.", response.message)
        self.assertNotIn("Default conversation.", response.message)

    def test_recall_session_override_does_not_change_the_active_session(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Default conversation.",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.session_manager.set_active("work-1")

        response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "default"})
        )

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Default conversation.", response.message)
        self.assertEqual(self.session_manager.get_active().session_id, "work-1")

    def test_custom_session_recall_returns_only_its_records(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Default conversation.",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Work conversation.",
            metadata={"session_id": "work-1"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Personal conversation.",
            metadata={"session_id": "personal"},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "work-1"})
        )

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Work conversation.", response.message)
        self.assertNotIn("Default conversation.", response.message)
        self.assertNotIn("Personal conversation.", response.message)

    def test_recall_applies_the_limit_after_session_filtering(self) -> None:
        for index in range(5):
            self.memory_manager.add(
                f"User: cats other {index}\nHypatia: other {index}",
                metadata={"session_id": "other"},
                tags={"brain", "conversation"},
            )
        for index in range(6):
            self.memory_manager.add(
                f"User: cats work {index}\nHypatia: work {index}",
                metadata={"session_id": "work-1"},
                tags={"brain", "conversation"},
            )

        response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "work-1"})
        )

        self.assertEqual(response.memory_count, 5)
        self.assertIn("User: cats work 0", response.message)
        self.assertIn("User: cats work 4", response.message)
        self.assertNotIn("User: cats work 5", response.message)
        self.assertNotIn("User: cats other 0", response.message)

    def test_same_query_returns_different_results_for_different_sessions(self) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Work answer.",
            metadata={"session_id": "work-1"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Personal answer.",
            metadata={"session_id": "personal"},
            tags={"brain", "conversation"},
        )

        work_response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "work-1"})
        )
        personal_response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "personal"})
        )

        self.assertIn("Work answer.", work_response.message)
        self.assertNotIn("Personal answer.", work_response.message)
        self.assertIn("Personal answer.", personal_response.message)
        self.assertNotIn("Work answer.", personal_response.message)

    def test_custom_session_recall_excludes_default_and_none_session_records(
        self,
    ) -> None:
        self.memory_manager.add(
            "User: cats\nHypatia: Legacy conversation.",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "User: cats\nHypatia: Null session conversation.",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "work-1"})
        )

        self.assertEqual(response.memory_count, 0)
        self.assertNotIn("Legacy conversation.", response.message)
        self.assertNotIn("Null session conversation.", response.message)

    def test_invalid_session_id_prevents_recall_search(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            RecallSearchMustNotRunMemoryManager(),
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": 123})
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "session_id must be a string.")

    def test_unknown_session_override_prevents_recall_search(self) -> None:
        engine = CognitiveEngine(
            self.knowledge_engine,
            RecallSearchMustNotRunMemoryManager(),
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="recall cats", metadata={"session_id": "unknown"})
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Unknown session: unknown")

    def test_conversation_search_precedes_generic_knowledge_search(self) -> None:
        self.memory_manager.add(
            "Bootstrap loading order",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="search conversations bootstrap")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "conversation_search")
        self.assertIn("Bootstrap loading order", response.message)

    def test_conversation_search_preserves_query_case_and_uses_no_memory_limit(
        self,
    ) -> None:
        memory_manager = RecordingConversationSearchMemoryManager(
            [
                MemoryRecord(
                    memory_id="match-1",
                    content="Session Manager transaction contract",
                    metadata={"session_id": "default"},
                    tags=frozenset({"brain", "conversation"}),
                )
            ]
        )
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(message="SEARCH CONVERSATIONS Session Manager")
        )

        self.assertTrue(response.success)
        self.assertEqual(memory_manager.calls, [("Session Manager", None)])

    def test_empty_conversation_search_fails_without_memory_or_knowledge_access(
        self,
    ) -> None:
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),
            RecentConversationsMustNotReadMemoryManager(),
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(BrainRequest(message="search conversations"))

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "conversation_search")
        self.assertEqual(response.message, "Search query must not be empty.")

    def test_conversation_search_filters_sessions_and_tags_before_limiting(
        self,
    ) -> None:
        now = datetime.now(UTC)
        records = [
            MemoryRecord(
                memory_id=f"other-{index}",
                content=f"Other relevance {index}",
                metadata={"session_id": "personal"},
                tags=frozenset({"brain", "conversation"}),
                created_at=now + timedelta(hours=index),
            )
            for index in range(5)
        ]
        records.extend(
            MemoryRecord(
                memory_id=f"work-{index}",
                content=f"Work relevance {index}",
                metadata={"session_id": "work-1"},
                tags=frozenset({"brain", "conversation"}),
                created_at=now + timedelta(hours=10 - index),
            )
            for index in range(6)
        )
        records.extend(
            [
                MemoryRecord(
                    memory_id="search-record",
                    content="Knowledge search relevance",
                    metadata={"session_id": "work-1"},
                    tags=frozenset({"cognition", "knowledge-search", "conversation"}),
                ),
                MemoryRecord(
                    memory_id="plan-record",
                    content="Plan relevance",
                    metadata={"session_id": "work-1"},
                    tags=frozenset({"brain", "plan"}),
                ),
            ]
        )
        memory_manager = RecordingConversationSearchMemoryManager(records)
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),
            memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        response = engine.process(
            BrainRequest(
                message="search conversations relevance",
                metadata={"session_id": "work-1"},
            )
        )

        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. Work relevance 0", response.message)
        self.assertIn("5. Work relevance 4", response.message)
        self.assertNotIn("Work relevance 5", response.message)
        self.assertNotIn("Other relevance", response.message)
        self.assertNotIn("Knowledge search relevance", response.message)
        self.assertNotIn("Plan relevance", response.message)

    def test_conversation_search_treats_only_missing_session_metadata_as_legacy(
        self,
    ) -> None:
        self.memory_manager.add(
            "Legacy conversation match",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null session conversation match",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(
            BrainRequest(message="search conversations conversation")
        )

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Legacy conversation match", response.message)
        self.assertNotIn("Null session conversation match", response.message)

    def test_conversation_search_maps_memory_failure_without_composing(self) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.memory_manager,
                "search",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "conversation_search_results",
                wraps=self.response_composer.conversation_search_results,
            ) as conversation_search_results,
            patch.object(
                self.response_composer,
                "conversation_search_empty",
                wraps=self.response_composer.conversation_search_empty,
            ) as conversation_search_empty,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="search conversations project",
                    request_id="request-123",
                )
            )

        conversation_search_results.assert_not_called()
        conversation_search_empty.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "conversation_search")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "Memory snapshot changed.")
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_conversation_search_uses_active_session_and_request_override(
        self,
    ) -> None:
        self.memory_manager.add(
            "Default conversation match",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Work conversation match",
            metadata={"session_id": "work-1"},
            tags={"brain", "conversation"},
        )
        self.session_manager.set_active("work-1")

        active_response = self.engine.process(
            BrainRequest(message="search conversations match")
        )
        override_response = self.engine.process(
            BrainRequest(
                message="search conversations match",
                metadata={"session_id": "default"},
            )
        )

        self.assertIn("Work conversation match", active_response.message)
        self.assertNotIn("Default conversation match", active_response.message)
        self.assertIn("Default conversation match", override_response.message)
        self.assertNotIn("Work conversation match", override_response.message)
        self.assertEqual(self.session_manager.get_active().session_id, "work-1")

    def test_invalid_conversation_search_session_override_has_no_side_effects(
        self,
    ) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        engine = CognitiveEngine(
            KnowledgeSearchMustNotRun(),
            RecentConversationsMustNotReadMemoryManager(),
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for session_id, expected in (
            (123, "session_id must be a string."),
            ("unknown", "Unknown session: unknown"),
        ):
            with self.subTest(session_id=session_id):
                response = engine.process(
                    BrainRequest(
                        message="search conversations bootstrap",
                        metadata={"session_id": session_id},
                    )
                )

                self.assertFalse(response.success)
                self.assertEqual(response.message, expected)

        self.assertEqual(events, [])
        self.assertEqual(self.session_manager.get_active().session_id, "default")

    def test_conversation_search_does_not_create_new_events_or_memory_records(
        self,
    ) -> None:
        self.memory_manager.add(
            "Stored conversation match",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        memory_count = self.memory_manager.count()

        response = self.engine.process(
            BrainRequest(message="search conversations match")
        )

        self.assertTrue(response.success)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(events, [])

    def test_recent_conversations_uses_a_default_limit_of_five_newest_records(
        self,
    ) -> None:
        for index in range(6):
            self.memory_manager.add(
                f"Conversation {index}",
                metadata={"session_id": "default"},
                tags={"brain", "conversation"},
            )

        response = self.engine.process(BrainRequest(message="recent conversations"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "recent_conversations")
        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. Conversation 5", response.message)
        self.assertIn("5. Conversation 1", response.message)
        self.assertNotIn("Conversation 0", response.message)

    def test_recent_conversations_honours_explicit_one_and_twenty_limits(self) -> None:
        for index in range(6):
            self.memory_manager.add(
                f"Conversation {index}",
                metadata={"session_id": "default"},
                tags={"brain", "conversation"},
            )

        one_response = self.engine.process(
            BrainRequest(message="recent conversations 1")
        )
        twenty_response = self.engine.process(
            BrainRequest(message="recent conversations 20")
        )

        self.assertEqual(one_response.memory_count, 1)
        self.assertIn("1. Conversation 5", one_response.message)
        self.assertEqual(twenty_response.memory_count, 6)
        self.assertIn("6. Conversation 0", twenty_response.message)

    def test_recent_conversations_rejects_invalid_counts(self) -> None:
        expected_messages = {
            "recent conversations abc": "Count must be an integer.",
            "recent conversations 0": "Count must be between 1 and 20.",
            "recent conversations 21": "Count must be between 1 and 20.",
        }

        for message, expected in expected_messages.items():
            with self.subTest(message=message):
                response = self.engine.process(BrainRequest(message=message))

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "recent_conversations")
                self.assertEqual(response.message, expected)
                self.assertEqual(response.memory_count, 0)

    def test_recent_conversations_filters_tags_and_other_sessions_before_limiting(
        self,
    ) -> None:
        for index in range(5):
            self.memory_manager.add(
                f"Other session {index}",
                metadata={"session_id": "personal"},
                tags={"brain", "conversation"},
            )
        for index in range(6):
            self.memory_manager.add(
                f"Work conversation {index}",
                metadata={"session_id": "work-1"},
                tags={"brain", "conversation"},
            )
        self.memory_manager.add(
            "Search record",
            metadata={"session_id": "work-1"},
            tags={"cognition", "knowledge-search", "conversation"},
        )
        self.memory_manager.add(
            "Plan record",
            metadata={"session_id": "work-1"},
            tags={"brain", "plan"},
        )

        response = self.engine.process(
            BrainRequest(
                message="recent conversations",
                metadata={"session_id": "work-1"},
            )
        )

        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. Work conversation 5", response.message)
        self.assertIn("5. Work conversation 1", response.message)
        self.assertNotIn("Work conversation 0", response.message)
        self.assertNotIn("Other session", response.message)
        self.assertNotIn("Search record", response.message)
        self.assertNotIn("Plan record", response.message)

    def test_recent_conversations_treats_only_missing_session_metadata_as_legacy(
        self,
    ) -> None:
        self.memory_manager.add(
            "Legacy conversation",
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Null session conversation",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        response = self.engine.process(BrainRequest(message="recent conversations"))

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Legacy conversation", response.message)
        self.assertNotIn("Null session conversation", response.message)

    def test_recent_conversations_maps_memory_failure_without_composing(self) -> None:
        sessions_before = self.session_manager.snapshot()
        memory_before = self.memory_manager.snapshot()
        events: list[object] = []
        self.event_bus.subscribe("*", events.append)

        with (
            patch.object(
                self.memory_manager,
                "all",
                side_effect=MemoryError("Memory snapshot changed."),
            ),
            patch.object(
                self.response_composer,
                "recent_conversations",
                wraps=self.response_composer.recent_conversations,
            ) as recent_conversations,
            patch.object(
                self.response_composer,
                "recent_conversations_empty",
                wraps=self.response_composer.recent_conversations_empty,
            ) as recent_conversations_empty,
        ):
            response = self.engine.process(
                BrainRequest(
                    message="recent conversations",
                    request_id="request-123",
                )
            )

        recent_conversations.assert_not_called()
        recent_conversations_empty.assert_not_called()
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.intent, "recent_conversations")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "Memory snapshot changed.")
        self.assertEqual(self.session_manager.snapshot(), sessions_before)
        self.assertEqual(self.memory_manager.snapshot(), memory_before)
        self.assertEqual(events, [])

    def test_recent_conversations_uses_active_session_and_request_override(
        self,
    ) -> None:
        self.memory_manager.add(
            "Default conversation",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            "Work conversation",
            metadata={"session_id": "work-1"},
            tags={"brain", "conversation"},
        )
        self.session_manager.set_active("work-1")

        active_response = self.engine.process(
            BrainRequest(message="recent conversations")
        )
        override_response = self.engine.process(
            BrainRequest(
                message="recent conversations",
                metadata={"session_id": "default"},
            )
        )

        self.assertIn("Work conversation", active_response.message)
        self.assertNotIn("Default conversation", active_response.message)
        self.assertIn("Default conversation", override_response.message)
        self.assertNotIn("Work conversation", override_response.message)
        self.assertEqual(self.session_manager.get_active().session_id, "work-1")

    def test_invalid_recent_conversations_session_overrides_have_no_side_effects(
        self,
    ) -> None:
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        engine = CognitiveEngine(
            self.knowledge_engine,
            RecentConversationsMustNotReadMemoryManager(),
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
        )

        for session_id, expected in (
            (123, "session_id must be a string."),
            ("unknown", "Unknown session: unknown"),
        ):
            with self.subTest(session_id=session_id):
                response = engine.process(
                    BrainRequest(
                        message="recent conversations",
                        metadata={"session_id": session_id},
                    )
                )

                self.assertFalse(response.success)
                self.assertEqual(response.message, expected)

        self.assertEqual(events, [])
        self.assertEqual(self.session_manager.get_active().session_id, "default")

    def test_recent_conversations_does_not_create_conversation_or_session_events(
        self,
    ) -> None:
        self.memory_manager.add(
            "Stored conversation",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        memory_count = self.memory_manager.count()

        response = self.engine.process(BrainRequest(message="recent conversations"))

        self.assertTrue(response.success)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(events, [])
