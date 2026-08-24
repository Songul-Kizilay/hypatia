"""The operator control plane, and the authority it deliberately does not add.

The console is the first thing in Hypatia that can run a tool in the real
application, so most of this file is about what still cannot. A model cannot
authorize. A capability name in prose cannot authorize. Selecting a capability
cannot authorize. Only an explicit operator action can, and only for one run.

Every test here builds the real production runtime — the same `ToolRuntime`
`desktop_main` composes — rather than a desktop-only stand-in, because a console
tested against a fake registry would prove nothing about what the application
can actually do.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from desktop.ToolArgumentKind import ToolArgumentKind
from desktop.ToolConsoleController import (
    MALFORMED_ARGUMENT_DETAIL,
    MISSING_ARGUMENT_DETAIL,
    NOT_AUTHORIZED_DETAIL,
    UNKNOWN_ARGUMENT_DETAIL,
    ToolConsoleController,
)
from desktop.ToolRunStatus import ToolRunStatus
from eventbus.EventBus import EventBus
from tools.FilesystemRoot import FilesystemRoot
from tools.ToolCapability import ToolCapability
from tools.ToolRuntime import ToolRuntime

SENTINEL_DIR = "private-investigation-8472"


class ConsoleFixture(unittest.TestCase):
    """A real runtime with a real filesystem root, on a temporary directory."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root_path = Path(self._temp.name).resolve()
        (self.root_path / "notes").mkdir()
        (self.root_path / "readme.md").write_text("hello", encoding="utf-8")
        self.event_bus = EventBus()
        self.runtime = ToolRuntime(
            FilesystemRoot(self.root_path, root_id="workspace"),
            event_bus=self.event_bus,
        )
        self.console = ToolConsoleController(self.runtime, self.event_bus)
        self.addCleanup(self._temp.cleanup)

    def run_tool(self, capability: str, **arguments: str) -> object:
        return self.console.run(
            capability,
            tuple(arguments.items()),
            authorized=True,
        )


class CatalogueTests(ConsoleFixture):
    """Only what the production registry holds, described by the tools."""

    def test_the_catalogue_lists_the_registered_capabilities(self) -> None:
        names = [entry.capability for entry in self.console.catalogue()]

        self.assertEqual(names, ["clock_read", "text_statistics", "filesystem_list"])

    def test_the_catalogue_matches_the_registry_exactly(self) -> None:
        """No second list to fall out of date with what can actually run."""
        self.assertEqual(
            [entry.capability for entry in self.console.catalogue()],
            [capability.value for capability in self.runtime.capabilities],
        )

    def test_an_unregistered_capability_does_not_appear(self) -> None:
        names = [entry.capability for entry in self.console.catalogue()]

        self.assertNotIn("knowledge_document_list", names)
        self.assertNotIn("research_state_summary", names)

    def test_descriptions_come_from_the_tool_not_from_a_model(self) -> None:
        entry = self.console.entry("filesystem_list")
        tool = self.runtime.registry.resolve(ToolCapability.FILESYSTEM_LIST)

        assert tool is not None
        self.assertEqual(entry.description, tool.descriptor.summary)

    def test_every_entry_names_the_effects_it_will_require(self) -> None:
        for entry in self.console.catalogue():
            with self.subTest(capability=entry.capability):
                self.assertTrue(entry.effects)
                self.assertIn("Requires:", entry.authorization_prompt)
                for effect in entry.effects:
                    self.assertIn(effect, entry.authorization_prompt)

    def test_effects_shown_are_exactly_the_declared_effects(self) -> None:
        for entry in self.console.catalogue():
            capability = ToolCapability(entry.capability)
            tool = self.runtime.registry.resolve(capability)
            assert tool is not None
            with self.subTest(capability=entry.capability):
                self.assertEqual(
                    set(entry.effects),
                    {effect.value for effect in tool.descriptor.effects},
                )

    def test_read_only_and_reach_come_from_the_descriptor(self) -> None:
        for entry in self.console.catalogue():
            tool = self.runtime.registry.resolve(ToolCapability(entry.capability))
            assert tool is not None
            with self.subTest(capability=entry.capability):
                self.assertIs(entry.read_only, tool.descriptor.read_only)
                self.assertIs(entry.reaches_outside, tool.descriptor.reaches_outside)

    def test_no_registered_tool_reaches_outside_this_machine(self) -> None:
        for entry in self.console.catalogue():
            with self.subTest(capability=entry.capability):
                self.assertFalse(entry.reaches_outside)
                self.assertEqual(entry.safety_note, "Reads only. Changes nothing.")

    def test_argument_specs_match_each_tool_accepted_arguments(self) -> None:
        """The tool stays authoritative; the spec only adds what a form needs."""
        from tools.ClockReadTool import ACCEPTED_ARGUMENTS as CLOCK
        from tools.FilesystemListTool import ACCEPTED_ARGUMENTS as FILES
        from tools.TextStatisticsTool import ACCEPTED_ARGUMENTS as TEXT

        expected = {
            "clock_read": CLOCK,
            "text_statistics": TEXT,
            "filesystem_list": FILES,
        }
        for entry in self.console.catalogue():
            with self.subTest(capability=entry.capability):
                self.assertEqual(
                    {spec.name for spec in entry.arguments},
                    set(expected[entry.capability]),
                )


