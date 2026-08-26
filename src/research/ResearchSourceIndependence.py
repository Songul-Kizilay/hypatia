"""Whether a source is its own witness, or is repeating another one.

Canonical identity already merges the cases a machine can be sure about: the
same DOI, the same URL up to case and a trailing slash. It cannot see the cases
that matter most to corroboration — a press release restating a vendor advisory,
a news article summarising one paper, two papers reanalysing one dataset. Those
are four documents and one witness, and only somebody who read them knows it.

Recording that judgement changes nothing on its own. No records merge, nothing
is deleted, and no corroboration count moves, because counting is a separate
question that a later milestone may answer by consulting this. What it does is
stop the knowledge being lost the moment the person who had it closes the panel.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSourceIndependence(StrEnum):
    """Say whether a source stands alone or repeats another."""

    UNKNOWN = "unknown"
    INDEPENDENT = "independent"
    LIKELY_DUPLICATE = "likely_duplicate"
    DERIVATIVE = "derivative"
