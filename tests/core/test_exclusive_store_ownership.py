"""Only one process may own a writable execution store.

Two Hypatia processes pointed at one store do not race over a field. Each keeps
its own picture in memory and each save replaces the whole document, so the
later writer erases the other's executions outright. That was reproduced with
two real processes before this guard existed, which is why the refusal is a
refusal and not a warning.

What makes it ownership rather than a note pinned to the door is that the kernel
holds it. A file that merely existed would keep a dead owner's claim forever and
leave somebody deleting it by hand after every crash; a lock is released when the
owning process ends, however it ends. The test below kills an owner outright to
show that.

The claim is per store. Two processes working on different stores are no danger
to each other and are left alone, and within one process the same store may be
claimed again — the process already owns it, and rebuilding an application
should not deadlock against itself.

Where an OS process really has to be involved the tests spawn one, with bounded
waits and no sleeps. Nothing here touches a real user store.
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

from core.Exceptions import BootstrapError
from core.ExclusiveStoreOwnership import claim

#: Claims the store, reports, then waits for a line on stdin before letting go.
HOLDER = """
import sys
sys.path.insert(0, {src!r})
from pathlib import Path
from core.ExclusiveStoreOwnership import claim
claim(Path(sys.argv[1]))
print("held", flush=True)
sys.stdin.readline()
"""

#: Tries to claim the store and reports which way it went.
CHALLENGER = """
import sys
sys.path.insert(0, {src!r})
from pathlib import Path
from core.ExclusiveStoreOwnership import claim
from core.Exceptions import BootstrapError
try:
    claim(Path(sys.argv[1]))
except BootstrapError as error:
    print("refused:" + str(error), flush=True)
else:
    print("claimed", flush=True)
"""


class OwnershipFixture(unittest.TestCase):
    """A store path of our own, never a real one."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.store = self.root / "research_executions.json"
        self.claims: list = []

    def tearDown(self) -> None:
        for held in self.claims:
            held.release()
        super().tearDown()

    def _claim(self, path: Path | None = None):
        held = claim(path or self.store)
        self.claims.append(held)
        return held

    def _spawn(self, script: str, path: Path) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-c", script.format(src=str(SRC_DIR)), str(path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )

    def _challenge(self, path: Path) -> str:
        finished = subprocess.run(
            [sys.executable, "-c", CHALLENGER.format(src=str(SRC_DIR)), str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return finished.stdout.strip()


class OneProcessOwnsOneStoreTests(OwnershipFixture):
    def test_an_unused_store_can_be_claimed(self) -> None:
        held = self._claim()

        self.assertTrue(held.held)
        self.assertEqual(held.path, self.store.resolve())

    def test_a_second_process_is_refused(self) -> None:
        """The proof that needed a real process."""
        self._claim()

        answer = self._challenge(self.store)

        self.assertTrue(answer.startswith("refused:"), answer)

    def test_the_refusal_says_what_is_wrong(self) -> None:
        self._claim()

        answer = self._challenge(self.store)

        self.assertIn("already owned by another Hypatia process", answer)
        self.assertNotIn("corrupt", answer.casefold())

    def test_a_refused_process_leaves_the_store_untouched(self) -> None:
        self._claim()
        self.store.write_text('{"schema_version": 2, "executions": []}', "utf-8")
        before = self.store.read_text("utf-8")

        self._challenge(self.store)

        self.assertEqual(self.store.read_text("utf-8"), before)

    def test_a_refused_process_writes_no_alternative_store(self) -> None:
        """No quiet fallback to another file, which would split the truth."""
        self._claim()
        before = {path.name for path in self.root.iterdir()}

        self._challenge(self.store)

        self.assertEqual({path.name for path in self.root.iterdir()}, before)

    def test_a_different_store_may_be_owned_at_the_same_time(self) -> None:
        self._claim()
        other = self.root / "other_executions.json"

        answer = self._challenge(other)

        self.assertEqual(answer, "claimed")

    def test_the_same_process_may_claim_its_own_store_again(self) -> None:
        """Rebuilding an application must not deadlock against itself."""
        first = self._claim()

        second = self._claim()

        self.assertIs(first, second)


class OwnershipEndsWithTheOwnerTests(OwnershipFixture):
    def test_releasing_lets_another_process_take_it(self) -> None:
        held = self._claim()

        held.release()

        self.assertEqual(self._challenge(self.store), "claimed")
        self.assertFalse(held.held)

    def test_releasing_twice_is_harmless(self) -> None:
        held = self._claim()

        held.release()
        held.release()

        self.assertFalse(held.held)

    def test_killing_the_owner_frees_the_store(self) -> None:
        """A crash must not brick the store until somebody deletes a file."""
        owner = self._spawn(HOLDER, self.store)
        try:
            self.assertEqual(owner.stdout.readline().strip(), "held")
            self.assertTrue(self.store.with_name(self.store.name + ".lock").exists())

            owner.kill()
            owner.wait(timeout=60)

            self.assertEqual(self._challenge(self.store), "claimed")
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=60)

    def test_the_leftover_lock_file_grants_nothing_by_itself(self) -> None:
        """Existence is not ownership; only the held lock is."""
        lock_path = self.store.with_name(self.store.name + ".lock")
        lock_path.write_bytes(b"")

        self.assertEqual(self._challenge(self.store), "claimed")

    def test_an_orderly_exit_frees_the_store(self) -> None:
        owner = self._spawn(HOLDER, self.store)
        try:
            self.assertEqual(owner.stdout.readline().strip(), "held")
            owner.stdin.write("go\n")
            owner.stdin.flush()
            owner.wait(timeout=60)

            self.assertEqual(self._challenge(self.store), "claimed")
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=60)


class TheGuardIsNarrowTests(OwnershipFixture):
    def test_it_claims_a_store_rather_than_the_application(self) -> None:
        """Nothing global: two Hypatias on separate stores both run."""
        source = (SRC_DIR / "core" / "ExclusiveStoreOwnership.py").read_text("utf-8")

        for forbidden in ("hypatia.lock", "global", "singleton", "os.getpid"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, source.casefold())

    def test_a_path_is_required_rather_than_a_name(self) -> None:
        with self.assertRaises(BootstrapError):
            claim("not a path")

    def test_ownership_is_taken_where_the_store_is_built(self) -> None:
        bootstrap = (SRC_DIR / "core" / "Bootstrap.py").read_text("utf-8")

        self.assertIn("claim(store_path)", bootstrap)
        self.assertIn("JsonFileResearchExecutionStore(store_path)", bootstrap)

    def test_no_scheduler_process_was_introduced(self) -> None:
        bootstrap = (SRC_DIR / "core" / "Bootstrap.py").read_text("utf-8")

        for forbidden in ("Popen", "subprocess", "multiprocessing"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, bootstrap)


if __name__ == "__main__":
    unittest.main()
