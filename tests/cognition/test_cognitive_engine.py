"""Unit tests for the first CognitiveEngine implementation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from collections.abc import Callable, Mapping
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
from core.CancellationSignal import CancellationSignal
from core.Exceptions import (
    KnowledgeError,
    MemoryError,
    PlannerError,
    ResearchError,
    SessionDeleteEventError,
)
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeContextPrompt import KNOWLEDGE_CONTEXT_SYSTEM_INSTRUCTION
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
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimContradictionCandidate import (
    ResearchClaimContradictionCandidate,
)
from research.ResearchClaimContradictionProposalProvider import (
    ResearchClaimContradictionProposalError,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunMarkdownRenderer import render_research_run_markdown
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceContentRecord import ResearchSourceContentRecord
from research.ResearchSourceEvidenceType import ResearchSourceEvidenceType
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
        self.system_instructions: list[str | None] = []
        self.response = response

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
    ) -> str:
        self.calls.append((prompt, history))
        self.system_instructions.append(system_instruction)
        return self.response


class FailingLLMProvider:
    """Raises the provider boundary's controlled generation error."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[LLMConversationMessage, ...]]] = []
        self.system_instructions: list[str | None] = []

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
    ) -> str:
        self.calls.append((prompt, history))
        self.system_instructions.append(system_instruction)
        raise LLMError("Generation unavailable.")


