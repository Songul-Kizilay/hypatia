"""Tests for `.claude/hooks/hypatia_guard.py`'s destructive Git-command
denial (v0.3.471: shared-worktree mutation safety).

These tests invoke the real guard script as a subprocess, exactly as
Claude Code's own PreToolUse hook does (synthetic hook JSON on stdin),
rather than re-implementing its parser. `IncidentRegressionTests` also
characterizes real Git behavior in a disposable temporary repository
(never the real repository worktree) to prove the exact incident class
the guard now prevents, and that the documented workflow restores exact
pre-mutation content instead.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GUARD_PATH = PROJECT_ROOT / ".claude" / "hooks" / "hypatia_guard.py"


def _invoke_guard_command(command_text: str) -> dict[str, object] | None:
    completed = subprocess.run(
        [sys.executable, str(GUARD_PATH), "command"],
        input=json.dumps({"tool_input": {"command": command_text}}),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    output = completed.stdout.strip()
    return json.loads(output) if output else None


def _decision(command_text: str) -> str | None:
    result = _invoke_guard_command(command_text)
    if result is None:
        return None
    hook_output = result.get("hookSpecificOutput")
    if not isinstance(hook_output, dict):
        return None
    decision = hook_output.get("permissionDecision")
    return decision if isinstance(decision, str) else None


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


class DestructiveGitDiscardDenialTests(unittest.TestCase):
    """The guard unconditionally denies every reviewed Git-level
    worktree-discard command class, regardless of arguments, a `-C`/global
    option prefix, or chain position."""

    def test_git_restore_denied_in_every_form(self) -> None:
        for command_text in [
            "git restore file.py",
            "git restore .",
            "git restore --source=HEAD file.py",
            "git -C . restore file.py",
        ]:
            with self.subTest(command_text=command_text):
                self.assertEqual(_decision(command_text), "deny")

    def test_git_checkout_path_forms_denied(self) -> None:
        for command_text in [
            "git checkout -- file.py",
            "git checkout HEAD -- file.py",
            "git checkout .",
            "git checkout -f branch",
        ]:
            with self.subTest(command_text=command_text):
                self.assertEqual(_decision(command_text), "deny")

    def test_git_checkout_index_denied(self) -> None:
        self.assertEqual(_decision("git checkout-index -a -f"), "deny")

    def test_git_reset_destructive_modes_denied(self) -> None:
        for command_text in [
            "git reset --hard",
            "git reset --hard HEAD",
            "git -C . reset --hard",
            "git reset --merge",
            "git reset --keep",
        ]:
            with self.subTest(command_text=command_text):
                self.assertEqual(_decision(command_text), "deny")

    def test_git_switch_discard_forms_denied(self) -> None:
        for command_text in [
            "git switch --discard-changes branch",
            "git switch -f branch",
            "git switch --force branch",
        ]:
            with self.subTest(command_text=command_text):
                self.assertEqual(_decision(command_text), "deny")

    def test_git_clean_force_forms_denied(self) -> None:
        for command_text in [
            "git clean -f",
            "git clean -fd",
            "git clean -df",
            "git clean -fx",
            "git clean --force",
            "git -C . clean -fd",
        ]:
            with self.subTest(command_text=command_text):
                self.assertEqual(_decision(command_text), "deny")

    def test_chained_destructive_commands_denied(self) -> None:
        for command_text in [
            "git status && git restore file.py",
            "echo ok ; git reset --hard",
        ]:
            with self.subTest(command_text=command_text):
                self.assertEqual(_decision(command_text), "deny")


class SafeDevelopmentWorkflowRemainsAvailableTests(unittest.TestCase):
    """The new policy must not block ordinary, non-destructive development
    commands -- including the ones the established milestone workflow
    actually uses."""

    def test_safe_commands_produce_no_denial(self) -> None:
        for command_text in [
            "git status",
            "git diff",
            "git diff --check",
            "git log -1",
            "git show HEAD",
            "git rev-parse HEAD",
            "git merge-base --is-ancestor HEAD HEAD",
            "git fetch origin",
            "git add file.py",
            "git commit -F message.txt",
            "git push origin feature/test",
            "git clean -n",
            "git clean --dry-run",
            "git switch feature/test",
            "git branch --show-current",
            "git worktree add D:/hypatia-vtest -b feature/test origin/main",
            "git worktree list",
        ]:
            with self.subTest(command_text=command_text):
                self.assertIsNone(_decision(command_text))

    def test_pr_merge_allowlist_still_allows(self) -> None:
        self.assertEqual(_decision("gh pr merge 451 --merge"), "allow")

    def test_pr_merge_other_shapes_still_denied(self) -> None:
        for command_text in [
            "gh pr merge 451 --squash",
            "gh pr merge 451 --merge --admin",
            "gh pr merge 451 --merge && echo done",
            "gh -R owner/repo pr merge 451 --merge",
        ]:
            with self.subTest(command_text=command_text):
                self.assertEqual(_decision(command_text), "deny")

    def test_force_push_protection_unchanged(self) -> None:
        for command_text in [
            "git push --force origin main",
            "git push -f origin main",
            "git -C . push --force origin main",
            "git push origin +main",
        ]:
            with self.subTest(command_text=command_text):
                self.assertEqual(_decision(command_text), "deny")

    def test_repo_delete_protection_unchanged(self) -> None:
        self.assertEqual(_decision("gh repo delete owner/repo"), "deny")

    def test_permission_bypass_protection_unchanged(self) -> None:
        self.assertEqual(_decision("claude --dangerously-skip-permissions"), "deny")


class ParserFallbackTests(unittest.TestCase):
    """Unparseable quoting falls back to a conservative, substring-based
    check for the specific destructive classes this guard denies -- never
    a global denial of all commands."""

    def test_unparseable_quoting_with_destructive_text_still_denies(self) -> None:
        # An unbalanced quote makes shlex raise ValueError; the raw text
        # still clearly names a denied destructive operation.
        self.assertEqual(_decision('git restore "unterminated'), "deny")

    def test_unparseable_quoting_without_destructive_text_is_not_denied(
        self,
    ) -> None:
        self.assertIsNone(_decision('git status "unterminated'))


class IncidentRegressionTests(unittest.TestCase):
    """Reproduces the exact v0.3.470 incident class in a disposable
    temporary repository -- never the real repository worktree.

    Conceptual state: HEAD file is "A"; the working-tree milestone file is
    "A + MILESTONE_CHANGE" (uncommitted); a review mutation makes it
    "A + MILESTONE_CHANGE + TEMP_MUTATION". The guard must deny the exact
    commands that, if run, would discard the milestone change (not merely
    the mutation) by replacing the file with HEAD's content. The
    documented workflow instead restores "A + MILESTONE_CHANGE" via a
    targeted write and proves exact hash equality.
    """

    def test_denied_discard_commands_would_have_erased_milestone_content(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git(repo, "init", "-q")
            _git(repo, "config", "user.email", "test@example.com")
            _git(repo, "config", "user.name", "Test")
            _git(repo, "config", "core.autocrlf", "false")

            target = repo / "production.py"
            target.write_bytes(b"A\n")
            _git(repo, "add", "production.py")
            _git(repo, "commit", "-q", "-m", "initial (HEAD)")

            # Uncommitted milestone work on top of HEAD.
            target.write_bytes(b"A\nMILESTONE_CHANGE\n")
            pre_mutation_bytes = target.read_bytes()
            pre_mutation_hash = hashlib.sha256(pre_mutation_bytes).hexdigest()

            # A reviewer's temporary test mutation on top of that.
            target.write_bytes(b"A\nMILESTONE_CHANGE\nTEMP_MUTATION\n")

            # The guard denies exactly the commands that caused the
            # incident -- they must never be reachable in the automated
            # workflow to "revert" a mutation.
            self.assertEqual(_decision("git checkout -- production.py"), "deny")
            self.assertEqual(_decision("git restore production.py"), "deny")
            self.assertEqual(_decision("git reset --hard"), "deny")

            # Ground truth, in a disposable repo only: if the denied
            # command WERE run anyway, it discards the milestone change
            # too, not merely the mutation -- this characterizes the
            # actual incident mechanism rather than assuming it.
            _git(repo, "checkout", "--", "production.py")
            self.assertEqual(target.read_bytes(), b"A\n")
            self.assertNotEqual(
                hashlib.sha256(target.read_bytes()).hexdigest(),
                pre_mutation_hash,
                "git checkout -- <file> must not merely undo the mutation; "
                "it discards the milestone change too, which is the "
                "incident this guard now prevents.",
            )

    def test_documented_workflow_restores_exact_pre_mutation_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git(repo, "init", "-q")
            _git(repo, "config", "user.email", "test@example.com")
            _git(repo, "config", "user.name", "Test")
            _git(repo, "config", "core.autocrlf", "false")

            target = repo / "production.py"
            target.write_bytes(b"A\n")
            _git(repo, "add", "production.py")
            _git(repo, "commit", "-q", "-m", "initial (HEAD)")

            target.write_bytes(b"A\nMILESTONE_CHANGE\n")
            pre_mutation_bytes = target.read_bytes()
            pre_mutation_hash = hashlib.sha256(pre_mutation_bytes).hexdigest()
            pre_mutation_diff = subprocess.run(
                ["git", "diff", "--", "production.py"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            target.write_bytes(b"A\nMILESTONE_CHANGE\nTEMP_MUTATION\n")

            # The controlled mutation-test workflow: revert ONLY the
            # mutation via a targeted write of the exact saved
            # pre-mutation content -- never a Git-level discard -- and
            # verify exact hash and diff equality afterward.
            target.write_bytes(pre_mutation_bytes)

            restored_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertEqual(restored_hash, pre_mutation_hash)

            restored_diff = subprocess.run(
                ["git", "diff", "--", "production.py"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertEqual(restored_diff, pre_mutation_diff)


if __name__ == "__main__":
    unittest.main()
