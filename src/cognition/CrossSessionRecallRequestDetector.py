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
)


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