class RecordingResearchSourceFetcher:
    """Returns one traceable source while recording explicit acquisition calls."""

    def __init__(
        self,
        source: ResearchSource | None = None,
        error: ResearchError | None = None,
        cancellation_signal: CancellationSignal | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.source = source
        self.error = error
        self.cancellation_signal = cancellation_signal

    def fetch(self, url: str) -> ResearchSource:
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        if self.cancellation_signal is not None:
            self.cancellation_signal.cancel()
        assert self.source is not None
        return self.source


class RecordingResearchSourceDiscoveryProvider:
    """Returns bounded metadata while recording explicit discovery calls."""

    provider_name = "test-provider"

    def __init__(
        self,
        candidates: list[ResearchSourceCandidate] | None = None,
        error: ResearchError | None = None,
        cancellation_signal: CancellationSignal | None = None,
    ) -> None:
        self.calls: list[tuple[str, int]] = []
        self.candidates = list(candidates or [])
        self.error = error
        self.cancellation_signal = cancellation_signal

    def discover(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[ResearchSourceCandidate]:
        self.calls.append((query, limit))
        if self.error is not None:
            raise self.error
        if self.cancellation_signal is not None:
            self.cancellation_signal.cancel()
        return list(self.candidates)


class RecordingContradictionProposalProvider:
    """Returns caller-supplied read-only candidates and records exact inputs."""

    provider_name = "test-contradiction-provider"

    def __init__(
        self,
        candidates: list[ResearchClaimContradictionCandidate] | None = None,
        error: ResearchClaimContradictionProposalError | None = None,
        cancellation_signal: CancellationSignal | None = None,
        on_propose: Callable[[], None] | None = None,
    ) -> None:
        self.candidates = list(candidates or [])
        self.error = error
        self.cancellation_signal = cancellation_signal
        self.on_propose = on_propose
        self.calls: list[tuple[str, tuple[ResearchClaimRecord, ...], int]] = []

    def propose(
        self,
        question: str,
        claims: tuple[ResearchClaimRecord, ...],
        *,
        limit: int,
    ) -> list[ResearchClaimContradictionCandidate]:
        self.calls.append((question, claims, limit))
        if self.error is not None:
            raise self.error
        if self.on_propose is not None:
            self.on_propose()
        if self.cancellation_signal is not None:
            self.cancellation_signal.cancel()
        return list(self.candidates)


class ToggleResearchRunStore:
    """Keep snapshots and optionally fail the next persistence operation."""

    def __init__(self, operations: list[str] | None = None) -> None:
        self.runs: list[ResearchRun] = []
        self.fail_saves = False
        self.save_calls = 0
        self.operations = operations

    def load(self) -> list[ResearchRun]:
        return list(self.runs)

    def save(self, runs: list[ResearchRun]) -> None:
        self.save_calls += 1
        if self.operations is not None:
            self.operations.append("run_save")
        if self.fail_saves:
            raise ResearchError("Research run store unavailable.")
        self.runs = list(runs)


class ToggleResearchSourceContentStore:
    """Keep accepted content snapshots and support deterministic save failures."""

    def __init__(
        self,
        records: list[ResearchSourceContentRecord] | None = None,
        operations: list[str] | None = None,
    ) -> None:
        self.records = list(records or [])
        self.fail_loads = False
        self.fail_save_calls: set[int] = set()
        self.save_calls = 0
        self.operations = operations

    def load(self) -> list[ResearchSourceContentRecord]:
        if self.operations is not None:
            self.operations.append("content_load")
        if self.fail_loads:
            raise ResearchError("Research source content store unavailable.")
        return list(self.records)

    def save(self, records: list[ResearchSourceContentRecord]) -> None:
        self.save_calls += 1
        if self.operations is not None:
            self.operations.append("content_save")
        if self.save_calls in self.fail_save_calls:
            raise ResearchError("Research source content store unavailable.")
        self.records = list(records)


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

    def test_substantive_turkish_greeting_reaches_an_injected_llm_provider(
        self,
    ) -> None:
        llm_provider = RecordingLLMProvider("Merhaba! Ben Hypatia.")
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
        message = "Merhaba Hypatia. Tek Türkçe cümleyle kendini tanıt."

        response = engine.process(BrainRequest(message=message))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "message")
        self.assertEqual(response.message, "Merhaba! Ben Hypatia.")
        self.assertEqual(llm_provider.calls, [(message, ())])

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
                "cognition.LearnedMemoryContextService.load_learned_memory_context",
                wraps=load_learned_memory_context,
            ) as load_context,
            patch(
                "cognition.LearnedMemoryContextService.load_bounded_learned_memory_context",
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
                "cognition.LearnedMemoryContextService.load_learned_memory_context",
            ) as load_context,
            patch(
                "cognition.LearnedMemoryContextService.load_bounded_learned_memory_context",
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
                "cognition.LearnedMemoryContextService.load_learned_memory_context",
            ) as load_context,
            patch(
                "cognition.LearnedMemoryContextService.load_bounded_learned_memory_context",
            ) as load_bounded_context,
            patch(
                "cognition.LearnedMemoryContextService.load_current_selected_learned_memory_context",
                return_value=selected_context,
            ) as load_selected_context,
            patch(
                "cognition.LearnedMemoryContextService."
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
                "cognition.LearnedMemoryContextService.load_learned_memory_context",
            ) as load_context,
            patch(
                "cognition.LearnedMemoryContextService.load_bounded_learned_memory_context",
            ) as load_bounded_context,
            patch(
                "cognition.LearnedMemoryContextService.load_current_selected_learned_memory_context",
            ) as load_selected_context,
            patch(
                "cognition.LearnedMemoryContextService."
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
                "cognition.LearnedMemoryContextService.load_learned_memory_context",
            ) as load_context,
            patch(
                "cognition.LearnedMemoryContextService.load_bounded_learned_memory_context",
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
                "cognition.LearnedMemoryContextService.load_learned_memory_context",
            ) as load_context,
            patch(
                "cognition.LearnedMemoryContextService.load_bounded_learned_memory_context",
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

    def test_learning_failure_emits_one_bounded_diagnostic_event(self) -> None:
        llm_provider = RecordingLLMProvider("The conversation succeeded.")
        cause = LLMError("provider unavailable")
        extraction_error = LearnedMemoryCandidateExtractionError(
            "Learned memory candidate extraction failed."
        )
        extraction_error.__cause__ = cause
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=FailingCandidateExtractor(
                extraction_error
            ),
        )
        failures: list[Event] = []
        self.event_bus.subscribe(
            "brain.learned_memory.extraction_failed",
            failures.append,
        )
        message = "  My favorite planet is Saturn.  "

        response = engine.process(
            BrainRequest(message=message, request_id="request-987")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.message, "The conversation succeeded.")
        self.assertEqual(len(failures), 1)
        event = failures[0]
        self.assertEqual(event.source, "brain")
        self.assertEqual(
            event.payload,
            {"request_id": "request-987", "cause": "LLMError"},
        )
        encoded_payload = repr(event.payload)
        self.assertNotIn(message, encoded_payload)
        self.assertNotIn("Saturn", encoded_payload)
        self.assertNotIn("provider unavailable", encoded_payload)

    def test_learning_failure_without_cause_reports_unknown_category(self) -> None:
        llm_provider = RecordingLLMProvider("The conversation succeeded.")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            learned_memory_candidate_extractor=FailingCandidateExtractor(
                LearnedMemoryCandidateExtractionError("failed")
            ),
        )
        failures: list[Event] = []
        self.event_bus.subscribe(
            "brain.learned_memory.extraction_failed",
            failures.append,
        )

        response = engine.process(
            BrainRequest(message="exact message", request_id="request-654")
        )

        self.assertTrue(response.success)
        self.assertEqual(len(failures), 1)
        self.assertEqual(
            failures[0].payload,
            {"request_id": "request-654", "cause": "unknown"},
        )

    def test_successful_extraction_emits_no_failure_event(self) -> None:
        llm_provider = RecordingLLMProvider("I will remember that.")
        batch = LearnedMemoryCandidateBatch(
            source_text="My favorite planet is Saturn.",
            candidates=(
                LearnedMemoryCandidate(
                    memory=LearnedMemory(
                        kind="preference",
                        key="favorite_planet",
                        value="Saturn",
                    ),
                    source_text="My favorite planet is Saturn.",
                ),
            ),
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
            learned_memory_candidate_extractor=RecordingCandidateExtractor(batch),
        )
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = engine.process(BrainRequest(message="My favorite planet is Saturn."))

        self.assertTrue(response.success)
        self.assertNotIn("brain.learned_memory.extraction_failed", events)

    def test_no_op_extraction_emits_no_failure_event(self) -> None:
        llm_provider = RecordingLLMProvider("The conversation succeeded.")
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

        response = engine.process(BrainRequest(message="exact message"))

        self.assertTrue(response.success)
        self.assertEqual(
            events,
            [
                "brain.request.received",
                "brain.intent.detected",
                "memory.record.added",
                "brain.response.ready",
            ],
        )

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

    def test_knowledge_relation_removal_is_previewed_then_applied_without_memory(
        self,
    ) -> None:
        extra_path = Path(self.temporary_directory.name) / "extra.md"
        extra_path.write_text("Extra", encoding="utf-8")
        self.knowledge_engine.load(extra_path)
        source_id, target_id = [
            document.document_id for document in self.knowledge_engine.documents()
        ]
        self.engine.process(
            BrainRequest(
                message=("apply knowledge relation " f"{source_id} -- {target_id}")
            )
        )

        preview = self.engine.process(
            BrainRequest(
                message=(
                    "preview remove knowledge relation " f"{source_id} -- {target_id}"
                )
            )
        )
        removal = self.engine.process(
            BrainRequest(
                message=("remove knowledge relation " f"{source_id} -- {target_id}")
            )
        )
        duplicate = self.engine.process(
            BrainRequest(
                message=("remove knowledge relation " f"{source_id} -- {target_id}")
            )
        )

        self.assertTrue(preview.success)
        self.assertEqual(preview.intent, "knowledge_relation_removal_preview")
        self.assertIn("Changes: ready to remove", preview.message)
        self.assertTrue(removal.success)
        self.assertEqual(removal.intent, "knowledge_relation_remove")
        self.assertIn("Knowledge relation removed:", removal.message)
        self.assertFalse(duplicate.success)
        self.assertIn("Knowledge graph relation is not applied.", duplicate.message)
        self.assertEqual(self.memory_manager.all(), [])

    def test_knowledge_relation_list_is_read_only_and_exposes_active_link(
        self,
    ) -> None:
        extra_path = Path(self.temporary_directory.name) / "extra.md"
        extra_path.write_text("Extra", encoding="utf-8")
        self.knowledge_engine.load(extra_path)
        source_id, target_id = [
            document.document_id for document in self.knowledge_engine.documents()
        ]
        self.engine.process(
            BrainRequest(
                message=("apply knowledge relation " f"{source_id} -- {target_id}")
            )
        )

        response = self.engine.process(BrainRequest(message="list knowledge relations"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_relation_list")
        self.assertEqual(len(response.knowledge_relations), 1)
        self.assertIn("Applied knowledge relations:", response.message)
        self.assertIn("storage: in-memory only", response.message)
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
        self.assertIn("Explicit user question:\nhypatia", prompt)
        self.assertIn("[UNTRUSTED SOURCE 1]", prompt)
        self.assertIn(str(Path(self.temporary_directory.name) / "knowledge.md"), prompt)
        self.assertEqual(history, ())
        self.assertEqual(
            llm_provider.system_instructions,
            [KNOWLEDGE_CONTEXT_SYSTEM_INSTRUCTION],
        )
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

    def test_structured_knowledge_load_indexes_one_source_without_memory_side_effects(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "project notes.md"
            path.write_text("Hypatia\n\nLocal knowledge", encoding="utf-8")
            events: list[str] = []
            self.event_bus.subscribe("*", lambda event: events.append(event.name))
            memory_count = self.memory_manager.count()

            response = self.engine.process(
                BrainRequest(
                    message="Load selected local knowledge source",
                    metadata={
                        "intent": "knowledge_load",
                        "knowledge_path": str(path),
                    },
                )
            )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_load")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(events, [])
        self.assertEqual(len(response.knowledge_documents), 1)
        self.assertEqual(response.knowledge_documents[0].title, "project notes")
        self.assertEqual(response.knowledge_documents[0].chunk_count, 2)
        self.assertIn("Local knowledge source loaded:", response.message)

    def test_structured_knowledge_load_rejects_missing_or_invalid_paths_without_loading(
        self,
    ) -> None:
        documents_before = self.knowledge_engine.documents()
        memory_count = self.memory_manager.count()
        for path in (None, "  ", 123):
            with self.subTest(path=path):
                response = self.engine.process(
                    BrainRequest(
                        message="Load selected local knowledge source",
                        metadata={
                            "intent": "knowledge_load",
                            "knowledge_path": path,
                        },
                    )
                )

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "knowledge_load")
                self.assertEqual(response.memory_count, 0)
                self.assertEqual(response.knowledge_documents, [])
                self.assertEqual(
                    response.message,
                    "A local knowledge source path is required.",
                )

        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        self.assertEqual(self.memory_manager.count(), memory_count)

    def test_research_source_discovery_persists_candidates_without_loading_them(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            discovery_id_factory=lambda: "discovery-123",
        )
        run = manager.create("Compare local models")
        candidate = ResearchSourceCandidate(
            url="https://example.com/comparison",
            title="Model comparison",
            snippet="A possible comparison source.",
        )
        provider = RecordingResearchSourceDiscoveryProvider([candidate])
        source_fetcher = RecordingResearchSourceFetcher(
            source=ResearchSource(
                url=candidate.url,
                title=candidate.title,
                content="Must not be fetched.",
                content_type="text/plain",
                fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
            )
        )
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_source_fetcher=source_fetcher,
            research_run_manager=manager,
            research_source_discovery_provider=provider,
        )
        documents_before = self.knowledge_engine.documents()
        memory_count = self.memory_manager.count()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = engine.process(
            BrainRequest(
                message="Discover candidate research sources",
                metadata={
                    "intent": "research_source_discover",
                    "research_run_id": run.run_id,
                },
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "research_source_discover")
        self.assertEqual(provider.calls, [(run.question, 5)])
        self.assertEqual(source_fetcher.calls, [])
        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        self.assertEqual(events, [])
        updated = response.research_runs[0]
        self.assertEqual(updated.sources, ())
        self.assertEqual(updated.evidence, ())
        self.assertEqual(len(updated.discoveries), 1)
        discovery = updated.discoveries[0]
        self.assertEqual(discovery.discovery_id, "discovery-123")
        self.assertEqual(discovery.provider, "test-provider")
        self.assertEqual(discovery.candidates, (candidate,))
        self.assertIn("candidates only", response.message)
        self.assertEqual(store.runs, [updated])

    def test_discovery_cancellation_after_provider_return_persists_nothing(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(store, id_factory=lambda: "run-123")
        run = manager.create("Question")
        cancellation_signal = CancellationSignal()
        candidate = ResearchSourceCandidate(
            "https://example.com/source",
            "Source",
            "Summary",
        )
        provider = RecordingResearchSourceDiscoveryProvider(
            [candidate],
            cancellation_signal=cancellation_signal,
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
            research_source_discovery_provider=provider,
        )
        save_calls_before = store.save_calls

        response = engine.process(
            BrainRequest(
                message="Discover candidate research sources",
                metadata={
                    "intent": "research_source_discover",
                    "research_run_id": run.run_id,
                },
                cancellation_token=cancellation_signal,
            )
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Research source discovery was cancelled.")
        self.assertEqual(provider.calls, [(run.question, 5)])
        self.assertEqual(manager.get(run.run_id), run)
        self.assertEqual(manager.get(run.run_id).discoveries, ())
        self.assertEqual(manager.get(run.run_id).failures, ())
        self.assertEqual(store.save_calls, save_calls_before)

    def test_pre_cancelled_discovery_never_calls_the_provider(self) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Question")
        provider = RecordingResearchSourceDiscoveryProvider()
        cancellation_signal = CancellationSignal()
        cancellation_signal.cancel()
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
            research_source_discovery_provider=provider,
        )

        response = engine.process(
            BrainRequest(
                message="Discover candidate research sources",
                metadata={
                    "intent": "research_source_discover",
                    "research_run_id": run.run_id,
                },
                cancellation_token=cancellation_signal,
            )
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Research source discovery was cancelled.")
        self.assertEqual(provider.calls, [])
        self.assertEqual(manager.get(run.run_id), run)

    def test_discovery_failure_records_only_a_safe_reason(self) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(store, id_factory=lambda: "run-123")
        run = manager.create("Question")
        secret = "https://user:secret@example.com/private"
        provider = RecordingResearchSourceDiscoveryProvider(
            error=ResearchError(f"Provider rejected {secret}")
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
            research_source_discovery_provider=provider,
        )

        response = engine.process(
            BrainRequest(
                message="Discover candidate research sources",
                metadata={
                    "intent": "research_source_discover",
                    "research_run_id": run.run_id,
                },
            )
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Research source discovery failed.")
        updated = manager.get(run.run_id)
        self.assertEqual(updated.discoveries, ())
        self.assertEqual(len(updated.failures), 1)
        self.assertEqual(updated.failures[0].stage, "source_discovery")
        self.assertEqual(updated.failures[0].provider, provider.provider_name)
        self.assertNotIn(secret, repr(updated))

    def test_discovery_rejects_provider_contract_overflow_as_audited_failure(
        self,
    ) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Question")
        provider = RecordingResearchSourceDiscoveryProvider(
            [
                ResearchSourceCandidate(
                    f"https://example.com/{index}",
                    f"Candidate {index}",
                    "",
                )
                for index in range(6)
            ]
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
            research_source_discovery_provider=provider,
        )

        response = engine.process(
            BrainRequest(
                message="Discover candidate research sources",
                metadata={
                    "intent": "research_source_discover",
                    "research_run_id": run.run_id,
                },
            )
        )

        self.assertFalse(response.success)
        updated = manager.get(run.run_id)
        self.assertEqual(updated.discoveries, ())
        self.assertEqual(updated.failures[0].stage, "source_discovery")

    def test_closed_or_unknown_run_rejects_discovery_before_provider_access(
        self,
    ) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Question")
        manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)
        provider = RecordingResearchSourceDiscoveryProvider()
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
            research_source_discovery_provider=provider,
        )

        for run_id, expected in (
            (run.run_id, "closed"),
            ("missing-run", "not found"),
        ):
            with self.subTest(run_id=run_id):
                response = engine.process(
                    BrainRequest(
                        message="Discover candidate research sources",
                        metadata={
                            "intent": "research_source_discover",
                            "research_run_id": run_id,
                        },
                    )
                )
                self.assertFalse(response.success)
                self.assertIn(expected, response.message)

        self.assertEqual(provider.calls, [])

    def test_discovery_audit_failure_does_not_publish_candidates(self) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            discovery_id_factory=lambda: "discovery-123",
        )
        run = manager.create("Question")
        provider = RecordingResearchSourceDiscoveryProvider(
            [
                ResearchSourceCandidate(
                    "https://example.com/source",
                    "Source",
                    "Summary",
                )
            ]
        )
        store.fail_saves = True
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
            research_source_discovery_provider=provider,
        )

        response = engine.process(
            BrainRequest(
                message="Discover candidate research sources",
                metadata={
                    "intent": "research_source_discover",
                    "research_run_id": run.run_id,
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("audit could not be saved", response.message)
        self.assertEqual(manager.get(run.run_id), run)
        self.assertEqual(manager.get(run.run_id).discoveries, ())

    def test_structured_research_source_load_indexes_provenance_without_side_effects(
        self,
    ) -> None:
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="First finding.\n\nSecond finding.",
            content_type="text/html",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        fetcher = RecordingResearchSourceFetcher(source=source)
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_source_fetcher=fetcher,
        )
        memory_count = self.memory_manager.count()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": "  https://example.com/research  ",
                },
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "research_source_load")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(fetcher.calls, ["https://example.com/research"])
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        self.assertEqual(self.memory_manager.count(), memory_count)
        # The guarantee is that a structured source load has no conversation,
        # memory, or model side effects -- not that it is silent. Observability
        # events for the ingestion itself are the point of that subsystem, so
        # this asserts the absence of brain events rather than of all events.
        self.assertEqual([name for name in events if name.startswith("brain.")], [])
        self.assertTrue(all(name.startswith("source_ingestion.") for name in events))
        self.assertEqual(len(response.knowledge_documents), 1)
        document = response.knowledge_documents[0]
        self.assertEqual(document.source, source.url)
        self.assertEqual(document.chunk_count, 2)
        self.assertEqual(
            self.knowledge_engine.search("second")[0].document_id, document.document_id
        )

    def test_source_load_cancellation_after_fetch_mutates_no_local_state(self) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(store, id_factory=lambda: "run-123")
        run = manager.create("Question")
        content_store = ToggleResearchSourceContentStore()
        cancellation_signal = CancellationSignal()
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="Fetched but not accepted.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        fetcher = RecordingResearchSourceFetcher(
            source=source,
            cancellation_signal=cancellation_signal,
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=fetcher,
            research_run_manager=manager,
            research_source_content_store=content_store,
        )
        documents_before = self.knowledge_engine.documents()
        save_calls_before = store.save_calls

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": source.url,
                    "research_run_id": run.run_id,
                },
                cancellation_token=cancellation_signal,
            )
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Research source loading was cancelled.")
        self.assertEqual(fetcher.calls, [source.url])
        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        self.assertEqual(manager.get(run.run_id), run)
        self.assertEqual(manager.get(run.run_id).sources, ())
        self.assertEqual(manager.get(run.run_id).failures, ())
        self.assertEqual(store.save_calls, save_calls_before)
        self.assertEqual(content_store.save_calls, 0)

    def test_candidate_preview_is_read_only_and_accept_uses_guarded_loader(
        self,
    ) -> None:
        manager = ResearchRunManager(
            id_factory=lambda: "run-123",
            discovery_id_factory=lambda: "discovery-123",
        )
        run = manager.create("Question")
        candidate = ResearchSourceCandidate(
            "https://example.com/paper", "Paper", "Summary"
        )
        manager.add_discovery(run.run_id, run.question, "provider", [candidate])
        source = ResearchSource(
            candidate.url,
            candidate.title,
            "Accepted evidence.",
            "text/plain",
            datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        fetcher = RecordingResearchSourceFetcher(source=source)
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=fetcher,
            research_run_manager=manager,
        )
        metadata = {
            "research_run_id": run.run_id,
            "research_discovery_id": "discovery-123",
            "research_url": candidate.url,
        }
        documents_before = self.knowledge_engine.documents()

        preview = engine.process(
            BrainRequest(
                "Preview candidate",
                metadata={
                    "intent": "research_source_candidate_acceptance_preview",
                    **metadata,
                },
            )
        )

        self.assertTrue(preview.success)
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        decision = preview.research_source_candidate_acceptance_preview
        self.assertIsNotNone(decision)
        assert decision is not None
        self.assertTrue(decision.allowed)

        accepted = engine.process(
            BrainRequest(
                "Accept candidate",
                metadata={"intent": "research_source_candidate_accept", **metadata},
            )
        )

        self.assertTrue(accepted.success)
        self.assertEqual(accepted.intent, "research_source_candidate_accept")
        self.assertEqual(fetcher.calls, [candidate.url])
        self.assertEqual(len(accepted.knowledge_documents), 1)
        self.assertEqual(len(manager.get(run.run_id).sources), 1)

    def test_candidate_accept_rejects_unlisted_url_before_network_access(self) -> None:
        manager = ResearchRunManager(
            id_factory=lambda: "run-123",
            discovery_id_factory=lambda: "discovery-123",
        )
        run = manager.create("Question")
        candidate = ResearchSourceCandidate(
            "https://example.com/paper", "Paper", "Summary"
        )
        manager.add_discovery(run.run_id, run.question, "provider", [candidate])
        fetcher = RecordingResearchSourceFetcher()
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=fetcher,
            research_run_manager=manager,
        )
        documents_before = self.knowledge_engine.documents()

        response = engine.process(
            BrainRequest(
                "Accept candidate",
                metadata={
                    "intent": "research_source_candidate_accept",
                    "research_run_id": run.run_id,
                    "research_discovery_id": "discovery-123",
                    "research_url": "https://example.com/unlisted",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "research_source_candidate_accept")
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(self.knowledge_engine.documents(), documents_before)

    def test_research_source_load_fails_safely_without_partial_indexing(self) -> None:
        fetcher = RecordingResearchSourceFetcher(
            error=ResearchError("Host is not public.")
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=fetcher,
        )
        documents_before = self.knowledge_engine.documents()

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": "https://localhost/private",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "research_source_load")
        self.assertIn("Host is not public.", response.message)
        self.assertEqual(self.knowledge_engine.documents(), documents_before)

    def test_research_run_create_and_list_are_persisted_without_side_effects(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(store, id_factory=lambda: "run-123")
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_run_manager=manager,
        )
        memory_count = self.memory_manager.count()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        created = engine.process(
            BrainRequest(
                message="Create internet research run",
                metadata={
                    "intent": "research_run_create",
                    "research_question": "  Compare local models  ",
                },
            )
        )
        listed = engine.process(
            BrainRequest(
                message="List internet research runs",
                metadata={"intent": "research_run_list"},
            )
        )

        self.assertTrue(created.success)
        self.assertEqual(created.intent, "research_run_create")
        self.assertEqual(created.research_runs[0].run_id, "run-123")
        self.assertEqual(created.research_runs[0].question, "Compare local models")
        self.assertEqual(listed.research_runs, created.research_runs)
        self.assertEqual(store.runs, created.research_runs)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        # Creating a run consults failure memory for advice, which is a read and
        # says so. Naming the one permitted event is a stronger claim than an
        # empty list: a derive, a store or a run mutation would still fail here.
        self.assertEqual(events, ["failure_memory.lessons_recalled"])
        self.assertEqual(created.failure_lessons, ())

    def test_terminal_research_markdown_preview_is_read_only_and_local(self) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(store, id_factory=lambda: "run-123")
        run = manager.create("Export local evidence")
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_run_manager=manager,
        )
        request = BrainRequest(
            message="Preview terminal research run as Markdown",
            metadata={
                "intent": "research_run_markdown_export_preview",
                "research_run_id": run.run_id,
            },
        )

        collecting = engine.process(request)
        terminal = manager.transition_status(
            run.run_id,
            ResearchRunStatus.CANCELLED,
        )
        persisted_save_count = store.save_calls
        memory_count = self.memory_manager.count()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        previewed = engine.process(request)

        self.assertFalse(collecting.success)
        self.assertEqual(collecting.intent, "research_run_markdown_export_preview")
        self.assertTrue(previewed.success)
        preview = previewed.research_run_markdown_export_preview
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual(preview.run_id, terminal.run_id)
        self.assertIn("# Hypatia Research Export", preview.markdown_preview)
        self.assertIn("no file was written", previewed.message)
        self.assertEqual(manager.get(run.run_id), terminal)
        self.assertEqual(store.save_calls, persisted_save_count)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        self.assertEqual(events, [])

    def test_research_markdown_save_revalidates_preview_and_creates_only_new_file(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(store, id_factory=lambda: "run-123")
        run = manager.create("Export local evidence")
        terminal = manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)
        preview = manager.preview_markdown_export(run.run_id)
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_run_manager=manager,
        )
        destination = Path(self.temporary_directory.name) / "research-export.md"
        request = BrainRequest(
            message="Save previewed research run as Markdown",
            metadata={
                "intent": "research_run_markdown_export_save",
                "research_run_id": run.run_id,
                "research_export_snapshot_updated_at": (
                    preview.snapshot_updated_at.isoformat()
                ),
                "research_export_content_sha256": preview.content_sha256,
                "research_export_destination_path": str(destination),
            },
        )
        persisted_save_count = store.save_calls
        memory_count = self.memory_manager.count()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        saved = engine.process(request)

        self.assertTrue(saved.success)
        self.assertEqual(saved.intent, "research_run_markdown_export_save")
        result = saved.research_run_markdown_export_result
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.destination_path, str(destination))
        self.assertEqual(result.content_sha256, preview.content_sha256)
        self.assertEqual(
            destination.read_text(encoding="utf-8"),
            render_research_run_markdown(terminal),
        )
        self.assertIn("no existing file was replaced", saved.message)
        self.assertEqual(manager.get(run.run_id), terminal)
        self.assertEqual(store.save_calls, persisted_save_count)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        self.assertEqual(events, [])

    def test_research_markdown_save_rejects_stale_or_existing_destination_safely(
        self,
    ) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Protect export")
        manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)
        preview = manager.preview_markdown_export(run.run_id)
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )
        destination = Path(self.temporary_directory.name) / "existing-export.md"
        destination.write_text("keep this", encoding="utf-8")
        metadata = {
            "intent": "research_run_markdown_export_save",
            "research_run_id": run.run_id,
            "research_export_snapshot_updated_at": (
                preview.snapshot_updated_at.isoformat()
            ),
            "research_export_content_sha256": preview.content_sha256,
            "research_export_destination_path": str(destination),
        }

        existing = engine.process(BrainRequest(message="Save", metadata=metadata))
        stale = engine.process(
            BrainRequest(
                message="Save",
                metadata={**metadata, "research_export_content_sha256": "0" * 64},
            )
        )

        self.assertFalse(existing.success)
        self.assertFalse(stale.success)
        self.assertEqual(existing.intent, "research_run_markdown_export_save")
        self.assertEqual(stale.intent, "research_run_markdown_export_save")
        self.assertEqual(destination.read_text(encoding="utf-8"), "keep this")
        self.assertNotIn(str(destination), existing.message)

    def test_research_markdown_save_rejects_invalid_metadata_before_file_access(
        self,
    ) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )
        destination = Path(self.temporary_directory.name) / "must-not-exist.md"
        base = {
            "intent": "research_run_markdown_export_save",
            "research_run_id": "run-123",
            "research_export_snapshot_updated_at": "2026-08-21T00:00:00+00:00",
            "research_export_content_sha256": "a" * 64,
            "research_export_destination_path": str(destination),
        }
        invalid_values = (
            {"research_run_id": ""},
            {"research_export_snapshot_updated_at": "not-a-time"},
            {"research_export_snapshot_updated_at": "2026-08-21T00:00:00"},
            {"research_export_content_sha256": ""},
            {"research_export_destination_path": ""},
        )

        for replacement in invalid_values:
            with self.subTest(replacement=replacement):
                response = engine.process(
                    BrainRequest(message="Save", metadata={**base, **replacement})
                )
                self.assertFalse(response.success)
                self.assertEqual(
                    response.intent,
                    "research_run_markdown_export_save",
                )
        self.assertFalse(destination.exists())

    def test_research_markdown_verification_reports_exact_match_and_tampering(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(store, id_factory=lambda: "run-123")
        run = manager.create("Verify local export")
        terminal = manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)
        source = Path(self.temporary_directory.name) / "research-export.md"
        expected_markdown = render_research_run_markdown(terminal)
        source.write_text(expected_markdown, encoding="utf-8", newline="\n")
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_run_manager=manager,
        )
        request = BrainRequest(
            message="Verify existing research Markdown export",
            metadata={
                "intent": "research_run_markdown_export_verify",
                "research_run_id": run.run_id,
                "research_export_source_path": str(source),
            },
        )
        persisted_save_count = store.save_calls
        memory_count = self.memory_manager.count()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        matching = engine.process(request)
        source.write_text("# tampered\n", encoding="utf-8", newline="\n")
        mismatching = engine.process(request)

        self.assertTrue(matching.success)
        self.assertTrue(mismatching.success)
        self.assertEqual(matching.intent, "research_run_markdown_export_verify")
        exact = matching.research_run_markdown_export_verification
        changed = mismatching.research_run_markdown_export_verification
        self.assertIsNotNone(exact)
        self.assertIsNotNone(changed)
        assert exact is not None
        assert changed is not None
        self.assertTrue(exact.matches)
        self.assertFalse(changed.matches)
        self.assertIn("Result: MATCH", matching.message)
        self.assertIn("Result: DOES NOT MATCH", mismatching.message)
        self.assertIn("no data was imported or changed", matching.message)
        self.assertEqual(source.read_text(encoding="utf-8"), "# tampered\n")
        self.assertEqual(manager.get(run.run_id), terminal)
        self.assertEqual(store.save_calls, persisted_save_count)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        self.assertEqual(events, [])

    def test_research_markdown_verification_rejects_invalid_request_safely(
        self,
    ) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Reject unsafe verification")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )
        missing_source = Path(self.temporary_directory.name) / "secret-export.md"
        base = {
            "intent": "research_run_markdown_export_verify",
            "research_run_id": run.run_id,
            "research_export_source_path": str(missing_source),
        }

        collecting = engine.process(BrainRequest(message="Verify", metadata=base))
        manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)
        missing = engine.process(BrainRequest(message="Verify", metadata=base))
        empty_run = engine.process(
            BrainRequest(
                message="Verify",
                metadata={**base, "research_run_id": ""},
            )
        )
        empty_path = engine.process(
            BrainRequest(
                message="Verify",
                metadata={**base, "research_export_source_path": ""},
            )
        )

        for verification_response in (collecting, missing, empty_run, empty_path):
            self.assertFalse(verification_response.success)
            self.assertEqual(
                verification_response.intent,
                "research_run_markdown_export_verify",
            )
            self.assertIsNone(
                verification_response.research_run_markdown_export_verification
            )
        self.assertNotIn(str(missing_source), missing.message)
        self.assertFalse(missing_source.exists())

    def test_research_source_is_attached_to_the_selected_persisted_run(self) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(store, id_factory=lambda: "run-123")
        manager.create("Compare local models")
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="First finding.",
            content_type="text/html",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=RecordingResearchSourceFetcher(source=source),
            research_run_manager=manager,
        )

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": source.url,
                    "research_run_id": "run-123",
                },
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.research_runs, manager.list())
        self.assertEqual(len(response.research_runs[0].sources), 1)
        self.assertEqual(
            response.research_runs[0].sources[0].document_id,
            response.knowledge_documents[0].document_id,
        )
        self.assertNotIn(source.content, repr(store.runs))

    def test_research_source_acceptance_persists_content_before_provenance(
        self,
    ) -> None:
        operations: list[str] = []
        run_store = ToggleResearchRunStore(operations)
        manager = ResearchRunManager(run_store, id_factory=lambda: "run-123")
        manager.create("Compare local models")
        operations.clear()
        content_store = ToggleResearchSourceContentStore(operations=operations)
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="Exact accepted finding.\n\nSecond paragraph.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=RecordingResearchSourceFetcher(source=source),
            research_run_manager=manager,
            research_source_content_store=content_store,
        )

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": source.url,
                    "research_run_id": "run-123",
                },
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(
            operations,
            ["content_load", "content_save", "run_save"],
        )
        self.assertEqual(content_store.save_calls, 1)
        self.assertEqual(len(content_store.records), 1)
        content_record = content_store.records[0]
        self.assertEqual(content_record.content, source.content)
        self.assertEqual(
            content_record.document_id,
            response.knowledge_documents[0].document_id,
        )
        self.assertEqual(
            manager.get("run-123").sources[0].document_id,
            content_record.document_id,
        )
        self.assertNotIn(source.content, repr(run_store.runs))

    def test_failed_content_save_rolls_back_new_knowledge_without_provenance(
        self,
    ) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        manager.create("Compare local models")
        content_store = ToggleResearchSourceContentStore()
        content_store.fail_save_calls.add(1)
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="Temporary accepted finding.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=RecordingResearchSourceFetcher(source=source),
            research_run_manager=manager,
            research_source_content_store=content_store,
        )
        documents_before = self.knowledge_engine.documents()

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": source.url,
                    "research_run_id": "run-123",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("knowledge was rolled back", response.message)
        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        self.assertEqual(content_store.records, [])
        self.assertEqual(manager.get("run-123").sources, ())

    def test_failed_source_audit_restores_content_and_knowledge_snapshots(
        self,
    ) -> None:
        run_store = ToggleResearchRunStore()
        manager = ResearchRunManager(run_store, id_factory=lambda: "run-123")
        manager.create("Compare local models")
        run_store.fail_saves = True
        prior_source = ResearchSource(
            url="https://example.com/prior",
            title="Prior source",
            content="Prior accepted finding.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
        )
        prior_record = ResearchSourceContentRecord.from_source(
            prior_source,
            "prior-document",
            datetime(2026, 8, 20, 10, 1, tzinfo=UTC),
        )
        content_store = ToggleResearchSourceContentStore([prior_record])
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="Temporary accepted finding.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=RecordingResearchSourceFetcher(source=source),
            research_run_manager=manager,
            research_source_content_store=content_store,
        )
        documents_before = self.knowledge_engine.documents()

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": source.url,
                    "research_run_id": "run-123",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("content and knowledge were rolled back", response.message)
        self.assertEqual(content_store.save_calls, 2)
        self.assertEqual(content_store.records, [prior_record])
        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        self.assertEqual(manager.get("run-123").sources, ())

    def test_content_rollback_failure_still_removes_new_knowledge_document(
        self,
    ) -> None:
        run_store = ToggleResearchRunStore()
        manager = ResearchRunManager(run_store, id_factory=lambda: "run-123")
        manager.create("Compare local models")
        run_store.fail_saves = True
        content_store = ToggleResearchSourceContentStore()
        content_store.fail_save_calls.add(2)
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="Temporary accepted finding.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=RecordingResearchSourceFetcher(source=source),
            research_run_manager=manager,
            research_source_content_store=content_store,
        )
        documents_before = self.knowledge_engine.documents()

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": source.url,
                    "research_run_id": "run-123",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("content rollback failed", response.message)
        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        self.assertEqual(len(content_store.records), 1)
        self.assertEqual(manager.get("run-123").sources, ())

    def test_research_source_failure_records_only_a_safe_audit_reason(self) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(store, id_factory=lambda: "run-123")
        manager.create("Compare local models")
        rejected_url = "https://secret.example/private?token=value"
        fetcher = RecordingResearchSourceFetcher(
            error=ResearchError(f"Could not fetch {rejected_url}")
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=fetcher,
            research_run_manager=manager,
        )

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": rejected_url,
                    "research_run_id": "run-123",
                },
            )
        )

        self.assertFalse(response.success)
        failure = manager.get("run-123").failures[0]
        self.assertEqual(failure.reason, "Research source acquisition failed.")
        self.assertNotIn(rejected_url, repr(store.runs))

    def test_failed_source_audit_rolls_back_the_new_knowledge_document(self) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(store, id_factory=lambda: "run-123")
        manager.create("Compare local models")
        store.fail_saves = True
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="Temporary finding.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=RecordingResearchSourceFetcher(source=source),
            research_run_manager=manager,
        )
        documents_before = self.knowledge_engine.documents()

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": source.url,
                    "research_run_id": "run-123",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("rolled back", response.message)
        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        self.assertEqual(manager.get("run-123").sources, ())

    def test_research_source_rejects_unknown_run_before_network_access(self) -> None:
        documents_before = self.knowledge_engine.documents()
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        fetcher = RecordingResearchSourceFetcher(
            source=ResearchSource(
                url="https://example.com/research",
                title="Example",
                content="Finding.",
                content_type="text/plain",
                fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
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
            research_source_fetcher=fetcher,
            research_run_manager=manager,
        )

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": "https://example.com/research",
                    "research_run_id": "missing-run",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Research run was not found.")
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(self.knowledge_engine.documents(), documents_before)

    def test_research_evidence_records_an_attached_chunk_without_side_effects(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=lambda: "evidence-123",
        )
        run = manager.create("Compare local models")
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="First finding.\n\nSecond finding.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        document = self.knowledge_engine.add_document(source.to_document())
        manager.add_source(run.run_id, source, document.document_id)
        chunk = self.knowledge_engine.search("second")[0]
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_run_manager=manager,
        )
        memory_count = self.memory_manager.count()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = engine.process(
            BrainRequest(
                message="Record selected research evidence",
                metadata={
                    "intent": "research_evidence_record",
                    "research_run_id": run.run_id,
                    "research_chunk_id": chunk.chunk_id,
                    "research_evidence_note": "  Supports the comparison.  ",
                },
            )
        )
        listed = engine.process(
            BrainRequest(
                message="List selected research evidence",
                metadata={
                    "intent": "research_evidence_list",
                    "research_run_id": run.run_id,
                },
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "research_evidence_record")
        self.assertEqual(response.memory_count, 0)
        evidence = response.research_runs[0].evidence[0]
        self.assertEqual(evidence.evidence_id, "evidence-123")
        self.assertEqual(evidence.chunk_id, chunk.chunk_id)
        self.assertEqual(evidence.source_document_id, document.document_id)
        self.assertEqual(evidence.note, "Supports the comparison.")
        self.assertTrue(listed.success)
        self.assertEqual(listed.intent, "research_evidence_list")
        self.assertEqual(listed.research_runs, response.research_runs)
        self.assertIn("Second finding.", listed.message)
        self.assertIn("paragraph: 2", listed.message)
        self.assertEqual(store.runs, response.research_runs)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        self.assertEqual(events, [])

    def test_research_evidence_rejects_missing_or_unattached_chunks_without_mutation(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(store, id_factory=lambda: "run-123")
        run = manager.create("Compare local models")
        other_document = self.knowledge_engine.add_document(
            ResearchSource(
                url="https://example.org/other",
                title="Other source",
                content="Other evidence.",
                content_type="text/plain",
                fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
            ).to_document()
        )
        other_chunk = self.knowledge_engine.search("other")[0]
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )
        run_before = manager.get(run.run_id)
        documents_before = self.knowledge_engine.documents()

        for chunk_id, expected in (
            ("missing-chunk", "chunk was not found"),
            (other_chunk.chunk_id, "could not be saved"),
        ):
            with self.subTest(chunk_id=chunk_id):
                response = engine.process(
                    BrainRequest(
                        message="Record selected research evidence",
                        metadata={
                            "intent": "research_evidence_record",
                            "research_run_id": run.run_id,
                            "research_chunk_id": chunk_id,
                            "research_evidence_note": "Relevant.",
                        },
                    )
                )

                self.assertFalse(response.success)
                self.assertIn(expected, response.message)

        self.assertEqual(other_chunk.document_id, other_document.document_id)
        self.assertEqual(manager.get(run.run_id), run_before)
        self.assertEqual(self.knowledge_engine.documents(), documents_before)

    def test_source_assessment_preview_is_persisted_evidence_only(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=lambda: "evidence-123",
        )
        run = manager.create("Compare local models")
        source = ResearchSource(
            "https://example.com/research",
            "Example research",
            "Evidence paragraph.",
            "text/plain",
            datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        document = self.knowledge_engine.add_document(source.to_document())
        manager.add_source(run.run_id, source, document.document_id)
        evidence = manager.add_evidence(
            run.run_id,
            self.knowledge_engine.search("evidence")[0],
            "Supports manual assessment.",
        ).evidence[-1]
        fetcher = RecordingResearchSourceFetcher()
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_source_fetcher=fetcher,
            research_run_manager=manager,
        )
        documents_before = self.knowledge_engine.documents()
        memory_count = self.memory_manager.count()
        saves_before = store.save_calls
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = engine.process(
            BrainRequest(
                "Preview accepted research source assessment",
                metadata={
                    "intent": "research_source_assessment_preview",
                    "research_run_id": run.run_id,
                    "research_source_document_id": document.document_id,
                },
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "research_source_assessment_preview")
        preview = response.research_source_assessment_preview
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual(preview.source.document_id, document.document_id)
        self.assertEqual(preview.evidence, (evidence,))
        self.assertTrue(preview.has_recorded_evidence)
        self.assertIn("information trust is user-authored", response.message)
        self.assertIn("Instruction authority: none", response.message)
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        self.assertEqual(events, [])
        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(store.save_calls, saves_before)

    def test_source_comparison_preview_is_ordered_current_and_side_effect_free(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        assessment_ids = iter(("assessment-original", "assessment-current"))
        evidence_ids = iter(("evidence-1", "evidence-2"))
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=evidence_ids.__next__,
            assessment_id_factory=assessment_ids.__next__,
        )
        run = manager.create("Compare local models")
        documents = []
        for number in (1, 2):
            source = ResearchSource(
                f"https://example.com/{number}",
                f"Source {number}",
                f"Unique evidence {number}.",
                "text/plain",
                datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
            )
            document = self.knowledge_engine.add_document(source.to_document())
            documents.append(document)
            manager.add_source(run.run_id, source, document.document_id)
            manager.add_evidence(
                run.run_id,
                next(
                    chunk
                    for chunk in self.knowledge_engine.search("unique evidence")
                    if chunk.document_id == document.document_id
                ),
                f"Selected note {number}.",
            )
        first_evidence = manager.get(run.run_id).evidence[0]
        original = manager.record_source_assessment(
            run.run_id,
            documents[0].document_id,
            [first_evidence.evidence_id],
            "Original assessment.",
        ).assessments[-1]
        correction = manager.record_source_assessment(
            run.run_id,
            documents[0].document_id,
            [first_evidence.evidence_id],
            "Current assessment.",
            original.assessment_id,
        ).assessments[-1]
        fetcher = RecordingResearchSourceFetcher()
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_source_fetcher=fetcher,
            research_run_manager=manager,
        )
        documents_before = self.knowledge_engine.documents()
        memory_count = self.memory_manager.count()
        saves_before = store.save_calls
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        response = engine.process(
            BrainRequest(
                "Compare selected sources",
                metadata={
                    "intent": "research_source_comparison_preview",
                    "research_run_id": run.run_id,
                    "research_source_document_ids": [
                        documents[1].document_id,
                        documents[0].document_id,
                    ],
                },
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "research_source_comparison_preview")
        preview = response.research_source_comparison_preview
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual(
            tuple(item.source.document_id for item in preview.sources),
            (documents[1].document_id, documents[0].document_id),
        )
        self.assertEqual(preview.sources[1].current_assessments, (correction,))
        self.assertNotIn("Original assessment.", response.message)
        self.assertIn("Selected evidence: showing 1 of 1", response.message)
        self.assertIn("Current assessments: showing 1 of 1", response.message)
        self.assertIn("no verdict, trust score", response.message)
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        self.assertEqual(events, [])
        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(store.save_calls, saves_before)

    def test_source_comparison_rejects_invalid_selection_without_side_effects(
        self,
    ) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Question")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )
        for document_ids in ([], ["one"], ["one", "one"], ["one", "two"]):
            with self.subTest(document_ids=document_ids):
                response = engine.process(
                    BrainRequest(
                        "Compare selected sources",
                        metadata={
                            "intent": "research_source_comparison_preview",
                            "research_run_id": run.run_id,
                            "research_source_document_ids": document_ids,
                        },
                    )
                )
                self.assertFalse(response.success)
                self.assertEqual(
                    response.intent,
                    "research_source_comparison_preview",
                )

        self.assertEqual(manager.get(run.run_id), run)

    def test_authored_comparison_note_previews_then_commits_without_providers(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        evidence_ids = iter(("evidence-1", "evidence-2"))
        assessment_ids = iter(("assessment-1", "assessment-2"))
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=evidence_ids.__next__,
            assessment_id_factory=assessment_ids.__next__,
            comparison_note_id_factory=lambda: "comparison-note-1",
        )
        run = manager.create("Compare sources")
        documents = []
        for number in (1, 2):
            source = ResearchSource(
                f"https://example.com/{number}",
                f"Source {number}",
                f"Unique comparison evidence {number}.",
                "text/plain",
                datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
            )
            document = self.knowledge_engine.add_document(source.to_document())
            documents.append(document)
            manager.add_source(run.run_id, source, document.document_id)
            chunk = next(
                item
                for item in self.knowledge_engine.search("unique comparison evidence")
                if item.document_id == document.document_id
            )
            manager.add_evidence(run.run_id, chunk, f"Note {number}.")
        evidence = manager.get(run.run_id).evidence
        for number, record in enumerate(evidence):
            manager.record_source_assessment(
                run.run_id,
                documents[number].document_id,
                [record.evidence_id],
                f"Assessment {number + 1}.",
            )
        assessments = manager.get(run.run_id).assessments
        fetcher = RecordingResearchSourceFetcher()
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_source_fetcher=fetcher,
            research_run_manager=manager,
        )
        metadata = {
            "research_run_id": run.run_id,
            "research_source_document_ids": [
                documents[1].document_id,
                documents[0].document_id,
            ],
            "research_comparison_evidence_ids": [
                evidence[1].evidence_id,
                evidence[0].evidence_id,
            ],
            "research_comparison_assessment_ids": [
                assessments[1].assessment_id,
                assessments[0].assessment_id,
            ],
            "research_comparison_note_text": "My comparison note.",
        }
        documents_before = self.knowledge_engine.documents()
        memory_count = self.memory_manager.count()
        saves_before = store.save_calls
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        preview_response = engine.process(
            BrainRequest(
                "Preview comparison note",
                metadata={
                    "intent": "research_source_comparison_note_write_preview",
                    **metadata,
                },
            )
        )

        self.assertTrue(preview_response.success)
        preview = preview_response.research_source_comparison_note_write_preview
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertTrue(preview.allowed)
        self.assertEqual(preview.text, "My comparison note.")
        self.assertIn("no verdict, score", preview_response.message)
        self.assertEqual(store.save_calls, saves_before)

        recorded = engine.process(
            BrainRequest(
                "Record comparison note",
                metadata={
                    "intent": "research_source_comparison_note_record",
                    **metadata,
                },
            )
        )

        self.assertTrue(recorded.success)
        self.assertEqual(
            recorded.intent,
            "research_source_comparison_note_record",
        )
        note = recorded.research_runs[0].comparison_notes[-1]
        self.assertEqual(note.note_id, "comparison-note-1")
        self.assertEqual(
            note.source_document_ids,
            (documents[1].document_id, documents[0].document_id),
        )
        self.assertEqual(store.save_calls, saves_before + 1)
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        self.assertEqual(events, [])
        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        self.assertEqual(self.memory_manager.count(), memory_count)

    def test_authored_comparison_note_invalid_input_fails_without_mutation(
        self,
    ) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Question")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )
        metadata = {
            "research_run_id": run.run_id,
            "research_source_document_ids": ["document-1", "document-2"],
            "research_comparison_evidence_ids": [],
            "research_comparison_assessment_ids": ["assessment-1"],
            "research_comparison_note_text": "Note.",
        }

        for intent in (
            "research_source_comparison_note_write_preview",
            "research_source_comparison_note_record",
        ):
            response = engine.process(
                BrainRequest("Comparison note", metadata={"intent": intent, **metadata})
            )
            self.assertFalse(response.success)
            self.assertEqual(response.intent, intent)

        self.assertEqual(manager.get(run.run_id), run)

    def test_source_assessment_rejects_unknown_or_cross_run_source(self) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Question")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )

        for metadata in (
            {
                "intent": "research_source_assessment_preview",
                "research_source_document_id": "document-1",
            },
            {
                "intent": "research_source_assessment_preview",
                "research_run_id": run.run_id,
            },
            {
                "intent": "research_source_assessment_preview",
                "research_run_id": run.run_id,
                "research_source_document_id": "document-1",
            },
        ):
            with self.subTest(metadata=metadata):
                response = engine.process(
                    BrainRequest("Preview source", metadata=metadata)
                )
                self.assertFalse(response.success)
                self.assertEqual(
                    response.intent,
                    "research_source_assessment_preview",
                )

        self.assertEqual(manager.get(run.run_id), run)

    def test_evidence_linked_claim_previews_then_commits_without_providers(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        claim_ids = iter(("claim-123", "claim-124"))
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=lambda: "evidence-123",
            claim_id_factory=claim_ids.__next__,
            claim_contradiction_id_factory=lambda: "contradiction-123",
        )
        run = manager.create("Evaluate a claim")
        source = ResearchSource(
            "https://example.com/research",
            "Example research",
            "Evidence paragraph.",
            "text/plain",
            datetime(2026, 8, 21, 20, 0, tzinfo=UTC),
        )
        document = self.knowledge_engine.add_document(source.to_document())
        manager.add_source(run.run_id, source, document.document_id)
        evidence = manager.add_evidence(
            run.run_id,
            self.knowledge_engine.search("evidence")[0],
            "Supports authored claim review.",
        ).evidence[-1]
        llm_provider = RecordingLLMProvider("must not run")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            research_run_manager=manager,
        )
        saves_before = store.save_calls

        history_response = engine.process(
            BrainRequest(
                "View claims",
                metadata={
                    "intent": "research_claim_preview",
                    "research_run_id": run.run_id,
                },
            )
        )
        metadata = {
            "research_run_id": run.run_id,
            "research_claim_evidence_ids": [evidence.evidence_id],
            "research_claim_text": "The evidence likely supports the claim.",
            "research_claim_epistemic_state": "likely",
            "research_claim_confidence": "medium",
        }
        preview_response = engine.process(
            BrainRequest(
                "Preview claim",
                metadata={"intent": "research_claim_write_preview", **metadata},
            )
        )

        self.assertTrue(history_response.success)
        history = history_response.research_claim_preview
        self.assertIsNotNone(history)
        assert history is not None
        self.assertEqual(history.claims, ())
        self.assertTrue(preview_response.success)
        preview = preview_response.research_claim_write_preview
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual(preview.epistemic_state, ResearchEpistemicState.LIKELY)
        self.assertEqual(preview.confidence, ResearchClaimConfidence.MEDIUM)
        self.assertEqual(store.save_calls, saves_before)

        recorded = engine.process(
            BrainRequest(
                "Record claim",
                metadata={"intent": "research_claim_record", **metadata},
            )
        )

        self.assertTrue(recorded.success)
        claim = recorded.research_runs[0].claims[-1]
        self.assertEqual(claim.claim_id, "claim-123")
        self.assertEqual(claim.source_document_ids, (document.document_id,))
        self.assertEqual(claim.evidence_ids, (evidence.evidence_id,))
        self.assertIn("Epistemic state: likely", recorded.message)
        self.assertEqual(store.save_calls, saves_before + 1)

        correction_metadata = {
            **metadata,
            "research_claim_text": "The evidence contradicts the original claim.",
            "research_claim_epistemic_state": "contradicted",
            "research_claim_confidence": "high",
            "research_claim_supersedes_id": claim.claim_id,
        }
        corrected = engine.process(
            BrainRequest(
                "Correct claim",
                metadata={"intent": "research_claim_record", **correction_metadata},
            )
        )

        self.assertTrue(corrected.success)
        correction = corrected.research_runs[0].claims[-1]
        self.assertEqual(correction.claim_id, "claim-124")
        self.assertEqual(correction.supersedes_claim_id, claim.claim_id)
        self.assertEqual(
            correction.epistemic_state,
            ResearchEpistemicState.CONTRADICTED,
        )
        contradiction_history = engine.process(
            BrainRequest(
                "View contradictions",
                metadata={
                    "intent": "research_claim_contradiction_preview",
                    "research_run_id": run.run_id,
                },
            )
        )
        contradiction_metadata = {
            "research_run_id": run.run_id,
            "research_claim_contradiction_claim_ids": [
                claim.claim_id,
                correction.claim_id,
            ],
            "research_claim_contradiction_note": (
                "The corrected claim conflicts with the original conclusion."
            ),
        }
        saves_before_contradiction = store.save_calls
        contradiction_preview = engine.process(
            BrainRequest(
                "Preview contradiction",
                metadata={
                    "intent": "research_claim_contradiction_write_preview",
                    **contradiction_metadata,
                },
            )
        )

        self.assertTrue(contradiction_history.success)
        contradiction_history_value = (
            contradiction_history.research_claim_contradiction_preview
        )
        self.assertIsNotNone(contradiction_history_value)
        assert contradiction_history_value is not None
        self.assertEqual(contradiction_history_value.contradictions, ())
        self.assertTrue(contradiction_preview.success)
        contradiction_decision = (
            contradiction_preview.research_claim_contradiction_write_preview
        )
        self.assertIsNotNone(contradiction_decision)
        assert contradiction_decision is not None
        self.assertEqual(contradiction_decision.claims, (claim, correction))
        self.assertEqual(store.save_calls, saves_before_contradiction)

        contradiction_recorded = engine.process(
            BrainRequest(
                "Record contradiction",
                metadata={
                    "intent": "research_claim_contradiction_record",
                    **contradiction_metadata,
                },
            )
        )

        self.assertTrue(contradiction_recorded.success)
        contradiction = contradiction_recorded.research_runs[0].claim_contradictions[-1]
        self.assertEqual(contradiction.contradiction_id, "contradiction-123")
        self.assertEqual(
            contradiction.claim_ids,
            (claim.claim_id, correction.claim_id),
        )
        self.assertEqual(contradiction.evidence_ids, (evidence.evidence_id,))
        self.assertEqual(store.save_calls, saves_before_contradiction + 1)
        duplicate_preview = engine.process(
            BrainRequest(
                "Duplicate contradiction",
                metadata={
                    "intent": "research_claim_contradiction_write_preview",
                    **contradiction_metadata,
                    "research_claim_contradiction_claim_ids": [
                        correction.claim_id,
                        claim.claim_id,
                    ],
                },
            )
        )
        self.assertFalse(duplicate_preview.success)
        self.assertEqual(llm_provider.calls, [])

        invalid = engine.process(
            BrainRequest(
                "Invalid claim",
                metadata={
                    **metadata,
                    "intent": "research_claim_record",
                    "research_claim_epistemic_state": "certain",
                },
            )
        )
        self.assertFalse(invalid.success)
        self.assertEqual(len(manager.get(run.run_id).claims), 2)
        invalid_contradiction = engine.process(
            BrainRequest(
                "Invalid contradiction",
                metadata={
                    "intent": "research_claim_contradiction_record",
                    "research_run_id": run.run_id,
                    "research_claim_contradiction_claim_ids": [claim.claim_id],
                    "research_claim_contradiction_note": "Note.",
                },
            )
        )
        self.assertFalse(invalid_contradiction.success)
        self.assertEqual(
            len(manager.get(run.run_id).claim_contradictions),
            1,
        )

    def test_claim_contradiction_write_preview_secret_shaped_note_is_refused(
        self,
    ) -> None:
        sentinel = "distinct-cognitive-engine-secret"
        store = ToggleResearchRunStore()
        claim_ids = iter(("claim-123", "claim-124"))
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=lambda: "evidence-123",
            claim_id_factory=claim_ids.__next__,
        )
        run = manager.create("Evaluate a claim")
        source = ResearchSource(
            "https://example.com/research",
            "Example research",
            "Evidence paragraph.",
            "text/plain",
            datetime(2026, 8, 21, 20, 0, tzinfo=UTC),
        )
        document = self.knowledge_engine.add_document(source.to_document())
        manager.add_source(run.run_id, source, document.document_id)
        evidence = manager.add_evidence(
            run.run_id,
            self.knowledge_engine.search("evidence")[0],
            "Supports authored claim review.",
        ).evidence[-1]
        first = manager.record_claim(
            run.run_id,
            [evidence.evidence_id],
            "Claim one.",
            ResearchEpistemicState.UNKNOWN,
        ).claims[-1]
        second = manager.record_claim(
            run.run_id,
            [evidence.evidence_id],
            "Claim two.",
            ResearchEpistemicState.UNKNOWN,
        ).claims[-1]
        llm_provider = RecordingLLMProvider("must not run")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            llm_provider=llm_provider,
            research_run_manager=manager,
        )
        saves_before = store.save_calls

        response = engine.process(
            BrainRequest(
                "Preview contradiction",
                metadata={
                    "intent": "research_claim_contradiction_write_preview",
                    "research_run_id": run.run_id,
                    "research_claim_contradiction_claim_ids": [
                        first.claim_id,
                        second.claim_id,
                    ],
                    "research_claim_contradiction_note": (
                        f"Authorization: Bearer {sentinel}"
                    ),
                },
            )
        )

        self.assertFalse(response.success)
        self.assertNotIn(sentinel, response.message)
        self.assertEqual(store.save_calls, saves_before)
        self.assertEqual(llm_provider.calls, [])

    def test_explicit_contradiction_proposal_is_read_only_and_uses_current_claims(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        claim_ids = iter(("claim-1", "claim-2", "claim-3"))
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=lambda: "evidence-123",
            claim_id_factory=claim_ids.__next__,
        )
        run = manager.create("Does the treatment help?")
        source = ResearchSource(
            "https://example.com/research",
            "Example research",
            "Evidence paragraph.",
            "text/plain",
            datetime(2026, 8, 21, 21, 0, tzinfo=UTC),
        )
        document = self.knowledge_engine.add_document(source.to_document())
        manager.add_source(run.run_id, source, document.document_id)
        evidence = manager.add_evidence(
            run.run_id,
            self.knowledge_engine.search("evidence")[0],
            "User selected evidence.",
        ).evidence[-1]
        first_run = manager.record_claim(
            run.run_id,
            [evidence.evidence_id],
            "The treatment improves recovery.",
            "likely",
            "medium",
        )
        first_claim = first_run.claims[-1]
        second_run = manager.record_claim(
            run.run_id,
            [evidence.evidence_id],
            "The treatment does not improve recovery.",
            "likely",
            "medium",
        )
        second_claim = second_run.claims[-1]
        candidate = ResearchClaimContradictionCandidate(
            (second_claim.claim_id, first_claim.claim_id),
            (evidence.evidence_id,),
            "The reported effects point in opposite directions.",
        )
        provider = RecordingContradictionProposalProvider([candidate])
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
            research_claim_contradiction_proposal_provider=provider,
        )
        before = manager.get(run.run_id)
        saves_before = store.save_calls

        response = engine.process(
            BrainRequest(
                "Suggest contradictions",
                metadata={
                    "intent": "research_claim_contradiction_proposal",
                    "research_run_id": run.run_id,
                },
            )
        )

        self.assertTrue(response.success)
        preview = response.research_claim_contradiction_proposal_preview
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual(preview.candidates, (candidate,))
        self.assertEqual(preview.claims, (first_claim, second_claim))
        self.assertIn("untrusted suggestion", response.message)
        self.assertIn("nothing recorded", response.message)
        self.assertEqual(
            provider.calls,
            [(run.question, (first_claim, second_claim), 10)],
        )
        self.assertEqual(store.save_calls, saves_before)
        self.assertEqual(manager.get(run.run_id), before)

        def add_concurrent_claim() -> None:
            manager.record_claim(
                run.run_id,
                [evidence.evidence_id],
                "A concurrently added claim.",
                "unknown",
                "unassessed",
            )

        changing_provider = RecordingContradictionProposalProvider(
            [candidate],
            on_propose=add_concurrent_claim,
        )
        changing_engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
            research_claim_contradiction_proposal_provider=changing_provider,
        )
        changed = changing_engine.process(
            BrainRequest(
                "Suggest contradictions",
                metadata={
                    "intent": "research_claim_contradiction_proposal",
                    "research_run_id": run.run_id,
                },
            )
        )
        self.assertFalse(changed.success)
        self.assertIn("changed while", changed.message)
        self.assertEqual(store.save_calls, saves_before + 1)

    def test_contradiction_proposal_rejects_unavailable_existing_and_cancelled(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        claim_ids = iter(("claim-1", "claim-2"))
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=lambda: "evidence-123",
            claim_id_factory=claim_ids.__next__,
            claim_contradiction_id_factory=lambda: "contradiction-1",
        )
        run = manager.create("Question")
        source = ResearchSource(
            "https://example.com/research",
            "Example research",
            "Evidence paragraph.",
            "text/plain",
            datetime(2026, 8, 21, 21, 0, tzinfo=UTC),
        )
        document = self.knowledge_engine.add_document(source.to_document())
        manager.add_source(run.run_id, source, document.document_id)
        evidence = manager.add_evidence(
            run.run_id,
            self.knowledge_engine.search("evidence")[0],
            "Selected.",
        ).evidence[-1]
        manager.record_claim(
            run.run_id,
            [evidence.evidence_id],
            "Claim one.",
            "likely",
            "medium",
        )
        manager.record_claim(
            run.run_id,
            [evidence.evidence_id],
            "Claim two.",
            "likely",
            "medium",
        )
        claims = manager.get(run.run_id).claims
        candidate = ResearchClaimContradictionCandidate(
            (claims[0].claim_id, claims[1].claim_id),
            (evidence.evidence_id,),
            "Possible conflict.",
        )
        unavailable_engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )
        unavailable = unavailable_engine.process(
            BrainRequest(
                "Suggest",
                metadata={
                    "intent": "research_claim_contradiction_proposal",
                    "research_run_id": run.run_id,
                },
            )
        )
        self.assertFalse(unavailable.success)

        manager.record_claim_contradiction(
            run.run_id,
            [claims[0].claim_id, claims[1].claim_id],
            "User already reviewed this pair.",
        )
        provider = RecordingContradictionProposalProvider([candidate])
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
            research_claim_contradiction_proposal_provider=provider,
        )
        saves_before = store.save_calls
        existing = engine.process(
            BrainRequest(
                "Suggest",
                metadata={
                    "intent": "research_claim_contradiction_proposal",
                    "research_run_id": run.run_id,
                },
            )
        )
        self.assertTrue(existing.success)
        existing_preview = existing.research_claim_contradiction_proposal_preview
        self.assertIsNotNone(existing_preview)
        assert existing_preview is not None
        self.assertEqual(existing_preview.candidates, ())
        self.assertEqual(store.save_calls, saves_before)

        cancellation_signal = CancellationSignal()
        cancelling_provider = RecordingContradictionProposalProvider(
            [candidate],
            cancellation_signal=cancellation_signal,
        )
        cancelling_engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
            research_claim_contradiction_proposal_provider=cancelling_provider,
        )
        cancelled = cancelling_engine.process(
            BrainRequest(
                "Suggest",
                metadata={
                    "intent": "research_claim_contradiction_proposal",
                    "research_run_id": run.run_id,
                },
                cancellation_token=cancellation_signal,
            )
        )
        self.assertFalse(cancelled.success)
        self.assertIn("cancelled", cancelled.message)
        self.assertEqual(store.save_calls, saves_before)

    def test_authored_source_assessment_previews_then_commits_without_providers(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        assessment_ids = iter(("assessment-123", "assessment-124"))
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=lambda: "evidence-123",
            assessment_id_factory=assessment_ids.__next__,
        )
        run = manager.create("Compare local models")
        source = ResearchSource(
            "https://example.com/research",
            "Example research",
            "Evidence paragraph.",
            "text/plain",
            datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        document = self.knowledge_engine.add_document(source.to_document())
        manager.add_source(run.run_id, source, document.document_id)
        evidence = manager.add_evidence(
            run.run_id,
            self.knowledge_engine.search("evidence")[0],
            "Supports the assessment.",
        ).evidence[-1]
        fetcher = RecordingResearchSourceFetcher()
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_source_fetcher=fetcher,
            research_run_manager=manager,
        )
        metadata = {
            "research_run_id": run.run_id,
            "research_source_document_id": document.document_id,
            "research_assessment_evidence_ids": [evidence.evidence_id],
            "research_assessment_text": "The source supports the claim.",
            "research_information_trust": "high",
        }
        saves_before = store.save_calls
        documents_before = self.knowledge_engine.documents()
        memory_count = self.memory_manager.count()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        preview_response = engine.process(
            BrainRequest(
                "Preview assessment write",
                metadata={
                    "intent": "research_source_assessment_write_preview",
                    **metadata,
                },
            )
        )

        self.assertTrue(preview_response.success)
        preview = preview_response.research_source_assessment_write_preview
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertTrue(preview.allowed)
        self.assertEqual(preview.evidence, (evidence,))
        self.assertEqual(preview.information_trust, ResearchInformationTrust.HIGH)
        self.assertIn("Information trust: high", preview_response.message)
        self.assertIn("Instruction authority: none", preview_response.message)
        self.assertEqual(store.save_calls, saves_before)

        recorded = engine.process(
            BrainRequest(
                "Record assessment",
                metadata={
                    "intent": "research_source_assessment_record",
                    **metadata,
                },
            )
        )

        self.assertTrue(recorded.success)
        self.assertEqual(recorded.intent, "research_source_assessment_record")
        assessment = recorded.research_runs[0].assessments[-1]
        self.assertEqual(assessment.assessment_id, "assessment-123")
        self.assertEqual(assessment.evidence_ids, (evidence.evidence_id,))
        self.assertEqual(
            assessment.information_trust,
            ResearchInformationTrust.HIGH,
        )
        self.assertIn("Information trust: high", recorded.message)
        self.assertIn("Instruction authority: none", recorded.message)
        self.assertEqual(store.save_calls, saves_before + 1)

        correction_metadata = {
            **metadata,
            "research_assessment_text": "The source supports a narrower claim.",
            "research_assessment_supersedes_id": assessment.assessment_id,
            "research_information_trust": "low",
        }
        correction_preview_response = engine.process(
            BrainRequest(
                "Preview assessment correction",
                metadata={
                    "intent": "research_source_assessment_write_preview",
                    **correction_metadata,
                },
            )
        )
        self.assertTrue(correction_preview_response.success)
        correction_preview = (
            correction_preview_response.research_source_assessment_write_preview
        )
        self.assertIsNotNone(correction_preview)
        assert correction_preview is not None
        self.assertEqual(correction_preview.supersedes_assessment, assessment)
        self.assertEqual(
            correction_preview.information_trust,
            ResearchInformationTrust.LOW,
        )

        corrected = engine.process(
            BrainRequest(
                "Record assessment correction",
                metadata={
                    "intent": "research_source_assessment_record",
                    **correction_metadata,
                },
            )
        )
        self.assertTrue(corrected.success)
        correction = corrected.research_runs[0].assessments[-1]
        self.assertEqual(correction.assessment_id, "assessment-124")
        self.assertEqual(
            correction.supersedes_assessment_id,
            assessment.assessment_id,
        )
        self.assertEqual(
            correction.information_trust,
            ResearchInformationTrust.LOW,
        )
        self.assertEqual(store.save_calls, saves_before + 2)
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        self.assertEqual(events, [])
        self.assertEqual(self.knowledge_engine.documents(), documents_before)
        self.assertEqual(self.memory_manager.count(), memory_count)

    def test_authored_assessment_invalid_inputs_fail_without_mutation(self) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Question")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )

        for intent in (
            "research_source_assessment_write_preview",
            "research_source_assessment_record",
        ):
            for metadata in (
                {},
                {
                    "research_run_id": run.run_id,
                    "research_source_document_id": "document-1",
                    "research_assessment_evidence_ids": [],
                    "research_assessment_text": "Assessment.",
                },
                {
                    "research_run_id": run.run_id,
                    "research_source_document_id": "document-1",
                    "research_assessment_evidence_ids": ["evidence-1"],
                    "research_assessment_text": "Assessment.",
                    "research_information_trust": "trusted",
                },
            ):
                with self.subTest(intent=intent, metadata=metadata):
                    response = engine.process(
                        BrainRequest(
                            "Assessment",
                            metadata={"intent": intent, **metadata},
                        )
                    )
                    self.assertFalse(response.success)
                    self.assertEqual(response.intent, intent)

        self.assertEqual(manager.get(run.run_id), run)

    def test_evidence_type_metadata_threads_through_to_the_recorded_assessment(
        self,
    ) -> None:
        """Mirrors the existing four-dimension metadata pattern exactly.

        Absent means the operator did not answer, which is `unknown` -- never a
        favourable default -- and an explicit answer must reach the persisted
        record unchanged.
        """
        manager = ResearchRunManager(
            id_factory=lambda: "run-123",
            evidence_id_factory=lambda: "evidence-123",
            assessment_id_factory=iter(
                f"assessment-{number}" for number in range(1, 3)
            ).__next__,
        )
        run = manager.create("Compare local models")
        source = ResearchSource(
            "https://example.com/research",
            "Example research",
            "Evidence paragraph.",
            "text/plain",
            datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        document = self.knowledge_engine.add_document(source.to_document())
        manager.add_source(run.run_id, source, document.document_id)
        evidence = manager.add_evidence(
            run.run_id,
            self.knowledge_engine.search("evidence")[0],
            "Supports the assessment.",
        ).evidence[-1]
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )
        base_metadata = {
            "research_run_id": run.run_id,
            "research_source_document_id": document.document_id,
            "research_assessment_evidence_ids": [evidence.evidence_id],
            "research_assessment_text": "The source is a firsthand account.",
        }

        # Absent metadata defaults to unknown, exactly like the other four.
        absent = engine.process(
            BrainRequest(
                "Record assessment",
                metadata={
                    "intent": "research_source_assessment_record",
                    **base_metadata,
                },
            )
        )
        self.assertTrue(absent.success)
        self.assertEqual(
            absent.research_runs[0].assessments[-1].evidence_type,
            ResearchSourceEvidenceType.UNKNOWN,
        )

        # An explicit answer reaches the persisted record unchanged.
        explicit = engine.process(
            BrainRequest(
                "Record corrected assessment",
                metadata={
                    "intent": "research_source_assessment_record",
                    **base_metadata,
                    "research_assessment_text": "Corrected: it is a primary source.",
                    "research_source_evidence_type": "primary",
                },
            )
        )
        self.assertTrue(explicit.success)
        self.assertEqual(
            explicit.research_runs[0].assessments[-1].evidence_type,
            ResearchSourceEvidenceType.PRIMARY,
        )

    def test_failed_authored_assessment_save_is_not_published(self) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=lambda: "evidence-123",
            assessment_id_factory=lambda: "assessment-123",
        )
        run = manager.create("Question")
        source = ResearchSource(
            "https://example.com/research",
            "Research",
            "Evidence.",
            "text/plain",
            datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        document = self.knowledge_engine.add_document(source.to_document())
        manager.add_source(run.run_id, source, document.document_id)
        evidence = manager.add_evidence(
            run.run_id,
            self.knowledge_engine.search("evidence")[0],
            "Relevant.",
        ).evidence[-1]
        before = manager.get(run.run_id)
        store.fail_saves = True
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )

        response = engine.process(
            BrainRequest(
                "Record assessment",
                metadata={
                    "intent": "research_source_assessment_record",
                    "research_run_id": run.run_id,
                    "research_source_document_id": document.document_id,
                    "research_assessment_evidence_ids": [evidence.evidence_id],
                    "research_assessment_text": "Assessment.",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertEqual(manager.get(run.run_id), before)

    def test_failed_research_evidence_save_does_not_publish_candidate(self) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=lambda: "evidence-123",
        )
        run = manager.create("Compare local models")
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="Evidence paragraph.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        document = self.knowledge_engine.add_document(source.to_document())
        attached_run = manager.add_source(run.run_id, source, document.document_id)
        chunk = self.knowledge_engine.search("evidence")[0]
        store.fail_saves = True
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )

        response = engine.process(
            BrainRequest(
                message="Record selected research evidence",
                metadata={
                    "intent": "research_evidence_record",
                    "research_run_id": run.run_id,
                    "research_chunk_id": chunk.chunk_id,
                    "research_evidence_note": "Relevant.",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertEqual(response.message, "Research evidence could not be saved.")
        self.assertEqual(manager.get(run.run_id), attached_run)
        self.assertEqual(manager.get(run.run_id).evidence, ())

    def test_research_status_preview_and_update_close_a_complete_run_safely(
        self,
    ) -> None:
        store = ToggleResearchRunStore()
        manager = ResearchRunManager(
            store,
            id_factory=lambda: "run-123",
            evidence_id_factory=lambda: "evidence-123",
        )
        run = manager.create("Compare local models")
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="Evidence paragraph.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        document = self.knowledge_engine.add_document(source.to_document())
        manager.add_source(run.run_id, source, document.document_id)
        manager.add_evidence(
            run.run_id,
            self.knowledge_engine.search("evidence")[0],
            "Supports completion.",
        )
        llm_provider = RecordingLLMProvider("must not run")
        extractor = RecordingCandidateExtractor()
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
            research_run_manager=manager,
        )
        memory_count = self.memory_manager.count()
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))
        metadata = {
            "research_run_id": run.run_id,
            "research_target_status": "completed",
        }

        preview_response = engine.process(
            BrainRequest(
                message="Preview selected research status",
                metadata={"intent": "research_run_status_preview", **metadata},
            )
        )

        self.assertTrue(preview_response.success)
        preview = preview_response.research_run_status_transition_preview
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertTrue(preview.allowed)
        self.assertEqual(manager.get(run.run_id).status, ResearchRunStatus.COLLECTING)

        updated = engine.process(
            BrainRequest(
                message="Update selected research status",
                metadata={"intent": "research_run_status_update", **metadata},
            )
        )

        self.assertTrue(updated.success)
        self.assertEqual(updated.intent, "research_run_status_update")
        self.assertEqual(updated.research_runs[0].status, ResearchRunStatus.COMPLETED)
        self.assertEqual(store.runs, updated.research_runs)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(llm_provider.calls, [])
        self.assertEqual(extractor.calls, [])
        self.assertEqual(events, [])

    def test_research_status_completion_is_blocked_without_auditable_content(
        self,
    ) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Compare local models")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )
        metadata = {
            "research_run_id": run.run_id,
            "research_target_status": "completed",
        }

        preview_response = engine.process(
            BrainRequest(
                message="Preview selected research status",
                metadata={"intent": "research_run_status_preview", **metadata},
            )
        )
        update_response = engine.process(
            BrainRequest(
                message="Update selected research status",
                metadata={"intent": "research_run_status_update", **metadata},
            )
        )
        invalid_response = engine.process(
            BrainRequest(
                message="Preview selected research status",
                metadata={
                    "intent": "research_run_status_preview",
                    "research_run_id": run.run_id,
                    "research_target_status": "collecting-again",
                },
            )
        )

        self.assertTrue(preview_response.success)
        preview = preview_response.research_run_status_transition_preview
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertFalse(preview.allowed)
        self.assertIn("accepted source", preview.reason)
        self.assertFalse(update_response.success)
        self.assertFalse(invalid_response.success)
        self.assertIn("valid research run ID", invalid_response.message)
        self.assertEqual(manager.get(run.run_id), run)

    def test_closed_research_run_rejects_source_before_network_access(self) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Compare local models")
        manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)
        source = ResearchSource(
            url="https://example.com/research",
            title="Example",
            content="Evidence.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        fetcher = RecordingResearchSourceFetcher(source=source)
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_source_fetcher=fetcher,
            research_run_manager=manager,
        )
        documents_before = self.knowledge_engine.documents()

        response = engine.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": source.url,
                    "research_run_id": run.run_id,
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("closed", response.message)
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(self.knowledge_engine.documents(), documents_before)

    def test_research_status_update_revalidates_after_preview(self) -> None:
        manager = ResearchRunManager(id_factory=lambda: "run-123")
        run = manager.create("Compare local models")
        engine = ProductionCognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            self.planner,
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            research_run_manager=manager,
        )
        metadata = {
            "research_run_id": run.run_id,
            "research_target_status": "cancelled",
        }
        preview_response = engine.process(
            BrainRequest(
                message="Preview selected research status",
                metadata={"intent": "research_run_status_preview", **metadata},
            )
        )
        manager.transition_status(run.run_id, ResearchRunStatus.CANCELLED)

        update_response = engine.process(
            BrainRequest(
                message="Update selected research status",
                metadata={"intent": "research_run_status_update", **metadata},
            )
        )

        preview = preview_response.research_run_status_transition_preview
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertTrue(preview.allowed)
        self.assertFalse(update_response.success)
        self.assertEqual(manager.get(run.run_id).status, ResearchRunStatus.CANCELLED)

    def test_research_source_load_requires_explicit_url_and_fetcher(self) -> None:
        for metadata, expected in (
            ({"intent": "research_source_load"}, "URL is required"),
            (
                {
                    "intent": "research_source_load",
                    "research_url": "https://example.com",
                },
                "loading is unavailable",
            ),
        ):
            with self.subTest(metadata=metadata):
                response = self.engine.process(
                    BrainRequest(
                        message="Load selected internet research source",
                        metadata=metadata,
                    )
                )

                self.assertFalse(response.success)
                self.assertEqual(response.intent, "research_source_load")
                self.assertIn(expected, response.message)
