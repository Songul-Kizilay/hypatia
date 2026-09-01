"""One process owns the directories a runtime writes, or it does not start.

v0.3.275 guarded one file. That was the file whose loss had been demonstrated,
but it was never the only writable state: sessions, memory, knowledge relations,
research runs and everything research keeps beside them are ordinary whole-file
JSON stores with the same replace-the-document write. A second process opening
those loses records exactly the same way.

So the claim moved up to the directories. Research keeps its many stores next to
the run snapshot — executions, background tasks, curiosity questions,
reflections, lessons, approvals, hypotheses, the vulnerability graph — and they
are written by one runtime as a set, so the directory is the honest unit rather
than nine separate locks on files nobody shares individually.

The claim is taken before a single store is opened. A second process has to be
refused while it can still do no harm, not after it has loaded sessions and
memory and is one save away from replacing somebody else's.

It is emphatically not one Hypatia per machine. Two runtimes on separate data
directories are no danger to each other and both run, which the tests check with
real processes.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Bootstrap import Bootstrap
from core.ExclusiveStoreOwnership import release_all

#: Owns every directory one runtime root implies, then waits to be told to stop.
HOLDER = """
import sys
sys.path.insert(0, {src!r})
from pathlib import Path
from core.Bootstrap import Bootstrap
root = Path(sys.argv[1])
bootstrap = Bootstrap(
    memory_path=root / "memory" / "memory.json",
    session_path=root / "sessions" / "sessions.json",
    knowledge_relation_path=root / "knowledge" / "relations.json",
    research_run_path=root / "research" / "runs.json",
)
bootstrap._claim_writable_directories()
print("held", flush=True)
sys.stdin.readline()
"""

#: Tries the same, and reports which way it went.
CHALLENGER = """
import sys
sys.path.insert(0, {src!r})
from pathlib import Path
from core.Bootstrap import Bootstrap
from core.Exceptions import BootstrapError
root = Path(sys.argv[1])
bootstrap = Bootstrap(
    memory_path=root / "memory" / "memory.json",
    session_path=root / "sessions" / "sessions.json",
    knowledge_relation_path=root / "knowledge" / "relations.json",
    research_run_path=root / "research" / "runs.json",
)
try:
    bootstrap._claim_writable_directories()
except BootstrapError as error:
    print("refused:" + str(error), flush=True)
else:
    print("claimed", flush=True)
"""


class RuntimeOwnershipFixture(unittest.TestCase):
    """Temporary roots only; never a real data directory."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.addCleanup(release_all)
        self.root = Path(self.temporary_directory.name) / "runtime"

    def _bootstrap(self, root: Path | None = None) -> Bootstrap:
        base = root or self.root
        return Bootstrap(
            memory_path=base / "memory" / "memory.json",
            session_path=base / "sessions" / "sessions.json",
            knowledge_relation_path=base / "knowledge" / "relations.json",
            research_run_path=base / "research" / "runs.json",
        )

    def _spawn(self, script: str, root: Path) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-c", script.format(src=str(SRC_DIR)), str(root)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )

    def _challenge(self, root: Path) -> str:
        finished = subprocess.run(
            [sys.executable, "-c", CHALLENGER.format(src=str(SRC_DIR)), str(root)],
            capture_output=True,
            text=True,
            timeout=90,
        )
        return finished.stdout.strip()


class EveryWritableDirectoryIsCoveredTests(RuntimeOwnershipFixture):
    def test_the_directories_are_the_ones_the_stores_use(self) -> None:
        directories = set(self._bootstrap()._writable_directories())

        self.assertEqual(
            directories,
            {
                self.root / "memory",
                self.root / "sessions",
                self.root / "knowledge",
                self.root / "research",
            },
        )

    def test_research_keeps_its_stores_in_one_claimed_directory(self) -> None:
        """One entry covers runs, executions, tasks and the rest beside them."""
        bootstrap = self._bootstrap()
        directories = set(bootstrap._writable_directories())

        for name in (
            "research_executions.json",
            "research_background_tasks.json",
            "research_curiosity_questions.json",
            "research_plan_authorizations.json",
            "research_hypotheses.json",
        ):
            with self.subTest(name=name):
                self.assertIn((self.root / "research" / name).parent, directories)

    def test_a_default_runtime_names_its_directories_too(self) -> None:
        """No configured path, so the defaults must still resolve to somewhere."""
        directories = Bootstrap()._writable_directories()

        self.assertTrue(directories)
        self.assertTrue(all(isinstance(entry, Path) for entry in directories))


