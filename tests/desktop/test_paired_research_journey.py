"""One operator, one question, two providers — driven through the real controls.

Everything below already worked when called service by service. That is exactly
why this module exists: the previous milestone proved the pieces and left the
join between them untested, and the join is where a desktop goes wrong. A
refresh that reselects, a completion callback that fires in the wrong order, a
selector that defaults back to the first row, a status line that overwrites the
outcome — none of those are visible from a service test, and all of them have
already happened at least once in this codebase.

So the window here is a real `TkinterDesktopWindow` with its Tk variables
replaced by recorders, wired to a real `DesktopController` over a real
`CognitiveEngine` with real stores in a temporary directory. The tests press the
same methods the buttons are bound to, in the order an operator presses them.
Only two things are fake: the two discovery providers and the source fetcher,
because a test that reaches the network is not deterministic and this milestone
needs no evidence the network could provide.

Every assessment recorded here is fixture data in a temporary directory. None of
it is an operator's judgement, and the tests that matter most are the ones
asserting the system records what a person said rather than deciding it: an
unassessed source stays unknown, and confidence does not move because a provider
happened to be NIST.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from cognition.CognitiveEngine import CognitiveEngine
from core.Exceptions import ResearchError
from desktop.DesktopController import DesktopController
from desktop.ResearchWorkspaceReadModel import ResearchRunSort
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.JsonFileResearchSourceContentStore import (
    JsonFileResearchSourceContentStore,
)
from research.NvdResearchSourceDiscoveryProvider import (
    NVD_CVE_ENDPOINT,
    NVD_DETAIL_PREFIX,
)
from research.NvdResearchSourceFetcher import NVD_API_ACQUISITION
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchPairedProviderQualityEvaluator import (
    ResearchPairedProviderQualityEvaluator,
)
from research.ResearchPairedProviderQualityReport import (
    PAIRED_NO_POLICY_NOTICE,
    PAIRED_SELECTION_BIAS_NOTICE,
)
from research.ResearchProviderComparisonBuilder import ResearchProviderComparisonBuilder
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import HTTPS_ACQUISITION, ResearchSource
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceContentRestorer import ResearchSourceContentRestorer
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourceUsefulness import ResearchSourceUsefulness
from research.ResearchVulnerabilityRecord import ResearchVulnerabilityRecord
from research.SourceIdentity import identity_of
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService
from tests.desktop.test_tkinter_desktop_window import (
    ImmediateRequestRunner,
    RecordingCandidateSelector,
    RecordingRequestRoot,
    RecordingStatus,
    RecordingVariable,
    _configure_research_evidence_selector,
)

QUESTION = "CVE-2025-29927"
CVE = "CVE-2025-29927"
DETAIL_URL = f"{NVD_DETAIL_PREFIX}{CVE}"
DOI_URL = "https://doi.org/10.1000/middleware"
NVD_REFERENCE_URL = "https://github.test/advisory"
CROSSREF_LINK_URL = "https://publisher.test/article"
FETCHED_AT = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

NVD_CONTENT = "\n".join(
    (
        "This document was materialized from the NVD CVE API 2.0 response for "
        "this CVE. References below were listed by NVD; none was fetched.",
        "",
        f"CVE: {CVE}",
        "Provider record status: Analyzed",
        "Weaknesses: CWE-285",
        "",
        "Description (as published by NVD):",
        "Next.js middleware authorization bypass affecting several releases.",
        "",
        "References listed by NVD (not fetched, not verified):",
        f"- {NVD_REFERENCE_URL} [Patch]",
    )
)

CROSSREF_CONTENT = "\n".join(
    (
        "A peer-reviewed analysis of middleware authorization failures.",
        "",
        f"The authors host supplementary material at {CROSSREF_LINK_URL}.",
    )
)


class FakeDiscoveryProvider:
    """Return one fixed candidate and count every discovery request."""

    def __init__(self, provider_name: str, candidate: ResearchSourceCandidate) -> None:
        self.provider_name = provider_name
        self._candidate = candidate
        self.queries: list[str] = []

    def discover(self, query: str, *, limit: int) -> list[ResearchSourceCandidate]:
        self.queries.append(query)
        return [self._candidate]


class FakeRoutedFetcher:
    """Materialize either provider's source, recording every URL it is given.

    It records rather than merely returning, because several tests below are
    about what was *not* requested — a reference that stayed text, a preview
    that reached nothing, a refused side that did not quietly retry.
    """

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.refuse: set[str] = set()

    def fetch(self, url: str) -> ResearchSource:
        self.urls.append(url)
        if url in self.refuse:
            raise ResearchError("Research source did not contain readable text.")
        if url == DETAIL_URL:
            return ResearchSource(
                url=DETAIL_URL,
                title=f"{CVE}: Next.js middleware authorization bypass",
                content=NVD_CONTENT,
                content_type="text/plain",
                fetched_at=FETCHED_AT,
                content_resource=NVD_CVE_ENDPOINT,
                acquisition=NVD_API_ACQUISITION,
            )
        if url == DOI_URL:
            return ResearchSource(
                url=DOI_URL,
                title="Middleware authorization failures",
                content=CROSSREF_CONTENT,
                content_type="text/html",
                fetched_at=FETCHED_AT,
            )
        raise ResearchError("Unexpected research source URL.")


def crossref_candidate() -> ResearchSourceCandidate:
    return ResearchSourceCandidate(
        url=DOI_URL,
        title="Middleware authorization failures",
        snippet="Journal of Systems - 2025",
        container="Journal of Systems",
        published_year=2025,
    )


def nvd_candidate() -> ResearchSourceCandidate:
    return ResearchSourceCandidate(
        url=DETAIL_URL,
        title=f"{CVE}: middleware authorization bypass",
        snippet="Next.js middleware authorization bypass.",
        vulnerability=ResearchVulnerabilityRecord(cve_id=CVE),
    )


class PairedJourneyFixture(unittest.TestCase):
    """A real controller over real stores, driven through real window methods."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        self.content_path = self.root / "content.json"

        self.crossref = FakeDiscoveryProvider("crossref", crossref_candidate())
        self.nvd = FakeDiscoveryProvider("nvd", nvd_candidate())
        self.fetcher = FakeRoutedFetcher()
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        self.manager.load()
        self.content_store = JsonFileResearchSourceContentStore(self.content_path)
        self.controller = DesktopController(self._engine())
        self.run_id = self.manager.create(QUESTION).run_id
        self.window = self._window()

    def _engine(self) -> CognitiveEngine:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        session_manager = SessionManager(event_bus)
        return CognitiveEngine(
            self.knowledge_engine,
            memory_manager,
            Planner(),
            event_bus,
            ResponseComposer(),
            session_manager,
            SessionRenameTransactionService(
                session_manager=session_manager,
                memory_manager=memory_manager,
                event_bus=event_bus,
            ),
            research_run_manager=self.manager,
            research_source_fetcher=self.fetcher,
            research_source_content_store=self.content_store,
            # The named map alone leaves discovery unregistered: the runtime
            # wires the capability from the default provider and consults the
            # map for a named one, exactly as the composition root does.
            research_source_discovery_provider=self.crossref,
            research_source_discovery_providers={
                ResearchDiscoveryProviderName.CROSSREF: self.crossref,
                ResearchDiscoveryProviderName.NVD: self.nvd,
            },
        )

    def _window(self) -> Any:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._controller = self.controller
        window._research_run_id = RecordingVariable(self.run_id)
        window._research_run_choice = RecordingVariable("")
        window._research_run_summary = RecordingVariable("")
        window._research_run_context = RecordingVariable("")
        window._research_run_progress = RecordingVariable("")
        window._research_workflow_snapshot = RecordingVariable("")
        window._research_evidence_coverage = RecordingVariable("")
        window._research_assessment_coverage = RecordingVariable("")
        window._research_run_metadata = RecordingVariable("")
        window._research_run_filter = RecordingVariable("")
        window._research_run_filter_summary = RecordingVariable("")
        window._research_run_status_filter = RecordingVariable("all")
        window._research_run_catalog_summary = RecordingVariable("")
        window._research_run_sort = RecordingVariable(
            ResearchRunSort.UPDATED_NEWEST.value
        )
        window._research_run_sort_summary = RecordingVariable("")
        window._research_run_selector = RecordingCandidateSelector(selected_index=0)
        window._research_runs = ()
        window._visible_research_runs = ()
        window._research_url = RecordingVariable("")
        window._research_source_choice = RecordingVariable("")
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_sources = ()
        window._research_source_run_id = ""
        window._research_source_document_id = RecordingVariable("")
        window._research_comparison_document_ids = RecordingVariable("")
        window._research_claim_contradiction_proposal = RecordingVariable("")
        window._research_claim_contradiction_proposal_selector = (
            RecordingCandidateSelector()
        )
        window._research_claim_contradiction_proposal_run_id = ""
        window._research_claim_contradiction_proposals = ()
        window._research_markdown_export_preview = None
        window._research_discovery_provider = RecordingVariable("crossref")
        window._status = RecordingStatus()
        window._transcript_lines = []
        window._append_response = window._transcript_lines.append
        _configure_research_evidence_selector(window)
        window._request_runner = ImmediateRequestRunner()
        window._request_completion_handler = None
        window._request_controls = []
        window._request_label = None
        window._request_started_at = None
        window._closing = False
        window._research_refresh_signal = None
        window._root = RecordingRequestRoot()
        return window

    # ---- operator gestures --------------------------------------------

    def _discover(self, provider: str) -> None:
        """Press Discover for one provider and drain the worker."""
        self.window._research_discovery_provider.set(provider)
        self.window._discover_research_sources()
        self.window._poll_requests()

    def _select_candidate(self, url: str) -> None:
        """Select the candidate row whose URL this is."""
        index = [
            position
            for position, candidate in enumerate(self.window._research_candidates)
            if candidate.url == url
        ]
        self.assertEqual(len(index), 1, f"expected exactly one row for {url}")
        self.window._research_candidate_selector.current(index[0])

    def _accept_selected(self, *, confirm: bool = True) -> None:
        """Press Preview & load and answer the confirmation."""
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=confirm
        ):
            self.window._preview_and_accept_research_candidate()
        self.window._poll_requests()

    def _accept_both(self) -> None:
        self._discover("crossref")
        self._select_candidate(DOI_URL)
        self._accept_selected()
        self._discover("nvd")
        self._select_candidate(DETAIL_URL)
        self._accept_selected()

    def _source_for(self, url: str) -> Any:
        [source] = [
            source
            for source in self.manager.get(self.run_id).sources
            if source.url == url
        ]
        return source

    def _first_chunk(self, document_id: str) -> Any:
        chunks = [
            chunk
            for chunk in self.knowledge_engine.chunks()
            if chunk.document_id == document_id
        ]
        self.assertTrue(chunks, f"no chunks for {document_id}")
        return chunks[0]


