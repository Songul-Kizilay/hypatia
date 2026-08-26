"""How much weight a set of assessed samples can carry, which is usually little.

The failure this exists to prevent is a percentage. Three useful sources out of
four is 75%, and 75% reads like a measurement even though it is four decisions by
one person about four documents they chose to look at. Attaching a band to every
ratio makes the sample size travel with the number instead of being something a
reader has to go and find.

`NO_DATA` is a real answer and the most common one early on. Zero assessed
samples is not zero quality, and a provider nobody has judged yet has not been
found wanting — it has not been looked at.

None of these bands is a confidence interval. There is no statistics layer here
and inventing one would give manual, self-selected observations a precision they
cannot have. They are a reminder, in the only place a reader will definitely
see it.
"""

from __future__ import annotations

from enum import StrEnum

#: Where the bands change. Deliberately unambitious: nothing in this range is
#: enough to conclude anything about a provider, and the largest band is named
#: `DESCRIPTIVE` rather than `SUFFICIENT` for that reason.
VERY_SMALL_SAMPLE_MAXIMUM = 4
LIMITED_SAMPLE_MAXIMUM = 19


class ProviderSampleSize(StrEnum):
    """Say how much a count of assessed samples can be leaned on."""

    NO_DATA = "no_data"
    VERY_SMALL = "very_small"
    LIMITED = "limited"
    DESCRIPTIVE = "descriptive"

    @property
    def caution(self) -> str:
        """Return the warning that travels with every ratio in this band."""
        return _CAUTION[self]


_CAUTION = {
    ProviderSampleSize.NO_DATA: (
        "No assessed samples. Nothing is measured here, which is not the same "
        "as measuring nothing good."
    ),
    ProviderSampleSize.VERY_SMALL: (
        "Very small sample — descriptive only, and one more judgement would "
        "move it noticeably."
    ),
    ProviderSampleSize.LIMITED: (
        "Limited sample — descriptive only."
    ),
    ProviderSampleSize.DESCRIPTIVE: (
        "Descriptive only: these are sources the operator chose to inspect, "
        "not a measured sample of what the provider returns."
    ),
}


def sample_size_of(assessed_count: int) -> ProviderSampleSize:
    """Return the band this many assessed samples falls in."""
    if isinstance(assessed_count, bool) or not isinstance(assessed_count, int):
        return ProviderSampleSize.NO_DATA
    if assessed_count <= 0:
        return ProviderSampleSize.NO_DATA
    if assessed_count <= VERY_SMALL_SAMPLE_MAXIMUM:
        return ProviderSampleSize.VERY_SMALL
    if assessed_count <= LIMITED_SAMPLE_MAXIMUM:
        return ProviderSampleSize.LIMITED
    return ProviderSampleSize.DESCRIPTIVE