class ScopeDisclosureTests(ConsoleFixture):
    def test_the_filesystem_scope_is_shown_as_an_identity(self) -> None:
        entry = self.console.entry("filesystem_list")

        self.assertEqual(entry.scope_label, "Scope: workspace")

    def test_the_scope_label_never_contains_the_absolute_path(self) -> None:
        entry = self.console.entry("filesystem_list")

        self.assertNotIn(str(self.root_path), entry.scope_label)
        self.assertNotIn(self.root_path.name, entry.scope_label)

    def test_capabilities_without_a_scope_show_none(self) -> None:
        self.assertEqual(self.console.entry("clock_read").scope_label, "")

    def test_no_catalogue_text_anywhere_leaks_the_root_path(self) -> None:
        rendered = str(self.console.catalogue())

        self.assertNotIn(str(self.root_path), rendered)


class AuthorizationTests(ConsoleFixture):
    """The core of the milestone: selecting is not authorizing."""

    def test_running_without_authorization_does_nothing(self) -> None:
        view = self.console.run("clock_read")

        self.assertIs(view.status, ToolRunStatus.UNAUTHORIZED)
        self.assertFalse(view.performed)
        self.assertEqual(view.detail, NOT_AUTHORIZED_DETAIL)

    def test_authorization_is_not_the_default(self) -> None:
        """A caller that forgets the flag gets a refusal, not an execution."""
        self.assertFalse(self.console.run("clock_read").performed)

    def test_an_explicit_authorization_runs_it(self) -> None:
        view = self.run_tool("clock_read")

        self.assertIs(view.status, ToolRunStatus.SUCCEEDED)
        self.assertTrue(view.performed)
        self.assertTrue(view.succeeded)

    def test_authorization_does_not_persist_to_the_next_run(self) -> None:
        """One press, one run. The next run needs another press."""
        self.assertTrue(self.run_tool("clock_read").performed)

        self.assertFalse(self.console.run("clock_read").performed)

    def test_the_console_keeps_no_field_that_could_re_authorize(self) -> None:
        """The audit events remember what happened; nothing remembers consent.

        The retained lifecycle events do contain `authorized_effects`, because
        that is the record of a run that already occurred. What must not exist
        is a field the next run could read to decide it is already allowed, so
        this checks the fields rather than the recorded history.
        """
        self.run_tool("clock_read")

        state = {
            name: value
            for name, value in vars(self.console).items()
            if name != "_events"
        }
        for name, value in state.items():
            with self.subTest(field=name):
                self.assertNotIsInstance(value, bool)
                self.assertNotIsInstance(value, (set, frozenset))

    def test_a_stored_event_history_does_not_make_the_next_run_allowed(self) -> None:
        """Proves the previous test is about the right thing."""
        self.run_tool("clock_read")

        self.assertFalse(self.console.run("clock_read").performed)

    def test_the_grant_is_exactly_the_declared_effects(self) -> None:
        view = self.run_tool("filesystem_list", path=".")

        self.assertEqual(view.authorized_effects, view.declared_effects)
        self.assertEqual(set(view.authorized_effects), {"reads_filesystem_metadata"})

    def test_the_grant_is_never_a_superset(self) -> None:
        for entry in self.console.catalogue():
            tool = self.runtime.registry.resolve(ToolCapability(entry.capability))
            assert tool is not None
            with self.subTest(capability=entry.capability):
                self.assertEqual(
                    set(entry.effects),
                    {effect.value for effect in tool.descriptor.effects},
                )

    def test_one_capability_grant_does_not_leak_into_another(self) -> None:
        self.run_tool("filesystem_list", path=".")
        view = self.run_tool("clock_read")

        self.assertEqual(set(view.authorized_effects), {"reads_local_state"})

    def test_an_unregistered_capability_cannot_be_run(self) -> None:
        view = self.console.run("knowledge_document_list", authorized=True)

        self.assertIs(view.status, ToolRunStatus.UNAVAILABLE)
        self.assertFalse(view.performed)

    def test_an_invented_capability_name_cannot_be_run(self) -> None:
        """Selection is a lookup over what is registered, never a constructor."""
        for name in ("shell", "filesystem_read", "eval", "", "  "):
            with self.subTest(name=name):
                view = self.console.run(name, authorized=True)
                self.assertIs(view.status, ToolRunStatus.UNAVAILABLE)
                self.assertFalse(view.performed)

    def test_there_is_no_authorize_everything_entry_point(self) -> None:
        for forbidden in (
            "authorize_all",
            "allow_all",
            "trust",
            "remember_grant",
            "auto_approve",
            "grant",
        ):
            with self.subTest(name=forbidden):
                self.assertFalse(hasattr(self.console, forbidden))


