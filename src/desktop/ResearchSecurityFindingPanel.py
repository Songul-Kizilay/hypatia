"""Operator-authored Bug Bounty security findings: promote, cite, transition, list.

Reuses the exact `ttk.Treeview` + scrollbar + `<<TreeviewSelect>>` +
`iid -> detail-text` dict pattern already established by
`ResearchSecurityHypothesisPanel`. Plain text labels distinguish `CANDIDATE`
from `VALIDATED` — no color or severity styling of any kind, since this
milestone adds no severity concept and `VALIDATED` is never authority to act.

Each listing row names its kind, subject, status, source hypothesis, and
creation time, as the milestone's panel scope requires. The fixed
not-authority notice is imported from `response.ResponseComposer` rather than
restated, so its wording can never drift between the panel and Brain
responses. The detail pane shows it for every status, terminal ones included
— stricter than the Brain responses, which omit it for terminal statuses.
`desktop` already depends on `response` elsewhere and `response` never
imports `desktop`, so this adds no new layer direction or cycle.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from brain.BrainResponse import BrainResponse
from desktop.DesktopController import DesktopController
from research.ResearchSecurityFindingEvidenceRelation import (
    ResearchSecurityFindingEvidenceRelation,
)
from research.ResearchSecurityFindingStatus import ResearchSecurityFindingStatus
from response.ResponseComposer import SECURITY_FINDING_NOT_AUTHORITY_NOTICE


def _single_line(value: str) -> str:
    """Render one recorded field as a single line, or say there is none."""
    return " ".join(value.split()) or "none"


class ResearchSecurityFindingPanel:
    """List, create, cite evidence for, and transition security findings."""

    def __init__(
        self,
        parent: ttk.Frame,
        controller: DesktopController,
        dispatch: Callable[
            [Callable[[], BrainResponse], Callable[[BrainResponse], None], str], None
        ],
    ) -> None:
        self._controller = controller
        self._dispatch = dispatch
        self._details: dict[str, str] = {}
        relations = tuple(
            relation.value for relation in ResearchSecurityFindingEvidenceRelation
        )
        statuses = tuple(status.value for status in ResearchSecurityFindingStatus)

        self.program_id = tk.StringVar(master=parent)
        self.source_hypothesis_id = tk.StringVar(master=parent)
        self.title = tk.StringVar(master=parent)
        self.description = tk.StringVar(master=parent)
        self.required_followup = tk.StringVar(master=parent)

        self.attach_finding_id = tk.StringVar(master=parent)
        self.attach_evidence_ids = tk.StringVar(master=parent)
        self.attach_relation = tk.StringVar(
            master=parent,
            value=ResearchSecurityFindingEvidenceRelation.SUPPORTS.value,
        )

        self.transition_finding_id = tk.StringVar(master=parent)
        self.transition_status = tk.StringVar(
            master=parent, value=ResearchSecurityFindingStatus.VALIDATION_REQUIRED.value
        )
        self.transition_reason = tk.StringVar(master=parent)
        self.transition_duplicate_of_finding_id = tk.StringVar(master=parent)
        self.transition_superseded_by_finding_id = tk.StringVar(master=parent)

        self.status = tk.StringVar(
            master=parent, value="Enter a program ID and load findings."
        )
        self.detail = tk.StringVar(
            master=parent, value="Select a row to see its recorded fields."
        )

        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)
        parent.rowconfigure(5, weight=1)

        ttk.Label(parent, text="Program ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.program_id).grid(
            row=0, column=1, columnspan=2, sticky="ew", padx=8, pady=4
        )
        ttk.Button(parent, text="Load findings", command=self.load).grid(
            row=0, column=3, padx=4
        )

        create_frame = ttk.LabelFrame(
            parent, text="Record a new security finding", padding=8
        )
        create_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        create_frame.columnconfigure(1, weight=1)
        create_frame.columnconfigure(3, weight=1)
        ttk.Label(create_frame, text="Source hypothesis ID").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(create_frame, textvariable=self.source_hypothesis_id).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Label(create_frame, text="Title (never enter a secret)").grid(
            row=1, column=0, sticky="w"
        )
        ttk.Entry(create_frame, textvariable=self.title).grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Label(create_frame, text="Description (never enter a secret)").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Entry(create_frame, textvariable=self.description).grid(
            row=2, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Label(create_frame, text="Required followup (never enter a secret)").grid(
            row=3, column=0, sticky="w"
        )
        ttk.Entry(create_frame, textvariable=self.required_followup).grid(
            row=3, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Button(
            create_frame, text="Record finding", command=self.create_finding
        ).grid(row=4, column=3, sticky="e", pady=(4, 0))

        attach_frame = ttk.LabelFrame(parent, text="Attach evidence", padding=8)
        attach_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        attach_frame.columnconfigure(1, weight=1)
        attach_frame.columnconfigure(3, weight=1)
        ttk.Label(attach_frame, text="Finding ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(attach_frame, textvariable=self.attach_finding_id).grid(
            row=0, column=1, sticky="ew", padx=8, pady=2
        )
        ttk.Label(attach_frame, text="Relation").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            attach_frame,
            textvariable=self.attach_relation,
            values=relations,
            state="readonly",
        ).grid(row=0, column=3, sticky="ew", padx=8, pady=2)
        ttk.Label(attach_frame, text="HTTP evidence IDs (comma-separated)").grid(
            row=1, column=0, sticky="w"
        )
        ttk.Entry(attach_frame, textvariable=self.attach_evidence_ids).grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Button(
            attach_frame, text="Attach evidence", command=self.attach_evidence
        ).grid(row=2, column=3, sticky="e", pady=(4, 0))

        transition_frame = ttk.LabelFrame(parent, text="Transition status", padding=8)
        transition_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        transition_frame.columnconfigure(1, weight=1)
        transition_frame.columnconfigure(3, weight=1)
        ttk.Label(transition_frame, text="Finding ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(transition_frame, textvariable=self.transition_finding_id).grid(
            row=0, column=1, sticky="ew", padx=8, pady=2
        )
        ttk.Label(transition_frame, text="New status").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            transition_frame,
            textvariable=self.transition_status,
            values=statuses,
            state="readonly",
        ).grid(row=0, column=3, sticky="ew", padx=8, pady=2)
        ttk.Label(transition_frame, text="Reason (never enter a secret)").grid(
            row=1, column=0, sticky="w"
        )
        ttk.Entry(transition_frame, textvariable=self.transition_reason).grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Label(
            transition_frame, text="Duplicate-of finding ID (if applicable)"
        ).grid(row=2, column=0, sticky="w")
        ttk.Entry(
            transition_frame, textvariable=self.transition_duplicate_of_finding_id
        ).grid(row=2, column=1, sticky="ew", padx=8, pady=2)
        ttk.Label(
            transition_frame, text="Superseded-by finding ID (if applicable)"
        ).grid(row=2, column=2, sticky="w")
        ttk.Entry(
            transition_frame, textvariable=self.transition_superseded_by_finding_id
        ).grid(row=2, column=3, sticky="ew", padx=8, pady=2)
        ttk.Button(
            transition_frame,
            text="Transition status",
            command=self.transition_finding_status,
        ).grid(row=3, column=3, sticky="e", pady=(4, 0))

        ttk.Label(parent, textvariable=self.status, wraplength=900).grid(
            row=4, column=0, columnspan=4, sticky="w", pady=(8, 0)
        )

        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=5, column=0, columnspan=4, sticky="nsew", pady=(4, 0))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, show="tree", height=12)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.tree.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        ttk.Label(
            parent, textvariable=self.detail, wraplength=900, justify=tk.LEFT
        ).grid(row=6, column=0, columnspan=4, sticky="w", pady=(4, 0))

    def load(self) -> None:
        """Fetch the derived read-only finding listing; never itself a mutation."""
        program_id = self.program_id.get().strip()
        if not program_id:
            self.status.set("Enter a program ID first.")
            return

        def action() -> BrainResponse:
            return self._controller.preview_research_security_findings(program_id)

        self._dispatch(action, self._render, "security findings")

    def create_finding(self) -> None:
        program_id = self.program_id.get().strip()
        source_hypothesis_id = self.source_hypothesis_id.get().strip()
        if not program_id or not source_hypothesis_id:
            self.status.set("Enter a program ID and source hypothesis ID first.")
            return
        title = self.title.get()
        description = self.description.get()
        required_followup = self.required_followup.get()

        def action() -> BrainResponse:
            return self._controller.create_research_security_finding(
                program_id,
                source_hypothesis_id,
                title,
                description,
                required_followup,
            )

        self._dispatch(action, self._after_write, "security finding")

    def attach_evidence(self) -> None:
        program_id = self.program_id.get().strip()
        finding_id = self.attach_finding_id.get().strip()
        if not program_id or not finding_id:
            self.status.set("Enter a program ID and finding ID first.")
            return
        evidence_ids = tuple(
            value.strip()
            for value in self.attach_evidence_ids.get().split(",")
            if value.strip()
        )
        relation = self.attach_relation.get()

        def action() -> BrainResponse:
            return self._controller.attach_research_security_finding_evidence(
                finding_id, program_id, evidence_ids, relation
            )

        self._dispatch(action, self._after_write, "security finding evidence")

    def transition_finding_status(self) -> None:
        program_id = self.program_id.get().strip()
        finding_id = self.transition_finding_id.get().strip()
        if not program_id or not finding_id:
            self.status.set("Enter a program ID and finding ID first.")
            return
        new_status = self.transition_status.get()
        reason = self.transition_reason.get()
        duplicate_of_finding_id = self.transition_duplicate_of_finding_id.get()
        superseded_by_finding_id = self.transition_superseded_by_finding_id.get()

        def action() -> BrainResponse:
            return self._controller.transition_research_security_finding_status(
                finding_id,
                program_id,
                new_status,
                reason,
                duplicate_of_finding_id,
                superseded_by_finding_id,
            )

        self._dispatch(action, self._after_write, "security finding status transition")

    def _after_write(self, response: BrainResponse) -> None:
        self.status.set(response.message)
        if response.success:
            self.load()

    def _render(self, response: BrainResponse) -> None:
        self.status.set(response.message)
        for item in self.tree.get_children(""):
            self.tree.delete(item)
        self._details = {}
        self.detail.set("Select a row to see its recorded fields.")
        if not response.success:
            return
        for entry in response.research_security_findings:
            finding = entry.finding
            if entry.scope.has_active_scope_revision and entry.scope.resolution:
                scope_text = (
                    f"{entry.scope.resolution.status.value} "
                    "(recomputed live from active policy, not stored)"
                )
            else:
                scope_text = "no active scope revision for this program"
            label = (
                f"{finding.finding_kind.value} on "
                f"{finding.subject_kind.value}:{finding.subject_canonical_value} "
                f"({finding.status.value}) from hypothesis "
                f"{finding.source_hypothesis_id}, created "
                f"{finding.created_at.isoformat()}"
            )
            iid = self.tree.insert("", "end", text=label)
            history_lines = [
                f"  {transition.recorded_at.isoformat()}: {transition.status.value}"
                f" ({_single_line(transition.reason)})"
                for transition in finding.status_history
            ] or ["  none"]
            supporting_ids = (
                ", ".join(link.evidence_id for link in finding.supporting_evidence)
                or "none"
            )
            contradicting_ids = (
                ", ".join(link.evidence_id for link in finding.contradicting_evidence)
                or "none"
            )
            validation_ids = (
                ", ".join(link.evidence_id for link in finding.validation_evidence)
                or "none"
            )
            latest = finding.status_history[-1] if finding.status_history else None
            duplicate_of = (
                latest.duplicate_of_finding_id if latest is not None else None
            ) or "none"
            superseded_by = (
                latest.superseded_by_finding_id if latest is not None else None
            ) or "none"
            self._details[iid] = "\n".join(
                (
                    f"Finding ID: {finding.finding_id}",
                    f"Program: {finding.program_id}",
                    f"Source hypothesis: {finding.source_hypothesis_id}",
                    f"Kind: {finding.finding_kind.value}",
                    "Subject: "
                    f"{finding.subject_kind.value}:{finding.subject_canonical_value}",
                    f"Title: {_single_line(finding.title)}",
                    f"Description: {_single_line(finding.description)}",
                    f"Required followup: {_single_line(finding.required_followup)}",
                    f"Origin: {finding.origin.value}",
                    f"Created at: {finding.created_at.isoformat()}",
                    f"Status: {finding.status.value}",
                    f"Supporting evidence IDs: {supporting_ids}",
                    f"Contradicting evidence IDs: {contradicting_ids}",
                    f"Validation evidence IDs: {validation_ids}",
                    f"Duplicate of: {duplicate_of}",
                    f"Superseded by: {superseded_by}",
                    "Status history:",
                    *history_lines,
                    f"Scope: {scope_text}",
                    SECURITY_FINDING_NOT_AUTHORITY_NOTICE,
                )
            )

    def _on_select(self, _event: object = None) -> None:
        """Show one already-loaded row's fields. Never starts a request."""
        selected = self.tree.selection()
        if not selected:
            self.detail.set("Select a row to see its recorded fields.")
            return
        self.detail.set(
            self._details.get(selected[0], "No detail is recorded for this row.")
        )
