"""Tkinter presentation for the deliberately narrow first desktop shell."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, scrolledtext, ttk
from typing import Protocol

from brain.BrainResponse import BrainResponse
from brain.SessionSummary import SessionSummary
from desktop.DesktopController import DesktopController
from knowledge.KnowledgeCitation import KnowledgeCitation


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

    def __init__(
        self,
        controller: DesktopController,
        root: tk.Tk | None = None,
    ) -> None:
        self._controller = controller
        self._root = root or tk.Tk()
        self._status = tk.StringVar(value="Ready")
        self._session_id = tk.StringVar()
        self._session_rename_target = tk.StringVar()
        self._recall_query = tk.StringVar()
        self._knowledge_query = tk.StringVar()
        self._relation_source_id = tk.StringVar()
        self._relation_target_id = tk.StringVar()
        self._session_summaries: list[SessionSummary] = []

        self._root.title("Hypatia")
        self._root.minsize(760, 520)
        self._build_layout()

    def run(self) -> None:
        """Enter the local desktop event loop."""
        self._root.mainloop()

    def _build_layout(self) -> None:
        container = ttk.Frame(self._root, padding=12)
        container.grid(sticky="nsew")
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(5, weight=1)

        session_frame = ttk.LabelFrame(container, text="Session", padding=8)
        session_frame.grid(row=0, column=0, sticky="ew")
        session_frame.columnconfigure(0, weight=1)
        self._session_list = tk.Listbox(
            session_frame,
            height=4,
            exportselection=False,
        )
        self._session_list.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        self._session_list.bind("<<ListboxSelect>>", self._choose_session)
        ttk.Entry(session_frame, textvariable=self._session_id).grid(
            row=1, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            session_frame,
            text="Select session",
            command=self._select_session,
        ).grid(row=1, column=1, sticky="ew")
        ttk.Button(
            session_frame,
            text="Refresh sessions",
            command=self._refresh_sessions,
        ).grid(row=1, column=2, sticky="ew", padx=(8, 0))
        ttk.Button(
            session_frame,
            text="Semantic status",
            command=self._show_semantic_status,
        ).grid(row=1, column=3, sticky="ew", padx=(8, 0))
        ttk.Button(
            session_frame,
            text="Session details",
            command=self._show_session_details,
        ).grid(row=2, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(
            session_frame,
            text="Recent chats",
            command=self._show_session_recent,
        ).grid(row=2, column=2, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(
            session_frame,
            text="Session activity",
            command=self._show_session_activity,
        ).grid(row=2, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(session_frame, text="New session ID").grid(
            row=3,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Entry(session_frame, textvariable=self._session_rename_target).grid(
            row=3,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=(8, 8),
            pady=(8, 0),
        )
        ttk.Button(
            session_frame,
            text="Preview rename",
            command=self._preview_and_rename_session,
        ).grid(row=3, column=3, sticky="ew", pady=(8, 0))

        recall_frame = ttk.LabelFrame(container, text="Conversation recall", padding=8)
        recall_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        recall_frame.columnconfigure(0, weight=1)
        ttk.Entry(recall_frame, textvariable=self._recall_query).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            recall_frame,
            text="Recall",
            command=self._show_recall,
        ).grid(row=0, column=1, sticky="ew")
        ttk.Button(
            recall_frame,
            text="Semantic recall",
            command=self._show_semantic_recall,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))

        knowledge_frame = ttk.LabelFrame(container, text="Local knowledge", padding=8)
        knowledge_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        knowledge_frame.columnconfigure(0, weight=1)
        ttk.Entry(knowledge_frame, textvariable=self._knowledge_query).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            knowledge_frame,
            text="Knowledge context",
            command=self._show_knowledge_context,
        ).grid(row=0, column=1, sticky="ew")
        ttk.Button(
            knowledge_frame,
            text="Knowledge graph",
            command=self._show_knowledge_graph,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))
        ttk.Button(
            knowledge_frame,
            text="Ask sources",
            command=self._ask_knowledge,
        ).grid(row=0, column=3, sticky="ew", padx=(8, 0))
        ttk.Button(
            knowledge_frame,
            text="Loaded sources",
            command=self._show_knowledge_list,
        ).grid(row=0, column=4, sticky="ew", padx=(8, 0))

        relation_frame = ttk.LabelFrame(
            container,
            text="Local source relation",
            padding=8,
        )
        relation_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
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

        ttk.Label(container, textvariable=self._status).grid(
            row=4, column=0, sticky="w", pady=(8, 4)
        )

        self._transcript = scrolledtext.ScrolledText(
            container,
            wrap=tk.WORD,
            state=tk.DISABLED,
            height=18,
        )
        self._transcript.grid(row=5, column=0, sticky="nsew")

        composer_frame = ttk.LabelFrame(container, text="Message", padding=8)
        composer_frame.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        composer_frame.columnconfigure(0, weight=1)
        self._composer = tk.Text(composer_frame, height=4, wrap=tk.WORD)
        self._composer.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(composer_frame, text="Send", command=self._send_message).grid(
            row=0, column=1, sticky="ns"
        )
        self._composer.bind("<Control-Return>", self._send_with_keyboard)
        self._composer.focus_set()

    def _send_with_keyboard(self, _event: tk.Event[tk.Text]) -> str:
        self._send_message()
        return "break"

    def _send_message(self) -> None:
        message = self._composer.get("1.0", "end-1c")
        try:
            response = self._controller.submit_message(message)
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_exchange("You", message, response)
        self._composer.delete("1.0", tk.END)

    def _select_session(self) -> None:
        try:
            response = self._controller.select_session(self._session_id.get())
        except ValueError as error:
            self._status.set(str(error))
            return
        self._append_response(response)

    def _show_semantic_status(self) -> None:
        self._append_response(self._controller.semantic_status())

    def _show_recall(self) -> None:
        self._show_recall_response(self._controller.recall)

    def _show_semantic_recall(self) -> None:
        self._show_recall_response(self._controller.semantic_recall)

    def _show_knowledge_context(self) -> None:
        self._show_knowledge_response(self._controller.knowledge_context)

    def _show_knowledge_graph(self) -> None:
        self._show_knowledge_response(self._controller.knowledge_graph)

    def _ask_knowledge(self) -> None:
        self._show_knowledge_response(self._controller.ask_knowledge)

    def _show_knowledge_list(self) -> None:
        self._append_response(self._controller.list_knowledge())

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
        self._session_id.set(self._session_summaries[selected_indices[0]].session_id)

    def _render_session_summaries(self, response: BrainResponse) -> None:
        """Show only current successful Brain data, never a stale local copy."""
        self._session_list.delete(0, tk.END)
        self._session_summaries = []
        if not response.success:
            return
        self._session_summaries = response.session_summaries
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

    def _append_to_transcript(self, value: str) -> None:
        self._transcript.configure(state=tk.NORMAL)
        self._transcript.insert(tk.END, value)
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
