"""Deterministic backstop: assisted answers cannot become independent mastery.

`LLMLearnedMemoryCandidateExtractor` now receives bounded recent-session
context and an instruction not to credit assistance it sees there -- but an
instruction is something a model can fail to follow, and this file's whole
purpose is to not depend on that happening. Every check here is a plain
string comparison over already-known, already-bounded text: no model call,
no inference, no "probably". A candidate this module drops stays dropped
regardless of what the extractor returned; nothing here can add a candidate
or widen what gets kept.

Scope is deliberately narrow. Only `self_fact` candidates -- the kind that
can state something like "the user understands/solved/mastered X" -- are
ever filtered. `user_fact`, `preference`, `project_fact` and `goal`
candidates (favourite language, a project detail, an intention) have nothing
to do with demonstrated understanding and are never touched, so an ordinary
session keeps learning ordinary things about the user exactly as before.

Each rule is independently sufficient to drop a candidate, and failing
closed is the point: if a rule's evidence is ambiguous, the candidate is
dropped rather than kept. A dropped self_fact is not an error and is not
reported to the user -- the conversational reply (built separately,
upstream) still answers normally; this module only decides what is durably
remembered as demonstrated understanding.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from memory.LearnedMemoryCandidate import (
    LearnedMemoryCandidate,
    LearnedMemoryCandidateBatch,
)

#: Kinds a mastery/understanding claim could plausibly take. Everything else
#: (preferences, project facts, user facts, goals) is never filtered here.
_MASTERY_CLAIM_KIND = "self_fact"

#: A candidate `value` sharing a verbatim run at least this long with a
#: recent Hypatia reply is read as restating that reply, not demonstrating
#: independent understanding of it. Short shared phrases ("SQL injection",
#: "the database") are expected and common even in genuinely independent
#: answers, so the threshold is set above ordinary topic-name length.
_VERBATIM_OVERLAP_MINIMUM_CHARACTERS = 28

#: A recent reply shorter than this reads as an acknowledgement ("Correct!",
#: "Doğru.") rather than a hint or explanation substantial enough to make a
#: same-turn independence claim suspect.
_SUBSTANTIAL_REPLY_MINIMUM_CHARACTERS = 120

#: Bound comparisons against pathologically long stored text; recent replies
#: are conversational turns, never multi-page documents.
_MAX_COMPARISON_CHARACTERS = 4_000

_ASSISTANT_NAMES = (
    "chatgpt",
    "gpt-4",
    "gpt4",
    "openai",
    "claude",
    "gemini",
    "copilot",
    "bard",
    "bing",
    "stackoverflow",
    "stack overflow",
)
_HELP_MARKERS_EN = (
    "helped",
    "help",
    "gave me the answer",
    "gave me a hint",
    "told me the answer",
    "solved it for me",
    "wrote it for me",
)
_HELP_MARKERS_TR = (
    "yardım etti",
    "yardımıyla",
    "yardımı ile",
    "cevabı verdi",
    "cevabını verdi",
    "ipucu verdi",
    "çözdü",
    "yazdı",
)
_GENERIC_DISCLOSURE = (
    "someone helped me",
    "my friend helped",
    "with help from",
    "with external help",
    "i got help",
    "i had help",
    "i used help",
    "googled the answer",
    "looked up the answer",
    "biri bana yardım etti",
    "arkadaşım yardım etti",
    "yardım aldım",
    "dışarıdan yardım aldım",
    "bana yardım etti",
    "cevabı google'dan buldum",
    "cevabı internetten buldum",
)

_INDEPENDENCE_CLAIM_PHRASES = (
    "independently",
    "on my own",
    "by myself",
    "without help",
    "without any help",
    "unaided",
    "no help",
    "kendi başıma",
    "kendim çözdüm",
    "bağımsız olarak",
    "bağımsız şekilde",
    "yardım almadan",
    "yardımsız",
)

#: Word-level, not phrase-level, so "I understand now" and "I understand"
#: are recognized the same way without enumerating every combination. A
#: message counts as bare acknowledgement only when *every* one of its
#: (bounded-count) words is drawn from this set -- a single real-content
#: word (a technique name, a tool, a technical term) takes it out of scope.
_BARE_ACKNOWLEDGEMENT_WORDS = frozenset(
    {
        "ok",
        "okay",
        "got",
        "it",
        "i",
        "get",
        "see",
        "understand",
        "understood",
        "that",
        "makes",
        "sense",
        "now",
        "thanks",
        "thank",
        "you",
        "tamam",
        "anladım",
        "anladim",
        "anlaşıldı",
        "anlasildi",
        "mantıklı",
        "mantikli",
        "evet",
        "peki",
    }
)
_BARE_ACKNOWLEDGEMENT_TRIM = ".,!?;:\"' \t\n"
_BARE_ACKNOWLEDGEMENT_MAX_WORDS = 5


def _fold(text: str) -> str:
    return " ".join(text.casefold().split())[:_MAX_COMPARISON_CHARACTERS]


def discloses_external_assistance(message: str) -> bool:
    """Return whether the user's own message names outside help for this answer."""
    if not isinstance(message, str) or not message.strip():
        return False
    folded = _fold(message)
    for name in _ASSISTANT_NAMES:
        if name not in folded:
            continue
        if any(marker in folded for marker in _HELP_MARKERS_EN + _HELP_MARKERS_TR):
            return True
    return any(phrase in folded for phrase in _GENERIC_DISCLOSURE)


