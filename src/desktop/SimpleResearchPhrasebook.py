"""The exact words Simple mode uses, looked up rather than composed.

Every string a person reads in Simple mode comes from this table. None of it is
generated, and a model is never asked to explain what happened, because the
whole value of Simple mode is that it says less than the audit view without
saying anything different. A model asked to phrase "the source was indexed but
the run did not accept it" will eventually phrase it as "loaded", and that
specific sentence is the failure this project already fixed once.

The stage translations are the load-bearing entries. `INDEXED_WITHOUT_RUN` is
the stage that looks like success from the outside — a document really does
exist locally — and it must never render as "Loaded". It renders as a sentence
that contains the word "but", because the whole point is the second half.

Technical codes are never hidden, only moved. Each stage has both a plain
sentence and its exact enum value; Simple mode shows the sentence and Advanced
Details shows the value. A person who cannot act on `run_attach_failed` is not
helped by reading it, and a person who can is not helped by it being deleted.

The table follows `HonestyPhrasebook`: same keys in every language, English as
the fallback for anything untranslated, so a partial translation degrades into a
readable answer rather than a wrong one.
"""

from __future__ import annotations

from research.SourceLoadStage import SourceLoadStage
from response.ResponseLanguage import ResponseLanguage

_ENGLISH: dict[str, str] = {
    # Panel furniture
    "panel_title": "Research",
    "question_prompt": "What do you want to research?",
    "start_research": "Start research",
    "status_heading": "Status",
    "sources_heading": "Sources",
    "selected_heading": "Selected source",
    "advanced_details": "Advanced details",
    "use_this_source": "Use this source",
    "find_sources": "Find sources",
    "view_evidence": "View evidence",
    "research_this": "Research this",
    # Steps
    "step_question_created": "Question created",
    "step_sources_discovered": "Sources found",
    "step_source_accepted": "Accepted for research",
    "step_evidence_recorded": "Evidence recorded",
    # Activities
    "activity_creating_question": "Creating the question...",
    "activity_finding_sources": "Finding sources...",
    "activity_loading_source": "Loading source...",
    # States
    "no_question_yet": "No research question yet. Type one above to begin.",
    "no_sources_yet": "No sources yet. Use Find sources to look for some.",
    "discovery_found_nothing": (
        "The search ran and returned no sources. Nothing was fetched."
    ),
    "candidate_discovered": "Discovered",
    "relevance_strong": "Closely matches your question",
    "relevance_moderate": "Partly matches your question",
    "relevance_weak": "Barely matches your question",
    "relevance_unrelated": "Does not match your question",
    "relevance_unmeasured": "Not compared to your question",
    "relevance_meaning": (
        "Matching means your words appear in the title. It does not mean the "
        "source is reliable or correct."
    ),
    "candidate_accepted": "Accepted for research",
    "candidate_not_fetched": (
        "Discovered means proposed, not fetched. Nothing has been downloaded yet."
    ),
    "evidence_none": ("No evidence recorded yet. An accepted source is not evidence."),
    "evidence_present": (
        "Evidence has been recorded. Evidence is not a verified claim."
    ),
    "confirm_title": "Load this source?",
    "confirm_body": (
        "Hypatia will fetch this source over the network, index it on this "
        "machine, and add it to this research. Continue?"
    ),
    "cancelled_by_user": "Not loaded. Nothing was fetched.",
    "select_source_first": "Choose a source first.",
    "question_required": "Type a research question first.",
    # Source load stages, plainly
    "stage_not_attempted": "Nothing was attempted for this source.",
    "stage_cancelled": "Cancelled before it finished. Nothing was added.",
    "stage_fetch_refused": (
        "Hypatia could not fetch this source under the current network safety "
        "rules. Nothing was downloaded."
    ),
    "stage_index_failed": (
        "The source was fetched, but could not be indexed on this machine. "
        "It was not added to this research."
    ),
    "stage_content_persist_failed": (
        "The source was fetched and indexed, but its audit copy could not be "
        "saved, so the local copy was undone and nothing was added."
    ),
    "stage_run_attach_failed": (
        "The source was processed, but could not be added to this research, so "
        "the local copy was undone."
    ),
    "stage_indexed_without_run": (
        "Indexed locally, but not added to this research. No evidence can be "
        "recorded from it."
    ),
    "stage_accepted_into_run": (
        "Accepted for research. Being accepted is not the same as being evidence."
    ),
    # Advanced
    "advanced_technical_code": "Technical code",
    "advanced_run_id": "Research run ID",
    "advanced_discovery_id": "Discovery ID",
    "advanced_document_id": "Document ID",
    "advanced_url": "Source URL",
    "advanced_hidden_note": (
        "Technical identifiers are hidden in Simple mode. They are shown here "
        "unchanged."
    ),
}

