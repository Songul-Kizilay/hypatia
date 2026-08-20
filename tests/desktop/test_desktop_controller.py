"""Headless regression coverage for the narrow desktop-to-Brain adapter."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from desktop.DesktopController import DesktopController


class RecordingBrain:
    """Minimal deterministic Brain substitute for desktop adapter tests."""

    def __init__(self, response: BrainResponse) -> None:
        self.requests: list[BrainRequest | str] = []
        self._response = response

    def process(self, request: BrainRequest | str) -> BrainResponse:
        self.requests.append(request)
        return self._response


class DesktopControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.response = BrainResponse(
            message="Completed.",
            request_id="desktop-test",
            intent="message",
            memory_count=0,
        )
        self.brain = RecordingBrain(self.response)
        self.controller = DesktopController(self.brain)

    def test_submit_message_preserves_non_empty_composer_text(self) -> None:
        message = "  Explain my active project.  "

        response = self.controller.submit_message(message)

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, [message])

    def test_submit_message_rejects_empty_text_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.submit_message(" \t\n ")

        self.assertEqual(self.brain.requests, [])

    def test_select_session_uses_existing_explicit_session_command(self) -> None:
        response = self.controller.select_session("  Work-1  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["use session Work-1"])

    def test_select_session_rejects_empty_id_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.select_session("   ")

        self.assertEqual(self.brain.requests, [])

    def test_session_overview_uses_the_read_only_runtime_command(self) -> None:
        response = self.controller.session_overview()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["session overview"])

    def test_session_details_uses_the_explicit_read_only_command(self) -> None:
        response = self.controller.session_details("  Work-1  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["session details Work-1"])

    def test_session_recent_uses_the_explicit_read_only_command(self) -> None:
        response = self.controller.session_recent("  Work-1  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["session recent Work-1"])

    def test_session_activity_uses_the_explicit_read_only_command(self) -> None:
        response = self.controller.session_activity("  Work-1  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["session activity Work-1"])

    def test_session_specific_views_reject_empty_id_without_calling_brain(self) -> None:
        for action in (
            self.controller.session_details,
            self.controller.session_recent,
            self.controller.session_activity,
        ):
            with self.subTest(action=action.__name__):
                with self.assertRaisesRegex(ValueError, "cannot be empty"):
                    action("   ")

        self.assertEqual(self.brain.requests, [])

    def test_session_search_uses_the_existing_read_only_command(self) -> None:
        response = self.controller.session_search("  Work-1  ", " project plan ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["session search Work-1 -- project plan"],
        )

    def test_session_search_rejects_missing_session_or_query_without_brain_call(
        self,
    ) -> None:
        for session_id, query in (("", "project"), ("Work-1", " \t ")):
            with self.subTest(session_id=session_id, query=query):
                with self.assertRaisesRegex(ValueError, "cannot be empty"):
                    self.controller.session_search(session_id, query)

        self.assertEqual(self.brain.requests, [])

    def test_session_rename_preview_uses_the_existing_read_only_command(self) -> None:
        response = self.controller.preview_session_rename("  Work-1  ", " Archive ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["preview rename session Work-1 -- Archive"],
        )

    def test_session_rename_uses_the_existing_transactional_command(self) -> None:
        response = self.controller.rename_session("  Work-1  ", " Archive ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["rename session Work-1 -- Archive"])

    def test_session_rename_actions_reject_missing_ids_without_calling_brain(
        self,
    ) -> None:
        for action in (
            self.controller.preview_session_rename,
            self.controller.rename_session,
        ):
            for source_id, target_id in (("", "Archive"), ("Work-1", " \t ")):
                with self.subTest(action=action.__name__, ids=(source_id, target_id)):
                    with self.assertRaisesRegex(ValueError, "Both session IDs"):
                        action(source_id, target_id)

        self.assertEqual(self.brain.requests, [])

    def test_session_delete_actions_use_existing_guarded_commands(self) -> None:
        preview = self.controller.preview_session_delete("  Work-1  ")
        deleted = self.controller.delete_session("  Work-1  ")

        self.assertIs(preview, self.response)
        self.assertIs(deleted, self.response)
        self.assertEqual(
            self.brain.requests,
            ["preview delete session Work-1", "delete session Work-1"],
        )

    def test_recall_uses_the_explicit_lexical_command(self) -> None:
        response = self.controller.recall("  project plan  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["recall project plan"])

    def test_semantic_recall_uses_the_explicit_opt_in_command(self) -> None:
        response = self.controller.semantic_recall("  project plan  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["semantic recall project plan"])

    def test_recall_actions_reject_empty_query_without_calling_brain(self) -> None:
        for action in (self.controller.recall, self.controller.semantic_recall):
            with self.subTest(action=action.__name__):
                with self.assertRaisesRegex(ValueError, "cannot be empty"):
                    action(" \t\n ")

        self.assertEqual(self.brain.requests, [])

    def test_knowledge_context_uses_the_explicit_local_command(self) -> None:
        response = self.controller.knowledge_context("  project plan  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["knowledge context project plan"])

    def test_knowledge_context_rejects_empty_query_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.knowledge_context(" \t\n ")

        self.assertEqual(self.brain.requests, [])

    def test_knowledge_graph_uses_the_explicit_local_command(self) -> None:
        response = self.controller.knowledge_graph("  project plan  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["knowledge graph project plan"])

    def test_knowledge_graph_rejects_empty_query_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.knowledge_graph(" \t\n ")

        self.assertEqual(self.brain.requests, [])

    def test_load_knowledge_uses_a_structured_brain_request_for_a_spaced_path(
        self,
    ) -> None:
        response = self.controller.load_knowledge("  C:/Local Notes/project plan.md  ")

        self.assertIs(response, self.response)
        self.assertEqual(len(self.brain.requests), 1)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Load selected local knowledge source")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "knowledge_load",
                "knowledge_path": "C:/Local Notes/project plan.md",
            },
        )

    def test_load_knowledge_rejects_an_empty_path_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.load_knowledge(" \t ")

        self.assertEqual(self.brain.requests, [])

    def test_load_research_source_uses_a_structured_explicit_request(self) -> None:
        response = self.controller.load_research_source(
            "  https://example.com/research  "
        )

        self.assertIs(response, self.response)
        self.assertEqual(len(self.brain.requests), 1)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Load selected internet research source")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_source_load",
                "research_url": "https://example.com/research",
            },
        )

    def test_create_research_run_uses_a_structured_explicit_request(self) -> None:
        response = self.controller.create_research_run("  Compare local models  ")

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Create internet research run")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_run_create",
                "research_question": "Compare local models",
            },
        )

    def test_create_research_run_rejects_empty_question_locally(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.create_research_run(" \t ")

        self.assertEqual(self.brain.requests, [])

    def test_list_research_runs_uses_a_structured_read_only_request(self) -> None:
        response = self.controller.list_research_runs()

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "List internet research runs")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(request.metadata, {"intent": "research_run_list"})

    def test_discover_research_sources_uses_a_structured_explicit_request(
        self,
    ) -> None:
        response = self.controller.discover_research_sources("  run-123  ")

        self.assertIs(response, self.response)
        request = self.brain.requests[-1]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Discover candidate research sources")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_source_discover",
                "research_run_id": "run-123",
            },
        )

    def test_discover_research_sources_rejects_empty_run_id_locally(self) -> None:
        with self.assertRaisesRegex(ValueError, "run ID cannot be empty"):
            self.controller.discover_research_sources(" \t ")

        self.assertEqual(self.brain.requests, [])

    def test_candidate_preview_and_accept_use_explicit_structured_requests(
        self,
    ) -> None:
        values = (" run-123 ", " discovery-1 ", " https://example.com/paper ")

        self.controller.preview_research_source_candidate_acceptance(*values)
        self.controller.accept_research_source_candidate(*values)

        expected = {
            "research_run_id": "run-123",
            "research_discovery_id": "discovery-1",
            "research_url": "https://example.com/paper",
        }
        first, second = self.brain.requests
        assert isinstance(first, BrainRequest)
        assert isinstance(second, BrainRequest)
        self.assertEqual(
            first.metadata,
            {"intent": "research_source_candidate_acceptance_preview", **expected},
        )
        self.assertEqual(
            second.metadata,
            {"intent": "research_source_candidate_accept", **expected},
        )

    def test_candidate_requests_reject_empty_identifiers_locally(self) -> None:
        for values in (
            ("", "discovery-1", "https://example.com/paper"),
            ("run-1", "", "https://example.com/paper"),
            ("run-1", "discovery-1", ""),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.controller.preview_research_source_candidate_acceptance(*values)

        self.assertEqual(self.brain.requests, [])

    def test_record_research_evidence_uses_an_explicit_structured_request(self) -> None:
        response = self.controller.record_research_evidence(
            " run-123 ",
            " chunk-456 ",
            " This paragraph supports the comparison. ",
        )

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "Record selected research evidence")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_evidence_record",
                "research_run_id": "run-123",
                "research_chunk_id": "chunk-456",
                "research_evidence_note": ("This paragraph supports the comparison."),
            },
        )

    def test_record_research_evidence_rejects_empty_fields_locally(self) -> None:
        for run_id, chunk_id, note in (
            ("", "chunk-1", "Note"),
            ("run-1", " ", "Note"),
            ("run-1", "chunk-1", "\t"),
        ):
            with self.subTest(values=(run_id, chunk_id, note)):
                with self.assertRaisesRegex(ValueError, "cannot be empty"):
                    self.controller.record_research_evidence(run_id, chunk_id, note)

        self.assertEqual(self.brain.requests, [])

    def test_list_research_evidence_uses_a_structured_read_only_request(self) -> None:
        response = self.controller.list_research_evidence(" run-123 ")

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(request.message, "List selected research evidence")
        self.assertEqual(request.source, "desktop")
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_evidence_list",
                "research_run_id": "run-123",
            },
        )

    def test_list_research_evidence_rejects_empty_run_id_locally(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.list_research_evidence(" \t ")

        self.assertEqual(self.brain.requests, [])

    def test_research_status_preview_and_update_use_structured_requests(self) -> None:
        preview = self.controller.preview_research_run_status(
            " run-123 ",
            " CANCELLED ",
        )
        updated = self.controller.update_research_run_status(
            " run-123 ",
            " CANCELLED ",
        )

        self.assertIs(preview, self.response)
        self.assertIs(updated, self.response)
        requests = self.brain.requests
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(isinstance(request, BrainRequest) for request in requests))
        assert isinstance(requests[0], BrainRequest)
        assert isinstance(requests[1], BrainRequest)
        expected_values = {
            "research_run_id": "run-123",
            "research_target_status": "cancelled",
        }
        self.assertEqual(
            requests[0].metadata,
            {"intent": "research_run_status_preview", **expected_values},
        )
        self.assertEqual(
            requests[1].metadata,
            {"intent": "research_run_status_update", **expected_values},
        )

    def test_research_status_actions_reject_invalid_values_locally(self) -> None:
        for action in (
            self.controller.preview_research_run_status,
            self.controller.update_research_run_status,
        ):
            for run_id, target in (("", "completed"), ("run-1", "collecting")):
                with self.subTest(action=action.__name__, values=(run_id, target)):
                    with self.assertRaises(ValueError):
                        action(run_id, target)

        self.assertEqual(self.brain.requests, [])

    def test_load_research_source_can_attach_to_an_explicit_run(self) -> None:
        response = self.controller.load_research_source(
            " https://example.com/research ",
            " run-123 ",
        )

        self.assertIs(response, self.response)
        request = self.brain.requests[0]
        self.assertIsInstance(request, BrainRequest)
        assert isinstance(request, BrainRequest)
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_source_load",
                "research_url": "https://example.com/research",
                "research_run_id": "run-123",
            },
        )

    def test_load_research_source_rejects_empty_url_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.load_research_source(" \t ")

        self.assertEqual(self.brain.requests, [])

    def test_ask_knowledge_uses_the_explicit_local_rag_command(self) -> None:
        response = self.controller.ask_knowledge("  what is the project plan?  ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["ask knowledge what is the project plan?"],
        )

    def test_ask_knowledge_rejects_empty_query_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.ask_knowledge(" \t\n ")

        self.assertEqual(self.brain.requests, [])

    def test_knowledge_relation_preview_uses_the_existing_read_only_command(
        self,
    ) -> None:
        response = self.controller.preview_knowledge_relation("  source  ", " target ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["preview knowledge relation source -- target"],
        )

    def test_knowledge_relation_apply_uses_the_existing_mutating_command(self) -> None:
        response = self.controller.apply_knowledge_relation("  source  ", " target ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["apply knowledge relation source -- target"],
        )

    def test_knowledge_relation_actions_reject_missing_ids_without_calling_brain(
        self,
    ) -> None:
        for action in (
            self.controller.preview_knowledge_relation,
            self.controller.apply_knowledge_relation,
        ):
            for source_id, target_id in (("", "target"), ("source", " \t ")):
                with self.subTest(action=action.__name__, ids=(source_id, target_id)):
                    with self.assertRaisesRegex(
                        ValueError, "Both knowledge source IDs"
                    ):
                        action(source_id, target_id)

        self.assertEqual(self.brain.requests, [])

    def test_knowledge_relation_removal_preview_uses_the_existing_command(
        self,
    ) -> None:
        response = self.controller.preview_knowledge_relation_removal(
            "  source  ",
            " target ",
        )

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["preview remove knowledge relation source -- target"],
        )

    def test_knowledge_relation_removal_uses_the_existing_mutating_command(
        self,
    ) -> None:
        response = self.controller.remove_knowledge_relation("  source  ", " target ")

        self.assertIs(response, self.response)
        self.assertEqual(
            self.brain.requests,
            ["remove knowledge relation source -- target"],
        )

    def test_knowledge_relation_removal_actions_reject_missing_ids(self) -> None:
        for action in (
            self.controller.preview_knowledge_relation_removal,
            self.controller.remove_knowledge_relation,
        ):
            for source_id, target_id in (("", "target"), ("source", " \t ")):
                with self.subTest(action=action.__name__, ids=(source_id, target_id)):
                    with self.assertRaisesRegex(
                        ValueError, "Both knowledge source IDs"
                    ):
                        action(source_id, target_id)

        self.assertEqual(self.brain.requests, [])

    def test_list_knowledge_relations_uses_the_existing_read_only_command(
        self,
    ) -> None:
        response = self.controller.list_knowledge_relations()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["list knowledge relations"])

    def test_list_knowledge_uses_the_existing_read_only_catalog_command(self) -> None:
        response = self.controller.list_knowledge()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["list knowledge"])

    def test_semantic_status_uses_the_read_only_runtime_command(self) -> None:
        response = self.controller.semantic_status()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["semantic recall status"])


if __name__ == "__main__":
    unittest.main()
