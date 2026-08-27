"""Tests for the relevance score itself: its weights, parts, bands, and bounds."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from core.Exceptions import ResearchError
from research.ResearchRelevanceCategory import ResearchRelevanceCategory
from research.ResearchRelevanceComponent import ResearchRelevanceComponent
from research.ResearchRelevanceReason import ResearchRelevanceReason
from research.ResearchRelevanceWeights import (
    DEFAULT_RELEVANCE_WEIGHTS,
    ResearchRelevanceWeights,
)
from research.ResearchSourceRelevance import (
    UNRANKED_RELEVANCE,
    ResearchSourceRelevance,
)


def _component(
    name: str = "title_coverage",
    value: float = 1.0,
    weight: float = 40.0,
    applicable: bool = True,
) -> ResearchRelevanceComponent:
    return ResearchRelevanceComponent(
        name=name, value=value, weight=weight, applicable=applicable
    )


class ResearchRelevanceWeightTests(unittest.TestCase):
    def test_defaults_make_an_identifier_worth_more_than_a_common_word(self) -> None:
        """The one judgement the numbers encode, asserted rather than assumed."""
        weights = DEFAULT_RELEVANCE_WEIGHTS

        self.assertGreater(weights.technical_term_specificity, 1.0)
        self.assertGreater(weights.title_coverage, weights.phrase_adjacency)
        self.assertGreater(weights.phrase_adjacency, weights.venue_terms)

    def test_thresholds_must_descend(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchRelevanceWeights(strong_score=30, moderate_score=50, weak_score=10)

    def test_a_weight_outside_its_range_is_refused(self) -> None:
        for kwargs in (
            {"title_coverage": -1.0},
            {"recency": 101.0},
            {"venue_terms": "heavy"},
            {"technical_term_specificity": 0.5},
            {"phrase_adjacency": True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ResearchError):
                    ResearchRelevanceWeights(**kwargs)  # type: ignore[arg-type]

    def test_title_coverage_must_carry_weight(self) -> None:
        """It is the only component every record can answer."""
        with self.assertRaises(ResearchError):
            ResearchRelevanceWeights(title_coverage=0.0)

    def test_a_threshold_outside_zero_to_one_hundred_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchRelevanceWeights(strong_score=140)

    def test_weights_are_frozen_against_being_retuned_in_place(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            DEFAULT_RELEVANCE_WEIGHTS.title_coverage = 1.0  # type: ignore[misc]

    def test_an_unknown_component_has_no_weight_to_look_up(self) -> None:
        with self.assertRaises(ResearchError):
            DEFAULT_RELEVANCE_WEIGHTS.weight_of("reputation")
        with self.assertRaises(ResearchError):
            DEFAULT_RELEVANCE_WEIGHTS.weight_of("strong_score")


class ResearchRelevanceComponentTests(unittest.TestCase):
    def test_contribution_is_value_times_weight(self) -> None:
        self.assertAlmostEqual(_component(value=0.5, weight=40.0).contribution, 20.0)

    def test_an_inapplicable_component_contributes_nothing_and_offers_no_weight(
        self,
    ) -> None:
        component = _component(value=0.0, weight=30.0, applicable=False)

        self.assertEqual(component.contribution, 0.0)
        self.assertEqual(component.available_weight, 0.0)

    def test_an_inapplicable_component_cannot_smuggle_in_a_value(self) -> None:
        with self.assertRaises(ResearchError):
            _component(value=0.9, applicable=False)

    def test_a_component_value_must_be_a_fraction(self) -> None:
        for value in (-0.1, 1.5, True, "half"):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    _component(value=value)  # type: ignore[arg-type]

    def test_a_component_needs_a_bounded_name(self) -> None:
        for name in ("", "   ", "x" * 200, 7):
            with self.subTest(name=name):
                with self.assertRaises(ResearchError):
                    _component(name=name)  # type: ignore[arg-type]


class ResearchSourceRelevanceTests(unittest.TestCase):
    def test_score_is_taken_over_the_weight_that_actually_applied(self) -> None:
        """Missing metadata reads as unknown, not as a fault."""
        full_match_without_venue = ResearchSourceRelevance.of(
            (
                _component(value=1.0, weight=40.0),
                _component(name="venue_terms", value=0.0, weight=5.0, applicable=False),
            ),
            (),
        )

        self.assertEqual(full_match_without_venue.score, 100)

    def test_a_present_but_unmatched_component_does_lower_the_score(self) -> None:
        scored = ResearchSourceRelevance.of(
            (
                _component(value=1.0, weight=40.0),
                _component(name="venue_terms", value=0.0, weight=40.0),
            ),
            (),
        )

        self.assertEqual(scored.score, 50)

    def test_bands_follow_the_configured_thresholds(self) -> None:
        weights = DEFAULT_RELEVANCE_WEIGHTS
        for value, expected in (
            (1.0, ResearchRelevanceCategory.STRONG),
            (weights.moderate_score / 100.0, ResearchRelevanceCategory.MODERATE),
            (weights.weak_score / 100.0, ResearchRelevanceCategory.WEAK),
            (0.0, ResearchRelevanceCategory.UNRELATED),
        ):
            with self.subTest(value=value):
                relevance = ResearchSourceRelevance.of(
                    (_component(value=value),), (), weights
                )
                self.assertEqual(relevance.category, expected)

    def test_nothing_measurable_scores_zero_rather_than_dividing_by_zero(self) -> None:
        relevance = ResearchSourceRelevance.of(
            (_component(value=0.0, applicable=False),), ()
        )

        self.assertEqual(relevance.score, 0)

    def test_the_parts_survive_alongside_the_total(self) -> None:
        relevance = ResearchSourceRelevance.of(
            (
                _component(value=0.5),
                _component(name="recency", value=1.0, weight=10.0),
            ),
            (ResearchRelevanceReason.SOME_QUERY_TERMS_IN_TITLE,),
        )

        self.assertIsNotNone(relevance.component("recency"))
        self.assertIsNone(relevance.component("reputation"))
        self.assertEqual(
            relevance.reasons, (ResearchRelevanceReason.SOME_QUERY_TERMS_IN_TITLE,)
        )

    def test_a_component_cannot_be_measured_twice(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSourceRelevance.of((_component(), _component()), ())

    def test_a_score_must_keep_the_components_that_produced_it(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSourceRelevance.of((), ())

    def test_reasons_must_be_known_codes_and_never_prose(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSourceRelevance(
                score=50,
                category=ResearchRelevanceCategory.MODERATE,
                components=(_component(),),
                reasons=("it looked relevant",),  # type: ignore[arg-type]
            )

    def test_a_reason_is_not_repeated(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSourceRelevance(
                score=50,
                category=ResearchRelevanceCategory.MODERATE,
                components=(_component(),),
                reasons=(
                    ResearchRelevanceReason.QUERY_PHRASE_IN_TITLE,
                    ResearchRelevanceReason.QUERY_PHRASE_IN_TITLE,
                ),
            )

    def test_a_score_stays_between_zero_and_one_hundred(self) -> None:
        for score in (-1, 101, True, 5.5):
            with self.subTest(score=score):
                with self.assertRaises(ResearchError):
                    ResearchSourceRelevance(
                        score=score,  # type: ignore[arg-type]
                        category=ResearchRelevanceCategory.WEAK,
                        components=(_component(),),
                        reasons=(),
                    )

    def test_not_compared_is_its_own_answer_rather_than_unrelated(self) -> None:
        self.assertEqual(
            UNRANKED_RELEVANCE.category, ResearchRelevanceCategory.UNMEASURED
        )
        self.assertEqual(UNRANKED_RELEVANCE.score, 0)
        self.assertEqual(UNRANKED_RELEVANCE.reasons, ())


if __name__ == "__main__":
    unittest.main()
