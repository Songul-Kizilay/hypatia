"""Ordinary chat may not narrate research it never performed.

These tests come from a real failure. Asked in Turkish for three 2026 papers on
web application security, and later for three of today's security news stories
with sources, the runtime answered with plausible authors, journals, and
outlets that do not exist, and then — asked what evidence it had collected —
described those inventions as collected evidence.

Two things are asserted here, and they are different things. The first is that
such a request never reaches the model at all, so there is nothing to fabricate.
The second is that even an ordinary reply that claims research is corrected
against canonical persisted state, because a prompt cannot make a model honest
and only the recorded operations know what happened.

Nothing in this file is allowed to touch a network, and every test asserts that
research state is byte-identical afterwards.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from datetime import UTC, datetime

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ConversationResearchClaimGuard import (
    CORRECTION_HEADING,
    ConversationResearchClaimGuard,
)
from cognition.LiveInformationRequestDetector import LiveInformationRequestDetector
from cognition.LiveInformationRequestKind import LiveInformationRequestKind
from cognition.ResearchHonestyApplicationService import (
    ResearchHonestyApplicationService,
)
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from llm.LLMConversationMessage import LLMConversationMessage
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.HonestyPhrasebook import phrase
from response.ResponseComposer import ResponseComposer
from response.ResponseLanguage import (
    ResponseLanguage,
    detect_response_language,
)
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

FETCHED = datetime(2026, 8, 1, tzinfo=UTC)

FABRICATION_PROMPTS = (
    "2026 yılında yayımlanmış web application security veya bug bounty ile "
    "ilgili 3 güncel akademik kaynak bul.",
    "Bugün yayımlanan 3 siber güvenlik haberi bul. Kaynaklarını ver.",
    "Find me three recent papers on web application security.",
    "Search the internet for the latest news on bug bounty programs.",
    "Give me sources for this and cite your sources.",
)

ORDINARY_PROMPTS = (
    "Merhaba, nasılsın?",
    "What is HTTP?",
    "Explain what a closure is in Python.",
    "Bu konuda haberim yok, açıklar mısın?",
    "My test secret word is Morvella.",
    "Kaynak kodunu nasıl derlerim?",
)


class RecordingLLMProvider:
    """Record every generation so an accidental model call is visible."""

    def __init__(self, response: str) -> None:
        self.calls: list[tuple[str, tuple[LLMConversationMessage, ...]]] = []
        self.response = response

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
    ) -> str:
        self.calls.append((prompt, history))
        return self.response


class HonestyFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        self.knowledge_engine = KnowledgeEngine()
        document = self.root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        self.knowledge_engine.load(document)
        self.manager = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        self.manager.load()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def build_engine(
        self,
        provider: RecordingLLMProvider | None = None,
        with_runs: bool = True,
    ) -> CognitiveEngine:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        session_manager = SessionManager(event_bus)
        return CognitiveEngine(
            self.knowledge_engine,
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
            llm_provider=provider,
            research_run_manager=self.manager if with_runs else None,
        )

    def chat(self, engine: CognitiveEngine, message: str) -> object:
        return engine.process(BrainRequest(message=message))

    def research_state(self) -> bytes:
        return self.run_path.read_bytes() if self.run_path.exists() else b""

    def recorded_evidence(self) -> str:
        """Create a run with one accepted source and one evidence record."""
        run_id = self.manager.create("Does the ring system have an age?").run_id
        acceptance = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            _InMemoryContentStore(),  # type: ignore[arg-type]
        )
        result = acceptance.accept(
            ResearchSource(
                url="https://example.test/rings",
                title="Rings",
                content="Saturn has a prominent ring system with a debated age.",
                content_type="text/html",
                fetched_at=FETCHED,
            ),
            run_id,
        )
        assert result.document_id is not None
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == result.document_id and candidate.index == 0
        )
        self.manager.add_evidence(run_id, chunk, "Directly relevant.")
        return run_id


class _InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


class LiveInformationDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = LiveInformationRequestDetector()

    def test_the_real_fabrication_prompts_are_all_detected(self) -> None:
        for prompt in FABRICATION_PROMPTS:
            with self.subTest(prompt=prompt):
                self.assertTrue(self.detector.detect(prompt).detected, prompt)

    def test_ordinary_conversation_is_not_detected(self) -> None:
        for prompt in ORDINARY_PROMPTS:
            with self.subTest(prompt=prompt):
                self.assertIs(
                    self.detector.detect(prompt),
                    LiveInformationRequestKind.NONE,
                    prompt,
                )

    def test_an_evidence_question_is_classified_most_specifically(self) -> None:
        self.assertIs(
            self.detector.detect("Bu konuda hangi kanıtları topladın?"),
            LiveInformationRequestKind.EVIDENCE_PROVENANCE,
        )
        self.assertIs(
            self.detector.detect("What evidence did you collect for this?"),
            LiveInformationRequestKind.EVIDENCE_PROVENANCE,
        )

    def test_current_events_academic_and_search_are_distinguished(self) -> None:
        self.assertIs(
            self.detector.detect("Bugün yayımlanan 3 haberi bul."),
            LiveInformationRequestKind.CURRENT_EVENTS,
        )
        self.assertIs(
            self.detector.detect("Bana akademik kaynak lazım."),
            LiveInformationRequestKind.ACADEMIC_SOURCES,
        )
        self.assertIs(
            self.detector.detect("Please search the internet."),
            LiveInformationRequestKind.WEB_SEARCH,
        )

    def test_turkish_dotted_capitals_still_match(self) -> None:
        self.assertTrue(self.detector.detect("İNTERNETTEN ARA").detected)
        self.assertTrue(self.detector.detect("KAYNAKLARINI VER").detected)

    def test_an_empty_message_is_not_detected(self) -> None:
        for message in ("", "   ", None):
            with self.subTest(message=message):
                self.assertIs(
                    self.detector.detect(message),  # type: ignore[arg-type]
                    LiveInformationRequestKind.NONE,
                )

    def test_only_a_live_kind_requires_research(self) -> None:
        self.assertFalse(LiveInformationRequestKind.NONE.requires_live_research)
        self.assertFalse(
            LiveInformationRequestKind.EVIDENCE_PROVENANCE.requires_live_research
        )
        for kind in (
            LiveInformationRequestKind.CURRENT_EVENTS,
            LiveInformationRequestKind.ACADEMIC_SOURCES,
            LiveInformationRequestKind.WEB_SEARCH,
        ):
            self.assertTrue(kind.requires_live_research)


class LiveResearchRefusalTests(HonestyFixture):
    def test_a_live_information_request_never_reaches_the_model(self) -> None:
        provider = RecordingLLMProvider("Here are three papers: Smith et al.")
        engine = self.build_engine(provider)

        for prompt in FABRICATION_PROMPTS:
            with self.subTest(prompt=prompt):
                self.chat(engine, prompt)

        self.assertEqual(provider.calls, [])

    def test_the_refusal_states_that_live_research_did_not_happen(self) -> None:
        engine = self.build_engine(RecordingLLMProvider("fabricated"))

        prompt = FABRICATION_PROMPTS[0]
        response = self.chat(engine, prompt)

        self.assertIn(
            phrase("no_live_research", detect_response_language(prompt)),
            response.message,
        )
        self.assertIs(
            response.live_information_request,
            LiveInformationRequestKind.ACADEMIC_SOURCES,
        )

    def test_the_refusal_reports_canonical_counts(self) -> None:
        engine = self.build_engine(RecordingLLMProvider("fabricated"))

        response = self.chat(engine, FABRICATION_PROMPTS[1])

        self.assertIn("Sources accepted: 0", response.message)
        self.assertIn("Evidence records: 0", response.message)
        assert response.canonical_research_summary is not None
        self.assertTrue(response.canonical_research_summary.empty)

    def test_the_refusal_points_at_the_explicit_research_workflow(self) -> None:
        engine = self.build_engine(RecordingLLMProvider("fabricated"))

        prompt = FABRICATION_PROMPTS[3]
        response = self.chat(engine, prompt)

        self.assertIn(
            phrase("use_research", detect_response_language(prompt)),
            response.message,
        )

    def test_refusing_creates_no_research_state(self) -> None:
        engine = self.build_engine(RecordingLLMProvider("fabricated"))
        before = self.research_state()

        for prompt in FABRICATION_PROMPTS:
            self.chat(engine, prompt)

        self.assertEqual(self.research_state(), before)
        self.assertEqual(self.manager.list(), [])

    def test_ordinary_chat_still_reaches_the_model(self) -> None:
        provider = RecordingLLMProvider("A closure captures its enclosing scope.")
        engine = self.build_engine(provider)

        response = self.chat(engine, "Explain what a closure is in Python.")

        self.assertEqual(len(provider.calls), 1)
        self.assertIn("closure", response.message)

    def test_the_refusal_works_without_a_run_store(self) -> None:
        engine = self.build_engine(RecordingLLMProvider("x"), with_runs=False)

        response = self.chat(engine, FABRICATION_PROMPTS[2])

        self.assertIn(
            phrase("no_live_research", ResponseLanguage.ENGLISH),
            response.message,
        )
        self.assertIn("Research runs: 0", response.message)


class EvidenceProvenanceTests(HonestyFixture):
    def test_an_evidence_question_is_answered_from_canonical_state(self) -> None:
        provider = RecordingLLMProvider("I collected these sources for you.")
        engine = self.build_engine(provider)

        question = "Bu konuda hangi kanıtları topladın?"
        language = detect_response_language(question)

        response = self.chat(engine, question)

        self.assertEqual(provider.calls, [])
        self.assertIn(phrase("evidence_heading", language), response.message)
        self.assertIn("Evidence records: 0", response.message)
        self.assertIn(phrase("evidence_none_at_all", language), response.message)

    def test_recorded_evidence_is_reported_truthfully(self) -> None:
        self.recorded_evidence()
        engine = self.build_engine(RecordingLLMProvider("x"))

        response = self.chat(engine, "What evidence did you collect?")

        self.assertIn("Evidence records: 1", response.message)
        self.assertIn("Sources accepted: 1", response.message)
        assert response.canonical_research_summary is not None
        self.assertTrue(response.canonical_research_summary.has_evidence)

    def test_an_accepted_source_alone_is_not_reported_as_evidence(self) -> None:
        run_id = self.manager.create("Does the ring system have an age?").run_id
        ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            _InMemoryContentStore(),  # type: ignore[arg-type]
        ).accept(
            ResearchSource(
                url="https://example.test/rings",
                title="Rings",
                content="Saturn has a prominent ring system.",
                content_type="text/html",
                fetched_at=FETCHED,
            ),
            run_id,
        )
        engine = self.build_engine(RecordingLLMProvider("x"))

        response = self.chat(engine, "What evidence did you collect?")

        self.assertIn("Sources accepted: 1", response.message)
        self.assertIn("Evidence records: 0", response.message)
        self.assertIn(
            phrase("evidence_sources_without_evidence", ResponseLanguage.ENGLISH),
            response.message,
        )

    def test_the_summary_keeps_every_stage_separate(self) -> None:
        self.recorded_evidence()

        summary = CanonicalResearchSummary.from_runs(self.manager.list())

        self.assertEqual(summary.source_count, 1)
        self.assertEqual(summary.evidence_count, 1)
        self.assertEqual(summary.assessment_count, 0)
        self.assertEqual(summary.claim_count, 0)
        self.assertEqual(summary.contradiction_count, 0)

    def test_an_empty_summary_reports_zeros(self) -> None:
        summary = CanonicalResearchSummary()

        self.assertTrue(summary.empty)
        self.assertFalse(summary.has_evidence)
        self.assertIn("Evidence records: 0", summary.lines())


class ResearchClaimGuardTests(HonestyFixture):
    def setUp(self) -> None:
        super().setUp()
        self.guard = ConversationResearchClaimGuard()

    def test_first_person_research_claims_are_recognised(self) -> None:
        for reply in (
            "I researched this and found three papers.",
            "Based on my research, the outlet published it today.",
            "My sources show a different date.",
            "I verified this against two references.",
            "Bunu araştırdım ve üç kaynak buldum.",
            "Konuyla ilgili kanıtları topladım.",
        ):
            with self.subTest(reply=reply):
                self.assertTrue(self.guard.inspect(reply), reply)

    def test_an_ordinary_reply_is_left_exactly_alone(self) -> None:
        reply = "A closure captures the variables of its enclosing scope."

        self.assertFalse(self.guard.inspect(reply))
        self.assertEqual(self.guard.annotate(reply, CanonicalResearchSummary()), reply)

    def test_an_overclaiming_reply_is_annotated_not_replaced(self) -> None:
        reply = "I researched this and found three papers by Smith et al."

        annotated = self.guard.annotate(reply, CanonicalResearchSummary())

        self.assertIn(reply, annotated)
        self.assertIn(CORRECTION_HEADING, annotated)
        self.assertIn("Evidence records: 0", annotated)
        self.assertIn("model output, not something Hypatia read", annotated)

    def test_the_correction_names_what_the_turn_did_not_do(self) -> None:
        correction = "\n".join(
            ConversationResearchClaimGuard.correction(CanonicalResearchSummary())
        )

        self.assertIn("no source discovery", correction)
        self.assertIn("no fetch", correction)
        self.assertIn("recorded no evidence", correction)

    def test_a_model_reply_claiming_research_is_corrected_end_to_end(self) -> None:
        provider = RecordingLLMProvider(
            "I searched the web and found three articles from SecurityNow.net."
        )
        engine = self.build_engine(provider)

        response = self.chat(engine, "Tell me something about bug bounty programs.")

        self.assertEqual(len(provider.calls), 1)
        self.assertIn(CORRECTION_HEADING, response.message)
        self.assertIn("Evidence records: 0", response.message)

    def test_the_correction_reports_real_counts_when_they_exist(self) -> None:
        self.recorded_evidence()
        provider = RecordingLLMProvider("I verified this myself.")
        engine = self.build_engine(provider)

        response = self.chat(engine, "Tell me about the rings.")

        self.assertIn(CORRECTION_HEADING, response.message)
        self.assertIn("Evidence records: 1", response.message)

    def test_guarding_creates_no_research_state(self) -> None:
        provider = RecordingLLMProvider("I researched this thoroughly.")
        engine = self.build_engine(provider)
        before = self.research_state()

        self.chat(engine, "Tell me about bug bounty programs.")

        self.assertEqual(self.research_state(), before)


class OrdinaryChatIsInertTests(HonestyFixture):
    RESEARCH_TALK = (
        "Tell me what evidence means in your architecture.",
        "Explain how a research run works.",
        "What is a source assessment?",
        "Describe a claim and a contradiction.",
        "Bir kaynak nasıl kabul edilir?",
    )

    def test_talking_about_research_mutates_no_research_state(self) -> None:
        provider = RecordingLLMProvider("Here is an explanation of the concept.")
        engine = self.build_engine(provider)
        self.recorded_evidence()
        before = self.research_state()
        summary_before = CanonicalResearchSummary.from_runs(self.manager.list())

        for message in self.RESEARCH_TALK:
            self.chat(engine, message)

        self.assertEqual(self.research_state(), before)
        self.assertEqual(
            CanonicalResearchSummary.from_runs(self.manager.list()),
            summary_before,
        )

    def test_ordinary_chat_creates_no_run_source_or_evidence(self) -> None:
        provider = RecordingLLMProvider("An explanation.")
        engine = self.build_engine(provider)

        for message in (*self.RESEARCH_TALK, *ORDINARY_PROMPTS):
            self.chat(engine, message)

        self.assertEqual(self.manager.list(), [])
        self.assertTrue(CanonicalResearchSummary.from_runs(self.manager.list()).empty)


class HonestyCompositionTests(HonestyFixture):
    def test_the_engine_wires_the_honesty_service_over_the_run_manager(self) -> None:
        engine = self.build_engine(RecordingLLMProvider("x"))

        service = engine._research_honesty_service

        self.assertIsInstance(service, ResearchHonestyApplicationService)
        self.assertIs(service._run_manager, self.manager)
        self.assertIsInstance(
            engine._conversation_research_claim_guard,
            ConversationResearchClaimGuard,
        )

    def test_the_service_reports_zeros_without_a_run_manager(self) -> None:
        service = ResearchHonestyApplicationService(ResponseComposer())

        self.assertTrue(service.summary().empty)

    def test_the_service_answers_without_calling_any_model(self) -> None:
        service = ResearchHonestyApplicationService(
            ResponseComposer(),
            run_manager=self.manager,
        )
        request = BrainRequest(message="Search the internet for today's news.")

        kind = service.detect(request)
        response = service.process(request, kind)

        self.assertIs(kind, LiveInformationRequestKind.CURRENT_EVENTS)
        self.assertIn(
            phrase("no_live_research", ResponseLanguage.ENGLISH),
            response.message,
        )


if __name__ == "__main__":
    unittest.main()
