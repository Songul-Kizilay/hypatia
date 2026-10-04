"""Restart the actual desktop application chain against synthetic disk stores.

Mirrors `test_cross_session_recall_restart.py`'s pattern exactly: a real
`HypatiaApplication`, a real `DesktopController`, a real `CognitiveEngine`
with the real `LLMLearnedMemoryCandidateExtractor` (gated on
HYPATIA_LEARNING_ENABLED, matching Bootstrap's own wiring), with only the
HTTP transport mocked -- the same provider class answers both the ordinary
chat call and the learned-memory extraction call, distinguished here by
their actual payload shape (`response_format.type == "json_schema"` for
extraction), exactly as `OpenAICompatibleProvider` really sends them.

No real EVREN/model call is made; this is a mocked-transport integration
test of the real wiring, not a live-model test.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.Brain import Brain
from cognition.CognitiveEngine import CognitiveEngine
from core.Application import HypatiaApplication
from desktop.DesktopController import DesktopController
from llm.LLMRuntimeConfig import LLMRuntimeConfig
from memory.LearnedMemoryStore import load_learned_memories

HINT_REPLY = (
    "Hint: since the application already displays query results, you can "
    "use the UNION keyword to execute an additional SELECT statement and "
    "append its results to the original query -- for example, appending a "
    "UNION SELECT that reads from the users table."
)
ACKNOWLEDGEMENT_REPLY = "Correct! Well done."
NEW_TOPIC_REPLY = "Good catch -- reflected XSS echoes input back unescaped."


def _transport_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


class SameSessionAssistedLearningRestartTests(unittest.TestCase):
    def _start(
        self, root: Path, chat_replies: list[str], extraction_payloads: list[str]
    ):
        chat_queue = list(chat_replies)
        extraction_queue = list(extraction_payloads)

        def transport(url, headers, payload):
            del url, headers
            response_format = payload.get("response_format")
            is_extraction = (
                isinstance(response_format, dict)
                and response_format.get("type") == "json_schema"
            )
            content = extraction_queue.pop(0) if is_extraction else chat_queue.pop(0)
            return _transport_response(content)

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
            patch.dict(
                "os.environ",
                {"HYPATIA_LEARNING_ENABLED": "true"},
            ),
        ):
            app = HypatiaApplication.from_process_environment(
                memory_path=root / "memory.json",
                session_path=root / "sessions.json",
            )
            app.start()
        engine = app.bootstrap.container.resolve(CognitiveEngine)
        engine._llm_provider._transport = Mock(side_effect=transport)
        desktop = DesktopController(app.bootstrap.container.resolve(Brain), None, None)
        return app, engine, desktop

    def test_an_independence_claim_right_after_a_hint_is_not_persisted_as_mastery(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine, desktop = self._start(
                root,
                chat_replies=[HINT_REPLY, ACKNOWLEDGEMENT_REPLY],
                extraction_payloads=[
                    '{"candidates":[]}',
                    (
                        '{"candidates":[{"kind":"self_fact",'
                        '"key":"sql_injection_understanding",'
                        '"value":"User independently solved SQL injection '
                        'using UNION SELECT."}]}'
                    ),
                ],
            )
            try:
                engine._session_manager.create("bscp-sqli-lesson")
                desktop.select_session("bscp-sqli-lesson")
                hint_response = desktop.submit_message(
                    "I don't know, can you give me a hint?"
                )
                self.assertTrue(hint_response.success, hint_response.message)
                self.assertEqual(hint_response.message, HINT_REPLY)

                claim_response = desktop.submit_message(
                    "My answer is UNION SELECT username, password FROM "
                    "users. I solved it independently."
                )
                self.assertTrue(claim_response.success, claim_response.message)
                self.assertEqual(claim_response.message, ACKNOWLEDGEMENT_REPLY)
            finally:
                app.stop()
            self.assertTrue((root / "memory.json").is_file())

            reopened, reopened_engine, _ = self._start(root, [], [])
            try:
                learned = load_learned_memories(reopened_engine._memory_manager)
                self.assertFalse(
                    any(memory.kind == "self_fact" for memory in learned),
                    f"A self_fact survived restart: {learned}",
                )
            finally:
                reopened.stop()

    def test_an_unaided_answer_to_a_new_question_is_persisted_normally(self) -> None:
        """Negative control: no recent hint means no suppression."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine, desktop = self._start(
                root,
                chat_replies=[NEW_TOPIC_REPLY],
                extraction_payloads=[
                    (
                        '{"candidates":[{"kind":"self_fact",'
                        '"key":"xss_understanding",'
                        '"value":"User independently explained reflected '
                        'XSS."}]}'
                    ),
                ],
            )
            try:
                engine._session_manager.create("bscp-xss-lesson")
                desktop.select_session("bscp-xss-lesson")
                response = desktop.submit_message(
                    "Reflected XSS happens when unsanitized input is echoed "
                    "back in the response; I worked this out independently."
                )
                self.assertTrue(response.success, response.message)
            finally:
                app.stop()

            reopened, reopened_engine, _ = self._start(root, [], [])
            try:
                learned = load_learned_memories(reopened_engine._memory_manager)
                self.assertTrue(
                    any(
                        memory.kind == "self_fact" and memory.key == "xss_understanding"
                        for memory in learned
                    ),
                    f"The unaided self_fact did not survive restart: {learned}",
                )
            finally:
                reopened.stop()


if __name__ == "__main__":
    unittest.main()
