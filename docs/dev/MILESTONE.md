# Milestone ledger

Hand-edited at milestone boundaries only (never generated), so it does not
dirty the tree during work. The Lead updates it when a milestone is defined;
Release records the delivered SHA and CI in the next milestone's first commit.
Live CI for `HEAD` is reported at session start by `.claude/hooks/hypatia_guard.py`.

Status values: planned, implementation, qa, release, ci-pending, delivered.
`delivered` requires verified reachability from `origin/main` (CLAUDE.md's
"Default-branch integration"), not merely green exact-SHA CI on the
development branch — `release`/`ci-pending` cover that intermediate state.

## Current

| Field | Value |
| --- | --- |
| Milestone | Close the cleanup-failure exception-masking gap in the remaining 10 `JsonFile*Store` classes |
| Base SHA | 46964c41e592bc22b056058ea55613df5e4ea79c |
| Status | release |
| Specialists | hypatia-runtime + hypatia-epistemics: implementation complete; hypatia-security: APPROVED, no blockers; hypatia-qa: READY WITH NOTES (noted gap — missing round-trip tests in 5 of 10 new test files — closed by hypatia-lead immediately afterward); full canonical gates independently reproduced clean on the final tree |
| Blockers | none |

Scope: v0.3.397 fixed one store's `save()` cleanup `finally` block — an
unguarded `temporary_path.unlink(missing_ok=True)` that could let a
transient cleanup-time `OSError` (e.g. a Windows AV/indexer lock) silently
replace a propagating `ResearchError` — and left a tracked note that the
identical pattern exists, unfixed, in roughly ten other stores. Confirmed by
direct inspection (grep) that exactly these 10 files still have the
unguarded pattern, byte-identical to what v0.3.397 fixed: `src/research/`
`JsonFileResearchKaliOperationAuthorizationStore.py`,
`JsonFileDeferredExecutionGrantStore.py`,
`JsonFileResearchPlanAuthorizationStore.py`,
`JsonFileOneShotDeferredExecutionScheduleStore.py`, `JsonFileHypothesisStore.py`,
`JsonFileFailureLessonStore.py`, `JsonFileReflectionReportStore.py`,
`JsonFileCuriosityQuestionStore.py`, `JsonFileBackgroundTaskStore.py`, and
`src/security/JsonFileVulnerabilityGraphStore.py`. Two of these
(`JsonFileResearchKaliOperationAuthorizationStore`,
`JsonFileDeferredExecutionGrantStore`) persist authority/budget-bearing
state, making this the highest-priority remaining instance of the pattern.

This milestone applies the identical, already-reviewed v0.3.397 fix
(a guarded `_remove_temporary_file` helper wrapping the cleanup unlink in
`try/except OSError: pass`) to all 10 files, plus matching regression
coverage: for each store, a new direct unit test file (none currently
exist for any of these 10 stores — only indirect integration coverage
through higher-level services) proving (a) a genuine mid-write failure
(real partial bytes physically written before the fault) leaves the
destination byte-for-byte unchanged and no temp file behind, and (b) a
nested cleanup failure (the write fails AND the cleanup unlink also fails)
still raises `ResearchError`, never the raw secondary `OSError`, with the
exception cause chain intact.

Non-goals: no change to any store's schema, public read/write API, or what
gets persisted; no change to authority/budget/target/credential semantics
anywhere (this only affects which exception type propagates from a rare
double-fault during cleanup, never what is written or who may write); no
change to the already-fixed/already-guarded stores from v0.3.397 or
earlier; no new store, no new persistence mechanism.

Permanent invariants affected: none weakened. This closes a fail-open gap
(a masked `ResearchError` could let a caller misinterpret a failed durable
write as some other, unhandled exception) toward the existing fail-closed
contract every one of these stores already claims.

## Last delivered product milestone

| Field | Value |
| --- | --- |
| Milestone | v0.3.397: fix cleanup-failure exception masking in the execution store |
| SHA | aeff7713a8fea7efd247892272c78a80b9d16176 |
| Linux desktop CI | success (run 35516821367) |
| Windows desktop CI | success (run 35516822640) |

Developer-infrastructure changes (for example the Claude team setup) are not
product milestones and do not bump the version.
