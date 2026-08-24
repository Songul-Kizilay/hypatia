"""Project canonical research state into something an ordinary person can read.

Simple mode is a projection, not a second research engine. Everything here is a
pure function of one immutable `ResearchRun` snapshot plus, at most, a transient
activity. There is no store, no service call, no cache, and no writable field,
so there is nowhere for the interface to keep a belief that canonical state does
not support. When a caller wants fresher answers it re-reads the run and builds
this again.

That constraint is what makes the simplification safe. The simplifying happens
in the wording and the layout; the facts are the same facts the audit view
shows, and each one is still derived from a persisted record rather than from
what a button press was supposed to achieve.

Two distinctions are preserved here even though collapsing them would make the
interface tidier. A discovered candidate is not a fetched source, so it is never
shown as loaded. An accepted source is not evidence, so a run with sources and
no evidence says exactly that rather than reporting itself finished.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from desktop.SimpleResearchActivity import SimpleResearchActivity
from desktop.SimpleResearchPhrasebook import phrase, stage_phrase
from desktop.SimpleResearchStep import SimpleResearchStep
from desktop.SimpleSourceCard import SimpleSourceCard
from research.ResearchRun import ResearchRun
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.SourceIdentity import identity_of
from research.SourceLoadStage import SourceLoadStage
from response.ResponseLanguage import ResponseLanguage


@dataclass(frozen=True, slots=True)
class SimpleResearchReadModel:
    """Render one run snapshot in ordinary language, hiding its identifiers."""

    run: ResearchRun | None
    language: ResponseLanguage = ResponseLanguage.ENGLISH
    activity: SimpleResearchActivity = SimpleResearchActivity.IDLE
    last_stage: SourceLoadStage | None = None

    @property
    def step(self) -> SimpleResearchStep:
        """Return the canonical step, which no button press can advance."""
        return SimpleResearchStep.for_run(self.run)

    def say(self, key: str) -> str:
        """Look up one fixed string in the current language."""
        return phrase(key, self.language)

    def question_text(self) -> str:
        """Return the run's question, or the prompt inviting one."""
        if self.run is None:
            return self.say("no_question_yet")
        return self.run.question

    def status_text(self) -> str:
        """Return the one line describing where this research stands.

        An in-flight activity is reported as an activity and never as a step, so
        "Finding sources..." can never be read as "sources found".
        """
        if self.activity.in_flight:
            return self.say(f"activity_{self.activity.value}")
        if self.run is None:
            return self.say("no_question_yet")
        if self.step is SimpleResearchStep.QUESTION_CREATED:
            if self.run.discoveries:
                return self.say("discovery_found_nothing")
            return self.say("no_sources_yet")
        return self.say(f"step_{self.step.value}")

    def ladder(self) -> tuple[tuple[str, bool], ...]:
        """Return each visible step with whether canonical state reached it."""
        reached = self.step.reached_by
        return tuple(
            (self.say(f"step_{candidate.value}"), candidate in reached)
            for candidate in SimpleResearchStep.ladder()
        )

    def stage_text(self) -> str:
        """Return the plain sentence for the most recent load, if there was one.

        `INDEXED_WITHOUT_RUN` renders as a sentence saying the source was not
        added. It must never render as "Loaded": a local document really does
        exist, which is exactly why that outcome is the one most easily mistaken
        for success.
        """
        if self.last_stage is None:
            return ""
        return stage_phrase(self.last_stage, self.language)

    def evidence_text(self) -> str:
        """State whether evidence exists, without implying what it proves."""
        if self.run is None or not self.run.evidence:
            return self.say("evidence_none")
        return self.say("evidence_present")

    def accepted_identities(self) -> frozenset[str]:
        """Return canonical resource identities the run actually accepted."""
        if self.run is None:
            return frozenset()
        return frozenset(identity_of(source.url) for source in self.run.sources)

    def candidate_cards(self) -> tuple[SimpleSourceCard, ...]:
        """Project the latest discovery's candidates as readable cards.

        Only the most recent discovery is shown. Older ones remain in canonical
        state and in the audit view; repeating them here would present the same
        resource several times, and a list that shows one source twice is the
        shape a person reads as two independent sources.
        """
        if self.run is None or not self.run.discoveries:
            return ()
        latest = self.run.discoveries[-1]
        accepted = self.accepted_identities()
        documents = self._documents_by_identity()
        cards: list[SimpleSourceCard] = []
        seen: set[str] = set()
        for candidate in latest.candidates:
            identity = identity_of(candidate.url)
            if identity in seen:
                continue
            seen.add(identity)
            cards.append(self._card(candidate, identity in accepted, documents))
        return tuple(cards)

    def accepted_cards(self) -> tuple[SimpleSourceCard, ...]:
        """Project every source the run canonically accepted."""
        if self.run is None:
            return ()
        return tuple(
            SimpleSourceCard(
                title=source.title or self.site_of(source.url) or source.url,
                site=self.site_of(source.url),
                status_text=self.say("candidate_accepted"),
                accepted=True,
                url=source.url,
                document_id=source.document_id,
            )
            for source in self.run.sources
        )

    def advanced_details(self) -> tuple[tuple[str, str], ...]:
        """Return the identifiers Simple mode hides, labelled and unchanged.

        Nothing is abbreviated, hashed, or prettified here. The audit view and
        this panel must agree exactly, or the hiding becomes a second version of
        the truth rather than a smaller view of the same one.
        """
        if self.run is None:
            return ()
        rows = [(self.say("advanced_run_id"), self.run.run_id)]
        if self.run.discoveries:
            rows.append(
                (
                    self.say("advanced_discovery_id"),
                    self.run.discoveries[-1].discovery_id,
                )
            )
        for source in self.run.sources:
            rows.append((self.say("advanced_document_id"), source.document_id))
            rows.append((self.say("advanced_url"), source.url))
        if self.last_stage is not None:
            rows.append((self.say("advanced_technical_code"), self.last_stage.value))
        return tuple(rows)

    def hides_identifiers(self) -> bool:
        """Return whether any visible text carries a technical identifier.

        This is asserted rather than assumed, because the identifiers leak by
        accident — a title that happens to be a URL, a status that interpolates
        a document ID — and the promise Simple mode makes is exactly this one.
        """
        visible = " ".join(
            [self.status_text(), self.evidence_text(), self.stage_text()]
            + [text for text, _ in self.ladder()]
            + [card.heading for card in self.candidate_cards()]
            + [card.status_text for card in self.candidate_cards()]
        )
        return not any(
            identifier and identifier in visible
            for _, identifier in self.advanced_details()
        )

    def _documents_by_identity(self) -> dict[str, str]:
        if self.run is None:
            return {}
        return {
            identity_of(source.url): source.document_id for source in self.run.sources
        }

    def _card(
        self,
        candidate: ResearchSourceCandidate,
        accepted: bool,
        documents: dict[str, str],
    ) -> SimpleSourceCard:
        identity = identity_of(candidate.url)
        return SimpleSourceCard(
            title=candidate.title,
            site=self.site_of(candidate.url),
            status_text=self.say(
                "candidate_accepted" if accepted else "candidate_discovered"
            ),
            accepted=accepted,
            url=candidate.url,
            document_id=documents.get(identity, "") if accepted else "",
        )

    @staticmethod
    def site_of(url: str) -> str:
        """Return the readable host of a URL, or nothing when it has none.

        The host is the only publication-like fact available. A candidate
        carries a title, a URL, and a snippet, so a journal name or a year would
        have to be guessed at, and a guessed publication year on a research
        source is precisely the kind of confident detail that is worth nothing
        and looks like everything.
        """
        if not isinstance(url, str) or not url.strip():
            return ""
        try:
            host = urlsplit(url.strip()).hostname
        except ValueError:
            return ""
        if not host:
            return ""
        host = host.casefold()
        return host[4:] if host.startswith("www.") else host