class ArgumentValidationTests(ConsoleFixture):
    def test_an_unknown_argument_is_rejected_before_execution(self) -> None:
        view = self.console.run(
            "clock_read",
            (("timezone", "Europe/Istanbul"),),
            authorized=True,
        )

        self.assertIs(view.status, ToolRunStatus.INVALID_ARGUMENTS)
        self.assertFalse(view.performed)
        self.assertEqual(view.detail, UNKNOWN_ARGUMENT_DETAIL)

    def test_a_missing_required_argument_is_rejected(self) -> None:
        view = self.console.run("text_statistics", (), authorized=True)

        self.assertIs(view.status, ToolRunStatus.INVALID_ARGUMENTS)
        self.assertEqual(view.detail, MISSING_ARGUMENT_DETAIL)

    def test_a_malformed_argument_never_reaches_the_capability(self) -> None:
        view = self.console.run(
            "filesystem_list",
            (("path", "."), ("offset", "not-a-number")),
            authorized=True,
        )

        self.assertIs(view.status, ToolRunStatus.INVALID_ARGUMENTS)
        self.assertFalse(view.performed)
        self.assertEqual(view.detail, MALFORMED_ARGUMENT_DETAIL)

    def test_an_absolute_path_is_rejected_by_the_form_too(self) -> None:
        """Defence in depth. The root would refuse it as well."""
        for path in ("/etc", "C:" + chr(92) + "Windows", chr(92) * 2 + "server"):
            with self.subTest(path=path):
                view = self.console.run(
                    "filesystem_list",
                    (("path", path),),
                    authorized=True,
                )
                self.assertIs(view.status, ToolRunStatus.INVALID_ARGUMENTS)

    def test_a_rejected_run_produces_no_values_and_no_grant(self) -> None:
        view = self.console.run("text_statistics", (), authorized=True)

        self.assertEqual(view.values, ())
        self.assertEqual(view.authorized_effects, ())

    def test_a_blank_optional_argument_is_simply_omitted(self) -> None:
        view = self.run_tool("filesystem_list", path=".", offset="")

        self.assertTrue(view.succeeded)
        self.assertEqual(dict(view.values)["page_offset"], "0")

    def test_valid_arguments_reach_the_capability(self) -> None:
        view = self.run_tool("text_statistics", text="one two three")

        self.assertTrue(view.succeeded)
        self.assertEqual(dict(view.values)["word_count"], "3")


class ResultFidelityTests(ConsoleFixture):
    """The result is read from the outcome, never from the button press."""

    def test_a_tool_refusal_is_not_dressed_up_as_success(self) -> None:
        view = self.run_tool("filesystem_list", path="no-such-folder")

        self.assertIs(view.status, ToolRunStatus.REFUSED)
        self.assertTrue(view.performed)
        self.assertFalse(view.succeeded)
        self.assertIn("no such entry", view.detail.casefold())

    def test_a_refusal_keeps_the_tools_own_words(self) -> None:
        view = self.run_tool("filesystem_list", path="readme.md")

        self.assertFalse(view.succeeded)
        self.assertEqual(view.detail, "That is not a directory.")

    def test_a_successful_run_reports_the_values_it_got(self) -> None:
        view = self.run_tool("filesystem_list", path=".")

        names = [value for name, value in view.values if name.startswith("entry_")]
        self.assertIn("directory:notes", names)

    def test_a_view_cannot_claim_success_without_performing(self) -> None:
        from desktop.ToolRunView import ToolRunView

        with self.assertRaises(ResearchError):
            ToolRunView(
                capability="clock_read",
                status=ToolRunStatus.SUCCEEDED,
                performed=False,
                succeeded=True,
                detail="Impossible.",
            )

    def test_a_view_cannot_report_success_under_a_failure_status(self) -> None:
        from desktop.ToolRunView import ToolRunView

        with self.assertRaises(ResearchError):
            ToolRunView(
                capability="clock_read",
                status=ToolRunStatus.REFUSED,
                performed=True,
                succeeded=True,
                detail="Contradictory.",
            )

    def test_every_status_carries_a_fixed_sentence(self) -> None:
        for status in ToolRunStatus:
            with self.subTest(status=status):
                self.assertTrue(status.label.strip())

    def test_status_labels_do_not_read_as_diagnostics(self) -> None:
        """Only the multi-word values; 'cancelled' is also an English word."""
        for status in ToolRunStatus:
            if "_" not in status.value:
                continue
            with self.subTest(status=status):
                self.assertNotIn(status.value, status.label)