class CandidateReachabilityTests(PairedJourneyFixture):
    def test_both_providers_answer_the_same_canonical_question(self) -> None:
        self._discover("crossref")
        self._discover("nvd")

        self.assertEqual(self.crossref.queries, [QUESTION])
        self.assertEqual(self.nvd.queries, [QUESTION])

    def test_both_candidate_sets_are_selectable_after_the_second_discovery(
        self,
    ) -> None:
        """A paired run is only assessable on both halves if both are reachable."""
        self._discover("crossref")
        self._discover("nvd")

        urls = [candidate.url for candidate in self.window._research_candidates]
        self.assertEqual(sorted(urls), sorted((DOI_URL, DETAIL_URL)))

    def test_each_candidate_keeps_its_own_provider_discovery(self) -> None:
        self._discover("crossref")
        self._discover("nvd")

        run = self.manager.get(self.run_id)
        by_provider = {
            discovery.provider: discovery.discovery_id for discovery in run.discoveries
        }
        pairs = dict(
            zip(
                [candidate.url for candidate in self.window._research_candidates],
                self.window._research_candidate_discovery_ids,
                strict=True,
            )
        )
        self.assertEqual(pairs[DOI_URL], by_provider["crossref"])
        self.assertEqual(pairs[DETAIL_URL], by_provider["nvd"])

    def test_using_a_candidate_url_loads_nothing(self) -> None:
        self._discover("nvd")
        self._select_candidate(DETAIL_URL)

        self.window._use_selected_research_candidate()

        self.assertEqual(self.window._research_url.value, DETAIL_URL)
        self.assertEqual(self.fetcher.urls, [])
        self.assertEqual(self.manager.get(self.run_id).sources, ())


