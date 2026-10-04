"""Deterministic filtering: assisted answers cannot become independent mastery.

No LLM, no mock transport -- every function here is a plain string
comparison, so these tests exercise the real functions directly against
fixed inputs rather than a fixture standing in for a model.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.AssistedLearningGuard import (
    _BARE_ACKNOWLEDGEMENT_MAX_WORDS,
    _SUBSTANTIAL_REPLY_MINIMUM_CHARACTERS,
    _VERBATIM_OVERLAP_MINIMUM_CHARACTERS,
    AssistedLearningSignals,
    claims_independence,
    discloses_external_assistance,
    filter_assisted_learning_candidates,
    is_bare_acknowledgement,
)
from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCandidate import (
    LearnedMemoryCandidate,
    LearnedMemoryCandidateBatch,
)

HINT_REPLY = (
    "You can use the UNION keyword to execute an additional SELECT query and "
    "append the results from another table to the original query's results."
)
SHORT_REPLY = "Correct!"


def self_fact(
    value: str, key: str = "sql_injection_understanding"
) -> LearnedMemoryCandidate:
    return LearnedMemoryCandidate(
        memory=LearnedMemory(kind="self_fact", key=key, value=value),
        source_text="irrelevant for these tests",
    )


def preference(value: str = "Python") -> LearnedMemoryCandidate:
    return LearnedMemoryCandidate(
        memory=LearnedMemory(kind="preference", key="preferred_language", value=value),
        source_text="irrelevant for these tests",
    )


def batch_of(*candidates: LearnedMemoryCandidate) -> LearnedMemoryCandidateBatch:
    return LearnedMemoryCandidateBatch(
        source_text="irrelevant for these tests", candidates=candidates
    )


class DisclosureDetectionTests(unittest.TestCase):
    def test_chatgpt_helped_is_detected_in_english(self) -> None:
        self.assertTrue(
            discloses_external_assistance("ChatGPT helped me with this answer.")
        )

    def test_turkish_phrasing_is_detected(self) -> None:
        self.assertTrue(
            discloses_external_assistance("Bu soruda ChatGPT bana yardım etti.")
        )

    def test_generic_someone_helped_is_detected(self) -> None:
        self.assertTrue(discloses_external_assistance("Someone helped me with this."))
        self.assertTrue(discloses_external_assistance("Biri bana yardım etti."))

    def test_mentioning_an_assistant_name_alone_is_not_enough(self) -> None:
        """Naming a tool without a help marker is not itself a disclosure."""
        self.assertFalse(
            discloses_external_assistance("ChatGPT is a popular AI chatbot.")
        )

    def test_ordinary_answer_is_not_a_disclosure(self) -> None:
        self.assertFalse(
            discloses_external_assistance(
                "My answer is UNION SELECT username, password FROM users."
            )
        )

    def test_empty_and_non_string_input_is_never_a_disclosure(self) -> None:
        self.assertFalse(discloses_external_assistance(""))
        self.assertFalse(discloses_external_assistance("   "))


class IndependenceClaimTests(unittest.TestCase):
    def test_english_independence_claim_is_detected(self) -> None:
        self.assertTrue(claims_independence("I solved it independently."))
        self.assertTrue(claims_independence("I did this on my own."))

    def test_turkish_independence_claim_is_detected(self) -> None:
        self.assertTrue(claims_independence("Bunu kendi başıma çözdüm."))
        self.assertTrue(claims_independence("Yardım almadan buldum."))

    def test_an_ordinary_answer_makes_no_independence_claim(self) -> None:
        self.assertFalse(
            claims_independence("My answer is UNION SELECT username FROM users.")
        )


class BareAcknowledgementTests(unittest.TestCase):
    def test_short_acknowledgements_are_bare(self) -> None:
        for message in ("ok", "Got it.", "I understand", "tamam", "anladım", "Thanks!"):
            with self.subTest(message=message):
                self.assertTrue(is_bare_acknowledgement(message))

    def test_a_substantive_answer_starting_with_an_acknowledgement_is_not_bare(
        self,
    ) -> None:
        self.assertFalse(
            is_bare_acknowledgement(
                "Ok, here is how UNION-based SQL injection actually works in "
                "this case: the attacker appends a UNION SELECT clause."
            )
        )

    def test_empty_message_is_not_bare(self) -> None:
        self.assertFalse(is_bare_acknowledgement(""))


class FilterPreservesOrdinaryMemoriesTests(unittest.TestCase):
    """Non-self_fact candidates are never touched, under any signal."""

    def test_preference_survives_assistance_disclosure(self) -> None:
        batch = batch_of(preference())
        signals = AssistedLearningSignals.of(
            "ChatGPT helped me with this answer.",
        )

        self.assertEqual(filter_assisted_learning_candidates(batch, signals), batch)

    def test_a_batch_with_no_self_fact_is_returned_unchanged_as_the_same_object(
        self,
    ) -> None:
        batch = batch_of(preference())
        signals = AssistedLearningSignals.of("anything", recent_assistant_replies=())

        self.assertIs(filter_assisted_learning_candidates(batch, signals), batch)


class FilterDropsDisclosedAssistanceTests(unittest.TestCase):
    def test_self_fact_is_dropped_when_assistance_is_disclosed(self) -> None:
        batch = batch_of(self_fact("User understands UNION-based SQL injection."))
        signals = AssistedLearningSignals.of("ChatGPT helped me with this answer.")

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, ())

    def test_mixed_batch_keeps_preference_but_drops_self_fact(self) -> None:
        kept_preference = preference()
        batch = batch_of(
            kept_preference,
            self_fact("User understands SQL injection independently."),
        )
        signals = AssistedLearningSignals.of("Someone helped me with this.")

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, (kept_preference,))


class FilterDropsIndependenceClaimAfterSubstantialHintTests(unittest.TestCase):
    def test_independence_claim_right_after_a_real_hint_is_dropped(self) -> None:
        batch = batch_of(
            self_fact("User independently solved the SQL injection challenge.")
        )
        signals = AssistedLearningSignals.of(
            "My answer is UNION SELECT; I solved it independently.",
            recent_assistant_replies=(HINT_REPLY,),
        )

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, ())

    def test_independence_claim_after_only_a_short_acknowledgement_is_kept(
        self,
    ) -> None:
        """A bare prior "Correct!" is not a hint; an independence claim stands."""
        candidate = self_fact("User independently solved a new SQL injection task.")
        batch = batch_of(candidate)
        signals = AssistedLearningSignals.of(
            "I solved the new one independently.",
            recent_assistant_replies=(SHORT_REPLY,),
        )

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, (candidate,))

    def test_independence_claim_with_no_recent_reply_at_all_is_kept(self) -> None:
        """The required negative scenario: no hint was ever given."""
        candidate = self_fact("User independently solved the SQL injection task.")
        batch = batch_of(candidate)
        signals = AssistedLearningSignals.of(
            "I solved it independently.",
            recent_assistant_replies=(),
        )

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, (candidate,))

    def test_a_correct_answer_with_no_independence_claim_is_not_penalized(self) -> None:
        """Requirement: a genuinely new, unaided answer must not be misclassified.

        No independence claim is made at all here, so the mere existence of a
        substantial recent reply (about something else entirely) must not by
        itself cause a self_fact to be dropped.
        """
        candidate = self_fact("User correctly explained reflected XSS.")
        batch = batch_of(candidate)
        signals = AssistedLearningSignals.of(
            "Reflected XSS happens when unsanitized input is echoed back.",
            recent_assistant_replies=(HINT_REPLY,),
        )

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, (candidate,))


class FilterDropsVerbatimRestatementTests(unittest.TestCase):
    def test_a_claim_quoting_a_long_run_of_the_hint_is_dropped(self) -> None:
        candidate = self_fact(
            "User independently explained: use the UNION keyword to execute "
            "an additional SELECT query and append the results from another "
            "table to the original query's results."
        )
        batch = batch_of(candidate)
        signals = AssistedLearningSignals.of(
            "My answer uses UNION SELECT.",
            recent_assistant_replies=(HINT_REPLY,),
        )

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, ())

    def test_a_claim_with_no_meaningful_overlap_with_the_hint_is_kept(self) -> None:
        candidate = self_fact(
            "User correctly explained blind boolean-based SQL injection using "
            "true/false response timing, a different technique from the hint."
        )
        batch = batch_of(candidate)
        signals = AssistedLearningSignals.of(
            "My answer uses a boolean-based blind technique.",
            recent_assistant_replies=(HINT_REPLY,),
        )

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, (candidate,))


class FilterDropsBareAcknowledgementTests(unittest.TestCase):
    def test_a_self_fact_extracted_from_a_bare_ok_is_dropped(self) -> None:
        """Agreement alone is never evidence of independent mastery."""
        batch = batch_of(self_fact("User understands SQL injection."))
        signals = AssistedLearningSignals.of("Tamam, anladım.")

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, ())


_UNIQUE_CHARACTERS = "abcdefghijklmnopqrstuvwxyz0123456789"


class VerbatimOverlapThresholdTests(unittest.TestCase):
    """Boundary coverage for `_VERBATIM_OVERLAP_MINIMUM_CHARACTERS`.

    Built from a run of distinct characters (never a repeated one), so the
    longest-common-substring length is exactly the shared prefix length,
    with no risk of an accidental longer match elsewhere in the text.
    """

    def test_a_shared_run_one_below_the_threshold_is_kept(self) -> None:
        # The character immediately before and after the shared run differs
        # between the two strings ("#"/"!" vs "@"/"?"), so the match cannot
        # extend past the shared run itself via an incidental extra space or
        # word boundary -- a prior version of this fixture accidentally
        # shared a boundary space on both sides, silently inflating the
        # match by one and making this exact test fail.
        shared = _UNIQUE_CHARACTERS[: _VERBATIM_OVERLAP_MINIMUM_CHARACTERS - 1]
        reply = f"Hint#{shared}!"
        candidate = self_fact(f"Done@{shared}?")
        batch = batch_of(candidate)
        signals = AssistedLearningSignals.of(
            "My answer explains it fully.",
            recent_assistant_replies=(reply,),
        )

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, (candidate,))

    def test_a_shared_run_at_exactly_the_threshold_is_dropped(self) -> None:
        shared = _UNIQUE_CHARACTERS[:_VERBATIM_OVERLAP_MINIMUM_CHARACTERS]
        reply = f"Hint#{shared}!"
        candidate = self_fact(f"Done@{shared}?")
        batch = batch_of(candidate)
        signals = AssistedLearningSignals.of(
            "My answer explains it fully.",
            recent_assistant_replies=(reply,),
        )

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, ())


class SubstantialReplyThresholdTests(unittest.TestCase):
    """Boundary coverage for `_SUBSTANTIAL_REPLY_MINIMUM_CHARACTERS`."""

    def test_an_independence_claim_after_a_reply_one_below_threshold_is_kept(
        self,
    ) -> None:
        candidate = self_fact("User independently solved a new task.")
        batch = batch_of(candidate)
        signals = AssistedLearningSignals.of(
            "I solved it independently.",
            recent_assistant_replies=(
                "x" * (_SUBSTANTIAL_REPLY_MINIMUM_CHARACTERS - 1),
            ),
        )

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, (candidate,))

    def test_an_independence_claim_after_a_reply_at_exactly_threshold_is_dropped(
        self,
    ) -> None:
        candidate = self_fact("User independently solved a new task.")
        batch = batch_of(candidate)
        signals = AssistedLearningSignals.of(
            "I solved it independently.",
            recent_assistant_replies=("x" * _SUBSTANTIAL_REPLY_MINIMUM_CHARACTERS,),
        )

        result = filter_assisted_learning_candidates(batch, signals)

        self.assertEqual(result.candidates, ())


class BareAcknowledgementWordCountBoundaryTests(unittest.TestCase):
    """Boundary coverage for `_BARE_ACKNOWLEDGEMENT_MAX_WORDS`."""

    def test_exactly_the_maximum_word_count_of_ack_words_is_bare(self) -> None:
        words = ["ok", "got", "it", "i", "see"][:_BARE_ACKNOWLEDGEMENT_MAX_WORDS]
        self.assertEqual(len(words), _BARE_ACKNOWLEDGEMENT_MAX_WORDS)

        self.assertTrue(is_bare_acknowledgement(" ".join(words)))

    def test_one_more_than_the_maximum_is_not_bare_even_if_all_are_ack_words(
        self,
    ) -> None:
        words = ["ok", "got", "it", "i", "see", "now"][
            : _BARE_ACKNOWLEDGEMENT_MAX_WORDS + 1
        ]
        self.assertEqual(len(words), _BARE_ACKNOWLEDGEMENT_MAX_WORDS + 1)

        self.assertFalse(is_bare_acknowledgement(" ".join(words)))


if __name__ == "__main__":
    unittest.main()
