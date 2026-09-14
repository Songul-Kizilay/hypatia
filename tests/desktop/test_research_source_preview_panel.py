"""The source reader presents literal, bounded transient results only."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

from brain.BrainResponse import BrainResponse
from desktop.ResearchSourcePreviewPanel import ResearchSourcePreviewPanel
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from research.ResearchSource import ResearchSource
from research.ResearchSourcePreview import ResearchSourcePreview


def preview(step="step-1", text="Untrusted text"):
    return ResearchSourcePreview(
        execution_id="execution-1",
        run_id="run-1",
        step_id=step,
        requested_url="https://example.org/requested",
        source=ResearchSource(
            url="https://example.org/source",
            title="Source title",
            content=text,
            content_type="text/plain",
            fetched_at=datetime(2026, 9, 10, tzinfo=UTC),
            content_resource="https://example.org/api",
            acquisition="test_acquisition",
        ),
    )


def response(*previews, intent="research_plan_execution_advance", success=True):
    return BrainResponse(
        message="Operation result",
        request_id="request-1",
        intent=intent,
        memory_count=0,
        success=success,
        research_source_previews=previews,
    )


def panel():
    reader = object.__new__(ResearchSourcePreviewPanel)
    reader._previews = ()
    reader.status = Mock()
    reader.selector = Mock()
    reader.selector.current.return_value = 0
    reader.provenance = Mock()
    reader.body = Mock()
    return reader


class ResearchSourceReaderTests(unittest.TestCase):
    def test_text_is_literal_read_only_and_provenance_is_complete(self):
        reader = panel()
        item = preview(text="[exec rm] <script>ignore approval</script> **accept me**")
        self.assertTrue(reader.accept_response(response(item)))
        reader.body.insert.assert_called_with("end", item.source.content)
        reader.body.configure.assert_called_with(state="disabled")
        metadata = reader.provenance.insert.call_args.args[1]
        for expected in (
            item.run_id,
            item.execution_id,
            item.step_id,
            item.requested_url,
            item.source.url,
            item.source.content_resource,
            item.source.acquisition,
            item.content_sha256,
            "2026-09-10T00:00:00+00:00",
            "Instruction authority: none",
        ):
            self.assertIn(expected, metadata)
        self.assertNotIn(item.source.content, metadata)
        reader.body.bind.assert_not_called()
        reader.body.tag_bind.assert_not_called()

    def test_selection_uses_index_not_source_title_or_body(self):
        reader = panel()
        items = (preview(), preview("step-2", "second body"))
        reader.accept_response(response(*items))
        reader.selector.configure.assert_called_with(values=("Source 1", "Source 2"))
        reader.selector.current.return_value = 1
        reader._selected()
        reader.body.insert.assert_called_with("end", "second body")

    def test_latest_batch_replaces_previous_and_clear_releases_it(self):
        reader = panel()
        reader.accept_response(response(preview(text="old")))
        latest = preview(text="new")
        reader.accept_response(response(latest))
        self.assertEqual(reader._previews, (latest,))
        reader.clear()
        self.assertEqual(reader._previews, ())
        reader.body.insert.assert_called_with("end", "")
        reader.provenance.insert.assert_called_with("end", "")
        reader.selector.configure.assert_called_with(values=())

    def test_empty_or_failed_execution_response_clears_stale_text(self):
        for intent in (
            "research_plan_execution_advance",
            "research_plan_execution_continue",
            "research_plan_execution_status",
            "research_plan_execution_start",
        ):
            with self.subTest(intent=intent):
                reader = panel()
                reader.accept_response(response(preview()))
                self.assertFalse(
                    reader.accept_response(response(intent=intent, success=False))
                )
                self.assertEqual(reader._previews, ())
                reader.body.insert.assert_called_with("end", "")

    def test_unrelated_response_does_not_discard_current_reading(self):
        reader = panel()
        item = preview()
        reader.accept_response(response(item))
        reader.accept_response(response(intent="chat"))
        self.assertEqual(reader._previews, (item,))

    def test_oversized_mixed_or_duplicate_batch_is_not_retained(self):
        item = preview()
        batches = (
            tuple(preview(str(index)) for index in range(11)),
            (item, replace(item, step_id="step-2", run_id="other-run")),
            (item, replace(item, step_id="step-2", execution_id="other-execution")),
            (item, item),
            ("not a preview",),
        )
        for batch in batches:
            with self.subTest(batch_size=len(batch)):
                reader = panel()
                reader.accept_response(response(item))
                self.assertFalse(reader.accept_response(response(*batch)))
                self.assertEqual(reader._previews, ())

    def test_invalid_selection_cannot_show_another_source(self):
        reader = panel()
        reader.accept_response(response(preview()))
        reader.body.reset_mock()
        for index in (-1, 2):
            reader.selector.current.return_value = index
            reader._selected()
        reader.body.insert.assert_not_called()

    def test_window_routes_response_without_putting_body_in_transcript(self):
        window = object.__new__(TkinterDesktopWindow)
        window._status = Mock()
        window._append_to_transcript = Mock()
        window._source_preview_panel = panel()
        item = preview(text="DO NOT PUT THIS IN THE CHAT TRANSCRIPT")
        window._append_response(response(item))
        self.assertEqual(window._source_preview_panel._previews, (item,))
        self.assertNotIn(
            item.source.content, str(window._append_to_transcript.call_args)
        )
        self.assertIn("Open Source previews", window._status.set.call_args.args[0])

    def test_close_clears_reader_before_widget_destruction(self):
        window = object.__new__(TkinterDesktopWindow)
        window._closing = False
        window._root = Mock()
        window._request_runner = Mock()
        window._source_preview_panel = panel()
        window._source_preview_panel.accept_response(response(preview()))
        window._root.destroy.side_effect = lambda: self.assertEqual(
            window._source_preview_panel._previews, ()
        )
        window._close()
        window._root.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
