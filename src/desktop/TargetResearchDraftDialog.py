"""Desktop-only exact target drafting; editing never grants or runs anything."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import scrolledtext, ttk
from typing import Protocol

from core.Exceptions import ResearchError
from desktop.TargetResearchDraft import TargetResearchDraft, target_scope_from_fields
from research.ResearchProgramScopeEnrollmentPreview import (
    PROGRAM_SCOPE_CREATE_ACTION,
    PROGRAM_SCOPE_REVOKE_ACTION,
    ResearchProgramScopeEnrollmentPreview,
)
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from research.ResearchTargetScope import ResearchTargetScope

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


class ProgramScopeEnrollmentProcessor(Protocol):
    """Narrow desktop boundary for exact program-scope enrollment."""

    def revisions(self) -> tuple[ResearchProgramScopeRevision, ...]:
        """Return durable program-scope revisions."""

    def preview_create(
        self,
        program_id: str,
        scope: ResearchTargetScope,
    ) -> ResearchProgramScopeEnrollmentPreview:
        """Preview a scope creation without persisting it."""

    def confirm_create(
        self,
        revision_id: str,
        revision_digest: str,
    ) -> ResearchProgramScopeRevision:
        """Persist the exact previewed scope creation."""

    def preview_revoke(
        self,
        revision_id: str,
        revision_digest: str,
    ) -> ResearchProgramScopeEnrollmentPreview:
        """Preview revocation of one exact active scope."""

    def confirm_revoke(
        self,
        revision_id: str,
        revision_digest: str,
    ) -> ResearchProgramScopeRevision:
        """Persist the exact previewed revocation."""


class TargetResearchDraftDialog:
    """Edit an immutable in-memory draft, retaining old state on refusal/cancel."""

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        initial: TargetResearchDraft | None,
        on_apply: Callable[[TargetResearchDraft], None],
        *,
        scope_enrollment_service: ProgramScopeEnrollmentProcessor | None = None,
        background: str = "#20252b",
        field_background: str = "#2b3139",
        foreground: str = "#dce2e8",
    ) -> None:
        self._on_apply = on_apply
        self._scope_enrollment_service = scope_enrollment_service
        self._pending_scope_preview: ResearchProgramScopeEnrollmentPreview | None = None
        self._active_scope_revisions: tuple[ResearchProgramScopeRevision, ...] = ()
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
                "lasts only for this window session. Saving a scope record still "
                "does not authorize or start the plan, Kali, or a terminal. "
                "Next: preview the plan, preview/confirm its approval, then Start."
            ),
            wraplength=800,
            justify="left",
            style="Hint.TLabel",
        ).grid(row=8, column=0, columnspan=2, sticky="ew")
        if self._scope_enrollment_service is not None:
            self._build_scope_enrollment_section(panel, row=9)
        ttk.Label(panel, textvariable=self.status, wraplength=800).grid(
            row=10, column=0, columnspan=2, sticky="ew", pady=(8, 6)
        )
        buttons = ttk.Frame(panel)
        buttons.grid(row=11, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.window.destroy).pack(
            side="left", padx=6
        )
        ttk.Button(buttons, text="Use in plan — no network", command=self.apply).pack(
            side="left"
        )
        self.window.bind("<Escape>", lambda _event: self.window.destroy())

    def _build_scope_enrollment_section(self, parent: ttk.Frame, *, row: int) -> None:
        section = ttk.LabelFrame(
            parent,
            text="Confirmed scope record — no plan approval or execution",
            padding=6,
        )
        section.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        section.columnconfigure(0, weight=1)
        self.scope_revision = tk.StringVar(master=self.window)
        self.scope_revision_selector = ttk.Combobox(
            section,
            textvariable=self.scope_revision,
            values=(),
            state="readonly",
        )
        self.scope_revision_selector.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        buttons = ttk.Frame(section)
        buttons.grid(row=0, column=1, sticky="e")
        ttk.Button(
            buttons,
            text="Refresh",
            command=self._refresh_scope_revisions,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            buttons,
            text="Preview save",
            command=self._preview_scope_enrollment,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            buttons,
            text="Confirm save",
            command=self._confirm_scope_enrollment,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            buttons,
            text="Preview revoke",
            command=self._preview_scope_revocation,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            buttons,
            text="Confirm revoke",
            command=self._confirm_scope_revocation,
        ).pack(side="left")
        self._refresh_scope_revisions()

    def apply(self) -> None:
        try:
            action = _ACTIONS.get(self.action.get())
            if action is None:
                raise ResearchError("Choose a supported target action.")
            revision = self._selected_scope_revision()
            if self._scope_enrollment_service is not None:
                if revision is None:
                    raise ResearchError(
                        "Select an active saved scope before using it in a plan."
                    )
                if not self._scope_revision_matches_form(revision):
                    raise ResearchError(
                        "Selected saved scope no longer matches the form."
                    )
            draft = TargetResearchDraft.from_fields(
                program_id=self.program.get(),
                action=action,
                scope_revision_id=(
                    revision.revision_id if revision is not None else None
                ),
                scope_revision_digest=(
                    revision.revision_digest if revision is not None else None
                ),
                **{key: box.get("1.0", "end-1c") for key, box in self.fields.items()},
            )
        except (ResearchError, ValueError) as error:
            self.status.set(f"Draft not applied: {error}")
            return
        self._on_apply(draft)
        self.window.destroy()

    def _current_scope(self) -> ResearchTargetScope:
        return target_scope_from_fields(
            self.fields["allowed_hosts"].get("1.0", "end-1c"),
            self.fields["excluded_hosts"].get("1.0", "end-1c"),
            self.fields["allowed_networks"].get("1.0", "end-1c"),
            self.fields["excluded_networks"].get("1.0", "end-1c"),
        )

    def _preview_scope_enrollment(self) -> None:
        service = self._scope_enrollment_service
        if service is None:
            self.status.set("Scope records are not available in this runtime.")
            return
        try:
            preview = service.preview_create(self.program.get(), self._current_scope())
        except (ResearchError, ValueError) as error:
            self._pending_scope_preview = None
            self.status.set(f"Scope preview refused: {error}")
            return
        self._pending_scope_preview = preview
        revision = preview.revision
        self.status.set(
            "Scope preview ready: "
            f"{revision.program_id} · {revision.revision_id} · "
            f"{revision.revision_digest[:12]}... · not saved"
        )

    def _confirm_scope_enrollment(self) -> None:
        service = self._scope_enrollment_service
        preview = self._pending_scope_preview
        if service is None:
            self.status.set("Scope records are not available in this runtime.")
            return
        if preview is None or preview.action != PROGRAM_SCOPE_CREATE_ACTION:
            self.status.set("Preview a scope save before confirming it.")
            return
        if not self._scope_preview_still_matches_form(preview):
            self._pending_scope_preview = None
            self.status.set("Scope preview changed; preview again before saving.")
            return
        try:
            revision = service.confirm_create(
                preview.revision.revision_id,
                preview.revision.revision_digest,
            )
        except ResearchError as error:
            self._pending_scope_preview = None
            self.status.set(f"Scope not saved: {error}")
            return
        self._pending_scope_preview = None
        self._refresh_scope_revisions()
        self.status.set(
            "Scope saved: "
            f"{revision.program_id} · {revision.revision_id} · "
            f"{revision.revision_digest[:12]}... · plan still needs approval"
        )

    def _preview_scope_revocation(self) -> None:
        service = self._scope_enrollment_service
        if service is None:
            self.status.set("Scope records are not available in this runtime.")
            return
        revision = self._selected_scope_revision()
        if revision is None:
            self.status.set("Select an active saved scope to revoke.")
            return
        try:
            preview = service.preview_revoke(
                revision.revision_id,
                revision.revision_digest,
            )
        except ResearchError as error:
            self._pending_scope_preview = None
            self.status.set(f"Scope revoke preview refused: {error}")
            return
        self._pending_scope_preview = preview
        self.status.set(
            "Scope revoke preview ready: "
            f"{preview.revision.program_id} · {preview.revision.revision_id} · "
            f"{preview.revision.revision_digest[:12]}... · not revoked"
        )

    def _confirm_scope_revocation(self) -> None:
        service = self._scope_enrollment_service
        preview = self._pending_scope_preview
        if service is None:
            self.status.set("Scope records are not available in this runtime.")
            return
        if preview is None or preview.action != PROGRAM_SCOPE_REVOKE_ACTION:
            self.status.set("Preview a scope revocation before confirming it.")
            return
        try:
            revision = service.confirm_revoke(
                preview.revision.revision_id,
                preview.revision.revision_digest,
            )
        except ResearchError as error:
            self._pending_scope_preview = None
            self.status.set(f"Scope not revoked: {error}")
            return
        self._pending_scope_preview = None
        self._refresh_scope_revisions()
        self.status.set(
            "Scope revoked: "
            f"{revision.program_id} · {revision.revision_id} · "
            f"{revision.revision_digest[:12]}..."
        )

    def _refresh_scope_revisions(self) -> None:
        service = self._scope_enrollment_service
        if service is None:
            return
        try:
            active = tuple(
                revision for revision in service.revisions() if revision.active
            )
        except ResearchError as error:
            self._active_scope_revisions = ()
            self.status.set(f"Scope records unavailable: {error}")
            return
        self._active_scope_revisions = active
        labels = tuple(_scope_revision_label(revision) for revision in active)
        selector = getattr(self, "scope_revision_selector", None)
        if selector is not None:
            selector.configure(values=labels)
            if labels:
                selector.current(0)
            else:
                self.scope_revision.set("")

    def _selected_scope_revision(self) -> ResearchProgramScopeRevision | None:
        active: tuple[ResearchProgramScopeRevision, ...] = self._active_scope_revisions
        selector = getattr(self, "scope_revision_selector", None)
        if selector is None:
            return active[0] if active else None
        index = int(selector.current())
        if not 0 <= index < len(active):
            return None
        return active[index]

    def _scope_preview_still_matches_form(
        self, preview: ResearchProgramScopeEnrollmentPreview
    ) -> bool:
        try:
            return (
                preview.revision.program_id == self.program.get().strip()
                and preview.revision.scope == self._current_scope()
            )
        except ResearchError, ValueError:
            return False

    def _scope_revision_matches_form(
        self,
        revision: ResearchProgramScopeRevision,
    ) -> bool:
        try:
            return (
                revision.program_id == self.program.get().strip()
                and revision.scope == self._current_scope()
            )
        except ResearchError, ValueError:
            return False


def _scope_revision_label(revision: ResearchProgramScopeRevision) -> str:
    return (
        f"{revision.program_id} · {revision.revision_id} · "
        f"{revision.revision_digest[:12]}..."
    )
