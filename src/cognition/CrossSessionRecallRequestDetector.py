"""Recognise ordinary chat asking to recall or continue a *different* session.

Detection is a fixed phrase table, not a model and not a fuzzy score, mirroring
`LiveInformationRequestDetector`. That matters for the same two reasons: the
result must be reproducible in a test, and it must never become a way for
arbitrary text to talk Hypatia into a capability. This detector grants
nothing. Its entire output is one boolean signal that makes Hypatia offer
bounded, already-retrieved, already-ranked reference context from other
sessions for that turn -- never an authority action, never a write, never a
new capability, and never a change to the ordinary same-session conversation
history.

Because the only consequence of a match is offering reference context the
model is explicitly told to treat as non-authoritative (see
`CrossSessionRecallContext`), the safe error direction is to over-match rather
than under-match. Phrases are still specific enough that ordinary conversation
does not trip them: the table asks for explicit continuation/recall framing
such as "let's continue" or "where did we leave off", never a bare topic
mention like "SQL injection" on its own.

Turkish and English are both matched because the runtime is used in both, but
neither language is privileged: adding a language means adding phrases, and no
behaviour anywhere is conditioned on which language matched. This milestone
only needs one boolean signal, not a taxonomy, so unlike
`LiveInformationRequestKind` there is no enum/kind hierarchy here.
"""

from __future__ import annotations

import re

MAX_INSPECTED_CHARACTERS = 4000

RECALL_PHRASES = (
    "continue the lesson",
    "continue our lesson",
    "continue with the lesson",
    "let's continue",
    "lets continue",
    "let us continue",
    "where did we leave off",
    "where we left off",
    "what was my last question",
    "what was my last question about",
    "what did we discuss last time",
    "what did we discuss before",
    "what did we discuss in our last session",
    "last time we",
    "last session we",
    "previous session",
    "earlier session",
    "in our previous session",
    "in our earlier session",
    "derse devam",
    "derse devam edelim",
    "önceki oturum",
    "onceki oturum",
    "geçen oturumda",
    "gecen oturumda",
    "nerede kalmıştık",
    "nerede kalmistik",
    "son sorum neydi",
    "ne kalmıştı",
    "ne kalmisti",
    "hangi soruda kalmıştık",
    "hangi soruda kalmistik",
    "dersine devam",
    "konusuna devam",
    "konusuna dön",
    "konusuna don",
)

#: Deliberately a fixed, bounded list -- the same reproducible, test-covered
#: discipline as `RECALL_PHRASES` above, not a fuzzy or statistical filter.
#: Extending coverage means adding a word here, verified by a test, exactly
#: like adding a phrase to a detector table elsewhere in this codebase; it
#: never becomes partial-match, edit-distance, or model-scored stripping.
#: Grammatical scaffolding and instructional verbs ("bul", "söyle", "ve",
#: "find", "tell") are stripped because they routinely survive into the
#: term list from a natural recall sentence without naming any topic, and
#: `CognitiveEngine._cross_session_lexical_recall_records` requires every
#: surviving term to match the same candidate record -- a single leaked
#: boilerplate word is therefore enough to hide a real, relevant record.
_QUERY_STOP_WORDS = frozenset(
    "a an the i we you our my me it is was were about in on from to of and "
    "can could please let lets s continue lesson lessons session previous "
    "last earlier time what where did do leave left off question before "
    "hey so exactly yesterday with that this discuss talked explained "
    "find tell bring fetch say says said brought told found fetched "
    "old record records which id "
    "derse dersine ders oturum oturumda önceki onceki geçen gecen devam "
    "edelim mi ne neydi nerede hangi soruda son sorum kalmıştık kalmistik "
    "kalmıştı kalmisti öğrendik ogrendik konuşmuştuk konusmustuk "
    "ve veya ile icin için lütfen lutfen bana bize "
    "bul bulabilir bulur bulunuz bulup "
    "getir getirir getirdi getirdin getirdiniz getirdiğini getirdigini "
    "söyle soyle söyler soyler söyledi soyledi "
    "anlat anlatir anlatır aktar aktarir aktarır "
    "konusunda hakkında hakkinda eski "
    "kayıt kayit kayıtlar kayitlar kayıtlardan kayitlardan "
    "kayıtlarından kayitlarindan "
    "den dan ten tan".split()
)


def recall_query_terms(message: str) -> tuple[str, ...]:
    """Bounded lexical topics, excluding the recall request's boilerplate."""
    normalized = message[:MAX_INSPECTED_CHARACTERS].replace("İ", "i").casefold()
    return tuple(
        dict.fromkeys(
            token
            for token in re.findall(r"[^\W_]+", normalized)
            if len(token) > 1 and token not in _QUERY_STOP_WORDS
        )
    )[:12]


class CrossSessionRecallRequestDetector:
    """Classify one message against a fixed table, granting nothing."""

    def detect(self, message: str) -> bool:
        """Return whether the message asks to recall or continue another session."""
        if not isinstance(message, str) or not message.strip():
            return False
        bounded = message[:MAX_INSPECTED_CHARACTERS]
        forms = _normalized_forms(bounded)
        return any(phrase in form for form in forms for phrase in RECALL_PHRASES)


def _normalized_forms(message: str) -> tuple[str, ...]:
    """Return casefolded variants so Turkish dotted capitals also match.

    Turkish maps I and İ differently from English, and a single casefold cannot
    satisfy both. Comparing against both variants keeps the table language
    neutral instead of forcing one locale onto the other.
    """
    plain = message.casefold()
    turkish = message.replace("İ", "i").replace("I", "ı").casefold()
    if turkish == plain:
        return (plain,)
    return (plain, turkish)