class AcceptanceTests(PairedJourneyFixture):
    def test_declining_the_confirmation_attaches_nothing(self) -> None:
        self._discover("nvd")
        self._select_candidate(DETAIL_URL)

        self._accept_selected(confirm=False)

        self.assertEqual(self.fetcher.urls, [])
        self.assertEqual(self.manager.get(self.run_id).sources, ())

    def test_confirming_loads_exactly_the_selected_source_once(self) -> None:
        self._discover("nvd")
        self._select_candidate(DETAIL_URL)

        self._accept_selected()

        self.assertEqual(self.fetcher.urls, [DETAIL_URL])
        run = self.manager.get(self.run_id)
        self.assertEqual([source.url for source in run.sources], [DETAIL_URL])

    def test_both_providers_end_with_exactly_two_sources(self) -> None:
        self._accept_both()

        run = self.manager.get(self.run_id)
        self.assertEqual(len(run.sources), 2)
        self.assertEqual(
            sorted(source.url for source in run.sources), sorted((DOI_URL, DETAIL_URL))
        )
        self.assertEqual(sorted(self.fetcher.urls), sorted((DOI_URL, DETAIL_URL)))

    def test_the_selector_holds_both_sources_after_the_second_acceptance(self) -> None:
        """The second acceptance must not hide, replace, or duplicate the first."""
        self._accept_both()

        urls = [source.url for source in self.window._research_sources]
        self.assertEqual(sorted(urls), sorted((DOI_URL, DETAIL_URL)))
        self.assertEqual(len(set(urls)), 2)

    def test_the_selected_run_never_changes_through_the_journey(self) -> None:
        self._accept_both()

        self.assertEqual(self.window._research_run_id.get(), self.run_id)
        self.assertEqual(self.window._research_source_run_id, self.run_id)

    def test_the_successful_outcome_is_not_overwritten_by_the_refresh(self) -> None:
        self._accept_both()

        self.assertEqual(
            self.window._status.values[-1], "research candidate load: source attached"
        )

    def test_accepting_the_same_candidate_twice_adds_no_second_source(self) -> None:
        self._discover("nvd")
        self._select_candidate(DETAIL_URL)
        self._accept_selected()

        self._accept_selected()

        self.assertEqual(len(self.manager.get(self.run_id).sources), 1)
        self.assertEqual(
            self.window._status.values[-1],
            "research candidate load: failed; no source was attached",
        )


