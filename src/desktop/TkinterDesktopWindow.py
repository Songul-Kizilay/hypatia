"""Tkinter presentation for the deliberately narrow first desktop shell."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from brain.BrainResponse import BrainResponse
from desktop.DesktopController import DesktopController


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
        container.rowconfigure(2, weight=1)

        session_frame = ttk.LabelFrame(container, text="Session", padding=8)
        session_frame.grid(row=0, column=0, sticky="ew")
        session_frame.columnconfigure(0, weight=1)
        ttk.Entry(session_frame, textvariable=self._session_id).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            session_frame,
            text="Select session",
            command=self._select_session,
        ).grid(row=0, column=1, sticky="ew")
        ttk.Button(
            session_frame,
            text="Semantic status",
            command=self._show_semantic_status,
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))

        ttk.Label(container, textvariable=self._status).grid(
            row=1, column=0, sticky="w", pady=(8, 4)
        )

        self._transcript = scrolledtext.ScrolledText(
            container,
            wrap=tk.WORD,
            state=tk.DISABLED,
            height=18,
        )
        self._transcript.grid(row=2, column=0, sticky="nsew")

        composer_frame = ttk.LabelFrame(container, text="Message", padding=8)
        composer_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
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
        self._append_to_transcript(f"Hypatia: {response.message}\n")

    def _append_to_transcript(self, value: str) -> None:
        self._transcript.configure(state=tk.NORMAL)
        self._transcript.insert(tk.END, value)
        self._transcript.see(tk.END)
        self._transcript.configure(state=tk.DISABLED)
