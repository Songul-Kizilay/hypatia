"""Tkinter presentation for the deliberately narrow first desktop shell."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from time import monotonic
from tkinter import filedialog, font, messagebox, scrolledtext, ttk
from typing import Literal, Protocol

from brain.BrainResponse import BrainResponse
from brain.SessionSummary import SessionSummary
from core.CancellationSignal import CancellationSignal
from desktop.DesktopController import DesktopController
from desktop.DesktopRequestRunner import DesktopRequestRunner
from desktop.FilesystemContentPreview import FilesystemContentPreview
from desktop.MarkdownTextSegments import (
    MarkdownStyle,
    markdown_segments,
)
from desktop.ResearchStateRefreshSignal import ResearchStateRefreshSignal
from desktop.ResearchWorkspaceReadModel import (
    ResearchRunSort,
    ResearchRunStatusFacet,
    ResearchSourceCoverageFacet,
    ResearchWorkspaceReadModel,
)
from desktop.SimpleResearchActivity import SimpleResearchActivity
from desktop.SimpleResearchPhrasebook import phrase as simple_phrase
from desktop.SimpleResearchReadModel import SimpleResearchReadModel
from desktop.SimpleSourceCard import SimpleSourceCard
from desktop.ToolConsoleController import ToolConsoleController
from desktop.ToolConsoleEntry import ToolConsoleEntry
from desktop.ToolRunView import ToolRunView
from eventbus.EventBus import EventBus
from knowledge.KnowledgeCitation import KnowledgeCitation
from research.HypothesisEvidenceRelation import HypothesisEvidenceRelation
from research.RankedResearchSourceDiscovery import ranked_candidates
from research.ResearchAttemptRecoveryDecision import (
    ResearchAttemptRecoveryDecision,
)
from research.ResearchAttemptResolution import ResearchAttemptResolution
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
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunMarkdownExportPreview import (
    ResearchRunMarkdownExportPreview,
)
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceComparisonNoteRecord import (
    MAX_COMPARISON_NOTE_ASSESSMENTS,
    MAX_COMPARISON_NOTE_EVIDENCE,
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceRecord import ResearchSourceRecord
from research.ResearchSourceUsefulness import ResearchSourceUsefulness
from research.SourceIdentity import identity_of
from research.SourceLoadStage import SourceLoadStage
from research.SourceOrigin import origin_of
from research.SourceReputationLedger import SourceReputationLedger
from response.ResponseLanguage import ResponseLanguage, detect_response_language
from security.VulnerabilityFamilyGraph import MAX_TRAVERSAL_DEPTH
from security.VulnerabilityRelationKind import VulnerabilityRelationKind

_WEAKNESS_PANEL_NOTE = (
    "A weakness class is a concept, never a finding. There is nowhere here to "
    "name a host, a product, a version, or a payload, and nothing on this tab "
    "scans, probes, or reaches any system."
)
_WEAKNESS_IDLE_STATUS = "Nothing has been recorded or looked up yet."
_LEARNING_IDLE_STATUS = "Nothing has been proposed, remembered, or recalled yet."
_LEARNING_PANEL_NOTE = (
    "Hypotheses record what you expect and what would change your mind. "
    "Lessons record what did not work. Nothing on this tab decides that "
    "anything is true, and no status here means confirmed."
)
_HYPOTHESIS_DEFEATER_NOTE = (
    "Required. A conjecture that names nothing capable of counting against it "
    "will survive any amount of evidence, because nothing was ever allowed to "
    "threaten it."
)
_HYPOTHESIS_EVIDENCE_NOTE = (
    "Evidence must already be recorded in the run. Separate several IDs with "
    "commas or spaces. The same record cannot be entered on both sides."
)
_RECOVERY_PANEL_NOTE = (
    "This step is blocked because the operation may have run and Hypatia never "
    "saw its result. The attempt has already been charged. Anything you record "
    "here is kept as your account, not as something the provider returned, and "
    "supplying it does not mark the step completed. Abandoning it stops this "
    "step without claiming it succeeded or failed."
)
_INTERRUPTED_PANEL_NOTE = (
    "Previous attempt was interrupted. The external operation may have "
    "occurred. Its final result is unknown. The attempt has already been "
    "charged. Recording what you know runs nothing and retries nothing."
)


def _granted_authority_lines(budget, fit=None) -> list[str]:
    """Render the authority a confirmation is about to grant.

    Shared by both approval surfaces so the two cannot drift into describing
    the same thing differently. The budget passed in is always the one that
    will actually be recorded; where a fit is known it is shown beside it, and
    where none is known nothing is invented to fill the gap.
    """
    lines = [
        "This is the authority you are about to grant:",
        f"  step advances: {budget.max_step_advances}",
        f"  network operations: {budget.max_network_operations}",
        f"  seconds: {budget.max_seconds}",
    ]
    if fit is not None:
        lines.append("")
        lines.extend(f"  {line}" for line in fit.lines())
    return lines


_CURIOSITY_BUDGET_NOTE = (
    "This is the authority you are granting to this exact Hypatia-proposed "
    "plan. Hypatia did not choose it for itself. Leave a box blank to grant the "
    "standing default; Prepare shows what the plan needs beside what you are "
    "granting, and an approval too small to cover one attempt at every authored "
    "step is refused rather than granted."
)
_AUTHORIZATION_BUDGET_NOTE = (
    "This is the authority you are granting, not what Hypatia decided it may "
    "use. Leave a box blank to grant the standing default. Preview shows what "
    "the plan needs beside what you are granting; an approval that cannot cover "
    "one attempt at every authored step is refused rather than granted."
)
_EXECUTION_PANEL_NOTE = (
    "An execution that has already been started. Refresh shows its canonical "
    "state and what remains of the approved budget. Advance attempts exactly "
    "one step and then stops; it never continues to the next step by itself. "
    "Cancelling is final, and returns neither the approval nor the budget "
    "already spent."
)
_APPROVAL_IDLE_STATUS = "Nothing has been approved yet."
_APPROVAL_PANEL_NOTE = (
    "Approving records that you permitted this exact plan. It starts no "
    "research on its own. The approval names the plan by content, so editing "
    "the plan afterwards makes the approval refuse it rather than silently "
    "covering the change.\n"
    "Starting is a separate, explicit act. It uses up one approval to begin "
    "one execution, which then does nothing further until you advance it. "
    "Nothing is scheduled, nothing repeats, and one execution cannot start "
    "another."
)
_REVIEW_IDLE_STATUS = "Nothing has been reviewed yet."
_REVIEW_PANEL_NOTE = (
    "Three ways of looking back at a run: how far each claim outruns its "
    "evidence, how the run went, and what was never asked. None of them "
    "changes a run, a claim, or a confidence."
)
_PROVIDER_COMPARISON_NOTE = (
    "Provider comparison shows the two result sets for this run's question side "
    "by side, each ranked within its own provider. It contacts nobody, merges "
    "no ranking, and names no winner: asking both providers takes one approved "
    "plan and two separate presses of Advance."
)
_PROVIDER_QUALITY_NOTE = (
    "Provider quality describes sources you chose to ask for, accept and "
    "assess. It selects no provider, changes no default, alters no ranking and "
    "updates no reputation, and it shows every denominator so a percentage over "
    "three sources cannot be mistaken for a measurement."
)
_CALIBRATION_NOTE = (
    "Calibration reports a mismatch and never adjusts one. What you are "
    "willing to assert is your judgement; a system that quietly downgraded it "
    "would be overruling you and calling it bookkeeping. It also reports where "
    "a claim rests on a source you yourself marked retracted, unrelated, "
    "useless or derivative, and it changes nothing about those either. A claim "
    "with no warnings has not been checked and found sound; it may simply rest "
    "on sources nobody has assessed."
)
_CURIOSITY_RULING_NOTE = (
    "A ruling records what you think is worth pursuing. It starts no research "
    "and reaches no source."
)
_LESSON_ADVISORY_NOTE = (
    "Recall is advisory. It blocks no plan, refuses no capability, and "
    "downgrades no claim. Something failing once is not a reason not to try it."
)
_WEAKNESS_RELATION_NOTE = (
    "Every relation is authored with a reason. Nothing here infers an edge "
    "from similar names, so the graph only ever holds connections a person "
    "was willing to explain."
)

_TOOL_IDLE_STATUS = "Nothing has been run yet."
_TOOL_NO_SELECTION = "Choose a capability first."
_TOOL_NO_ARGUMENTS = "This capability takes no arguments."
_TOOL_GRANT_NOTE = (
    "These effects are granted for this one run only. Nothing is remembered "
    "between runs or across restarts."
)
_FILESYSTEM_READ_CAPABILITY = "filesystem_read"
_CONTENT_PREVIEW_BANNER = (
    "LOCAL FILE PREVIEW - UNTRUSTED DATA - NO INSTRUCTION AUTHORITY"
)

_DEFAULT_FONT_SIZE = 12
_MINIMUM_FONT_SIZE = 10
_MAXIMUM_FONT_SIZE = 20
_DEFAULT_WINDOW_WIDTH = 1920
_DEFAULT_WINDOW_HEIGHT = 1080
_MINIMUM_WINDOW_WIDTH = 760
_MINIMUM_WINDOW_HEIGHT = 520
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
    "Plan draft",
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


def _initial_window_size(
    screen_width: int,
    screen_height: int,
) -> tuple[int, int]:
    """Prefer 1920x1080 while fitting smaller screens without overflow."""
    if (
        isinstance(screen_width, bool)
        or not isinstance(screen_width, int)
        or screen_width <= 0
        or isinstance(screen_height, bool)
        or not isinstance(screen_height, int)
        or screen_height <= 0
    ):
        raise ValueError("Screen dimensions must be positive integers.")
    return (
        min(_DEFAULT_WINDOW_WIDTH, screen_width),
        min(_DEFAULT_WINDOW_HEIGHT, screen_height),
    )


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

    #: Set for every constructed window. Declared at class level because
    #: focused unit tests build bare instances through ``object.__new__`` to
    #: exercise one method, and the polling loop must stay safe for those
    #: rather than requiring every such test to know about this subsystem.
    _research_refresh_signal: ResearchStateRefreshSignal | None = None

    #: Simple mode state, declared here for the same reason: focused tests build
    #: bare instances to exercise one method, and a Simple-mode handler must not
    #: require the whole window to have been constructed.
    _simple_run_id: str = ""
    _simple_run: ResearchRun | None = None
    _simple_discovery_id: str = ""
    _simple_cards: tuple[SimpleSourceCard, ...] = ()
    _simple_activity: SimpleResearchActivity = SimpleResearchActivity.IDLE
    _simple_last_stage: SourceLoadStage | None = None
    _simple_language: ResponseLanguage = ResponseLanguage.ENGLISH
    _pending_research_question: str = ""

    #: Present only when an operator-facing tool console was composed for
    #: this window. None means the Tools tab is absent, not disabled: a
    #: panel that could not run anything should not offer to.
    _tool_console: ToolConsoleController | None = None
    _tool_entries: tuple[ToolConsoleEntry, ...] = ()

    #: True only when this installation keeps a durable weakness taxonomy. The
    #: Security tab follows the same rule as the Tools tab: absent rather than
    #: present-and-forgetful, because a panel that records classes into a store
    #: that does not exist would lose them at the next restart without saying so.
    _weakness_graph_enabled: bool = False

    #: The learning surfaces follow the same rule, and separately. Each is a
    #: distinct opt-in with its own store, so one being kept says nothing about
    #: the other, and a section for an absent store would collect work that
    #: never survives a restart.
    _hypothesis_enabled: bool = False
    _failure_memory_enabled: bool = False

    #: Reflection and curiosity keep history, so each follows the same rule.
    #: Calibration keeps nothing — it derives its report from the run on every
    #: request — so it needs no opt-in and is always offered where runs exist.
    _reflection_enabled: bool = False
    _curiosity_enabled: bool = False

    #: Recording an approval starts nothing, but it is the first durable step
    #: toward work that would. Absent unless the runtime keeps approvals, on
    #: the same rule every other durable engine here follows.
    _plan_authorization_enabled: bool = False

    def __init__(
        self,
        controller: DesktopController,
        root: tk.Tk | None = None,
        event_bus: EventBus | None = None,
        tool_console: ToolConsoleController | None = None,
        weakness_graph_enabled: bool = False,
        hypothesis_enabled: bool = False,
        failure_memory_enabled: bool = False,
        reflection_enabled: bool = False,
        curiosity_enabled: bool = False,
        plan_authorization_enabled: bool = False,
    ) -> None:
        self._controller = controller
        self._tool_console = tool_console
        self._weakness_graph_enabled = weakness_graph_enabled
        self._hypothesis_enabled = hypothesis_enabled
        self._failure_memory_enabled = failure_memory_enabled
        self._reflection_enabled = reflection_enabled
        self._curiosity_enabled = curiosity_enabled
        self._plan_authorization_enabled = plan_authorization_enabled
        self._root = root or tk.Tk()
        self._research_refresh_signal = ResearchStateRefreshSignal(event_bus)
        self._request_runner = DesktopRequestRunner()
        self._request_completion_handler: Callable[[object], None] | None = None
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
        self._research_source_catalog_summary = tk.StringVar(
            value=(
                "Accepted-source coverage — All: 0 · Without evidence: 0 · "
                "Without current assessment: 0"
            )
        )
        self._research_selected_source_summary = tk.StringVar(
            value=(
                "Selected-source records unavailable until an accepted source "
                "is selected."
            )
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
        self._research_source_usefulness = tk.StringVar(
            value=ResearchSourceUsefulness.UNKNOWN.value
        )
        self._research_source_applicability = tk.StringVar(
            value=ResearchSourceApplicability.UNKNOWN.value
        )
        self._research_source_independence = tk.StringVar(
            value=ResearchSourceIndependence.UNKNOWN.value
        )
        self._research_source_publication_status = tk.StringVar(
            value=ResearchSourcePublicationStatus.UNKNOWN.value
        )
        self._research_source_dimensions = tk.StringVar(value="")
        self._research_discovery_provider = tk.StringVar(
            value=ResearchDiscoveryProviderName.CROSSREF.value
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
        self._research_candidate_discovery_ids: tuple[str, ...] = ()
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
        # Simple mode keeps its own run context so an ordinary user is never
        # told to go to another tab and select something. It is a separate
        # field from the Advanced selector on purpose: sharing one would let a
        # click in Advanced silently redirect where a Simple load attaches.
        self._simple_run_id = ""
        self._simple_run: ResearchRun | None = None
        self._simple_discovery_id = ""
        self._simple_cards: tuple[SimpleSourceCard, ...] = ()
        self._simple_activity = SimpleResearchActivity.IDLE
        self._simple_last_stage: SourceLoadStage | None = None
        self._simple_language = ResponseLanguage.ENGLISH
        self._font_size = _DEFAULT_FONT_SIZE
        self._font_size_label = tk.StringVar()
        self._theme_mode = tk.StringVar(value=DesktopTheme.EYE_COMFORT.value)
        self._style = ttk.Style(self._root)
        if "clam" in self._style.theme_names():
            self._style.theme_use("clam")

        self._root.title("Hypatia")
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        window_width, window_height = _initial_window_size(
            screen_width,
            screen_height,
        )
        window_x = max((screen_width - window_width) // 2, 0)
        window_y = max((screen_height - window_height) // 2, 0)
        self._root.geometry(f"{window_width}x{window_height}+{window_x}+{window_y}")
        self._root.minsize(
            min(_MINIMUM_WINDOW_WIDTH, window_width),
            min(_MINIMUM_WINDOW_HEIGHT, window_height),
        )
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

        def present(value: object) -> None:
            if not isinstance(value, BrainResponse):
                raise TypeError("A Brain request returned the wrong result type.")
            on_success(value)

        self._start_bounded_action(
            action,
            present,
            label,
            cancellation_signal=cancellation_signal,
        )

    def _start_tool_request(
        self,
        action: Callable[[], ToolRunView],
        on_success: Callable[[ToolRunView], None],
        label: str,
    ) -> None:
        """Run one local Tool action through the shared single-flight worker."""

        def present(value: object) -> None:
            if not isinstance(value, ToolRunView):
                raise TypeError("A Tool request returned the wrong result type.")
            on_success(value)

        result = self._start_bounded_action(action, present, label)
        if result == "busy":
            self._tool_status.set("Hypatia is already processing a request.")
        elif result == "stopped":
            self._tool_status.set("Hypatia is closing.")
        elif result == "failed":
            self._tool_status.set("Local file read could not be started.")

    def _start_bounded_action(
        self,
        action: Callable[[], object],
        on_success: Callable[[object], None],
        label: str,
        *,
        cancellation_signal: CancellationSignal | None = None,
    ) -> Literal["started", "busy", "stopped", "failed"]:
        """Reserve the one desktop worker for one bounded local action."""
        if self._closing:
            self._status.set("Hypatia is closing.")
            return "stopped"
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
            return "started"
        if start_result == "busy":
            self._status.set("Hypatia is already processing a request.")
            return "busy"
        if start_result == "stopped":
            self._status.set("Hypatia is closing.")
            return "stopped"
        self._status.set("Desktop request could not be started.")
        return "failed"

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
            if handler is None:
                self._status.set("Desktop request failed.")
                continue
            try:
                handler(completion.value)
            except Exception:
                self._status.set("Desktop request failed.")
        self._apply_pending_research_refresh()
        if self._request_runner.is_running():
            self._update_request_progress()
        if not self._closing:
            self._root.after(_REQUEST_POLL_INTERVAL_MS, self._poll_requests)

    def _apply_pending_research_refresh(self) -> None:
        """Re-read runs the event bus reported as canonically changed.

        The event supplies only the identifier. Every number shown is read back
        from the store, so a payload can never put a count on screen that the
        store does not hold.
        """
        if self._research_refresh_signal is None:
            return
        changed = self._research_refresh_signal.drain()
        if not changed:
            return
        try:
            response = self._controller.list_research_runs()
        except Exception:
            self._status.set("Research state could not be refreshed.")
            return
        if not response.success or not response.research_runs:
            return
        self._refresh_research_run_presentations(tuple(response.research_runs))

    def _refresh_research_run_presentations(
        self,
        runs: tuple[ResearchRun, ...],
    ) -> None:
        """Redraw only the research presentations, keeping the selection.

        The selected run is looked up in the freshly read catalogue rather than
        reused, so the counts on screen and the run they describe come from the
        same read.
        """
        selected_run_id = self._research_run_id.get().strip()
        self._research_runs = runs
        visible = self._sort_research_runs(runs, self._current_research_run_sort())
        self._visible_research_runs = visible
        self._research_run_selector.configure(
            values=tuple(self._research_run_label(run) for run in visible)
        )
        self._research_run_catalog_summary.set(
            self._research_run_catalog_summary_text(runs)
        )
        if not selected_run_id:
            return
        selected = next(
            (run for run in visible if run.run_id == selected_run_id),
            None,
        )
        if selected is None:
            return
        self._render_research_source_selector(selected)
        self._render_research_claim_selector(selected)
        self._render_research_persisted_contradiction_selector(selected)
        self._render_research_persisted_comparison_note_selector(selected)
        read_view = ResearchWorkspaceReadModel.run_view(selected)
        self._research_run_summary.set(read_view.summary)
        self._research_run_context.set(read_view.context)
        self._research_run_progress.set(read_view.progress)
        self._research_workflow_snapshot.set(read_view.workflow_snapshot)
        self._research_evidence_coverage.set(read_view.evidence_coverage)
        self._research_assessment_coverage.set(read_view.assessment_coverage)
        self._research_run_metadata.set(read_view.metadata)

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
            self._clear_tool_content()
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
        self._clear_tool_content()
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
        simple_research_tab = ttk.Frame(self._workspace_tabs, padding=10)
        research_tab = ttk.Frame(self._workspace_tabs, padding=10)
        appearance_tab = ttk.Frame(self._workspace_tabs, padding=10)
        self._workspace_tabs.add(chat_tab, text="Chat")
        self._workspace_tabs.add(knowledge_tab, text="Knowledge")
        # Simple comes first and keeps the plain name. The detailed workflow is
        # not reduced, only relabelled: it is where identifiers, assessments,
        # claims, and failure stages stay, and nothing was removed from it.
        self._workspace_tabs.add(simple_research_tab, text="Research")
        self._workspace_tabs.add(research_tab, text="Research (Advanced)")
        tabs = [
            chat_tab,
            knowledge_tab,
            simple_research_tab,
            research_tab,
        ]
        # The Tools tab appears only when a console was composed. An empty
        # panel offering to run nothing would read as a feature that is broken
        # rather than a capability this installation was not given.
        if self._tool_console is not None:
            tools_tab = ttk.Frame(self._workspace_tabs, padding=10)
            self._workspace_tabs.add(tools_tab, text="Tools")
            tabs.append(tools_tab)
        # Same rule, different capability. Without a durable taxonomy the panel
        # would accept weakness classes and forget them at the next restart.
        if self._weakness_graph_enabled:
            security_tab = ttk.Frame(self._workspace_tabs, padding=10)
            self._workspace_tabs.add(security_tab, text="Security")
            tabs.append(security_tab)
        # Either opt-in earns the tab; each section still checks its own. The
        # two stores are independent, so a build that keeps hypotheses but not
        # lessons should show exactly the half it can honour.
        if self._learning_visible:
            learning_tab = ttk.Frame(self._workspace_tabs, padding=10)
            self._workspace_tabs.add(learning_tab, text="Learning")
            tabs.append(learning_tab)
        # Calibration alone earns this tab, because it stores nothing and is
        # available wherever runs are. Reflection and curiosity each add their
        # own section when kept.
        review_tab = ttk.Frame(self._workspace_tabs, padding=10)
        self._workspace_tabs.add(review_tab, text="Review")
        tabs.append(review_tab)
        self._workspace_tabs.add(appearance_tab, text="Appearance")
        tabs.append(appearance_tab)
        for tab in tabs:
            tab.columnconfigure(0, weight=1)
        self._build_simple_research_tab(simple_research_tab)
        if self._tool_console is not None:
            self._build_tool_console_tab(tools_tab)
        if self._weakness_graph_enabled:
            self._build_security_tab(security_tab)
        if self._learning_visible:
            self._build_learning_tab(learning_tab)
        self._build_review_tab(review_tab)
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
        ttk.Label(
            accepted_source_frame,
            textvariable=self._research_source_catalog_summary,
            style="Hint.TLabel",
            anchor="w",
        ).grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(8, 0),
        )
        ttk.Button(
            accepted_source_frame,
            text="Show active source",
            command=self._show_active_research_source,
        ).grid(row=2, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(
            accepted_source_frame,
            textvariable=self._research_selected_source_summary,
            style="Hint.TLabel",
            anchor="w",
            justify="left",
            wraplength=850,
        ).grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        ttk.Label(accepted_source_frame, text="Recorded evidence").grid(
            row=4,
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
            row=4,
            column=1,
            columnspan=3,
            sticky="ew",
            pady=(8, 0),
        )
        ttk.Button(
            accepted_source_frame,
            text="Use in assessment",
            command=self._add_selected_research_evidence_to_assessment,
        ).grid(row=5, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(
            accepted_source_frame,
            text="Use in claim",
            command=self._add_selected_research_evidence_to_claim,
        ).grid(row=5, column=2, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            accepted_source_frame,
            text="Add to comparison",
            command=self._add_selected_research_evidence_to_comparison,
        ).grid(row=5, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(accepted_source_frame, text="Authored assessments").grid(
            row=6,
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
            row=6,
            column=1,
            columnspan=3,
            sticky="ew",
            pady=(8, 0),
        )
        ttk.Button(
            accepted_source_frame,
            text="Source details",
            command=self._show_selected_research_source_details,
        ).grid(row=7, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(
            accepted_source_frame,
            text="Use as correction target",
            command=self._use_selected_research_assessment_as_correction_target,
        ).grid(row=7, column=2, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            accepted_source_frame,
            text="Add to comparison",
            command=self._add_selected_research_assessment_to_comparison,
        ).grid(row=7, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
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
        research_plan_frame = ttk.Frame(
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
        self._research_analysis_tabs.add(
            research_plan_frame,
            text=_RESEARCH_ANALYSIS_TAB_TITLES[4],
        )
        for analysis_section in (
            research_saved_records_frame,
            research_comparison_frame,
            research_assessment_frame,
            research_claims_frame,
            research_plan_frame,
        ):
            analysis_section.columnconfigure(1, weight=1)
        research_plan_frame.columnconfigure(0, weight=1)
        research_plan_frame.columnconfigure(1, weight=1)
        research_plan_frame.rowconfigure(3, weight=1)
        research_plan_frame.rowconfigure(6, weight=1)
        ttk.Label(
            research_plan_frame,
            text=(
                "Draft only: write one ordered instruction per line. On the same "
                "line in Sources, enter optional exact document IDs separated by "
                "commas. Preview never saves or executes the plan."
            ),
            style="Hint.TLabel",
            wraplength=1100,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(research_plan_frame, text="Question").grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
        )
        ttk.Entry(
            research_plan_frame,
            textvariable=self._research_question,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        instruction_frame = ttk.LabelFrame(
            research_plan_frame,
            text="Ordered instructions — one step per line",
            padding=6,
        )
        instruction_frame.grid(row=3, column=0, sticky="nsew", padx=(0, 4))
        instruction_frame.columnconfigure(0, weight=1)
        instruction_frame.rowconfigure(0, weight=1)
        self._research_plan_instructions = scrolledtext.ScrolledText(
            instruction_frame,
            height=9,
            wrap=tk.WORD,
        )
        self._research_plan_instructions.grid(row=0, column=0, sticky="nsew")
        source_frame = ttk.LabelFrame(
            research_plan_frame,
            text="Sources — matching line; comma-separated exact IDs",
            padding=6,
        )
        source_frame.grid(row=3, column=1, sticky="nsew", padx=(4, 0))
        source_frame.columnconfigure(0, weight=1)
        source_frame.rowconfigure(0, weight=1)
        self._research_plan_source_ids = scrolledtext.ScrolledText(
            source_frame,
            height=9,
            wrap=tk.WORD,
        )
        self._research_plan_source_ids.grid(row=0, column=0, sticky="nsew")
        ttk.Button(
            research_plan_frame,
            text="Preview plan — no write",
            command=self._preview_research_plan_draft,
        ).grid(row=4, column=1, sticky="e", pady=(8, 8))
        # Reaches the same preview as the button above and nothing else. There
        # is no shortcut here: approving the plan and pressing Advance twice is
        # still what turns this into two requests.
        ttk.Button(
            research_plan_frame,
            text="Compare Crossref + NVD — preview only",
            command=self._preview_provider_comparison_plan,
        ).grid(row=4, column=0, sticky="w", pady=(8, 8))
        ttk.Label(research_plan_frame, text="Complete preview or rejection").grid(
            row=5,
            column=0,
            columnspan=2,
            sticky="w",
        )
        self._research_plan_preview = scrolledtext.ScrolledText(
            research_plan_frame,
            height=8,
            wrap=tk.WORD,
        )
        self._research_plan_preview.grid(
            row=6,
            column=0,
            columnspan=2,
            sticky="nsew",
            pady=(4, 0),
        )
        self._research_plan_preview.insert(
            tk.END,
            "No plan preview yet. Enter the authored draft and choose Preview plan.",
        )
        self._research_plan_preview.configure(state=tk.DISABLED)
        if self._plan_authorization_enabled:
            self._build_plan_approval_section(research_plan_frame)
            self._build_execution_control_section(research_plan_frame)
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
        # The choice is the operator's and it is made before the search, not
        # inferred from the question afterwards. Nothing queries both providers
        # and nothing falls back from one to the other: a provider that refuses
        # is reported as refusing, because a silent second search answers a
        # question the person did not ask.
        ttk.Combobox(
            research_sources_frame,
            textvariable=self._research_discovery_provider,
            values=tuple(provider.value for provider in ResearchDiscoveryProviderName),
            state="readonly",
            width=10,
        ).grid(row=3, column=2, sticky="ew", padx=(8, 0), pady=(8, 0))
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
        # Four separate answers rather than one quality score. A single number
        # would let "useful to me" and "methodologically sound" and "still
        # published" collapse into each other, and the whole point of asking is
        # that they are different questions with different answers.
        for offset, (label, variable, vocabulary) in enumerate(
            (
                (
                    "Usefulness (operator judgement)",
                    self._research_source_usefulness,
                    ResearchSourceUsefulness,
                ),
                (
                    "Applicability to this question (operator judgement)",
                    self._research_source_applicability,
                    ResearchSourceApplicability,
                ),
                (
                    "Independence (operator judgement)",
                    self._research_source_independence,
                    ResearchSourceIndependence,
                ),
                (
                    "Publication status (operator judgement)",
                    self._research_source_publication_status,
                    ResearchSourcePublicationStatus,
                ),
            )
        ):
            row = 3 + offset
            ttk.Label(research_assessment_frame, text=label).grid(
                row=row,
                column=0,
                sticky="w",
                pady=(8, 0),
            )
            ttk.Combobox(
                research_assessment_frame,
                textvariable=variable,
                values=tuple(value.value for value in vocabulary),
                state="readonly",
            ).grid(
                row=row,
                column=1,
                columnspan=3,
                sticky="ew",
                padx=(8, 0),
                pady=(8, 0),
            )
        # The separation, written out where a person reads it. Each dimension is
        # named with what produced it, because the failure this guards against
        # is somebody reading "Relevance: strong" as "this source is sound".
        ttk.Label(
            research_assessment_frame,
            textvariable=self._research_source_dimensions,
            justify="left",
        ).grid(
            row=7,
            column=0,
            columnspan=4,
            sticky="w",
            padx=(8, 8),
            pady=(8, 0),
        )
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
        self._configure_transcript_styles()
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
        # Offered only after chat has said it did not research something, and
        # it starts nothing: it carries the question to the Research panel as a
        # draft the user still has to start.
        self._research_this_button = ttk.Button(
            composer_frame,
            text=simple_phrase("research_this", ResponseLanguage.ENGLISH),
            command=self._research_this,
        )
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
        text_widgets = [self._transcript, self._composer]
        text_widgets.extend(
            widget
            for widget in (
                getattr(self, "_research_plan_instructions", None),
                getattr(self, "_research_plan_source_ids", None),
                getattr(self, "_research_plan_preview", None),
            )
            if widget is not None
        )
        for widget in text_widgets:
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
        self._offer_research_this(message, response)

    def _offer_research_this(self, message: str, response: BrainResponse) -> None:
        """Show a research offer when chat has just said it researched nothing.

        Only an offer. Ordinary chat stays non-networked, and this button does
        not change that: pressing it fills in the Research panel and stops.
        """
        kind = response.live_information_request
        wanted = kind is not None and kind.requires_live_research
        self._pending_research_question = message.strip() if wanted else ""
        if not hasattr(self, "_research_this_button"):
            return
        if wanted:
            self._research_this_button.grid(row=1, column=1, sticky="ew", pady=(6, 0))
        else:
            self._research_this_button.grid_remove()

    def _research_this(self) -> None:
        """Carry the last unresearched question into the Research panel."""
        if not self._pending_research_question:
            return
        self._offer_simple_research_handoff(self._pending_research_question)

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
        """Present an accepted network source only on the Tkinter event thread.

        The canonical re-read below reselects the run, and reselecting a run
        writes its own status line — "no action started" — which is precisely
        wrong after a load that was started and refused. The refused fetch was
        therefore reported for one instant and then relabelled as nothing having
        happened, leaving an operator watching an unchanged source count with no
        indication that their confirmation had been acted on at all.

        The outcome of this attempt is therefore restated last, after every
        refresh that could overwrite it. The refresh itself is kept: a refused
        load records a failure on the run, and that is a real change the
        operator should see counted.
        """
        self._append_response(response)
        try:
            canonical_response = self._controller.list_research_runs()
        except ValueError:
            canonical_response = None
        if canonical_response is not None and canonical_response.success:
            self._render_research_run_selector(tuple(canonical_response.research_runs))
        self._capture_accepted_research_source(response)
        self._status.set(
            "research candidate load: source attached"
            if response.success
            else "research candidate load: failed; no source was attached"
        )

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

    def _preview_provider_comparison_plan(self) -> None:
        """Draft the two-step comparison plan. Contact no provider.

        The comparison is two ordinary discovery steps in one plan, so it goes
        through the same preview, the same approval and the same two explicit
        advances as anything else. Pressing this reaches a preview.
        """
        self._start_request(
            lambda: self._controller.preview_provider_comparison_plan(
                self._research_question.get()
            ),
            self._complete_research_plan_draft_preview,
            "provider comparison plan preview",
        )

    def _preview_research_plan_draft(self) -> None:
        """Send only the explicit no-write plan-preview request."""
        question = self._research_question.get()
        instruction_lines = self._research_plan_instructions.get("1.0", "end-1c")
        source_id_lines = self._research_plan_source_ids.get("1.0", "end-1c")
        self._start_request(
            lambda: self._controller.preview_research_plan_draft(
                question,
                instruction_lines,
                source_id_lines,
            ),
            self._complete_research_plan_draft_preview,
            "research plan preview",
        )

    def _complete_research_plan_draft_preview(
        self,
        response: BrainResponse,
    ) -> None:
        """Show the complete ready or rejected runtime preview without confirmation."""
        self._research_plan_preview.configure(state=tk.NORMAL)
        self._research_plan_preview.delete("1.0", tk.END)
        self._research_plan_preview.insert(tk.END, response.message)
        self._research_plan_preview.see("1.0")
        self._research_plan_preview.configure(state=tk.DISABLED)
        self._append_response(response)

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
        """Delegate immutable catalog projection outside the Tkinter adapter."""
        return ResearchWorkspaceReadModel(runs).catalog_summary_text()

    @staticmethod
    def _filter_research_runs(
        runs: tuple[ResearchRun, ...],
        query: str,
    ) -> tuple[ResearchRun, ...]:
        """Delegate local matching outside the Tkinter adapter."""
        return ResearchWorkspaceReadModel(runs).filter_runs(query)

    @staticmethod
    def _filter_research_runs_by_status(
        runs: tuple[ResearchRun, ...],
        status_filter: ResearchRunStatus | None,
    ) -> tuple[ResearchRun, ...]:
        """Delegate exact lifecycle filtering outside the Tkinter adapter."""
        return ResearchWorkspaceReadModel(runs).filter_runs_by_status(status_filter)

    @staticmethod
    def _sort_research_runs(
        runs: tuple[ResearchRun, ...],
        mode: ResearchRunSort,
    ) -> tuple[ResearchRun, ...]:
        """Delegate deterministic ordering outside the Tkinter adapter."""
        return ResearchWorkspaceReadModel(runs).sort_runs(mode)

    @staticmethod
    def _research_run_label(run: ResearchRun) -> str:
        return ResearchWorkspaceReadModel.run_label(run)

    @staticmethod
    def _research_run_context_text(run: ResearchRun) -> str:
        """Identify the exact immutable run snapshot used by later tabs."""
        return ResearchWorkspaceReadModel.run_context_text(run)

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
        self._show_research_run_candidates(selected_run)
        self._render_research_source_selector(selected_run)
        self._render_research_claim_selector(selected_run)
        self._render_research_persisted_contradiction_selector(selected_run)
        self._render_research_persisted_comparison_note_selector(selected_run)
        read_view = ResearchWorkspaceReadModel.run_view(selected_run)
        self._research_run_summary.set(read_view.summary)
        self._research_run_context.set(read_view.context)
        self._research_run_progress.set(read_view.progress)
        self._research_workflow_snapshot.set(read_view.workflow_snapshot)
        self._research_evidence_coverage.set(read_view.evidence_coverage)
        self._research_assessment_coverage.set(read_view.assessment_coverage)
        self._research_run_metadata.set(read_view.metadata)
        self._status.set(
            f"research run selected: {selected_run.run_id}; no action started"
        )

    @staticmethod
    def _research_run_summary_text(run: ResearchRun) -> str:
        """Delegate the selected-run summary outside the Tkinter adapter."""
        return ResearchWorkspaceReadModel.run_summary_text(run)

    @staticmethod
    def _research_run_progress_text(run: ResearchRun) -> str:
        """Delegate complete selected-snapshot counts outside Tkinter."""
        return ResearchWorkspaceReadModel.run_progress_text(run)

    @staticmethod
    def _research_workflow_snapshot_text(run: ResearchRun) -> str:
        """Delegate the existing-stage projection outside Tkinter."""
        return ResearchWorkspaceReadModel.workflow_snapshot_text(run)

    @staticmethod
    def _research_evidence_coverage_text(run: ResearchRun) -> str:
        """Delegate evidence coverage projection outside Tkinter."""
        return ResearchWorkspaceReadModel.evidence_coverage_text(run)

    @staticmethod
    def _research_assessment_coverage_text(run: ResearchRun) -> str:
        """Delegate assessment coverage projection outside Tkinter."""
        return ResearchWorkspaceReadModel.assessment_coverage_text(run)

    @staticmethod
    def _current_research_assessment_source_ids(
        sources: tuple[ResearchSourceRecord, ...],
        assessments: tuple[ResearchSourceAssessmentRecord, ...],
    ) -> frozenset[str]:
        """Delegate current-assessment membership outside Tkinter."""
        return ResearchWorkspaceReadModel.current_assessment_source_ids(
            sources,
            assessments,
        )

    @staticmethod
    def _research_run_metadata_text(run: ResearchRun) -> str:
        """Delegate safe run metadata projection outside Tkinter."""
        return ResearchWorkspaceReadModel.run_metadata_text(run)

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
        self._research_source_catalog_summary.set(
            self._research_source_catalog_summary_text(run)
        )
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
            selected_run.assessments,
            facet,
        )
        self._render_visible_research_sources(selected_run, visible_sources)
        total_count = len(self._research_source_catalog)
        visible_count = len(visible_sources)
        if total_count == 0:
            summary = "No accepted sources are available."
        elif facet is ResearchSourceCoverageFacet.ALL:
            summary = f"All {total_count} accepted sources are shown."
        elif facet is ResearchSourceCoverageFacet.WITHOUT_EVIDENCE and visible_sources:
            summary = (
                f"{visible_count} of {total_count} accepted sources have no "
                "recorded evidence."
            )
        elif facet is ResearchSourceCoverageFacet.WITHOUT_EVIDENCE:
            summary = (
                f"All {total_count} accepted sources have recorded evidence; "
                "no sources match this view."
            )
        elif visible_sources:
            summary = (
                f"{visible_count} of {total_count} accepted sources have no "
                "current authored assessment."
            )
        else:
            summary = (
                f"All {total_count} accepted sources have a current authored "
                "assessment; no sources match this view."
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

    def _show_active_research_source(self) -> None:
        """Restore one hidden active source without opening a read path."""
        active_source_id = self._active_research_source_document_id
        if not active_source_id:
            self._research_source_coverage_summary.set(
                "No active accepted source is selected."
            )
            self._status.set("Select an accepted source before showing it.")
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
            self._research_run_id.get().strip() != self._research_source_run_id
            or selected_run is None
            or selected_run.sources != self._research_source_catalog
        ):
            self._research_source_coverage_summary.set(
                "Accepted-source snapshot is stale; refresh research runs."
            )
            self._status.set("Accepted-source snapshot is stale.")
            return
        active_source = next(
            (
                source
                for source in self._research_source_catalog
                if source.document_id == active_source_id
            ),
            None,
        )
        if active_source is None:
            self._research_source_coverage_summary.set(
                "The active accepted source is not loaded; refresh research runs."
            )
            self._status.set("Active accepted source is not loaded.")
            return
        self._research_source_coverage_filter.set(ResearchSourceCoverageFacet.ALL.value)
        self._render_visible_research_sources(
            selected_run,
            self._research_source_catalog,
        )
        self._research_source_choice.set(self._research_source_label(active_source))
        total_count = len(self._research_source_catalog)
        self._research_source_coverage_summary.set(
            f"All {total_count} accepted sources are shown."
        )
        self._status.set(
            f"active accepted source shown: {active_source_id}; "
            f"{total_count} accepted sources; view restored to All sources"
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
            self._research_selected_source_summary.set(
                "Selected-source records unavailable in the current source view."
            )
            self._clear_research_evidence()
            self._clear_research_assessments()
            return
        self._research_source_selector.current(selected_index)
        selected_source = visible_sources[selected_index]
        self._research_selected_source_summary.set(
            self._research_selected_source_summary_text(run, selected_source)
        )
        self._render_research_evidence_selector(run, selected_source)
        self._render_research_assessment_selector(run, selected_source)

    @staticmethod
    def _filter_research_sources_by_coverage(
        sources: tuple[ResearchSourceRecord, ...],
        evidence: tuple[ResearchEvidenceRecord, ...],
        assessments: tuple[ResearchSourceAssessmentRecord, ...],
        facet: ResearchSourceCoverageFacet,
    ) -> tuple[ResearchSourceRecord, ...]:
        """Delegate source coverage membership outside Tkinter."""
        return ResearchWorkspaceReadModel.filter_sources_by_coverage(
            sources,
            evidence,
            assessments,
            facet,
        )

    @staticmethod
    def _research_source_catalog_summary_text(run: ResearchRun) -> str:
        """Delegate complete source coverage outside Tkinter."""
        return ResearchWorkspaceReadModel.source_catalog_summary_text(run)

    @staticmethod
    def _research_selected_source_summary_text(
        run: ResearchRun,
        source: ResearchSourceRecord,
    ) -> str:
        """Delegate canonical selected-source projection outside Tkinter."""
        return ResearchWorkspaceReadModel.source_view(run, source).summary

    @staticmethod
    def _bounded_research_source_title(source: ResearchSourceRecord) -> str:
        """Delegate untrusted-title normalization outside Tkinter."""
        return ResearchWorkspaceReadModel.bounded_source_title(source)

    @staticmethod
    def _research_source_details_text(
        run: ResearchRun,
        source: ResearchSourceRecord,
    ) -> str | None:
        """Delegate safe canonical provenance projection outside Tkinter."""
        return ResearchWorkspaceReadModel.source_details_text(run, source)

    @staticmethod
    def _research_source_label(source: ResearchSourceRecord) -> str:
        """Delegate bounded source identity projection outside Tkinter."""
        return ResearchWorkspaceReadModel.source_label(source)

    def _selected_research_source(self) -> ResearchSourceRecord | None:
        """Return only a source tied to the currently selected loaded run."""
        if self._research_run_id.get().strip() != self._research_source_run_id:
            self._clear_research_sources()
            return None
        selected_index = self._research_source_selector.current()
        if not 0 <= selected_index < len(self._research_sources):
            return None
        return self._research_sources[selected_index]

    def _show_selected_research_source_details(self) -> None:
        """Show safe local provenance without exposing URL or source content."""
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
            self._status.set("Select an accepted source first.")
            return
        details = self._research_source_details_text(selected_run, source)
        if details is None:
            self._status.set(
                "Selected accepted source is not part of the loaded research run."
            )
            return
        messagebox.showinfo(
            "Selected source details",
            details,
            parent=self._root,
        )
        self._status.set(
            f"accepted source details shown: {source.document_id}; no action started"
        )

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
        self._research_selected_source_summary.set(
            self._research_selected_source_summary_text(selected_run, source)
        )
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
        self._render_research_source_dimensions(run, source)
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

    def _render_research_source_dimensions(
        self,
        run: ResearchRun,
        source: ResearchSourceRecord,
    ) -> None:
        """Show relevance, judgement, reputation and acceptance as separate answers.

        They are rendered together and never combined. Each line names where it
        came from, because the failure worth preventing is somebody reading
        `Relevance: strong` as a statement that the source is sound — the ranker
        compared words in a title and has no opinion about soundness at all.
        """
        identity = identity_of(source.url)
        relevance = "not among the latest discovered candidates"
        provider = "unknown"
        if run.discoveries:
            latest = run.discoveries[-1]
            provider = latest.provider
            for entry in ranked_candidates(latest):
                if identity_of(entry.candidate.url) == identity:
                    relevance = (
                        f"{entry.relevance.category.value} "
                        f"({entry.relevance.score}), rank {entry.relevance_rank}, "
                        f"provider rank {entry.provider_rank}"
                    )
                    break
        current = self._current_research_assessment(run, source)
        if current is None:
            judgement = "none recorded"
        else:
            judgement = (
                f"usefulness={current.usefulness.value}, "
                f"applicability={current.applicability.value}, "
                f"independence={current.independence.value}, "
                f"publication={current.publication_status.value}, "
                f"information trust={current.information_trust.value}"
            )
        reputation = SourceReputationLedger().for_origin(origin_of(source.url), [run])
        reputation_text = (
            "unknown"
            if reputation is None
            else (
                f"{reputation.assessed_count} assessed at this origin "
                f"(high {reputation.high_count}, medium {reputation.medium_count}, "
                f"low {reputation.low_count})"
            )
        )
        evidence_count = sum(
            1
            for record in run.evidence
            if record.source_document_id == source.document_id
        )
        self._research_source_dimensions.set(
            "\n".join(
                (
                    f"Relevance: {relevance} (deterministic lexical ranking, "
                    f"provider {provider})",
                    f"Operator assessment: {judgement} (human judgement)",
                    f"Source reputation: {reputation_text} (our own past "
                    "assessments, counted)",
                    f"Evidence status: accepted, {evidence_count} evidence "
                    "record(s) (separate from every line above)",
                )
            )
        )

    @staticmethod
    def _current_research_assessment(
        run: ResearchRun,
        source: ResearchSourceRecord,
    ) -> ResearchSourceAssessmentRecord | None:
        """Return the assessment nothing has superseded, or nothing at all."""
        superseded = {
            record.supersedes_assessment_id
            for record in run.assessments
            if record.supersedes_assessment_id is not None
        }
        for record in reversed(run.assessments):
            if (
                record.source_document_id == source.document_id
                and record.assessment_id not in superseded
            ):
                return record
        return None

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
        judged = ", ".join(
            f"{name}={value}"
            for name, value in (
                ("usefulness", record.usefulness.value),
                ("applicability", record.applicability.value),
                ("independence", record.independence.value),
                ("publication", record.publication_status.value),
            )
            if value != "unknown"
        )
        judged = f" [{judged}]" if judged else ""
        return f"[{state}]{judged} {text} — {record.assessment_id}"

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
        self._research_source_catalog_summary.set(
            "Accepted-source coverage — All: 0 · Without evidence: 0 · "
            "Without current assessment: 0"
        )
        self._research_selected_source_summary.set(
            "Selected-source records unavailable until an accepted source is selected."
        )
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

    # ------------------------------------------------------------------
    # Tool console
    #
    # An operator control plane, not a reasoning feature. Nothing here asks a
    # model anything: the capability list comes from the production registry,
    # the descriptions are each tool's own declared summary, and the result is
    # read from the execution outcome rather than from the fact that a button
    # was pressed. It works with the LLM switched off, and a test says so.
    #
    # The window holds no tool-layer types. It passes plain strings to the
    # console controller and renders plain data back, so this file cannot name
    # an effect or build an invocation even by mistake.
    # ------------------------------------------------------------------

    def _build_plan_approval_section(self, parent: ttk.Frame) -> None:
        """Record a human approval of the exact plan above. Run nothing.

        Deliberately placed under the plan draft and using its fields, so the
        plan being approved is the plan on screen rather than a second copy
        someone typed twice.
        """
        self._plan_approval_run_id = tk.StringVar()
        self._plan_approval_id = tk.StringVar()
        self._plan_approval_disclosure = tk.StringVar(
            value=ResearchDisclosure.NONE.value
        )
        self._plan_approval_status = tk.StringVar(value=_APPROVAL_IDLE_STATUS)

        section = ttk.LabelFrame(parent, text="Plan approval", padding=8)
        section.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        section.columnconfigure(1, weight=1)
        ttk.Label(section, text=_APPROVAL_PANEL_NOTE, wraplength=680).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(section, text="Research run ID").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(section, textvariable=self._plan_approval_run_id).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(section, text="Model disclosure").grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Combobox(
            section,
            textvariable=self._plan_approval_disclosure,
            state="readonly",
            values=tuple(member.value for member in ResearchDisclosure),
        ).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        ttk.Label(section, text="Previewed approval ID").grid(
            row=3, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(section, textvariable=self._plan_approval_id).grid(
            row=3, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        #: The authority being granted, typed by the operator. Blank means
        #: "leave this bound alone", never zero and never "whatever it needs".
        self._authorization_advances = tk.StringVar()
        self._authorization_network = tk.StringVar()
        self._authorization_seconds = tk.StringVar()
        ttk.Label(section, text=_AUTHORIZATION_BUDGET_NOTE, wraplength=680).grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        for offset, (label, variable) in enumerate(
            (
                ("Grant step advances (blank = default)", self._authorization_advances),
                (
                    "Grant network operations (blank = default)",
                    self._authorization_network,
                ),
                ("Grant seconds (blank = default)", self._authorization_seconds),
            )
        ):
            ttk.Label(section, text=label).grid(
                row=11 + offset, column=0, sticky="w", pady=(6, 0)
            )
            ttk.Entry(section, textvariable=variable).grid(
                row=11 + offset, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
            )

        buttons = ttk.Frame(section)
        buttons.grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        for column, (label, command) in enumerate(
            (
                ("Preview approval — no write", self._preview_plan_authorization),
                ("Confirm approval", self._confirm_plan_authorization),
                ("List approvals", self._list_plan_authorizations),
                ("Use approval to start once", self._start_authorized_execution),
            )
        ):
            self._request_button(buttons, label, command).grid(
                row=0, column=column, sticky="w", padx=(0 if column == 0 else 8, 0)
            )
        ttk.Label(
            section,
            textvariable=self._plan_approval_status,
            wraplength=680,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._plan_approval_output = tk.Text(section, height=10, wrap="word")
        self._plan_approval_output.grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )
        self._plan_approval_output.configure(state=tk.DISABLED)

    def _build_execution_control_section(self, parent: ttk.Frame) -> None:
        """Watch, step, and stop one already-authorized execution.

        Placed beside the approval it was started with, because the two are one
        story: the approval was spent to begin this, and everything below stays
        inside what it approved.
        """
        self._execution_id = tk.StringVar()

        section = ttk.LabelFrame(parent, text="Started execution", padding=8)
        section.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        section.columnconfigure(1, weight=1)
        ttk.Label(section, text=_EXECUTION_PANEL_NOTE, wraplength=680).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(section, text="Execution ID").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(section, textvariable=self._execution_id).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        #: Named separately from the execution because a ruling is about one
        #: exact attempt, and "the interrupted one" is not an identity.
        self._interrupted_step_id = tk.StringVar()
        self._interrupted_resolution = tk.StringVar(
            value=ResearchAttemptResolution.REMAINS_UNKNOWN.value
        )
        ttk.Label(section, text=_INTERRUPTED_PANEL_NOTE, wraplength=680).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        ttk.Label(section, text="Interrupted step ID").grid(
            row=4, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(section, textvariable=self._interrupted_step_id).grid(
            row=4, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(section, text="What actually happened").grid(
            row=5, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Combobox(
            section,
            textvariable=self._interrupted_resolution,
            state="readonly",
            values=tuple(
                member.value
                for member in ResearchAttemptResolution
                if member is not ResearchAttemptResolution.NONE
            ),
        ).grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        self._request_button(
            section,
            "Record ruling",
            self._resolve_interrupted_attempt,
        ).grid(row=6, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        self._recovery_summary = tk.StringVar()
        self._recovery_claimed_operation = tk.StringVar()
        ttk.Label(section, text=_RECOVERY_PANEL_NOTE, wraplength=680).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        ttk.Label(section, text="What you found (your account)").grid(
            row=8, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(section, textvariable=self._recovery_summary).grid(
            row=8, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(section, text="Operation you say produced it").grid(
            row=9, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(section, textvariable=self._recovery_claimed_operation).grid(
            row=9, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        recovery_buttons = ttk.Frame(section)
        recovery_buttons.grid(row=10, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        for column, (label, command) in enumerate(
            (
                ("Record recovered information", self._record_recovered_information),
                ("Abandon step", self._abandon_step),
            )
        ):
            self._request_button(recovery_buttons, label, command).grid(
                row=0, column=column, sticky="w", padx=(0 if column == 0 else 8, 0)
            )

        #: A bound the operator types, never defaulted to "as many as it takes".
        self._continuation_steps = tk.StringVar(value="1")
        ttk.Label(section, text="Continue at most (steps)").grid(
            row=11, column=0, sticky="w", pady=(10, 0)
        )
        ttk.Entry(section, textvariable=self._continuation_steps).grid(
            row=11, column=1, sticky="ew", padx=(8, 0), pady=(10, 0)
        )
        self._request_button(
            section,
            "Continue bounded",
            self._continue_execution_bounded,
        ).grid(row=12, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        buttons = ttk.Frame(section)
        buttons.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        commands: list[tuple[str, Callable[[], None]]] = [
            ("Refresh status", self._refresh_execution_status),
            ("Advance one step", self._advance_execution_one_step),
            ("Cancel execution", self._cancel_execution),
        ]
        if self._curiosity_enabled:
            # Only offered where the question it needs can be named. Resuming
            # asks which question the execution came from, and that field
            # exists on the curiosity surface.
            commands.insert(1, ("Resume after restart", self._resume_execution))
        for column, (label, command) in enumerate(commands):
            self._request_button(buttons, label, command).grid(
                row=0, column=column, sticky="w", padx=(0 if column == 0 else 8, 0)
            )

    def _refresh_execution_status(self) -> None:
        self._approval_request(
            lambda: self._controller.research_execution_status(self._execution_id.get())
        )

    def _advance_execution_one_step(self) -> None:
        """Attempt one step, after showing what that step would cost."""
        execution_id = self._execution_id.get().strip()
        if not execution_id:
            self._plan_approval_status.set("An execution ID is required.")
            return
        if not messagebox.askyesno(
            "Advance one step?",
            (
                f"Execution: {execution_id}\n\n"
                "This attempts exactly one step and then stops. It does not "
                "continue to the next step on its own.\n\n"
                "The attempt is charged against the approved budget whether or "
                "not it succeeds. Choose Refresh status first to see what "
                "remains and what the next step would use."
            ),
            parent=self._root,
        ):
            self._plan_approval_status.set("Not advanced. Nothing was attempted.")
            return
        self._approval_request(
            lambda: self._controller.advance_research_execution(execution_id)
        )

    def _resume_execution(self) -> None:
        """Recover one named durable execution so it can be advanced again.

        Reads both identifiers when pressed, so it follows what the operator
        has selected rather than resuming whatever ran last. It performs no
        step: advancing stays a separate, explicit decision afterwards.
        """
        execution_id = self._execution_id.get().strip()
        question_id = self._curiosity_question_id.get().strip()
        if not execution_id or not question_id:
            self._plan_approval_status.set(
                "A question ID and an execution ID are both required."
            )
            return
        if not messagebox.askyesno(
            "Resume this execution?",
            (
                f"Execution: {execution_id}\n"
                f"Question: {question_id}\n\n"
                "This recovers an execution that was already approved and "
                "already started, so that it can be advanced again. It creates "
                "no new approval and gives back no spent budget.\n\n"
                "No step runs. Steps that finished before the restart stay "
                "finished and are not repeated."
            ),
            parent=self._root,
        ):
            self._plan_approval_status.set("Not resumed. Nothing was recovered.")
            return
        self._approval_request(
            lambda: self._controller.resume_research_execution(
                question_id,
                execution_id,
            )
        )

    def _resolve_interrupted_attempt(self) -> None:
        """Record one human ruling about an attempt nobody saw the end of.

        The dialog states what is and is not known before asking, because the
        whole reason this control exists is that the system cannot tell the
        operator what happened. It runs nothing and retries nothing.
        """
        execution_id = self._execution_id.get().strip()
        step_id = self._interrupted_step_id.get().strip()
        resolution = self._interrupted_resolution.get().strip()
        if not execution_id or not step_id:
            self._plan_approval_status.set(
                "An execution ID and the interrupted step ID are both required."
            )
            return
        if not messagebox.askyesno(
            "Record this ruling?",
            (
                f"Execution: {execution_id}\n"
                f"Step: {step_id}\n"
                f"Ruling: {resolution}\n\n"
                "Previous attempt was interrupted. The external operation may "
                "have occurred. Its final result is unknown. The attempt has "
                "already been charged.\n\n"
                "This records what you know and nothing else. No operation "
                "runs, nothing is retried, and the charge already made is "
                "neither refunded nor repeated."
            ),
            parent=self._root,
        ):
            self._plan_approval_status.set("No ruling recorded.")
            return
        self._approval_request(
            lambda: self._controller.resolve_interrupted_attempt(
                execution_id,
                step_id,
                resolution,
            )
        )

    def _record_recovered_information(self) -> None:
        """Keep the operator's own account of an outcome Hypatia never saw."""
        self._recover(
            ResearchAttemptRecoveryDecision.OPERATOR_SUPPLIED_RESULT,
            (
                "This records what YOU found. It is stored as your account, "
                "never as a provider result, and the step stays blocked rather "
                "than being marked completed.\n\n"
                "No operation runs, nothing is retried, and the charge already "
                "made is neither refunded nor repeated."
            ),
        )

    def _abandon_step(self) -> None:
        """Stop pursuing one step without claiming it succeeded or failed."""
        self._recover(
            ResearchAttemptRecoveryDecision.ABANDONED,
            (
                "This step will not be pursued. It is not marked succeeded and "
                "not marked failed, and the record still shows the operation "
                "may have run.\n\n"
                "Nothing is retried and the charge already made stays spent. "
                "Later steps become available to advance explicitly."
            ),
        )

    def _recover(
        self,
        decision: ResearchAttemptRecoveryDecision,
        warning: str,
    ) -> None:
        """Ask once, plainly, then record one explicit operator decision."""
        execution_id = self._execution_id.get().strip()
        step_id = self._interrupted_step_id.get().strip()
        if not execution_id or not step_id:
            self._plan_approval_status.set(
                "An execution ID and the blocked step ID are both required."
            )
            return
        if not messagebox.askyesno(
            "Record this decision?",
            (
                f"Execution: {execution_id}\n"
                f"Step: {step_id}\n"
                f"Decision: {decision.value}\n\n" + warning
            ),
            parent=self._root,
        ):
            self._plan_approval_status.set("No decision recorded.")
            return
        self._approval_request(
            lambda: self._controller.recover_interrupted_attempt(
                execution_id,
                step_id,
                decision.value,
                self._recovery_summary.get(),
                self._recovery_claimed_operation.get(),
            )
        )

    def _continue_execution_bounded(self) -> None:
        """Run at most the number of steps the operator typed, then stop.

        The dialog names the bound and says what ends the run early, because
        "continue" is the word most likely to be read as "finish this for me".
        """
        execution_id = self._execution_id.get().strip()
        steps = self._continuation_steps.get().strip()
        if not execution_id or not steps:
            self._plan_approval_status.set(
                "An execution ID and a step count are both required."
            )
            return
        if not messagebox.askyesno(
            "Continue within this bound?",
            (
                f"Execution: {execution_id}\n\n"
                f"Run at most {steps} foreground research steps. Each step uses "
                "the existing budget and capability checks, exactly as pressing "
                "Advance once does.\n\n"
                "Execution stops early on failure, block, interruption, "
                "cancellation or budget limit. Nothing runs in the background "
                "and nothing continues after this returns."
            ),
            parent=self._root,
        ):
            self._plan_approval_status.set("Not continued. Nothing was attempted.")
            return
        self._approval_request(
            lambda: self._controller.continue_research_execution(
                execution_id,
                steps,
            )
        )

    def _cancel_execution(self) -> None:
        execution_id = self._execution_id.get().strip()
        if not execution_id:
            self._plan_approval_status.set("An execution ID is required.")
            return
        if not messagebox.askyesno(
            "Cancel this execution?",
            (
                f"Execution: {execution_id}\n\n"
                "Cancelling stops this execution for good. The approval it "
                "used stays used and the budget already spent stays spent; "
                "neither comes back."
            ),
            parent=self._root,
        ):
            self._plan_approval_status.set("Not cancelled.")
            return
        self._approval_request(
            lambda: self._controller.cancel_research_execution(execution_id)
        )

    def _approval_request(
        self,
        call: Callable[[], BrainResponse],
    ) -> BrainResponse | None:
        """Run one approval request into the approval panel's result area.

        The response comes back so a caller can read structured state out of
        it — the exact approval a preview built, say — instead of reading it
        out of the rendered text.
        """
        return self._panel_request(
            self._plan_approval_status,
            self._plan_approval_output,
            call,
        )

    def _preview_plan_authorization(self) -> None:
        """Show what confirming would record, and remember the exact terms.

        The approval the runtime built is captured here rather than re-derived
        later, because that object is the one confirming records. Editing the
        budget fields afterwards changes nothing until this is pressed again,
        and the confirmation says so.
        """
        response = self._approval_request(
            lambda: self._controller.preview_plan_authorization(
                self._research_question.get(),
                self._text_value(self._research_plan_instructions),
                self._text_value(self._research_plan_source_ids),
                self._plan_approval_run_id.get(),
                self._plan_approval_disclosure.get(),
                self._authorization_advances.get(),
                self._authorization_network.get(),
                self._authorization_seconds.get(),
            )
        )
        authorization = getattr(response, "research_plan_authorization", None)
        self._previewed_authority = (
            authorization.budget if authorization is not None else None
        )
        self._previewed_fit = getattr(response, "research_plan_budget_fit", None)

    def _confirm_plan_authorization(self) -> None:
        """Record the previewed approval, after showing its exact terms.

        Confirming records the approval built when Preview ran, so the budget
        shown here is that one and not whatever the fields say now. Anybody who
        has edited them since is told plainly that this is not what they typed,
        which is more use than quietly recording the older figure.
        """
        previewed = getattr(self, "_previewed_authority", None)
        if previewed is None:
            self._plan_approval_status.set(
                "Preview an approval first; confirming records exactly what it "
                "described."
            )
            return
        if not messagebox.askyesno(
            "Record this approval?",
            (
                f"Approval: {self._plan_approval_id.get().strip()}\n\n"
                + "\n".join(_granted_authority_lines(previewed, self._previewed_fit))
                + "\n\nThese are the terms Preview recorded. If you have "
                "changed the budget boxes since, those changes are not part of "
                "this approval; press Preview again to approve them instead.\n\n"
                "Nothing runs. Beginning the work is a separate action."
            ),
            parent=self._root,
        ):
            self._plan_approval_status.set("Not confirmed. Nothing was recorded.")
            return
        self._approval_request(
            lambda: self._controller.confirm_plan_authorization(
                self._plan_approval_id.get(),
                self._research_question.get(),
                self._text_value(self._research_plan_instructions),
                self._text_value(self._research_plan_source_ids),
                self._plan_approval_run_id.get(),
            )
        )

    def _start_authorized_execution(self) -> None:
        """Spend one approval on one foreground start, after saying so plainly.

        The dialog names the approval and states both halves of what happens:
        the approval is used up, and one execution begins. An operator who
        expects only one of those has been told the wrong thing.
        """
        authorization_id = self._plan_approval_id.get().strip()
        if not authorization_id:
            self._plan_approval_status.set("A recorded approval ID is required.")
            return
        if not messagebox.askyesno(
            "Use this approval?",
            (
                f"Approval: {authorization_id}\n\n"
                "This will use up this approval and start one foreground "
                "execution of the plan above.\n\n"
                "The approval cannot be used again, even if the execution "
                "fails, blocks, or is cancelled. Nothing is scheduled and "
                "nothing continues on its own."
            ),
            parent=self._root,
        ):
            self._plan_approval_status.set("Not started. The approval is unused.")
            return
        self._approval_request(
            lambda: self._controller.start_authorized_execution(
                authorization_id,
                self._research_question.get(),
                self._text_value(self._research_plan_instructions),
                self._text_value(self._research_plan_source_ids),
                self._plan_approval_run_id.get(),
            )
        )

    def _list_plan_authorizations(self) -> None:
        self._approval_request(self._controller.list_plan_authorizations)

    def _build_review_tab(self, parent: ttk.Frame) -> None:
        """Lay out the three ways of looking back at a run that is under way.

        Calibration asks how far each claim outruns its evidence, reflection
        asks how the run went, and curiosity asks what was never asked. None of
        them changes a run, a claim, or a confidence: they report, and the
        judgement stays where it was.
        """
        self._review_run_id = tk.StringVar()
        self._review_claim_id = tk.StringVar()
        self._review_status = tk.StringVar(value=_REVIEW_IDLE_STATUS)
        parent.rowconfigure(4, weight=1)
        ttk.Label(parent, text=_REVIEW_PANEL_NOTE, wraplength=720).grid(
            row=0, column=0, sticky="w"
        )

        run = ttk.LabelFrame(parent, text="Research run", padding=12)
        run.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        run.columnconfigure(1, weight=1)
        ttk.Label(run, text="Run ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(run, textvariable=self._review_run_id).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        ttk.Label(run, text=_CALIBRATION_NOTE, wraplength=680).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(run, text="Claim ID for review").grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(run, textvariable=self._review_claim_id).grid(
            row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(run, text=_PROVIDER_QUALITY_NOTE, wraplength=680).grid(
            row=4, column=1, sticky="w", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(run, text=_PROVIDER_COMPARISON_NOTE, wraplength=680).grid(
            row=5, column=1, sticky="w", padx=(8, 0), pady=(6, 0)
        )
        commands: list[tuple[str, Callable[[], None]]] = [
            ("Calibrate claims", self._report_claim_calibration),
            ("Prepare claim review", self._prepare_claim_revision_review),
            # Not run-scoped like the others: provider experience accumulates
            # across every run, and one run is never a sample.
            ("Provider quality", self._report_provider_quality),
            ("Paired quality", self._report_paired_provider_quality),
            ("Provider comparison", self._report_provider_comparison),
        ]
        if self._reflection_enabled:
            commands.append(("Reflect", self._preview_reflection))
            commands.append(("Reflect and keep", self._store_reflection))
        if self._curiosity_enabled:
            commands.append(("Find gaps", self._detect_curiosity_gaps))
            commands.append(("Draft questions", self._preview_curiosity_questions))
            commands.append(("Draft and keep", self._store_curiosity_questions))
        buttons = ttk.Frame(run)
        buttons.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        for index, (label, command) in enumerate(commands):
            self._request_button(buttons, label, command).grid(
                row=index // 3,
                column=index % 3,
                sticky="w",
                padx=(0 if index % 3 == 0 else 8, 0),
                pady=(0 if index < 3 else 6, 0),
            )

        if self._curiosity_enabled:
            self._build_curiosity_ruling_section(parent)
        if self._reflection_enabled or self._curiosity_enabled:
            self._build_review_history_section(parent)

        results = ttk.LabelFrame(parent, text="Result", padding=12)
        results.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        results.columnconfigure(0, weight=1)
        results.rowconfigure(1, weight=1)
        ttk.Label(results, textvariable=self._review_status, wraplength=720).grid(
            row=0, column=0, sticky="w"
        )
        self._review_output = tk.Text(results, height=14, wrap="word")
        self._review_output.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self._review_output.configure(state=tk.DISABLED)

    def _build_curiosity_ruling_section(self, parent: ttk.Frame) -> None:
        """One question, one human ruling. Neither ruling starts any research."""
        self._curiosity_question_id = tk.StringVar()
        #: The digest the operator was shown. Carried so approving names the
        #: exact plan that was read rather than whatever the system would draft
        #: at the moment the button is pressed.
        self._curiosity_plan_digest = tk.StringVar()
        #: The durable approval returned by the authorization response. A
        #: start names it exactly; there is no "latest approval" lookup.
        self._curiosity_authorization_id = tk.StringVar()
        section = ttk.LabelFrame(parent, text="Rule on a question", padding=12)
        section.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        section.columnconfigure(1, weight=1)
        ttk.Label(section, text="Question ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(section, textvariable=self._curiosity_question_id).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        ttk.Label(section, text=_CURIOSITY_RULING_NOTE, wraplength=680).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0)
        )
        buttons = ttk.Frame(section)
        buttons.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        self._request_button(
            buttons, "Worth pursuing", self._accept_curiosity_question
        ).grid(row=0, column=0, sticky="w")
        self._request_button(
            buttons, "Not worth pursuing", self._dismiss_curiosity_question
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))
        self._request_button(
            buttons,
            "Prepare research proposal",
            self._prepare_curiosity_research_proposal,
        ).grid(row=0, column=2, sticky="w", padx=(8, 0))
        self._request_button(
            buttons,
            "Authorize this proposal",
            self._authorize_curiosity_research_proposal,
        ).grid(row=0, column=3, sticky="w", padx=(8, 0))
        self._request_button(
            buttons,
            "Start authorized proposal",
            self._start_authorized_curiosity_research_proposal,
        ).grid(row=0, column=4, sticky="w", padx=(8, 0))
        ttk.Label(section, text="Plan digest").grid(
            row=3, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(
            section, textvariable=self._curiosity_plan_digest, state="readonly"
        ).grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        #: The authority granted to a plan Hypatia proposed. Blank keeps the
        #: standing default; nothing here is filled in from what the plan needs.
        self._curiosity_advances = tk.StringVar()
        self._curiosity_network = tk.StringVar()
        self._curiosity_seconds = tk.StringVar()
        ttk.Label(section, text=_CURIOSITY_BUDGET_NOTE, wraplength=680).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        for offset, (label, variable) in enumerate(
            (
                ("Grant step advances (blank = default)", self._curiosity_advances),
                (
                    "Grant network operations (blank = default)",
                    self._curiosity_network,
                ),
                ("Grant seconds (blank = default)", self._curiosity_seconds),
            )
        ):
            ttk.Label(section, text=label).grid(
                row=7 + offset, column=0, sticky="w", pady=(6, 0)
            )
            ttk.Entry(section, textvariable=variable).grid(
                row=7 + offset, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
            )
        ttk.Label(section, text="Approval ID").grid(
            row=4, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(
            section,
            textvariable=self._curiosity_authorization_id,
            state="readonly",
        ).grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))

    def _build_review_history_section(self, parent: ttk.Frame) -> None:
        """Read back what was kept, producing nothing new."""
        section = ttk.LabelFrame(parent, text="Kept", padding=12)
        section.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        section.columnconfigure(0, weight=1)
        buttons = ttk.Frame(section)
        buttons.grid(row=0, column=0, sticky="w")
        column = 0
        if self._reflection_enabled:
            self._request_button(
                buttons, "List reflections", self._list_reflections
            ).grid(row=0, column=column, sticky="w")
            column += 1
        if self._curiosity_enabled:
            self._request_button(
                buttons, "List questions", self._list_curiosity_questions
            ).grid(row=0, column=column, sticky="w", padx=(0 if column == 0 else 8, 0))

    def _review_request(
        self,
        call: Callable[[], BrainResponse],
    ) -> BrainResponse | None:
        """Run one review request into the Review panel's result area."""
        return self._panel_request(self._review_status, self._review_output, call)

    def _report_provider_comparison(self) -> None:
        """Show one run's two provider result sets. Contact no provider."""
        self._review_request(
            lambda: self._controller.report_provider_comparison(
                self._review_run_id.get()
            )
        )

    def _report_provider_quality(self) -> None:
        """Describe provider samples. Change no provider, default, or ranking."""
        self._review_request(self._controller.report_provider_quality)

    def _report_paired_provider_quality(self) -> None:
        """Describe aligned provider samples. Select and change nothing."""
        self._review_request(self._controller.report_paired_provider_quality)

    def _report_claim_calibration(self) -> None:
        self._review_request(
            lambda: self._controller.report_claim_calibration(self._review_run_id.get())
        )

    def _prepare_claim_revision_review(self) -> None:
        """Show exact current context; draft and record no replacement."""
        self._review_request(
            lambda: self._controller.prepare_claim_revision_review(
                self._review_run_id.get(),
                self._review_claim_id.get(),
            )
        )

    def _preview_reflection(self) -> None:
        self._review_request(
            lambda: self._controller.preview_reflection(self._review_run_id.get())
        )

    def _store_reflection(self) -> None:
        self._review_request(
            lambda: self._controller.store_reflection(self._review_run_id.get())
        )

    def _list_reflections(self) -> None:
        self._review_request(self._controller.list_reflections)

    def _detect_curiosity_gaps(self) -> None:
        self._review_request(
            lambda: self._controller.detect_curiosity_gaps(self._review_run_id.get())
        )

    def _preview_curiosity_questions(self) -> None:
        self._review_request(
            lambda: self._controller.preview_curiosity_questions(
                self._review_run_id.get()
            )
        )

    def _store_curiosity_questions(self) -> None:
        self._review_request(
            lambda: self._controller.store_curiosity_questions(
                self._review_run_id.get()
            )
        )

    def _list_curiosity_questions(self) -> None:
        self._review_request(self._controller.list_curiosity_questions)

    def _accept_curiosity_question(self) -> None:
        self._review_request(
            lambda: self._controller.accept_curiosity_question(
                self._curiosity_question_id.get()
            )
        )

    def _authorize_curiosity_research_proposal(self) -> None:
        """Approve exactly the proposal on screen, after asking.

        The digest is shown in the confirmation rather than only in the panel,
        because the digest is what the approval is bound to and an operator
        approving one plan while reading another is the failure this exists to
        prevent. Answering No records nothing at all.
        """
        question_id = self._curiosity_question_id.get().strip()
        digest = self._curiosity_plan_digest.get().strip()
        if not question_id or not digest:
            self._review_status.set(
                "Prepare a research proposal first; approving needs its digest."
            )
            return
        # Read the budget boxes as they stand now, not as they stood when
        # Preview last ran. Approving parses these same values, so a dialog
        # describing anything else would describe the wrong grant.
        current = self._review_request(
            lambda: self._controller.prepare_curiosity_research_proposal(
                question_id,
                self._curiosity_advances.get(),
                self._curiosity_network.get(),
                self._curiosity_seconds.get(),
            )
        )
        proposal = getattr(current, "curiosity_proposal", None)
        fit = getattr(current, "research_plan_budget_fit", None)
        if current is None or proposal is None:
            reason = current.message.splitlines()[0] if current is not None else ""
            self._review_status.set(
                ("curiosity proposal: not authorized. " + reason).strip()
            )
            return
        if proposal.digest != digest:
            self._review_status.set(
                "curiosity proposal: not authorized. The proposal changed since "
                "you read it; prepare it again before approving."
            )
            return
        if fit is not None and not fit.sufficient:
            self._review_status.set(
                "curiosity proposal: not authorized. " + " ".join(fit.lines()[1:])
            )
            return
        if not messagebox.askyesno(
            "Authorize this research proposal?",
            (
                f"Curiosity question: {question_id}\n"
                f"Plan digest: {digest}\n\n"
                + (
                    "\n".join(_granted_authority_lines(fit.budget, fit)) + "\n\n"
                    if fit is not None
                    else ""
                )
                + "This records that you approve exactly this plan, with the "
                "budget you entered as the authority you are granting it. It "
                "starts nothing: no provider is contacted and no step runs. "
                "Beginning the work is a separate action.\n\n"
                "If the proposal has changed since you previewed it, the "
                "approval is refused rather than moved to the new plan."
            ),
            parent=self._root,
        ):
            self._review_status.set("curiosity proposal: not authorized")
            return
        response = self._review_request(
            lambda: self._controller.authorize_curiosity_research_proposal(
                question_id,
                digest,
                self._curiosity_advances.get(),
                self._curiosity_network.get(),
                self._curiosity_seconds.get(),
            )
        )
        authorization = getattr(response, "research_plan_authorization", None)
        self._curiosity_authorization_id.set(
            authorization.authorization_id if authorization else ""
        )

    def _start_authorized_curiosity_research_proposal(self) -> None:
        """Spend the displayed approval on a zero-step foreground start."""
        question_id = self._curiosity_question_id.get().strip()
        digest = self._curiosity_plan_digest.get().strip()
        authorization_id = self._curiosity_authorization_id.get().strip()
        if not question_id or not digest or not authorization_id:
            self._review_status.set(
                "Prepare and authorize a proposal before starting it."
            )
            return
        if not messagebox.askyesno(
            "Start this authorized proposal?",
            (
                f"Curiosity question: {question_id}\n"
                f"Plan digest: {digest}\n"
                f"Approval ID: {authorization_id}\n\n"
                "This uses up the approval and creates one foreground "
                "execution in Running state. No provider is contacted and no "
                "research step runs now. The first step still requires a "
                "separate Advance action."
            ),
            parent=self._root,
        ):
            self._review_status.set(
                "curiosity proposal: not started; approval remains unused"
            )
            return
        response = self._review_request(
            lambda: self._controller.start_authorized_curiosity_research_proposal(
                question_id,
                digest,
                authorization_id,
            )
        )
        # The started execution's own identity, taken from the canonical
        # response rather than typed again, so Advance and Cancel act on
        # exactly what was started. A refusal carries no execution and clears
        # the field, because a stale identity here would point the next advance
        # at whatever was started before.
        execution = getattr(response, "research_plan_execution", None)
        self._execution_id.set(execution.plan_id if execution else "")

    def _prepare_curiosity_research_proposal(self) -> None:
        """Preview what the selected accepted question would research.

        Reads the identifier when the control is pressed, so it follows the
        operator's current selection rather than whichever question was newest.
        Nothing is accepted, authorized, or started here; an ineligible question
        comes back as an explicit refusal rather than being quietly accepted
        first.
        """
        response = self._review_request(
            lambda: self._controller.prepare_curiosity_research_proposal(
                self._curiosity_question_id.get(),
                self._curiosity_advances.get(),
                self._curiosity_network.get(),
                self._curiosity_seconds.get(),
            )
        )
        # Captured from the canonical response rather than parsed out of the
        # rendered text, so approving cannot bind to a digest scraped from
        # prose. A refusal carries no proposal and clears the field.
        proposal = getattr(response, "curiosity_proposal", None)
        self._curiosity_plan_digest.set(proposal.digest if proposal else "")
        self._curiosity_authorization_id.set("")

    def _dismiss_curiosity_question(self) -> None:
        self._review_request(
            lambda: self._controller.dismiss_curiosity_question(
                self._curiosity_question_id.get()
            )
        )

    @property
    def _learning_visible(self) -> bool:
        """Return whether either learning surface has somewhere durable to go."""
        return self._hypothesis_enabled or self._failure_memory_enabled

    def _build_learning_tab(self, parent: ttk.Frame) -> None:
        """Lay out the two halves of learning: what we expect, and what failed.

        These have existed in the runtime for some time with no way to reach
        them, which made the loop real and unusable at once. Hypotheses feed
        failure memory, failure memory surfaces itself when a new run begins,
        and neither half could be driven by the person the loop is for.
        """
        self._learning_status = tk.StringVar(value=_LEARNING_IDLE_STATUS)
        parent.rowconfigure(3, weight=1)
        ttk.Label(parent, text=_LEARNING_PANEL_NOTE, wraplength=720).grid(
            row=0, column=0, sticky="w"
        )
        if self._hypothesis_enabled:
            self._build_hypothesis_section(parent)
        if self._failure_memory_enabled:
            self._build_lesson_section(parent)

        results = ttk.LabelFrame(parent, text="Result", padding=12)
        results.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        results.columnconfigure(0, weight=1)
        results.rowconfigure(1, weight=1)
        ttk.Label(results, textvariable=self._learning_status, wraplength=720).grid(
            row=0, column=0, sticky="w"
        )
        self._learning_output = tk.Text(results, height=12, wrap="word")
        self._learning_output.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self._learning_output.configure(state=tk.DISABLED)

    def _build_hypothesis_section(self, parent: ttk.Frame) -> None:
        """Propose, take evidence on either side, withdraw, and review."""
        self._hypothesis_run_id = tk.StringVar()
        self._hypothesis_id = tk.StringVar()
        self._hypothesis_evidence_ids = tk.StringVar()

        self._hypothesis_relation = tk.StringVar(
            value=HypothesisEvidenceRelation.SUPPORTS.value
        )

        section = ttk.LabelFrame(parent, text="Hypotheses", padding=12)
        section.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        section.columnconfigure(1, weight=1)
        ttk.Label(section, text="Research run ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(section, textvariable=self._hypothesis_run_id).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        ttk.Label(section, text="Statement").grid(
            row=1, column=0, sticky="nw", pady=(6, 0)
        )
        self._hypothesis_statement_text = tk.Text(section, height=3, wrap="word")
        self._hypothesis_statement_text.grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(section, text="What would count against it").grid(
            row=2, column=0, sticky="nw", pady=(6, 0)
        )
        self._hypothesis_test_text = tk.Text(section, height=3, wrap="word")
        self._hypothesis_test_text.grid(
            row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(section, text=_HYPOTHESIS_DEFEATER_NOTE, wraplength=680).grid(
            row=3, column=1, sticky="w", padx=(8, 0), pady=(6, 0)
        )
        self._request_button(section, "Propose", self._propose_hypothesis).grid(
            row=4, column=1, sticky="w", padx=(8, 0), pady=(8, 0)
        )

        ttk.Separator(section).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(12, 8)
        )
        ttk.Label(section, text="Hypothesis ID").grid(row=6, column=0, sticky="w")
        ttk.Entry(section, textvariable=self._hypothesis_id).grid(
            row=6, column=1, sticky="ew", padx=(8, 0)
        )
        ttk.Label(section, text="Evidence IDs").grid(
            row=7, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(section, textvariable=self._hypothesis_evidence_ids).grid(
            row=7, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(section, text=_HYPOTHESIS_EVIDENCE_NOTE, wraplength=680).grid(
            row=8, column=1, sticky="w", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(section, text="Relation to retract").grid(
            row=9, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Combobox(
            section,
            textvariable=self._hypothesis_relation,
            values=tuple(relation.value for relation in HypothesisEvidenceRelation),
            state="readonly",
        ).grid(row=9, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        buttons = ttk.Frame(section)
        buttons.grid(row=10, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        for column, (label, command) in enumerate(
            (
                ("Support", self._support_hypothesis),
                ("Oppose", self._oppose_hypothesis),
                ("Addresses test", self._associate_hypothesis_test_evidence),
                ("Retract relation", self._retract_hypothesis_relation),
                ("View history", self._view_hypothesis_history),
                ("Withdraw", self._withdraw_hypothesis),
                ("List hypotheses", self._list_hypotheses),
            )
        ):
            self._request_button(buttons, label, command).grid(
                row=0, column=column, sticky="w", padx=(0 if column == 0 else 8, 0)
            )

    def _build_lesson_section(self, parent: ttk.Frame) -> None:
        """Preview, remember, recall, and review what did not work."""
        self._lesson_run_id = tk.StringVar()
        self._lesson_question = tk.StringVar()

        section = ttk.LabelFrame(parent, text="Failure lessons", padding=12)
        section.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        section.columnconfigure(1, weight=1)
        ttk.Label(section, text="Research run ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(section, textvariable=self._lesson_run_id).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        run_buttons = ttk.Frame(section)
        run_buttons.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        commands: list[tuple[str, Callable[[], None]]] = [
            ("Preview", self._preview_failure_lessons),
            ("Remember", self._store_failure_lessons),
        ]
        # Remembering hypothesis outcomes reads the durable hypothesis store, so
        # it is offered only where that store exists. Without it the command
        # would refuse every time, which reads as breakage rather than as a
        # capability this build was not given.
        if self._hypothesis_enabled:
            commands.append(
                ("Remember hypothesis outcomes", self._remember_hypothesis_outcomes)
            )
        for column, (label, command) in enumerate(commands):
            self._request_button(run_buttons, label, command).grid(
                row=0, column=column, sticky="w", padx=(0 if column == 0 else 8, 0)
            )

        ttk.Separator(section).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(12, 8)
        )
        ttk.Label(section, text="Question").grid(row=3, column=0, sticky="w")
        ttk.Entry(section, textvariable=self._lesson_question).grid(
            row=3, column=1, sticky="ew", padx=(8, 0)
        )
        ttk.Label(section, text=_LESSON_ADVISORY_NOTE, wraplength=680).grid(
            row=4, column=1, sticky="w", padx=(8, 0), pady=(6, 0)
        )
        recall_buttons = ttk.Frame(section)
        recall_buttons.grid(row=5, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        self._request_button(
            recall_buttons, "Recall relevant", self._recall_failure_lessons
        ).grid(row=0, column=0, sticky="w")
        self._request_button(
            recall_buttons, "List lessons", self._list_failure_lessons
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

    def _learning_request(self, call: Callable[[], BrainResponse]) -> None:
        """Run one learning request into the Learning panel's result area."""
        self._panel_request(self._learning_status, self._learning_output, call)

    def _propose_hypothesis(self) -> None:
        self._learning_request(
            lambda: self._controller.propose_hypothesis(
                self._hypothesis_run_id.get(),
                self._text_value(self._hypothesis_statement_text),
                self._text_value(self._hypothesis_test_text),
            )
        )

    def _support_hypothesis(self) -> None:
        self._learning_request(
            lambda: self._controller.support_hypothesis(
                self._hypothesis_id.get(),
                self._hypothesis_evidence_ids.get(),
            )
        )

    def _oppose_hypothesis(self) -> None:
        self._learning_request(
            lambda: self._controller.oppose_hypothesis(
                self._hypothesis_id.get(),
                self._hypothesis_evidence_ids.get(),
            )
        )

    def _associate_hypothesis_test_evidence(self) -> None:
        self._learning_request(
            lambda: self._controller.associate_hypothesis_test_evidence(
                self._hypothesis_id.get(),
                self._hypothesis_evidence_ids.get(),
            )
        )

    def _view_hypothesis_history(self) -> None:
        """Read the currently selected hypothesis's history and show it.

        Reads the identifier when the control is pressed rather than when the
        panel was built, so it follows the operator's selection, and asks the
        controller afresh each time so a correction made a moment ago is in it.
        """
        self._learning_request(
            lambda: self._controller.hypothesis_history(self._hypothesis_id.get())
        )

    def _retract_hypothesis_relation(self) -> None:
        """Show exactly what will be taken back, then record only that.

        The evidence field accepts several identifiers for the authoring
        controls beside this one, but a retraction is about a single statement,
        so this asks for exactly one rather than quietly withdrawing several at
        once from a field that looks the same.
        """
        hypothesis_id = self._hypothesis_id.get().strip()
        evidence_ids = [
            value.strip()
            for value in self._hypothesis_evidence_ids.get().split(",")
            if value.strip()
        ]
        relation = self._hypothesis_relation.get().strip()
        if not hypothesis_id or len(evidence_ids) != 1 or not relation:
            self._learning_status.set(
                "Retracting needs one hypothesis, exactly one evidence ID, "
                "and a relation."
            )
            return
        if not messagebox.askyesno(
            "Retract this relationship?",
            (
                f"Hypothesis: {hypothesis_id}\n"
                f"Evidence: {evidence_ids[0]}\n"
                f"Relationship: {relation}\n"
                "Action: RETRACT\n\n"
                "This records that the statement no longer stands. The evidence "
                "and the hypothesis are both kept, nothing moves to another "
                "relationship, and the retraction stays visible in this "
                "hypothesis's history."
            ),
            parent=self._root,
        ):
            self._learning_status.set("hypothesis relation: not retracted")
            return
        self._learning_request(
            lambda: self._controller.retract_hypothesis_evidence_relation(
                hypothesis_id,
                evidence_ids[0],
                relation,
            )
        )

    def _withdraw_hypothesis(self) -> None:
        self._learning_request(
            lambda: self._controller.withdraw_hypothesis(self._hypothesis_id.get())
        )

    def _list_hypotheses(self) -> None:
        self._learning_request(self._controller.list_hypotheses)

    def _preview_failure_lessons(self) -> None:
        self._learning_request(
            lambda: self._controller.preview_failure_lessons(self._lesson_run_id.get())
        )

    def _store_failure_lessons(self) -> None:
        self._learning_request(
            lambda: self._controller.store_failure_lessons(self._lesson_run_id.get())
        )

    def _remember_hypothesis_outcomes(self) -> None:
        self._learning_request(
            lambda: self._controller.remember_hypothesis_outcomes(
                self._lesson_run_id.get()
            )
        )

    def _recall_failure_lessons(self) -> None:
        self._learning_request(
            lambda: self._controller.recall_failure_lessons(self._lesson_question.get())
        )

    def _list_failure_lessons(self) -> None:
        self._learning_request(self._controller.list_failure_lessons)

    def _build_security_tab(self, parent: ttk.Frame) -> None:
        """Lay out the weakness taxonomy: record, relate, and look around.

        The point of the graph is the third one. Recording a class is filing;
        asking what shares its root cause or is prevented by the same control
        is the part that catches the four siblings of a finding someone would
        otherwise have treated as one problem.
        """
        self._weakness_family_id = tk.StringVar()
        self._weakness_family_name = tk.StringVar()
        self._weakness_relation_from = tk.StringVar()
        self._weakness_relation_to = tk.StringVar()
        self._weakness_relation_kind = tk.StringVar(
            value=VulnerabilityRelationKind.SHARES_ROOT_CAUSE.value
        )
        self._weakness_lookup_id = tk.StringVar()
        self._weakness_depth = tk.IntVar(value=1)
        self._weakness_status = tk.StringVar(value=_WEAKNESS_IDLE_STATUS)

        parent.rowconfigure(3, weight=1)
        ttk.Label(parent, text=_WEAKNESS_PANEL_NOTE, wraplength=720).grid(
            row=0, column=0, sticky="w"
        )

        record = ttk.LabelFrame(parent, text="Record a weakness class", padding=12)
        record.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        record.columnconfigure(1, weight=1)
        ttk.Label(record, text="ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(record, textvariable=self._weakness_family_id).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        ttk.Label(record, text="Name").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(record, textvariable=self._weakness_family_name).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(record, text="Weakness").grid(
            row=2, column=0, sticky="nw", pady=(6, 0)
        )
        self._weakness_summary_text = tk.Text(record, height=3, wrap="word")
        self._weakness_summary_text.grid(
            row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(record, text="Generally prevented by").grid(
            row=3, column=0, sticky="nw", pady=(6, 0)
        )
        self._weakness_prevention_text = tk.Text(record, height=3, wrap="word")
        self._weakness_prevention_text.grid(
            row=3, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        self._request_button(record, "Record class", self._record_weakness_family).grid(
            row=4, column=1, sticky="w", pady=(8, 0)
        )

        relate = ttk.LabelFrame(parent, text="Relate two classes", padding=12)
        relate.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        relate.columnconfigure(1, weight=1)
        ttk.Label(relate, text="From ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(relate, textvariable=self._weakness_relation_from).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        ttk.Label(relate, text="To ID").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(relate, textvariable=self._weakness_relation_to).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(relate, text="Relation").grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Combobox(
            relate,
            textvariable=self._weakness_relation_kind,
            state="readonly",
            values=tuple(kind.value for kind in VulnerabilityRelationKind),
        ).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        ttk.Label(relate, text="Because").grid(
            row=3, column=0, sticky="nw", pady=(6, 0)
        )
        self._weakness_rationale_text = tk.Text(relate, height=3, wrap="word")
        self._weakness_rationale_text.grid(
            row=3, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )
        ttk.Label(relate, text=_WEAKNESS_RELATION_NOTE, wraplength=680).grid(
            row=4, column=1, sticky="w", padx=(8, 0), pady=(6, 0)
        )
        self._request_button(
            relate, "Record relation", self._record_weakness_relation
        ).grid(row=5, column=1, sticky="w", pady=(8, 0))

        lookup = ttk.LabelFrame(parent, text="Look around a class", padding=12)
        lookup.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        lookup.columnconfigure(1, weight=1)
        lookup.rowconfigure(3, weight=1)
        ttk.Label(lookup, text="Class ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(lookup, textvariable=self._weakness_lookup_id).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        ttk.Label(lookup, text="Depth").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(
            lookup,
            from_=1,
            to=MAX_TRAVERSAL_DEPTH,
            textvariable=self._weakness_depth,
            state="readonly",
            width=5,
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        buttons = ttk.Frame(lookup)
        buttons.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        self._request_button(
            buttons, "Show neighbourhood", self._show_weakness_neighbourhood
        ).grid(row=0, column=0, sticky="w")
        self._request_button(
            buttons, "List recorded classes", self._list_weakness_families
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(lookup, textvariable=self._weakness_status, wraplength=720).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        self._weakness_output = tk.Text(lookup, height=10, wrap="word")
        self._weakness_output.grid(
            row=4, column=0, columnspan=2, sticky="nsew", pady=(6, 0)
        )
        self._weakness_output.configure(state=tk.DISABLED)

    def _record_weakness_family(self) -> None:
        """Send one authored weakness class through the Brain boundary."""
        self._weakness_request(
            lambda: self._controller.record_vulnerability_family(
                self._weakness_family_id.get(),
                self._weakness_family_name.get(),
                self._text_value(self._weakness_summary_text),
                self._text_value(self._weakness_prevention_text),
            )
        )

    def _record_weakness_relation(self) -> None:
        """Send one authored, explained edge through the Brain boundary."""
        self._weakness_request(
            lambda: self._controller.record_vulnerability_relation(
                self._weakness_relation_from.get(),
                self._weakness_relation_to.get(),
                self._weakness_relation_kind.get(),
                self._text_value(self._weakness_rationale_text),
            )
        )

    def _show_weakness_neighbourhood(self) -> None:
        """Ask what else is worth reading near one weakness class."""
        self._weakness_request(
            lambda: self._controller.vulnerability_neighbourhood(
                self._weakness_lookup_id.get(),
                self._weakness_depth.get(),
            )
        )

    def _list_weakness_families(self) -> None:
        """Show every recorded class, traversing nothing."""
        self._weakness_request(self._controller.list_vulnerability_families)

    def _weakness_request(self, call: Callable[[], BrainResponse]) -> None:
        """Run one taxonomy request into the Security panel's own result area."""
        self._panel_request(self._weakness_status, self._weakness_output, call)

    def _panel_request(
        self,
        status: tk.StringVar,
        output: tk.Text,
        call: Callable[[], BrainResponse],
    ) -> BrainResponse | None:
        """Run one request, reporting a refusal as plainly as a result.

        A rejected request is shown in the panel rather than only in the status
        line. An unsuccessful response — a durable-write failure, a refusal —
        is displayed unchanged: these surfaces repeat the runtime's answer and
        never improve on it.
        """
        try:
            response = call()
        except ValueError as error:
            status.set(str(error))
            return None
        status.set("Done." if response.success else "That request did not complete.")
        output.configure(state=tk.NORMAL)
        output.delete("1.0", tk.END)
        output.insert(tk.END, response.message)
        output.configure(state=tk.DISABLED)
        self._append_response(response)
        # Returned so a caller can read canonical fields off the response
        # rather than parsing the text it just rendered. Callers that ignore it
        # are unaffected.
        return response

    @staticmethod
    def _text_value(widget: tk.Text) -> str:
        """Read one multi-line field as a single trimmed value."""
        return widget.get("1.0", tk.END).strip()

    def _build_tool_console_tab(self, parent: ttk.Frame) -> None:
        """Lay out the operator surface for the capabilities actually present."""
        if self._tool_console is None:
            return
        self._tool_entries = self._tool_console.catalogue()
        self._tool_choice = tk.StringVar()
        self._tool_effects = tk.StringVar(value="")
        self._tool_safety = tk.StringVar(value="")
        self._tool_scope = tk.StringVar(value="")
        self._tool_description = tk.StringVar(value="")
        self._tool_status = tk.StringVar(value=_TOOL_IDLE_STATUS)
        self._tool_argument_values: dict[str, tk.StringVar] = {}
        self._tool_argument_texts: dict[str, tk.Text] = {}

        parent.rowconfigure(3, weight=1)

        chooser = ttk.LabelFrame(parent, text="Capability", padding=12)
        chooser.grid(row=0, column=0, sticky="ew")
        chooser.columnconfigure(0, weight=1)
        self._tool_selector = ttk.Combobox(
            chooser,
            textvariable=self._tool_choice,
            state="readonly",
            values=tuple(entry.capability for entry in self._tool_entries),
        )
        self._tool_selector.grid(row=0, column=0, sticky="ew")
        self._tool_selector.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._tool_selected(),
        )
        ttk.Label(chooser, textvariable=self._tool_description, wraplength=720).grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Label(chooser, textvariable=self._tool_safety).grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(chooser, textvariable=self._tool_scope).grid(
            row=3, column=0, sticky="w"
        )

        self._tool_arguments_frame = ttk.LabelFrame(
            parent, text="Arguments", padding=12
        )
        self._tool_arguments_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self._tool_arguments_frame.columnconfigure(1, weight=1)

        authorize = ttk.LabelFrame(parent, text="Authorization", padding=12)
        authorize.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        authorize.columnconfigure(0, weight=1)
        ttk.Label(authorize, textvariable=self._tool_effects, wraplength=720).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(authorize, text=_TOOL_GRANT_NOTE, wraplength=720).grid(
            row=1, column=0, sticky="w", pady=(4, 8)
        )
        self._request_button(
            authorize,
            "Authorize and run once",
            self._run_selected_tool,
        ).grid(row=2, column=0, sticky="w")

        results = ttk.LabelFrame(parent, text="Result", padding=12)
        results.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        results.columnconfigure(0, weight=1)
        results.rowconfigure(2, weight=1)
        ttk.Label(results, textvariable=self._tool_status, wraplength=720).grid(
            row=0, column=0, sticky="w"
        )
        self._tool_output = tk.Text(results, height=7, wrap="word")
        self._tool_output.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self._tool_output.configure(state=tk.DISABLED)
        self._tool_content_metadata = tk.StringVar(value="")
        content = ttk.LabelFrame(
            results,
            text=_CONTENT_PREVIEW_BANNER,
            padding=8,
        )
        content.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)
        ttk.Label(
            content,
            textvariable=self._tool_content_metadata,
            wraplength=960,
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky="w")
        self._tool_content_output = tk.Text(content, height=9, wrap="word")
        self._tool_content_output.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        for sequence in ("<<Copy>>", "<Control-c>", "<Control-C>", "<Command-c>"):
            self._tool_content_output.bind(sequence, lambda _event: "break")
        self._tool_content_output.configure(state=tk.DISABLED)
        if self._tool_entries:
            self._tool_selector.current(0)
            self._tool_selected()

    def _tool_selected(self) -> None:
        """Show what the chosen capability declares, before anything runs."""
        entry = self._selected_tool_entry()
        if entry is None:
            return
        self._tool_description.set(entry.description)
        self._tool_safety.set(entry.safety_note)
        self._tool_scope.set(entry.scope_label)
        self._tool_effects.set(entry.authorization_prompt)
        self._tool_status.set(_TOOL_IDLE_STATUS)
        self._clear_tool_content()
        self._render_tool_arguments(entry)

    def _render_tool_arguments(self, entry: ToolConsoleEntry) -> None:
        """Build one typed control per declared argument, and nothing else.

        There is no free-form field. An operator can fill in what the capability
        declares and cannot express anything it did not, which is what stops the
        panel becoming a place to type whatever the layer happens to accept.
        """
        for child in self._tool_arguments_frame.winfo_children():
            child.destroy()
        self._tool_argument_values = {}
        self._tool_argument_texts = {}
        if not entry.arguments:
            ttk.Label(self._tool_arguments_frame, text=_TOOL_NO_ARGUMENTS).grid(
                row=0, column=0, columnspan=2, sticky="w"
            )
            return
        for row, spec in enumerate(entry.arguments):
            suffix = " *" if spec.required else ""
            ttk.Label(self._tool_arguments_frame, text=spec.label + suffix).grid(
                row=row * 2, column=0, sticky="nw", padx=(0, 8)
            )
            if spec.kind.multiline:
                widget = tk.Text(self._tool_arguments_frame, height=4, wrap="word")
                widget.grid(row=row * 2, column=1, sticky="ew")
                self._tool_argument_texts[spec.name] = widget
            else:
                value = tk.StringVar()
                ttk.Entry(self._tool_arguments_frame, textvariable=value).grid(
                    row=row * 2, column=1, sticky="ew"
                )
                self._tool_argument_values[spec.name] = value
            if spec.hint:
                ttk.Label(self._tool_arguments_frame, text=spec.hint).grid(
                    row=row * 2 + 1, column=1, sticky="w", pady=(0, 6)
                )

    def _selected_tool_entry(self) -> ToolConsoleEntry | None:
        """Return the chosen catalogue entry, matched by exact capability."""
        chosen = self._tool_choice.get().strip()
        for entry in self._tool_entries:
            if entry.capability == chosen:
                return entry
        return None

    def _collect_tool_arguments(
        self,
        entry: ToolConsoleEntry,
    ) -> tuple[tuple[str, str], ...]:
        """Read the form, naming only arguments this capability declared."""
        collected: list[tuple[str, str]] = []
        for spec in entry.arguments:
            if spec.name in self._tool_argument_texts:
                value = self._tool_argument_texts[spec.name].get("1.0", "end-1c")
            elif spec.name in self._tool_argument_values:
                value = self._tool_argument_values[spec.name].get()
            else:
                continue
            collected.append((spec.name, value))
        return tuple(collected)

    def _run_selected_tool(self) -> None:
        """Authorize exactly the declared effects, for exactly this one run.

        The authorization is this method call and nothing else. It is not
        stored, not reused for the next run, and not widened: the controller
        grants the resolved tool's own declared effects and forgets them again.
        """
        if self._tool_console is None:
            return
        entry = self._selected_tool_entry()
        if entry is None:
            self._tool_status.set(_TOOL_NO_SELECTION)
            return
        arguments = self._collect_tool_arguments(entry)
        problem = self._tool_console.validation_problem(entry.capability, arguments)
        if problem is not None:
            self._clear_tool_content()
            self._tool_status.set(problem)
            return
        if entry.capability == _FILESYSTEM_READ_CAPABILITY:
            self._run_confirmed_filesystem_read(entry, arguments)
            return
        view = self._tool_console.run(entry.capability, arguments, authorized=True)
        self._present_tool_run(view)

    def _run_confirmed_filesystem_read(
        self,
        entry: ToolConsoleEntry,
        arguments: tuple[tuple[str, str], ...],
    ) -> None:
        """Confirm one exact local path/range before starting its bounded read."""
        supplied = dict(arguments)
        confirmation = (
            "Read local file content once?\n\n"
            f"Capability: {entry.capability}\n"
            f"Requires: {', '.join(entry.effects)}\n"
            f"{entry.scope_label}\n"
            f"Entry: {supplied['path']}\n"
            f"Offset: {supplied['offset']}\n"
            f"Maximum: {supplied['max_bytes']} bytes\n\n"
            "The result stays in this Tool Console as untrusted local data.\n"
            "It is not sent to a model, memory, research, evidence, or an export.\n"
            "This authorizes one bounded read only."
        )
        if not messagebox.askyesno(
            "Authorize one local file read",
            confirmation,
            parent=self._root,
        ):
            self._clear_tool_content()
            self._tool_status.set("File-content read cancelled before execution.")
            return
        self._clear_tool_content()
        console = self._tool_console
        if console is None:
            return
        capability = entry.capability
        exact_arguments = tuple(arguments)
        self._tool_status.set("Reading one bounded local range...")
        self._start_tool_request(
            lambda: console.run(
                capability,
                exact_arguments,
                authorized=True,
            ),
            self._present_tool_run,
            "Local file read",
        )

    def _present_tool_run(self, view: ToolRunView) -> None:
        """Render generic audit separately from optional literal file content."""
        self._tool_status.set(view.headline + " " + view.detail)
        lines = list(view.lines())
        if lines:
            lines.append("")
        lines.append("Audit")
        lines.extend(view.audit_lines())
        self._tool_output.configure(state=tk.NORMAL)
        self._tool_output.delete("1.0", tk.END)
        self._tool_output.insert(tk.END, chr(10).join(lines))
        self._tool_output.configure(state=tk.DISABLED)
        self._clear_tool_content()
        if view.content_preview is not None:
            self._present_filesystem_content(view.content_preview)

    def _present_filesystem_content(
        self,
        preview: FilesystemContentPreview,
    ) -> None:
        """Insert untrusted text literally, with no parser or action binding."""
        metadata = getattr(self, "_tool_content_metadata", None)
        output = getattr(self, "_tool_content_output", None)
        if metadata is None or output is None:
            return
        metadata.set(chr(10).join(preview.provenance_lines()))
        output.configure(state=tk.NORMAL)
        output.delete("1.0", tk.END)
        output.insert(tk.END, preview.text)
        output.configure(state=tk.DISABLED)

    def _clear_tool_content(self) -> None:
        """Make stale content disappear before every new terminal state."""
        metadata = getattr(self, "_tool_content_metadata", None)
        if metadata is not None:
            metadata.set("")
        output = getattr(self, "_tool_content_output", None)
        if output is None:
            return
        try:
            output.configure(state=tk.NORMAL)
            output.delete("1.0", tk.END)
            output.configure(state=tk.DISABLED)
        except tk.TclError:
            # Close may race only with widget destruction; content remains gone.
            pass

    # ------------------------------------------------------------------
    # Simple research mode
    #
    # A presentation layer over the same canonical services the Advanced tab
    # uses. There is no second research engine here: every state change goes
    # through the existing controller methods, the existing guarded loader, and
    # the existing confirmation, and every displayed fact is re-read from
    # persisted state afterwards rather than inferred from what was returned.
    # ------------------------------------------------------------------

    def _build_simple_research_tab(self, parent: ttk.Frame) -> None:
        """Lay out the guided research panel an ordinary user starts from."""
        self._simple_question = tk.StringVar()
        self._simple_status = tk.StringVar(value=self._simple_say("no_question_yet"))
        self._simple_ladder = tk.StringVar(value="")
        self._simple_stage = tk.StringVar(value="")
        self._simple_evidence = tk.StringVar(value="")
        self._simple_advanced_visible = False

        parent.rowconfigure(2, weight=1)

        ask = ttk.LabelFrame(
            parent,
            text=self._simple_say("panel_title"),
            padding=12,
        )
        ask.grid(row=0, column=0, sticky="ew")
        ask.columnconfigure(0, weight=1)
        ttk.Label(ask, text=self._simple_say("question_prompt")).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        question_entry = ttk.Entry(ask, textvariable=self._simple_question)
        question_entry.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self._simple_question_entry = question_entry
        self._request_button(
            ask,
            self._simple_say("start_research"),
            self._simple_start_research,
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(4, 8))

        status = ttk.LabelFrame(
            parent,
            text=self._simple_say("status_heading"),
            padding=12,
        )
        status.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(
            status,
            textvariable=self._simple_status,
            wraplength=720,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self._simple_ladder, wraplength=720).grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Label(status, textvariable=self._simple_stage, wraplength=720).grid(
            row=2, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Label(status, textvariable=self._simple_evidence, wraplength=720).grid(
            row=3, column=0, sticky="w", pady=(4, 0)
        )
        self._request_button(
            status,
            self._simple_say("find_sources"),
            self._simple_find_sources,
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))

        sources = ttk.LabelFrame(
            parent,
            text=self._simple_say("sources_heading"),
            padding=12,
        )
        sources.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        sources.columnconfigure(0, weight=1)
        self._simple_cards_frame = ttk.Frame(sources)
        self._simple_cards_frame.grid(row=0, column=0, sticky="nsew")
        self._simple_cards_frame.columnconfigure(0, weight=1)

        advanced = ttk.Frame(parent)
        advanced.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        advanced.columnconfigure(0, weight=1)
        ttk.Button(
            advanced,
            text=self._simple_say("advanced_details"),
            command=self._simple_toggle_advanced,
        ).grid(row=0, column=0, sticky="w")
        self._simple_advanced_text = tk.Text(advanced, height=8, wrap="word")
        self._simple_advanced_text.configure(state=tk.DISABLED)
        self._simple_advanced_frame = advanced
        self._simple_render()

    def _simple_say(self, key: str) -> str:
        """Look up one fixed Simple-mode string in the active language."""
        return simple_phrase(key, self._simple_language)

    def _simple_model(self) -> SimpleResearchReadModel:
        """Build the projection from the canonical snapshot Simple mode holds."""
        return SimpleResearchReadModel(
            run=self._simple_run,
            language=self._simple_language,
            activity=self._simple_activity,
            last_stage=self._simple_last_stage,
        )

    def _simple_render(self) -> None:
        """Push the projection into the widgets, if the tab was ever built.

        Focused tests build bare windows to exercise one handler, so this stays
        safe when no widget exists. Everything it renders comes from the read
        model, so there is no path here that can display a fact the projection
        did not derive from canonical state.
        """
        if not hasattr(self, "_simple_status"):
            return
        model = self._simple_model()
        self._simple_status.set(model.status_text())
        self._simple_ladder.set(
            "  ".join(
                f"{'●' if reached else '○'} {label}"
                for label, reached in model.ladder()
            )
        )
        self._simple_stage.set(model.stage_text())
        self._simple_evidence.set(model.evidence_text())
        self._simple_cards = model.candidate_cards()
        self._simple_render_cards()
        self._simple_render_advanced(model)

    def _simple_render_cards(self) -> None:
        """Replace the card list with the current projection, one row each."""
        if not hasattr(self, "_simple_cards_frame"):
            return
        for child in self._simple_cards_frame.winfo_children():
            child.destroy()
        if not self._simple_cards:
            ttk.Label(
                self._simple_cards_frame,
                text=self._simple_say("no_sources_yet"),
                wraplength=700,
            ).grid(row=0, column=0, sticky="w")
            return
        for index, card in enumerate(self._simple_cards):
            row = ttk.Frame(self._simple_cards_frame, padding=(0, 6))
            row.grid(row=index, column=0, sticky="ew")
            row.columnconfigure(0, weight=1)
            ttk.Label(row, text=card.heading, wraplength=620).grid(
                row=0, column=0, sticky="w"
            )
            ttk.Label(row, text=card.subheading).grid(row=1, column=0, sticky="w")
            ttk.Label(row, text=card.status_text, wraplength=620).grid(
                row=2, column=0, sticky="w"
            )
            if not card.accepted:
                self._request_button(
                    row,
                    self._simple_say("use_this_source"),
                    self._simple_card_command(index),
                ).grid(row=0, column=1, rowspan=3, sticky="e", padx=(8, 0))

    def _simple_card_command(self, position: int) -> Callable[[], None]:
        """Bind one card's position, so every row acts on its own source.

        A closure over the loop variable would give every button the last
        index, and each one would then load a source the user did not press.
        """

        def use() -> None:
            self._simple_use_source(position)

        return use

    def _simple_render_advanced(self, model: SimpleResearchReadModel) -> None:
        """Write every hidden identifier out unchanged, when asked for."""
        if not hasattr(self, "_simple_advanced_text"):
            return
        lines = [self._simple_say("advanced_hidden_note"), ""]
        lines.extend(f"{label}: {value}" for label, value in model.advanced_details())
        self._simple_advanced_text.configure(state=tk.NORMAL)
        self._simple_advanced_text.delete("1.0", tk.END)
        self._simple_advanced_text.insert(tk.END, "\n".join(lines))
        self._simple_advanced_text.configure(state=tk.DISABLED)

    def _simple_toggle_advanced(self) -> None:
        """Show or hide the identifiers, which are moved rather than removed."""
        if not hasattr(self, "_simple_advanced_text"):
            return
        self._simple_advanced_visible = not self._simple_advanced_visible
        if self._simple_advanced_visible:
            self._simple_advanced_text.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        else:
            self._simple_advanced_text.grid_remove()

    def _simple_start_research(self) -> None:
        """Create one run for the typed question and keep it as the context.

        The run is created and then held here, so a person is never told that
        no research run is selected. It is never inherited from the Advanced
        selector: attaching a source to a run the user did not create in this
        workflow is the one mistake this whole panel exists to prevent.
        """
        question = self._simple_question.get().strip()
        if not question:
            self._status.set(self._simple_say("question_required"))
            return
        self._simple_language = detect_response_language(question)
        try:
            response = self._controller.create_research_run(question)
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)
        if not response.success or not response.research_runs:
            return
        created = response.research_runs[-1]
        self._simple_run_id = created.run_id
        self._simple_run = created
        self._simple_discovery_id = ""
        self._simple_last_stage = None
        self._simple_render()
        self._simple_find_sources()

    def _simple_find_sources(self) -> None:
        """Ask the existing discovery service for candidates for this run."""
        if not self._simple_run_id:
            self._status.set(self._simple_say("question_required"))
            return
        run_id = self._simple_run_id
        cancellation_signal = CancellationSignal()
        self._simple_activity = SimpleResearchActivity.FINDING_SOURCES
        self._simple_render()
        self._start_request(
            lambda: self._controller.discover_research_sources(
                run_id,
                cancellation_token=cancellation_signal,
            ),
            self._complete_simple_discovery,
            "simple research discovery",
            cancellation_signal=cancellation_signal,
        )

    def _complete_simple_discovery(self, response: BrainResponse) -> None:
        """Adopt the discovered candidates from canonical run state only."""
        self._append_response(response)
        self._simple_activity = SimpleResearchActivity.IDLE
        self._simple_adopt_canonical(response)
        self._simple_render()

    def _simple_use_source(self, position: int) -> None:
        """Preview, confirm, then load one card through the guarded path.

        This is one button for the user and the same three boundaries
        underneath. The preview still runs, the confirmation is still shown,
        and the fetch still goes through the loader that validates the URL.
        Nothing is skipped because the surface got smaller.
        """
        if not 0 <= position < len(self._simple_cards):
            self._status.set(self._simple_say("select_source_first"))
            return
        card = self._simple_cards[position]
        if not self._simple_run_id or not self._simple_discovery_id:
            self._status.set(self._simple_say("select_source_first"))
            return
        run_id = self._simple_run_id
        discovery_id = self._simple_discovery_id
        try:
            preview_response = (
                self._controller.preview_research_source_candidate_acceptance(
                    run_id,
                    discovery_id,
                    card.url,
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
            self._simple_say("confirm_title"),
            f"{card.heading}\n{card.subheading}\n\n"
            f"{self._simple_say('confirm_body')}",
            parent=self._root,
        ):
            self._status.set(self._simple_say("cancelled_by_user"))
            return
        cancellation_signal = CancellationSignal()
        self._simple_activity = SimpleResearchActivity.LOADING_SOURCE
        self._simple_render()
        self._start_request(
            lambda: self._controller.accept_research_source_candidate(
                run_id,
                discovery_id,
                card.url,
                cancellation_token=cancellation_signal,
            ),
            self._complete_simple_source_load,
            "simple research source load",
            cancellation_signal=cancellation_signal,
        )

    def _complete_simple_source_load(self, response: BrainResponse) -> None:
        """Report the stage the loader reached, then re-read canonical state.

        The stage is taken from the loader because it is a fact about what
        happened. Everything else is re-read, because a response saying a
        source was accepted and a run holding that source are different claims,
        and only the second one is the one this panel is allowed to show.
        """
        self._append_response(response)
        self._simple_activity = SimpleResearchActivity.IDLE
        self._simple_last_stage = response.source_load_stage
        self._simple_refresh_canonical()
        self._simple_render()

    def _simple_refresh_canonical(self) -> None:
        """Re-read the persisted run rather than trusting an earlier result."""
        if not self._simple_run_id:
            return
        try:
            response = self._controller.list_research_runs()
        except ValueError:
            return
        self._simple_adopt_canonical(response)

    def _simple_adopt_canonical(self, response: BrainResponse) -> None:
        """Take the run matching the Simple context, and nothing else.

        Matching by ID matters. A response carrying several runs must never
        move this panel onto a different one, because the source the user is
        about to load would then attach somewhere they never chose.
        """
        if not response.success or not self._simple_run_id:
            return
        for run in response.research_runs:
            if run.run_id != self._simple_run_id:
                continue
            self._simple_run = run
            if run.discoveries:
                self._simple_discovery_id = run.discoveries[-1].discovery_id
            return

    def _offer_simple_research_handoff(self, question: str) -> None:
        """Carry a chat question into Simple mode as a draft, not as an action.

        This creates nothing and fetches nothing. It fills the question box and
        moves the user to the panel, so starting the research stays an explicit
        press. Text that arrived in a conversation must not become authority to
        run anything, however clearly it reads as a request.
        """
        if not hasattr(self, "_simple_question"):
            return
        self._simple_question.set(question.strip())
        self._simple_language = detect_response_language(question)
        if hasattr(self, "_workspace_tabs"):
            self._workspace_tabs.select(2)
        self._status.set(self._simple_say("start_research"))

    def _discover_research_sources(self) -> None:
        """Discover and display metadata candidates for the selected run."""
        run_id = self._research_run_id.get()
        cancellation_signal = CancellationSignal()
        self._start_request(
            lambda: self._controller.discover_research_sources(
                run_id,
                self._research_discovery_provider.get(),
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
        """Replace stale candidate choices with this run's recorded discoveries."""
        self._clear_research_candidates()
        if not response.success:
            return
        selected_run_id = self._research_run_id.get().strip()
        selected_runs = [
            run for run in response.research_runs if run.run_id == selected_run_id
        ]
        if not selected_runs:
            return
        self._show_research_run_candidates(selected_runs[0])

    def _show_research_run_candidates(self, run: ResearchRun) -> None:
        """Offer every recorded discovery's candidates, not only the newest one.

        A paired comparison records one discovery per provider, so listing only
        the most recent left the other provider's candidates readable in the
        comparison report and impossible to accept. A paired run could then only
        ever be assessed on one half, which is exactly the half of the data the
        measurement was for.

        Each discovery is still ranked on its own. The lists are shown together
        because they are one run's work, not because they are one ranking:
        every row names the provider it came from and keeps that provider's own
        position, and no row is ranked against a row from the other side.
        """
        self._clear_research_candidates()
        if not run.discoveries:
            return
        self._research_candidate_run_id = run.run_id
        candidates: list[ResearchSourceCandidate] = []
        discovery_ids: list[str] = []
        labels: list[str] = []
        for discovery in run.discoveries:
            # Relevance order is the default, and the provider's own position
            # travels with each row. The audit view shows the exact codes rather
            # than a phrase: a person reading this panel is the person who needs
            # to know that `technical_identifier_missing` is why something sank.
            for entry in ranked_candidates(discovery):
                candidates.append(entry.candidate)
                discovery_ids.append(discovery.discovery_id)
                labels.append(
                    f"{discovery.provider} {entry.relevance_rank}. "
                    f"[{entry.relevance.category.value} {entry.relevance.score}] "
                    f"(provider #{entry.provider_rank}"
                    + (
                        f", duplicate of #{entry.duplicate_of_rank}"
                        if entry.duplicate_of_rank is not None
                        else ""
                    )
                    + f") {entry.candidate.title} — {entry.candidate.url}"
                    + _vulnerability_label(entry.candidate)
                    + (
                        " ["
                        + ", ".join(reason.value for reason in entry.relevance.reasons)
                        + "]"
                        if entry.relevance.reasons
                        else ""
                    )
                )
        self._research_candidates = tuple(candidates)
        self._research_candidate_discovery_ids = tuple(discovery_ids)
        self._research_candidate_selector.configure(values=tuple(labels))
        if labels:
            self._research_candidate_selector.current(0)
            self._research_candidate_discovery_id = discovery_ids[0]

    def _clear_research_candidates(self) -> None:
        self._research_candidates = ()
        self._research_candidate_discovery_ids = ()
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
        # The discovery is read per candidate. One list can hold both sides of
        # a paired run, and accepting a Crossref candidate against the NVD
        # discovery would file it under a search that never returned it.
        return (
            run_id,
            self._research_candidate_discovery_ids[selected_index],
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
                "This performs one bounded network request, indexes the result "
                "locally, and attaches it to the research run. Continue?"
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
            self._research_source_usefulness.get(),
            self._research_source_applicability.get(),
            self._research_source_independence.get(),
            self._research_source_publication_status.get(),
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

    def _configure_transcript_styles(self) -> None:
        """Prepare styling tags, tolerating a font the platform cannot derive.

        Styling is presentation only. If a derived font is unavailable the tags
        simply do nothing and the transcript reads exactly as before.
        """
        try:
            base = font.nametofont(self._transcript.cget("font"))
            bold = base.copy()
            bold.configure(weight="bold")
            italic = base.copy()
            italic.configure(slant="italic")
            self._transcript.tag_configure(MarkdownStyle.BOLD.value, font=bold)
            self._transcript.tag_configure(MarkdownStyle.ITALIC.value, font=italic)
            self._transcript.tag_configure(
                MarkdownStyle.CODE.value,
                font=font.nametofont("TkFixedFont"),
            )
        except tk.TclError:
            return

    def _append_to_transcript(self, value: str) -> None:
        self._transcript.configure(state=tk.NORMAL)
        for segment in markdown_segments(value):
            if segment.style is MarkdownStyle.PLAIN:
                self._transcript.insert(tk.END, segment.text)
            else:
                self._transcript.insert(tk.END, segment.text, segment.style.value)
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


def _vulnerability_label(candidate: ResearchSourceCandidate) -> str:
    """Render the structured vulnerability facts a candidate carries, if any.

    Bounded fields, never the provider's raw document. Severity and known
    exploitation are shown because a person deciding what to read wants them,
    and they are shown as what they are: each metric attributed to whoever
    scored it, and neither one folded into the relevance score sitting next to
    them on the same line.
    """
    record = candidate.vulnerability
    if record is None:
        return ""
    parts = [record.cve_id]
    if record.status:
        parts.append(f"status {record.status}")
    if record.weaknesses:
        parts.append(",".join(record.weaknesses))
    if record.metrics:
        parts.append(
            "severity " + " / ".join(metric.summary() for metric in record.metrics)
        )
    if record.known_exploited:
        parts.append("CISA known-exploited")
    parts.append(
        f"{len(record.references)}/{record.reference_total} reference(s), "
        "none fetched"
    )
    return " {" + "; ".join(parts) + "}"
