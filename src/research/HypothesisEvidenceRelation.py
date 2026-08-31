"""The three things a person can say about evidence and a hypothesis.

Closed, because a relationship somebody can invent by typing a new string is a
relationship nothing downstream can be written against. These three already
existed as separate collections on the hypothesis; naming them lets one
operation speak about any of them without a fourth appearing by accident.

They are genuinely different statements and none implies another. Evidence can
support a hypothesis without touching the question it was built around, address
that question without the operator having said which way it cuts, and oppose it
while addressing it. Retracting one says nothing about the other two.
"""

from __future__ import annotations

from enum import StrEnum


class HypothesisEvidenceRelation(StrEnum):
    """Name one bounded thing evidence can be said to do to a hypothesis."""

    SUPPORTS = "supports"
    OPPOSES = "opposes"
    ADDRESSES_DISCRIMINATING_TEST = "addresses_discriminating_test"

    @property
    def collection_name(self) -> str:
        """Return the hypothesis field holding this relation's current members.

        The collections are the current projection: an identifier is in one
        exactly while that relation is active, and retraction removes it from
        there while the retraction record keeps the history. Naming the field
        here keeps that mapping in one place rather than in every caller.
        """
        return _COLLECTIONS[self]

    @property
    def label(self) -> str:
        """Return the wording an operator sees for this relation."""
        return _LABELS[self]


_COLLECTIONS: dict[HypothesisEvidenceRelation, str] = {
    HypothesisEvidenceRelation.SUPPORTS: "supporting_evidence_ids",
    HypothesisEvidenceRelation.OPPOSES: "opposing_evidence_ids",
    HypothesisEvidenceRelation.ADDRESSES_DISCRIMINATING_TEST: (
        "discriminating_test_evidence_ids"
    ),
}

_LABELS: dict[HypothesisEvidenceRelation, str] = {
    HypothesisEvidenceRelation.SUPPORTS: "supports this hypothesis",
    HypothesisEvidenceRelation.OPPOSES: "opposes this hypothesis",
    HypothesisEvidenceRelation.ADDRESSES_DISCRIMINATING_TEST: (
        "addresses the discriminating test"
    ),
}


def relation_of(value: object) -> HypothesisEvidenceRelation:
    """Return the named relation, refusing anything outside the vocabulary."""
    if isinstance(value, HypothesisEvidenceRelation):
        return value
    if isinstance(value, str):
        for relation in HypothesisEvidenceRelation:
            if relation.value == value.strip().casefold():
                return relation
    raise ValueError("That is not a hypothesis evidence relation.")