class PartialPairTests(PairedJourneyFixture):
    def test_a_refused_second_side_leaves_the_first_source_intact(self) -> None:
        """A failed provider is a failed provider, not a reason to undo the other."""
        self.fetcher.refuse.add(DETAIL_URL)
        self._discover("crossref")
        self._select_candidate(DOI_URL)
        self._accept_selected()

        self._discover("nvd")
        self._select_candidate(DETAIL_URL)
        self._accept_selected()

        run = self.manager.get(self.run_id)
        self.assertEqual([source.url for source in run.sources], [DOI_URL])
        self.assertEqual(
            self.window._status.values[-1],
            "research candidate load: failed; no source was attached",
        )

    def test_the_refused_side_is_recorded_as_a_visible_failure(self) -> None:
        self.fetcher.refuse.add(DETAIL_URL)
        self._discover("nvd")
        self._select_candidate(DETAIL_URL)

        self._accept_selected()

        run = self.manager.get(self.run_id)
        self.assertTrue(
            [failure for failure in run.failures if failure.stage == "source_load"]
        )

    def test_a_refused_side_is_not_retried_or_substituted(self) -> None:
        self.fetcher.refuse.add(DETAIL_URL)
        self._discover("nvd")
        self._select_candidate(DETAIL_URL)

        self._accept_selected()

        self.assertEqual(self.fetcher.urls, [DETAIL_URL])


