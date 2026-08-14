"""Deterministic structural graph for locally loaded knowledge."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from core.Exceptions import KnowledgeError
from knowledge.Chunk import Chunk
from knowledge.Document import Document


class KnowledgeGraphNodeKind(StrEnum):
    """The source-model kinds represented by a graph node."""

    DOCUMENT = "document"
    CHUNK = "chunk"


class KnowledgeGraphRelation(StrEnum):
    """Explainable structural relationships created from local sources."""

    CONTAINS = "contains"
    PRECEDES = "precedes"


@dataclass(frozen=True, slots=True)
class KnowledgeGraphNode:
    """An immutable, locally derived graph node."""

    node_id: str
    kind: KnowledgeGraphNodeKind
    label: str
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id.strip():
            raise KnowledgeError("Knowledge graph node ID cannot be empty.")
        if not isinstance(self.label, str) or not self.label.strip():
            raise KnowledgeError("Knowledge graph node label cannot be empty.")
        if not isinstance(self.kind, KnowledgeGraphNodeKind):
            raise KnowledgeError("Knowledge graph node kind is invalid.")
        object.__setattr__(self, "node_id", self.node_id.strip())
        object.__setattr__(self, "label", self.label.strip())
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class KnowledgeGraphEdge:
    """A directed, typed relationship between two graph nodes."""

    source_node_id: str
    relation: KnowledgeGraphRelation
    target_node_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_node_id, str) or not self.source_node_id.strip():
            raise KnowledgeError("Knowledge graph edge source cannot be empty.")
        if not isinstance(self.target_node_id, str) or not self.target_node_id.strip():
            raise KnowledgeError("Knowledge graph edge target cannot be empty.")
        if not isinstance(self.relation, KnowledgeGraphRelation):
            raise KnowledgeError("Knowledge graph edge relation is invalid.")
        object.__setattr__(self, "source_node_id", self.source_node_id.strip())
        object.__setattr__(self, "target_node_id", self.target_node_id.strip())


@dataclass(frozen=True, slots=True)
class KnowledgeGraphView:
    """A deterministic, bounded subgraph selected for an explicit request."""

    nodes: tuple[KnowledgeGraphNode, ...]
    edges: tuple[KnowledgeGraphEdge, ...]


class KnowledgeGraph:
    """Keeps a derived local document-and-chunk graph separate from persistence."""

    def __init__(self) -> None:
        self._nodes: dict[str, KnowledgeGraphNode] = {}
        self._edges: dict[
            tuple[str, KnowledgeGraphRelation, str], KnowledgeGraphEdge
        ] = {}

    def index_document(self, document: Document, chunks: Iterable[Chunk]) -> None:
        """Add one document, its chunks, and their structural relationships."""
        if not isinstance(document, Document):
            raise KnowledgeError("Knowledge graph expects a Document instance.")
        chunk_values = tuple(chunks)
        if not all(isinstance(chunk, Chunk) for chunk in chunk_values):
            raise KnowledgeError("Knowledge graph accepts only Chunk instances.")
        if any(chunk.document_id != document.document_id for chunk in chunk_values):
            raise KnowledgeError(
                "Knowledge graph chunks must belong to their document."
            )

        candidate_nodes: dict[str, KnowledgeGraphNode] = {}
        candidate_edges: dict[
            tuple[str, KnowledgeGraphRelation, str], KnowledgeGraphEdge
        ] = {}
        document_node = KnowledgeGraphNode(
            node_id=self.document_node_id(document.document_id),
            kind=KnowledgeGraphNodeKind.DOCUMENT,
            label=document.title,
            metadata={
                "document_id": document.document_id,
                "source": document.source,
                "document_type": document.document_type.value,
            },
        )
        self._stage_node(candidate_nodes, document_node)

        previous_chunk_node_id: str | None = None
        for chunk in chunk_values:
            chunk_node = KnowledgeGraphNode(
                node_id=self.chunk_node_id(chunk.chunk_id),
                kind=KnowledgeGraphNodeKind.CHUNK,
                label=f"Paragraph {chunk.index + 1}",
                metadata={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "index": chunk.index,
                },
            )
            self._stage_node(candidate_nodes, chunk_node)
            self._stage_edge(
                candidate_nodes,
                candidate_edges,
                KnowledgeGraphEdge(
                    source_node_id=document_node.node_id,
                    relation=KnowledgeGraphRelation.CONTAINS,
                    target_node_id=chunk_node.node_id,
                ),
            )
            if previous_chunk_node_id is not None:
                self._stage_edge(
                    candidate_nodes,
                    candidate_edges,
                    KnowledgeGraphEdge(
                        source_node_id=previous_chunk_node_id,
                        relation=KnowledgeGraphRelation.PRECEDES,
                        target_node_id=chunk_node.node_id,
                    ),
                )
            previous_chunk_node_id = chunk_node.node_id

        if any(node_id in self._nodes for node_id in candidate_nodes):
            duplicate_node_id = next(
                node_id for node_id in candidate_nodes if node_id in self._nodes
            )
            raise KnowledgeError(
                f"Knowledge graph node is already indexed: {duplicate_node_id}"
            )
        if any(edge_key in self._edges for edge_key in candidate_edges):
            raise KnowledgeError("Knowledge graph edge is already indexed.")
        self._nodes.update(candidate_nodes)
        self._edges.update(candidate_edges)

    def view_for_chunks(self, chunks: Iterable[Chunk]) -> KnowledgeGraphView:
        """Return the containing-document relationships for selected chunks."""
        selected_nodes: dict[str, KnowledgeGraphNode] = {}
        selected_edges: list[KnowledgeGraphEdge] = []

        for chunk in chunks:
            if not isinstance(chunk, Chunk):
                raise KnowledgeError("Knowledge graph accepts only Chunk instances.")
            chunk_node_id = self.chunk_node_id(chunk.chunk_id)
            chunk_node = self._nodes.get(chunk_node_id)
            if chunk_node is None:
                raise KnowledgeError(
                    f"Knowledge graph chunk was not found: {chunk.chunk_id}"
                )
            contains_edge = self._containing_edge(chunk_node_id)
            document_node = self._nodes[contains_edge.source_node_id]
            selected_nodes.setdefault(document_node.node_id, document_node)
            selected_nodes.setdefault(chunk_node.node_id, chunk_node)
            if contains_edge not in selected_edges:
                selected_edges.append(contains_edge)

        return KnowledgeGraphView(
            nodes=tuple(selected_nodes.values()),
            edges=tuple(selected_edges),
        )

    def node_count(self) -> int:
        """Return the number of derived graph nodes."""
        return len(self._nodes)

    def edge_count(self) -> int:
        """Return the number of derived graph edges."""
        return len(self._edges)

    def clear(self) -> None:
        """Clear only derived graph state."""
        self._nodes.clear()
        self._edges.clear()

    @staticmethod
    def document_node_id(document_id: str) -> str:
        return f"document:{document_id}"

    @staticmethod
    def chunk_node_id(chunk_id: str) -> str:
        return f"chunk:{chunk_id}"

    @staticmethod
    def _stage_node(
        nodes: dict[str, KnowledgeGraphNode],
        node: KnowledgeGraphNode,
    ) -> None:
        if node.node_id in nodes:
            raise KnowledgeError(
                f"Knowledge graph node is already indexed: {node.node_id}"
            )
        nodes[node.node_id] = node

    @staticmethod
    def _stage_edge(
        nodes: Mapping[str, KnowledgeGraphNode],
        edges: dict[tuple[str, KnowledgeGraphRelation, str], KnowledgeGraphEdge],
        edge: KnowledgeGraphEdge,
    ) -> None:
        if edge.source_node_id not in nodes or edge.target_node_id not in nodes:
            raise KnowledgeError("Knowledge graph edge references an unknown node.")
        key = (edge.source_node_id, edge.relation, edge.target_node_id)
        if key in edges:
            raise KnowledgeError("Knowledge graph edge is already indexed.")
        edges[key] = edge

    def _containing_edge(self, chunk_node_id: str) -> KnowledgeGraphEdge:
        for edge in self._edges.values():
            if (
                edge.relation is KnowledgeGraphRelation.CONTAINS
                and edge.target_node_id == chunk_node_id
            ):
                return edge
        raise KnowledgeError(
            f"Knowledge graph containing document was not found: {chunk_node_id}"
        )