_TURKISH: dict[str, str] = {
    "panel_title": "Araştırma",
    "question_prompt": "Neyi araştırmak istiyorsun?",
    "start_research": "Araştırmayı başlat",
    "status_heading": "Durum",
    "sources_heading": "Kaynaklar",
    "selected_heading": "Seçili kaynak",
    "advanced_details": "Gelişmiş ayrıntılar",
    "use_this_source": "Bu kaynağı kullan",
    "find_sources": "Kaynak ara",
    "view_evidence": "Kanıtları gör",
    "research_this": "Bunu araştır",
    "step_question_created": "Soru oluşturuldu",
    "step_sources_discovered": "Kaynaklar bulundu",
    "step_source_accepted": "Araştırmaya kabul edildi",
    "step_evidence_recorded": "Kanıt kaydedildi",
    "activity_creating_question": "Soru oluşturuluyor...",
    "activity_finding_sources": "Kaynaklar aranıyor...",
    "activity_loading_source": "Kaynak yükleniyor...",
    "no_question_yet": (
        "Henüz bir araştırma sorusu yok. Başlamak için yukarıya bir soru yaz."
    ),
    "no_sources_yet": "Henüz kaynak yok. Aramak için Kaynak ara düğmesini kullan.",
    "discovery_found_nothing": (
        "Arama çalıştı ve hiç kaynak dönmedi. Hiçbir şey indirilmedi."
    ),
    "candidate_discovered": "Bulundu",
    "relevance_strong": "Sorunla yakından eşleşiyor",
    "relevance_moderate": "Sorunla kısmen eşleşiyor",
    "relevance_weak": "Sorunla zar zor eşleşiyor",
    "relevance_unrelated": "Sorunla eşleşmiyor",
    "relevance_unmeasured": "Sorunla karşılaştırılmadı",
    "relevance_meaning": (
        "Eşleşme, kelimelerinin başlıkta geçtiği anlamına gelir. Kaynağın "
        "güvenilir ya da doğru olduğu anlamına gelmez."
    ),
    "candidate_accepted": "Araştırmaya kabul edildi",
    "candidate_not_fetched": (
        "Bulundu, önerildi demektir; indirildi demek değildir. Henüz hiçbir şey "
        "indirilmedi."
    ),
    "evidence_none": (
        "Henüz kanıt kaydedilmedi. Kabul edilmiş bir kaynak kanıt değildir."
    ),
    "evidence_present": ("Kanıt kaydedildi. Kanıt, doğrulanmış bir iddia değildir."),
    "confirm_title": "Bu kaynak yüklensin mi?",
    "confirm_body": (
        "Hypatia bu kaynağı ağ üzerinden indirecek, bu bilgisayarda "
        "dizinleyecek ve bu araştırmaya ekleyecek. Devam edilsin mi?"
    ),
    "cancelled_by_user": "Yüklenmedi. Hiçbir şey indirilmedi.",
    "select_source_first": "Önce bir kaynak seç.",
    "question_required": "Önce bir araştırma sorusu yaz.",
    "stage_not_attempted": "Bu kaynak için hiçbir işlem denenmedi.",
    "stage_cancelled": "Tamamlanmadan iptal edildi. Hiçbir şey eklenmedi.",
    "stage_fetch_refused": (
        "Hypatia mevcut ağ güvenliği kuralları altında bu kaynağı indiremedi. "
        "Hiçbir şey indirilmedi."
    ),
    "stage_index_failed": (
        "Kaynak indirildi ama bu bilgisayarda dizinlenemedi. Bu araştırmaya "
        "eklenmedi."
    ),
    "stage_content_persist_failed": (
        "Kaynak indirildi ve dizinlendi ama denetim kopyası kaydedilemedi; "
        "yerel kopya geri alındı ve hiçbir şey eklenmedi."
    ),
    "stage_run_attach_failed": (
        "Kaynak işlendi ama bu araştırmaya eklenemedi; yerel kopya geri alındı."
    ),
    "stage_indexed_without_run": (
        "Yerel olarak dizinlendi ama bu araştırmaya eklenmedi. Bu kaynaktan "
        "kanıt kaydedilemez."
    ),
    "stage_accepted_into_run": (
        "Araştırmaya kabul edildi. Kabul edilmiş olmak kanıt olmakla aynı şey "
        "değildir."
    ),
    "advanced_technical_code": "Teknik kod",
    "advanced_run_id": "Araştırma kaydı kimliği",
    "advanced_discovery_id": "Keşif kimliği",
    "advanced_document_id": "Belge kimliği",
    "advanced_url": "Kaynak adresi",
    "advanced_hidden_note": (
        "Teknik kimlikler Basit modda gizlenir. Burada değiştirilmeden " "gösterilir."
    ),
}