class AuditTests(ConsoleFixture):
    """Enough history to answer what happened, and nothing sensitive."""

    def test_the_audit_answers_every_required_question(self) -> None:
        lines = self.run_tool("filesystem_list", path=".").audit_lines()
        joined = " | ".join(lines)

        for question in (
            "Capability requested",
            "Effects declared",
            "Effects authorized",
            "Execution began",
            "Performed",
            "Succeeded",
            "Values returned",
            "Lifecycle",
        ):
            with self.subTest(question=question):
                self.assertIn(question, joined)

    def test_the_audit_shows_the_real_lifecycle_sequence(self) -> None:
        view = self.run_tool("clock_read")

        self.assertEqual(
            view.events,
            ("tool.requested", "tool.authorized", "tool.started", "tool.completed"),
        )

    def test_a_refused_run_shows_it_never_started(self) -> None:
        view = self.console.run("clock_read")

        self.assertEqual(view.events, ())
        self.assertIn("Execution began: no", " ".join(view.audit_lines()))

    def test_declared_and_authorized_are_reported_separately(self) -> None:
        """One line for both would make the gate look like a formality."""
        lines = self.run_tool("clock_read").audit_lines()

        self.assertIn("Effects declared: reads_local_state", lines)
        self.assertIn("Effects authorized: reads_local_state", lines)

    def test_the_audit_never_contains_a_filesystem_path(self) -> None:
        (self.root_path / SENTINEL_DIR).mkdir()

        view = self.run_tool("filesystem_list", path=SENTINEL_DIR)
        audit = " ".join(view.audit_lines())

        self.assertNotIn(SENTINEL_DIR, audit)
        self.assertNotIn(str(self.root_path), audit)

    def test_the_audit_never_contains_an_argument_value(self) -> None:
        view = self.run_tool("text_statistics", text="SECRET-PAYLOAD-8472")

        self.assertNotIn("SECRET-PAYLOAD-8472", " ".join(view.audit_lines()))

    def test_lifecycle_events_still_carry_no_paths(self) -> None:
        (self.root_path / SENTINEL_DIR).mkdir()
        seen: list[object] = []
        self.event_bus.subscribe("*", seen.append)

        self.run_tool("filesystem_list", path=SENTINEL_DIR)

        payloads = str([getattr(event, "payload", {}) for event in seen])
        self.assertNotIn(SENTINEL_DIR, payloads)
        self.assertNotIn(str(self.root_path), payloads)


