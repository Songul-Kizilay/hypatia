"""Tkinter presentation for the deliberately narrow first desktop shell."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
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
from research.ResearchClaimContradictionCandidate import (
    ResearchClaimContradictionCandidate,
)
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimRecord import (
    MAX_RESEARCH_CLAIM_EVIDENCE,
    ResearchClaimRecord,
)
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunMarkdownExportPreview import (
    ResearchRunMarkdownExportPreview,
)
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceComparisonNoteRecord import (
    MAX_COMPARISON_NOTE_ASSESSMENTS,
    MAX_COMPARISON_NOTE_EVIDENCE,
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceRecord import ResearchSourceRecord

_DEFAULT_FONT_SIZE = 12
_MINIMUM_FONT_SIZE = 10
_MAXIMUM_FONT_SIZE = 20
_REQUEST_POLL_INTERVAL_MS = 50
_MAX_RESEARCH_RUN_FILTER_LENGTH = 200
_RESEARCH_WORKFLOW_TAB_TITLES = (
    "1  Overview",
    "2  Sources & evidence",
    "3  Authored analysis",
    "4  Review & export",
)
_RESEARCH_ANALYSIS_TAB_TITLES = (
    "Saved records",
    "Comparison",
    "Assessment",
    "Claims & contradictions",
)


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
    border_color: str
    muted_foreground: str


class DesktopTheme(StrEnum):
    """User-selectable presentation themes with no runtime side effects."""

    EYE_COMFORT = "eye_comfort"
    LIGHT = "light"
    HIGH_CONTRAST = "high_contrast"


class ResearchRunSort(StrEnum):
    """User-facing deterministic orders for the loaded run presentation."""

    UPDATED_NEWEST = "Updated — newest first"
    UPDATED_OLDEST = "Updated — oldest first"
    CREATED_NEWEST = "Created — newest first"
    QUESTION = "Question — A to Z"


class ResearchRunStatusFacet(StrEnum):
    """User-facing local status views for the loaded run catalog."""

    ALL = "All statuses"
    COLLECTING = "Collecting"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class ResearchSourceCoverageFacet(StrEnum):
    """User-facing local coverage views for accepted research sources."""

    ALL = "All sources"
    WITHOUT_EVIDENCE = "Without evidence"


def _accessibility_palette(
    theme: DesktopTheme | str = DesktopTheme.EYE_COMFORT,
) -> AccessibilityPalette:
    """Return a complete palette independent of platform-native ttk colors."""
    try:
        normalized_theme = DesktopTheme(theme)
    except ValueError:
        normalized_theme = DesktopTheme.EYE_COMFORT
    if normalized_theme is DesktopTheme.HIGH_CONTRAST:
        return AccessibilityPalette(
            background="#000000",
            foreground="#FFFFFF",
            field_background="#000000",
            button_background="#1A1A1A",
            active_background="#005A9C",
            selection_background="#005A9C",
            focus_color="#00B7FF",
            border_color="#FFFFFF",
            muted_foreground="#D6D6D6",
        )
    if normalized_theme is DesktopTheme.LIGHT:
        return AccessibilityPalette(
            background="#F0F2F5",
            foreground="#20242A",
            field_background="#FFFFFF",
            button_background="#E2E7EC",
            active_background="#D2DAE2",
            selection_background="#3B73AF",
            focus_color="#1A73E8",
            border_color="#B8C1CB",
            muted_foreground="#68727D",
        )
    return AccessibilityPalette(
        background="#20242B",
        foreground="#E4E9EF",
        field_background="#2B313A",
        button_background="#343C46",
        active_background="#44515F",
        selection_background="#365F83",
        focus_color="#78A9D4",
        border_color="#4A5562",
        muted_foreground="#98A3AF",
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
        self._research_run_choice = tk.StringVar()
        self._research_run_summary = tk.StringVar(
            value="Select or create a research run."
        )
        self._research_run_context = tk.StringVar(
            value="No research run selected. Return to Overview to choose one."
        )
        self._research_run_progress = tk.StringVar(
            value="Progress unavailable until a research run is selected."
        )
        self._research_run_filter = tk.StringVar()
        self._research_run_filter_summary = tk.StringVar(
            value="All loaded research runs are shown."
        )
        self._research_run_status_filter = tk.StringVar(
            value=ResearchRunStatusFacet.ALL.value
        )
        self._research_run_catalog_summary = tk.StringVar(
            value=(
                "Loaded catalog: All 0 · Collecting 0 · Completed 0 · "
                "Failed 0 · Cancelled 0"
            )
        )
        self._research_run_sort = tk.StringVar(
            value=ResearchRunSort.UPDATED_NEWEST.value
        )
        self._research_run_sort_summary = tk.StringVar(
            value=f"Current sort: {ResearchRunSort.UPDATED_NEWEST.value}."
        )
        self._research_workflow_snapshot = tk.StringVar(
            value="Select or create a research run to see stage records."
        )
        self._research_evidence_coverage = tk.StringVar(
            value=("Evidence coverage unavailable until a research run is selected.")
        )
        self._research_assessment_coverage = tk.StringVar(
            value=("Assessment coverage unavailable until a research run is selected.")
        )
        self._research_run_metadata = tk.StringVar(
            value="Run metadata unavailable until a research run is selected."
        )
        self._research_source_choice = tk.StringVar()
        self._research_source_coverage_filter = tk.StringVar(
            value=ResearchSourceCoverageFacet.ALL.value
        )
        self._research_source_coverage_summary = tk.StringVar(
            value="No accepted sources are available."
        )
        self._research_evidence_choice = tk.StringVar()
        self._research_assessment_choice = tk.StringVar()
        self._research_claim_choice = tk.StringVar()
        self._research_persisted_contradiction_choice = tk.StringVar()
        self._research_persisted_comparison_note_choice = tk.StringVar()
        self._research_persisted_comparison_note_references = tk.StringVar()
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
        self._research_claim_contradiction_ids = tk.StringVar()
        self._research_claim_contradiction_note = tk.StringVar()
        self._research_claim_contradiction_proposal = tk.StringVar()
        self._research_target_status = tk.StringVar(value="completed")
        self._relation_source_id = tk.StringVar()
        self._relation_target_id = tk.StringVar()
        self._session_summaries: list[SessionSummary] = []
        self._research_candidates: tuple[ResearchSourceCandidate, ...] = ()
        self._research_runs: tuple[ResearchRun, ...] = ()
        self._visible_research_runs: tuple[ResearchRun, ...] = ()
        self._research_source_catalog: tuple[ResearchSourceRecord, ...] = ()
        self._research_sources: tuple[ResearchSourceRecord, ...] = ()
        self._research_source_run_id = ""
        self._active_research_source_document_id = ""
        self._research_evidence_records: tuple[ResearchEvidenceRecord, ...] = ()
        self._research_evidence_run_id = ""
        self._research_evidence_source_document_id = ""
        self._research_assessment_records: tuple[
            ResearchSourceAssessmentRecord, ...
        ] = ()
        self._research_current_assessment_ids: frozenset[str] = frozenset()
        self._research_assessment_run_id = ""
        self._research_assessment_source_document_id = ""
        self._research_claim_records: tuple[ResearchClaimRecord, ...] = ()
        self._research_current_claim_ids: frozenset[str] = frozenset()
        self._research_claim_run_id = ""
        self._research_persisted_contradiction_records: tuple[
            ResearchClaimContradictionRecord, ...
        ] = ()
        self._research_persisted_contradiction_run_id = ""
        self._research_persisted_comparison_note_records: tuple[
            ResearchSourceComparisonNoteRecord, ...
        ] = ()
        self._research_persisted_comparison_note_run_id = ""
        self._research_candidate_run_id = ""
        self._research_candidate_discovery_id = ""
        self._research_claim_contradiction_proposal_run_id = ""
        self._research_claim_contradiction_proposals: tuple[
            ResearchClaimContradictionCandidate, ...
        ] = ()
        self._research_markdown_export_preview: (
            ResearchRunMarkdownExportPreview | None
        ) = None
        self._font_size = _DEFAULT_FONT_SIZE
        self._font_size_label = tk.StringVar()
        self._theme_mode = tk.StringVar(value=DesktopTheme.EYE_COMFORT.value)
        self._style = ttk.Style(self._root)
        if "clam" in self._style.theme_names():
            self._style.theme_use("clam")

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
        container = ttk.Frame(self._root, padding=8)
        container.grid(sticky="nsew")
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self._workspace_tabs = ttk.Notebook(container)
        self._workspace_tabs.grid(row=0, column=0, sticky="nsew")
        chat_tab = ttk.Frame(self._workspace_tabs, padding=10)
        knowledge_tab = ttk.Frame(self._workspace_tabs, padding=10)
        research_tab = ttk.Frame(self._workspace_tabs, padding=10)
        appearance_tab = ttk.Frame(self._workspace_tabs, padding=10)
        self._workspace_tabs.add(chat_tab, text="Chat")
        self._workspace_tabs.add(knowledge_tab, text="Knowledge")
        self._workspace_tabs.add(research_tab, text="Research")
        self._workspace_tabs.add(appearance_tab, text="Appearance")
        for tab in (chat_tab, knowledge_tab, research_tab, appearance_tab):
            tab.columnconfigure(0, weight=1)
        chat_tab.rowconfigure(3, weight=1)

        accessibility_frame = ttk.LabelFrame(
            appearance_tab,
            text="Comfort and accessibility",
            padding=12,
        )
        accessibility_frame.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            accessibility_frame,
            text=(
                "Eye comfort uses soft charcoal colors for everyday use. "
                "High contrast remains available for maximum separation."
            ),
            wraplength=720,
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 12))
        ttk.Button(
            accessibility_frame,
            text="Text −",
            command=lambda: self._change_font_size(-1),
        ).grid(row=1, column=0, sticky="ew")
        ttk.Label(accessibility_frame, textvariable=self._font_size_label).grid(
            row=1,
            column=1,
            padx=8,
        )
        ttk.Button(
            accessibility_frame,
            text="Text +",
            command=lambda: self._change_font_size(1),
        ).grid(row=1, column=2, sticky="ew")
        ttk.Radiobutton(
            accessibility_frame,
            text="Eye comfort",
            variable=self._theme_mode,
            value=DesktopTheme.EYE_COMFORT.value,
            command=self._apply_accessibility_preferences,
        ).grid(row=1, column=3, sticky="w", padx=(20, 0))
        ttk.Radiobutton(
            accessibility_frame,
            text="Light",
            variable=self._theme_mode,
            value=DesktopTheme.LIGHT.value,
            command=self._apply_accessibility_preferences,
        ).grid(row=1, column=4, sticky="w", padx=(12, 0))
        ttk.Radiobutton(
            accessibility_frame,
            text="High contrast",
            variable=self._theme_mode,
            value=DesktopTheme.HIGH_CONTRAST.value,
            command=self._apply_accessibility_preferences,
        ).grid(row=1, column=5, sticky="w", padx=(12, 0))

        session_frame = ttk.LabelFrame(chat_tab, text="Sessions", padding=8)
        session_frame.grid(row=0, column=0, sticky="ew")
        session_frame.columnconfigure(1, weight=1)
        self._session_list = tk.Listbox(
            session_frame,
            height=3,
            exportselection=False,
        )
        self._session_list.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        self._session_list.bind("<<ListboxSelect>>", self._choose_session)
        self._session_list.insert(
            tk.END,
            "No sessions shown yet — choose Refresh.",
        )
        ttk.Label(session_frame, text="Session ID").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 8),
        )
        ttk.Entry(session_frame, textvariable=self._session_id).grid(
            row=1, column=1, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            session_frame,
            text="Open session",
            command=self._select_session,
        ).grid(row=1, column=2, sticky="ew")
        ttk.Button(
            session_frame,
            text="Refresh",
            command=self._refresh_sessions,
        ).grid(row=1, column=3, sticky="ew", padx=(8, 0))
        session_actions = ttk.Frame(session_frame)
        session_actions.grid(
            row=2,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(8, 0),
        )
        for column in range(4):
            session_actions.columnconfigure(column, weight=1)
        ttk.Button(
            session_actions,
            text="Details",
            command=self._show_session_details,
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            session_actions,
            text="Recent messages",
            command=self._show_session_recent,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Button(
            session_actions,
            text="Activity",
            command=self._show_session_activity,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))
        ttk.Button(
            session_actions,
            text="Memory status",
            command=self._show_semantic_status,
        ).grid(row=0, column=3, sticky="ew", padx=(8, 0))
        ttk.Label(session_frame, text="Rename selected to").grid(
            row=3,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(session_frame, textvariable=self._session_rename_target).grid(
            row=3,
            column=1,
            sticky="ew",
            padx=(0, 8),
            pady=(8, 0),
        )
        ttk.Button(
            session_frame,
            text="Rename…",
            command=self._preview_and_rename_session,
        ).grid(row=3, column=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            session_frame,
            text="Delete…",
            command=self._preview_and_delete_session,
        ).grid(row=3, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(session_frame, text="Search selected session").grid(
            row=4, column=0, sticky="w", padx=(0, 8), pady=(8, 0)
        )
        ttk.Entry(session_frame, textvariable=self._session_search_query).grid(
            row=4, column=1, columnspan=2, sticky="ew", padx=(0, 8), pady=(8, 0)
        )
        ttk.Button(
            session_frame,
            text="Search",
            command=self._show_session_search,
        ).grid(row=4, column=3, sticky="ew", pady=(8, 0))

        recall_frame = ttk.LabelFrame(chat_tab, text="Search past chats", padding=8)
        recall_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        recall_frame.columnconfigure(0, weight=1)
        ttk.Entry(recall_frame, textvariable=self._recall_query).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            recall_frame,
            text="Keyword search",
            command=self._show_recall,
        ).grid(row=0, column=1, sticky="ew")
        self._request_button(
            recall_frame,
            text="Meaning search",
            command=self._show_semantic_recall,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))

        knowledge_frame = ttk.LabelFrame(
            knowledge_tab,
            text="Local knowledge",
            padding=10,
        )
        knowledge_frame.grid(row=0, column=0, sticky="ew")
        knowledge_frame.columnconfigure(0, weight=1)
        ttk.Label(
            knowledge_frame,
            text=(
                "Search your local notes, ask a cited question, or add a Markdown "
                "or text file. Nothing is sent automatically."
            ),
            style="Hint.TLabel",
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))
        ttk.Entry(knowledge_frame, textvariable=self._knowledge_query).grid(
            row=1, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            knowledge_frame,
            text="Find in notes",
            command=self._show_knowledge_context,
        ).grid(row=1, column=1, sticky="ew")
        ttk.Button(
            knowledge_frame,
            text="Show connections",
            command=self._show_knowledge_graph,
        ).grid(row=1, column=2, sticky="ew", padx=(8, 0))
        self._request_button(
            knowledge_frame,
            text="Ask my sources",
            command=self._ask_knowledge,
        ).grid(row=1, column=3, sticky="ew", padx=(8, 0))
        ttk.Button(
            knowledge_frame,
            text="My sources",
            command=self._show_knowledge_list,
        ).grid(row=1, column=4, sticky="ew", padx=(8, 0))
        ttk.Button(
            knowledge_frame,
            text="Add file…",
            command=self._load_knowledge,
        ).grid(row=1, column=5, sticky="ew", padx=(8, 0))

        research_frame = ttk.LabelFrame(
            research_tab,
            text="Research workspace",
            padding=8,
        )
        research_frame.grid(row=0, column=0, sticky="nsew")
        research_tab.rowconfigure(0, weight=1)
        research_frame.columnconfigure(0, weight=1)
        research_frame.rowconfigure(1, weight=1)
        ttk.Label(
            research_frame,
            text=(
                "Follow the four steps from left to right. Changing sections never "
                "starts a request or saves data."
            ),
            style="Hint.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._research_workflow_tabs = ttk.Notebook(research_frame)
        self._research_workflow_tabs.grid(row=1, column=0, sticky="nsew")
        research_overview_frame = ttk.Frame(
            self._research_workflow_tabs,
            padding=10,
        )
        research_sources_frame = ttk.Frame(
            self._research_workflow_tabs,
            padding=10,
        )
        research_analysis_frame = ttk.Frame(
            self._research_workflow_tabs,
            padding=10,
        )
        research_review_frame = ttk.Frame(
            self._research_workflow_tabs,
            padding=10,
        )
        self._research_workflow_tabs.add(
            research_overview_frame,
            text=_RESEARCH_WORKFLOW_TAB_TITLES[0],
        )
        self._research_workflow_tabs.add(
            research_sources_frame,
            text=_RESEARCH_WORKFLOW_TAB_TITLES[1],
        )
        self._research_workflow_tabs.add(
            research_analysis_frame,
            text=_RESEARCH_WORKFLOW_TAB_TITLES[2],
        )
        self._research_workflow_tabs.add(
            research_review_frame,
            text=_RESEARCH_WORKFLOW_TAB_TITLES[3],
        )
        for section in (
            research_overview_frame,
            research_sources_frame,
            research_analysis_frame,
            research_review_frame,
        ):
            section.columnconfigure(1, weight=1)
        for section in (
            research_sources_frame,
            research_analysis_frame,
            research_review_frame,
        ):
            selected_run_frame = ttk.LabelFrame(
                section,
                text="Current research run",
                padding=(8, 6),
            )
            selected_run_frame.grid(
                row=0,
                column=0,
                columnspan=4,
                sticky="ew",
                pady=(0, 8),
            )
            selected_run_frame.columnconfigure(0, weight=1)
            ttk.Label(
                selected_run_frame,
                textvariable=self._research_run_context,
                style="Hint.TLabel",
                anchor="w",
            ).grid(row=0, column=0, sticky="ew")
            ttk.Label(
                selected_run_frame,
                textvariable=self._research_run_progress,
                style="Hint.TLabel",
                anchor="w",
            ).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(
            research_overview_frame,
            text=(
                "Start one research question or select an existing run before "
                "continuing to sources."
            ),
            style="Hint.TLabel",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(research_overview_frame, text="Question").grid(
            row=1,
            column=0,
            sticky="w",
        )
        ttk.Entry(
            research_overview_frame,
            textvariable=self._research_question,
        ).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(8, 8),
        )
        ttk.Button(
            research_overview_frame,
            text="Start research",
            command=self._create_research_run,
        ).grid(row=1, column=2, sticky="ew")
        ttk.Button(
            research_overview_frame,
            text="Research runs",
            command=self._show_research_runs,
        ).grid(row=1, column=3, sticky="ew", padx=(8, 0))
        ttk.Label(research_overview_frame, text="Research run").grid(
            row=2,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        research_run_frame = ttk.Frame(research_overview_frame)
        research_run_frame.grid(
            row=2,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        research_run_frame.columnconfigure(0, weight=1)
        self._research_run_selector = ttk.Combobox(
            research_run_frame,
            textvariable=self._research_run_choice,
            values=(),
            state="readonly",
        )
        self._research_run_selector.grid(
            row=0,
            column=0,
            sticky="ew",
        )
        self._research_run_selector.bind(
            "<<ComboboxSelected>>",
            self._select_research_run,
        )
        ttk.Label(
            research_run_frame,
            textvariable=self._research_run_summary,
            style="Hint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        research_run_filter_frame = ttk.Frame(research_run_frame)
        research_run_filter_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        research_run_filter_frame.columnconfigure(1, weight=1)
        ttk.Label(research_run_filter_frame, text="Filter loaded runs").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
        )
        ttk.Entry(
            research_run_filter_frame,
            textvariable=self._research_run_filter,
        ).grid(row=0, column=1, sticky="ew")
        ttk.Button(
            research_run_filter_frame,
            text="Filter",
            command=self._apply_research_run_filter,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))
        ttk.Button(
            research_run_filter_frame,
            text="Clear",
            command=self._clear_research_run_filter,
        ).grid(row=0, column=3, sticky="ew", padx=(8, 0))
        ttk.Label(
            research_run_filter_frame,
            textvariable=self._research_run_filter_summary,
            style="Hint.TLabel",
        ).grid(row=1, column=1, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Button(
            research_run_filter_frame,
            text="Show active run",
            command=self._show_active_research_run,
        ).grid(row=1, column=3, sticky="ew", padx=(8, 0), pady=(4, 0))
        ttk.Label(research_run_filter_frame, text="Status").grid(
            row=2,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=(8, 0),
        )
        self._research_run_status_filter_selector = ttk.Combobox(
            research_run_filter_frame,
            textvariable=self._research_run_status_filter,
            values=tuple(facet.value for facet in ResearchRunStatusFacet),
            state="readonly",
        )
        self._research_run_status_filter_selector.grid(
            row=2,
            column=1,
            columnspan=3,
            sticky="ew",
            pady=(8, 0),
        )
        self._research_run_status_filter_selector.bind(
            "<<ComboboxSelected>>",
            self._apply_research_run_status_filter,
        )
        ttk.Label(research_run_filter_frame, text="Catalog").grid(
            row=3,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=(8, 0),
        )
        ttk.Label(
            research_run_filter_frame,
            textvariable=self._research_run_catalog_summary,
            style="Hint.TLabel",
            anchor="w",
        ).grid(row=3, column=1, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_run_filter_frame, text="Sort visible runs").grid(
            row=4,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=(8, 0),
        )
        self._research_run_sort_selector = ttk.Combobox(
            research_run_filter_frame,
            textvariable=self._research_run_sort,
            values=tuple(mode.value for mode in ResearchRunSort),
            state="readonly",
        )
        self._research_run_sort_selector.grid(
            row=4,
            column=1,
            columnspan=3,
            sticky="ew",
            pady=(8, 0),
        )
        self._research_run_sort_selector.bind(
            "<<ComboboxSelected>>",
            self._apply_research_run_sort,
        )
        ttk.Label(
            research_run_filter_frame,
            textvariable=self._research_run_sort_summary,
            style="Hint.TLabel",
        ).grid(row=5, column=1, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Button(
            research_run_filter_frame,
            text="Reset view",
            command=self._reset_research_run_view,
        ).grid(row=5, column=3, sticky="ew", padx=(8, 0), pady=(4, 0))
        research_workflow_snapshot_frame = ttk.LabelFrame(
            research_overview_frame,
            text="Workflow snapshot",
            padding=(8, 6),
        )
        research_workflow_snapshot_frame.grid(
            row=3,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(10, 0),
        )
        research_workflow_snapshot_frame.columnconfigure(0, weight=1)
        ttk.Label(
            research_workflow_snapshot_frame,
            textvariable=self._research_workflow_snapshot,
            style="Hint.TLabel",
            anchor="w",
            justify="left",
            wraplength=820,
        ).grid(row=0, column=0, sticky="ew")
        ttk.Label(
            research_workflow_snapshot_frame,
            textvariable=self._research_evidence_coverage,
            style="Hint.TLabel",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(
            research_workflow_snapshot_frame,
            textvariable=self._research_assessment_coverage,
            style="Hint.TLabel",
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(
            research_workflow_snapshot_frame,
            textvariable=self._research_run_metadata,
            style="Hint.TLabel",
            anchor="w",
        ).grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(
            research_sources_frame,
            text=(
                "Discover or load sources, inspect recorded evidence, and pass exact "
                "references to later steps."
            ),
            style="Hint.TLabel",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 8))
        accepted_source_frame = ttk.LabelFrame(
            research_sources_frame,
            text="Selected run records",
            padding=8,
        )
        accepted_source_frame.grid(
            row=2,
            column=0,
            columnspan=4,
            sticky="ew",
        )
        accepted_source_frame.columnconfigure(1, weight=1)
        ttk.Label(accepted_source_frame, text="Accepted source").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
        )
        self._research_source_selector = ttk.Combobox(
            accepted_source_frame,
            textvariable=self._research_source_choice,
            values=(),
            state="readonly",
        )
        self._research_source_selector.grid(row=0, column=1, sticky="ew")
        self._research_source_selector.bind(
            "<<ComboboxSelected>>",
            self._select_research_source,
        )
        ttk.Button(
            accepted_source_frame,
            text="Use for assessment",
            command=self._use_selected_research_source_for_assessment,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))
        ttk.Button(
            accepted_source_frame,
            text="Add to comparison",
            command=self._add_selected_research_source_to_comparison,
        ).grid(row=0, column=3, sticky="ew", padx=(8, 0))
        ttk.Label(accepted_source_frame, text="Source view").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=(8, 0),
        )
        self._research_source_coverage_filter_selector = ttk.Combobox(
            accepted_source_frame,
            textvariable=self._research_source_coverage_filter,
            values=tuple(facet.value for facet in ResearchSourceCoverageFacet),
            state="readonly",
        )
        self._research_source_coverage_filter_selector.grid(
            row=1,
            column=1,
            sticky="ew",
            pady=(8, 0),
        )
        self._research_source_coverage_filter_selector.bind(
            "<<ComboboxSelected>>",
            self._apply_research_source_coverage_filter,
        )
        ttk.Label(
            accepted_source_frame,
            textvariable=self._research_source_coverage_summary,
            style="Hint.TLabel",
            anchor="w",
        ).grid(
            row=1,
            column=2,
            columnspan=2,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(accepted_source_frame, text="Recorded evidence").grid(
            row=2,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=(8, 0),
        )
        self._research_evidence_selector = ttk.Combobox(
            accepted_source_frame,
            textvariable=self._research_evidence_choice,
            values=(),
            state="readonly",
        )
        self._research_evidence_selector.grid(
            row=2,
            column=1,
            columnspan=3,
            sticky="ew",
            pady=(8, 0),
        )
        ttk.Button(
            accepted_source_frame,
            text="Use in assessment",
            command=self._add_selected_research_evidence_to_assessment,
        ).grid(row=3, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(
            accepted_source_frame,
            text="Use in claim",
            command=self._add_selected_research_evidence_to_claim,
        ).grid(row=3, column=2, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            accepted_source_frame,
            text="Add to comparison",
            command=self._add_selected_research_evidence_to_comparison,
        ).grid(row=3, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(accepted_source_frame, text="Authored assessments").grid(
            row=4,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=(8, 0),
        )
        self._research_assessment_selector = ttk.Combobox(
            accepted_source_frame,
            textvariable=self._research_assessment_choice,
            values=(),
            state="readonly",
        )
        self._research_assessment_selector.grid(
            row=4,
            column=1,
            columnspan=3,
            sticky="ew",
            pady=(8, 0),
        )
        ttk.Button(
            accepted_source_frame,
            text="Use as correction target",
            command=self._use_selected_research_assessment_as_correction_target,
        ).grid(row=5, column=2, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            accepted_source_frame,
            text="Add to comparison",
            command=self._add_selected_research_assessment_to_comparison,
        ).grid(row=5, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(
            research_analysis_frame,
            text=(
                "Review saved analysis, then author comparisons, assessments, "
                "claims, and contradiction notes with explicit previews."
            ),
            style="Hint.TLabel",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 8))
        research_analysis_frame.rowconfigure(2, weight=1)
        self._research_analysis_tabs = ttk.Notebook(research_analysis_frame)
        self._research_analysis_tabs.grid(
            row=2,
            column=0,
            columnspan=4,
            sticky="nsew",
        )
        research_saved_records_frame = ttk.Frame(
            self._research_analysis_tabs,
            padding=8,
        )
        research_comparison_frame = ttk.Frame(
            self._research_analysis_tabs,
            padding=8,
        )
        research_assessment_frame = ttk.Frame(
            self._research_analysis_tabs,
            padding=8,
        )
        research_claims_frame = ttk.Frame(
            self._research_analysis_tabs,
            padding=8,
        )
        self._research_analysis_tabs.add(
            research_saved_records_frame,
            text=_RESEARCH_ANALYSIS_TAB_TITLES[0],
        )
        self._research_analysis_tabs.add(
            research_comparison_frame,
            text=_RESEARCH_ANALYSIS_TAB_TITLES[1],
        )
        self._research_analysis_tabs.add(
            research_assessment_frame,
            text=_RESEARCH_ANALYSIS_TAB_TITLES[2],
        )
        self._research_analysis_tabs.add(
            research_claims_frame,
            text=_RESEARCH_ANALYSIS_TAB_TITLES[3],
        )
        for analysis_section in (
            research_saved_records_frame,
            research_comparison_frame,
            research_assessment_frame,
            research_claims_frame,
        ):
            analysis_section.columnconfigure(1, weight=1)
        authored_claim_frame = ttk.LabelFrame(
            research_saved_records_frame,
            text="Recorded claims and contradictions",
            padding=8,
        )
        authored_claim_frame.grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="ew",
        )
        authored_claim_frame.columnconfigure(1, weight=1)
        ttk.Label(authored_claim_frame, text="Authored claims").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
        )
        self._research_claim_selector = ttk.Combobox(
            authored_claim_frame,
            textvariable=self._research_claim_choice,
            values=(),
            state="readonly",
        )
        self._research_claim_selector.grid(
            row=0,
            column=1,
            columnspan=3,
            sticky="ew",
        )
        ttk.Button(
            authored_claim_frame,
            text="Use as predecessor",
            command=self._use_selected_research_claim_as_predecessor,
        ).grid(row=1, column=2, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            authored_claim_frame,
            text="Add to contradiction",
            command=self._add_selected_research_claim_to_contradiction,
        ).grid(row=1, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(authored_claim_frame, text="Recorded contradictions").grid(
            row=2,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=(8, 0),
        )
        self._research_persisted_contradiction_selector = ttk.Combobox(
            authored_claim_frame,
            textvariable=self._research_persisted_contradiction_choice,
            values=(),
            state="readonly",
        )
        self._research_persisted_contradiction_selector.grid(
            row=2,
            column=1,
            columnspan=3,
            sticky="ew",
            pady=(8, 0),
        )
        ttk.Button(
            authored_claim_frame,
            text="Use selected pair",
            command=self._use_selected_persisted_contradiction_pair,
        ).grid(row=3, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        comparison_note_frame = ttk.LabelFrame(
            research_saved_records_frame,
            text="Recorded comparison notes",
            padding=8,
        )
        comparison_note_frame.grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(8, 0),
        )
        comparison_note_frame.columnconfigure(1, weight=1)
        ttk.Label(comparison_note_frame, text="Comparison note").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
        )
        self._research_persisted_comparison_note_selector = ttk.Combobox(
            comparison_note_frame,
            textvariable=self._research_persisted_comparison_note_choice,
            values=(),
            state="readonly",
        )
        self._research_persisted_comparison_note_selector.grid(
            row=0,
            column=1,
            columnspan=3,
            sticky="ew",
        )
        self._research_persisted_comparison_note_selector.bind(
            "<<ComboboxSelected>>",
            self._select_persisted_research_comparison_note,
        )
        ttk.Label(
            comparison_note_frame,
            textvariable=self._research_persisted_comparison_note_references,
            style="Hint.TLabel",
            justify="left",
            wraplength=1000,
        ).grid(row=1, column=1, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Button(
            comparison_note_frame,
            text="Use sources",
            command=self._use_selected_persisted_comparison_note_sources,
        ).grid(row=2, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(
            comparison_note_frame,
            text="Use evidence",
            command=self._use_selected_persisted_comparison_note_evidence,
        ).grid(row=2, column=2, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            comparison_note_frame,
            text="Use assessments",
            command=self._use_selected_persisted_comparison_note_assessments,
        ).grid(row=2, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(research_sources_frame, text="Source discovery").grid(
            row=3,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        self._request_button(
            research_sources_frame,
            text="Find sources",
            command=self._discover_research_sources,
        ).grid(row=3, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_sources_frame, text="Candidates").grid(
            row=4,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        self._research_candidate_selector = ttk.Combobox(
            research_sources_frame,
            textvariable=self._research_candidate,
            values=(),
            state="readonly",
        )
        self._research_candidate_selector.grid(
            row=4,
            column=1,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_sources_frame,
            text="Use selected URL",
            command=self._use_selected_research_candidate,
        ).grid(row=4, column=2, sticky="ew", pady=(8, 0))
        self._request_button(
            research_sources_frame,
            text="Preview & load",
            command=self._preview_and_accept_research_candidate,
        ).grid(row=4, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(research_sources_frame, text="HTTPS URL").grid(
            row=5,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(research_sources_frame, textvariable=self._research_url).grid(
            row=5,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        self._request_button(
            research_sources_frame,
            text="Load source",
            command=self._load_research_source,
        ).grid(row=5, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_sources_frame, text="Source document ID").grid(
            row=6,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_sources_frame,
            textvariable=self._research_source_document_id,
        ).grid(
            row=6,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_sources_frame,
            text="Preview assessment",
            command=self._preview_research_source_assessment,
        ).grid(row=6, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_comparison_frame, text="Comparison source IDs").grid(
            row=0,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_comparison_frame,
            textvariable=self._research_comparison_document_ids,
        ).grid(
            row=0,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_comparison_frame,
            text="Compare sources",
            command=self._preview_research_source_comparison,
        ).grid(row=0, column=3, sticky="ew")
        ttk.Label(research_comparison_frame, text="Comparison evidence IDs").grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_comparison_frame,
            textvariable=self._research_comparison_evidence_ids,
        ).grid(
            row=1,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(research_comparison_frame, text="Comparison assessment IDs").grid(
            row=2,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_comparison_frame,
            textvariable=self._research_comparison_assessment_ids,
        ).grid(
            row=2,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(research_comparison_frame, text="Comparison note").grid(
            row=3,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_comparison_frame,
            textvariable=self._research_comparison_note_text,
        ).grid(
            row=3,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_comparison_frame,
            text="Preview & save note",
            command=self._preview_and_record_research_source_comparison_note,
        ).grid(row=3, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_sources_frame, text="Chunk ID").grid(
            row=7,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(research_sources_frame, textvariable=self._research_chunk_id).grid(
            row=7,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_sources_frame,
            text="View evidence",
            command=self._show_research_evidence,
        ).grid(row=7, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_sources_frame, text="Evidence note").grid(
            row=8,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_sources_frame,
            textvariable=self._research_evidence_note,
        ).grid(
            row=8,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_sources_frame,
            text="Save evidence",
            command=self._record_research_evidence,
        ).grid(row=8, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_assessment_frame, text="Assessment evidence IDs").grid(
            row=0,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_assessment_frame,
            textvariable=self._research_assessment_evidence_ids,
        ).grid(
            row=0,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(research_assessment_frame, text="Assessment text").grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_assessment_frame,
            textvariable=self._research_assessment_text,
        ).grid(
            row=1,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_assessment_frame,
            text="Preview & save assessment",
            command=self._preview_and_record_research_source_assessment,
        ).grid(row=1, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(
            research_assessment_frame,
            text="Information trust (user-authored)",
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Combobox(
            research_assessment_frame,
            textvariable=self._research_information_trust,
            values=tuple(value.value for value in ResearchInformationTrust),
            state="readonly",
        ).grid(row=2, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(
            research_assessment_frame,
            text="Supersedes assessment ID (optional)",
        ).grid(
            row=3,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_assessment_frame,
            textvariable=self._research_assessment_supersedes_id,
        ).grid(
            row=3,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(
            research_claims_frame,
            text="Claim evidence IDs (comma-separated)",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_claims_frame,
            textvariable=self._research_claim_evidence_ids,
        ).grid(
            row=0,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(research_claims_frame, text="User-authored claim").grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_claims_frame,
            textvariable=self._research_claim_text,
        ).grid(
            row=1,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(8, 0),
            pady=(8, 0),
        )
        ttk.Label(research_claims_frame, text="Epistemic state / confidence").grid(
            row=2,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Combobox(
            research_claims_frame,
            textvariable=self._research_claim_epistemic_state,
            values=tuple(value.value for value in ResearchEpistemicState),
            state="readonly",
        ).grid(row=2, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        ttk.Combobox(
            research_claims_frame,
            textvariable=self._research_claim_confidence,
            values=tuple(value.value for value in ResearchClaimConfidence),
            state="readonly",
        ).grid(row=2, column=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            research_claims_frame,
            text="View claims",
            command=self._preview_research_claims,
        ).grid(row=2, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(research_claims_frame, text="Supersedes claim ID (optional)").grid(
            row=3,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_claims_frame,
            textvariable=self._research_claim_supersedes_id,
        ).grid(row=3, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        ttk.Button(
            research_claims_frame,
            text="Preview & save claim",
            command=self._preview_and_record_research_claim,
        ).grid(row=3, column=2, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(
            research_claims_frame,
            text="Contradicting claim IDs (exactly two)",
        ).grid(
            row=4,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_claims_frame,
            textvariable=self._research_claim_contradiction_ids,
        ).grid(row=4, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        ttk.Button(
            research_claims_frame,
            text="Suggest contradictions",
            command=self._suggest_research_claim_contradictions,
        ).grid(row=4, column=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            research_claims_frame,
            text="View contradictions",
            command=self._preview_research_claim_contradictions,
        ).grid(row=4, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_claims_frame, text="Suggested pair (not saved)").grid(
            row=5,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        self._research_claim_contradiction_proposal_selector = ttk.Combobox(
            research_claims_frame,
            textvariable=self._research_claim_contradiction_proposal,
            state="readonly",
        )
        self._research_claim_contradiction_proposal_selector.grid(
            row=5,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            research_claims_frame,
            text="Use selected pair",
            command=self._use_selected_research_claim_contradiction_proposal,
        ).grid(row=5, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(research_claims_frame, text="User contradiction note").grid(
            row=6,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(
            research_claims_frame,
            textvariable=self._research_claim_contradiction_note,
        ).grid(row=6, column=1, columnspan=2, sticky="ew", padx=(8, 8), pady=(8, 0))
        ttk.Button(
            research_claims_frame,
            text="Preview & save contradiction",
            command=self._preview_and_record_research_claim_contradiction,
        ).grid(row=6, column=3, sticky="ew", pady=(8, 0))
        ttk.Label(
            research_review_frame,
            text=(
                "Review integrity, choose a terminal status, and explicitly preview "
                "or save the final Markdown export."
            ),
            style="Hint.TLabel",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 8))
        ttk.Label(research_review_frame, text="Final status").grid(
            row=2,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Combobox(
            research_review_frame,
            textvariable=self._research_target_status,
            values=("completed", "failed", "cancelled"),
            state="readonly",
        ).grid(row=2, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        ttk.Button(
            research_review_frame,
            text="Preview status",
            command=self._preview_and_update_research_status,
        ).grid(row=2, column=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            research_review_frame,
            text="Export preview",
            command=self._preview_research_run_markdown_export,
        ).grid(row=2, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            research_review_frame,
            text="Verify export",
            command=self._verify_research_run_markdown_export,
        ).grid(row=3, column=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            research_review_frame,
            text="Save export",
            command=self._save_research_run_markdown_export,
        ).grid(row=3, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            research_review_frame,
            text="Evidence integrity",
            command=self._show_research_evidence_integrity,
        ).grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(
            research_review_frame,
            text="Research data status",
            command=self._show_research_content_status,
        ).grid(row=3, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))

        relation_frame = ttk.LabelFrame(
            knowledge_tab,
            text="Local source relation",
            padding=10,
        )
        relation_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
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

        status_frame = ttk.Frame(chat_tab)
        status_frame.grid(row=2, column=0, sticky="ew", pady=(8, 4))
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

        transcript_frame = ttk.LabelFrame(chat_tab, text="Conversation", padding=6)
        transcript_frame.grid(row=3, column=0, sticky="nsew")
        transcript_frame.columnconfigure(0, weight=1)
        transcript_frame.rowconfigure(0, weight=1)
        self._transcript = scrolledtext.ScrolledText(
            transcript_frame,
            wrap=tk.WORD,
            height=18,
        )
        self._transcript.grid(row=0, column=0, sticky="nsew")
        self._transcript.insert(
            "1.0",
            (
                "Welcome to Hypatia.\n"
                "Open a session above, then type a message below. "
                "Use Ctrl+Enter to send.\n\n"
            ),
        )
        self._transcript.configure(state=tk.DISABLED)

        composer_frame = ttk.LabelFrame(
            chat_tab,
            text="Message · Ctrl+Enter to send",
            padding=8,
        )
        composer_frame.grid(row=4, column=0, sticky="ew", pady=(8, 0))
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
        """Render explicit size and theme choices without changing runtime state."""
        try:
            theme = DesktopTheme(self._theme_mode.get())
        except ValueError:
            theme = DesktopTheme.EYE_COMFORT
            self._theme_mode.set(theme.value)
        palette = _accessibility_palette(theme)
        font = ("TkDefaultFont", self._font_size)
        self._font_size_label.set(f"Text size: {self._font_size} pt")
        self._root.configure(background=palette.background)
        self._style.configure(
            ".",
            background=palette.background,
            foreground=palette.foreground,
            font=font,
            bordercolor=palette.border_color,
            darkcolor=palette.border_color,
            lightcolor=palette.border_color,
            troughcolor=palette.field_background,
        )
        self._style.configure(
            "TFrame",
            background=palette.background,
        )
        self._style.configure(
            "Hint.TLabel",
            background=palette.background,
            foreground=palette.muted_foreground,
            font=font,
        )
        self._style.configure(
            "TLabelframe",
            background=palette.background,
            foreground=palette.foreground,
            bordercolor=palette.border_color,
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
            bordercolor=palette.border_color,
            lightcolor=palette.border_color,
            darkcolor=palette.border_color,
            padding=(10, 5),
        )
        self._style.map(
            "TButton",
            background=[
                ("disabled", palette.field_background),
                ("pressed", palette.selection_background),
                ("active", palette.active_background),
                ("focus", palette.focus_color),
            ],
            foreground=[
                ("disabled", palette.muted_foreground),
                ("active", palette.foreground),
                ("pressed", palette.foreground),
            ],
            bordercolor=[
                ("focus", palette.focus_color),
                ("!focus", palette.border_color),
            ],
        )
        for style_name in ("TCheckbutton", "TRadiobutton"):
            self._style.configure(
                style_name,
                background=palette.background,
                foreground=palette.foreground,
                font=font,
                focuscolor=palette.focus_color,
            )
            self._style.map(
                style_name,
                background=[("active", palette.background)],
                foreground=[("disabled", palette.muted_foreground)],
            )
        self._style.configure(
            "TEntry",
            fieldbackground=palette.field_background,
            foreground=palette.foreground,
            font=font,
            insertcolor=palette.foreground,
            bordercolor=palette.border_color,
            lightcolor=palette.border_color,
            darkcolor=palette.border_color,
        )
        self._style.map(
            "TEntry",
            fieldbackground=[
                ("disabled", palette.background),
                ("focus", palette.field_background),
            ],
            foreground=[("disabled", palette.muted_foreground)],
            bordercolor=[
                ("focus", palette.focus_color),
                ("!focus", palette.border_color),
            ],
        )
        self._style.configure(
            "TCombobox",
            background=palette.button_background,
            fieldbackground=palette.field_background,
            foreground=palette.foreground,
            arrowcolor=palette.foreground,
            bordercolor=palette.border_color,
            lightcolor=palette.border_color,
            darkcolor=palette.border_color,
            font=font,
        )
        self._style.map(
            "TCombobox",
            background=[("active", palette.active_background)],
            fieldbackground=[
                ("readonly", palette.field_background),
                ("disabled", palette.background),
            ],
            foreground=[("disabled", palette.muted_foreground)],
            arrowcolor=[("disabled", palette.muted_foreground)],
            bordercolor=[
                ("focus", palette.focus_color),
                ("!focus", palette.border_color),
            ],
        )
        self._style.configure(
            "TNotebook",
            background=palette.background,
            bordercolor=palette.border_color,
            tabmargins=(2, 2, 2, 0),
        )
        self._style.configure(
            "TNotebook.Tab",
            background=palette.button_background,
            foreground=palette.foreground,
            padding=(16, 8),
            font=font,
            focuscolor=palette.focus_color,
            bordercolor=palette.border_color,
        )
        self._style.map(
            "TNotebook.Tab",
            background=[
                ("selected", palette.active_background),
                ("active", palette.selection_background),
            ],
            foreground=[("disabled", palette.muted_foreground)],
        )
        self._style.configure(
            "TScrollbar",
            background=palette.button_background,
            troughcolor=palette.field_background,
            arrowcolor=palette.foreground,
            bordercolor=palette.border_color,
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
            self._render_research_run_selector(response.research_runs)

    def _show_research_runs(self) -> None:
        """Render the current persisted run catalog without network access."""
        response = self._controller.list_research_runs()
        self._append_response(response)
        if response.success:
            self._render_research_run_selector(tuple(response.research_runs))

    def _render_research_run_selector(
        self,
        runs: tuple[ResearchRun, ...] | list[ResearchRun],
    ) -> None:
        """Replace the presentation-only run catalog and select a valid item."""
        normalized_runs = tuple(runs)
        selected_run_id = self._research_run_id.get().strip()
        self._research_runs = normalized_runs
        sort_mode = self._current_research_run_sort()
        visible_runs = self._sort_research_runs(normalized_runs, sort_mode)
        self._visible_research_runs = visible_runs
        self._research_run_filter.set("")
        self._research_run_status_filter.set(ResearchRunStatusFacet.ALL.value)
        self._research_run_catalog_summary.set(
            self._research_run_catalog_summary_text(normalized_runs)
        )
        self._research_run_filter_summary.set(
            "No research runs are available."
            if not normalized_runs
            else f"All {len(normalized_runs)} loaded research runs are shown."
        )
        self._research_run_sort_summary.set(f"Current sort: {sort_mode.value}.")
        labels = tuple(self._research_run_label(run) for run in visible_runs)
        self._research_run_selector.configure(values=labels)
        if not normalized_runs:
            self._research_run_choice.set("")
            self._research_run_id.set("")
            self._research_run_summary.set("No research runs available.")
            self._research_run_context.set(
                "No research runs available. Return to Overview to start one."
            )
            self._research_run_progress.set(
                "Progress unavailable: no research runs available."
            )
            self._research_workflow_snapshot.set(
                "No research runs are available to summarize."
            )
            self._research_evidence_coverage.set(
                "Evidence coverage unavailable: no research runs available."
            )
            self._research_assessment_coverage.set(
                "Assessment coverage unavailable: no research runs available."
            )
            self._research_run_metadata.set(
                "Run metadata unavailable: no research runs are available."
            )
            self._clear_research_run_dependent_presentations()
            return
        selected_index = next(
            (
                index
                for index, run in enumerate(visible_runs)
                if run.run_id == selected_run_id
            ),
            0,
        )
        self._research_run_selector.current(selected_index)
        self._select_research_run()

    def _apply_research_run_filter(self) -> None:
        """Filter only the loaded catalog without changing the active run."""
        query = self._research_run_filter.get().strip()
        if len(query) > _MAX_RESEARCH_RUN_FILTER_LENGTH:
            self._research_run_filter_summary.set(
                "Filter is too long; the loaded catalog is unchanged."
            )
            self._status.set(
                f"Research run filter cannot exceed "
                f"{_MAX_RESEARCH_RUN_FILTER_LENGTH} characters."
            )
            return
        try:
            status_filter = self._selected_research_run_status_filter()
        except ValueError:
            self._research_run_filter_summary.set(
                "Status filter is invalid; the loaded view is unchanged."
            )
            self._status.set("Research run status filter is invalid.")
            return
        text_matching_runs = self._filter_research_runs(self._research_runs, query)
        matching_runs = self._filter_research_runs_by_status(
            text_matching_runs,
            status_filter,
        )
        visible_runs = self._sort_research_runs(
            matching_runs,
            self._current_research_run_sort(),
        )
        self._render_visible_research_runs(visible_runs)
        total_count = len(self._research_runs)
        visible_count = len(visible_runs)
        if total_count == 0:
            self._research_run_filter_summary.set("No research runs are available.")
        elif not query and status_filter is None:
            self._research_run_filter_summary.set(
                f"All {total_count} loaded research runs are shown."
            )
        elif visible_runs:
            self._research_run_filter_summary.set(
                f"{visible_count} of {total_count} loaded research runs match "
                f"({self._research_run_status_filter.get()})."
            )
        else:
            self._research_run_filter_summary.set(
                "No loaded research runs match the current filters; "
                "the active run is unchanged."
            )
        self._status.set(
            f"research run filter: {visible_count} of {total_count} shown; "
            "active run unchanged"
        )

    def _clear_research_run_filter(self) -> None:
        """Restore the complete loaded catalog without opening a read path."""
        self._research_run_filter.set("")
        self._apply_research_run_filter()

    def _reset_research_run_view(self) -> None:
        """Restore every local catalog view control to its safe default."""
        default_sort = ResearchRunSort.UPDATED_NEWEST
        self._research_run_filter.set("")
        self._research_run_status_filter.set(ResearchRunStatusFacet.ALL.value)
        self._research_run_sort.set(default_sort.value)
        visible_runs = self._sort_research_runs(self._research_runs, default_sort)
        self._render_visible_research_runs(visible_runs)

        selected_run_id = self._research_run_id.get().strip()
        selected_run = next(
            (run for run in self._research_runs if run.run_id == selected_run_id),
            None,
        )
        if selected_run is not None:
            self._research_run_choice.set(self._research_run_label(selected_run))

        total_count = len(self._research_runs)
        self._research_run_filter_summary.set(
            "No research runs are available."
            if total_count == 0
            else f"All {total_count} loaded research runs are shown."
        )
        self._research_run_sort_summary.set(f"Current sort: {default_sort.value}.")
        if selected_run is not None:
            active_status = f"active run shown: {selected_run_id}"
        elif selected_run_id:
            active_status = f"active run not loaded: {selected_run_id}"
        else:
            active_status = "no active run selected"
        self._status.set(
            f"research run view reset: {total_count} loaded; filters cleared; "
            f"default sort restored; {active_status}"
        )

    def _apply_research_run_status_filter(
        self,
        _event: object | None = None,
    ) -> None:
        """Apply one local status facet through the combined filter pipeline."""
        self._apply_research_run_filter()

    def _show_active_research_run(self) -> None:
        """Restore one filtered-out active run without opening a read path."""
        selected_run_id = self._research_run_id.get().strip()
        if not selected_run_id:
            self._research_run_filter_summary.set("No active research run is selected.")
            self._status.set("Select a research run before showing it.")
            return
        selected_run = next(
            (run for run in self._research_runs if run.run_id == selected_run_id),
            None,
        )
        if selected_run is None:
            self._research_run_filter_summary.set(
                "The active research run is not in the loaded catalog; refresh runs."
            )
            self._status.set("Active research run is not loaded.")
            return
        try:
            sort_mode = ResearchRunSort(self._research_run_sort.get())
        except ValueError:
            self._research_run_filter_summary.set(
                "Current sort is invalid; the active run was not shown."
            )
            self._status.set("Research run sort is invalid.")
            return
        visible_runs = self._sort_research_runs(self._research_runs, sort_mode)
        self._research_run_filter.set("")
        self._research_run_status_filter.set(ResearchRunStatusFacet.ALL.value)
        self._render_visible_research_runs(visible_runs)
        self._research_run_choice.set(self._research_run_label(selected_run))
        self._research_run_filter_summary.set(
            f"All {len(self._research_runs)} loaded research runs are shown."
        )
        self._status.set(
            f"active research run shown: {selected_run_id}; "
            f"{len(self._research_runs)} loaded; filters cleared; sort preserved"
        )

    def _apply_research_run_sort(self, _event: object | None = None) -> None:
        """Reorder only the current visible membership without a runtime call."""
        try:
            sort_mode = ResearchRunSort(self._research_run_sort.get())
        except ValueError:
            self._research_run_sort_summary.set(
                "Invalid sort; the visible research runs are unchanged."
            )
            self._status.set("Research run sort is invalid.")
            return
        visible_runs = self._sort_research_runs(
            self._visible_research_runs,
            sort_mode,
        )
        self._render_visible_research_runs(visible_runs)
        self._research_run_sort_summary.set(f"Current sort: {sort_mode.value}.")
        self._status.set(
            f"research run sort: {sort_mode.value}; "
            f"{len(visible_runs)} visible; active run unchanged"
        )

    def _render_visible_research_runs(
        self,
        visible_runs: tuple[ResearchRun, ...],
    ) -> None:
        """Render one local view while preserving any visible active run."""
        self._visible_research_runs = visible_runs
        self._research_run_selector.configure(
            values=tuple(self._research_run_label(run) for run in visible_runs)
        )
        selected_run_id = self._research_run_id.get().strip()
        selected_index = next(
            (
                index
                for index, run in enumerate(visible_runs)
                if run.run_id == selected_run_id
            ),
            None,
        )
        if selected_index is None:
            self._research_run_choice.set("")
        else:
            self._research_run_selector.current(selected_index)

    def _current_research_run_sort(self) -> ResearchRunSort:
        """Return one valid sort, restoring the safe default if state is invalid."""
        try:
            return ResearchRunSort(self._research_run_sort.get())
        except ValueError:
            default = ResearchRunSort.UPDATED_NEWEST
            self._research_run_sort.set(default.value)
            return default

    def _selected_research_run_status_filter(self) -> ResearchRunStatus | None:
        """Return the exact local status represented by the current facet."""
        facet = ResearchRunStatusFacet(self._research_run_status_filter.get())
        if facet is ResearchRunStatusFacet.ALL:
            return None
        return ResearchRunStatus(facet.value.casefold())

    @staticmethod
    def _research_run_catalog_summary_text(
        runs: tuple[ResearchRun, ...],
    ) -> str:
        """Summarize complete immutable catalog membership by lifecycle."""
        status_counts = " · ".join(
            f"{status.value.title()} " f"{sum(run.status is status for run in runs)}"
            for status in ResearchRunStatus
        )
        return f"Loaded catalog: All {len(runs)} · {status_counts}"

    @staticmethod
    def _filter_research_runs(
        runs: tuple[ResearchRun, ...],
        query: str,
    ) -> tuple[ResearchRun, ...]:
        """Match bounded question text, exact status, or exact run ID locally."""
        normalized_query = query.strip().casefold()
        if not normalized_query:
            return runs
        return tuple(
            run
            for run in runs
            if normalized_query in run.question.casefold()
            or normalized_query == run.status.value.casefold()
            or normalized_query == run.run_id.casefold()
        )

    @staticmethod
    def _filter_research_runs_by_status(
        runs: tuple[ResearchRun, ...],
        status_filter: ResearchRunStatus | None,
    ) -> tuple[ResearchRun, ...]:
        """Restrict one already loaded tuple to an exact lifecycle status."""
        if status_filter is None:
            return runs
        return tuple(run for run in runs if run.status is status_filter)

    @staticmethod
    def _sort_research_runs(
        runs: tuple[ResearchRun, ...],
        mode: ResearchRunSort,
    ) -> tuple[ResearchRun, ...]:
        """Sort one presentation tuple with deterministic ascending ID ties."""
        id_ordered = tuple(
            sorted(runs, key=lambda run: (run.run_id.casefold(), run.run_id))
        )
        if mode is ResearchRunSort.UPDATED_NEWEST:
            return tuple(
                sorted(id_ordered, key=lambda run: run.updated_at, reverse=True)
            )
        if mode is ResearchRunSort.UPDATED_OLDEST:
            return tuple(sorted(id_ordered, key=lambda run: run.updated_at))
        if mode is ResearchRunSort.CREATED_NEWEST:
            return tuple(
                sorted(id_ordered, key=lambda run: run.created_at, reverse=True)
            )
        return tuple(
            sorted(
                id_ordered,
                key=lambda run: (
                    run.question.casefold(),
                    run.run_id.casefold(),
                    run.run_id,
                ),
            )
        )

    @staticmethod
    def _research_run_label(run: ResearchRun) -> str:
        question = run.question
        if len(question) > 80:
            question = f"{question[:77]}..."
        return f"{question} [{run.status.value}] — {run.run_id}"

    @staticmethod
    def _research_run_context_text(run: ResearchRun) -> str:
        """Identify the exact immutable run snapshot used by later tabs."""
        return f"Working on: {TkinterDesktopWindow._research_run_label(run)}"

    def _select_research_run(self, _event: object | None = None) -> None:
        """Select one catalogued run without starting any research action."""
        selected_index = self._research_run_selector.current()
        if not 0 <= selected_index < len(self._visible_research_runs):
            self._clear_research_sources()
            self._clear_research_claims()
            self._clear_research_persisted_contradictions()
            self._clear_research_persisted_comparison_notes()
            self._research_run_summary.set("Refresh and select a research run.")
            self._research_run_context.set(
                "No research run selected. Return to Overview to refresh or choose one."
            )
            self._research_run_progress.set(
                "Progress unavailable until a research run is selected."
            )
            self._research_workflow_snapshot.set(
                "Refresh and select a research run to see stage records."
            )
            self._research_evidence_coverage.set(
                "Evidence coverage unavailable until a research run is selected."
            )
            self._research_assessment_coverage.set(
                "Assessment coverage unavailable until a research run is selected."
            )
            self._research_run_metadata.set(
                "Run metadata unavailable until a research run is selected."
            )
            self._status.set("Refresh and select a research run first.")
            return
        selected_run = self._visible_research_runs[selected_index]
        previous_run_id = self._research_run_id.get().strip()
        self._research_run_id.set(selected_run.run_id)
        if previous_run_id != selected_run.run_id:
            self._clear_research_run_dependent_presentations()
        self._render_research_source_selector(selected_run)
        self._render_research_claim_selector(selected_run)
        self._render_research_persisted_contradiction_selector(selected_run)
        self._render_research_persisted_comparison_note_selector(selected_run)
        self._research_run_summary.set(self._research_run_summary_text(selected_run))
        self._research_run_context.set(self._research_run_context_text(selected_run))
        self._research_run_progress.set(self._research_run_progress_text(selected_run))
        self._research_workflow_snapshot.set(
            self._research_workflow_snapshot_text(selected_run)
        )
        self._research_evidence_coverage.set(
            self._research_evidence_coverage_text(selected_run)
        )
        self._research_assessment_coverage.set(
            self._research_assessment_coverage_text(selected_run)
        )
        self._research_run_metadata.set(self._research_run_metadata_text(selected_run))
        self._status.set(
            f"research run selected: {selected_run.run_id}; no action started"
        )

    @staticmethod
    def _research_run_summary_text(run: ResearchRun) -> str:
        """Summarize bounded catalog counts without opening another read path."""
        return (
            f"Status: {run.status.value} · "
            f"{TkinterDesktopWindow._research_run_progress_text(run)}"
        )

    @staticmethod
    def _research_run_progress_text(run: ResearchRun) -> str:
        """Show complete selected-snapshot counts in each later workflow tab."""
        return (
            f"Sources: {len(run.sources)} · "
            f"Evidence: {len(run.evidence)} · Claims: {len(run.claims)}"
        )

    @staticmethod
    def _research_workflow_snapshot_text(run: ResearchRun) -> str:
        """Describe existing stage records without inferring readiness or truth."""
        return (
            f"Sources & evidence — Sources: {len(run.sources)} · "
            f"Evidence: {len(run.evidence)} | Authored analysis — "
            f"Assessments: {len(run.assessments)} · "
            f"Comparison notes: {len(run.comparison_notes)} · "
            f"Claims: {len(run.claims)} · "
            f"Contradictions: {len(run.claim_contradictions)} | "
            f"Review & export — Status: {run.status.value}"
        )

    @staticmethod
    def _research_evidence_coverage_text(run: ResearchRun) -> str:
        """Count accepted sources represented by evidence without inference."""
        accepted_source_ids = {source.document_id for source in run.sources}
        represented_source_ids = {
            record.source_document_id for record in run.evidence
        } & accepted_source_ids
        accepted_count = len(accepted_source_ids)
        represented_count = len(represented_source_ids)
        return (
            f"Evidence coverage — Accepted sources: {accepted_count} · "
            f"With evidence: {represented_count} · "
            f"Without evidence: {accepted_count - represented_count}"
        )

    @staticmethod
    def _research_assessment_coverage_text(run: ResearchRun) -> str:
        """Count accepted sources with a current authored assessment."""
        accepted_source_ids = {source.document_id for source in run.sources}
        superseded_assessment_ids = {
            record.supersedes_assessment_id
            for record in run.assessments
            if record.supersedes_assessment_id is not None
        }
        current_assessment_source_ids = {
            record.source_document_id
            for record in run.assessments
            if record.assessment_id not in superseded_assessment_ids
        } & accepted_source_ids
        accepted_count = len(accepted_source_ids)
        current_count = len(current_assessment_source_ids)
        return (
            f"Assessment coverage — Accepted sources: {accepted_count} · "
            f"With current assessment: {current_count} · "
            f"Without current assessment: {accepted_count - current_count}"
        )

    @staticmethod
    def _research_run_metadata_text(run: ResearchRun) -> str:
        """Expose bounded audit timing and a count without failure details."""
        created = run.created_at.isoformat(timespec="seconds")
        updated = run.updated_at.isoformat(timespec="seconds")
        return (
            f"Run metadata — Created: {created} · Updated: {updated} · "
            f"Safe failures: {len(run.failures)}"
        )

    def _render_research_claim_selector(self, run: ResearchRun) -> None:
        """Render authored claims from the already loaded exact run snapshot."""
        records = run.claims
        superseded_ids = {
            record.supersedes_claim_id
            for record in records
            if record.supersedes_claim_id is not None
        }
        current_ids = frozenset(
            record.claim_id
            for record in records
            if record.claim_id not in superseded_ids
        )
        self._research_claim_records = records
        self._research_current_claim_ids = current_ids
        self._research_claim_run_id = run.run_id
        labels = tuple(
            self._research_claim_label(
                record,
                is_current=record.claim_id in current_ids,
            )
            for record in records
        )
        self._research_claim_selector.configure(values=labels)
        if not records:
            self._research_claim_choice.set("")
            return
        selected_index = next(
            (
                index
                for index, record in enumerate(records)
                if record.claim_id in current_ids
            ),
            0,
        )
        self._research_claim_selector.current(selected_index)

    @staticmethod
    def _research_claim_label(
        record: ResearchClaimRecord,
        *,
        is_current: bool,
    ) -> str:
        """Show audit state, uncertainty, bounded text, and the exact claim ID."""
        text = " ".join(record.text.split())
        if len(text) > 100:
            text = f"{text[:97]}..."
        audit_state = "current" if is_current else "superseded"
        return (
            f"[{audit_state}] [{record.epistemic_state.value}/"
            f"{record.confidence.value}] {text} — {record.claim_id}"
        )

    def _selected_research_claim(self) -> ResearchClaimRecord | None:
        """Return only a claim bound to the currently selected loaded run."""
        if self._research_run_id.get().strip() != self._research_claim_run_id:
            self._clear_research_claims()
            return None
        selected_index = self._research_claim_selector.current()
        if not 0 <= selected_index < len(self._research_claim_records):
            return None
        return self._research_claim_records[selected_index]

    def _use_selected_research_claim_as_predecessor(self) -> None:
        """Copy one current claim ID into the manual supersession field only."""
        record = self._selected_research_claim()
        if record is None:
            self._status.set("Select an authored claim first.")
            return
        if record.claim_id not in self._research_current_claim_ids:
            self._status.set("Only a current claim can be superseded.")
            return
        self._research_claim_supersedes_id.set(record.claim_id)
        self._status.set("claim ID copied as predecessor; nothing requested or saved")

    def _add_selected_research_claim_to_contradiction(self) -> None:
        """Append one current claim ID to the two-ID contradiction field only."""
        record = self._selected_research_claim()
        if record is None:
            self._status.set("Select an authored claim first.")
            return
        if record.claim_id not in self._research_current_claim_ids:
            self._status.set("Only a current claim can be used in a contradiction.")
            return
        current_ids = tuple(
            value.strip()
            for value in self._research_claim_contradiction_ids.get().split(",")
            if value.strip()
        )
        if record.claim_id in current_ids:
            self._status.set(
                "claim ID is already in the contradiction; nothing changed"
            )
            return
        if len(current_ids) >= 2:
            self._status.set("A contradiction accepts exactly two claim IDs.")
            return
        self._research_claim_contradiction_ids.set(
            ", ".join((*current_ids, record.claim_id))
        )
        self._status.set("claim ID added to contradiction; nothing requested or saved")

    def _render_research_persisted_contradiction_selector(
        self,
        run: ResearchRun,
    ) -> None:
        """Render recorded contradictions from the loaded exact run snapshot."""
        records = run.claim_contradictions
        self._research_persisted_contradiction_records = records
        self._research_persisted_contradiction_run_id = run.run_id
        labels = tuple(
            self._research_persisted_contradiction_label(record) for record in records
        )
        self._research_persisted_contradiction_selector.configure(values=labels)
        if not records:
            self._research_persisted_contradiction_choice.set("")
            return
        self._research_persisted_contradiction_selector.current(0)

    @staticmethod
    def _research_persisted_contradiction_label(
        record: ResearchClaimContradictionRecord,
    ) -> str:
        """Show exact pair, bounded note, time, and exact contradiction ID."""
        note = " ".join(record.note.split())
        if len(note) > 100:
            note = f"{note[:97]}..."
        return (
            f"[{record.recorded_at.isoformat()}] {record.claim_ids[0]} ↔ "
            f"{record.claim_ids[1]} | {note} — {record.contradiction_id}"
        )

    def _selected_persisted_research_contradiction(
        self,
    ) -> ResearchClaimContradictionRecord | None:
        """Return only a contradiction bound to the selected loaded run."""
        if (
            self._research_run_id.get().strip()
            != self._research_persisted_contradiction_run_id
        ):
            self._clear_research_persisted_contradictions()
            return None
        selected_index = self._research_persisted_contradiction_selector.current()
        if (
            not 0
            <= selected_index
            < len(self._research_persisted_contradiction_records)
        ):
            return None
        return self._research_persisted_contradiction_records[selected_index]

    def _use_selected_persisted_contradiction_pair(self) -> None:
        """Copy one recorded exact claim pair without editing its authored note."""
        record = self._selected_persisted_research_contradiction()
        if record is None:
            self._status.set("Select a recorded contradiction first.")
            return
        self._research_claim_contradiction_ids.set(", ".join(record.claim_ids))
        self._status.set(
            "recorded claim pair copied; note unchanged; nothing requested or saved"
        )

    def _render_research_persisted_comparison_note_selector(
        self,
        run: ResearchRun,
    ) -> None:
        """Render recorded comparison notes from the loaded exact run snapshot."""
        records = run.comparison_notes
        self._research_persisted_comparison_note_records = records
        self._research_persisted_comparison_note_run_id = run.run_id
        labels = tuple(
            self._research_persisted_comparison_note_label(record) for record in records
        )
        self._research_persisted_comparison_note_selector.configure(values=labels)
        if not records:
            self._research_persisted_comparison_note_choice.set("")
            self._research_persisted_comparison_note_references.set("")
            return
        self._research_persisted_comparison_note_selector.current(0)
        self._render_selected_persisted_comparison_note_references()

    @staticmethod
    def _research_persisted_comparison_note_label(
        record: ResearchSourceComparisonNoteRecord,
    ) -> str:
        """Show bounded authored text, time, and the exact comparison-note ID."""
        text = " ".join(record.text.split())
        if len(text) > 100:
            text = f"{text[:97]}..."
        return f"[{record.recorded_at.isoformat()}] {text} — {record.note_id}"

    @staticmethod
    def _research_persisted_comparison_note_reference_summary(
        record: ResearchSourceComparisonNoteRecord,
    ) -> str:
        """Expose every persisted exact reference without changing form fields."""
        return (
            f"Sources: {', '.join(record.source_document_ids)}\n"
            f"Evidence: {', '.join(record.evidence_ids)}\n"
            f"Assessments: {', '.join(record.assessment_ids)}"
        )

    def _selected_persisted_research_comparison_note(
        self,
    ) -> ResearchSourceComparisonNoteRecord | None:
        """Return only a comparison note bound to the selected loaded run."""
        if (
            self._research_run_id.get().strip()
            != self._research_persisted_comparison_note_run_id
        ):
            self._clear_research_persisted_comparison_notes()
            return None
        selected_index = self._research_persisted_comparison_note_selector.current()
        if (
            not 0
            <= selected_index
            < len(self._research_persisted_comparison_note_records)
        ):
            return None
        return self._research_persisted_comparison_note_records[selected_index]

    def _render_selected_persisted_comparison_note_references(self) -> None:
        """Refresh only the read-only exact-reference summary."""
        record = self._selected_persisted_research_comparison_note()
        if record is None:
            self._research_persisted_comparison_note_references.set("")
            return
        self._research_persisted_comparison_note_references.set(
            self._research_persisted_comparison_note_reference_summary(record)
        )

    def _select_persisted_research_comparison_note(
        self,
        _event: object | None = None,
    ) -> None:
        """Select one recorded note without editing fields or starting work."""
        record = self._selected_persisted_research_comparison_note()
        if record is None:
            self._research_persisted_comparison_note_references.set("")
            self._status.set("Select a recorded comparison note first.")
            return
        self._research_persisted_comparison_note_references.set(
            self._research_persisted_comparison_note_reference_summary(record)
        )
        self._status.set(
            f"recorded comparison note selected: {record.note_id}; no action started"
        )

    def _use_selected_persisted_comparison_note_sources(self) -> None:
        """Copy only one recorded note's exact ordered source references."""
        record = self._selected_persisted_research_comparison_note()
        if record is None:
            self._status.set("Select a recorded comparison note first.")
            return
        self._research_comparison_document_ids.set(
            ", ".join(record.source_document_ids)
        )
        self._status.set(
            "recorded comparison source IDs copied; other fields unchanged; "
            "nothing requested or saved"
        )

    def _use_selected_persisted_comparison_note_evidence(self) -> None:
        """Copy only one recorded note's exact evidence references."""
        record = self._selected_persisted_research_comparison_note()
        if record is None:
            self._status.set("Select a recorded comparison note first.")
            return
        self._research_comparison_evidence_ids.set(", ".join(record.evidence_ids))
        self._status.set(
            "recorded comparison evidence IDs copied; other fields unchanged; "
            "nothing requested or saved"
        )

    def _use_selected_persisted_comparison_note_assessments(self) -> None:
        """Copy only one recorded note's exact assessment references."""
        record = self._selected_persisted_research_comparison_note()
        if record is None:
            self._status.set("Select a recorded comparison note first.")
            return
        self._research_comparison_assessment_ids.set(", ".join(record.assessment_ids))
        self._status.set(
            "recorded comparison assessment IDs copied; other fields unchanged; "
            "nothing requested or saved"
        )

    def _render_research_source_selector(self, run: ResearchRun) -> None:
        """Render accepted sources from the already loaded exact run snapshot."""
        previous_run_id = self._research_source_run_id
        active_source_id = (
            self._active_research_source_document_id
            if previous_run_id == run.run_id
            else ""
        )
        self._research_source_catalog = run.sources
        self._research_source_run_id = run.run_id
        self._research_source_coverage_filter.set(ResearchSourceCoverageFacet.ALL.value)
        if not run.sources:
            self._active_research_source_document_id = ""
            self._research_source_coverage_summary.set(
                "No accepted sources are available."
            )
            self._render_visible_research_sources(run, ())
            return
        if active_source_id not in {source.document_id for source in run.sources}:
            active_source_id = run.sources[0].document_id
        self._active_research_source_document_id = active_source_id
        self._research_source_coverage_summary.set(
            f"All {len(run.sources)} accepted sources are shown."
        )
        self._render_visible_research_sources(run, run.sources)

    def _apply_research_source_coverage_filter(
        self,
        _event: object | None = None,
    ) -> None:
        """Apply one local accepted-source coverage view without a runtime call."""
        try:
            facet = ResearchSourceCoverageFacet(
                self._research_source_coverage_filter.get()
            )
        except ValueError:
            self._research_source_coverage_summary.set(
                "Source view is invalid; accepted sources are unchanged."
            )
            self._status.set("Accepted-source coverage view is invalid.")
            return
        selected_run = next(
            (
                run
                for run in self._research_runs
                if run.run_id == self._research_source_run_id
            ),
            None,
        )
        if (
            selected_run is None
            or selected_run.sources != self._research_source_catalog
        ):
            self._research_source_coverage_summary.set(
                "Accepted-source snapshot is stale; refresh research runs."
            )
            self._status.set("Accepted-source snapshot is stale.")
            return
        visible_sources = self._filter_research_sources_by_coverage(
            self._research_source_catalog,
            selected_run.evidence,
            facet,
        )
        self._render_visible_research_sources(selected_run, visible_sources)
        total_count = len(self._research_source_catalog)
        visible_count = len(visible_sources)
        if total_count == 0:
            summary = "No accepted sources are available."
        elif facet is ResearchSourceCoverageFacet.ALL:
            summary = f"All {total_count} accepted sources are shown."
        elif visible_sources:
            summary = (
                f"{visible_count} of {total_count} accepted sources have no "
                "recorded evidence."
            )
        else:
            summary = (
                f"All {total_count} accepted sources have recorded evidence; "
                "no sources match this view."
            )
        self._research_source_coverage_summary.set(summary)
        active_hidden = bool(self._active_research_source_document_id) and all(
            source.document_id != self._active_research_source_document_id
            for source in visible_sources
        )
        hidden_status = "; active source hidden" if active_hidden else ""
        self._status.set(
            f"accepted source view: {facet.value}; {visible_count} of "
            f"{total_count} shown; active source unchanged{hidden_status}"
        )

    def _render_visible_research_sources(
        self,
        run: ResearchRun,
        visible_sources: tuple[ResearchSourceRecord, ...],
    ) -> None:
        """Render one source view while retaining an exact hidden active ID."""
        self._research_sources = visible_sources
        self._research_source_selector.configure(
            values=tuple(
                self._research_source_label(source) for source in visible_sources
            )
        )
        selected_index = next(
            (
                index
                for index, source in enumerate(visible_sources)
                if source.document_id == self._active_research_source_document_id
            ),
            None,
        )
        if selected_index is None:
            self._research_source_choice.set("")
            self._clear_research_evidence()
            self._clear_research_assessments()
            return
        self._research_source_selector.current(selected_index)
        selected_source = visible_sources[selected_index]
        self._render_research_evidence_selector(run, selected_source)
        self._render_research_assessment_selector(run, selected_source)

    @staticmethod
    def _filter_research_sources_by_coverage(
        sources: tuple[ResearchSourceRecord, ...],
        evidence: tuple[ResearchEvidenceRecord, ...],
        facet: ResearchSourceCoverageFacet,
    ) -> tuple[ResearchSourceRecord, ...]:
        """Return stable source membership for one exact local coverage facet."""
        if facet is ResearchSourceCoverageFacet.ALL:
            return sources
        represented_source_ids = {record.source_document_id for record in evidence}
        return tuple(
            source
            for source in sources
            if source.document_id not in represented_source_ids
        )

    @staticmethod
    def _research_source_label(source: ResearchSourceRecord) -> str:
        """Keep the exact document ID visible beside a bounded source title."""
        title = source.title
        if len(title) > 80:
            title = f"{title[:77]}..."
        return f"{title} — {source.document_id}"

    def _selected_research_source(self) -> ResearchSourceRecord | None:
        """Return only a source tied to the currently selected loaded run."""
        if self._research_run_id.get().strip() != self._research_source_run_id:
            self._clear_research_sources()
            return None
        selected_index = self._research_source_selector.current()
        if not 0 <= selected_index < len(self._research_sources):
            return None
        return self._research_sources[selected_index]

    def _select_research_source(self, _event: object | None = None) -> None:
        """Select one accepted source without editing fields or starting work."""
        source = self._selected_research_source()
        selected_run = next(
            (
                run
                for run in self._research_runs
                if run.run_id == self._research_source_run_id
            ),
            None,
        )
        if source is None or selected_run is None:
            self._clear_research_evidence()
            self._clear_research_assessments()
            self._status.set("Select an accepted source first.")
            return
        self._active_research_source_document_id = source.document_id
        self._render_research_evidence_selector(selected_run, source)
        self._render_research_assessment_selector(selected_run, source)
        self._status.set(
            f"accepted source selected: {source.document_id}; no action started"
        )

    def _render_research_evidence_selector(
        self,
        run: ResearchRun,
        source: ResearchSourceRecord,
    ) -> None:
        """Render source-owned evidence from one already loaded run snapshot."""
        records = tuple(
            record
            for record in run.evidence
            if record.source_document_id == source.document_id
        )
        self._research_evidence_records = records
        self._research_evidence_run_id = run.run_id
        self._research_evidence_source_document_id = source.document_id
        labels = tuple(self._research_evidence_label(record) for record in records)
        self._research_evidence_selector.configure(values=labels)
        if not records:
            self._research_evidence_choice.set("")
            return
        self._research_evidence_selector.current(0)

    @staticmethod
    def _research_evidence_label(record: ResearchEvidenceRecord) -> str:
        """Keep an exact evidence ID visible beside one bounded-line excerpt."""
        excerpt = " ".join(record.excerpt.split())
        if len(excerpt) > 100:
            excerpt = f"{excerpt[:97]}..."
        return f"{excerpt} — {record.evidence_id}"

    def _render_research_assessment_selector(
        self,
        run: ResearchRun,
        source: ResearchSourceRecord,
    ) -> None:
        """Render source-owned authored assessments from one loaded snapshot."""
        records = tuple(
            record
            for record in run.assessments
            if record.source_document_id == source.document_id
        )
        superseded_ids = {
            record.supersedes_assessment_id
            for record in run.assessments
            if record.supersedes_assessment_id is not None
        }
        current_ids = frozenset(
            record.assessment_id
            for record in records
            if record.assessment_id not in superseded_ids
        )
        self._research_assessment_records = records
        self._research_current_assessment_ids = current_ids
        self._research_assessment_run_id = run.run_id
        self._research_assessment_source_document_id = source.document_id
        labels = tuple(
            self._research_assessment_label(
                record,
                is_current=record.assessment_id in current_ids,
            )
            for record in records
        )
        self._research_assessment_selector.configure(values=labels)
        if not records:
            self._research_assessment_choice.set("")
            return
        selected_index = next(
            (
                index
                for index, record in enumerate(records)
                if record.assessment_id in current_ids
            ),
            0,
        )
        self._research_assessment_selector.current(selected_index)

    @staticmethod
    def _research_assessment_label(
        record: ResearchSourceAssessmentRecord,
        *,
        is_current: bool,
    ) -> str:
        """Show audit state, bounded authored text, and the exact assessment ID."""
        text = " ".join(record.text.split())
        if len(text) > 100:
            text = f"{text[:97]}..."
        state = "current" if is_current else "superseded"
        return f"[{state}] {text} — {record.assessment_id}"

    def _selected_research_assessment(
        self,
    ) -> ResearchSourceAssessmentRecord | None:
        """Return only an assessment bound to the current exact run and source."""
        source = self._selected_research_source()
        if (
            source is None
            or self._research_run_id.get().strip() != self._research_assessment_run_id
            or source.document_id != self._research_assessment_source_document_id
        ):
            self._clear_research_assessments()
            return None
        selected_index = self._research_assessment_selector.current()
        if not 0 <= selected_index < len(self._research_assessment_records):
            return None
        return self._research_assessment_records[selected_index]

    def _use_selected_research_assessment_as_correction_target(self) -> None:
        """Copy one current same-source ID into the manual predecessor field."""
        record = self._selected_research_assessment()
        if record is None:
            self._status.set("Select an authored assessment first.")
            return
        if record.assessment_id not in self._research_current_assessment_ids:
            self._status.set("Only a current assessment can be corrected.")
            return
        if self._research_source_document_id.get().strip() != record.source_document_id:
            self._status.set("Use the accepted source for assessment first.")
            return
        self._research_assessment_supersedes_id.set(record.assessment_id)
        self._status.set(
            "assessment ID copied as correction target; nothing requested or saved"
        )

    def _add_selected_research_assessment_to_comparison(self) -> None:
        """Append one current same-source assessment ID to the manual comparison."""
        record = self._selected_research_assessment()
        if record is None:
            self._status.set("Select an authored assessment first.")
            return
        if record.assessment_id not in self._research_current_assessment_ids:
            self._status.set("Only a current assessment can be compared.")
            return
        comparison_source_ids = {
            value.strip()
            for value in self._research_comparison_document_ids.get().split(",")
            if value.strip()
        }
        if record.source_document_id not in comparison_source_ids:
            self._status.set("Add the accepted source to the comparison first.")
            return
        current_ids = tuple(
            value.strip()
            for value in self._research_comparison_assessment_ids.get().split(",")
            if value.strip()
        )
        if record.assessment_id in current_ids:
            self._status.set(
                "assessment ID is already in the comparison; nothing changed"
            )
            return
        if len(current_ids) >= MAX_COMPARISON_NOTE_ASSESSMENTS:
            self._status.set(
                "The comparison accepts at most "
                f"{MAX_COMPARISON_NOTE_ASSESSMENTS} assessment IDs."
            )
            return
        self._research_comparison_assessment_ids.set(
            ", ".join((*current_ids, record.assessment_id))
        )
        self._status.set(
            "assessment ID added to comparison; nothing requested or saved"
        )

    def _selected_research_evidence(self) -> ResearchEvidenceRecord | None:
        """Return only evidence bound to the current exact run and source."""
        source = self._selected_research_source()
        if (
            source is None
            or self._research_run_id.get().strip() != self._research_evidence_run_id
            or source.document_id != self._research_evidence_source_document_id
        ):
            self._clear_research_evidence()
            return None
        selected_index = self._research_evidence_selector.current()
        if not 0 <= selected_index < len(self._research_evidence_records):
            return None
        return self._research_evidence_records[selected_index]

    def _add_selected_research_evidence_to_assessment(self) -> None:
        """Append exact same-source evidence to the manual assessment field."""
        record = self._selected_research_evidence()
        if record is None:
            self._status.set("Select recorded evidence first.")
            return
        if self._research_source_document_id.get().strip() != record.source_document_id:
            self._status.set("Use the accepted source for assessment first.")
            return
        self._append_research_evidence_id(
            record,
            self._research_assessment_evidence_ids,
            maximum=None,
            destination="assessment",
        )

    def _add_selected_research_evidence_to_claim(self) -> None:
        """Append exact evidence to the manual claim field within its bound."""
        record = self._selected_research_evidence()
        if record is None:
            self._status.set("Select recorded evidence first.")
            return
        self._append_research_evidence_id(
            record,
            self._research_claim_evidence_ids,
            maximum=MAX_RESEARCH_CLAIM_EVIDENCE,
            destination="claim",
        )

    def _add_selected_research_evidence_to_comparison(self) -> None:
        """Append exact evidence only when its source is in the comparison."""
        record = self._selected_research_evidence()
        if record is None:
            self._status.set("Select recorded evidence first.")
            return
        comparison_source_ids = {
            value.strip()
            for value in self._research_comparison_document_ids.get().split(",")
            if value.strip()
        }
        if record.source_document_id not in comparison_source_ids:
            self._status.set("Add the accepted source to the comparison first.")
            return
        self._append_research_evidence_id(
            record,
            self._research_comparison_evidence_ids,
            maximum=MAX_COMPARISON_NOTE_EVIDENCE,
            destination="comparison",
        )

    def _append_research_evidence_id(
        self,
        record: ResearchEvidenceRecord,
        target: tk.StringVar,
        *,
        maximum: int | None,
        destination: str,
    ) -> None:
        """Append one unique exact ID without invoking any runtime boundary."""
        current_ids = tuple(
            value.strip() for value in target.get().split(",") if value.strip()
        )
        if record.evidence_id in current_ids:
            self._status.set(
                f"evidence ID is already in the {destination}; nothing changed"
            )
            return
        if maximum is not None and len(current_ids) >= maximum:
            self._status.set(
                f"The {destination} accepts at most {maximum} evidence IDs."
            )
            return
        target.set(", ".join((*current_ids, record.evidence_id)))
        self._status.set(
            f"evidence ID added to {destination}; nothing requested or saved"
        )

    def _use_selected_research_source_for_assessment(self) -> None:
        """Copy one exact source ID into the manual assessment field only."""
        source = self._selected_research_source()
        if source is None:
            self._status.set("Select an accepted source first.")
            return
        self._research_source_document_id.set(source.document_id)
        self._status.set(
            "accepted source ID copied for assessment; nothing requested or saved"
        )

    def _add_selected_research_source_to_comparison(self) -> None:
        """Append one exact source ID to the manual comparison field only."""
        source = self._selected_research_source()
        if source is None:
            self._status.set("Select an accepted source first.")
            return
        current_ids = tuple(
            value.strip()
            for value in self._research_comparison_document_ids.get().split(",")
            if value.strip()
        )
        if source.document_id in current_ids:
            self._status.set(
                "accepted source ID is already in the comparison; nothing changed"
            )
            return
        if len(current_ids) >= 5:
            self._status.set("A research source comparison accepts at most 5 IDs.")
            return
        self._research_comparison_document_ids.set(
            ", ".join((*current_ids, source.document_id))
        )
        self._status.set(
            "accepted source ID added to comparison; nothing requested or saved"
        )

    def _clear_research_sources(self) -> None:
        """Discard the run-bound source presentation without editing form fields."""
        self._clear_research_evidence()
        self._clear_research_assessments()
        self._research_source_catalog = ()
        self._research_sources = ()
        self._research_source_run_id = ""
        self._active_research_source_document_id = ""
        self._research_source_coverage_filter.set(ResearchSourceCoverageFacet.ALL.value)
        self._research_source_coverage_summary.set("No accepted sources are available.")
        self._research_source_choice.set("")
        self._research_source_selector.configure(values=())

    def _clear_research_evidence(self) -> None:
        """Discard source-bound evidence presentation without editing form fields."""
        self._research_evidence_records = ()
        self._research_evidence_run_id = ""
        self._research_evidence_source_document_id = ""
        self._research_evidence_choice.set("")
        self._research_evidence_selector.configure(values=())

    def _clear_research_assessments(self) -> None:
        """Discard source-bound assessment views without editing form fields."""
        self._research_assessment_records = ()
        self._research_current_assessment_ids = frozenset()
        self._research_assessment_run_id = ""
        self._research_assessment_source_document_id = ""
        self._research_assessment_choice.set("")
        self._research_assessment_selector.configure(values=())

    def _clear_research_claims(self) -> None:
        """Discard run-bound claim views without editing manual form fields."""
        self._research_claim_records = ()
        self._research_current_claim_ids = frozenset()
        self._research_claim_run_id = ""
        self._research_claim_choice.set("")
        self._research_claim_selector.configure(values=())

    def _clear_research_persisted_contradictions(self) -> None:
        """Discard run-bound contradiction views without editing manual fields."""
        self._research_persisted_contradiction_records = ()
        self._research_persisted_contradiction_run_id = ""
        self._research_persisted_contradiction_choice.set("")
        self._research_persisted_contradiction_selector.configure(values=())

    def _clear_research_persisted_comparison_notes(self) -> None:
        """Discard run-bound comparison-note views without editing manual fields."""
        self._research_persisted_comparison_note_records = ()
        self._research_persisted_comparison_note_run_id = ""
        self._research_persisted_comparison_note_choice.set("")
        self._research_persisted_comparison_note_references.set("")
        self._research_persisted_comparison_note_selector.configure(values=())

    def _clear_research_run_dependent_presentations(self) -> None:
        """Clear only ephemeral views tied to a previous exact run."""
        self._clear_research_sources()
        self._clear_research_claims()
        self._clear_research_persisted_contradictions()
        self._clear_research_persisted_comparison_notes()
        self._clear_research_candidates()
        self._clear_research_claim_contradiction_proposals()
        self._research_markdown_export_preview = None

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

    def _preview_research_claim_contradictions(self) -> None:
        """Show only persisted user-reviewed contradiction relationships."""
        try:
            response = self._controller.preview_research_claim_contradictions(
                self._research_run_id.get()
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _suggest_research_claim_contradictions(self) -> None:
        """Request non-persistent candidates on the provider worker."""
        self._clear_research_claim_contradiction_proposals()
        run_id = self._research_run_id.get()
        cancellation_signal = CancellationSignal()
        self._start_request(
            lambda: self._controller.suggest_research_claim_contradictions(
                run_id,
                cancellation_token=cancellation_signal,
            ),
            self._render_research_claim_contradiction_proposals,
            "research claim contradiction suggestion",
            cancellation_signal=cancellation_signal,
        )

    def _render_research_claim_contradiction_proposals(
        self,
        response: BrainResponse,
    ) -> None:
        """Expose successful candidates only for the still-selected exact run."""
        self._append_response(response)
        self._clear_research_claim_contradiction_proposals()
        preview = response.research_claim_contradiction_proposal_preview
        selected_run_id = self._research_run_id.get().strip()
        if (
            not response.success
            or preview is None
            or preview.run_id != selected_run_id
            or not preview.candidates
        ):
            return
        self._research_claim_contradiction_proposal_run_id = preview.run_id
        self._research_claim_contradiction_proposals = preview.candidates
        labels = tuple(
            f"{index}. {candidate.claim_ids[0]} ↔ {candidate.claim_ids[1]}"
            for index, candidate in enumerate(preview.candidates, start=1)
        )
        self._research_claim_contradiction_proposal_selector.configure(values=labels)
        self._research_claim_contradiction_proposal_selector.current(0)

    def _clear_research_claim_contradiction_proposals(self) -> None:
        """Discard ephemeral model suggestions without touching authored fields."""
        self._research_claim_contradiction_proposal_run_id = ""
        self._research_claim_contradiction_proposals = ()
        self._research_claim_contradiction_proposal.set("")
        self._research_claim_contradiction_proposal_selector.configure(values=())

    def _use_selected_research_claim_contradiction_proposal(self) -> None:
        """Copy exactly one current pair into the manual form without recording."""
        selected_index = self._research_claim_contradiction_proposal_selector.current()
        if (
            self._research_run_id.get().strip()
            != self._research_claim_contradiction_proposal_run_id
        ):
            self._clear_research_claim_contradiction_proposals()
            self._status.set("Request and select a contradiction suggestion first.")
            return
        if not 0 <= selected_index < len(self._research_claim_contradiction_proposals):
            self._status.set("Request and select a contradiction suggestion first.")
            return
        candidate = self._research_claim_contradiction_proposals[selected_index]
        self._research_claim_contradiction_ids.set(", ".join(candidate.claim_ids))
        self._status.set("suggested claim IDs copied; note unchanged; nothing recorded")

    def _preview_and_record_research_claim_contradiction(self) -> None:
        """Preview, confirm, and revalidate one claim contradiction."""
        values = (
            self._research_run_id.get(),
            self._research_claim_contradiction_ids.get(),
            self._research_claim_contradiction_note.get(),
        )
        try:
            preview_response = (
                self._controller.preview_research_claim_contradiction_write(*values)
            )
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(preview_response)
        preview = preview_response.research_claim_contradiction_write_preview
        if not preview_response.success or preview is None or not preview.allowed:
            return
        if not messagebox.askyesno(
            "Save user-reviewed claim contradiction?",
            (
                f"{preview_response.message}\n\n"
                "This appends your contradiction note and the exact two claim and "
                "evidence references to the research audit record. Hypatia does not "
                "decide which claim is true or rewrite either claim. Continue?"
            ),
            parent=self._root,
        ):
            self._status.set("research claim contradiction: not saved")
            return
        response = self._controller.record_research_claim_contradiction(*values)
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
        selected_index = selected_indices[0]
        if selected_index >= len(self._session_summaries):
            return
        self._session_id.set(self._session_summaries[selected_index].session_id)

    def _render_session_summaries(self, response: BrainResponse) -> None:
        """Show only current successful Brain data, never a stale local copy."""
        self._session_list.delete(0, tk.END)
        self._session_summaries = []
        if not response.success:
            self._session_list.insert(tk.END, "Sessions are currently unavailable.")
            return
        self._session_summaries = response.session_summaries
        if not self._session_summaries:
            self._session_list.insert(tk.END, "No saved sessions yet.")
            return
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
