# Hypatia development constitution

This file governs how Claude Code develops Hypatia. It is developer
infrastructure, not a Hypatia runtime feature. Team roles live in
`.claude/agents/`, the current milestone ledger in `docs/dev/MILESTONE.md`.
Long-term product direction, phase ordering, and the implemented/planned
distinction are canonical in `docs/Roadmap/Master_Roadmap.md`; this file
governs engineering process, not product scope.

## Ground truth before claims

- Inspect the repository, tests and `git` state before stating anything about
  them. Never speculate about code you have not opened.
- Distinguish implemented behavior from planned behavior. README, roadmap,
  comments and module/folder names are not evidence that something works.
- Investigate before answering; characterize existing behavior before changing it.
- Every important claim in a report must be grounded in an inspected file, test
  or command output.

## Change discipline

- Preserve working behavior. Prefer small, incremental, reviewable changes; no
  broad architectural rewrite unless the milestone requires it.
- One coherent milestone at a time. Do not modify unrelated user changes; stage
  only the files the milestone owns.
- Clean up temporary scratch files; keep them out of the repository.
- Heredocs in this environment can corrupt backslashes: write source containing
  escapes with file-edit tools, and edit files that may hold stray CR bytes
  byte-safely.

## Hypatia invariants (never weaken)

- No silent authority expansion, no hidden budget, no unsafe replay, no
  invented provenance, no backfilled legacy fields.
- Runtime authority is deterministic. Description is not authority; a model
  saying it can do something never makes it executable.
- plan created != work performed; source fetched != evidence; evidence !=
  verified claim; execution completed != goal satisfied; historical
  observation != current truth; revalidation != freshness; model confidence !=
  evidence; chat != research execution; restart != fresh authority or budget.

## Quality gates (milestone boundary)

Focused tests while developing; the full suite once per milestone, never in
parallel with another heavy run.

```bash
.venv/Scripts/python.exe -m unittest discover -s tests -t .
.venv/Scripts/python.exe -m black --check .
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m mypy src
git diff --check
```

Single module: set `PYTHONPATH="src;."` and run
`.venv/Scripts/python.exe -m unittest tests.<package>.<module>`.
If Windows Application Control blocks a standalone executable, use the Python
module form. Never disable or bypass host security controls, and never use
`--dangerously-skip-permissions` as part of the workflow.

## Delivery

- Version: `pyproject.toml` and `src/core/Version.py`; document in
  `CHANGELOG.md`, `PROJECT_STATUS.md` and the relevant README/roadmap section.
- Commit subject `v0.3.NNN: <milestone>` via `git commit -F <file>` with the
  required co-author trailer. Use the Git CLI; push the current feature branch.
- After push: `git fetch origin`; `HEAD` must equal `@{u}`; dispatch
  `Linux desktop` and `Windows desktop` (`gh workflow run <name> --ref <branch>`)
  and check both with `gh run list --commit <sha>`.
- Both exact-SHA CI runs passing on the development branch is a milestone
  prerequisite, not delivery. Do not start the next milestone, or edit the
  tree for it, while that CI is pending. If CI fails, fix the current
  milestone first.
- Default-branch integration (permanent process rule): once exact-SHA CI is
  green on the development branch, the release commit must reach `main`
  through a GitHub PR merged with a standard merge commit before the
  milestone is COMPLETE — see "Default-branch integration" below. This is a
  standing, expected step of every milestone, not a one-off exception
  requiring separate authorization each time.
- Never rewrite or rebase already-published history, amend a pushed commit,
  squash- or rebase-merge a milestone PR, or force-push `main` — for any
  reason, including manufacturing GitHub contribution activity. Never create
  empty/spam commits for that purpose either. Tagging and creating a GitHub
  Release still require separate explicit authorization each time; the
  standard merge-commit integration below does not.

## Default-branch integration

A product milestone is delivered only once its release commit is reachable
from `origin/main` — not merely pushed with green CI on the development
branch. After exact-SHA CI passes on the development branch:

1. `git fetch origin`, then check whether the release SHA is already an
   ancestor of `origin/main`
   (`git merge-base --is-ancestor <release-sha> origin/main`). If yes,
   record that and the milestone is COMPLETE.
2. Otherwise, reuse an appropriate already-open PR from the development
   branch to `main` if one exists, or open one. Title it to describe the
   version range being synced; state in the body that included commits
   already passed their own milestone-specific gates and exact-SHA CI.
3. Before merging, verify: base is `main`, head is the intended development
   branch, the release SHA is included in the PR's commit range, the diff
   has no unexpected files or unrelated history, there are no merge
   conflicts, and both PR-triggered Linux and Windows checks are green.
