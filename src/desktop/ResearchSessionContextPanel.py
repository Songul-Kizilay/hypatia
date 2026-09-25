"""Operator UI for inert historical authentication/session context labels."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from brain.BrainResponse import BrainResponse
from desktop.DesktopController import DesktopController
from research.ResearchAuthenticationState import ResearchAuthenticationState


def _single_line(value: str) -> str:
    return " ".join(value.split()) or "none"


class ResearchSessionContextPanel:
    """Record and list descriptive contexts; never establish or use a session."""

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

        self.program_id = tk.StringVar(master=parent)
        self.authentication_state = tk.StringVar(
            master=parent, value=ResearchAuthenticationState.UNAUTHENTICATED.value
        )
        self.identity_label = tk.StringVar(master=parent)
        self.evidence_ids = tk.StringVar(master=parent)
        self.note = tk.StringVar(master=parent)
        self.status = tk.StringVar(
            master=parent, value="Enter a program ID and load session contexts."
        )
        self.detail = tk.StringVar(
            master=parent, value="Select a row to see its recorded fields."
        )

        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)
        parent.rowconfigure(3, weight=1)

        ttk.Label(parent, text="Program ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.program_id).grid(
            row=0, column=1, columnspan=2, sticky="ew", padx=8, pady=4
        )
        ttk.Button(parent, text="Load contexts", command=self.load).grid(
            row=0, column=3, padx=4
        )

        form = ttk.LabelFrame(
            parent, text="Record historical authentication context", padding=8
        )
        form.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Authentication state").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.authentication_state,
            values=tuple(value.value for value in ResearchAuthenticationState),
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=8, pady=2)
        ttk.Label(form, text="Identity label (never enter a secret)").grid(
            row=1, column=0, sticky="w"
        )
        ttk.Entry(form, textvariable=self.identity_label).grid(
            row=1, column=1, sticky="ew", padx=8, pady=2
        )
        ttk.Label(form, text="HTTP evidence IDs (comma-separated)").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Entry(form, textvariable=self.evidence_ids).grid(
            row=2, column=1, sticky="ew", padx=8, pady=2
        )
        ttk.Label(form, text="Note").grid(row=3, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.note).grid(
            row=3, column=1, sticky="ew", padx=8, pady=2
        )
        ttk.Button(form, text="Record context", command=self.record).grid(
            row=4, column=1, sticky="e", pady=(4, 0)
        )

        ttk.Label(parent, textvariable=self.status, wraplength=900).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(8, 0)
        )
        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", pady=(4, 0))
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
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))

    def load(self) -> None:
        program_id = self.program_id.get().strip()
        if not program_id:
            self.status.set("Enter a program ID first.")
            return

        def action() -> BrainResponse:
            return self._controller.preview_research_session_contexts(program_id)

        self._dispatch(action, self._render, "research session contexts")

    def record(self) -> None:
        program_id = self.program_id.get().strip()
        if not program_id:
            self.status.set("Enter a program ID first.")
            return
        evidence_ids = tuple(
            value.strip()
            for value in self.evidence_ids.get().split(",")
            if value.strip()
        )

        def action() -> BrainResponse:
            return self._controller.record_research_session_context(
                program_id,
                self.authentication_state.get(),
                self.identity_label.get(),
                evidence_ids,
                self.note.get(),
            )

        self._dispatch(action, self._after_write, "research session context")

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
        for record in response.research_session_contexts:
            identity = _single_line(record.identity_label)
            label = (
                f"{record.authentication_state.value}: {identity} "
                f"({len(record.evidence_ids)} evidence reference(s))"
            )
            iid = self.tree.insert("", "end", text=label)
            self._details[iid] = "\n".join(
                (
                    f"Context ID: {record.session_context_id}",
                    f"Program: {record.program_id}",
                    f"Authentication state: {record.authentication_state.value}",
                    f"Identity label: {identity}",
                    f"HTTP evidence IDs: {', '.join(record.evidence_ids) or 'none'}",
                    f"Note: {_single_line(record.note)}",
                    f"Recorded at: {record.recorded_at.isoformat()}",
                    "Historical label only; no live session or credential authority.",
                )
            )

    def _on_select(self, _event: object = None) -> None:
        selected = self.tree.selection()
        if not selected:
            self.detail.set("Select a row to see its recorded fields.")
            return
        self.detail.set(
            self._details.get(selected[0], "No detail is recorded for this row.")
        )
