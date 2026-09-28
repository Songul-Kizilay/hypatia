"""Operator-authored security validation recipes: record and list, per subject.

Reuses the exact `ttk.Treeview` + scrollbar + `<<TreeviewSelect>>` +
`iid -> detail-text` dict pattern already established by
`ResearchSecurityFindingPanel`/`ResearchSecurityHypothesisPanel`. Unlike
those two, `ResearchSecurityValidationRecipeApplicationService` has no
program-wide listing: recipes are always read for one specific
(`program_id`, `subject_kind`, `subject_id`) subject, so this panel's load
action takes the same three fields as its record action, not just a program
ID.

A recipe is descriptive strategy text only, exactly like a finding's
`required_followup` — recording one never fetches, runs, or authorizes
anything, and never mutates the hypothesis or finding it names. The fixed
not-authority notice is imported from `response.ResponseComposer` rather
than restated, so its wording can never drift between the panel and Brain
responses. VALIDATION RECIPE != AUTHORITY TO ACT.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from brain.BrainResponse import BrainResponse
from desktop.DesktopController import DesktopController
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)
from response.ResponseComposer import SECURITY_VALIDATION_RECIPE_NOT_AUTHORITY_NOTICE


def _single_line(value: str) -> str:
    """Render one recorded field as a single line, or say there is none."""
    return " ".join(value.split()) or "none"


class ResearchSecurityValidationRecipePanel:
    """Record and list validation recipes for one hypothesis or finding."""

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
        subject_kinds = tuple(
            kind.value for kind in ResearchSecurityValidationRecipeSubjectKind
        )

        self.program_id = tk.StringVar(master=parent)
        self.subject_kind = tk.StringVar(
            master=parent,
            value=ResearchSecurityValidationRecipeSubjectKind.FINDING.value,
        )
        self.subject_id = tk.StringVar(master=parent)
        self.notes = tk.StringVar(master=parent)

        self.status = tk.StringVar(
            master=parent,
            value="Enter a program ID, subject kind, and subject ID, then load.",
        )
        self.detail = tk.StringVar(
            master=parent, value="Select a row to see its recorded fields."
        )

        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)
        parent.rowconfigure(4, weight=1)

        subject_frame = ttk.LabelFrame(parent, text="Subject", padding=8)
        subject_frame.grid(row=0, column=0, columnspan=4, sticky="ew")
        subject_frame.columnconfigure(1, weight=1)
        subject_frame.columnconfigure(3, weight=1)
        ttk.Label(subject_frame, text="Program ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(subject_frame, textvariable=self.program_id).grid(
            row=0, column=1, sticky="ew", padx=8, pady=2
        )
        ttk.Label(subject_frame, text="Subject kind").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            subject_frame,
            textvariable=self.subject_kind,
            values=subject_kinds,
            state="readonly",
        ).grid(row=0, column=3, sticky="ew", padx=8, pady=2)
        ttk.Label(subject_frame, text="Subject ID (hypothesis or finding ID)").grid(
            row=1, column=0, sticky="w"
        )
        ttk.Entry(subject_frame, textvariable=self.subject_id).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=8, pady=2
        )
        ttk.Button(subject_frame, text="Load recipes", command=self.load).grid(
            row=1, column=3, sticky="e", padx=8
        )

        record_frame = ttk.LabelFrame(
            parent,
            text="Record a new validation recipe for the subject above",
            padding=8,
        )
        record_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        record_frame.columnconfigure(0, weight=1)
        ttk.Label(record_frame, text="Steps, one per line (never enter a secret)").grid(
            row=0, column=0, sticky="w"
        )
        self.steps_text = tk.Text(record_frame, height=4, wrap="word")
        self.steps_text.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(record_frame, text="Notes (optional, never enter a secret)").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Entry(record_frame, textvariable=self.notes).grid(
            row=3, column=0, sticky="ew", pady=(0, 4)
        )
        ttk.Button(record_frame, text="Record recipe", command=self.record_recipe).grid(
            row=4, column=0, sticky="e"
        )

        ttk.Label(parent, textvariable=self.status, wraplength=900).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(8, 0)
        )

        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=4, column=0, columnspan=4, sticky="nsew", pady=(4, 0))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, show="tree", height=10)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.tree.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        ttk.Label(
            parent, textvariable=self.detail, wraplength=900, justify=tk.LEFT
        ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(4, 0))

    def _subject(self) -> tuple[str, str, str] | None:
        program_id = self.program_id.get().strip()
        subject_id = self.subject_id.get().strip()
        if not program_id or not subject_id:
            self.status.set("Enter a program ID and subject ID first.")
            return None
        return program_id, self.subject_kind.get(), subject_id

    def load(self) -> None:
        """Fetch the persisted, read-only recipe listing; never itself a mutation."""
        subject = self._subject()
        if subject is None:
            return
        program_id, subject_kind, subject_id = subject

        def action() -> BrainResponse:
            return self._controller.preview_research_security_validation_recipes(
                program_id, subject_kind, subject_id
            )

        self._dispatch(action, self._render, "validation recipes")

    def record_recipe(self) -> None:
        subject = self._subject()
        if subject is None:
            return
        program_id, subject_kind, subject_id = subject
        steps = tuple(
            line.strip()
            for line in self.steps_text.get("1.0", "end").splitlines()
            if line.strip()
        )
        if not steps:
            self.status.set("Enter at least one step first.")
            return
        notes = self.notes.get()

        def action() -> BrainResponse:
            return self._controller.record_research_security_validation_recipe(
                program_id, subject_kind, subject_id, steps, notes
            )

        self._dispatch(action, self._after_write, "validation recipe")

    def _after_write(self, response: BrainResponse) -> None:
        self.status.set(response.message)
        if response.success:
            self.steps_text.delete("1.0", "end")
            self.notes.set("")
            self.load()

    def _render(self, response: BrainResponse) -> None:
        self.status.set(response.message)
        for item in self.tree.get_children(""):
            self.tree.delete(item)
        self._details = {}
        self.detail.set("Select a row to see its recorded fields.")
        if not response.success:
            return
        for recipe in response.research_security_validation_recipes:
            label = f"{recipe.created_at.isoformat()}: {len(recipe.steps)} step(s)"
            iid = self.tree.insert("", "end", text=label)
            step_lines = [
                f"  {index + 1}. {step}" for index, step in enumerate(recipe.steps)
            ]
            self._details[iid] = "\n".join(
                (
                    f"Recipe ID: {recipe.recipe_id}",
                    f"Program: {recipe.program_id}",
                    f"Subject: {recipe.subject_kind.value} {recipe.subject_id}",
                    f"Created at: {recipe.created_at.isoformat()}",
                    "Steps:",
                    *step_lines,
                    f"Notes: {_single_line(recipe.notes)}",
                    SECURITY_VALIDATION_RECIPE_NOT_AUTHORITY_NOTICE,
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
