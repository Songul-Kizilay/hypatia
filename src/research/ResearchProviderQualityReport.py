"""Every provider profile together, with what the numbers cannot support attached.

Derived and never stored. Everything here recomputes from the research runs, so
persisting it would create a second copy that could drift from the first and
then be believed — and worse, a stored provider statistic is one step from a
stored provider preference.

There is no winner. The report has no field naming a better provider, no
recommended provider, and nothing downstream reads it to choose one, because the
data cannot support that: the operator chose which provider to ask, which
candidate to open, which source to accept, and which of those to appraise. Every
number here describes that chain of choices. It is evidence about the operator's
own experience, which is worth having, and it is not a benchmark.

Attribution that cannot be made is reported rather than guessed. A resource
discovered by both providers has no single provider to credit, so it is counted
apart instead of being assigned to whichever discovery happened to come first.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchProviderQualityProfile import ResearchProviderQualityProfile

#: Said in the report itself rather than left to documentation, because the
#: number and the caveat have to travel together or only the number travels.
SELECTION_BIAS_NOTICE = (
    "These figures describe sources the operator chose to ask for, chose to "
    "accept, and chose to assess. They are observational and selection-biased: "
    "they are descriptive evidence from actual use, not an unbiased measurement "
    "of what either provider returns."
)

NO_POLICY_NOTICE = (
    "No provider was selected, no default changed, no ranking altered, and no "
    "reputation updated. This report measures; it does not decide."
)

MAX_REPORTED_PROFILES = 40


@dataclass(frozen=True, slots=True)
class ResearchProviderQualityReport:
    """Report how assessed provider samples performed, deciding nothing."""

    profiles: tuple[ResearchProviderQualityProfile, ...] = ()
    ambiguous_attribution_count: int = 0
    unattributed_assessed_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.profiles, tuple):
            raise ResearchError("Provider quality profiles must be a tuple.")
        if len(self.profiles) > MAX_REPORTED_PROFILES:
            raise ResearchError("A provider quality report has too many profiles.")
        if not all(
            isinstance(profile, ResearchProviderQualityProfile)
            for profile in self.profiles
        ):
            raise ResearchError("A provider quality profile is invalid.")
        keys = [(profile.provider, profile.category) for profile in self.profiles]
        if len(keys) != len(set(keys)):
            raise ResearchError("A provider quality profile is reported twice.")
        for name in ("ambiguous_attribution_count", "unattributed_assessed_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Provider quality {name} must be whole.")

    @property
    def assessed_count(self) -> int:
        """Return how many appraised sources this report is built from."""
        return sum(profile.assessed_count for profile in self.profiles)

    @property
    def has_samples(self) -> bool:
        """Say whether anything has actually been appraised yet."""
        return self.assessed_count > 0

    def counts(self) -> dict[str, int]:
        """Return bounded structural counts suitable for an event payload."""
        return {
            "profile_count": len(self.profiles),
            "assessed_sample_count": self.assessed_count,
            "provider_count": len({profile.provider for profile in self.profiles}),
            "category_count": len({profile.category for profile in self.profiles}),
            "ambiguous_attribution_count": self.ambiguous_attribution_count,
            "unattributed_assessed_count": self.unattributed_assessed_count,
        }

    def lines(self) -> tuple[str, ...]:
        """Render the whole report, sample sizes and caveats included."""
        if not self.has_samples:
            return (
                "No assessed provider samples yet.",
                "",
                "Nothing has been appraised, so there is nothing to describe. "
                "That is not a finding about either provider.",
                "",
                NO_POLICY_NOTICE,
            )
        rendered: list[str] = []
        for profile in self.profiles:
            rendered.extend(profile.lines())
            rendered.append("")
        if self.ambiguous_attribution_count:
            rendered.append(
                f"Sources discovered by more than one provider: "
                f"{self.ambiguous_attribution_count} — left out of every profile "
                "rather than credited to one of them."
            )
        if self.unattributed_assessed_count:
            rendered.append(
                f"Assessed sources with no discovery record: "
                f"{self.unattributed_assessed_count} — added by hand, so no "
                "provider produced them."
            )
        rendered.extend(("", SELECTION_BIAS_NOTICE, "", NO_POLICY_NOTICE))
        return tuple(rendered)
