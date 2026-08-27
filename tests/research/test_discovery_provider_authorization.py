"""An approval names the host it will contact, or it authorizes nothing new.

Adding a provider adds a network destination, which is the one kind of change
that cannot ride along inside an existing approval. So the provider is part of
what a plan digest covers: an approval recorded for a scholarly search fails to
verify against a plan aimed at a vulnerability database, and it fails closed
rather than by coincidence.

The rest is about the things provider choice must not become — a URL, a string
from a model, a fallback when the chosen provider says no.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDigest import canonical_plan_bytes, plan_digest
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.SourceDiscoveryStepOperation import SourceDiscoveryStepOperation

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def plan(
    provider: ResearchDiscoveryProviderName | None = None,
    *,
    plan_id: str = "plan-1",
) -> ResearchPlan:
    return ResearchPlan(
        plan_id=plan_id,
        question="HTTP request smuggling in Next.js middleware",
        steps=(
            ResearchPlanStep(
                step_id="step-1",
                instruction="Discover candidate sources.",
                capability=ResearchPlanStepCapability.SOURCE_DISCOVERY,
                discovery_provider=provider,
            ),
        ),
        created_at=NOW,
    )


class RecordingProvider:
    def __init__(self, name: str) -> None:
        self.provider_name = name
        self.queries: list[str] = []

    def discover(self, query: str, *, limit: int) -> list[ResearchSourceCandidate]:
        self.queries.append(query)
        return [
            ResearchSourceCandidate(
                url=f"https://example.test/{self.provider_name}",
                title=f"Result from {self.provider_name}",
                snippet="",
            )
        ]


class DigestBindingTests(unittest.TestCase):
    def test_the_same_plan_with_a_different_provider_is_a_different_plan(
        self,
    ) -> None:
        """The load-bearing one: an approval cannot drift to another host."""
        crossref = plan_digest(plan(ResearchDiscoveryProviderName.CROSSREF))
        nvd = plan_digest(plan(ResearchDiscoveryProviderName.NVD))

        self.assertNotEqual(crossref, nvd)

    def test_naming_a_provider_differs_from_naming_none(self) -> None:
        unnamed = plan_digest(plan(None))

        self.assertNotIn(
            unnamed,
            {
                plan_digest(plan(ResearchDiscoveryProviderName.CROSSREF)),
                plan_digest(plan(ResearchDiscoveryProviderName.NVD)),
            },
        )

    def test_the_provider_is_inside_the_bytes_the_digest_covers(self) -> None:
        canonical = canonical_plan_bytes(plan(ResearchDiscoveryProviderName.NVD))

        self.assertIn(b"discovery_provider", canonical)
        self.assertIn(b"nvd", canonical)

    def test_the_digest_schema_moved_so_old_approvals_fail_closed(self) -> None:
        canonical = canonical_plan_bytes(plan(ResearchDiscoveryProviderName.NVD))

        self.assertIn(b"hypatia:research-plan-digest:v2", canonical)
        self.assertNotIn(b"hypatia:research-plan-digest:v1", canonical)

    def test_the_same_plan_digests_identically_every_time(self) -> None:
        first = plan_digest(plan(ResearchDiscoveryProviderName.NVD))
        second = plan_digest(plan(ResearchDiscoveryProviderName.NVD))

        self.assertEqual(first, second)


class ProviderVocabularyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ResearchPlanDraftService(
            id_factory=lambda: "plan-1", clock=lambda: NOW
        )

    def draft(self, provider: object) -> object:
        return self.service.preview(
            "Find the vulnerability",
            (
                ResearchPlanStepDraftInput(
                    instruction="Discover candidate sources.",
                    capability="source_discovery",
                    discovery_provider=provider,  # type: ignore[arg-type]
                ),
            ),
        )

    def test_a_named_provider_is_accepted(self) -> None:
        for name in ("crossref", "nvd"):
            with self.subTest(provider=name):
                preview = self.draft(name)
                self.assertTrue(preview.allowed)
                assert preview.plan is not None
                self.assertEqual(preview.plan.steps[0].discovery_provider.value, name)

    def test_a_url_is_never_a_provider(self) -> None:
        """The field decides a network destination, so it is never free text."""
        for value in (
            "https://attacker.example/rest/json",
            "http://127.0.0.1:8080",
            "nvd; crossref",
            "NVD",
            "",
        ):
            with self.subTest(provider=value):
                self.assertFalse(self.draft(value).allowed)

    def test_a_non_string_provider_is_refused(self) -> None:
        for value in (42, ["nvd"], {"name": "nvd"}):
            with self.subTest(provider=value):
                self.assertFalse(self.draft(value).allowed)

    def test_only_a_discovery_step_may_name_a_provider(self) -> None:
        """A provider on a step that cannot discover authorizes an unreachable host."""
        with self.assertRaises(ResearchError):
            ResearchPlanStep(
                step_id="step-1",
                instruction="Record evidence.",
                capability=ResearchPlanStepCapability.NONE,
                discovery_provider=ResearchDiscoveryProviderName.NVD,
            )


class ExecutionRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.crossref = RecordingProvider("crossref")
        self.nvd = RecordingProvider("nvd")
        self.operation = SourceDiscoveryStepOperation(
            self.crossref,  # type: ignore[arg-type]
            _RecordingRunManager(),  # type: ignore[arg-type]
            providers={
                # type: ignore[dict-item]
                ResearchDiscoveryProviderName.CROSSREF: self.crossref,
                # type: ignore[dict-item]
                ResearchDiscoveryProviderName.NVD: self.nvd,
            },
        )

    def step(self, provider: ResearchDiscoveryProviderName | None) -> ResearchPlanStep:
        return plan(provider).steps[0]

    def test_a_step_naming_nvd_reaches_nvd_and_not_crossref(self) -> None:
        self.operation.run(self.step(ResearchDiscoveryProviderName.NVD), _context())

        self.assertEqual(len(self.nvd.queries), 1)
        self.assertEqual(self.crossref.queries, [])

    def test_a_step_naming_crossref_reaches_crossref_and_not_nvd(self) -> None:
        self.operation.run(
            self.step(ResearchDiscoveryProviderName.CROSSREF), _context()
        )

        self.assertEqual(len(self.crossref.queries), 1)
        self.assertEqual(self.nvd.queries, [])

    def test_a_step_naming_nothing_keeps_the_wired_provider(self) -> None:
        """Which is what every plan approved before providers were nameable meant."""
        self.operation.run(self.step(None), _context())

        self.assertEqual(len(self.crossref.queries), 1)
        self.assertEqual(self.nvd.queries, [])

    def test_an_unavailable_provider_fails_rather_than_substituting(self) -> None:
        operation = SourceDiscoveryStepOperation(
            self.crossref,  # type: ignore[arg-type]
            _RecordingRunManager(),  # type: ignore[arg-type]
            providers={
                # type: ignore[dict-item]
                ResearchDiscoveryProviderName.CROSSREF: self.crossref,
            },
        )

        with self.assertRaises(ResearchError):
            operation.run(self.step(ResearchDiscoveryProviderName.NVD), _context())

        self.assertEqual(self.crossref.queries, [])
        self.assertEqual(self.nvd.queries, [])

    def test_one_advance_queries_exactly_one_provider(self) -> None:
        """Never both, and never a second one after the first disappoints."""
        self.operation.run(self.step(ResearchDiscoveryProviderName.NVD), _context())

        self.assertEqual(len(self.nvd.queries) + len(self.crossref.queries), 1)


class _RecordingRunManager:
    """The smallest run manager the discovery step needs."""

    def __init__(self) -> None:
        self.discoveries: list[tuple[str, str]] = []

    def get(self, run_id: str) -> object:
        return _Run()

    def add_discovery(
        self,
        run_id: str,
        question: str,
        provider: str,
        candidates: object,
    ) -> object:
        self.discoveries.append((provider, question))
        return _Run()

    def record_failure(self, *args: object, **kwargs: object) -> None:
        return None


class _Run:
    run_id = "run-1"
    question = "HTTP request smuggling in Next.js middleware"

    class status:
        terminal = False


def _context() -> object:
    class Context:
        research_run_id = "run-1"
        cancelled = False

    return Context()


if __name__ == "__main__":
    unittest.main()
