"""Restart the actual desktop application chain against synthetic disk stores."""

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


class CrossSessionRecallRestartTests(unittest.TestCase):
    def test_real_desktop_handler_reloads_disk_turns_and_preserves_assistance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def start():
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
                ):
                    app = HypatiaApplication.from_process_environment(
                        memory_path=root / "memory.json",
                        session_path=root / "sessions.json",
                    )
                    app.start()
                engine = app.bootstrap.container.resolve(CognitiveEngine)
                transport = Mock(
                    return_value={
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        "Hint: SQL injection can use UNION SELECT."
                                    )
                                }
                            }
                        ]
                    }
                )
                engine._llm_provider._transport = transport
                return (
                    app,
                    engine,
                    DesktopController(
                        app.bootstrap.container.resolve(Brain), None, None
                    ),
                    transport,
                )

            app, engine, desktop, _ = start()
            try:
                engine._session_manager.create("lesson-source")
                desktop.select_session("lesson-source")
                self.assertTrue(
                    desktop.submit_message(
                        "Please give me a SQL injection hint."
                    ).success
                )
                self.assertTrue(
                    desktop.submit_message(
                        "With that help, my SQL injection answer is UNION SELECT."
                    ).success
                )
                original_ids = {r.memory_id for r in engine._memory_manager.all()}
            finally:
                app.stop()
            self.assertTrue((root / "memory.json").is_file())

            reopened, engine, desktop, transport = start()
            try:
                self.assertTrue(
                    original_ids.issubset(
                        {r.memory_id for r in engine._memory_manager.all()}
                    )
                )
                engine._session_manager.create("fresh-session")
                desktop.select_session("fresh-session")
                learned_before = load_learned_memories(engine._memory_manager)
                recall_response = desktop.submit_message(
                    "Let's continue the SQL injection lesson."
                )
                self.assertTrue(recall_response.success)
                self.assertIn('"lesson-source"', recall_response.message)
                self.assertIn("Source sessions", recall_response.message)
                self.assertEqual(recall_response.message.count('"lesson-source"'), 1)
                prompt = transport.call_args.args[2]["messages"][-1]["content"]
                self.assertIn("[session: lesson-source]", prompt)
                original_times = {
                    r.created_at.isoformat()
                    for r in engine._memory_manager.all()
                    if r.memory_id in original_ids and r.created_at is not None
                }
                for timestamp in original_times:
                    self.assertIn(timestamp, prompt)
                self.assertIn("With that help", prompt)
                self.assertIn("Hint: SQL injection", prompt)
                self.assertIn("externally assisted, not independent", prompt)
                self.assertIn(
                    "Missing earlier hints never proves independent mastery", prompt
                )
                self.assertEqual(
                    load_learned_memories(engine._memory_manager), learned_before
                )
                messages = transport.call_args.args[2]["messages"]
                self.assertEqual(len([m for m in messages if m["role"] == "user"]), 1)
                response = desktop.submit_message(
                    "Let's continue quantum cryptography in lesson-source."
                )
                self.assertIn("could not find", response.message)
                self.assertNotIn("lesson-source", response.message)
                self.assertNotIn("Source sessions", response.message)
                self.assertEqual(transport.call_count, 1)
            finally:
                reopened.stop()


if __name__ == "__main__":
    unittest.main()
