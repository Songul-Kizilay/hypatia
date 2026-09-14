"""Reconcile what is indexed locally against what research actually uses.

This answers a question the live testing kept raising: a document was created,
so where did it go? The reconciliation says — it is indexed, and no research run
references it. That is a complete and often perfectly fine answer, and being able
to give it is the point.

Reading only. Nothing is deleted, merged, repaired, or garbage-collected, and
there is no method here that could. A knowledge-only document may be exactly what
someone wanted, and automatic cleanup of things whose consequences nobody has
worked out is how good data disappears.

Resources are keyed by identity rather than document ID, so the same page stored
twice is one resource holding two documents. Reporting only documents would make
a duplicate look like extra coverage, which is the confusion the corroboration
counting already had to fix.
"""

from __future__ import annotations

from collections.abc import Iterable

from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from research.KnowledgeAttachment import KnowledgeAttachment
from research.KnowledgeReconciliationReport import KnowledgeReconciliationReport
from research.KnowledgeResourceRecord import (
    MAX_RECORD_TITLE_LENGTH,
    KnowledgeResourceRecord,
)
from research.ResearchRun import ResearchRun
from research.SourceIdentity import identity_of


class KnowledgeAttachmentReconciler:
    """Classify every indexed resource against canonical run membership."""

    def reconcile(
        self,
        documents: Iterable[KnowledgeDocumentReference],
        runs: Iterable[ResearchRun],
    ) -> KnowledgeReconciliationReport:
        """Return one record per resource, plus any broken run reference."""
        indexed = list(documents)
        run_list = list(runs)
        runs_by_document = self._runs_by_document(run_list)
        identity_by_document = self._identity_by_document(run_list, indexed)

        grouped: dict[str, list[KnowledgeDocumentReference]] = {}
        for document in indexed:
            identity = identity_by_document.get(
                document.document_id
            ) or self._fallback_identity(document)
            grouped.setdefault(identity, []).append(document)

        records = [
            self._record(identity, members, runs_by_document)
            for identity, members in grouped.items()
        ]
        records.extend(self._broken(run_list, indexed, identity_by_document))
        records.sort(
            key=lambda record: (record.attachment.value, record.resource_identity)
        )
        return KnowledgeReconciliationReport(records=tuple(records))

    @staticmethod
    def _record(
        identity: str,
        members: list[KnowledgeDocumentReference],
        runs_by_document: dict[str, list[str]],
    ) -> KnowledgeResourceRecord:
        """Classify one resource from the runs referencing any of its documents."""
        run_ids: list[str] = []
        for document in members:
            for run_id in runs_by_document.get(document.document_id, ()):
                if run_id not in run_ids:
                    run_ids.append(run_id)
        attachment = (
            KnowledgeAttachment.ATTACHED
            if run_ids
            else KnowledgeAttachment.KNOWLEDGE_ONLY
        )
        return KnowledgeResourceRecord(
            resource_identity=identity,
            attachment=attachment,
            document_ids=tuple(document.document_id for document in members),
            run_ids=tuple(run_ids),
            title=members[0].title[:MAX_RECORD_TITLE_LENGTH],
        )

    @staticmethod
    def _broken(
        runs: list[ResearchRun],
        indexed: list[KnowledgeDocumentReference],
        identity_by_document: dict[str, str],
    ) -> list[KnowledgeResourceRecord]:
        """Report a run naming a document the local index cannot produce.

        This is the only genuinely structural breakage in this area, and the
        only case the word orphan would fit. Everything else is knowledge.
        """
        present = {document.document_id for document in indexed}
        missing: dict[str, list[str]] = {}
        for run in runs:
            for record in run.sources:
                if record.document_id in present:
                    continue
                identity = (
                    identity_by_document.get(record.document_id)
                    or f"missing:{record.document_id}"
                )
                runs_for_identity = missing.setdefault(identity, [])
                if run.run_id not in runs_for_identity:
                    runs_for_identity.append(run.run_id)
        return [
            KnowledgeResourceRecord(
                resource_identity=identity,
                attachment=KnowledgeAttachment.BROKEN_REFERENCE,
                run_ids=tuple(run_ids),
            )
            for identity, run_ids in missing.items()
        ]

    @staticmethod
    def _runs_by_document(runs: list[ResearchRun]) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for run in runs:
            for record in run.sources:
                run_ids = mapping.setdefault(record.document_id, [])
                if run.run_id not in run_ids:
                    run_ids.append(run.run_id)
        return mapping

    @staticmethod
    def _identity_by_document(
        runs: list[ResearchRun],
        indexed: list[KnowledgeDocumentReference],
    ) -> dict[str, str]:
        """Map documents to resource identity, preferring the run's own URL.

        A run's source record keeps the URL it was accepted from, which is the
        better identity. A knowledge-only document falls back to its source
        field, which is the only locator the index carries.
        """
        mapping: dict[str, str] = {}
        for run in runs:
            for record in run.sources:
                identity = identity_of(record.url)
                if identity:
                    mapping[record.document_id] = identity
        for document in indexed:
            if document.document_id in mapping:
                continue
            identity = identity_of(document.source)
            if identity:
                mapping[document.document_id] = identity
        return mapping

    @staticmethod
    def _fallback_identity(document: KnowledgeDocumentReference) -> str:
        """Return a stable identity for a document with no usable locator.

        A local file has no URL, so its own identifier stands in. That keeps it
        distinct from every other document rather than collapsing unrelated
        local files into one bucket.
        """
        return document.source.strip() or f"document:{document.document_id}"
