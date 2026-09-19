# Hypatia development constitution

This file governs how Claude Code develops Hypatia. It is developer
infrastructure, not a Hypatia runtime feature. Team roles live in
`.claude/agents/`, the current milestone ledger in `docs/dev/MILESTONE.md`.

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
- A milestone is delivered only when both CI runs pass on the exact pushed SHA.
  Do not start the next milestone, or edit the tree for it, while that CI is
  pending. If CI fails, fix the current milestone first.
- Never merge `main`, rebase just because `main` is ahead, force-push, tag or
  create a GitHub Release without separate explicit authorization.

## Team operating model

The Lead Architect (the main session) inspects first, defines one coherent
milestone, characterizes behavior, identifies authority/data/replay risks and
delegates only where it helps: independent workstreams, isolated review, or
parallel read-only investigation. No subagent for trivial, sequential or
single-file work. The Lead owns the integrated result.

| Role (agent) | Owns |
| --- | --- |
| `hypatia-lead` | milestone definition, decomposition, ordering, integration, readiness |
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
