"""What one provider produced for one kind of question, counted not scored.

There is no provider score here and there deliberately never will be one from
this data. A single number would compress four different judgements about a
handful of self-selected documents into something that looks measured, travels
easily, and cannot be argued with. The counts stay apart so a reader can see
which of them is actually carrying the claim.

The funnel is the load-bearing part. A candidate that was discovered, a source
that was accepted, a source that produced evidence, and a source somebody
appraised are four different populations, and dividing a number from the last by
a number from the first would be arithmetic between incomparable denominators.
So every stage is counted separately and every ratio names which one it used.

Silence is excluded rather than counted against anyone. `unknown` on a dimension
means nobody was asked, and an unassessed source means nobody looked; both are
reported as themselves and neither enters a usefulness rate. Coverage — how many
eligible sources were appraised at all — is reported next to the rate so a high
percentage over two sources cannot be mistaken for a finding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from research.ProviderSampleSize import ProviderSampleSize, sample_size_of
from research.ResearchQueryCategory import ResearchQueryCategory
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceEvidenceType import ResearchSourceEvidenceType
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceUsefulness import ResearchSourceUsefulness

MAX_REPORTED_SAMPLE_IDS = 50


@dataclass(frozen=True, slots=True)
class ResearchProviderQualityProfile:
    """Report one provider's record for one question category."""

    provider: str
    category: ResearchQueryCategory
    discovery_count: int = 0
    candidate_count: int = 0
    accepted_count: int = 0
    evidence_bearing_count: int = 0
    assessed_count: int = 0
    usefulness: dict[ResearchSourceUsefulness, int] = field(default_factory=dict)
    applicability: dict[ResearchSourceApplicability, int] = field(default_factory=dict)
    independence: dict[ResearchSourceIndependence, int] = field(default_factory=dict)
    publication: dict[ResearchSourcePublicationStatus, int] = field(
        default_factory=dict
    )
    evidence_type: dict[ResearchSourceEvidenceType, int] = field(default_factory=dict)
    sample_document_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ResearchError("A provider quality profile needs a provider.")
        if not isinstance(self.category, ResearchQueryCategory):
            raise ResearchError("A provider quality profile needs a query category.")
        for name in (
            "discovery_count",
            "candidate_count",
            "accepted_count",
            "evidence_bearing_count",
            "assessed_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Provider quality {name} must be whole.")
        if not isinstance(self.sample_document_ids, tuple):
            raise ResearchError("Provider quality samples must be an immutable tuple.")
        if len(self.sample_document_ids) > MAX_REPORTED_SAMPLE_IDS:
            raise ResearchError("A provider quality profile names too many samples.")
        if len(set(self.sample_document_ids)) != len(self.sample_document_ids):
            raise ResearchError("A provider quality sample is counted twice.")
        # The named samples are a bounded window onto the counted ones, so there
        # may be fewer names than samples but never more. More names than
        # samples would mean the audit trail disagreed with the number it is
        # supposed to explain.
        if len(self.sample_document_ids) > self.assessed_count:
            raise ResearchError("A provider quality profile names absent samples.")
        for name, vocabulary in (
            ("usefulness", ResearchSourceUsefulness),
            ("applicability", ResearchSourceApplicability),
            ("independence", ResearchSourceIndependence),
            ("publication", ResearchSourcePublicationStatus),
            ("evidence_type", ResearchSourceEvidenceType),
        ):
            counts = getattr(self, name)
            if not isinstance(counts, dict):
                raise ResearchError(f"Provider quality {name} must be a mapping.")
            for key, count in counts.items():
                if not isinstance(key, vocabulary):
                    raise ResearchError(f"Provider quality {name} key is invalid.")
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise ResearchError(f"Provider quality {name} count is invalid.")
        # The appraised sources are the unit, so the four dimensions describe the
        # same set and must agree about how big it is. A disagreement means a
        # source was counted on one dimension and lost on another.
        for name in (
            "usefulness",
            "applicability",
            "independence",
            "publication",
            "evidence_type",
        ):
            if sum(getattr(self, name).values()) != self.assessed_count:
                raise ResearchError(
                    f"Provider quality {name} does not describe every sample."
                )
        if self.assessed_count > self.evidence_bearing_count:
            raise ResearchError("More sources were assessed than could be.")

    @property
    def samples_truncated(self) -> bool:
        """Say whether more sources were counted than are named here."""
        return len(self.sample_document_ids) < self.assessed_count

    @property
    def sample_size(self) -> ProviderSampleSize:
        """Return how much weight these samples can carry."""
        return sample_size_of(self.assessed_count)

    @property
    def judged_usefulness_count(self) -> int:
        """Return how many samples the operator actually answered for.

        `unknown` is left out. It means the question was not answered, and
        rolling it into either side would turn a shrug into a verdict.
        """
        return self.assessed_count - self.usefulness.get(
            ResearchSourceUsefulness.UNKNOWN, 0
        )

    def coverage(self) -> str:
        """Render how much of the eligible population was appraised at all."""
        return f"{self.assessed_count} / {self.evidence_bearing_count}"

    def lines(self) -> tuple[str, ...]:
        """Render this profile with every denominator visible."""
        rendered = [
            f"{self.provider} — {self.category.label}",
            f"  discovery operations: {self.discovery_count}",
            f"  candidates discovered: {self.candidate_count}",
            f"  accepted sources: {self.accepted_count}",
            f"  sources with evidence: {self.evidence_bearing_count}",
            f"  assessed sources: {self.assessed_count}",
            f"  assessment coverage: {self.coverage()}",
            f"  samples named for inspection: {len(self.sample_document_ids)}"
            + (" (list truncated)" if self.samples_truncated else ""),
            f"  sample: {self.sample_size.value} — {self.sample_size.caution}",
        ]
        if not self.assessed_count:
            return tuple(rendered)
        judged = self.judged_usefulness_count
        rendered.append("  usefulness (of assessed sources):")
        for value in ResearchSourceUsefulness:
            count = self.usefulness.get(value, 0)
            if value is ResearchSourceUsefulness.UNKNOWN:
                rendered.append(
                    f"    {value.value}: {count} "
                    "(not answered; excluded from the rate below)"
                )
                continue
            rendered.append(
                f"    {value.value}: {count} / {judged}"
                + (f" ({round(100 * count / judged)}%)" if judged else "")
            )
        rendered.append(f"  applicability (of {self.assessed_count} assessed):")
        for applicability_value in ResearchSourceApplicability:
            count = self.applicability.get(applicability_value, 0)
            rendered.append(
                f"    {applicability_value.value}: {count} / {self.assessed_count}"
            )
        rendered.append(f"  independence (of {self.assessed_count} assessed):")
        for independence_value in ResearchSourceIndependence:
            count = self.independence.get(independence_value, 0)
            rendered.append(
                f"    {independence_value.value}: {count} / {self.assessed_count}"
            )
        rendered.append(f"  publication status (of {self.assessed_count} assessed):")
        for publication_value in ResearchSourcePublicationStatus:
            count = self.publication.get(publication_value, 0)
            rendered.append(
                f"    {publication_value.value}: {count} / {self.assessed_count}"
            )
        rendered.append(f"  evidence type (of {self.assessed_count} assessed):")
        for evidence_type_value in ResearchSourceEvidenceType:
            count = self.evidence_type.get(evidence_type_value, 0)
            rendered.append(
                f"    {evidence_type_value.value}: {count} / {self.assessed_count}"
            )
        return tuple(rendered)
