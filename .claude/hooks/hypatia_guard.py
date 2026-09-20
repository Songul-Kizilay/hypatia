"""Deterministic developer safeguards for Claude Code in the Hypatia repo.

Modes (argv[1]):
  session  SessionStart: report git state and exact-SHA CI of HEAD as context.
  command  PreToolUse (Bash/PowerShell): deny what is never part of the
           workflow (force-push, remote ref deletion, repo deletion,
           permission bypass), including forms permission rules cannot match
           (``git -C . push -f``, ``+refspec``, combined short flags).
           Merge, rebase, tag, hard reset, releases and PR merges are "ask"
           rules in settings.json: each needs the user's explicit approval,
           EXCEPT the one exact routine shape this guard explicitly allows:
           a lone ``gh pr merge <number> --merge`` (optionally with exactly
           one ``--subject <text>``) as the entire command, nothing chained
           before or after it, and no other flag present. That is the one
           step of CLAUDE.md's "Default-branch integration" a standing
           milestone authorization covers without a fresh prompt. A plain
           wildcard in settings.json cannot express this safely (it cannot
           refuse to match ``--admin``/``--squash``/``--rebase``/
           ``--delete-branch`` appearing inside the wildcarded region), so
           the exact-shape check is done here, on real parsed tokens, and
           the settings.json "ask" rule is left as the unchanged default
           for every other ``gh pr merge`` invocation.
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
GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


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


def _segments(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    segments: list[list[str]] = [[]]
    for token in lexer:
        if token in SEPARATORS or set(token) <= set(";&|()"):
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def _program(token: str) -> str:
    name = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _git_subcommand(tokens: list[str]) -> tuple[str, list[str]]:
    index = 1
    while index < len(tokens) and tokens[index].startswith("-"):
        index += 2 if tokens[index] in GIT_OPTIONS_WITH_VALUE else 1
    if index >= len(tokens):
        return "", []
    return tokens[index], tokens[index + 1 :]


def _force_push(arguments: list[str]) -> bool:
    for argument in arguments:
        if argument in {"--force", "--mirror", "--delete", "--force-if-includes"}:
            return True
        if argument.startswith("--force-with-lease"):
            return True
        if argument.startswith("-") and not argument.startswith("--"):
            if "f" in argument[1:] or "d" in argument[1:]:
                return True
        if argument.startswith("+") or argument.startswith(":"):
            return True
    return False


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
    if program == "gh" and tokens[1:3] == ["repo", "delete"]:
        return "Deleting the repository is never part of the workflow."
    if program == "claude" and any(
        token in {"--dangerously-skip-permissions", "bypassPermissions"}
        for token in tokens
    ):
        return "Bypassing permissions is not part of the Hypatia workflow."
    return None


def _pr_merge_auto_allow(tokens: list[str]) -> bool:
    """Only the exact routine shape: ``gh pr merge <number> --merge``,
    optionally with exactly one trailing ``--subject <text>``.

    Deliberately an allowlist of the exact expected shape, not a denylist of
    known-dangerous flags: any flag other than ``--merge``/``--subject``,
    any non-numeric PR identifier, or any extra token anywhere fails this
    check and falls through to the settings.json ask rule unchanged. This
    is checked against real parsed tokens (see ``_segments``), not a glob,
    specifically so a flag like ``--admin``, ``--squash``, ``--rebase`` or
    ``--delete-branch`` can never hide inside a wildcarded region.
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


def command(payload: dict[str, object]) -> None:
    tool_input = payload.get("tool_input")
    text = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(text, str):
        return
    try:
        segments = _segments(text)
    except ValueError:
        # Unparseable quoting: fall back to a conservative force-push check.
        segments = [text.split()] if "push" in text and "--force" in text else []
        if segments:
            _deny("Force-push is never part of the workflow.")
        return
    for tokens in segments:
        reason = _denial(tokens)
        if reason is not None:
            _deny(reason)
            return
    # The whole command must be exactly one safe-shaped call - nothing may
    # be chained before or after it, or the "allow" would cover that too.
    if len(segments) == 1 and _pr_merge_auto_allow(segments[0]):
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