class CrossProviderIdentityTests(PairedJourneyFixture):
    def test_neither_candidate_can_be_accepted_under_the_other_discovery(self) -> None:
        self._discover("crossref")
        self._discover("nvd")
        run = self.manager.get(self.run_id)
        by_provider = {
            discovery.provider: discovery.discovery_id for discovery in run.discoveries
        }

        for discovery_provider, url in (("crossref", DETAIL_URL), ("nvd", DOI_URL)):
            with self.subTest(discovery=discovery_provider):
                with self.assertRaises(ResearchError):
                    self.manager.preview_candidate_acceptance(
                        self.run_id, by_provider[discovery_provider], url
                    )

    def test_each_accepted_source_joins_only_its_own_provider_side(self) -> None:
        self._accept_both()

        report = ResearchProviderComparisonBuilder().build(
            self.manager.get(self.run_id)
        )

        sides = {side.provider: side for side in report.sides}
        self.assertEqual(sides["crossref"].accepted_count, 1)
        self.assertEqual(sides["nvd"].accepted_count, 1)
        self.assertNotEqual(sides["crossref"].discovery_id, sides["nvd"].discovery_id)

    def test_the_api_origin_never_becomes_the_nvd_source_identity(self) -> None:
        self._accept_both()

        source = self._source_for(DETAIL_URL)
        self.assertEqual(identity_of(source.url), identity_of(DETAIL_URL))
        self.assertNotEqual(identity_of(source.url), identity_of(NVD_CVE_ENDPOINT))

    def test_no_winner_is_produced_by_the_paired_comparison(self) -> None:
        self._accept_both()

        report = ResearchProviderComparisonBuilder().build(
            self.manager.get(self.run_id)
        )

        self.assertTrue(report.complete)
        rendered = " ".join(report.lines()).casefold()
        self.assertIn("no provider was judged better", rendered)
        for forbidden in ("winner", "recommended provider", "better provider"):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, rendered.replace("no provider", ""))


class AssessmentAndEvidenceTests(PairedJourneyFixture):
    def _select_source(self, url: str) -> None:
        index = [
            position
            for position, source in enumerate(self.window._research_sources)
            if source.url == url
        ]
        self.assertEqual(len(index), 1, f"expected exactly one source row for {url}")
        self.window._research_source_selector.current(index[0])

    def test_use_for_assessment_copies_each_providers_exact_document_id(self) -> None:
        self._accept_both()

        self._select_source(DOI_URL)
        self.window._use_selected_research_source_for_assessment()
        crossref_id = self.window._research_source_document_id.get()

        self._select_source(DETAIL_URL)
        self.window._use_selected_research_source_for_assessment()
        nvd_id = self.window._research_source_document_id.get()

        self.assertEqual(crossref_id, self._source_for(DOI_URL).document_id)
        self.assertEqual(nvd_id, self._source_for(DETAIL_URL).document_id)
        self.assertNotEqual(crossref_id, nvd_id)

    def test_selecting_a_source_saves_no_assessment(self) -> None:
        self._accept_both()

        self._select_source(DETAIL_URL)
        self.window._use_selected_research_source_for_assessment()

        self.assertEqual(self.manager.get(self.run_id).assessments, ())

    def test_each_providers_evidence_keeps_its_own_chunk_identity(self) -> None:
        self._accept_both()
        recorded = {}

        for url in (DOI_URL, DETAIL_URL):
            document_id = self._source_for(url).document_id
            chunk = self._first_chunk(document_id)
            run = self.manager.add_evidence(self.run_id, chunk, f"A note about {url}.")
            recorded[url] = (run.evidence[-1], chunk, document_id)

        for url, (evidence, chunk, document_id) in recorded.items():
            with self.subTest(url=url):
                self.assertEqual(evidence.source_document_id, document_id)
                self.assertEqual(evidence.chunk_id, chunk.chunk_id)
                self.assertEqual(evidence.chunk_index, chunk.index)
        self.assertNotEqual(
            recorded[DOI_URL][0].source_document_id,
            recorded[DETAIL_URL][0].source_document_id,
        )

    def test_recording_evidence_creates_no_claim(self) -> None:
        self._accept_both()
        document_id = self._source_for(DETAIL_URL).document_id

        run = self.manager.add_evidence(
            self.run_id, self._first_chunk(document_id), "A note."
        )

        self.assertEqual(run.claims, ())

    def test_one_claim_can_cite_evidence_from_both_providers(self) -> None:
        self._accept_both()
        evidence_ids = []
        for url in (DOI_URL, DETAIL_URL):
            document_id = self._source_for(url).document_id
            run = self.manager.add_evidence(
                self.run_id, self._first_chunk(document_id), f"Note for {url}."
            )
            evidence_ids.append(run.evidence[-1].evidence_id)

        run = self.manager.record_claim(
            self.run_id,
            evidence_ids,
            "Both records describe the same middleware bypass.",
            ResearchEpistemicState.HYPOTHESIS,
        )

        [claim] = run.claims
        self.assertEqual(sorted(claim.evidence_ids), sorted(evidence_ids))

    def test_two_providers_do_not_raise_the_recorded_confidence(self) -> None:
        """Two sources is a count. Confidence is a judgement, and stays one."""
        self._accept_both()
        evidence_ids = []
        for url in (DOI_URL, DETAIL_URL):
            document_id = self._source_for(url).document_id
            run = self.manager.add_evidence(
                self.run_id, self._first_chunk(document_id), f"Note for {url}."
            )
            evidence_ids.append(run.evidence[-1].evidence_id)

        run = self.manager.record_claim(
            self.run_id,
            evidence_ids,
            "A claim recorded without stating a confidence.",
            ResearchEpistemicState.HYPOTHESIS,
        )

        [claim] = run.claims
        self.assertEqual(claim.confidence.value, "unassessed")

    def test_no_reference_or_article_link_is_ever_requested(self) -> None:
        self._accept_both()
        for url in (DOI_URL, DETAIL_URL):
            document_id = self._source_for(url).document_id
            self.manager.add_evidence(
                self.run_id, self._first_chunk(document_id), f"Note for {url}."
            )

        self.assertEqual(sorted(self.fetcher.urls), sorted((DOI_URL, DETAIL_URL)))
        for inert in (NVD_REFERENCE_URL, CROSSREF_LINK_URL):
            with self.subTest(url=inert):
                self.assertNotIn(inert, self.fetcher.urls)
                self.assertNotIn(
                    inert,
                    [source.url for source in self.manager.get(self.run_id).sources],
                )


