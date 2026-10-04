"""Real research-grounded security knowledge: acquire, persist, apply.

Uses Hypatia's existing curated-source research pipeline (discover, accept,
index) together with the existing, unmodified `ask_knowledge` intent to prove
that researched SQL injection and XSS content becomes genuinely queryable
knowledge -- cited, bounded, honest about gaps -- and survives a real
application restart. Nothing here is a new mechanism: this is end-to-end
proof that the mechanisms delivered in v0.3.442 (curated discovery, fetch,
acceptance, content persistence/restoration) and the pre-existing
`ask_knowledge` intent compose correctly for a teaching use case.

Source retrieval itself (the live HTTPS fetch) is proven separately, live,
against the real internet -- see docs/dev/MILESTONE.md for that run's
evidence. These automated tests accept synthetic `ResearchSource` content
through the real, unmodified `ResearchSourceAcceptanceService` so the suite
stays offline and deterministic; everything downstream of "a source was
fetched" (indexing, citation, restart persistence, grounded answering, gap
honesty) is exercised for real.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from core.Application import HypatiaApplication
from llm.LLMRuntimeConfig import LLMRuntimeConfig
from memory.LearnedMemoryStore import load_learned_memories
from research.ResearchSource import ResearchSource

SQLI_EXCERPT = (
    "SQL injection using the UNION keyword lets an attacker execute an "
    "additional SELECT statement and append its results to the original "
    "query's output, provided the injected query returns the same number "
    "of columns. Preventing SQL injection centers on parameterized "
    "queries, which separate the query structure from user-supplied data "
    "so a value can never be interpreted as part of the query itself."
)
XSS_EXCERPT = (
    "Cross-site scripting (XSS) lets an attacker inject script that "
    "executes in another user's browser. Reflected XSS occurs when "
    "unsanitized input is echoed back in the immediate response. "
    "Preventing XSS centers on contextual output encoding: encoding user "
    "data for the specific HTML, attribute, or JavaScript context it is "
    "placed into, rather than a single generic escaping pass."
)
SFRF_UNRESEARCHED_QUERY = "What is server-side request forgery and how does it work?"


def _transport_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


class CybersecurityKnowledgeCurriculumTests(TestCase):
    def _start(
        self,
        root: Path,
        chat_replies: list[str] | None = None,
        extraction_payloads: list[str] | None = None,
        learning_enabled: bool = False,
    ):
        chat_queue = list(chat_replies or [])
        extraction_queue = list(extraction_payloads or [])

        def transport(url, headers, payload):
            del url, headers
            response_format = payload.get("response_format")
            is_extraction = (
                isinstance(response_format, dict)
                and response_format.get("type") == "json_schema"
            )
            content = extraction_queue.pop(0) if is_extraction else chat_queue.pop(0)
            return _transport_response(content)

        environment_patches = patch.dict(
            "os.environ",
            {"HYPATIA_LEARNING_ENABLED": "true"} if learning_enabled else {},
        )
        with (
            patch(
                "core.Bootstrap.load_llm_process_environment_settings",
                return_value=(
                    LLMRuntimeConfig(
                        enabled=True,
                        base_url="https://api.example.test/v1/chat/completions",
                        model="fixture",
                    ),
                    "test-key",
                ),
            ),
            patch(
                "core.Bootstrap.load_llm_process_system_prompt",
                return_value=None,
            ),
            environment_patches,
        ):
            app = HypatiaApplication.from_process_environment(
                memory_path=root / "memory.json",
                session_path=root / "sessions.json",
            )
            app.start()
        engine = app.bootstrap.container.resolve(CognitiveEngine)
        engine._llm_provider._transport = Mock(side_effect=transport)
        return app, engine

    @staticmethod
    def _accept(engine: CognitiveEngine, question: str, url: str, excerpt: str) -> None:
        run = engine._research_run_manager.create(question)
        source = ResearchSource(
            url=url,
            title=question,
            content=excerpt,
            content_type="text/plain",
            fetched_at=datetime.now(UTC),
        )
        result = engine._research_source_acceptance_service.accept(
            source, run.run_id, requested_url=url
        )
        assert result.accepted, result.failure_reason

    def test_accepted_sql_injection_content_grounds_a_cited_answer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine = self._start(
                root,
                ["SQL injection via UNION appends an attacker-chosen SELECT."],
            )
            try:
                self._accept(
                    engine,
                    "SQL injection",
                    "https://portswigger.net/web-security/sql-injection",
                    SQLI_EXCERPT,
                )

                response = engine.process(
                    BrainRequest(
                        message="ask knowledge How does UNION-based SQL "
                        "injection work?"
                    )
                )

                self.assertTrue(response.success, response.message)
                self.assertEqual(
                    response.message,
                    "SQL injection via UNION appends an attacker-chosen SELECT.",
                )
                self.assertEqual(len(response.knowledge_citations), 1)
                self.assertEqual(
                    response.knowledge_citations[0].source,
                    "https://portswigger.net/web-security/sql-injection",
                )
                # The actual retrieved excerpt reached the model, not a
                # paraphrase or a title alone.
                prompt = engine._llm_provider._transport.call_args.args[2]["messages"][
                    -1
                ]["content"]
                self.assertIn("parameterized queries", prompt)
                self.assertIn(
                    "https://portswigger.net/web-security/sql-injection", prompt
                )
            finally:
                app.stop()

    def test_an_unresearched_topic_is_reported_as_a_gap_not_invented(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine = self._start(root, [])
            try:
                self._accept(
                    engine,
                    "SQL injection",
                    "https://portswigger.net/web-security/sql-injection",
                    SQLI_EXCERPT,
                )

                response = engine.process(
                    BrainRequest(message=f"ask knowledge {SFRF_UNRESEARCHED_QUERY}")
                )

                self.assertFalse(response.success)
                self.assertEqual(
                    response.message, "No matching local knowledge was found."
                )
                engine._llm_provider._transport.assert_not_called()
            finally:
                app.stop()

    def test_two_topics_let_ask_knowledge_compare_sqli_and_xss(self) -> None:
        """Distinguishing easily-confused classes: both topics' evidence cited."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine = self._start(
                root,
                [
                    "SQL injection targets the database query; XSS targets "
                    "other users' browsers via injected script."
                ],
            )
            try:
                self._accept(
                    engine,
                    "SQL injection",
                    "https://portswigger.net/web-security/sql-injection",
                    SQLI_EXCERPT,
                )
                self._accept(
                    engine,
                    "Cross-site scripting",
                    "https://portswigger.net/web-security/cross-site-scripting",
                    XSS_EXCERPT,
                )

                response = engine.process(
                    BrainRequest(
                        message="ask knowledge difference between SQL "
                        "injection and cross-site scripting"
                    )
                )

                self.assertTrue(response.success, response.message)
                cited_sources = {c.source for c in response.knowledge_citations}
                self.assertIn(
                    "https://portswigger.net/web-security/sql-injection",
                    cited_sources,
                )
                self.assertIn(
                    "https://portswigger.net/web-security/cross-site-scripting",
                    cited_sources,
                )
            finally:
                app.stop()

    def test_a_synthetic_example_is_analyzed_with_accepted_evidence(self) -> None:
        """A previously-unseen, synthetic code snippet, grounded by evidence."""
        synthetic_example = (
            'query = "SELECT * FROM products WHERE category = \'" + '
            'user_input + "\'"'
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine = self._start(
                root,
                [
                    "This concatenates user input directly into the query, "
                    "so it is vulnerable; use a parameterized query instead."
                ],
            )
            try:
                self._accept(
                    engine,
                    "SQL injection",
                    "https://portswigger.net/web-security/sql-injection",
                    SQLI_EXCERPT,
                )

                response = engine.process(
                    BrainRequest(
                        message="ask knowledge Is this code vulnerable to "
                        f"SQL injection? {synthetic_example}"
                    )
                )

                self.assertTrue(response.success, response.message)
                prompt = engine._llm_provider._transport.call_args.args[2]["messages"][
                    -1
                ]["content"]
                # Both the user's own synthetic example and the cited
                # evidence reached the model -- an actual analysis input,
                # not a question answered from unstated model knowledge.
                self.assertIn(synthetic_example, prompt)
                self.assertIn("parameterized queries", prompt)
            finally:
                app.stop()

    def test_accepted_knowledge_survives_restart_and_still_grounds_answers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine = self._start(root, [])
            try:
                self._accept(
                    engine,
                    "SQL injection",
                    "https://portswigger.net/web-security/sql-injection",
                    SQLI_EXCERPT,
                )
            finally:
                app.stop()

            reopened, reopened_engine = self._start(
                root, ["Restored knowledge still answers: use UNION SELECT."]
            )
            try:
                response = reopened_engine.process(
                    BrainRequest(message="ask knowledge How does SQL injection work?")
                )

                self.assertTrue(response.success, response.message)
                self.assertEqual(len(response.knowledge_citations), 1)
                self.assertEqual(
                    response.knowledge_citations[0].source,
                    "https://portswigger.net/web-security/sql-injection",
                )
            finally:
                reopened.stop()

    def test_teach_via_ask_knowledge_then_assess_without_crediting_a_hint(
        self,
    ) -> None:
        """Requirement 12: teach from acquired knowledge, assess honestly.

        Teaching happens through `ask_knowledge` (cited, no memory mutation,
        so it is not itself a mastery claim). Assessment happens through the
        ordinary conversational path, where the existing, unmodified
        v0.3.443 `AssistedLearningGuard` already applies regardless of
        topic: a hint given in this very curriculum, followed by a claimed-
        independent answer, must still not be recorded as independent
        mastery -- proving the two milestones compose, not just that each
        passes its own tests in isolation.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine = self._start(
                root,
                chat_replies=[
                    "SQL injection via UNION appends an attacker SELECT.",
                    (
                        "Hint: try appending a UNION SELECT with the same "
                        "number of columns as the original query, since the "
                        "database requires both sides of a UNION to match "
                        "in column count before it will return any rows."
                    ),
                    "Correct! Well done.",
                ],
                extraction_payloads=[
                    '{"candidates":[]}',
                    (
                        '{"candidates":[{"kind":"self_fact",'
                        '"key":"sql_injection_understanding",'
                        '"value":"User independently solved the SQL '
                        'injection challenge using UNION SELECT."}]}'
                    ),
                ],
                learning_enabled=True,
            )
            try:
                self._accept(
                    engine,
                    "SQL injection",
                    "https://portswigger.net/web-security/sql-injection",
                    SQLI_EXCERPT,
                )

                # Teach: a cited, grounded explanation via ask_knowledge.
                taught = engine.process(
                    BrainRequest(
                        message="ask knowledge How does UNION-based SQL "
                        "injection work?"
                    )
                )
                self.assertTrue(taught.success, taught.message)
                self.assertEqual(len(taught.knowledge_citations), 1)

                # Assess: an ordinary conversation, hint then claimed-
                # independent answer, in a fresh session.
                engine._session_manager.create("bscp-practice")
                hint = engine.process(
                    BrainRequest(
                        message="I don't know, can you give me a hint?",
                        metadata={"session_id": "bscp-practice"},
                    )
                )
                self.assertTrue(hint.success)

                claim = engine.process(
                    BrainRequest(
                        message="My answer is UNION SELECT. I solved it "
                        "independently.",
                        metadata={"session_id": "bscp-practice"},
                    )
                )

                self.assertTrue(claim.success)
                self.assertEqual(claim.message, "Correct! Well done.")
                learned = load_learned_memories(engine._memory_manager)
                self.assertFalse(
                    any(memory.kind == "self_fact" for memory in learned),
                    "A hint-assisted answer was recorded as independent " "mastery.",
                )
            finally:
                app.stop()


if __name__ == "__main__":
    import unittest

    unittest.main()
