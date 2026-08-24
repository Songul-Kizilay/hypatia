"""Recognise requests ordinary chat must not answer as if research happened.

Detection is a fixed phrase table, not a model and not a fuzzy score. That
matters twice over: the result must be reproducible in a test, and it must never
become a way for arbitrary text to talk Hypatia into a capability. This detector
grants nothing. Its entire output is a category that makes Hypatia describe what
it did not do.

Because the only consequence of a match is an honest disclaimer, the safe error
direction is to over-match rather than under-match. Phrases are still specific
enough that ordinary conversation does not trip them: the table asks for
explicit markers such as "search the internet" or "kaynaklarını ver", never a
bare noun like "news" or "haber".

Turkish and English are both matched because the runtime is used in both, but
neither language is privileged: adding a language means adding phrases, and no
behaviour anywhere is conditioned on which language matched.

One rule needs two signals rather than one. A message is treated as asking about
a specific page only when it contains a URL *and* asks about reaching it, because
a pasted link is usually context for a question rather than a request to open
anything. Matching on the URL alone would take over every turn that mentioned
one.
"""

from __future__ import annotations

import re

from cognition.LiveInformationRequestKind import LiveInformationRequestKind

MAX_INSPECTED_CHARACTERS = 4000

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

URL_ACCESS_PHRASES = (
    "can you access",
    "can you open",
    "can you read",
    "can you reach",
    "can you visit",
    "can you fetch",
    "are you able to access",
    "do you have access to",
    "open this link",
    "open this url",
    "read this page",
    "check this page",
    "check this link",
    "fetch this",
    "erisebiliyo",
    "erişebiliyo",
    "erisebilir",
    "erişebilir",
    "erisim var",
    "erişim var",
    "acabiliyo",
    "açabiliyo",
    "acabilir",
    "açabilir",
    "okuyabiliyo",
    "okuyabilir",
    "bakabilir",
    "girebiliyo",
    "girebilir",
    "ulasabiliyo",
    "ulaşabiliyo",
    "ulasabilir",
    "ulaşabilir",
    "inceleyebilir",
)

EVIDENCE_PROVENANCE_PHRASES = (
    "what evidence did you",
    "which evidence did you",
    "evidence did you collect",
    "evidence have you collected",
    "what did you verify",
    "how did you verify",
    "did you actually research",
    "what sources did you",
    "which sources did you",
    "where did you get these sources",
    "hangi kanitlari",
    "hangi kanıtları",
    "kanit topladin",
    "kanıt topladın",
    "kanitlari topladin",
    "kanıtları topladın",
    "nasil dogruladin",
    "nasıl doğruladın",
    "hangi kaynaklari",
    "hangi kaynakları",
    "bu kaynaklari nereden",
    "bu kaynakları nereden",
)

CURRENT_EVENTS_PHRASES = (
    "latest news",
    "today's news",
    "todays news",
    "current news",
    "breaking news",
    "recent news",
    "news today",
    "in the news today",
    "what happened today",
    "son dakika",
    "bugunku haber",
    "bugünkü haber",
    "guncel haber",
    "güncel haber",
    "son haberler",
    "haber bul",
    "haberi bul",
    "haberleri bul",
    "bugun yayimlanan",
    "bugün yayımlanan",
    "guncel gelismeler",
    "güncel gelişmeler",
)

ACADEMIC_SOURCE_PHRASES = (
    "academic sources",
    "academic source",
    "scholarly articles",
    "peer-reviewed papers",
    "peer reviewed papers",
    "recent papers",
    "recent publications",
    "find sources",
    "find me sources",
    "give me sources",
    "cite your sources",
    "cite sources",
    "list your sources",
    "akademik kaynak",
    "bilimsel makale",
    "kaynak bul",
    "kaynak goster",
    "kaynak göster",
    "kaynaklarini ver",
    "kaynaklarını ver",
    "kaynak ver",
    "makale bul",
    "yayimlanmis",
    "yayımlanmış",
)

WEB_SEARCH_PHRASES = (
    "search the internet",
    "search the web",
    "search online",
    "look it up online",
    "browse the web",
    "google it",
    "look this up on the web",
    "internette ara",
    "internetten ara",
    "internetten bul",
    "webde ara",
    "web'de ara",
    "cevrimici ara",
    "çevrimiçi ara",
    "googlela",
)

_TABLE: tuple[tuple[LiveInformationRequestKind, tuple[str, ...]], ...] = (
    (LiveInformationRequestKind.EVIDENCE_PROVENANCE, EVIDENCE_PROVENANCE_PHRASES),
    (LiveInformationRequestKind.CURRENT_EVENTS, CURRENT_EVENTS_PHRASES),
    (LiveInformationRequestKind.ACADEMIC_SOURCES, ACADEMIC_SOURCE_PHRASES),
    (LiveInformationRequestKind.WEB_SEARCH, WEB_SEARCH_PHRASES),
)


class LiveInformationRequestDetector:
    """Classify one message against a fixed table, granting nothing."""

    def detect(self, message: str) -> LiveInformationRequestKind:
        """Return the most specific matching kind, or NONE."""
        if not isinstance(message, str) or not message.strip():
            return LiveInformationRequestKind.NONE
        bounded = message[:MAX_INSPECTED_CHARACTERS]
        forms = _normalized_forms(bounded)
        for kind, phrases in _TABLE:
            if any(phrase in form for form in forms for phrase in phrases):
                return kind
        if URL_PATTERN.search(bounded) and any(
            phrase in form for form in forms for phrase in URL_ACCESS_PHRASES
        ):
            return LiveInformationRequestKind.URL_ACCESS
        return LiveInformationRequestKind.NONE


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
