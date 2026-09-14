"""The exact sentences Hypatia uses to say what it did not do.

These are translations of fixed statements, not prompts. A model is never asked
to phrase them, because "I did not research this" is one rewrite away from "I
could not find much on this", and the second sentence is a lie about a network
request that never happened.

Every language therefore carries the same set of keys and each translation must
mean the same thing. Adding a language means adding entries; a missing key falls
back to English rather than being approximated, so a partial translation degrades
into a readable answer instead of a wrong one.

The ordering matters too. The first line a person reads is the plain statement;
the canonical counters follow under their own heading, because a reader who
asked a normal question should not have to parse a diagnostic to learn that
nothing was researched.
"""

from __future__ import annotations

from response.ResponseLanguage import ResponseLanguage

_ENGLISH: dict[str, str] = {
    "no_live_research": (
        "I did not search the internet for this, so I will not invent sources."
    ),
    "use_research": (
        "To research it for real, use the Research workflow, where each step is "
        "authorised separately."
    ),
    "url_not_opened": (
        "I did not open that link in this turn. Ordinary chat reaches no network."
    ),
    "url_unknown_reachability": (
        "That is not a statement about the site. I do not know whether it is "
        "reachable, because nothing tried it."
    ),
    "url_use_research": (
        "To actually check the page, load it as a source through the Research "
        "workflow."
    ),
    "evidence_none_at_all": (
        "I have not recorded any accepted source or any evidence."
    ),
    "evidence_sources_without_evidence": (
        "Accepted sources exist, but no evidence record does. An accepted source "
        "is not evidence: evidence is recorded separately, from a specific "
        "passage, by an explicit step."
    ),
    "evidence_recorded": (
        "These counts come from persisted research state. A recorded operation is "
        "not evidence, evidence is not a verified claim, and a claim is not an "
        "established truth."
    ),
    "evidence_heading": "Evidence actually recorded:",
    "details_heading": "Details:",
    "nothing_fabricated": (
        "Anything named as a source, paper, outlet, or date in an earlier reply "
        "was model output, not something I read."
    ),
}

_TURKISH: dict[str, str] = {
    "no_live_research": (
        "Bu konuda internette araştırma yapmadım, bu yüzden kaynak uydurmayacağım."
    ),
    "use_research": (
        "Gerçekten araştırmak için Research akışını kullanabilirsin; orada her "
        "adım ayrı ayrı onaylanır."
    ),
    "url_not_opened": (
        "Bu sohbet turunda bağlantıyı açmadım. Sıradan sohbet hiçbir ağa " "bağlanmaz."
    ),
    "url_unknown_reachability": (
        "Bu, site hakkında bir yargı değil. Erişilebilir olup olmadığını "
        "bilmiyorum, çünkü kimse denemedi."
    ),
    "url_use_research": (
        "Sayfayı gerçekten kontrol etmek için Research akışında kaynak olarak "
        "yükleyebilirsin."
    ),
    "evidence_none_at_all": ("Kabul edilmiş hiçbir kaynak ve hiçbir kanıt kaydım yok."),
    "evidence_sources_without_evidence": (
        "Kabul edilmiş kaynaklar var, ama kanıt kaydı yok. Kabul edilmiş bir "
        "kaynak kanıt değildir: kanıt, belirli bir bölümden ayrı bir adımla "
        "kaydedilir."
    ),
    "evidence_recorded": (
        "Bu sayılar kalıcı araştırma durumundan geliyor. Kaydedilmiş bir işlem "
        "kanıt değildir, kanıt doğrulanmış bir iddia değildir, iddia da "
        "kanıtlanmış bir gerçek değildir."
    ),
    "evidence_heading": "Gerçekten kaydedilmiş kanıt:",
    "details_heading": "Ayrıntılar:",
    "nothing_fabricated": (
        "Daha önceki bir yanıtta kaynak, makale, yayın ya da tarih olarak geçen "
        "şeyler modelin ürettiği metindi, okuduğum şeyler değil."
    ),
}

_PHRASES: dict[ResponseLanguage, dict[str, str]] = {
    ResponseLanguage.ENGLISH: _ENGLISH,
    ResponseLanguage.TURKISH: _TURKISH,
}


def phrase(key: str, language: ResponseLanguage) -> str:
    """Return one fixed sentence, falling back to English when untranslated."""
    if key not in _ENGLISH:
        raise KeyError(f"Unknown honesty phrase: {key}")
    return _PHRASES.get(language, _ENGLISH).get(key, _ENGLISH[key])


def phrase_keys() -> tuple[str, ...]:
    """Return every phrase key, so a translation can be checked for gaps."""
    return tuple(sorted(_ENGLISH))


def translated_languages() -> tuple[ResponseLanguage, ...]:
    """Return the languages carrying their own phrasing."""
    return tuple(_PHRASES)
