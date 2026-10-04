"""Real research-grounded Kali tool knowledge: acquire, persist, apply.

Same pipeline, same discipline, as `test_cybersecurity_knowledge_curriculum.py`
(v0.3.444): the existing curated-source research pipeline (discover, accept,
index) together with the existing, unmodified `ask_knowledge` intent proves
that researched tool-documentation content becomes genuinely queryable
knowledge -- cited, bounded, honest about gaps -- and survives a real
application restart. Nothing here is a new mechanism, and nothing here
executes a tool: this is LEARN-only knowledge, proven the same way the first
two topics were, for Nmap and OpenSSL as representative Kali Linux tools from
the eleven-entry catalog added in this milestone.

Source retrieval itself (the live HTTPS fetch) is proven separately, live,
against the real internet -- see docs/dev/MILESTONE.md for that run's
evidence. These automated tests accept synthetic `ResearchSource` content
through the real, unmodified `ResearchSourceAcceptanceService` so the suite
stays offline and deterministic.
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
from research.ResearchSource import ResearchSource

NMAP_URL = "https://nmap.org/book/man.html"
NMAP_EXCERPT = (
    "Nmap's default SYN scan (-sS) sends a TCP SYN packet to each probed "
    "port and inspects the response without completing the handshake: a "
    "SYN/ACK means the port is open, a RST means it is closed, and no "
    "response (after retries) means it is filtered. Service and version "
    "detection (-sV) then sends protocol-specific probes to an open port "
    "to identify the application and version actually listening there, "
    "rather than assuming it from the port number alone."
)
OPENSSL_URL = "https://docs.openssl.org/master/man1/openssl/"
OPENSSL_EXCERPT = (
    "openssl s_client connects to a remote TLS server and prints the "
    "negotiated protocol version, cipher suite, and the full certificate "
    "chain presented, which is the standard way to check what a server "
    "actually offers rather than what its configuration file claims. "
    "openssl x509 -noout -dates reads a certificate's own notBefore and "
    "notAfter fields to show exactly when it was issued and when it "
    "expires."
)
UNRESEARCHED_TOOL_QUERY = "What is Metasploit used for and how does it work?"


def _transport_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


class KaliToolKnowledgeTests(TestCase):
    def _start(self, root: Path, chat_replies: list[str] | None = None):
        chat_queue = list(chat_replies or [])

        def transport(url, headers, payload):
            del url, headers, payload
            return _transport_response(chat_queue.pop(0))

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

    def test_accepted_nmap_documentation_grounds_a_cited_answer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine = self._start(
                root,
                [
                    "A SYN scan sends a SYN and reads the reply without "
                    "finishing the handshake."
                ],
            )
            try:
                self._accept(engine, "Nmap", NMAP_URL, NMAP_EXCERPT)

                response = engine.process(
                    BrainRequest(message="ask knowledge How does Nmap's SYN scan work?")
                )

                self.assertTrue(response.success, response.message)
                self.assertEqual(len(response.knowledge_citations), 1)
                self.assertEqual(response.knowledge_citations[0].source, NMAP_URL)
                prompt = engine._llm_provider._transport.call_args.args[2]["messages"][
                    -1
                ]["content"]
                self.assertIn("SYN/ACK", prompt)
                self.assertIn(NMAP_URL, prompt)
            finally:
                app.stop()

    def test_an_uncatalogued_tool_is_reported_as_a_gap_not_invented(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine = self._start(root, [])
            try:
                self._accept(engine, "Nmap", NMAP_URL, NMAP_EXCERPT)

                response = engine.process(
                    BrainRequest(message=f"ask knowledge {UNRESEARCHED_TOOL_QUERY}")
                )

                self.assertFalse(response.success)
                self.assertEqual(
                    response.message, "No matching local knowledge was found."
                )
                engine._llm_provider._transport.assert_not_called()
            finally:
                app.stop()

    def test_two_tools_let_ask_knowledge_compare_nmap_and_openssl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine = self._start(
                root,
                [
                    "Nmap discovers open ports and services; openssl s_client "
                    "then inspects the TLS configuration one of those "
                    "services actually presents."
                ],
            )
            try:
                self._accept(engine, "Nmap", NMAP_URL, NMAP_EXCERPT)
                self._accept(engine, "OpenSSL", OPENSSL_URL, OPENSSL_EXCERPT)

                response = engine.process(
                    BrainRequest(
                        message="ask knowledge how would I use Nmap and "
                        "openssl together to check a server's TLS setup?"
                    )
                )

                self.assertTrue(response.success, response.message)
                cited_sources = {c.source for c in response.knowledge_citations}
                self.assertIn(NMAP_URL, cited_sources)
                self.assertIn(OPENSSL_URL, cited_sources)
            finally:
                app.stop()

    def test_accepted_tool_knowledge_survives_restart_and_still_grounds_answers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, engine = self._start(root, [])
            try:
                self._accept(engine, "OpenSSL", OPENSSL_URL, OPENSSL_EXCERPT)
            finally:
                app.stop()

            reopened, reopened_engine = self._start(
                root,
                [
                    "Restored knowledge still answers: use openssl s_client "
                    "to inspect the certificate chain."
                ],
            )
            try:
                response = reopened_engine.process(
                    BrainRequest(
                        message="ask knowledge How do I check a TLS "
                        "certificate with OpenSSL?"
                    )
                )

                self.assertTrue(response.success, response.message)
                self.assertEqual(len(response.knowledge_citations), 1)
                self.assertEqual(response.knowledge_citations[0].source, OPENSSL_URL)
            finally:
                reopened.stop()


if __name__ == "__main__":
    import unittest

    unittest.main()