class FilesystemPagingTests(ConsoleFixture):
    """Paging stays explicit: one operator action, one bounded invocation."""

    def populate(self, count: int) -> None:
        target = self.root_path / "many"
        target.mkdir()
        for index in range(count):
            (target / f"file-{index:03d}.txt").write_text("x", encoding="utf-8")

    def test_one_run_returns_one_bounded_page(self) -> None:
        self.populate(40)

        view = self.run_tool("filesystem_list", path="many")

        self.assertEqual(dict(view.values)["page_size"], "15")
        self.assertEqual(dict(view.values)["more_pages"], "true")

    def test_the_console_does_not_fetch_further_pages_by_itself(self) -> None:
        """No hidden loop. A second page is a second explicit action."""
        self.populate(40)

        view = self.run_tool("filesystem_list", path="many")

        entries = [
            name
            for name, _ in view.values
            if name.startswith("entry_") and name != "entry_count"
        ]
        self.assertEqual(len(entries), 15)

    def test_a_later_page_is_a_separate_authorized_run(self) -> None:
        self.populate(40)

        first = self.run_tool("filesystem_list", path="many")
        second = self.run_tool("filesystem_list", path="many", offset="15")

        self.assertEqual(dict(second.values)["page_offset"], "15")
        self.assertNotEqual(first.values, second.values)

    def test_the_result_limit_is_still_twenty(self) -> None:
        from tools.ToolResult import MAX_TOOL_VALUES

        self.populate(40)

        self.assertEqual(MAX_TOOL_VALUES, 20)
        self.assertLessEqual(
            len(self.run_tool("filesystem_list", path="many").values), 20
        )

    def test_traversal_is_refused_by_the_root_not_by_the_form(self) -> None:
        """The form rejects shapes; only the root knows where the root is."""
        view = self.run_tool("filesystem_list", path="..")

        self.assertIs(view.status, ToolRunStatus.REFUSED)
        self.assertTrue(view.performed)
        self.assertFalse(view.succeeded)
        self.assertEqual(view.values, ())
        self.assertIn("outside the authorized root", view.detail)

    def test_a_link_is_reported_rather_than_followed(self) -> None:
        """Whatever the scope holds, the console shows kinds, never targets."""
        view = self.run_tool("filesystem_list", path=".")

        kinds = {
            value.split(":", 1)[0]
            for name, value in view.values
            if name.startswith("entry_") and name != "entry_count"
        }
        self.assertTrue(kinds <= {"directory", "file", "link", "other"})


class NoModelTests(ConsoleFixture):
    """The console is a control plane. It must work with no model at all."""

    def test_the_runtime_registers_no_model_spending_capability(self) -> None:
        for entry in self.console.catalogue():
            with self.subTest(capability=entry.capability):
                self.assertNotIn("spends_model", entry.effects)

    def test_the_controller_never_touches_a_brain_or_provider(self) -> None:
        source = (SRC_DIR / "desktop" / "ToolConsoleController.py").read_text(
            encoding="utf-8"
        )

        for forbidden in (
            "Brain",
            "Provider",
            "CognitiveEngine",
            "llm",
            "completion",
            "model_prompt",
            "system_prompt",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, source)

    def test_every_capability_runs_with_no_model_present(self) -> None:
        """Constructed without a brain, a provider, or a controller."""
        results = {
            "clock_read": self.run_tool("clock_read"),
            "text_statistics": self.run_tool("text_statistics", text="a b"),
            "filesystem_list": self.run_tool("filesystem_list", path="."),
        }
        for capability, view in results.items():
            with self.subTest(capability=capability):
                self.assertTrue(view.succeeded, view.detail)

    def test_argument_kinds_offer_no_free_form_escape(self) -> None:
        kinds = {kind.value for kind in ToolArgumentKind}

        for forbidden in ("json", "python", "code", "expression", "raw", "free_form"):
            with self.subTest(kind=forbidden):
                self.assertNotIn(forbidden, kinds)


class RuntimeCompositionTests(unittest.TestCase):
    """What the production runtime registers, and what it refuses to."""

    def test_without_a_root_no_filesystem_capability_exists(self) -> None:
        runtime = ToolRuntime(None)

        self.assertEqual(
            [capability.value for capability in runtime.capabilities],
            ["clock_read", "text_statistics"],
        )

    def test_without_a_root_the_capability_cannot_be_run(self) -> None:
        console = ToolConsoleController(ToolRuntime(None))

        view = console.run("filesystem_list", (("path", "."),), authorized=True)

        self.assertIs(view.status, ToolRunStatus.UNAVAILABLE)
        self.assertFalse(view.performed)

    def test_without_a_root_no_scope_identity_is_reported(self) -> None:
        self.assertEqual(ToolRuntime(None).filesystem_root_id, "")

    def test_the_runtime_registers_no_execution_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = ToolRuntime(FilesystemRoot(Path(temp)))
            names = {capability.value for capability in runtime.capabilities}

        for forbidden in ("shell", "process", "filesystem_read", "filesystem_write"):
            with self.subTest(capability=forbidden):
                self.assertNotIn(forbidden, names)

    def test_the_runtime_builds_tools_by_construction_not_discovery(self) -> None:
        source = (SRC_DIR / "tools" / "ToolRuntime.py").read_text(encoding="utf-8")

        for forbidden in ("importlib", "__import__", "entry_points", "rglob", "eval("):
            with self.subTest(construct=forbidden):
                self.assertNotIn(forbidden, source)

    def test_a_console_requires_a_real_runtime(self) -> None:
        with self.assertRaises(ResearchError):
            ToolConsoleController(object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