class PairedQualityTests(PairedJourneyFixture):
    """Synthetic fixture assessments only — no operator judgement is authored."""

    def _assess_both(self) -> None:
        for url in (DOI_URL, DETAIL_URL):
            document_id = self._source_for(url).document_id
            run = self.manager.add_evidence(
                self.run_id, self._first_chunk(document_id), f"Fixture note {url}."
            )
            self.manager.record_source_assessment(
                self.run_id,
                document_id,
                [run.evidence[-1].evidence_id],
                "Fixture assessment recorded by a test, not by an operator.",
                usefulness=ResearchSourceUsefulness.USEFUL,
                applicability=ResearchSourceApplicability.DIRECT,
                independence=ResearchSourceIndependence.INDEPENDENT,
            )

    def test_the_paired_run_is_eligible_and_keeps_one_funnel_per_provider(
        self,
    ) -> None:
        self._accept_both()
        self._assess_both()

        report = ResearchPairedProviderQualityEvaluator().evaluate(self.manager.list())

        self.assertEqual(report.eligible_pair_count, 1)

    def test_each_provider_keeps_its_own_funnel(self) -> None:
        """Two funnels side by side, never one number covering both."""
        self._accept_both()
        self._assess_both()

        [comparison] = (
            ResearchPairedProviderQualityEvaluator()
            .evaluate(self.manager.list())
            .comparisons
        )
        sides = {side.provider: side for side in comparison.sides}

        self.assertEqual(sorted(sides), ["crossref", "nvd"])
        for provider, side in sides.items():
            with self.subTest(provider=provider):
                self.assertEqual(side.discovery_count, 1)
                self.assertEqual(side.candidate_count, 1)
                self.assertEqual(side.accepted_count, 1)
                self.assertEqual(side.assessed_count, 1)
        self.assertEqual(comparison.ambiguous_attribution_count, 0)
        self.assertEqual(comparison.unattributed_assessed_count, 0)

    def test_an_unassessed_pair_reports_an_empty_judgement_column(self) -> None:
        """Eligibility is about the pair existing; judgement is about a person."""
        self._accept_both()

        [comparison] = (
            ResearchPairedProviderQualityEvaluator()
            .evaluate(self.manager.list())
            .comparisons
        )

        self.assertEqual(comparison.assessed_count, 0)
        for side in comparison.sides:
            with self.subTest(provider=side.provider):
                self.assertEqual(side.accepted_count, 1)
                self.assertEqual(side.assessed_count, 0)
                self.assertEqual(side.usefulness, {})
        self.assertEqual(self.manager.get(self.run_id).assessments, ())

    def test_the_paired_report_names_no_winner_and_no_combined_score(self) -> None:
        self._accept_both()
        self._assess_both()

        rendered = " ".join(
            ResearchPairedProviderQualityEvaluator()
            .evaluate(self.manager.list())
            .lines()
        ).casefold()

        self.assertIn(PAIRED_SELECTION_BIAS_NOTICE.casefold(), rendered)
        self.assertIn(PAIRED_NO_POLICY_NOTICE.casefold(), rendered)
        for forbidden in ("winner", "recommended", "combined score", "overall score"):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, rendered)

    def test_an_unassessed_source_stays_unknown_rather_than_authoritative(
        self,
    ) -> None:
        self._accept_both()
        document_id = self._source_for(DETAIL_URL).document_id
        run = self.manager.add_evidence(
            self.run_id, self._first_chunk(document_id), "A note."
        )

        run = self.manager.record_source_assessment(
            self.run_id,
            document_id,
            [run.evidence[-1].evidence_id],
            "Recorded without judging it.",
        )

        [assessment] = run.assessments
        self.assertIs(assessment.usefulness, ResearchSourceUsefulness.UNKNOWN)
        self.assertIs(assessment.applicability, ResearchSourceApplicability.UNKNOWN)
        self.assertIs(assessment.independence, ResearchSourceIndependence.UNKNOWN)