class OneProcessOwnsOneRuntimeTests(RuntimeOwnershipFixture):
    def test_an_unused_runtime_root_can_be_claimed(self) -> None:
        self._bootstrap()._claim_writable_directories()

        self.assertTrue(self._challenge(self.root).startswith("refused:"))

    def test_a_second_process_is_refused(self) -> None:
        self._bootstrap()._claim_writable_directories()

        answer = self._challenge(self.root)

        self.assertIn("already owns this writable runtime data directory", answer)

    def test_a_refused_process_writes_no_store(self) -> None:
        """Refused before anything is opened, so nothing of its own appears."""
        self._bootstrap()._claim_writable_directories()
        before = sorted(path.name for path in self.root.rglob("*"))

        self._challenge(self.root)

        self.assertEqual(sorted(path.name for path in self.root.rglob("*")), before)

    def test_a_different_runtime_root_is_allowed(self) -> None:
        self._bootstrap()._claim_writable_directories()
        other = Path(self.temporary_directory.name) / "other-runtime"

        self.assertEqual(self._challenge(other), "claimed")

    def test_the_same_process_may_claim_its_own_runtime_again(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap._claim_writable_directories()

        bootstrap._claim_writable_directories()

        self.assertTrue(self._challenge(self.root).startswith("refused:"))

    def test_killing_the_owner_frees_the_runtime(self) -> None:
        owner = self._spawn(HOLDER, self.root)
        try:
            self.assertEqual(owner.stdout.readline().strip(), "held")

            owner.kill()
            owner.wait(timeout=90)

            self.assertEqual(self._challenge(self.root), "claimed")
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=90)

    def test_a_leftover_lock_artifact_blocks_nothing(self) -> None:
        (self.root / "research").mkdir(parents=True, exist_ok=True)
        (self.root / "research" / ".hypatia-owner.lock").write_bytes(b"")

        self.assertEqual(self._challenge(self.root), "claimed")


class SchedulerStateIsCoveredTests(RuntimeOwnershipFixture):
    """The stores a scheduler would need are inside the claimed directories."""

    def test_a_second_process_cannot_reach_the_scheduler_stores(self) -> None:
        """Background tasks and runs share the research directory that is held."""
        self._bootstrap()._claim_writable_directories()

        answer = self._challenge(self.root)

        self.assertTrue(answer.startswith("refused:"), answer)

    def test_the_scheduler_stores_resolve_into_a_claimed_directory(self) -> None:
        bootstrap = self._bootstrap()
        claimed = set(bootstrap._writable_directories())

        for name in ("runs.json", "research_background_tasks.json"):
            with self.subTest(name=name):
                self.assertIn((self.root / "research" / name).parent, claimed)

    def test_memory_and_sessions_are_claimed_as_canonical_state(self) -> None:
        directories = set(self._bootstrap()._writable_directories())

        self.assertIn(self.root / "memory", directories)
        self.assertIn(self.root / "sessions", directories)


class TheClaimComesFirstTests(unittest.TestCase):
    """Ordering matters as much as the claim itself."""

    def test_initialize_claims_before_it_opens_anything(self) -> None:
        source = (SRC_DIR / "core" / "Bootstrap.py").read_text("utf-8")
        start = source.index("    def initialize(self) -> None:")
        end = source.index("\n    def ", start + 1)
        body = source[start:end]

        claimed = body.index("_claim_writable_directories()")
        first_store = min(
            body.index(name)
            for name in ("JsonFileSessionStore(", "JsonFileMemoryStore(")
        )
        self.assertLess(claimed, first_store)

    def test_the_execution_store_keeps_its_own_claim(self) -> None:
        """Not removed: it guards callers that never run initialize()."""
        source = (SRC_DIR / "core" / "Bootstrap.py").read_text("utf-8")

        self.assertIn("claim(store_path)", source)

    def test_ownership_is_not_machine_global(self) -> None:
        source = (SRC_DIR / "core" / "ExclusiveStoreOwnership.py").read_text("utf-8")

        for forbidden in ("gettempdir", "home()", "singleton", "os.getpid"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, source.casefold())

    def test_no_scheduler_process_was_introduced(self) -> None:
        source = (SRC_DIR / "core" / "Bootstrap.py").read_text("utf-8")

        for forbidden in ("Popen", "multiprocessing", "subprocess"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, source)


class BothEntrypointsShareOneBoundaryTests(unittest.TestCase):
    """The desktop and the CLI must not disagree about what is being owned."""

    def test_the_desktop_paths_sit_under_one_root(self) -> None:
        from desktop.DesktopDataPaths import DesktopDataPaths

        paths = DesktopDataPaths(root=Path("/tmp/example-root"))

        for path in (
            paths.memory_path,
            paths.session_path,
            paths.knowledge_relation_path,
            paths.research_run_path,
            paths.research_source_content_path,
        ):
            with self.subTest(path=str(path)):
                self.assertEqual(path.parent.parent, paths.root)

    def test_the_desktop_paths_produce_the_same_directories(self) -> None:
        from desktop.DesktopDataPaths import DesktopDataPaths

        paths = DesktopDataPaths(root=Path("/tmp/example-root"))
        bootstrap = Bootstrap(
            memory_path=paths.memory_path,
            session_path=paths.session_path,
            knowledge_relation_path=paths.knowledge_relation_path,
            research_run_path=paths.research_run_path,
        )

        self.assertEqual(
            set(bootstrap._writable_directories()),
            {
                paths.memory_path.parent,
                paths.session_path.parent,
                paths.knowledge_relation_path.parent,
                paths.research_run_path.parent,
            },
        )


if __name__ == "__main__":
    unittest.main()
