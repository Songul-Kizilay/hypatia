"""Headless coverage for the Simple mode projection.

Simple mode's promise is that it says less than the audit view without saying
anything different. Most of these tests are that promise stated one case at a
time: a discovered candidate is not shown as loaded, an indexed-only source is
not shown as accepted, an accepted source is not shown as evidence, and a
request that is still in flight is not shown as progress.

Nothing here touches Tkinter, a network, or a store. The projection is a pure
function of one immutable run snapshot, which is what makes these assertions
mean something.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from desktop.SimpleResearchActivity import SimpleResearchActivity
from desktop.SimpleResearchPhrasebook import (
    phrase,
    phrase_keys,
    stage_phrase,
    translated_languages,
)
from desktop.SimpleResearchReadModel import SimpleResearchReadModel
from desktop.SimpleResearchStep import SimpleResearchStep
from desktop.SimpleSourceCard import SimpleSourceCard
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRecord import ResearchSourceRecord
from research.SourceLoadStage import SourceLoadStage
from response.ResponseLanguage import ResponseLanguage

NOW = datetime(2026, 8, 24, 10, tzinfo=UTC)
CANDIDATE_URL = "https://portswigger.net/web-security"


class SimpleResearchStepTests(unittest.TestCase):
    """The ladder is derived from persisted state, never from intent."""

    def test_no_run_is_not_started(self) -> None:
        self.assertIs(
            SimpleResearchStep.for_run(None),
            SimpleResearchStep.NOT_STARTED,
        )

    def test_a_bare_run_has_only_a_question(self) -> None:
        self.assertIs(
            SimpleResearchStep.for_run(_run()),
            SimpleResearchStep.QUESTION_CREATED,
        )

    def test_candidates_advance_to_sources_discovered(self) -> None:
        self.assertIs(
            SimpleResearchStep.for_run(_run(discoveries=(_discovery(),))),
            SimpleResearchStep.SOURCES_DISCOVERED,
        )

    def test_a_discovery_with_no_candidates_does_not_advance(self) -> None:
        """The search ran; it did not find anything. Those are different."""
        empty = _discovery(candidates=())

        self.assertIs(
            SimpleResearchStep.for_run(_run(discoveries=(empty,))),
            SimpleResearchStep.QUESTION_CREATED,
        )

    def test_accepted_sources_advance_further_than_candidates(self) -> None:
        run = _run(discoveries=(_discovery(),), sources=(_source(),))

        self.assertIs(
            SimpleResearchStep.for_run(run),
            SimpleResearchStep.SOURCE_ACCEPTED,
        )

    def test_evidence_is_the_furthest_step(self) -> None:
        run = _run(sources=(_source(),), evidence=(_evidence(),))

        self.assertIs(
            SimpleResearchStep.for_run(run),
            SimpleResearchStep.EVIDENCE_RECORDED,
        )

    def test_discovery_alone_is_not_an_accepted_source(self) -> None:
        step = SimpleResearchStep.for_run(_run(discoveries=(_discovery(),)))

        self.assertFalse(step.has_accepted_source)

    def test_an_accepted_source_is_not_evidence(self) -> None:
        step = SimpleResearchStep.for_run(_run(sources=(_source(),)))

        self.assertTrue(step.has_accepted_source)
        self.assertFalse(step.has_evidence)

    def test_the_ladder_stops_at_evidence(self) -> None:
        """There is no 'research ready' step, because nothing proves it."""
        labels = [step.value for step in SimpleResearchStep.ladder()]

        self.assertEqual(labels[-1], "evidence_recorded")
        self.assertNotIn("not_started", labels)

    def test_the_step_has_no_setter(self) -> None:
        self.assertFalse(hasattr(SimpleResearchStep, "advance"))


class SimpleResearchActivityTests(unittest.TestCase):
    """An in-flight request has achieved nothing yet."""

    def test_idle_is_not_in_flight(self) -> None:
        self.assertFalse(SimpleResearchActivity.IDLE.in_flight)

    def test_every_other_activity_is_in_flight(self) -> None:
        for activity in SimpleResearchActivity:
            if activity is SimpleResearchActivity.IDLE:
                continue
            with self.subTest(activity=activity):
                self.assertTrue(activity.in_flight)

    def test_creating_a_question_reaches_no_network(self) -> None:
        self.assertFalse(SimpleResearchActivity.CREATING_QUESTION.reaches_network)

    def test_finding_and_loading_reach_the_network(self) -> None:
        self.assertTrue(SimpleResearchActivity.FINDING_SOURCES.reaches_network)
        self.assertTrue(SimpleResearchActivity.LOADING_SOURCE.reaches_network)

    def test_an_activity_is_not_a_step(self) -> None:
        """Separate types, so a spinner cannot be mistaken for progress."""
        activity_values = {activity.value for activity in SimpleResearchActivity}
        step_values = {step.value for step in SimpleResearchStep}

        self.assertEqual(activity_values & step_values, set())


class StatusTextTests(unittest.TestCase):
    def test_no_run_invites_a_question(self) -> None:
        model = SimpleResearchReadModel(run=None)

        self.assertEqual(model.status_text(), phrase("no_question_yet", _EN))

    def test_an_in_flight_activity_outranks_the_step(self) -> None:
        """Reporting the step while working would claim it had finished."""
        model = SimpleResearchReadModel(
            run=_run(sources=(_source(),)),
            activity=SimpleResearchActivity.LOADING_SOURCE,
        )

        self.assertEqual(model.status_text(), phrase("activity_loading_source", _EN))

    def test_a_fresh_run_asks_for_sources(self) -> None:
        model = SimpleResearchReadModel(run=_run())

        self.assertEqual(model.status_text(), phrase("no_sources_yet", _EN))

    def test_an_empty_search_says_so_rather_than_staying_silent(self) -> None:
        model = SimpleResearchReadModel(run=_run(discoveries=(_discovery(()),)))

        self.assertEqual(model.status_text(), phrase("discovery_found_nothing", _EN))

    def test_an_accepted_source_reports_acceptance(self) -> None:
        model = SimpleResearchReadModel(run=_run(sources=(_source(),)))

        self.assertEqual(model.status_text(), phrase("step_source_accepted", _EN))


class LadderTests(unittest.TestCase):
    def test_an_unreached_step_is_marked_unreached(self) -> None:
        model = SimpleResearchReadModel(run=_run())

        reached = dict(model.ladder())
        self.assertTrue(reached[phrase("step_question_created", _EN)])
        self.assertFalse(reached[phrase("step_source_accepted", _EN)])

    def test_reaching_a_step_marks_every_earlier_one(self) -> None:
        model = SimpleResearchReadModel(
            run=_run(sources=(_source(),), evidence=(_evidence(),))
        )

        self.assertTrue(all(reached for _, reached in model.ladder()))

    def test_an_activity_does_not_mark_a_step_reached(self) -> None:
        """The load is running. The run has not accepted anything."""
        model = SimpleResearchReadModel(
            run=_run(discoveries=(_discovery(),)),
            activity=SimpleResearchActivity.LOADING_SOURCE,
        )

        reached = dict(model.ladder())
        self.assertFalse(reached[phrase("step_source_accepted", _EN)])


class SourceCardTests(unittest.TestCase):
    def test_a_candidate_is_shown_as_discovered_not_loaded(self) -> None:
        model = SimpleResearchReadModel(run=_run(discoveries=(_discovery(),)))

        card = model.candidate_cards()[0]
        self.assertEqual(card.status_text, phrase("candidate_discovered", _EN))
        self.assertFalse(card.accepted)
        self.assertNotIn("load", card.status_text.casefold())

    def test_a_card_shows_the_site_rather_than_the_raw_url(self) -> None:
        model = SimpleResearchReadModel(run=_run(discoveries=(_discovery(),)))

        card = model.candidate_cards()[0]
        self.assertEqual(card.site, "portswigger.net")
        self.assertNotIn("https://", card.heading)

    def test_www_is_dropped_from_the_site(self) -> None:
        self.assertEqual(
            SimpleResearchReadModel.site_of("https://www.Example.COM/a"),
            "example.com",
        )

    def test_a_candidate_the_run_accepted_is_shown_as_accepted(self) -> None:
        run = _run(
            discoveries=(_discovery(),),
            sources=(_source(url=CANDIDATE_URL),),
        )
        model = SimpleResearchReadModel(run=run)

        card = model.candidate_cards()[0]
        self.assertTrue(card.accepted)
        self.assertEqual(card.status_text, phrase("candidate_accepted", _EN))
        self.assertEqual(card.document_id, "document-1")

    def test_acceptance_is_matched_by_canonical_identity_not_exact_text(self) -> None:
        """Trailing slash and case are the same resource, and must not double."""
        run = _run(
            discoveries=(_discovery(),),
            sources=(_source(url="https://PortSwigger.net/web-security/"),),
        )
        model = SimpleResearchReadModel(run=run)

        self.assertTrue(model.candidate_cards()[0].accepted)

    def test_one_resource_listed_twice_is_shown_once(self) -> None:
        """A repeated row reads as two sources, which is the corroboration lie."""
        duplicated = _discovery(
            (
                _candidate(CANDIDATE_URL),
                _candidate("https://portswigger.net/web-security/"),
            )
        )
        model = SimpleResearchReadModel(run=_run(discoveries=(duplicated,)))

        self.assertEqual(len(model.candidate_cards()), 1)

    def test_only_the_latest_discovery_is_shown(self) -> None:
        older = _discovery((_candidate("https://example.org/old"),), "discovery-0")
        model = SimpleResearchReadModel(run=_run(discoveries=(older, _discovery())))

        sites = [card.site for card in model.candidate_cards()]
        self.assertEqual(sites, ["portswigger.net"])

    def test_the_list_a_person_reads_first_is_in_relevance_order(self) -> None:
        """Provider order put the vague result first; the panel must not."""
        discovery = ResearchSourceDiscoveryRecord(
            "discovery-1",
            "request smuggling",
            "test-provider",
            (
                _candidate("https://doi.org/10.1/survey", title="A general survey"),
                _candidate("https://doi.org/10.1/exact", title="Request smuggling"),
            ),
            NOW,
        )
        model = SimpleResearchReadModel(run=_run(discoveries=(discovery,)))

        self.assertEqual(
            [card.heading for card in model.candidate_cards()],
            ["Request smuggling", "A general survey"],
        )

    def test_a_card_says_how_well_it_matched_in_ordinary_words(self) -> None:
        discovery = ResearchSourceDiscoveryRecord(
            "discovery-1",
            "request smuggling",
            "test-provider",
            (_candidate("https://doi.org/10.1/exact", title="Request smuggling"),),
            NOW,
        )
        model = SimpleResearchReadModel(run=_run(discoveries=(discovery,)))

        card = model.candidate_cards()[0]
        self.assertEqual(card.relevance_text, phrase("relevance_strong", _EN))
        self.assertNotIn("score", card.relevance_text.casefold())

    def test_matching_well_is_never_worded_as_being_reliable(self) -> None:
        """The whole risk of a score is that it reads as a verdict on the source."""
        for key in (
            "relevance_strong",
            "relevance_moderate",
            "relevance_weak",
            "relevance_unrelated",
            "relevance_unmeasured",
        ):
            with self.subTest(key=key):
                words = phrase(key, _EN).casefold()
                for forbidden in ("reliable", "true", "correct", "trust", "verified"):
                    self.assertNotIn(forbidden, words)

    def test_a_card_names_the_journal_when_the_record_carries_one(self) -> None:
        """Every DOI result shares one host, so the host distinguishes nothing."""
        discovery = ResearchSourceDiscoveryRecord(
            "discovery-1",
            "web application security",
            "test-provider",
            (
                ResearchSourceCandidate(
                    url="https://doi.org/10.1/paper",
                    title="A paper",
                    snippet="USENIX Security · 2025",
                    container="USENIX Security",
                    published_year=2025,
                ),
            ),
            NOW,
        )
        model = SimpleResearchReadModel(run=_run(discoveries=(discovery,)))

        self.assertEqual(model.candidate_cards()[0].site, "USENIX Security")

    def test_a_record_without_a_venue_falls_back_to_its_host(self) -> None:
        model = SimpleResearchReadModel(run=_run(discoveries=(_discovery(),)))

        self.assertEqual(model.candidate_cards()[0].site, "portswigger.net")

    def test_the_venue_is_never_recovered_by_splitting_the_snippet(self) -> None:
        """A parsed display string is a guess wearing the clothes of a fact."""
        discovery = ResearchSourceDiscoveryRecord(
            "discovery-1",
            "web application security",
            "test-provider",
            (
                ResearchSourceCandidate(
                    url="https://doi.org/10.1/paper",
                    title="A paper",
                    snippet="Journal of Invented Facts · 1999",
                    container="",
                ),
            ),
            NOW,
        )
        model = SimpleResearchReadModel(run=_run(discoveries=(discovery,)))

        card = model.candidate_cards()[0]
        self.assertNotIn("Invented", card.site)
        self.assertNotIn("1999", card.site)

    def test_a_card_cannot_claim_acceptance_without_a_document(self) -> None:
        from core.Exceptions import ResearchError

        with self.assertRaises(ResearchError):
            SimpleSourceCard(
                title="Title",
                site="example.com",
                status_text="Accepted",
                accepted=True,
                url="https://example.com/a",
            )

    def test_a_card_cannot_carry_a_document_it_was_not_accepted_as(self) -> None:
        from core.Exceptions import ResearchError

        with self.assertRaises(ResearchError):
            SimpleSourceCard(
                title="Title",
                site="example.com",
                status_text="Discovered",
                accepted=False,
                url="https://example.com/a",
                document_id="document-1",
            )

    def test_a_long_title_is_bounded_for_display(self) -> None:
        card = SimpleSourceCard(
            title="word " * 60,
            site="example.com",
            status_text="Discovered",
            accepted=False,
            url="https://example.com/a",
        )

        self.assertLessEqual(len(card.heading), 90)
        self.assertTrue(card.heading.endswith("..."))


class StageTextTests(unittest.TestCase):
    """The stage that looks like success is the one that must not read like it."""

    def test_indexed_without_run_never_renders_as_loaded(self) -> None:
        text = stage_phrase(SourceLoadStage.INDEXED_WITHOUT_RUN, _EN)

        self.assertIn("not added to this research", text)
        self.assertNotIn("loaded", text.casefold())

    def test_indexed_without_run_admits_the_local_document_exists(self) -> None:
        """Hiding the local copy would be a different lie."""
        text = stage_phrase(SourceLoadStage.INDEXED_WITHOUT_RUN, _EN)

        self.assertIn("Indexed locally", text)

    def test_accepted_says_accepted_and_stops_short_of_evidence(self) -> None:
        text = stage_phrase(SourceLoadStage.ACCEPTED_INTO_RUN, _EN)

        self.assertIn("Accepted for research", text)
        self.assertIn("not the same as being evidence", text)

    def test_run_attach_failed_is_explained_in_ordinary_words(self) -> None:
        text = stage_phrase(SourceLoadStage.RUN_ATTACH_FAILED, _EN)

        self.assertIn("could not be added to this research", text)

    def test_fetch_refused_blames_the_safety_rules_not_the_user(self) -> None:
        text = stage_phrase(SourceLoadStage.FETCH_REFUSED, _EN)

        self.assertIn("network safety rules", text)
        self.assertIn("Nothing was downloaded", text)

    def test_index_failed_separates_fetching_from_indexing(self) -> None:
        text = stage_phrase(SourceLoadStage.INDEX_FAILED, _EN)

        self.assertIn("fetched", text)
        self.assertIn("could not be indexed", text)

    def test_every_stage_has_a_plain_sentence(self) -> None:
        for stage in SourceLoadStage:
            with self.subTest(stage=stage):
                self.assertTrue(stage_phrase(stage, _EN).strip())

    def test_no_stage_sentence_contains_the_enum_value(self) -> None:
        """Simple mode reads as language, not as a diagnostic."""
        for stage in SourceLoadStage:
            with self.subTest(stage=stage):
                self.assertNotIn(stage.value, stage_phrase(stage, _EN))

    def test_a_failed_stage_reaches_the_reader_deterministically(self) -> None:
        model = SimpleResearchReadModel(
            run=_run(),
            last_stage=SourceLoadStage.RUN_ATTACH_FAILED,
        )

        self.assertEqual(
            model.stage_text(),
            stage_phrase(SourceLoadStage.RUN_ATTACH_FAILED, _EN),
        )

    def test_no_stage_yields_no_sentence(self) -> None:
        self.assertEqual(SimpleResearchReadModel(run=_run()).stage_text(), "")


class EvidenceTextTests(unittest.TestCase):
    def test_an_accepted_source_alone_is_not_evidence(self) -> None:
        model = SimpleResearchReadModel(run=_run(sources=(_source(),)))

        self.assertEqual(model.evidence_text(), phrase("evidence_none", _EN))
        self.assertIn("not evidence", model.evidence_text())

    def test_evidence_present_stops_short_of_a_verified_claim(self) -> None:
        model = SimpleResearchReadModel(
            run=_run(sources=(_source(),), evidence=(_evidence(),))
        )

        self.assertIn("not a verified claim", model.evidence_text())


class AdvancedDetailsTests(unittest.TestCase):
    def test_identifiers_are_hidden_from_the_simple_surface(self) -> None:
        run = _run(discoveries=(_discovery(),), sources=(_source(url=CANDIDATE_URL),))
        model = SimpleResearchReadModel(run=run)

        self.assertTrue(model.hides_identifiers())

    def test_advanced_details_expose_every_identifier_unchanged(self) -> None:
        run = _run(discoveries=(_discovery(),), sources=(_source(url=CANDIDATE_URL),))
        model = SimpleResearchReadModel(run=run)

        values = [value for _, value in model.advanced_details()]
        self.assertIn("run-1", values)
        self.assertIn("discovery-1", values)
        self.assertIn("document-1", values)
        self.assertIn(CANDIDATE_URL, values)

    def test_advanced_details_carry_the_exact_technical_code(self) -> None:
        model = SimpleResearchReadModel(
            run=_run(),
            last_stage=SourceLoadStage.RUN_ATTACH_FAILED,
        )

        self.assertIn(
            ("Technical code", "run_attach_failed"),
            model.advanced_details(),
        )

    def test_no_run_exposes_nothing(self) -> None:
        self.assertEqual(SimpleResearchReadModel(run=None).advanced_details(), ())


class LanguageTests(unittest.TestCase):
    def test_turkish_renders_the_same_meaning(self) -> None:
        model = SimpleResearchReadModel(
            run=_run(sources=(_source(),)),
            language=ResponseLanguage.TURKISH,
        )

        self.assertEqual(model.status_text(), phrase("step_source_accepted", _TR))
        self.assertNotEqual(
            phrase("step_source_accepted", _TR),
            phrase("step_source_accepted", _EN),
        )

    def test_every_language_carries_every_key(self) -> None:
        for language in translated_languages():
            for key in phrase_keys():
                with self.subTest(language=language, key=key):
                    self.assertTrue(phrase(key, language).strip())

    def test_an_untranslated_language_falls_back_rather_than_failing(self) -> None:
        self.assertEqual(phrase("start_research", _EN), "Start research")

    def test_an_unknown_key_is_refused(self) -> None:
        with self.assertRaises(KeyError):
            phrase("no_such_key", _EN)

    def test_the_turkish_indexed_only_sentence_still_says_not_added(self) -> None:
        """The load-bearing distinction must survive translation."""
        text = stage_phrase(SourceLoadStage.INDEXED_WITHOUT_RUN, _TR)

        self.assertIn("eklenmedi", text)

    def test_canonical_vocabulary_stays_language_neutral(self) -> None:
        """Enums are not translated; only their presentation is."""
        self.assertEqual(SourceLoadStage.ACCEPTED_INTO_RUN.value, "accepted_into_run")
        self.assertEqual(
            SimpleResearchStep.SOURCE_ACCEPTED.value,
            "source_accepted",
        )


_EN = ResponseLanguage.ENGLISH
_TR = ResponseLanguage.TURKISH


def _candidate(
    url: str = CANDIDATE_URL,
    title: str = "Modern web application security in practice",
) -> ResearchSourceCandidate:
    return ResearchSourceCandidate(url, title, "A bounded snippet.")


def _discovery(
    candidates: tuple[ResearchSourceCandidate, ...] | None = None,
    discovery_id: str = "discovery-1",
) -> ResearchSourceDiscoveryRecord:
    return ResearchSourceDiscoveryRecord(
        discovery_id,
        "web application security",
        "test-provider",
        (_candidate(),) if candidates is None else candidates,
        NOW,
    )


def _source(
    document_id: str = "document-1",
    url: str = "https://example.com/paper",
) -> ResearchSourceRecord:
    return ResearchSourceRecord(
        document_id,
        url,
        "Accepted source title",
        "text/html",
        NOW,
        NOW + timedelta(minutes=1),
    )


def _evidence(
    evidence_id: str = "evidence-1",
    source_document_id: str = "document-1",
) -> ResearchEvidenceRecord:
    return ResearchEvidenceRecord(
        evidence_id,
        source_document_id,
        f"{source_document_id}:paragraph:0",
        0,
        "Bounded evidence",
        False,
        "0" * 64,
        "User note",
        NOW,
    )


def _run(
    *,
    sources: tuple[ResearchSourceRecord, ...] = (),
    discoveries: tuple[ResearchSourceDiscoveryRecord, ...] = (),
    evidence: tuple[ResearchEvidenceRecord, ...] = (),
) -> ResearchRun:
    return ResearchRun(
        "run-1",
        "What are the current web application security practices?",
        ResearchRunStatus.COLLECTING,
        sources,
        (),
        NOW,
        NOW,
        discoveries=discoveries,
        evidence=evidence,
    )


if __name__ == "__main__":
    unittest.main()