_PHRASES: dict[ResponseLanguage, dict[str, str]] = {
    ResponseLanguage.ENGLISH: _ENGLISH,
    ResponseLanguage.TURKISH: _TURKISH,
}

_STAGE_KEYS: dict[SourceLoadStage, str] = {
    SourceLoadStage.NOT_ATTEMPTED: "stage_not_attempted",
    SourceLoadStage.CANCELLED: "stage_cancelled",
    SourceLoadStage.FETCH_REFUSED: "stage_fetch_refused",
    SourceLoadStage.INDEX_FAILED: "stage_index_failed",
    SourceLoadStage.CONTENT_PERSIST_FAILED: "stage_content_persist_failed",
    SourceLoadStage.RUN_ATTACH_FAILED: "stage_run_attach_failed",
    SourceLoadStage.INDEXED_WITHOUT_RUN: "stage_indexed_without_run",
    SourceLoadStage.ACCEPTED_INTO_RUN: "stage_accepted_into_run",
}


def phrase(key: str, language: ResponseLanguage) -> str:
    """Return one fixed string, falling back to English when untranslated."""
    if key not in _ENGLISH:
        raise KeyError(f"Unknown simple research phrase: {key}")
    return _PHRASES.get(language, _ENGLISH).get(key, _ENGLISH[key])


def stage_phrase(stage: SourceLoadStage, language: ResponseLanguage) -> str:
    """Return the plain sentence for one load stage, refusing an unmapped one.

    Refusing rather than defaulting is deliberate. A stage added later without a
    translation would otherwise silently render as some other stage's sentence,
    and being told the wrong thing confidently is worse than being told nothing.
    """
    if stage not in _STAGE_KEYS:
        raise KeyError(f"Source load stage {stage} has no simple phrasing.")
    return phrase(_STAGE_KEYS[stage], language)


def phrase_keys() -> tuple[str, ...]:
    """Return every key, so a translation can be checked for gaps."""
    return tuple(sorted(_ENGLISH))


def translated_languages() -> tuple[ResponseLanguage, ...]:
    """Return the languages carrying their own phrasing."""
    return tuple(_PHRASES)