4. Merge with a standard merge commit — never squash, never rebase-merge —
   so the existing authored commits and their authorship are preserved
   exactly.
5. `git fetch origin` again; verify the PR is `MERGED`, the merge commit
   exists on `origin/main`, the release SHA (and every commit the PR
   carried) is reachable from `origin/main`, and author/committer identity
   on the affected commits is unchanged.

Only once this is verified may the milestone be reported COMPLETE. If
GitHub requires interactive authorization to merge, ask before proceeding.
Stop and report — do not improvise around — any unexpected history,
suspicious diff, failing check, merge conflict, branch-protection issue, or
provenance problem found during this sequence.

## Standing milestone authorization

When the user explicitly instructs the Lead to carry one bounded milestone
through implementation, review, release, CI, PR, and main integration, that
instruction is already authorization for the routine steps of that
lifecycle — pushing the release commit to the existing development branch,
creating the expected PR to `main`, waiting for and inspecting PR-triggered
CI, merging that verified PR with a standard merge commit, fetching origin,
and the post-merge reachability/provenance verification. Do not stop to ask
again between these routine stages merely because they touch git/GitHub;
the milestone authorization already covers them.

This does not relax any other rule in this file, and does not apply at all
if any of the following would be required — stop and ask first, always,
regardless of any standing authorization: widening product scope;
introducing or widening an authority class; granting fresh budget
automatically; changing target identity; changing credential authority;
adding automatic runtime execution; introducing an autonomous
planning/research loop; weakening a permanent security/epistemic
invariant; force-pushing; rewriting or destructively rebasing/amending
already-published history; bypassing branch protection; bypassing a
failing required check; merging a conflicted PR; merging unexpected or
unrelated commits; deleting an important branch, tag, or history; changing
repository visibility; changing GitHub security/access settings; any other
destructive repository operation; or any material ambiguity about what was
actually authorized.

Mechanism: `.claude/hooks/hypatia_guard.py`'s `command` PreToolUse guard
auto-allows exactly one shape without a prompt — a lone
`gh pr merge <number> --merge` (optionally with one `--subject <text>`) as
the entire command, nothing chained before or after it. This is an
allowlist of that exact shape, not a denylist of dangerous flags: a plain
wildcard in `.claude/settings.json` cannot safely express this, because a
`*` cannot refuse to match `--admin`/`--squash`/`--rebase`/
`--delete-branch` appearing inside the wildcarded region. Every other
`gh pr merge` invocation — any other flag, a non-numeric identifier,
anything chained — still hits the existing `Bash(gh pr merge *)` ask rule
in `.claude/settings.json` unchanged. That settings.json rule itself is
untouched by this section; the narrowing lives entirely in the guard's
token-level check, which is auditable and cannot be widened by an
in-conversation wildcard mistake.

## Team operating model

The Lead Architect (the main session) inspects first, defines one coherent
milestone, characterizes behavior, identifies authority/data/replay risks and
delegates only where it helps: independent workstreams, isolated review, or
parallel read-only investigation. No subagent for trivial, sequential or
single-file work. The Lead owns the integrated result.

| Role (agent) | Owns |
| --- | --- |
| `hypatia-lead` | milestone definition, decomposition, ordering, integration, default-branch integration, readiness |
| `hypatia-runtime` | Bootstrap, cognition, execution state, persistence, restart, authority/budget mechanics |
| `hypatia-epistemics` | research runs, evidence, claims, contradictions, provenance, observations, revalidation |
| `hypatia-security` | authorization boundaries, URL/TLS/SSRF, credentials, Kali limits, untrusted content |
| `hypatia-qa` | independent semantic review, characterization/regression tests, gates |
| `hypatia-release` | version, docs, staged diff, commit, push, exact-SHA CI |

Reserved, not active: CVE Intelligence Engineer.

Workflow: Lead inspects and plans -> specialists implement bounded changes and
report files, assumptions and risks -> Security reviews boundary changes -> QA
reviews independently -> Lead integrates -> gates -> Release delivers.

Parallel safety: never let two writing agents edit the same files. Use separate
git worktrees only for genuinely independent implementation streams, after
verifying the base SHA and defining file ownership and integration order.
Read-only agents may inspect concurrently. Give each specialist only the
context and invariants its task needs, never the whole roadmap.

## Secrets

Never place API keys, tokens or credentials in this file, agent definitions,
`.mcp.json`, committed settings, logs or prompts. MCP credentials come from
environment variables or the tool's own secure login.