class RestartTests(PairedJourneyFixture):
    def test_both_sources_survive_a_restart_with_their_own_provenance(self) -> None:
        """The provenance fixed in 0.3.225, asserted across the paired journey."""
        self._accept_both()

        restored_engine = KnowledgeEngine()
        status = ResearchSourceContentRestorer(
            JsonFileResearchSourceContentStore(self.content_path),
            restored_engine,
        ).restore(self.manager.list())

        self.assertTrue(status.available)
        self.assertEqual(status.restored_document_count, 2)
        metadata = {
            document.source: restored_engine.remove_document(
                document.document_id
            ).metadata
            for document in list(restored_engine.documents())
        }
        self.assertEqual(metadata[DETAIL_URL]["acquisition"], NVD_API_ACQUISITION)
        self.assertEqual(metadata[DETAIL_URL]["content_resource"], NVD_CVE_ENDPOINT)
        self.assertEqual(metadata[DOI_URL]["acquisition"], HTTPS_ACQUISITION)
        self.assertNotIn("content_resource", metadata[DOI_URL])

    def test_restoration_creates_no_duplicate_and_keeps_the_comparison_join(
        self,
    ) -> None:
        self._accept_both()

        restored_engine = KnowledgeEngine()
        ResearchSourceContentRestorer(
            JsonFileResearchSourceContentStore(self.content_path),
            restored_engine,
        ).restore(self.manager.list())

        self.assertEqual(len(restored_engine.documents()), 2)
        report = ResearchProviderComparisonBuilder().build(
            self.manager.get(self.run_id)
        )
        sides = {side.provider: side for side in report.sides}
        self.assertEqual(sides["crossref"].accepted_count, 1)
        self.assertEqual(sides["nvd"].accepted_count, 1)

    def test_a_reopened_run_still_shows_both_sources(self) -> None:
        self._accept_both()

        reopened = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        reopened.load()

        run = reopened.get(self.run_id)
        self.assertEqual(
            sorted(source.url for source in run.sources), sorted((DOI_URL, DETAIL_URL))
        )


if __name__ == "__main__":
    unittest.main()
