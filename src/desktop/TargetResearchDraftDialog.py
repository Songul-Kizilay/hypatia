"""Desktop-only exact target drafting; editing never grants or runs anything."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import scrolledtext, ttk

from core.Exceptions import ResearchError
from desktop.TargetResearchDraft import TargetResearchDraft

_FIELD_LABELS = (
    ("allowed_hosts", "Allowed hosts — exact or *.example.test"),
    ("excluded_hosts", "Excluded hosts — exclusions win"),
    ("allowed_networks", "Allowed IP networks — optional strict CIDRs"),
    ("excluded_networks", "Excluded IP networks — also checked after DNS"),
)
_ACTIONS = {
    "Read page only": "source_fetch",
    "Load page into research sources": "source_accept",
}


class TargetResearchDraftDialog:
    """Edit an immutable in-memory draft, retaining old state on refusal/cancel."""

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        initial: TargetResearchDraft | None,
        on_apply: Callable[[TargetResearchDraft], None],
        *,
        background: str = "#20252b",
        field_background: str = "#2b3139",
        foreground: str = "#dce2e8",
    ) -> None:
        self._on_apply = on_apply
        self.window = tk.Toplevel(parent)
        self.window.title("Target program — explicit scope and pages")
        self.window.transient(parent)
        self.window.configure(background=background)
        self.window.geometry("860x650")
        self.window.minsize(720, 600)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        panel = ttk.Frame(self.window, padding=16)
        panel.grid(sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.columnconfigure(1, weight=1)
        panel.rowconfigure(7, weight=1)
        values = initial.to_fields() if initial is not None else {}
        self.program = tk.StringVar(
            master=self.window, value=values.get("program_id", "")
        )
        selected = values.get("action", "source_fetch")
        self.action = tk.StringVar(
            master=self.window,
            value=next(name for name, value in _ACTIONS.items() if value == selected),
        )
        self.status = tk.StringVar(
            master=self.window, value="Nothing saved or started."
        )
        ttk.Label(panel, text="1. Name the program", style="Hint.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(panel, textvariable=self.program).grid(
            row=1, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Label(
            panel, text="2. Choose the permitted action", style="Hint.TLabel"
        ).grid(row=0, column=1, sticky="w")
        ttk.Combobox(
            panel, textvariable=self.action, values=tuple(_ACTIONS), state="readonly"
        ).grid(row=1, column=1, sticky="ew")
        ttk.Label(
            panel,
            text=(
                "3. Enter one rule per line. *.example.test excludes the apex; "
                "add the apex separately if allowed. Do not use this host-wide "
                "form for programs with path-specific restrictions."
            ),
            wraplength=800,
            justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 6))
        self.fields: dict[str, scrolledtext.ScrolledText] = {}
        for index, (key, label) in enumerate(_FIELD_LABELS):
            row, column = 3 + (index // 2) * 2, index % 2
            ttk.Label(panel, text=label).grid(
                row=row, column=column, sticky="w", pady=(4, 2)
            )
            box = scrolledtext.ScrolledText(
                panel,
                height=3 if index < 2 else 2,
                width=30,
                wrap=tk.WORD,
                background=field_background,
                foreground=foreground,
                insertbackground=foreground,
            )
            box.grid(
                row=row + 1,
                column=column,
                sticky="nsew",
                padx=(0, 8) if column == 0 else 0,
            )
            box.insert("1.0", values.get(key, ""))
            self.fields[key] = box
        urls = ttk.LabelFrame(
            panel, text="4. Exact HTTPS pages to request — one URL per line", padding=6
        )
        urls.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(10, 6))
        urls.columnconfigure(0, weight=1)
        urls.rowconfigure(0, weight=1)
        box = scrolledtext.ScrolledText(
            urls,
            height=4,
            width=60,
            wrap=tk.WORD,
            background=field_background,
            foreground=foreground,
            insertbackground=foreground,
        )
        box.grid(sticky="nsew")
        box.insert("1.0", values.get("source_urls", ""))
        self.fields["source_urls"] = box
        ttk.Label(
            panel,
            text=(
                "Public HTTPS :443 text pages only — no scans, credentials or "
                "exploitation. You must have the program's permission. This draft "
                "lasts only for this window session. "
                "Next: preview the plan, preview/confirm its approval, then Start."
            ),
            wraplength=800,
            justify="left",
            style="Hint.TLabel",
        ).grid(row=8, column=0, columnspan=2, sticky="ew")
        ttk.Label(panel, textvariable=self.status, wraplength=800).grid(
            row=9, column=0, columnspan=2, sticky="ew", pady=(8, 6)
        )
        buttons = ttk.Frame(panel)
        buttons.grid(row=10, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.window.destroy).pack(
            side="left", padx=6
        )
        ttk.Button(buttons, text="Use in plan — no network", command=self.apply).pack(
            side="left"
        )
        self.window.bind("<Escape>", lambda _event: self.window.destroy())

    def apply(self) -> None:
        try:
            action = _ACTIONS.get(self.action.get())
            if action is None:
                raise ResearchError("Choose a supported target action.")
            draft = TargetResearchDraft.from_fields(
                program_id=self.program.get(),
                action=action,
                **{key: box.get("1.0", "end-1c") for key, box in self.fields.items()},
            )
        except (ResearchError, ValueError) as error:
            self.status.set(f"Draft not applied: {error}")
            return
        self._on_apply(draft)
        self.window.destroy()
