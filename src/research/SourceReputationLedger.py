"""Aggregate our own assessments by origin, across every run.

The ledger is derived, never stored. That is what keeps a reputation honest: it
is recomputed from the assessments every time, so revising one assessment
revises the reputation, and a reputation can never outlive the judgements it
came from or drift from them.

Only authored assessments count. Nothing here reads a model's opinion of a
source, infers quality from a URL, or treats acceptance as approval — a source
is accepted because someone chose to read it, which says nothing about whether
it was any good.

Superseded assessments are excluded, so changing your mind about one page
actually changes the record rather than adding to it.

Assessing the same page twice counts once toward the standing. The sample is
meant to say how often this origin has produced work we judged well, and the same
page judged twice is one page's worth of evidence about the host. Accepted-record
counts stay as stored, because how many records exist is a storage fact. When
several active assessments cover equivalent records of that page, the least
trusting authored label represents the resource; input order is not an
epistemic rule.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.SourceIdentity import identity_of
from research.SourceOrigin import origin_of
from research.SourceReputation import SourceReputation

MAX_REPORTED_ORIGINS = 200


class SourceReputationLedger:
    """Build per-origin reputations from persisted assessments alone."""

    def build(
        self,
        runs: Iterable[ResearchRun],
    ) -> tuple[SourceReputation, ...]:
        """Return one reputation per origin, most-assessed first."""
        reputations: dict[str, SourceReputation] = {}
        seen_runs: dict[str, set[str]] = {}
        trust_by_resource: dict[
            tuple[str, str],
            ResearchInformationTrust,
        ] = {}
        for run in runs:
            origins = self._origins(run)
            urls = {source.document_id: source.url for source in run.sources}
            active_trust = self._active_trust(run)
            cited = self._cited_counts(run, origins)
            for document_id, origin in origins.items():
                current = reputations.get(origin) or SourceReputation(origin=origin)
                current = replace(
                    current,
                    accepted_count=current.accepted_count + 1,
                    evidence_count=current.evidence_count + cited.get(document_id, 0),
                )
                resource = identity_of(urls.get(document_id, "")) or document_id
                resource_key = (origin, resource)
                judged = active_trust.get(document_id)
                existing = trust_by_resource.get(resource_key)
                if judged is not None and (
                    existing is None
                    or self._trust_rank(judged) < self._trust_rank(existing)
                ):
                    trust_by_resource[resource_key] = judged
                reputations[origin] = current
                seen_runs.setdefault(origin, set()).add(run.run_id)
        for (origin, _resource), resource_trust in trust_by_resource.items():
            reputations[origin] = self._with_assessment(
                reputations[origin],
                resource_trust,
            )
        finished = [
            replace(reputation, run_count=len(seen_runs.get(origin, ())))
            for origin, reputation in reputations.items()
        ]
        finished.sort(key=lambda entry: (-entry.assessed_count, entry.origin))
        return tuple(finished[:MAX_REPORTED_ORIGINS])

    def for_origin(
        self,
        origin: str,
        runs: Iterable[ResearchRun],
    ) -> SourceReputation | None:
        """Return one origin's reputation, or None when we have never seen it."""
        normalised = origin_of(f"https://{origin}") or origin.strip().casefold()
        for reputation in self.build(runs):
            if reputation.origin == normalised:
                return reputation
        return None

    @staticmethod
    def _with_assessment(
        reputation: SourceReputation,
        trust: ResearchInformationTrust | None,
    ) -> SourceReputation:
        """Count one accepted source's judgement, if it carries one."""
        if trust is None or trust is ResearchInformationTrust.UNASSESSED:
            return reputation
        field = SourceReputation.trust_field(trust)
        if not field:
            return reputation
        return replace(
            reputation,
            assessed_count=reputation.assessed_count + 1,
            **{field: getattr(reputation, field) + 1},
        )

    @staticmethod
    def _origins(run: ResearchRun) -> dict[str, str]:
        """Map each accepted document to the origin its URL names."""
        origins: dict[str, str] = {}
        for source in run.sources:
            origin = origin_of(source.url)
            if origin:
                origins[source.document_id] = origin
        return origins

    @staticmethod
    def _cited_counts(run: ResearchRun, origins: dict[str, str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in run.evidence:
            if record.source_document_id in origins:
                counts[record.source_document_id] = (
                    counts.get(record.source_document_id, 0) + 1
                )
        return counts

    @staticmethod
    def _active_trust(run: ResearchRun) -> dict[str, ResearchInformationTrust]:
        """Return each source's least-trusting active authored assessment."""
        superseded = {
            assessment.supersedes_assessment_id
            for assessment in run.assessments
            if assessment.supersedes_assessment_id
        }
        trust: dict[str, ResearchInformationTrust] = {}
        for assessment in run.assessments:
            if assessment.assessment_id in superseded:
                continue
            current = trust.get(assessment.source_document_id)
            if current is None or SourceReputationLedger._trust_rank(
                assessment.information_trust
            ) < SourceReputationLedger._trust_rank(current):
                trust[assessment.source_document_id] = assessment.information_trust
        return trust

    @staticmethod
    def _trust_rank(value: ResearchInformationTrust) -> int:
        return {
            ResearchInformationTrust.UNASSESSED: 0,
            ResearchInformationTrust.LOW: 1,
            ResearchInformationTrust.MEDIUM: 2,
            ResearchInformationTrust.HIGH: 3,
        }[value]
