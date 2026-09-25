"""Operator-authored Bug Bounty security hypotheses: create, cite, transition, list.

Reuses the exact `ttk.Treeview` + scrollbar + `<<TreeviewSelect>>` +
`iid -> detail-text` dict pattern already established by
`ResearchAssetInventoryPanel`. No vulnerability dashboard, no severity
display, no confidence score: a hypothesis is reasoning over already-recorded
evidence, never a finding, and this panel never renders anything that could
be mistaken for one.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from brain.BrainResponse import BrainResponse
from desktop.DesktopController import DesktopController
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchSecurityHypothesisEvidenceRelation import (
    ResearchSecurityHypothesisEvidenceRelation,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityHypothesisStatus import ResearchSecurityHypothesisStatus


def _single_line(value: str) -> str:
    """Render one recorded field as a single line, or say there is none."""
    return " ".join(value.split()) or "none"


class ResearchSecurityHypothesisPanel:
    """List, create, cite evidence for, and transition security hypotheses."""

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
        hypothesis_kinds = tuple(kind.value for kind in ResearchSecurityHypothesisKind)
        subject_kinds = tuple(kind.value for kind in ResearchAssetKind)
        relations = tuple(
            relation.value for relation in ResearchSecurityHypothesisEvidenceRelation
        )
        statuses = tuple(status.value for status in ResearchSecurityHypothesisStatus)

        self.program_id = tk.StringVar(master=parent)
        self.hypothesis_kind = tk.StringVar(
            master=parent, value=ResearchSecurityHypothesisKind.UNKNOWN.value
        )
        self.subject_kind = tk.StringVar(
            master=parent, value=ResearchAssetKind.HOSTNAME.value
        )
        self.subject_value = tk.StringVar(master=parent)
        self.statement = tk.StringVar(master=parent)
        self.rationale = tk.StringVar(master=parent)
        self.required_validation = tk.StringVar(master=parent)
        self.supporting_evidence_ids = tk.StringVar(master=parent)

        self.attach_hypothesis_id = tk.StringVar(master=parent)
        self.attach_evidence_ids = tk.StringVar(master=parent)
        self.attach_relation = tk.StringVar(
            master=parent,
            value=ResearchSecurityHypothesisEvidenceRelation.SUPPORTS.value,
        )

        self.transition_hypothesis_id = tk.StringVar(master=parent)
        self.transition_status = tk.StringVar(
            master=parent, value=ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE.value
        )
        self.transition_reason = tk.StringVar(master=parent)

        self.status = tk.StringVar(
            master=parent, value="Enter a program ID and load hypotheses."
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
        ttk.Button(parent, text="Load hypotheses", command=self.load).grid(
            row=0, column=3, padx=4
        )

        create_frame = ttk.LabelFrame(
            parent, text="Record a new security hypothesis", padding=8
        )
        create_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        create_frame.columnconfigure(1, weight=1)
        create_frame.columnconfigure(3, weight=1)
        ttk.Label(create_frame, text="Kind").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            create_frame,
            textvariable=self.hypothesis_kind,
            values=hypothesis_kinds,
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=8, pady=2)
        ttk.Label(create_frame, text="Subject kind").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            create_frame,
            textvariable=self.subject_kind,
            values=subject_kinds,
            state="readonly",
        ).grid(row=0, column=3, sticky="ew", padx=8, pady=2)
        ttk.Label(create_frame, text="Subject value").grid(row=1, column=0, sticky="w")
        ttk.Entry(create_frame, textvariable=self.subject_value).grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Label(create_frame, text="Statement (never enter a secret)").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Entry(create_frame, textvariable=self.statement).grid(
            row=2, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Label(create_frame, text="Rationale (never enter a secret)").grid(
            row=3, column=0, sticky="w"
        )
        ttk.Entry(create_frame, textvariable=self.rationale).grid(
            row=3, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Label(create_frame, text="Required validation (never enter a secret)").grid(
            row=4, column=0, sticky="w"
        )
        ttk.Entry(create_frame, textvariable=self.required_validation).grid(
            row=4, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Label(create_frame, text="Supporting HTTP evidence IDs (comma-sep.)").grid(
            row=5, column=0, sticky="w"
        )
        ttk.Entry(create_frame, textvariable=self.supporting_evidence_ids).grid(
            row=5, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Button(
            create_frame, text="Record hypothesis", command=self.create_hypothesis
        ).grid(row=6, column=3, sticky="e", pady=(4, 0))

        attach_frame = ttk.LabelFrame(parent, text="Attach evidence", padding=8)
        attach_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        attach_frame.columnconfigure(1, weight=1)
        attach_frame.columnconfigure(3, weight=1)
        ttk.Label(attach_frame, text="Hypothesis ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(attach_frame, textvariable=self.attach_hypothesis_id).grid(
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
        ttk.Label(transition_frame, text="Hypothesis ID").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(transition_frame, textvariable=self.transition_hypothesis_id).grid(
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
        ttk.Button(
            transition_frame,
            text="Transition status",
            command=self.transition_hypothesis_status,
        ).grid(row=2, column=3, sticky="e", pady=(4, 0))

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
        """Fetch the derived read-only hypothesis listing; never itself a mutation."""
        program_id = self.program_id.get().strip()
        if not program_id:
            self.status.set("Enter a program ID first.")
            return

        def action() -> BrainResponse:
            return self._controller.preview_research_security_hypotheses(program_id)

        self._dispatch(action, self._render, "security hypotheses")

    def create_hypothesis(self) -> None:
        program_id = self.program_id.get().strip()
        if not program_id:
            self.status.set("Enter a program ID first.")
            return
        hypothesis_kind = self.hypothesis_kind.get()
        subject_kind = self.subject_kind.get()
        subject_value = self.subject_value.get()
        statement = self.statement.get()
        rationale = self.rationale.get()
        required_validation = self.required_validation.get()
        supporting_evidence_ids = tuple(
            value.strip()
            for value in self.supporting_evidence_ids.get().split(",")
            if value.strip()
        )

        def action() -> BrainResponse:
            return self._controller.create_research_security_hypothesis(
                program_id,
                hypothesis_kind,
                subject_kind,
                subject_value,
                statement,
                rationale,
                required_validation,
                supporting_evidence_ids,
            )

        self._dispatch(action, self._after_write, "security hypothesis")

    def attach_evidence(self) -> None:
        program_id = self.program_id.get().strip()
        hypothesis_id = self.attach_hypothesis_id.get().strip()
        if not program_id or not hypothesis_id:
            self.status.set("Enter a program ID and hypothesis ID first.")
            return
        evidence_ids = tuple(
            value.strip()
            for value in self.attach_evidence_ids.get().split(",")
            if value.strip()
        )
        relation = self.attach_relation.get()

        def action() -> BrainResponse:
            return self._controller.attach_research_security_hypothesis_evidence(
                hypothesis_id, program_id, evidence_ids, relation
            )

        self._dispatch(action, self._after_write, "security hypothesis evidence")

    def transition_hypothesis_status(self) -> None:
        program_id = self.program_id.get().strip()
        hypothesis_id = self.transition_hypothesis_id.get().strip()
        if not program_id or not hypothesis_id:
            self.status.set("Enter a program ID and hypothesis ID first.")
            return
        new_status = self.transition_status.get()
        reason = self.transition_reason.get()

        def action() -> BrainResponse:
            return self._controller.transition_research_security_hypothesis_status(
                hypothesis_id, program_id, new_status, reason
            )

        self._dispatch(
            action, self._after_write, "security hypothesis status transition"
        )

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
        for entry in response.research_security_hypotheses:
            hypothesis = entry.hypothesis
            if entry.scope.has_active_scope_revision and entry.scope.resolution:
                scope_text = (
                    f"{entry.scope.resolution.status.value} "
                    "(recomputed live from active policy, not stored)"
                )
            else:
                scope_text = "no active scope revision for this program"
            label = (
                f"{hypothesis.hypothesis_kind.value} on "
                f"{hypothesis.subject_kind.value}:{hypothesis.subject_canonical_value} "
                f"({hypothesis.status.value})"
            )
            iid = self.tree.insert("", "end", text=label)
            history_lines = [
                f"  {transition.recorded_at.isoformat()}: {transition.status.value}"
                f" ({_single_line(transition.reason)})"
                for transition in hypothesis.status_history
            ] or ["  none"]
            supporting_ids = (
                ", ".join(link.evidence_id for link in hypothesis.supporting_evidence)
                or "none"
            )
            contradicting_ids = (
                ", ".join(
                    link.evidence_id for link in hypothesis.contradicting_evidence
                )
                or "none"
            )
            self._details[iid] = "\n".join(
                (
                    f"Hypothesis ID: {hypothesis.hypothesis_id}",
                    f"Program: {hypothesis.program_id}",
                    f"Kind: {hypothesis.hypothesis_kind.value}",
                    "Subject: "
                    f"{hypothesis.subject_kind.value}:"
                    f"{hypothesis.subject_canonical_value}",
                    f"Statement: {_single_line(hypothesis.statement)}",
                    f"Rationale: {_single_line(hypothesis.rationale)}",
                    "Required validation: "
                    f"{_single_line(hypothesis.required_validation)}",
                    f"Origin: {hypothesis.origin.value}",
                    f"Status: {hypothesis.status.value}",
                    f"Supporting evidence IDs: {supporting_ids}",
                    f"Contradicting evidence IDs: {contradicting_ids}",
                    "Status history:",
                    *history_lines,
                    f"Scope: {scope_text}",
                    "This is a hypothesis, not a finding or a validated"
                    " vulnerability.",
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
