"""Whether a source is its own witness, or is repeating another one.

Canonical identity already merges the cases a machine can be sure about: the
same DOI, the same URL up to case and a trailing slash. It cannot see the cases
that matter most to corroboration — a press release restating a vendor advisory,
a news article summarising one paper, two papers reanalysing one dataset. Those
are four documents and one witness, and only somebody who read them knows it.

Recording that judgement changes nothing on its own. No records merge and
nothing is deleted. Claim calibration may consult it when deciding whether
several distinct resources provide explicitly independent corroboration, but it
never edits the underlying claim, evidence, source, or assessment. The record
also stops the knowledge being lost when the person who had it closes the panel.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSourceIndependence(StrEnum):
    """Say whether a source stands alone or repeats another."""

    UNKNOWN = "unknown"
    INDEPENDENT = "independent"
    LIKELY_DUPLICATE = "likely_duplicate"
    DERIVATIVE = "derivative"