def claims_independence(message: str) -> bool:
    """Return whether the user explicitly asserts they were unaided."""
    if not isinstance(message, str) or not message.strip():
        return False
    folded = _fold(message)
    return any(phrase in folded for phrase in _INDEPENDENCE_CLAIM_PHRASES)


def is_bare_acknowledgement(message: str) -> bool:
    """Return whether the message is just agreement, with no content of its own.

    Checked word-by-word against a closed vocabulary rather than matching a
    phrase list, so "I understand", "I understand now" and "Tamam, anladım"
    are all recognized without enumerating every combination -- but a single
    real-content word (a technique name, a tool, a technical term) is
    enough to take a message out of scope, so a substantive answer that
    happens to start with "ok, here is how UNION-based injection works..."
    is never mistaken for one.
    """
    if not isinstance(message, str):
        return False
    translated = message.casefold().translate(
        {ord(character): " " for character in _BARE_ACKNOWLEDGEMENT_TRIM}
    )
    words = translated.split()
    if not words or len(words) > _BARE_ACKNOWLEDGEMENT_MAX_WORDS:
        return False
    return all(word in _BARE_ACKNOWLEDGEMENT_WORDS for word in words)


def _is_substantial_reply(reply: str) -> bool:
    return len(reply.strip()) >= _SUBSTANTIAL_REPLY_MINIMUM_CHARACTERS


def _shares_verbatim_phrase(value: str, reply: str) -> bool:
    """Return whether `value` restates a long run of a recent Hypatia reply."""
    left, right = _fold(value), _fold(reply)
    if not left or not right:
        return False
    match = SequenceMatcher(None, left, right).find_longest_match(
        0, len(left), 0, len(right)
    )
    return match.size >= _VERBATIM_OVERLAP_MINIMUM_CHARACTERS


@dataclass(frozen=True, slots=True)
class AssistedLearningSignals:
    """Deterministic, already-computed facts this turn's filtering needs.

    Computed once per turn by the caller (which has the conversation state)
    and passed in, so this module stays pure text-comparison with no access
    to memory, sessions, or the clock.
    """

    assistance_disclosed: bool
    independence_claimed: bool
    bare_acknowledgement: bool
    recent_assistant_replies: tuple[str, ...] = ()

    @classmethod
    def of(
        cls,
        current_user_message: str,
        recent_assistant_replies: tuple[str, ...] = (),
    ) -> AssistedLearningSignals:
        """Precompute every signal from the current message, once.

        Nothing downstream re-reads `current_user_message` or any batch's
        `source_text` to re-derive these facts -- a candidate's own
        `source_text` is deliberately never consulted here, so filtering
        behaves the same regardless of what a caller happened to set it to.
        """
        return cls(
            assistance_disclosed=discloses_external_assistance(current_user_message),
            independence_claimed=claims_independence(current_user_message),
            bare_acknowledgement=is_bare_acknowledgement(current_user_message),
            recent_assistant_replies=recent_assistant_replies,
        )


def _is_disallowed_mastery_claim(
    candidate: LearnedMemoryCandidate,
    signals: AssistedLearningSignals,
) -> bool:
    if candidate.memory.kind != _MASTERY_CLAIM_KIND:
        return False
    if signals.assistance_disclosed:
        return True
    if signals.bare_acknowledgement:
        return True
    if signals.independence_claimed and any(
        _is_substantial_reply(reply) for reply in signals.recent_assistant_replies
    ):
        return True
    return any(
        _shares_verbatim_phrase(candidate.memory.value, reply)
        for reply in signals.recent_assistant_replies
    )


def filter_assisted_learning_candidates(
    batch: LearnedMemoryCandidateBatch,
    signals: AssistedLearningSignals,
) -> LearnedMemoryCandidateBatch:
    """Return `batch` with any disallowed mastery-claim candidate removed.

    Every non-`self_fact` candidate always survives unchanged; only
    `self_fact` candidates are ever evaluated, and only against the rules
    above. A batch with nothing to drop is returned as-is (same candidates,
    same order), so this is a safe no-op on the common, unassisted turn.
    """
    if not any(c.memory.kind == _MASTERY_CLAIM_KIND for c in batch.candidates):
        return batch
    kept = tuple(
        candidate
        for candidate in batch.candidates
        if not _is_disallowed_mastery_claim(candidate, signals)
    )
    if kept == batch.candidates:
        return batch
    return LearnedMemoryCandidateBatch(source_text=batch.source_text, candidates=kept)
