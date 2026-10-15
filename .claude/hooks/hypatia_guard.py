"""Deterministic developer safeguards for Claude Code in the Hypatia repo.

Modes (argv[1]):
  session  SessionStart: report git state and exact-SHA CI of HEAD as context.
  command  PreToolUse (Bash/PowerShell): deny what is never part of the
           workflow (force-push, remote ref deletion, repo deletion,
           permission bypass), including forms permission rules cannot match
           (``git -C . push -f``, ``+refspec``, combined short flags).
           Merge, rebase, tag and releases are "ask" rules in settings.json:
           each needs the user's explicit approval. `gh pr merge` is NOT an
           "ask" rule (see _pr_merge_auto_allow/_pr_merge_denial below for
           why): this guard allows only the one exact routine shape - a lone
           ``gh pr merge <number> --merge`` (optionally with exactly one
           ``--subject <text>``) as the entire command, nothing chained
           before or after it - and explicitly denies every other
           ``gh pr merge`` shape outright. That allowed shape is the one
           step of CLAUDE.md's "Default-branch integration" a standing
           milestone authorization covers without a fresh prompt.

           v0.3.471 hardening (see CLAUDE.md's "Mutation-test and
           shared-worktree safety"): this guard unconditionally denies the
           Git-level worktree-discard commands that caused the v0.3.470
           mutation-revert incident - a review agent used one of these to
           undo its own temporary test mutation, and because the production
           file already held uncommitted milestone work (never staged),
           the discard replaced the entire file with HEAD's content instead
           of reverting only the mutation. Denied unconditionally, any
           arguments, any ``-C``/global-option prefix, any chain position:
           ``git restore`` (every form), ``git checkout``/
           ``git checkout-index`` (every form - this guard does not
           distinguish safe branch checkout from destructive path checkout;
           use ``git switch`` for branch changes instead), ``git reset
           --hard``/``--merge``/``--keep``, ``git switch --force``/``-f``/
           ``--discard-changes``, and ``git clean`` with any force flag
           (``-f``, combined short flags containing ``f`` such as ``-fd``/
           ``-df``/``-fx``, or ``--force``) - ``git clean -n``/``--dry-run``
           remains allowed. This denies the reviewed Git-level
           worktree-discard commands that caused, or are close variants of,
           the v0.3.470 incident; it is not a general shell-security
           framework, does not claim to catch every destructive command in
           existence, and does not govern a human's own manual terminal use
           outside Claude Code.
  lint     PostToolUse (Edit/Write): run Ruff on one edited Python file.

Standard library only. Hook input is parsed, never executed: no text from the
repository or tool input is passed to a shell. Any internal error allows the
action (exit 0) so a broken guard never blocks unrelated work; permission
deny/ask rules in .claude/settings.json remain as a second layer.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
SEPARATORS = {";", "&&", "||", "|", "|&", "&", "\n", "(", ")"}
GIT_OPTIONS_WITH_VALUE = {
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--config-env",
    "--super-prefix",
}
GH_OPTIONS_WITH_VALUE = {"-R", "--repo"}


def _run(args: list[str], timeout: float = 15.0) -> str:
    completed = subprocess.run(
        args,
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def session() -> None:
    lines = ["Hypatia repo state (SessionStart guard):"]
    branch = _run(["git", "branch", "--show-current"])
    head = _run(["git", "rev-parse", "HEAD"])
    upstream = _run(["git", "rev-parse", "@{u}"])
    dirty = [line for line in _run(["git", "status", "--porcelain"]).splitlines()]
    lines.append(f"- branch {branch or '?'}, HEAD {head[:12] or '?'}")
    if upstream and upstream != head:
        lines.append(f"- WARNING: HEAD differs from upstream {upstream[:12]}.")
    if dirty:
        lines.append(
            f"- WARNING: working tree already has {len(dirty)} changed path(s). "
            "Inspect them before starting; never stage unrelated changes."
        )
    if head:
        runs = _run(
            [
                "gh",
                "run",
                "list",
                "--commit",
                head,
                "--json",
                "workflowName,status,conclusion",
            ]
        )
        try:
            records = json.loads(runs) if runs else []
        except json.JSONDecodeError:
            records = []
        results = {
            name: next(
                (
                    f"{r['status']}/{r['conclusion'] or '-'}"
                    for r in records
                    if r.get("workflowName") == name
                ),
                "not run",
            )
            for name in ("Linux desktop", "Windows desktop")
        }
        lines.append(
            "- exact-SHA CI for HEAD: "
            + ", ".join(f"{k}: {v}" for k, v in results.items())
        )
        if any(value != "completed/success" for value in results.values()):
            lines.append(
                "- HEAD is not confirmed delivered (both CI runs must succeed on "
                "this exact SHA). Do not start a new milestone; finish or fix "
                "the current one first. A commit that has not been released yet "
                "is expected to show 'not run'."
            )
    ledger = PROJECT / "docs" / "dev" / "MILESTONE.md"
    if ledger.is_file():
        lines.append("- milestone ledger: docs/dev/MILESTONE.md")
    print("\n".join(lines))


def _line_segments(line: str) -> list[list[str]]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    segments: list[list[str]] = [[]]
    for token in lexer:
        if token in SEPARATORS or set(token) <= set(";&|()"):
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def _segments(command: str) -> list[list[str]]:
    """Split `command` into chained-command segments.

    A literal newline is a command separator in both Bash and PowerShell,
    but ``shlex``'s default ``whitespace`` already includes ``\\n`` -- so
    it is silently consumed as whitespace between tokens before the
    ``token in SEPARATORS`` check below ever sees it as a token, and a
    multi-line command would otherwise collapse into a single segment
    (the second line parsed only as extra arguments to the first word).
    Splitting into physical lines first, and segmenting each line
    independently, keeps a destructive command on any later line from
    ever hiding behind an earlier, harmless one. A quoted argument that
    genuinely spans multiple physical lines will fail to tokenize on its
    own half and fall through to the caller's conservative fallback
    instead of parsing cleanly -- an acceptable, fail-closed trade-off
    for a shape this workflow does not use (``git commit -F <file>`` is
    required instead of an inline multi-line ``-m`` message)."""
    segments: list[list[str]] = []
    for line in command.split("\n"):
        segments.extend(_line_segments(line))
    return segments


def _program(token: str) -> str:
    name = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _gh_subcommand(tokens: list[str]) -> list[str]:
    """Return the first two ``gh`` subcommand words, skipping global flags."""
    index = 1
    while index < len(tokens) and tokens[index].startswith("-"):
        index += 2 if tokens[index] in GH_OPTIONS_WITH_VALUE else 1
    return tokens[index : index + 2]


def _git_subcommand(tokens: list[str]) -> tuple[str, list[str]]:
    index = 1
    while index < len(tokens) and tokens[index].startswith("-"):
        index += 2 if tokens[index] in GIT_OPTIONS_WITH_VALUE else 1
    if index >= len(tokens):
        return "", []
    return tokens[index], tokens[index + 1 :]


def _short_flag_contains(argument: str, letter: str) -> bool:
    """True for a short-option (``-f``, combined ``-fd``/``-df``) that
    contains ``letter`` anywhere - deliberately order-independent, so a
    settings.json wildcard (which can only match a fixed literal prefix)
    cannot be mistaken for full coverage of every flag permutation."""
    return (
        argument.startswith("-")
        and not argument.startswith("--")
        and len(argument) > 1
        and letter in argument[1:]
    )


def _is_abbreviated_long_option(argument: str, *full_spellings: str) -> bool:
    """True if `argument` is `--` plus a non-empty prefix of any of
    `full_spellings` - real git accepts an unambiguous prefix of its own
    long option names (``git reset --har`` really does run as
    ``--hard``), so an exact-string check alone is bypassable. Checking
    "is this a prefix of one of our OWN denied spellings" - never the
    reverse - is deliberately over-inclusive rather than reproducing
    git's own ambiguity resolution: a short, technically-ambiguous
    prefix among git's full option set (e.g. ``--d`` for both
    ``--delete`` and ``--dry-run``) still matches here, but denying it
    costs nothing since real git would refuse it as ambiguous anyway -
    only under-matching an abbreviation git genuinely accepts would be a
    real gap. ``len(argument) <= 2`` excludes bare ``--`` (git's
    "end of options" marker, used idiomatically and never itself
    destructive)."""
    if not argument.startswith("--") or len(argument) <= 2:
        return False
    return any(spelling.startswith(argument) for spelling in full_spellings)


def _force_push(arguments: list[str]) -> bool:
    for argument in arguments:
        if argument.startswith("--force-with-lease"):
            return True
        if _is_abbreviated_long_option(
            argument, "--force", "--mirror", "--delete", "--force-if-includes"
        ):
            return True
        if argument.startswith("-") and not argument.startswith("--"):
            if "f" in argument[1:] or "d" in argument[1:]:
                return True
        if argument.startswith("+") or argument.startswith(":"):
            return True
    return False


def _git_reset_discards(arguments: list[str]) -> bool:
    """``--hard``/``--merge``/``--keep`` replace working-tree content from
    HEAD/a stash/the index; plain (``--mixed``/``--soft``) reset never
    touches working-tree file content and is intentionally not denied."""
    return any(
        _is_abbreviated_long_option(argument, "--hard", "--merge", "--keep")
        for argument in arguments
    )


def _git_switch_discards(arguments: list[str]) -> bool:
    """``-f``/``--force`` is a documented alias for ``--discard-changes``."""
    for argument in arguments:
        if _short_flag_contains(argument, "f"):
            return True
        if _is_abbreviated_long_option(argument, "--force", "--discard-changes"):
            return True
    return False


def _git_clean_forces(arguments: list[str]) -> bool:
    """Any force flag, in any position/combination; ``-n``/``--dry-run``
    alone (no force flag) is deliberately left allowed."""
    for argument in arguments:
        if _short_flag_contains(argument, "f"):
            return True
        if _is_abbreviated_long_option(argument, "--force"):
            return True
    return False


#: v0.3.471: the reviewed Git-level worktree-discard command classes that
#: caused, or are close variants of, the v0.3.470 mutation-revert incident
#: (see CLAUDE.md's "Mutation-test and shared-worktree safety"). Denied
#: unconditionally - not merely when "dangerous-looking" arguments are
#: present - because MUTATION BASELINE != GIT HEAD: a reviewer can never
#: safely assume a changed production file was clean before its own
#: temporary mutation, so no Git-level discard of that file is ever part of
#: this automated workflow, regardless of its arguments.
_RESTORE_DENIAL = (
    "`git restore` can silently replace uncommitted file content with "
    "HEAD/index/source content and must never be used to revert a "
    "temporary mutation (MUTATION BASELINE != GIT HEAD). Use a targeted "
    "edit to restore exact pre-mutation content instead."
)
_CHECKOUT_DENIAL = (
    "`git checkout`/`git checkout-index` are denied entirely in this "
    "automated workflow: their path-restoring forms (`git checkout -- "
    "file`, `git checkout HEAD -- file`, `git checkout .`, "
    "`git checkout-index`) can silently discard or overwrite uncommitted "
    "milestone content, and this guard does not distinguish that from "
    "safe branch checkout. Use `git switch` for branch changes and a "
    "targeted edit, never a Git-level discard, to revert file content."
)
_RESET_DENIAL = (
    "`git reset --hard`/`--merge`/`--keep` discards uncommitted "
    "working-tree content and must never be used to revert a temporary "
    "mutation (MUTATION BASELINE != GIT HEAD). Use a targeted edit "
    "instead."
)
_SWITCH_DENIAL = (
    "`git switch --force`/`-f`/`--discard-changes` can silently discard "
    "uncommitted changes when switching branches. Use a plain "
    "`git switch <branch>` with a clean tree instead."
)
_CLEAN_DENIAL = (
    "`git clean` with a force flag (`-f`, a combined short flag "
    "containing `f`, or `--force`) permanently deletes untracked files "
    "and is never part of the automated workflow; `git clean -n`/"
    "`--dry-run` remains available."
)


def _denial(tokens: list[str]) -> str | None:
    while tokens and "=" in tokens[0] and not tokens[0].startswith("-"):
        tokens = tokens[1:]
    if not tokens:
        return None
    program = _program(tokens[0])
    if program == "git":
        subcommand, arguments = _git_subcommand(tokens)
        if subcommand == "push" and _force_push(arguments):
            return "Force-push or remote ref deletion is never part of the workflow."
        if subcommand == "restore":
            return _RESTORE_DENIAL
        if subcommand in {"checkout", "checkout-index"}:
            return _CHECKOUT_DENIAL
        if subcommand == "reset" and _git_reset_discards(arguments):
            return _RESET_DENIAL
        if subcommand == "switch" and _git_switch_discards(arguments):
            return _SWITCH_DENIAL
        if subcommand == "clean" and _git_clean_forces(arguments):
            return _CLEAN_DENIAL
    if program == "gh" and tokens[1:3] == ["repo", "delete"]:
        return "Deleting the repository is never part of the workflow."
    if program == "claude" and any(
        token in {"--dangerously-skip-permissions", "bypassPermissions"}
        for token in tokens
    ):
        return "Bypassing permissions is not part of the Hypatia workflow."
    return None


def _conservative_fallback_denial(text: str) -> str | None:
    """Best-effort denial when `_segments` cannot tokenize the command
    (unparseable quoting). Approximates tokens with a plain whitespace
    split and reuses the exact same per-class detection helpers as the
    primary tokenized path (`_force_push`/`_git_reset_discards`/
    `_git_switch_discards`/`_git_clean_forces`) against that rough token
    list, rather than duplicating separate raw-substring heuristics -
    duplicated heuristics drift (a raw ``"-f" in text`` substring check,
    for example, misses a combined flag like ``-df`` where ``f`` is not
    first, something `_short_flag_contains` already handles correctly).
    Only matches the specific destructive classes this guard denies, so
    an unrelated parser failure never becomes a global denial of all
    commands."""
    if "git" not in text:
        return None
    rough_tokens = text.replace("\n", " ").split()
    if "restore" in rough_tokens:
        return _RESTORE_DENIAL
    if "checkout" in rough_tokens or "checkout-index" in rough_tokens:
        return _CHECKOUT_DENIAL
    if "push" in rough_tokens and _force_push(rough_tokens):
        return "Force-push is never part of the workflow."
    if "reset" in rough_tokens and _git_reset_discards(rough_tokens):
        return _RESET_DENIAL
    if "switch" in rough_tokens and _git_switch_discards(rough_tokens):
        return _SWITCH_DENIAL
    if "clean" in rough_tokens and _git_clean_forces(rough_tokens):
        return _CLEAN_DENIAL
    return None


def _pr_merge_auto_allow(tokens: list[str]) -> bool:
    """Only the exact routine shape: ``gh pr merge <number> --merge``,
    optionally with exactly one trailing ``--subject <text>``.

    Deliberately an allowlist of the exact expected shape, not a denylist of
    known-dangerous flags: any flag other than ``--merge``/``--subject``,
    any non-numeric PR identifier, or any extra token anywhere fails this
    check. This is checked against real parsed tokens (see ``_segments``),
    not a glob, specifically so a flag like ``--admin``, ``--squash``,
    ``--rebase`` or ``--delete-branch`` can never hide inside a wildcarded
    region.

    Claude Code's own documented permission precedence is deny, then ask,
    then allow, and a matching ``ask`` rule always still prompts regardless
    of what a PreToolUse hook returns - a hook's ``"allow"`` cannot override
    an ``ask`` rule the way an earlier version of this guard assumed
    (confirmed against https://code.claude.com/docs/en/permissions.md and
    https://code.claude.com/docs/en/hooks-guide.md after that assumption
    was empirically wrong once in practice). settings.json therefore has NO
    ``ask`` rule for ``gh pr merge`` any more - see ``_pr_merge_denial``,
    which is what actually keeps every other shape from running. Because
    nothing in settings.json backstops this any more, ``_pr_merge_denial``
    also covers the form reached through a ``gh`` global flag (``-R``/
    ``--repo``), which no wildcard rule ever matched either.
    """
    if len(tokens) < 5:
        return False
    if _program(tokens[0]) != "gh":
        return False
    if tokens[1:3] != ["pr", "merge"]:
        return False
    if not tokens[3].isdigit():
        return False
    rest = tokens[4:]
    if not rest or rest[0] != "--merge":
        return False
    rest = rest[1:]
    if not rest:
        return True
    return len(rest) == 2 and rest[0] == "--subject"


def _pr_merge_denial(tokens: list[str], only_segment: bool) -> str | None:
    """Deny every ``gh pr merge`` shape except the one pre-authorized shape.

    A hook's "allow" cannot carve an exception out of a broader "ask" rule
    (deny > ask > allow is unconditional, per Claude Code's own docs), so an
    "ask" rule can no longer gate the unsafe shapes here without also
    gating the one safe shape this guard exists to auto-allow. Denying every
    other shape outright - rather than leaving it to fall through to
    whatever default handling an unmatched command would otherwise get -
    keeps this guard's behavior deterministic and provable, and matches
    CLAUDE.md's own absolute prohibition on squash/rebase-merging a
    milestone PR or using ``--admin`` to bypass checks: those were never
    meant to be merely "ask", so denying them outright is not a narrowing
    of policy, it is enforcing the policy that already existed.
    """
    if _program(tokens[0]) != "gh" or _gh_subcommand(tokens) != ["pr", "merge"]:
        return None
    if tokens[1:3] != ["pr", "merge"]:
        # Reached through a global flag such as ``-R owner/repo``. The allow
        # shape is the plain form only, so this can never be auto-allowed;
        # deny it rather than leave a pr-merge shape the guard does not decide.
        return (
            "A pre-authorized PR merge must be the plain "
            "`gh pr merge <number> --merge` form, with no global flag before "
            "the subcommand."
        )
    if not only_segment:
        return "A gh pr merge command must not be chained with anything else."
    if _pr_merge_auto_allow(tokens):
        return None
    return (
        "Only `gh pr merge <number> --merge` (optionally with one "
        "`--subject <text>`) is pre-authorized. Any other gh pr merge "
        "shape (a different flag, a non-numeric identifier, anything "
        "extra) needs the user to run or explicitly authorize it directly."
    )


def command(payload: dict[str, object]) -> None:
    tool_input = payload.get("tool_input")
    text = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(text, str):
        return
    try:
        segments = _segments(text)
    except ValueError:
        # Unparseable quoting: fall back to a conservative, substring-based
        # check for the specific destructive classes this guard denies.
        # An unrelated parser failure must not become a global denial of
        # all commands, so this only ever matches those specific classes.
        reason = _conservative_fallback_denial(text)
        if reason is not None:
            _deny(reason)
        return
    for tokens in segments:
        reason = _denial(tokens)
        if reason is not None:
            _deny(reason)
            return
    only_segment = len(segments) == 1
    for tokens in segments:
        reason = _pr_merge_denial(tokens, only_segment)
        if reason is not None:
            _deny(reason)
            return
    # The whole command must be exactly one safe-shaped call - nothing may
    # be chained before or after it, or the "allow" would cover that too.
    if only_segment and _pr_merge_auto_allow(segments[0]):
        _allow(
            "routine PR merge for an already-reviewed, CI-green Hypatia "
            "milestone (CLAUDE.md's Default-branch integration)."
        )


def _deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Hypatia guard: {reason}",
                }
            }
        )
    )


def _allow(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": f"Hypatia guard: {reason}",
                }
            }
        )
    )


def lint(payload: dict[str, object]) -> None:
    tool_input = payload.get("tool_input")
    raw = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(raw, str) or not raw.endswith(".py"):
        return
    path = Path(raw).resolve()
    if PROJECT not in path.parents or not path.is_file():
        return
    interpreter = next(
        (
            candidate
            for candidate in (
                PROJECT / ".venv" / "Scripts" / "python.exe",
                PROJECT / ".venv" / "bin" / "python",
            )
            if candidate.is_file()
        ),
        Path(sys.executable),
    )
    completed = subprocess.run(
        [str(interpreter), "-m", "ruff", "check", "--quiet", str(path)],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode == 1 and completed.stdout.strip():
        findings = "\n".join(completed.stdout.strip().splitlines()[:20])
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": f"Ruff findings in {raw}:\n{findings}",
                    }
                }
            )
        )


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if mode == "session":
            session()
            return 0
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return 0
        if mode == "command":
            command(payload)
        elif mode == "lint":
            lint(payload)
    except Exception:  # noqa: BLE001 - a guard fault must not block work
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
