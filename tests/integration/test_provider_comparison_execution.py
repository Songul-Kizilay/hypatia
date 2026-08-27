"""Driving one comparison plan through the ordinary execution machinery.

Everything else about this milestone was proved against the plan, the digest and
the cost table. This is the chain those pieces are supposed to add up to, driven
end to end through the real discovery operation with a provider on each side:
starting reaches nobody, one press reaches Crossref, the second press is what
reaches NVD, and an approval that only covers one network operation stops the
second before a request rather than after it.

The fixture is the existing foreground-execution one, unchanged, because a
comparison is an ordinary plan. If it needed its own harness it would not be a
comparison of ordinary steps; it would be a second execution path.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from research.ProviderComparisonRequest import ProviderComparisonRequest
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.SourceDiscoveryStepOperation import SourceDiscoveryStepOperation
from tests.integration.test_foreground_execution_control import ForegroundFixture


class RecordingProvider:
    """A provider that counts requests without making any."""

    def __init__(self, name: str, url: str) -> None:
        self.provider_name = name
        self._url = url
        self.queries: list[str] = []

    def discover(self, query: str, *, limit: int) -> list[ResearchSourceCandidate]:
        self.queries.append(query)
        return [
            ResearchSourceCandidate(
                url=self._url,
                title=f"Result from {self.provider_name}",
                snippet="",
            )
        ]


class ProviderComparisonExecutionTests(ForegroundFixture):
    def setUp(self) -> None:
        super().setUp()
        self.crossref = RecordingProvider(
            ResearchDiscoveryProviderName.CROSSREF.value,
            "https://doi.org/10.1000/paper",
        )
        self.nvd = RecordingProvider(
            ResearchDiscoveryProviderName.NVD.value,
            "https://nvd.nist.gov/vuln/detail/CVE-2025-29927",
        )
        self.steps = ProviderComparisonRequest().step_drafts()

    def comparison_service(self) -> object:
        registry = ResearchPlanOperationRegistry()
        registry.register(
            ResearchPlanStepCapability.SOURCE_DISCOVERY,
            SourceDiscoveryStepOperation(
                self.crossref,  # type: ignore[arg-type]
                self.manager,
                providers={
                    ResearchDiscoveryProviderName.CROSSREF: self.crossref,
                    ResearchDiscoveryProviderName.NVD: self.nvd,
                },  # type: ignore[arg-type]
            ),
        )
        return self.execution_service(registry)

    @property
    def requests_made(self) -> int:
        return len(self.crossref.queries) + len(self.nvd.queries)

    def test_starting_a_comparison_reaches_no_provider(self) -> None:
        execution = self.comparison_service()

        self.start(execution, self.steps)

        self.assertEqual(self.requests_made, 0)

    def test_the_first_advance_reaches_one_provider_only(self) -> None:
        execution = self.comparison_service()
        execution_id = self.start(execution, self.steps)

        self.advance(execution, execution_id)

        self.assertEqual(len(self.crossref.queries), 1)
        self.assertEqual(self.nvd.queries, [])

    def test_the_second_provider_needs_a_second_explicit_advance(self) -> None:
        execution = self.comparison_service()
        execution_id = self.start(execution, self.steps)

        self.advance(execution, execution_id)
        self.advance(execution, execution_id)

        self.assertEqual(len(self.crossref.queries), 1)
        self.assertEqual(len(self.nvd.queries), 1)

    def test_both_sides_were_asked_the_identical_question(self) -> None:
        """Not enforced anywhere: the question belongs to the run."""
        execution = self.comparison_service()
        execution_id = self.start(execution, self.steps)

        self.advance(execution, execution_id)
        self.advance(execution, execution_id)

        self.assertEqual(self.crossref.queries, self.nvd.queries)

    def test_two_discoveries_charge_two_network_operations(self) -> None:
        execution = self.comparison_service()
        execution_id = self.start(execution, self.steps)

        self.advance(execution, execution_id)
        self.advance(execution, execution_id)

        allowance = execution.allowance(execution_id)
        assert allowance is not None
        self.assertEqual(allowance.spend.network_operations, 2)
        self.assertEqual(allowance.spend.step_advances, 2)

    def test_a_budget_for_one_operation_stops_the_second_before_the_request(
        self,
    ) -> None:
        """Refused before the attempt, so the second provider is never reached."""
        execution = self.comparison_service()
        execution_id = self.start(
            execution,
            self.steps,
            budget=ResearchAutonomyBudget(
                max_step_advances=3,
                max_network_operations=1,
                max_llm_operations=0,
                max_seconds=60.0,
            ),
        )

        first = self.advance(execution, execution_id)
        second = self.advance(execution, execution_id)

        self.assertTrue(first.success)
        self.assertFalse(second.success)
        self.assertEqual(len(self.crossref.queries), 1)
        self.assertEqual(self.nvd.queries, [])
        allowance = execution.allowance(execution_id)
        assert allowance is not None
        self.assertEqual(allowance.spend.network_operations, 1)

    def test_an_unaffordable_second_side_refunds_nothing(self) -> None:
        execution = self.comparison_service()
        execution_id = self.start(
            execution,
            self.steps,
            budget=ResearchAutonomyBudget(
                max_step_advances=3,
                max_network_operations=1,
                max_llm_operations=0,
                max_seconds=60.0,
            ),
        )

        self.advance(execution, execution_id)
        self.advance(execution, execution_id)

        allowance = execution.allowance(execution_id)
        assert allowance is not None
        self.assertEqual(allowance.remaining_network_operations, 0)

    def test_cancelling_after_one_side_keeps_what_that_side_produced(self) -> None:
        execution = self.comparison_service()
        execution_id = self.start(execution, self.steps)

        self.advance(execution, execution_id)
        self.cancel(execution, execution_id)
        self.advance(execution, execution_id)

        self.assertEqual(len(self.crossref.queries), 1)
        self.assertEqual(self.nvd.queries, [])
        run = self.manager.get(self.run_id)
        self.assertEqual(len(run.discoveries), 1)
        self.assertEqual(
            run.discoveries[0].provider, ResearchDiscoveryProviderName.CROSSREF.value
        )

    def test_each_side_is_recorded_as_its_own_discovery(self) -> None:
        execution = self.comparison_service()
        execution_id = self.start(execution, self.steps)

        self.advance(execution, execution_id)
        self.advance(execution, execution_id)

        run = self.manager.get(self.run_id)
        self.assertEqual(
            [discovery.provider for discovery in run.discoveries],
            [
                ResearchDiscoveryProviderName.CROSSREF.value,
                ResearchDiscoveryProviderName.NVD.value,
            ],
        )
        self.assertEqual(
            len({discovery.discovery_id for discovery in run.discoveries}), 2
        )


if __name__ == "__main__":
    unittest.main()
