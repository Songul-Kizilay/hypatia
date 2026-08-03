"""File loading entry point for the Knowledge Foundation."""

from __future__ import annotations

from pathlib import Path

from core.Exceptions import KnowledgeError
from knowledge.Document import Document, DocumentType


class DocumentLoader:
    """Loads supported text files into common Document models."""

    _DOCUMENT_TYPES = {
        ".txt": DocumentType.TEXT,
        ".md": DocumentType.MARKDOWN,
    }

    def load(self, file_path: str | Path) -> Document:
        """Read a supported file and return its complete document content."""
        path = Path(file_path)

        if not path.is_file():
            raise KnowledgeError(f"Document file was not found: {path}")

        document_type = self._DOCUMENT_TYPES.get(path.suffix.casefold())
        if document_type is None:
            raise KnowledgeError(f"Unsupported document type: {path.suffix}")

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            raise KnowledgeError(f"Document file could not be read: {path}") from error

        if not content.strip():
            raise KnowledgeError(f"Document file is empty: {path}")

        return Document(
            title=path.stem,
            content=content,
            source=str(path),
            document_type=document_type,
        )
