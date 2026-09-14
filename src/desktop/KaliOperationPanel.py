"""Operator selections for the existing reviewed Kali operations."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import UTC, datetime
from tkinter import messagebox, scrolledtext, ttk

from brain.BrainResponse import BrainResponse
from core.Exceptions import HypatiaError
from desktop.DesktopController import DesktopController
from research.ResearchKaliOperationPreview import ResearchKaliOperationPreview
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision

_OPERATIONS = {
    "DNS kayıtlarını sorgula (dig)": "dns_record_lookup",
    "HTTPS başlıklarını oku (curl)": "https_header_lookup",
}


class KaliOperationPanel:
    """Keep returned preview/approval separate from editable form fields."""

    def __init__(
        self,
        parent: ttk.Frame,
        controller: DesktopController,
        revisions: Callable[[], tuple[ResearchProgramScopeRevision, ...]],
        dispatch: Callable[
            [Callable[[], BrainResponse], Callable[[BrainResponse], None], str], None
        ],
    ) -> None:
        self._controller = controller
        self._revisions = revisions
        self._dispatch = dispatch
        self._generation = 0
        self._preview: ResearchKaliOperationPreview | None = None
        self._authorization_id: str | None = None
        self._scope_choices: dict[str, ResearchProgramScopeRevision] = {}
        self.scope = tk.StringVar(master=parent)
        self.hostname = tk.StringVar(master=parent)
        self.operation = tk.StringVar(master=parent, value=next(iter(_OPERATIONS)))
        self.record_type = tk.StringVar(master=parent, value="A")
        self.status = tk.StringVar(master=parent, value="Bir kapsam ve hedef seç.")
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(7, weight=1)
        ttk.Label(
            parent,
            text="Kali araçları · Kapsam seç → Önizle → Onayla → Çalıştır",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=8)
        ttk.Label(parent, text="Kayıtlı program kapsamı").grid(
            row=1, column=0, sticky="w"
        )
        self.scope_selector = ttk.Combobox(
            parent, textvariable=self.scope, state="readonly"
        )
        self.scope_selector.grid(row=1, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(parent, text="Kapsamları yenile", command=self.refresh).grid(
            row=1, column=2
        )
        ttk.Label(parent, text="Hedef alan adı").grid(row=2, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.hostname).grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=8, pady=5
        )
        ttk.Label(parent, text="İşlem").grid(row=3, column=0, sticky="w")
        ttk.Combobox(
            parent,
            textvariable=self.operation,
            values=tuple(_OPERATIONS),
            state="readonly",
        ).grid(row=3, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
        ttk.Label(parent, text="DNS kayıt türü").grid(row=4, column=0, sticky="w")
        self.record_selector = ttk.Combobox(
            parent,
            textvariable=self.record_type,
            values=("A", "AAAA", "CNAME"),
            state="readonly",
        )
        self.record_selector.grid(row=4, column=1, sticky="ew", padx=8, pady=5)
        actions = ttk.Frame(parent)
        actions.grid(row=5, column=0, columnspan=3, sticky="w", pady=12)
        for label, command in (
            ("1. Önizle", self.preview),
            ("2. Onayla", self.authorize),
            ("3. Çalıştır", self.run),
        ):
            ttk.Button(actions, text=label, command=command).pack(side=tk.LEFT, padx=4)
        ttk.Label(parent, textvariable=self.status, wraplength=900).grid(
            row=6, column=0, columnspan=3, sticky="w", pady=8
        )
        self.output = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            height=16,
            state=tk.DISABLED,
            background="#2b3139",
            foreground="#dce2e8",
            insertbackground="#dce2e8",
        )
        self.output.grid(row=7, column=0, columnspan=3, sticky="nsew")
        for variable in (self.scope, self.hostname, self.operation, self.record_type):
            variable.trace_add("write", self._invalidate)

    def _invalidate(self, *_args: object) -> None:
        self._generation += 1
        self._preview = None
        self._authorization_id = None
        self.record_selector.configure(
            state=(
                "readonly"
                if _OPERATIONS.get(self.operation.get()) == "dns_record_lookup"
                else "disabled"
            )
        )
        self.status.set("Seçim değişti. İşlemi yeniden önizle.")

    def refresh(self) -> None:
        """Read confirmed scopes only when the operator requests the list."""
        self._invalidate()
        self._scope_choices = {}
        self.scope_selector.configure(values=())
        self.scope.set("")
        try:
            revisions = self._revisions()
        except (HypatiaError, OSError) as error:
            self.status.set(f"Kapsamlar yüklenemedi: {error}")
            return
        now = datetime.now(UTC)
        self._scope_choices = {
            f"{revision.program_id} · {revision.revision_id}": revision
            for revision in revisions
            if revision.valid_at(now)
        }
        self.scope_selector.configure(values=tuple(self._scope_choices))
        self.status.set(
            "Kapsamı seç ve alan adını yaz."
            if self._scope_choices
            else "Etkin kapsam bulunamadı. Research (Advanced) içindeki Target program "
            "formundan kapsam kaydedebilirsin."
        )

    def _submit(self, action: Callable[[], BrainResponse], stage: str) -> None:
        generation = self._generation

        def complete(response: BrainResponse) -> None:
            if generation != self._generation:
                self.status.set(
                    "Seçim değişti; önceki yanıtla işlem yapılamaz. Yeniden önizle."
                )
                return
            self.output.configure(state=tk.NORMAL)
            self.output.delete("1.0", tk.END)
            self.output.insert(tk.END, response.message)
            self.output.configure(state=tk.DISABLED)
            if not response.success:
                self._preview = None
                self._authorization_id = None
                self.status.set("İşlem tamamlanamadı. Ayrıntılar aşağıda.")
                return
            if stage == "Önizle":
                self._preview = response.kali_operation_preview
            elif stage == "Onayla":
                authorization = response.kali_operation_authorization
                if (
                    authorization is not None
                    and self._preview is not None
                    and authorization.operation_digest == self._preview.operation_digest
                ):
                    self._authorization_id = authorization.authorization_id
            self.status.set(f"{stage} tamamlandı. Sonucu aşağıdan inceleyebilirsin.")

        self._dispatch(action, complete, f"Kali · {stage}")

    def preview(self) -> None:
        self._invalidate()
        revision = self._scope_choices.get(self.scope.get())
        kind = _OPERATIONS.get(self.operation.get())
        hostname, record = self.hostname.get(), self.record_type.get()
        if revision is None or kind is None or not hostname.strip():
            self.status.set("Önce etkin kapsamı, işlemi ve hedef alan adını seç.")
            return
        self._submit(
            lambda: self._controller.preview_kali_operation(
                revision, hostname, kind, record
            ),
            "Önizle",
        )

    def authorize(self) -> None:
        preview = self._preview
        if preview is None:
            self.status.set("Önce işlemi önizle.")
            return
        if not messagebox.askyesno(
            "Kali işlemini onayla",
            f"Hedef: {preview.hostname}\nİşlem: {preview.operation_kind.value}\n"
            f"Program: {preview.program_id}\n\n"
            "Aşağıda önizlediğin işleme izin verilsin mi? Çalıştır ayrı bir adımdır.",
            parent=self.output,
        ):
            return
        self._authorization_id = None
        self._submit(
            lambda: self._controller.authorize_kali_operation(preview), "Onayla"
        )

    def run(self) -> None:
        preview, authorization_id = self._preview, self._authorization_id
        if preview is None or authorization_id is None:
            self.status.set("Önce işlemi önizle ve onayla.")
            return
        if not messagebox.askyesno(
            "Kali işlemini çalıştır",
            f"{preview.hostname} için onayladığın {preview.operation_kind.value} "
            "işlemi şimdi çalışacak ve ağ isteği yapacak. Devam edilsin mi?",
            parent=self.output,
        ):
            return
        self._authorization_id = None
        self._generation += 1
        self._submit(
            lambda: self._controller.run_kali_operation(
                preview, authorization_id, operator_opt_in=True
            ),
            "Çalıştır",
        )
