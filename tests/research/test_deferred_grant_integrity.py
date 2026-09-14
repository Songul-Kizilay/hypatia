"""What a stored grant's version means, and what a pending one will carry.

Two separate failures, both about a record or a screen saying something it
could not actually know.

The store declared a schema version and then ignored it. Entry shape was
validated against "either known field set", so a document could call itself
version 1 — the version written before restrictions were recorded at all — while
carrying the version 2 restriction field, and be believed about it. The reverse
passed too. A version marker that constrains nothing is decoration, and the one
thing it exists to guarantee is that the reader knows which format it is
holding.

The confirmation screen had the mirror-image problem. Before a grant exists
there is no snapshot to report, so it answered "no grant" — true, and useless
in the place where somebody is deciding whether to authorize unattended
execution. What they need is what the grant *would* carry. Reporting the
absence of the record instead reads as the absence of a restriction, which is
the permissive misreading.

So there are three distinct facts here and none of them may borrow another's
wording: what a grant would carry, what an existing grant does carry, and that
an old grant never recorded it at all.

Deterministic. No network, no model, no execution.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from cognition.TrustedDeferredExecutionControlService import (
    TrustedDeferredExecutionControlService,
)
from core.Exceptions import ResearchError
from research.JsonFileDeferredExecutionGrantStore import (
    JsonFileDeferredExecutionGrantStore,
)
from research.ResearchPlanAuthorization import restrictions_of
from tests.research.test_deferred_execution_grants import NOW, Context
from tests.research.test_deferred_grant_restriction_snapshot import (
    NO_EXTERNAL,
    restricted_context,
    schema_one_document,
)


def schema_two_document(context: Context, restrictions: list[str]) -> dict:
    """The current shape: schema 2, restrictions recorded explicitly."""
    document = schema_one_document(context)
    document["schema_version"] = 2
    document["grants"][0]["approved_restrictions"] = restrictions
    return document


def load(document: dict):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "grants.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return JsonFileDeferredExecutionGrantStore(path).load()


class TheDeclaredVersionDecidesTheShapeTests(unittest.TestCase):
    """Not the other way round, which is how the record got believed."""

    def test_case_d4_a_genuine_legacy_document_loads(self) -> None:
        [grant] = load(schema_one_document(Context()))

        self.assertIsNone(grant.approved_restrictions)
        self.assertFalse(grant.records_restrictions)

    def test_case_d5_a_current_document_with_an_empty_set_loads_as_recorded(
        self,
    ) -> None:
        """Recorded-empty is a claim; legacy-unrecorded is the absence of one."""
        [grant] = load(schema_two_document(Context(), []))

        self.assertEqual(grant.approved_restrictions, frozenset())
        self.assertTrue(grant.records_restrictions)

    def test_a_current_document_carrying_a_restriction_loads(self) -> None:
        [grant] = load(schema_two_document(Context(), ["no_external_source_access"]))

        self.assertEqual(grant.approved_restrictions, frozenset({NO_EXTERNAL}))

    def test_case_d1_legacy_version_carrying_the_newer_field_is_refused(self) -> None:
        """The dangerous direction: a version that never recorded restrictions."""
        document = schema_one_document(Context())
        document["grants"][0]["approved_restrictions"] = ["no_external_source_access"]

        with self.assertRaises(ResearchError):
            load(document)

    def test_case_d2_current_version_missing_the_current_field_is_refused(
        self,
    ) -> None:
        document = schema_one_document(Context())
        document["schema_version"] = 2

        with self.assertRaises(ResearchError):
            load(document)

    def test_case_d3_an_unknown_future_schema_is_refused(self) -> None:
        document = schema_two_document(Context(), [])
        document["schema_version"] = 3

        with self.assertRaises(ResearchError):
            load(document)

    def test_an_unknown_extra_field_is_refused(self) -> None:
        document = schema_two_document(Context(), [])
        document["grants"][0]["unexpected"] = "value"

        with self.assertRaises(ResearchError):
            load(document)

    def test_a_malformed_restriction_container_is_refused(self) -> None:
        document = schema_two_document(Context(), [])
        document["grants"][0]["approved_restrictions"] = "no_external_source_access"

        with self.assertRaises(ResearchError):
            load(document)

    def test_an_unknown_restriction_value_is_refused(self) -> None:
        document = schema_two_document(Context(), ["no_such_restriction"])

        with self.assertRaises(ResearchError):
            load(document)

    def test_every_readable_version_declares_its_own_shape(self) -> None:
        """A version without a declared shape must be unreadable, not lenient."""
        from research.JsonFileDeferredExecutionGrantStore import (
            _ENTRY_FIELDS_BY_VERSION,
            _READABLE_SCHEMA_VERSIONS,
        )

        self.assertEqual(_READABLE_SCHEMA_VERSIONS, frozenset(_ENTRY_FIELDS_BY_VERSION))


class ReadingALegacyGrantRewritesNothingTests(unittest.TestCase):
    def test_loading_leaves_the_document_byte_identical(self) -> None:
        """No migration on read: no upgrade, no fabricated snapshot."""
        original = json.dumps(schema_one_document(Context()))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grants.json"
            path.write_text(original, encoding="utf-8")

            JsonFileDeferredExecutionGrantStore(path).load()

            self.assertEqual(path.read_text(encoding="utf-8"), original)


class ThePendingGrantIsDescribedTruthfullyTests(unittest.TestCase):
    """Driven through the real service, which is where the plan is known."""

    def _service(self, context: Context, directory: str):
        return TrustedDeferredExecutionControlService(
            context,
            JsonFileDeferredExecutionGrantStore(Path(directory) / "grants.json"),
            clock=lambda: NOW,
            id_factory=lambda: "grant-1",
        )

    def _preview(self, context: Context):
        with tempfile.TemporaryDirectory() as directory:
            return self._service(context, directory).preview("task-1")

    def test_a_restricted_pending_plan_names_what_will_be_granted(self) -> None:
        view = self._preview(restricted_context())

        self.assertEqual(
            view.restriction_line,
            "Restrictions to be granted: no_external_source_access",
        )

    def test_a_restricted_pending_plan_never_answers_no_grant(self) -> None:
        """The exact defect: absence of a record read as absence of a limit."""
        view = self._preview(restricted_context())

        self.assertNotIn("no grant", view.restriction_line)
        self.assertIn("no_external_source_access", view.confirmation_text())

    def test_an_unrestricted_pending_plan_says_none_not_no_grant(self) -> None:
        """Two different facts, kept apart."""
        view = self._preview(Context())

        self.assertEqual(view.restriction_line, "Restrictions to be granted: none")

    def test_the_pending_answer_comes_from_the_plan(self) -> None:
        context = restricted_context()

        view = self._preview(context)

        self.assertEqual(view.pending_restrictions, restrictions_of(context.plan))

    def test_advisory_wording_alone_grants_no_pending_restriction(self) -> None:
        from dataclasses import replace

        from research.ResearchPlanConstraint import ResearchPlanConstraint
        from research.ResearchPlanExecutionState import ResearchPlanExecutionState

        context = Context()
        context.plan = replace(
            context.plan,
            constraints=(
                ResearchPlanConstraint(text="Do not access external sources."),
            ),
        )
        context.execution = ResearchPlanExecutionState.prepare(context.plan).start()

        view = self._preview(context)

        self.assertEqual(view.pending_restrictions, frozenset())
        self.assertEqual(view.restriction_line, "Restrictions to be granted: none")

    def test_the_view_accepts_no_separate_restriction_argument(self) -> None:
        """It is derived, so it cannot be typed wider than the plan."""
        import inspect

        parameters = inspect.signature(
            TrustedDeferredExecutionControlService.preview
        ).parameters

        self.assertEqual(list(parameters), ["self", "task_id"])


class PreviewingCreatesNothingTests(unittest.TestCase):
    def test_preview_writes_no_grant_and_no_file(self) -> None:
        context = restricted_context()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grants.json"
            service = TrustedDeferredExecutionControlService(
                context,
                JsonFileDeferredExecutionGrantStore(path),
                clock=lambda: NOW,
                id_factory=lambda: "grant-1",
            )

            view = service.preview("task-1")

            self.assertIsNone(view.grant)
            self.assertFalse(path.exists())

    def test_preview_spends_no_allowance(self) -> None:
        context = restricted_context()
        before = context.allowance
        with tempfile.TemporaryDirectory() as directory:
            TrustedDeferredExecutionControlService(
                context,
                JsonFileDeferredExecutionGrantStore(Path(directory) / "grants.json"),
                clock=lambda: NOW,
                id_factory=lambda: "grant-1",
            ).preview("task-1")

        self.assertEqual(context.allowance, before)

    def test_preview_leaves_the_plan_digest_alone(self) -> None:
        from research.ResearchPlanDigest import plan_digest

        context = restricted_context()
        before = plan_digest(context.plan)
        with tempfile.TemporaryDirectory() as directory:
            TrustedDeferredExecutionControlService(
                context,
                JsonFileDeferredExecutionGrantStore(Path(directory) / "grants.json"),
                clock=lambda: NOW,
                id_factory=lambda: "grant-1",
            ).preview("task-1")

        self.assertEqual(plan_digest(context.plan), before)


class AnExistingGrantStillSpeaksForItselfTests(unittest.TestCase):
    """Post-grant must read the record, not re-derive from the plan."""

    def _granted(self, context: Context):
        with tempfile.TemporaryDirectory() as directory:
            return TrustedDeferredExecutionControlService(
                context,
                JsonFileDeferredExecutionGrantStore(Path(directory) / "grants.json"),
                clock=lambda: NOW,
                id_factory=lambda: "grant-1",
            ).grant("task-1")

    def test_a_granted_restriction_is_reported_as_approved(self) -> None:
        view = self._granted(restricted_context())

        self.assertEqual(
            view.restriction_line, "Approved restrictions: no_external_source_access"
        )

    def test_a_recorded_empty_grant_reads_as_none(self) -> None:
        view = self._granted(Context())

        self.assertEqual(view.restriction_line, "Approved restrictions: none")

    def test_a_legacy_grant_reads_as_unavailable_not_none(self) -> None:
        """Unknown stays unknown, even though "none" would look tidier."""
        from dataclasses import replace

        from research.DeferredExecutionControlView import (
            DeferredExecutionControlView,
        )

        granted = self._granted(restricted_context())
        legacy = replace(
            granted,
            grant=replace(granted.grant, approved_restrictions=None),
        )
        assert isinstance(legacy, DeferredExecutionControlView)

        self.assertEqual(
            legacy.restriction_line,
            "Approved restrictions: unavailable for legacy grant",
        )

    def test_the_existing_grant_answer_ignores_the_pending_one(self) -> None:
        """Otherwise a stale plan could speak for a recorded grant."""
        from dataclasses import replace

        granted = self._granted(restricted_context())
        contradicted = replace(granted, pending_restrictions=frozenset())

        self.assertEqual(
            contradicted.restriction_line,
            "Approved restrictions: no_external_source_access",
        )


if __name__ == "__main__":
    unittest.main()
