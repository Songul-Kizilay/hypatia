"""Local-only, literal presentation of the latest acquired research text."""

from __future__ import annotations

import tkinter as tk
from datetime import UTC
from tkinter import scrolledtext, ttk

from brain.BrainResponse import BrainResponse
from research.ResearchSourcePreview import ResearchSourcePreview


class ResearchSourcePreviewPanel:
    """A bounded reader, not an acceptance, persistence or execution surface."""

    def __init__(self, parent: ttk.Frame) -> None:
        self._previews: tuple[ResearchSourcePreview, ...] = ()
        self.status = tk.StringVar(master=parent)
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(4, weight=1)
        ttk.Label(
            parent,
            text="Temporary sources — untrusted text, not accepted evidence",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Label(parent, textvariable=self.status, wraplength=850).grid(
            row=1, column=0, sticky="ew", pady=(0, 8)
        )
        controls = ttk.Frame(parent)
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Source").grid(row=0, column=0, padx=(0, 8))
        self.selector = ttk.Combobox(controls, state="readonly")
        self.selector.grid(row=0, column=1, sticky="ew")
        self.selector.bind("<<ComboboxSelected>>", self._selected)
        ttk.Button(controls, text="Clear previews", command=self.clear).grid(
            row=0, column=2, padx=(8, 0)
        )
        self.provenance = scrolledtext.ScrolledText(parent, height=7, wrap="word")
        self.provenance.grid(row=3, column=0, sticky="ew", pady=8)
        self.body = scrolledtext.ScrolledText(
            parent, height=15, wrap="word", undo=False
        )
        self.body.grid(row=4, column=0, sticky="nsew")
        self.clear()

    @property
    def text_widgets(self) -> tuple[tk.Text, ...]:
        return (self.provenance, self.body)

    def accept_response(self, response: BrainResponse) -> bool:
        """Replace a batch, never accumulate bodies across responses."""
        previews = response.research_source_previews
        if not previews:
            if response.intent.startswith("research_plan_execution_"):
                self.clear("This execution response contains no temporary source text.")
            return False
        if (
            len(previews) > 10
            or any(not isinstance(item, ResearchSourcePreview) for item in previews)
            or len({(item.execution_id, item.run_id) for item in previews}) != 1
            or len({item.step_id for item in previews}) != len(previews)
        ):
            self.clear("Source previews unavailable: invalid result batch.")
            return False
        self.clear()
        self._previews = tuple(previews)
        # Keep provider-controlled titles out of navigation labels. Full source
        # provenance is displayed literally in the separate read-only area.
        self.selector.configure(
            values=tuple(f"Source {index + 1}" for index in range(len(previews)))
        )
        self.selector.current(0)
        self.status.set(
            f"{len(previews)} temporary source(s). Latest batch only; clearing or "
            "closing loses this text. Reading does not save, accept or send it "
            "to a model."
        )
        self._selected()
        return True

    def _selected(self, _event: object = None) -> None:
        index = self.selector.current()
        if index < 0 or index >= len(self._previews):
            return
        preview = self._previews[index]
        source = preview.source
        lines = (
            "Instruction authority: none. Source claims remain unverified.",
            f"Research run: {preview.run_id}",
            f"Execution: {preview.execution_id} / step: {preview.step_id}",
            f"Requested URL: {preview.requested_url}",
            f"Source URL: {source.url}",
            f"Acquired from: {source.content_resource or source.url}",
            f"Acquisition: {source.acquisition}",
            f"Fetched UTC: {source.fetched_at.astimezone(UTC).isoformat()}",
            f"Title: {source.title}",
            f"Content type: {source.content_type}",
            f"Extracted text: {preview.content_byte_count} UTF-8 bytes",
            f"Extracted-text SHA-256: {preview.content_sha256}",
        )
        self._literal(self.provenance, "\n".join(lines))
        self._literal(self.body, source.content)

    def clear(
        self,
        message: str = "No temporary sources. Run an approved source-fetch plan first.",
    ) -> None:
        """Release the batch and clear both widgets without refetching."""
        self._previews = ()
        self.selector.set("")
        self.selector.configure(values=())
        self.status.set(message)
        self._literal(self.provenance, "")
        self._literal(self.body, "")

    @staticmethod
    def _literal(widget: tk.Text, value: str) -> None:
        # No Markdown/HTML parser, hyperlink binding, Tcl evaluation or commands.
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, value)
        widget.configure(state=tk.DISABLED)
