"""Local-only, literal presentation of the latest acquired research text."""

from __future__ import annotations

import tkinter as tk
from datetime import UTC
from tkinter import scrolledtext, ttk

from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.ResearchPassageProposal import propose_passages
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
        finder = ttk.LabelFrame(
            parent, text="Find candidate passages locally", padding=6
        )
        finder.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        finder.columnconfigure(0, weight=1)
        self.passage_query = tk.StringVar(master=parent)
        ttk.Entry(finder, textvariable=self.passage_query).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(
            finder, text="Suggest passages", command=self._suggest_passages
        ).grid(row=0, column=1, padx=8)
        self.passages = scrolledtext.ScrolledText(
            finder, height=7, wrap="word", undo=False
        )
        self.passages.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)
        self.passage_query.trace_add("write", self._clear_passages)
        self.clear()

    @property
    def text_widgets(self) -> tuple[tk.Text, ...]:
        return (self.provenance, self.body, self.passages)

    def _clear_passages(self, *_args: object) -> None:
        output = getattr(self, "passages", None)
        if output is not None:
            self._literal(output, "")

    def _suggest_passages(self) -> None:
        self._clear_passages()
        try:
            proposals = propose_passages(self.passage_query.get(), self._previews)
        except ResearchError as error:
            self._literal(self.passages, str(error))
            return
        lines = [
            "Keyword matches only — not accepted evidence or a truth judgment.",
            "Terms of at least 3 characters; exact word overlap, "
            "no semantic inference.",
            "Long lines use 800-character windows, which can split words or sentences.",
            "No model call, saving or refetch. "
            "Review each quote in its full source context.",
        ]
        if not proposals:
            lines.append("No matching passages in the current batch.")
        for index, proposal in enumerate(proposals, 1):
            preview = proposal.preview
            lines.extend(
                (
                    "",
                    f"Candidate {index} · source {self._previews.index(preview) + 1}",
                    f"Run {preview.run_id} / execution {preview.execution_id} "
                    f"/ step {preview.step_id}",
                    f"Source: {preview.source.url}",
                    f"Extracted-text SHA-256: {preview.content_sha256}",
                    f"Character range [{proposal.start}, {proposal.end}) "
                    "· not original file bytes",
                    "Matched terms: " + ", ".join(proposal.matched_terms),
                    "--- untrusted quotation ---",
                    proposal.quote,
                    "--- end quotation ---",
                )
            )
        self._literal(self.passages, "\n".join(lines))

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
        self._clear_passages()
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
