"""Join what a provider proposed to what the operator later concluded about it.

Two providers exist and nothing measures which one is earning its place. Both
halves of the answer are already recorded — a discovery names the provider that
produced it, and an assessment names what a person concluded after reading a
source — and no layer has ever put them together.

**The join, precisely.** There is no stored foreign key from an accepted source
back to the discovery that proposed it, so the bridge is canonical resource
identity: `identity_of(candidate.url)` against `identity_of(source.url)`. That is
not a fuzzy or domain-based match and it is not invented here — it is the same
function the panel already uses to decide whether a discovered candidate was
accepted, and the same one corroboration counting uses to decide whether two
records are one resource. From the accepted source onward the join is by exact
document identifier: source to evidence to assessment.

**What cannot be attributed is not guessed.** A resource both providers returned
has no single provider to credit, so it is counted apart rather than assigned to
whichever discovery came first. An assessed source that no discovery proposed was
added by hand and is counted apart too.

**Only the standing assessment speaks.** A judgement somebody later revised is
history, not a second sample; counting both would let changing your mind inflate
the evidence. And a source counts once no matter how many pieces of evidence came
out of it, because the unit is a document somebody appraised, not an excerpt.

Nothing here decides anything. It reads persisted runs, opens no socket, calls no
model, spends no budget, and returns counts. Measuring which provider has done
better is a prerequisite for ever choosing between them; it is not that choice.
"""

from __future__ import annotations

from collections.abc import Iterable

from core.Exceptions import ResearchError
from research.ResearchProviderQualityProfile import (
    MAX_REPORTED_SAMPLE_IDS,
    ResearchProviderQualityProfile,
)
from research.ResearchProviderQualityReport import (
    MAX_REPORTED_PROFILES,
    ResearchProviderQualityReport,
)
from research.ResearchQueryCategory import ResearchQueryCategory, category_of
from research.ResearchRun import ResearchRun
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceUsefulness import ResearchSourceUsefulness
from research.SourceIdentity import identity_of

_Key = tuple[str, ResearchQueryCategory]


class ResearchProviderQualityEvaluator:
    """Describe how each provider's assessed samples turned out."""

    def evaluate(
        self,
        runs: Iterable[ResearchRun],
    ) -> ResearchProviderQualityReport:
        """Return one profile per provider and question category."""
        materialised = list(runs)
        if not all(isinstance(run, ResearchRun) for run in materialised):
            raise ResearchError("Provider quality evaluation requires research runs.")

        discovery_counts: dict[_Key, int] = {}
        candidates: dict[_Key, set[str]] = {}
        # Identity to the keys that proposed it. A set, because the whole point
        # is to notice when it holds more than one.
        proposed_by: dict[str, set[_Key]] = {}
        accepted: dict[_Key, set[str]] = {}
        evidence_bearing: dict[_Key, set[str]] = {}
        assessed: dict[_Key, list[tuple[str, ResearchSourceAssessmentRecord]]] = {}
        ambiguous = 0
        unattributed = 0

        for run in materialised:
            for discovery in run.discoveries:
                key = (discovery.provider, category_of(discovery.query))
                discovery_counts[key] = discovery_counts.get(key, 0) + 1
                for candidate in discovery.candidates:
                    identity = identity_of(candidate.url)
                    candidates.setdefault(key, set()).add(identity)
                    proposed_by.setdefault(identity, set()).add(key)

            documents = {
                source.document_id: identity_of(source.url) for source in run.sources
            }
            with_evidence = {
                record.source_document_id
                for record in run.evidence
                if record.source_document_id in documents
            }
            current = _current_assessments(run)

            for document_id, identity in documents.items():
                attribution_keys = proposed_by.get(identity, set())
                if len(attribution_keys) != 1:
                    if document_id in current:
                        if attribution_keys:
                            ambiguous += 1
                        else:
                            unattributed += 1
                    continue
                [key] = tuple(attribution_keys)
                accepted.setdefault(key, set()).add(document_id)
                if document_id not in with_evidence:
                    continue
                evidence_bearing.setdefault(key, set()).add(document_id)
                assessment = current.get(document_id)
                if assessment is not None:
                    assessed.setdefault(key, []).append((document_id, assessment))

        profile_keys = sorted(
            set(discovery_counts) | set(candidates) | set(assessed),
            key=lambda key: (key[0], key[1].value),
        )[:MAX_REPORTED_PROFILES]
        return ResearchProviderQualityReport(
            profiles=tuple(
                _profile(
                    key,
                    discovery_counts.get(key, 0),
                    candidates.get(key, set()),
                    accepted.get(key, set()),
                    evidence_bearing.get(key, set()),
                    assessed.get(key, []),
                )
                for key in profile_keys
            ),
            ambiguous_attribution_count=ambiguous,
            unattributed_assessed_count=unattributed,
        )


def _current_assessments(
    run: ResearchRun,
) -> dict[str, ResearchSourceAssessmentRecord]:
    """Return each source's standing assessment, ignoring superseded ones.

    A revision replaces a judgement rather than adding one. Counting both would
    mean that changing your mind about a single source produced two samples,
    which would let a careful operator's second thoughts look like more evidence.
    """
    superseded = {
        assessment.supersedes_assessment_id
        for assessment in run.assessments
        if assessment.supersedes_assessment_id
    }
    standing: dict[str, ResearchSourceAssessmentRecord] = {}
    for assessment in run.assessments:
        if assessment.assessment_id in superseded:
            continue
        standing[assessment.source_document_id] = assessment
    return standing


def _profile(
    key: _Key,
    discovery_count: int,
    candidates: set[str],
    accepted: set[str],
    evidence_bearing: set[str],
    assessed: list[tuple[str, ResearchSourceAssessmentRecord]],
) -> ResearchProviderQualityProfile:
    provider, category = key
    samples = tuple(sorted(document_id for document_id, _ in assessed))
    return ResearchProviderQualityProfile(
        provider=provider,
        category=category,
        discovery_count=discovery_count,
        candidate_count=len(candidates),
        accepted_count=len(accepted),
        evidence_bearing_count=len(evidence_bearing),
        assessed_count=len(assessed),
        usefulness=_counts(
            list(ResearchSourceUsefulness),
            [assessment.usefulness for _, assessment in assessed],
        ),
        applicability=_counts(
            list(ResearchSourceApplicability),
            [assessment.applicability for _, assessment in assessed],
        ),
        independence=_counts(
            list(ResearchSourceIndependence),
            [assessment.independence for _, assessment in assessed],
        ),
        publication=_counts(
            list(ResearchSourcePublicationStatus),
            [assessment.publication_status for _, assessment in assessed],
        ),
        sample_document_ids=samples[:MAX_REPORTED_SAMPLE_IDS],
    )


def _counts[Answer](
    vocabulary: Iterable[Answer], values: Iterable[Answer]
) -> dict[Answer, int]:
    """Count each recorded answer, including the ones that answered nothing."""
    counts = {member: 0 for member in vocabulary}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return {member: count for member, count in counts.items() if count}
