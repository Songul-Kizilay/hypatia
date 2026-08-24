"""Which language to answer a deterministic response in.

Hypatia's honesty responses are composed in code, not by a model, which is what
makes them trustworthy — a model asked to phrase "I did not research this" can
phrase it into something else. The cost is that they arrive in whatever language
the author wrote, and a Turkish speaker asking a Turkish question got a wall of
English that read like a developer diagnostic.

So the language is detected and the wording is looked up. No language is
privileged in the architecture: detection is a table of hints and the phrasing is
a table of translations, so adding a language is data rather than code, and
English is the fallback only because it is what the untranslated strings already
are.

Detection is deliberately crude. It decides which of a few fixed sentences to
show, so a wrong guess costs the reader a translation, never a change of
meaning — the sentences say the same thing in every language, and a language with
no entry falls back rather than being approximated.

The word hints are restricted to tokens that do not occur in the other
languages. An earlier version listed "site" and "var", which turned an English
question containing either word into a Turkish answer — a wrong guess is cheap,
but a hint that fires on ordinary English is not a hint.
"""

from __future__ import annotations

from enum import StrEnum

MIN_DETECTION_CHARACTERS = 2


class ResponseLanguage(StrEnum):
    """A language a deterministic response can be rendered in."""

    ENGLISH = "en"
    TURKISH = "tr"

    @property
    def is_fallback(self) -> bool:
        """Return whether this is the language used when detection fails."""
        return self is ResponseLanguage.ENGLISH


_TURKISH_CHARACTERS = frozenset("çğıöşüÇĞİÖŞÜ")

_HINTS: dict[ResponseLanguage, frozenset[str]] = {
    ResponseLanguage.TURKISH: frozenset(
        {
            "bir",
            "icin",
            "musun",
            "misin",
            "nedir",
            "nasil",
            "bul",
            "kaynak",
            "kaynaklari",
            "haber",
            "haberler",
            "guncel",
            "bugun",
            "siteye",
            "sayfayi",
            "erisebiliyo",
            "erisebilir",
            "arastir",
            "arastirma",
            "kanit",
            "kanitlari",
            "yapabilir",
            "lutfen",
            "tesekkur",
            "yayimlanan",
            "yayimlanmis",
        }
    ),
}


def detect_response_language(message: str) -> ResponseLanguage:
    """Return the language to answer in, falling back to English.

    A single distinctive character is enough on its own: Turkish dotted and
    dotless letters do not appear in English, and requiring a word match as well
    would fail on the short questions people actually type.
    """
    if not isinstance(message, str) or len(message.strip()) < MIN_DETECTION_CHARACTERS:
        return ResponseLanguage.ENGLISH
    if any(character in _TURKISH_CHARACTERS for character in message):
        return ResponseLanguage.TURKISH
    words = {word.strip(".,;:!?()[]\"'").casefold() for word in message.split()}
    for language, hints in _HINTS.items():
        if words & hints:
            return language
    return ResponseLanguage.ENGLISH
