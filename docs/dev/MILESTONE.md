# Milestone ledger

Hand-edited at milestone boundaries only (never generated), so it does not
dirty the tree during work. The Lead updates it when a milestone is defined;
Release records the delivered SHA and CI in the next milestone's first commit.
Live CI for `HEAD` is reported at session start by `.claude/hooks/hypatia_guard.py`.

Status values: planned, implementation, qa, release, ci-pending, delivered.

## Current

| Field | Value |
| --- | --- |
| Milestone | none — awaiting next milestone definition |
| Base SHA | - |
| Status | none |
| Specialists | - |
| Blockers | none — hypatia-lead has not yet defined the next milestone |

No milestone is currently open. v0.3.397 (fix cleanup-failure exception
masking in `JsonFileResearchExecutionStore.save()`'s durable-write path, plus
matching regression coverage in both `JsonFileResearchExecutionStore` and
`JsonFileResearchRunStore`) was just delivered; per this ledger's own
convention its exact SHA and CI results move into "Last delivered product
milestone" below in the next milestone's first commit, alongside the
"Current" entry that will define. A tracked, unscoped follow-up from
v0.3.397 for whoever defines that next milestone to consider: the same
unguarded-cleanup pattern it fixed in one store is still present, unfixed, in
roughly ten other `JsonFile*Store` classes in `src/research/` and
`src/security/`, including two authority/budget-critical ones —
`JsonFileResearchKaliOperationAuthorizationStore.py` and
`JsonFileDeferredExecutionGrantStore.py`.

## Last delivered product milestone

| Field | Value |
| --- | --- |
| Milestone | v0.3.396: add Evaluate -> Adapt v1 typed bounded research-plan proposal |
| SHA | 500d22168f6a49a8e919b76b0ea673f05041640b |
| Linux desktop CI | success (run 35509333572) |
| Windows desktop CI | success (run 35509334966) |

Developer-infrastructure changes (for example the Claude team setup) are not
product milestones and do not bump the version.
