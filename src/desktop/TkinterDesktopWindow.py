"""Tkinter presentation for the deliberately narrow first desktop shell."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Protocol

from brain.BrainResponse import BrainResponse
from brain.SessionSummary import SessionSummary
from core.CancellationSignal import CancellationSignal
from desktop.DesktopController import DesktopController
from desktop.DesktopRequestRunner import DesktopRequestRunner
from knowledge.KnowledgeCitation import KnowledgeCitation
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRunMarkdownExportPreview import (
    ResearchRunMarkdownExportPreview,
)
from research.ResearchSourceCandidate import ResearchSourceCandidate

_DEFAULT_FONT_SIZE = 12
_MINIMUM_FONT_SIZE = 10
_MAXIMUM_FONT_SIZE = 20
_REQUEST_POLL_INTERVAL_MS = 50


@dataclass(frozen=True, slots=True)
class AccessibilityPalette:
    """Explicit readable colors for the local desktop presentation."""

    background: str
    foreground: str
    field_background: str
    button_background: str
    active_background: str
    selection_background: str
    focus_color: str


def _accessibility_palette(high_contrast: bool) -> AccessibilityPalette:
    """Return a fully explicit palette so contrast never depends on color alone."""
    if high_contrast:
        return AccessibilityPalette(
            background="#000000",
            foreground="#FFFFFF",
            field_background="#000000",
            button_background="#1A1A1A",
            active_background="#005A9C",
            selection_background="#005A9C",
            focus_color="#00B7FF",
        )
    return AccessibilityPalette(
        background="#F0F0F0",
        foreground="#111111",
        field_background="#FFFFFF",
        button_background="#E1E1E1",
        active_background="#D0D0D0",
        selection_background="#3B73AF",
        focus_color="#1A73E8",
    )


def _next_font_size(current_size: int, adjustment: int) -> int:
    """Bound an explicit user-selected text-size adjustment."""
    return max(_MINIMUM_FONT_SIZE, min(_MAXIMUM_FONT_SIZE, current_size + adjustment))


class KnowledgeRelationProcessor(Protocol):
    """Small mutable relation boundary used by the confirmation helper."""

    def preview_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Return a validated relation preview without changing graph state."""

    def apply_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Apply the runtime-validated relation after confirmation."""


class KnowledgeRelationRemovalProcessor(Protocol):
    """Small removal boundary used by the relation-removal confirmation helper."""

    def preview_knowledge_relation_removal(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Return a validated relation-removal preview without changing it."""

    def remove_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Remove the runtime-validated relation after confirmation."""


class SessionRenameProcessor(Protocol):
    """Small session-rename boundary used by the confirmation helper."""

    def preview_session_rename(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        """Return a validated session-rename preview without changing state."""

    def rename_session(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        """Run the transactional rename after confirmation."""


class TkinterDesktopWindow:
    """Render conversation, session selection, and semantic status locally."""

    def __init__(
        self,
        controller: DesktopController,
        root: tk.Tk | None = None,
    ) -> None:
        self._controller = controller
        self._root = root or tk.Tk()
        self._request_runner = DesktopRequestRunner()
        self._request_completion_handler: Callable[[BrainResponse], None] | None = None
        self._request_controls: list[ttk.Button] = []
        self._request_label: str | None = None
        self._request_started_at: float | None = None
        self._closing = False
        self._status = tk.StringVar(value="Ready")
        self._session_id = tk.StringVar()
        self._session_rename_target = tk.StringVar()
        self._session_search_query = tk.StringVar()
        self._recall_query = tk.StringVar()
        self._knowledge_query = tk.StringVar()
        self._research_question = tk.StringVar()
        self._research_run_id = tk.StringVar()
        self._research_candidate = tk.StringVar()
        self._research_url = tk.StringVar()
        self._research_source_document_id = tk.StringVar()
        self._research_comparison_document_ids = tk.StringVar()
        self._research_comparison_evidence_ids = tk.StringVar()
        self._research_comparison_assessment_ids = tk.StringVar()
        self._research_comparison_note_text = tk.StringVar()
        self._research_chunk_id = tk.StringVar()
        self._research_evidence_note = tk.StringVar()
        self._research_assessment_evidence_ids = tk.StringVar()
        self._research_assessment_text = tk.StringVar()
        self._research_assessment_supersedes_id = tk.StringVar()
        self._research_information_trust = tk.StringVar(
            value=ResearchInformationTrust.UNASSESSED.value
        )
        self._research_claim_evidence_ids = tk.StringVar()
        self._research_claim_text = tk.StringVar()
        self._research_claim_epistemic_state = tk.StringVar(
            value=ResearchEpistemicState.UNKNOWN.value
        )
        self._research_claim_confidence = tk.StringVar(
            value=ResearchClaimConfidence.UNASSESSED.value
        )
        self._research_claim_supersedes_id = tk.StringVar()
        self._research_target_status = tk.StringVar(value="completed")
        self._relation_source_id = tk.StringVar()
        self._relation_target_id = tk.StringVar()
        self._session_summaries: list[SessionSummary] = []
        self._research_candidates: tuple[ResearchSourceCandidate, ...] = ()
        self._research_candidate_run_id = ""
        self._research_candidate_discovery_id = ""
        self._research_markdown_export_preview: (
            ResearchRunMarkdownExportPreview | None
        ) = None
        self._font_size = _DEFAULT_FONT_SIZE
        self._font_size_label = tk.StringVar()
        self._high_contrast = tk.BooleanVar(value=False)
        self._style = ttk.Style(self._root)

        self._root.title("Hypatia")
        self._root.minsize(760, 520)
        self._build_layout()
        self._apply_accessibility_preferences()
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._root.after(_REQUEST_POLL_INTERVAL_MS, self._poll_requests)

    def run(self) -> None:
        """Enter the local desktop event loop."""
        self._root.mainloop()

    def _start_request(
        self,
        action: Callable[[], BrainResponse],
        on_success: Callable[[BrainResponse], None],
        label: str,
        *,
        cancellation_signal: CancellationSignal | None = None,
    ) -> None:
        """Start one long action without blocking or queueing the Tk event loop."""
        if self._closing:
            self._status.set("Hypatia is closing.")
            return
        start_result = self._request_runner.start(
            action,
            cancel_callback=(
                cancellation_signal.cancel if cancellation_signal is not None else None
            ),
        )
        if start_result == "started":
            self._request_completion_handler = on_success
            self._request_label = label
            self._request_started_at = monotonic()
            self._set_request_controls_busy(True)
            self._status.set(f"{label}: working (0s elapsed)")
            return
        if start_result == "busy":
            self._status.set("Hypatia is already processing a request.")
            return
        if start_result == "stopped":
            self._status.set("Hypatia is closing.")
            return
        self._status.set("Desktop request could not be started.")

    def _poll_requests(self) -> None:
        """Consume worker results and touch widgets only from the Tk event loop."""
        if self._closing:
            return
        for completion in self._request_runner.drain():
            handler = self._request_completion_handler
            self._request_completion_handler = None
            self._set_request_controls_busy(False)
            self._request_label = None
            self._request_started_at = None
            if completion.cancelled:
                self._status.set(
                    "Request cancelled after the active operation finished."
                )
                continue
            if completion.error is not None:
                if isinstance(completion.error, ValueError):
                    self._status.set(str(completion.error))
                else:
                    self._status.set("Desktop request failed.")
                continue
            if handler is None or not isinstance(completion.value, BrainResponse):
                self._status.set("Desktop request failed.")
                continue
            try:
                handler(completion.value)
            except Exception:
                self._status.set("Desktop request failed.")
        if self._request_runner.is_running():
            self._update_request_progress()
        if not self._closing:
            self._root.after(_REQUEST_POLL_INTERVAL_MS, self._poll_requests)

    def _update_request_progress(self) -> None:
        """Show elapsed time without inventing a provider completion percentage."""
        if self._request_runner.is_cancellation_requested():
            return
        if self._request_label is None or self._request_started_at is None:
            return
        elapsed_seconds = max(0, int(monotonic() - self._request_started_at))
        self._status.set(f"{self._request_label}: working ({elapsed_seconds}s elapsed)")

    def _cancel_request(self) -> None:
        """Request result cancellation without claiming to kill active I/O."""
        if self._closing:
            self._status.set("Hypatia is closing.")
            return
        result = self._request_runner.request_cancel()
        if result in {"requested", "already_requested"}:
            cancel_button = getattr(self, "_cancel_button", None)
            if cancel_button is not None:
                cancel_button.state(("disabled",))
            label = self._request_label or "request"
            self._status.set(
                f"{label}: cancellation requested; waiting for the active "
                "operation to finish"
            )
            return
        if result == "stopped":
            self._status.set("Hypatia is closing.")
            return
        self._status.set("No desktop request is currently running.")

    def _set_request_controls_busy(self, busy: bool) -> None:
        """Keep a second long request from being started by a clickable control."""
        state = ("disabled",) if busy else ("!disabled",)
        for button in self._request_controls:
            button.state(state)
        cancel_button = getattr(self, "_cancel_button", None)
        if cancel_button is not None:
            cancel_button.state(("!disabled",) if busy else ("disabled",))

    def _close(self) -> None:
        """Discard late worker results before destroying Tkinter widgets."""
        if self._closing:
            return
        self._closing = True
        self._request_completion_handler = None
        self._request_runner.stop()
        self._root.destroy()

    def _request_button(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
    ) -> ttk.Button:
        """Create one control disabled while a long desktop request is active."""
        button = ttk.Button(parent, text=text, command=command)
        self._request_controls.append(button)
        return button

    def _collect_request_controls(self, parent: tk.Misc) -> list[ttk.Button]:
        """Collect every command button so Brain is never called concurrently."""
        buttons: list[ttk.Button] = []
        for child in parent.winfo_children():
            if isinstance(child, ttk.Button):
                buttons.append(child)
            buttons.extend(self._collect_request_controls(child))
        return buttons

    def _build_layout(self) -> None:
        container = ttk.Frame(self._root, padding=12)
        container.grid(sticky="nsew")
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(7, weight=1)

        accessibility_frame = ttk.LabelFrame(
            container,
            text="Accessibility",
            padding=8,
        )
        accessibility_frame.grid(row=0, column=0, sticky="ew")
        ttk.Button(
            accessibility_frame,
            text="Text −",
            command=lambda: self._change_font_size(-1),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Label(accessibility_frame, textvariable=self._font_size_label).grid(
            row=0,
            column=1,
            padx=8,
        )
        ttk.Button(
            accessibility_frame,
            text="Text +",
            command=lambda: self._change_font_size(1),
        ).grid(row=0, column=2, sticky="ew")
        ttk.Checkbutton(
            accessibility_frame,
            text="High contrast",
            variable=self._high_contrast,
            command=self._apply_accessibility_preferences,
        ).grid(row=0, column=3, sticky="w", padx=(12, 0))

        session_frame = ttk.LabelFrame(container, text="Session", padding=8)
        session_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        session_frame.columnconfigure(0, weight=1)
        self._session_list = tk.Listbox(
            session_frame,
            height=4,
            exportselection=False,
        )
        self._session_list.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        self._session_list.bind("<<ListboxSelect>>", self._choose_session)
        ttk.Entry(session_frame, textvariable=self._session_id).grid(
            row=1, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            session_frame,
            text="Select session",
            command=self._select_session,
        ).grid(row=1, column=1, sticky="ew")
        ttk.Button(
            session_frame,
            text="Refresh sessions",
            command=self._refresh_sessions,
        ).grid(row=1, column=2, sticky="ew", padx=(8, 0))
        ttk.Button(
            session_frame,
            text="Semantic status",
            command=self._show_semantic_status,
        ).grid(row=1, column=3, sticky="ew", padx=(8, 0))
        ttk.Button(
            session_frame,
            text="Research content",
            command=self._show_research_content_status,
        ).grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(
            session_frame,
            text="Session details",
            command=self._show_session_details,
        ).grid(row=2, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(
            session_frame,
            text="Recent chats",
            command=self._show_session_recent,
        ).grid(row=2, column=2, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            session_frame,
            text="Session activity",
            command=self._show_session_activity,
        ).grid(row=2, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(session_frame, text="New session ID").grid(
            row=3,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(session_frame, textvariable=self._session_rename_target).grid(
            row=3,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            session_frame,
            text="Preview rename",
            command=self._preview_and_rename_session,
        ).grid(row=3, column=3, sticky="ew", pady=(8, 0))
        ttk.Button(
            session_frame,
            text="Preview delete",
            command=self._preview_and_delete_session,
        ).grid(row=4, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(session_frame, text="Search this session").grid(
            row=5, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(session_frame, textvariable=self._session_search_query).grid(
            row=5, column=1, columnspan=2, sticky="ew", padx=(8, 8), pady=(8, 0)
        )
        ttk.Button(
            session_frame,
            text="Search",
            command=self._show_session_search,
        ).grid(row=5, column=3, sticky="ew", pady=(8, 0))

        recall_frame = ttk.LabelFrame(container, text="Conversation recall", padding=8)
        recall_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        recall_frame.columnconfigure(0, weight=1)
        ttk.Entry(recall_frame, textvariable=self._recall_query).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            recall_frame,
            text="Recall",
            command=self._show_recall,
        ).grid(row=0, column=1, sticky="ew")
        self._request_button(
            recall_frame,
            text="Semantic recall",
            command=self._show_semantic_recall,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))

        knowledge_frame = ttk.LabelFrame(container, text="Local knowledge", padding=8)
        knowledge_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        knowledge_frame.columnconfigure(0, weight=1)
        ttk.Entry(knowledge_frame, textvariable=self._knowledge_query).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            knowledge_frame,
            text="Knowledge context",
            command=self._show_knowledge_context,
        ).grid(row=0, column=1, sticky="ew")
        ttk.Button(
            knowledge_frame,
            text="Knowledge graph",
            command=self._show_knowledge_graph,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))
        self._request_button(
            knowledge_frame,
            text="Ask sources",
            command=self._ask_knowledge,
        ).grid(row=0, column=3, sticky="ew", padx=(8, 0))
        ttk.Button(
            knowledge_frame,
            text="Loaded sources",
            command=self._show_knowledge_list,
        ).grid(row=0, column=4, sticky="ew", padx=(8, 0))
        ttk.Button(
            knowledge_frame,
            text="Load file",
            command=self._load_knowledge,
        ).grid(row=0, column=5, sticky="ew", padx=(8, 0))

        research_frame = ttk.LabelFrame(
            container,
            text="Internet research source",
            padding=8,
        )
        research_frame.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        research_frame.columnconfigure(1, weight=1)
        ttk.Label(research_frame, text="Question").grid(row=0, column=0, sticky="w")
        ttk.Entry(research_frame, textvariable=self._research_question).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(8, 8),
        )
        ttk.Button(
            research_frame,
            text="Start research",
            command=self._create_research_run,
        ).grid(row=0, column=2, sticky="ew")
        ttk.Button(
            research_frame,
            text="Research runs",
            command=self._show_research_runs,
        ).grid(row=0, column=3, sticky="ew", padx=(8, 0))
        ttk.Label(research_frame, text="Run ID").grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(research_frame, textvariable=self._research_run_id).grid(
            row=1,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        self._request_button(
            research_frame,
            text="Find sources",
            command=self._discover_research_sources,
        ).grid(row=1, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_frame, text="Candidates").grid(
            row=2,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        self._research_candidate_selector = ttk.Combobox(
            research_frame,
            textvariable=self._research_candidate,
            values=(),
            state="readonly",
        )
        self._research_candidate_selector.grid(
            row=2,
            column=1,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_frame,
            text="Use selected URL",
            command=self._use_selected_research_candidate,
        ).grid(row=2, column=2, sticky="ew", pady=(8, 0))
        self._request_button(
            research_frame,
            text="Preview & load",
            command=self._preview_and_accept_research_candidate,
        ).grid(row=2, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(research_frame, text="HTTPS URL").grid(
            row=3,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(research_frame, textvariable=self._research_url).grid(
            row=3,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        self._request_button(
            research_frame,
            text="Load source",
            command=self._load_research_source,
        ).grid(row=3, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_frame, text="Source document ID").grid(
            row=4,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_frame,
            textvariable=self._research_source_document_id,
        ).grid(
            row=4,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_frame,
            text="Preview assessment",
            command=self._preview_research_source_assessment,
        ).grid(row=4, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_frame, text="Comparison source IDs").grid(
            row=5,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_frame,
            textvariable=self._research_comparison_document_ids,
        ).grid(
            row=5,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_frame,
            text="Compare sources",
            command=self._preview_research_source_comparison,
        ).grid(row=5, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_frame, text="Comparison evidence IDs").grid(
            row=6,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_frame,
            textvariable=self._research_comparison_evidence_ids,
        ).grid(
            row=6,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(research_frame, text="Comparison assessment IDs").grid(
            row=7,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_frame,
            textvariable=self._research_comparison_assessment_ids,
        ).grid(
            row=7,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(research_frame, text="Comparison note").grid(
            row=8,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_frame,
            textvariable=self._research_comparison_note_text,
        ).grid(
            row=8,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_frame,
            text="Preview & save note",
            command=self._preview_and_record_research_source_comparison_note,
        ).grid(row=8, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_frame, text="Chunk ID").grid(
            row=9,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(research_frame, textvariable=self._research_chunk_id).grid(
            row=9,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_frame,
            text="View evidence",
            command=self._show_research_evidence,
        ).grid(row=9, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_frame, text="Evidence note").grid(
            row=10,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(research_frame, textvariable=self._research_evidence_note).grid(
            row=10,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_frame,
            text="Save evidence",
            command=self._record_research_evidence,
        ).grid(row=10, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_frame, text="Assessment evidence IDs").grid(
            row=11,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_frame,
            textvariable=self._research_assessment_evidence_ids,
        ).grid(
            row=11,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(research_frame, text="Assessment text").grid(
            row=12,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_frame,
            textvariable=self._research_assessment_text,
        ).grid(
            row=12,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_frame,
            text="Preview & save assessment",
            command=self._preview_and_record_research_source_assessment,
        ).grid(row=12, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_frame, text="Information trust (user-authored)").grid(
            row=13,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Combobox(
            research_frame,
            textvariable=self._research_information_trust,
            values=tuple(value.value for value in ResearchInformationTrust),
            state="readonly",
        ).grid(row=13, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(research_frame, text="Supersedes assessment ID (optional)").grid(
            row=14,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_frame,
            textvariable=self._research_assessment_supersedes_id,
        ).grid(
            row=14,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(research_frame, text="Claim evidence IDs (comma-separated)").grid(
            row=15,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_frame,
            textvariable=self._research_claim_evidence_ids,
        ).grid(
            row=15,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(research_frame, text="User-authored claim").grid(
            row=16,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_frame,
            textvariable=self._research_claim_text,
        ).grid(
            row=16,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(research_frame, text="Epistemic state / confidence").grid(
            row=17,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Combobox(
            research_frame,
            textvariable=self._research_claim_epistemic_state,
            values=tuple(value.value for value in ResearchEpistemicState),
            state="readonly",
        ).grid(row=17, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        ttk.Combobox(
            research_frame,
            textvariable=self._research_claim_confidence,
            values=tuple(value.value for value in ResearchClaimConfidence),
            state="readonly",
        ).grid(row=17, column=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            research_frame,
            text="View claims",
            command=self._preview_research_claims,
        ).grid(row=17, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(research_frame, text="Supersedes claim ID (optional)").grid(
            row=18,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_frame,
            textvariable=self._research_claim_supersedes_id,
        ).grid(row=18, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        ttk.Button(
            research_frame,
            text="Preview & save claim",
            command=self._preview_and_record_research_claim,
        ).grid(row=18, column=2, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(research_frame, text="Final status").grid(
            row=19,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Combobox(
            research_frame,
            textvariable=self._research_target_status,
            values=("completed", "failed", "cancelled"),
            state="readonly",
        ).grid(row=19, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        ttk.Button(
            research_frame,
            text="Preview status",
            command=self._preview_and_update_research_status,
        ).grid(row=19, column=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            research_frame,
            text="Export preview",
            command=self._preview_research_run_markdown_export,
        ).grid(row=19, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            research_frame,
            text="Verify export",
            command=self._verify_research_run_markdown_export,
        ).grid(row=20, column=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            research_frame,
            text="Save export",
            command=self._save_research_run_markdown_export,
        ).grid(row=20, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            research_frame,
            text="Evidence integrity",
            command=self._show_research_evidence_integrity,
        ).grid(row=20, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        relation_frame = ttk.LabelFrame(
            container,
            text="Local source relation",
            padding=8,
        )
        relation_frame.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        relation_frame.columnconfigure(1, weight=1)
        relation_frame.columnconfigure(3, weight=1)
        ttk.Label(relation_frame, text="Source ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(relation_frame, textvariable=self._relation_source_id).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(8, 12),
        )
        ttk.Label(relation_frame, text="Target ID").grid(row=0, column=2, sticky="w")
        ttk.Entry(relation_frame, textvariable=self._relation_target_id).grid(
            row=0,
            column=3,
            sticky="ew",
            padx=(8, 12),
        )
        ttk.Button(
            relation_frame,
            text="Preview and link",
            command=self._preview_and_link_knowledge_relation,
        ).grid(row=0, column=4, sticky="ew", padx=(0, 8))
        ttk.Button(
            relation_frame,
            text="Preview and remove",
            command=self._preview_and_remove_knowledge_relation,
        ).grid(row=0, column=5, sticky="ew")
        ttk.Button(
            relation_frame,
            text="Active links",
            command=self._show_knowledge_relation_list,
        ).grid(row=0, column=6, sticky="ew", padx=(8, 0))

        status_frame = ttk.Frame(container)
        status_frame.grid(row=6, column=0, sticky="ew", pady=(8, 4))
        status_frame.columnconfigure(0, weight=1)
        ttk.Label(status_frame, textvariable=self._status).grid(
            row=0, column=0, sticky="w"
        )
        self._cancel_button = ttk.Button(
            status_frame,
            text="Cancel request",
            command=self._cancel_request,
        )
        self._cancel_button.grid(row=0, column=1, sticky="e")
        self._cancel_button.state(("disabled",))

        self._transcript = scrolledtext.ScrolledText(
            container,
            wrap=tk.WORD,
            state=tk.DISABLED,
            height=18,
        )
        self._transcript.grid(row=7, column=0, sticky="nsew")

        composer_frame = ttk.LabelFrame(container, text="Message", padding=8)
        composer_frame.grid(row=8, column=0, sticky="ew", pady=(8, 0))
        composer_frame.columnconfigure(0, weight=1)
        self._composer = tk.Text(composer_frame, height=4, wrap=tk.WORD)
        self._composer.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._request_button(
            composer_frame,
            text="Send",
            command=self._send_message,
        ).grid(row=0, column=1, sticky="ns")
        self._composer.bind("<Control-Return>", self._send_with_keyboard)
        self._composer.focus_set()
        self._request_controls = [
            button
            for button in self._collect_request_controls(container)
            if button is not self._cancel_button
        ]

    def _change_font_size(self, adjustment: int) -> None:
        """Apply only a bounded, user-initiated text-size preference."""
        self._font_size = _next_font_size(self._font_size, adjustment)
        self._apply_accessibility_preferences()

    def _apply_accessibility_preferences(self) -> None:
        """Render explicit size and contrast choices without changing runtime state."""
        palette = _accessibility_palette(bool(self._high_contrast.get()))
        font = ("TkDefaultFont", self._font_size)
        self._font_size_label.set(f"Text size: {self._font_size} pt")
        self._root.configure(background=palette.background)
        self._style.configure(
            ".",
            background=palette.background,
            foreground=palette.foreground,
            font=font,
        )
        self._style.configure(
            "TFrame",
            background=palette.background,
        )
        self._style.configure(
            "TLabelframe",
            background=palette.background,
            foreground=palette.foreground,
        )
        self._style.configure(
            "TLabelframe.Label",
            background=palette.background,
            foreground=palette.foreground,
            font=font,
        )
        self._style.configure(
            "TButton",
            background=palette.button_background,
            foreground=palette.foreground,
            font=font,
            focuscolor=palette.focus_color,
        )
        self._style.map(
            "TButton",
            background=[
                ("active", palette.active_background),
                ("focus", palette.focus_color),
            ],
        )
        self._style.configure(
            "TCheckbutton",
            background=palette.background,
            foreground=palette.foreground,
            font=font,
            focuscolor=palette.focus_color,
        )
        self._style.configure(
            "TEntry",
            fieldbackground=palette.field_background,
            foreground=palette.foreground,
            font=font,
        )
        self._style.map(
            "TEntry",
            fieldbackground=[("focus", palette.field_background)],
        )
        self._session_list.configure(
            background=palette.field_background,
            foreground=palette.foreground,
            selectbackground=palette.selection_background,
            selectforeground=palette.foreground,
            font=font,
        )
        for widget in (self._transcript, self._composer):
            widget.configure(
                background=palette.field_background,
                foreground=palette.foreground,
                insertbackground=palette.foreground,
                selectbackground=palette.selection_background,
                selectforeground=palette.foreground,
                font=font,
            )

    def _send_with_keyboard(self, _event: tk.Event[tk.Text]) -> str:
        self._send_message()
        return "break"

    def _send_message(self) -> None:
        message = self._composer.get("1.0", "end-1c")
        self._start_request(
            lambda: self._controller.submit_message(message),
            lambda response: self._complete_message(message, response),
            "message",
        )

    def _complete_message(self, message: str, response: BrainResponse) -> None:
        """Render one completed message only from the Tkinter event thread."""
        self._append_exchange("You", message, response)
        if self._composer.get("1.0", "end-1c") == message:
            self._composer.delete("1.0", tk.END)

    def _select_session(self) -> None:
        try:
            response = self._controller.select_session(self._session_id.get())
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _show_semantic_status(self) -> None:
        self._append_response(self._controller.semantic_status())

    def _show_research_content_status(self) -> None:
        self._append_response(self._controller.research_content_status())

    def _show_research_evidence_integrity(self) -> None:
        self._append_response(self._controller.research_evidence_status())

    def _show_recall(self) -> None:
        self._show_recall_response(self._controller.recall)

    def _show_semantic_recall(self) -> None:
        query = self._recall_query.get()
        self._start_request(
            lambda: self._controller.semantic_recall(query),
            self._append_response,
            "semantic recall",
        )

    def _show_knowledge_context(self) -> None:
        self._show_knowledge_response(self._controller.knowledge_context)

    def _show_knowledge_graph(self) -> None:
        self._show_knowledge_response(self._controller.knowledge_graph)

    def _ask_knowledge(self) -> None:
        query = self._knowledge_query.get()
        self._start_request(
            lambda: self._controller.ask_knowledge(query),
            self._append_response,
            "knowledge answer",
        )

    def _show_knowledge_list(self) -> None:
        self._append_response(self._controller.list_knowledge())

    def _load_knowledge(self) -> None:
        """Ask the user to choose one supported local source before loading it."""
        path = filedialog.askopenfilename(
            parent=self._root,
            title="Load local knowledge source",
            filetypes=[
                ("Knowledge files", "*.md *.txt"),
                ("Markdown files", "*.md"),
                ("Text files", "*.txt"),
            ],
        )
        if not path:
            self._status.set("knowledge load: cancelled")
            return
        try:
            response = self._controller.load_knowledge(path)
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _load_research_source(self) -> None:
        """Fetch only the HTTPS source explicitly entered by the user."""
        url = self._research_url.get()
        run_id = self._research_run_id.get()
        cancellation_signal = CancellationSignal()
        self._start_request(
            lambda: self._controller.load_research_source(
                url,
                run_id,
                cancellation_token=cancellation_signal,
            ),
            self._complete_research_source_load,
            "research source load",
            cancellation_signal=cancellation_signal,
        )

    def _complete_research_source_load(self, response: BrainResponse) -> None:
        """Present an accepted network source only on the Tkinter event thread."""
        self._append_response(response)
        self._capture_accepted_research_source(response)

    def _create_research_run(self) -> None:
        """Create a persistent run and select its returned identifier."""
        try:
            response = self._controller.create_research_run(
                self._research_question.get()
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)
        if response.success and response.research_runs:
            self._clear_research_candidates()
            self._research_run_id.set(response.research_runs[0].run_id)

    def _show_research_runs(self) -> None:
        """Render the current persisted run catalog without network access."""
        self._append_response(self._controller.list_research_runs())

    def _preview_research_run_markdown_export(self) -> None:
        """Render one terminal run as bounded Markdown without writing a file."""
        self._research_markdown_export_preview = None
        try:
            response = self._controller.preview_research_run_markdown_export(
                self._research_run_id.get()
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)
        preview = response.research_run_markdown_export_preview
        if (
            response.success
            and preview is not None
            and preview.run_id == self._research_run_id.get().strip()
        ):
            self._research_markdown_export_preview = preview

    def _save_research_run_markdown_export(self) -> None:
        """Choose, confirm, and save only the exact preview currently displayed."""
        preview = self._research_markdown_export_preview
        if preview is None or preview.run_id != self._research_run_id.get().strip():
            self._status.set("Preview the selected terminal research run first.")
            return
        path = filedialog.asksaveasfilename(
            parent=self._root,
            title="Save research Markdown export as a new file",
            initialfile=preview.suggested_filename,
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md")],
        )
        if not path:
            self._status.set("research export save: cancelled")
            return
        if not messagebox.askyesno(
            "Save research export?",
            (
                f"Create this new file?\n\n{path}\n\n"
                f"Content SHA-256: {preview.content_sha256}\n\n"
                "Hypatia will not replace an existing file."
            ),
            parent=self._root,
        ):
            self._status.set("research export save: not saved")
            return
        try:
            response = self._controller.save_research_run_markdown_export(
                preview,
                path,
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _verify_research_run_markdown_export(self) -> None:
        """Select one existing Markdown file for read-only integrity comparison."""
        run_id = self._research_run_id.get().strip()
        if not run_id:
            self._status.set("A research run ID cannot be empty.")
            return
        path = filedialog.askopenfilename(
            parent=self._root,
            title="Verify existing research Markdown export",
            filetypes=[("Markdown files", "*.md")],
        )
        if not path:
            self._status.set("research export verification: cancelled")
            return
        try:
            response = self._controller.verify_research_run_markdown_export(
                run_id,
                path,
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _discover_research_sources(self) -> None:
        """Discover and display metadata candidates for the selected run."""
        run_id = self._research_run_id.get()
        cancellation_signal = CancellationSignal()
        self._start_request(
            lambda: self._controller.discover_research_sources(
                run_id,
                cancellation_token=cancellation_signal,
            ),
            self._complete_research_source_discovery,
            "research source discovery",
            cancellation_signal=cancellation_signal,
        )

    def _complete_research_source_discovery(self, response: BrainResponse) -> None:
        """Present discovered candidates only on the Tkinter event thread."""
        self._append_response(response)
        self._render_research_candidates(response)

    def _render_research_candidates(self, response: BrainResponse) -> None:
        """Replace stale candidate choices with the latest successful discovery."""
        self._clear_research_candidates()
        if not response.success:
            return
        selected_run_id = self._research_run_id.get().strip()
        selected_runs = [
            run for run in response.research_runs if run.run_id == selected_run_id
        ]
        if not selected_runs or not selected_runs[0].discoveries:
            return
        self._research_candidate_run_id = selected_run_id
        discovery = selected_runs[0].discoveries[-1]
        self._research_candidate_discovery_id = discovery.discovery_id
        self._research_candidates = discovery.candidates
        labels = tuple(
            f"{index}. {candidate.title} — {candidate.url}"
            for index, candidate in enumerate(self._research_candidates, start=1)
        )
        self._research_candidate_selector.configure(values=labels)
        if labels:
            self._research_candidate_selector.current(0)

    def _clear_research_candidates(self) -> None:
        self._research_candidates = ()
        self._research_candidate_run_id = ""
        self._research_candidate_discovery_id = ""
        self._research_candidate.set("")
        self._research_candidate_selector.configure(values=())

    def _use_selected_research_candidate(self) -> None:
        """Copy one explicitly selected candidate URL without fetching it."""
        selected_index = self._research_candidate_selector.current()
        if (
            self._research_run_id.get().strip() != self._research_candidate_run_id
            or not 0 <= selected_index < len(self._research_candidates)
        ):
            self._status.set("Select a discovered source candidate first.")
            return
        self._research_url.set(self._research_candidates[selected_index].url)
        self._status.set("research candidate: URL copied; source not loaded")

    def _selected_research_candidate(
        self,
    ) -> tuple[str, str, ResearchSourceCandidate] | None:
        selected_index = self._research_candidate_selector.current()
        run_id = self._research_run_id.get().strip()
        if (
            run_id != self._research_candidate_run_id
            or not self._research_candidate_discovery_id
            or not 0 <= selected_index < len(self._research_candidates)
        ):
            return None
        return (
            run_id,
            self._research_candidate_discovery_id,
            self._research_candidates[selected_index],
        )

    def _preview_and_accept_research_candidate(self) -> None:
        """Preview, confirm, and separately accept one discovered candidate."""
        selected = self._selected_research_candidate()
        if selected is None:
            self._status.set("Select a discovered source candidate first.")
            return
        run_id, discovery_id, candidate = selected
        try:
            preview_response = (
                self._controller.preview_research_source_candidate_acceptance(
                    run_id,
                    discovery_id,
                    candidate.url,
                )
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(preview_response)
        preview = preview_response.research_source_candidate_acceptance_preview
        if not preview_response.success or preview is None or not preview.allowed:
            return
        if not messagebox.askyesno(
            "Load research source?",
            (
                f"{preview_response.message}\n\n"
                "This fetches the selected HTTPS source, indexes it locally, "
                "and attaches it to the research run. Continue?"
            ),
            parent=self._root,
        ):
            self._status.set("research candidate: not loaded")
            return
        cancellation_signal = CancellationSignal()
        self._start_request(
            lambda: self._controller.accept_research_source_candidate(
                run_id,
                discovery_id,
                candidate.url,
                cancellation_token=cancellation_signal,
            ),
            self._complete_research_source_load,
            "research candidate load",
            cancellation_signal=cancellation_signal,
        )

    def _capture_accepted_research_source(self, response: BrainResponse) -> None:
        """Select only a source that the returned run confirms as accepted."""
        if not response.success or not response.knowledge_documents:
            return
        document_id = response.knowledge_documents[0].document_id
        if not any(
            source.document_id == document_id
            for run in response.research_runs
            for source in run.sources
        ):
            return
        self._research_source_document_id.set(document_id)

    def _preview_research_source_assessment(self) -> None:
        """Render persisted source context without network, LLM, or mutation."""
        try:
            response = self._controller.preview_research_source_assessment(
                self._research_run_id.get(),
                self._research_source_document_id.get(),
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _preview_research_source_comparison(self) -> None:
        """Render explicitly selected accepted sources side by side, read-only."""
        try:
            response = self._controller.preview_research_source_comparison(
                self._research_run_id.get(),
                self._research_comparison_document_ids.get(),
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _preview_and_record_research_source_comparison_note(self) -> None:
        """Preview, confirm, and revalidate one authored comparison note."""
        values = (
            self._research_run_id.get(),
            self._research_comparison_document_ids.get(),
            self._research_comparison_evidence_ids.get(),
            self._research_comparison_assessment_ids.get(),
            self._research_comparison_note_text.get(),
        )
        try:
            preview_response = (
                self._controller.preview_research_source_comparison_note_write(*values)
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(preview_response)
        preview = preview_response.research_source_comparison_note_write_preview
        if not preview_response.success or preview is None or not preview.allowed:
            return
        if not messagebox.askyesno(
            "Save research comparison note?",
            (
                f"{preview_response.message}\n\n"
                "This appends your text and the exact listed source, evidence, "
                "and current assessment IDs to the research audit record. Continue?"
            ),
            parent=self._root,
        ):
            self._status.set("research comparison note: not saved")
            return
        response = self._controller.record_research_source_comparison_note(*values)
        self._append_response(response)

    def _preview_and_record_research_source_assessment(self) -> None:
        """Preview, confirm, and revalidate one user-authored assessment."""
        values = (
            self._research_run_id.get(),
            self._research_source_document_id.get(),
            self._research_assessment_evidence_ids.get(),
            self._research_assessment_text.get(),
            self._research_assessment_supersedes_id.get(),
            self._research_information_trust.get(),
        )
        try:
            preview_response = (
                self._controller.preview_research_source_assessment_write(*values)
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(preview_response)
        preview = preview_response.research_source_assessment_write_preview
        if not preview_response.success or preview is None or not preview.allowed:
            return
        if not messagebox.askyesno(
            "Save research source assessment?",
            (
                f"{preview_response.message}\n\n"
                "This appends your text, the listed evidence IDs, and any exact "
                "supersession link plus your information-trust label to the "
                "research audit record. External source instruction authority "
                "remains none. Continue?"
            ),
            parent=self._root,
        ):
            self._status.set("research assessment: not saved")
            return
        response = self._controller.record_research_source_assessment(*values)
        self._append_response(response)

    def _preview_research_claims(self) -> None:
        """Show persisted claim history for the explicitly selected run."""
        try:
            response = self._controller.preview_research_claims(
                self._research_run_id.get()
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _preview_and_record_research_claim(self) -> None:
        """Preview, confirm, and revalidate one evidence-linked claim."""
        values = (
            self._research_run_id.get(),
            self._research_claim_evidence_ids.get(),
            self._research_claim_text.get(),
            self._research_claim_epistemic_state.get(),
            self._research_claim_confidence.get(),
            self._research_claim_supersedes_id.get(),
        )
        try:
            preview_response = self._controller.preview_research_claim_write(*values)
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(preview_response)
        preview = preview_response.research_claim_write_preview
        if not preview_response.success or preview is None or not preview.allowed:
            return
        if not messagebox.askyesno(
            "Save evidence-linked research claim?",
            (
                f"{preview_response.message}\n\n"
                "This appends your claim, epistemic state, categorical confidence, "
                "and exact evidence/source provenance to the research audit record. "
                "Hypatia does not determine truth automatically. Continue?"
            ),
            parent=self._root,
        ):
            self._status.set("research claim: not saved")
            return
        response = self._controller.record_research_claim(*values)
        self._append_response(response)

    def _record_research_evidence(self) -> None:
        """Persist one user-selected indexed paragraph under the current run."""
        try:
            response = self._controller.record_research_evidence(
                self._research_run_id.get(),
                self._research_chunk_id.get(),
                self._research_evidence_note.get(),
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _show_research_evidence(self) -> None:
        """Display persisted evidence for only the explicitly selected run."""
        try:
            response = self._controller.list_research_evidence(
                self._research_run_id.get()
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _preview_and_update_research_status(self) -> None:
        """Preview and separately confirm one irreversible terminal status."""
        run_id = self._research_run_id.get()
        target_status = self._research_target_status.get()
        try:
            preview_response = self._controller.preview_research_run_status(
                run_id,
                target_status,
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(preview_response)
        preview = preview_response.research_run_status_transition_preview
        if not preview_response.success or preview is None or not preview.allowed:
            return
        if not messagebox.askyesno(
            "Close research run?",
            (
                f"{preview_response.message}\n\n"
                "This closes the run and prevents further source, evidence, "
                "or failure changes. Continue?"
            ),
            parent=self._root,
        ):
            self._status.set("research status: not updated")
            return
        response = self._controller.update_research_run_status(
            run_id,
            target_status,
        )
        self._append_response(response)

    def _preview_and_link_knowledge_relation(self) -> None:
        try:
            preview, application = _preview_and_confirm_knowledge_relation(
                self._controller,
                self._relation_source_id.get(),
                self._relation_target_id.get(),
                self._confirm_knowledge_relation,
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(preview)
        if application is None:
            if preview.success:
                self._status.set("knowledge relation: not applied")
            return
        self._append_response(application)

    def _preview_and_remove_knowledge_relation(self) -> None:
        try:
            preview, removal = _preview_and_confirm_knowledge_relation_removal(
                self._controller,
                self._relation_source_id.get(),
                self._relation_target_id.get(),
                self._confirm_knowledge_relation_removal,
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(preview)
        if removal is None:
            if preview.success:
                self._status.set("knowledge relation: not removed")
            return
        self._append_response(removal)

    def _show_knowledge_relation_list(self) -> None:
        self._append_response(self._controller.list_knowledge_relations())

    def _confirm_knowledge_relation(self, preview: BrainResponse) -> bool:
        """Display only the existing runtime preview before mutation."""
        return messagebox.askyesno(
            "Create local relation?",
            f"{preview.message}\n\nCreate this local relation?",
            parent=self._root,
        )

    def _confirm_knowledge_relation_removal(self, preview: BrainResponse) -> bool:
        """Display only the existing runtime removal preview before mutation."""
        return messagebox.askyesno(
            "Remove local relation?",
            f"{preview.message}\n\nRemove this local relation?",
            parent=self._root,
        )

    def _show_knowledge_response(
        self,
        action: Callable[[str], BrainResponse],
    ) -> None:
        try:
            response = action(self._knowledge_query.get())
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _show_session_details(self) -> None:
        self._show_selected_session_response(self._controller.session_details)

    def _show_session_recent(self) -> None:
        self._show_selected_session_response(self._controller.session_recent)

    def _show_session_activity(self) -> None:
        self._show_selected_session_response(self._controller.session_activity)

    def _show_session_search(self) -> None:
        try:
            response = self._controller.session_search(
                self._session_id.get(),
                self._session_search_query.get(),
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _preview_and_rename_session(self) -> None:
        source_id = self._session_id.get()
        target_id = self._session_rename_target.get()
        try:
            preview, renamed = _preview_and_confirm_session_rename(
                self._controller,
                source_id,
                target_id,
                self._confirm_session_rename,
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(preview)
        if renamed is None:
            if preview.success:
                self._status.set("session rename: not applied")
            return
        self._append_response(renamed)
        if renamed.success:
            self._session_id.set(target_id.strip())
            self._refresh_sessions()

    def _preview_and_delete_session(self) -> None:
        try:
            preview = self._controller.preview_session_delete(self._session_id.get())
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(preview)
        if not preview.success or preview.session_delete_allowed is not True:
            return
        if not messagebox.askyesno(
            "Delete session?",
            f"{preview.message}\n\nDelete this session permanently?",
            parent=self._root,
        ):
            self._status.set("session delete: not applied")
            return
        response = self._controller.delete_session(self._session_id.get())
        self._append_response(response)
        if response.success:
            self._session_id.set("")
            self._refresh_sessions()

    def _confirm_session_rename(self, preview: BrainResponse) -> bool:
        """Show only the existing runtime rename preview before mutation."""
        return messagebox.askyesno(
            "Rename session?",
            f"{preview.message}\n\nRename this session?",
            parent=self._root,
        )

    def _refresh_sessions(self) -> None:
        response = self._controller.session_overview()
        self._render_session_summaries(response)
        self._append_response(response)

    def _show_selected_session_response(
        self,
        action: Callable[[str], BrainResponse],
    ) -> None:
        try:
            response = action(self._session_id.get())
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _show_recall_response(
        self,
        action: Callable[[str], BrainResponse],
    ) -> None:
        try:
            response = action(self._recall_query.get())
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _choose_session(self, _event: tk.Event[tk.Listbox]) -> None:
        selected_indices = self._session_list.curselection()
        if not selected_indices:
            return
        self._session_id.set(self._session_summaries[selected_indices[0]].session_id)

    def _render_session_summaries(self, response: BrainResponse) -> None:
        """Show only current successful Brain data, never a stale local copy."""
        self._session_list.delete(0, tk.END)
        self._session_summaries = []
        if not response.success:
            return
        self._session_summaries = response.session_summaries
        for summary in self._session_summaries:
            active_label = " (active)" if summary.active else ""
            conversations = summary.conversation_count
            label = (
                f"{summary.session_id}{active_label} — {conversations} conversations"
            )
            self._session_list.insert(tk.END, label)

    def _append_exchange(
        self,
        speaker: str,
        message: str,
        response: BrainResponse,
    ) -> None:
        self._append_to_transcript(f"{speaker}: {message}\n")
        self._append_response(response)

    def _append_response(self, response: BrainResponse) -> None:
        outcome = "completed" if response.success else "failed"
        self._status.set(f"{response.intent}: {outcome}")
        citation_text = _format_citations(response.knowledge_citations)
        citations = f"\nSources:\n{citation_text}" if citation_text else ""
        self._append_to_transcript(f"Hypatia: {response.message}{citations}\n")

    def _append_to_transcript(self, value: str) -> None:
        self._transcript.configure(state=tk.NORMAL)
        self._transcript.insert(tk.END, value)
        self._transcript.see(tk.END)
        self._transcript.configure(state=tk.DISABLED)


def _format_citations(citations: list[KnowledgeCitation]) -> str:
    """Render existing source records in response order without new lookups."""
    return "\n".join(
        (
            f"{index}. {citation.document_title} — "
            f"{citation.source or 'local source unavailable'} "
            f"(paragraph {citation.chunk_index + 1}; {citation.chunk_id})"
        )
        for index, citation in enumerate(citations, start=1)
    )


def _preview_and_confirm_knowledge_relation(
    controller: KnowledgeRelationProcessor,
    source_document_id: str,
    target_document_id: str,
    confirm: Callable[[BrainResponse], bool],
) -> tuple[BrainResponse, BrainResponse | None]:
    """Preview first; invoke the mutating command only after explicit approval."""
    preview = controller.preview_knowledge_relation(
        source_document_id,
        target_document_id,
    )
    if not preview.success or not confirm(preview):
        return preview, None
    return preview, controller.apply_knowledge_relation(
        source_document_id,
        target_document_id,
    )


def _preview_and_confirm_knowledge_relation_removal(
    controller: KnowledgeRelationRemovalProcessor,
    source_document_id: str,
    target_document_id: str,
    confirm: Callable[[BrainResponse], bool],
) -> tuple[BrainResponse, BrainResponse | None]:
    """Preview removal first; mutate only after explicit approval."""
    preview = controller.preview_knowledge_relation_removal(
        source_document_id,
        target_document_id,
    )
    if not preview.success or not confirm(preview):
        return preview, None
    return preview, controller.remove_knowledge_relation(
        source_document_id,
        target_document_id,
    )


def _preview_and_confirm_session_rename(
    controller: SessionRenameProcessor,
    source_session_id: str,
    target_session_id: str,
    confirm: Callable[[BrainResponse], bool],
) -> tuple[BrainResponse, BrainResponse | None]:
    """Preview a session rename first; execute only after explicit approval."""
    preview = controller.preview_session_rename(source_session_id, target_session_id)
    if not preview.success or not confirm(preview):
        return preview, None
    return preview, controller.rename_session(source_session_id, target_session_id)
