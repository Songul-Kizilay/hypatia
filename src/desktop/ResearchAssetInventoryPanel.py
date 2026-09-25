"""Operator-authored Bug Bounty asset inventory: observe, relate, list.

Reuses the exact `ttk.Treeview` + scrollbar + `<<TreeviewSelect>>` +
`iid -> detail-text` dict pattern already established by the mission-audit
traceability view (`TkinterDesktopWindow._MissionAuditTraceabilityTreeBuilder`).
Every scope reading rendered here is explicitly labelled recomputed-live —
never a stored or stale value — matching the epistemic discipline this
inventory is built on: asset existence, an observation, or a `RESOLVES_TO`
relation is never itself authorization to fetch, scan, or execute anything.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from brain.BrainResponse import BrainResponse
from desktop.DesktopController import DesktopController
from research.ResearchAssetKind import ResearchAssetKind


def _single_line(note: str) -> str:
    """Render one recorded note as a single line, or say there is none.

    Notes are operator-authored text shown next to labelled fields. A note
    carrying interior newlines (possible only from a hand-edited store file,
    never from the single-line entry widgets) would otherwise render as extra
    `Recorded at:`/`Provenance:` lines and misrepresent recorded provenance.
    """
    return " ".join(note.split()) or "none"


class ResearchAssetInventoryPanel:
    """List, observe, and relate operator-authored assets for one program."""

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
        kinds = tuple(kind.value for kind in ResearchAssetKind)

        self.program_id = tk.StringVar(master=parent)
        self.observation_kind = tk.StringVar(
            master=parent, value=ResearchAssetKind.HOSTNAME.value
        )
        self.observation_value = tk.StringVar(master=parent)
        self.observation_note = tk.StringVar(master=parent)
        self.relation_source_kind = tk.StringVar(
            master=parent, value=ResearchAssetKind.HOSTNAME.value
        )
        self.relation_source_value = tk.StringVar(master=parent)
        self.relation_related_kind = tk.StringVar(
            master=parent, value=ResearchAssetKind.IP_ADDRESS.value
        )
        self.relation_related_value = tk.StringVar(master=parent)
        self.relation_note = tk.StringVar(master=parent)
        self.status = tk.StringVar(
            master=parent, value="Enter a program ID and load the inventory."
        )
        self.detail = tk.StringVar(
            master=parent, value="Select a row to see its recorded fields."
        )

        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)
        parent.rowconfigure(4, weight=1)

        ttk.Label(parent, text="Program ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.program_id).grid(
            row=0, column=1, columnspan=2, sticky="ew", padx=8, pady=4
        )
        ttk.Button(parent, text="Load inventory", command=self.load).grid(
            row=0, column=3, padx=4
        )

        observation_frame = ttk.LabelFrame(
            parent, text="Record a new observation", padding=8
        )
        observation_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        observation_frame.columnconfigure(1, weight=1)
        ttk.Label(observation_frame, text="Kind").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            observation_frame,
            textvariable=self.observation_kind,
            values=kinds,
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=8, pady=2)
        ttk.Label(observation_frame, text="Value").grid(row=1, column=0, sticky="w")
        ttk.Entry(observation_frame, textvariable=self.observation_value).grid(
            row=1, column=1, sticky="ew", padx=8, pady=2
        )
        ttk.Label(observation_frame, text="Note (never enter a secret)").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Entry(observation_frame, textvariable=self.observation_note).grid(
            row=2, column=1, sticky="ew", padx=8, pady=2
        )
        ttk.Button(
            observation_frame,
            text="Record observation",
            command=self.record_observation,
        ).grid(row=3, column=1, sticky="e", pady=(4, 0))

        relation_frame = ttk.LabelFrame(
            parent, text="Record a new relation (resolves_to)", padding=8
        )
        relation_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        relation_frame.columnconfigure(1, weight=1)
        relation_frame.columnconfigure(3, weight=1)
        ttk.Label(relation_frame, text="Source kind").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            relation_frame,
            textvariable=self.relation_source_kind,
            values=kinds,
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=8, pady=2)
        ttk.Label(relation_frame, text="Source value").grid(row=0, column=2, sticky="w")
        ttk.Entry(relation_frame, textvariable=self.relation_source_value).grid(
            row=0, column=3, sticky="ew", padx=8, pady=2
        )
        ttk.Label(relation_frame, text="Related kind").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            relation_frame,
            textvariable=self.relation_related_kind,
            values=kinds,
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=8, pady=2)
        ttk.Label(relation_frame, text="Related value").grid(
            row=1, column=2, sticky="w"
        )
        ttk.Entry(relation_frame, textvariable=self.relation_related_value).grid(
            row=1, column=3, sticky="ew", padx=8, pady=2
        )
        ttk.Label(relation_frame, text="Note (never enter a secret)").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Entry(relation_frame, textvariable=self.relation_note).grid(
            row=2, column=1, columnspan=3, sticky="ew", padx=8, pady=2
        )
        ttk.Button(
            relation_frame, text="Record relation", command=self.record_relation
        ).grid(row=3, column=3, sticky="e", pady=(4, 0))

        ttk.Label(parent, textvariable=self.status, wraplength=900).grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(8, 0)
        )

        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=4, column=0, columnspan=4, sticky="nsew", pady=(4, 0))
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
        ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(4, 0))

    def load(self) -> None:
        """Fetch the derived read-only inventory; never itself a mutation."""
        program_id = self.program_id.get().strip()
        if not program_id:
            self.status.set("Enter a program ID first.")
            return

        def action() -> BrainResponse:
            return self._controller.preview_research_asset_inventory(program_id)

        self._dispatch(action, self._render, "asset inventory")

    def record_observation(self) -> None:
        program_id = self.program_id.get().strip()
        if not program_id:
            self.status.set("Enter a program ID first.")
            return
        kind = self.observation_kind.get()
        value = self.observation_value.get()
        note = self.observation_note.get()

        def action() -> BrainResponse:
            return self._controller.record_research_asset_observation(
                program_id, kind, value, note
            )

        self._dispatch(action, self._after_write, "asset observation")

    def record_relation(self) -> None:
        program_id = self.program_id.get().strip()
        if not program_id:
            self.status.set("Enter a program ID first.")
            return
        source_kind = self.relation_source_kind.get()
        source_value = self.relation_source_value.get()
        related_kind = self.relation_related_kind.get()
        related_value = self.relation_related_value.get()
        note = self.relation_note.get()

        def action() -> BrainResponse:
            return self._controller.record_research_asset_relation(
                program_id,
                source_kind,
                source_value,
                related_kind,
                related_value,
                note=note,
            )

        self._dispatch(action, self._after_write, "asset relation")

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
        assets_root = self.tree.insert(
            "",
            "end",
            text=f"Assets ({len(response.research_asset_inventory)})",
        )
        for entry in response.research_asset_inventory:
            asset = entry.asset
            if entry.scope.has_active_scope_revision and entry.scope.resolution:
                scope_text = (
                    f"{entry.scope.resolution.status.value} "
                    "(recomputed live from active policy, not stored)"
                )
            else:
                scope_text = "no active scope revision for this program"
            label = (
                f"{asset.kind.value}: {asset.canonical_value} "
                f"({len(asset.observations)} observation(s), scope: {scope_text})"
            )
            asset_iid = self.tree.insert(assets_root, "end", text=label)
            self._details[asset_iid] = "\n".join(
                (
                    f"Kind: {asset.kind.value}",
                    f"Canonical value: {asset.canonical_value}",
                    f"Observations: {len(asset.observations)}",
                    f"First seen: {asset.first_seen.isoformat()}",
                    f"Last seen: {asset.last_seen.isoformat()}",
                    f"Scope: {scope_text}",
                )
            )
            for observation in asset.observations:
                observation_label = (
                    f"Observation {observation.observation_id} "
                    f"({observation.provenance.value}, "
                    f"{observation.recorded_at.isoformat()})"
                )
                observation_iid = self.tree.insert(
                    asset_iid, "end", text=observation_label
                )
                self._details[observation_iid] = "\n".join(
                    (
                        f"Observation ID: {observation.observation_id}",
                        f"Provenance: {observation.provenance.value}",
                        f"Note: {_single_line(observation.note)}",
                        f"Recorded at: {observation.recorded_at.isoformat()}",
                    )
                )
        relations_root = self.tree.insert(
            "",
            "end",
            text=f"Relations ({len(response.research_asset_relations)})",
        )
        for relation in response.research_asset_relations:
            label = (
                f"{relation.kind.value}: "
                f"{relation.source_kind.value}:{relation.source_value} -> "
                f"{relation.related_kind.value}:{relation.related_value}"
            )
            relation_iid = self.tree.insert(relations_root, "end", text=label)
            self._details[relation_iid] = "\n".join(
                (
                    f"Relation ID: {relation.relation_id}",
                    f"Kind: {relation.kind.value}",
                    f"Source: {relation.source_kind.value}:{relation.source_value}",
                    "Related: "
                    f"{relation.related_kind.value}:{relation.related_value}",
                    f"Note: {_single_line(relation.note)}",
                    f"Recorded at: {relation.recorded_at.isoformat()}",
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
