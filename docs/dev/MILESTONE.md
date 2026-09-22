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
| Milestone | Mission audit traceability view — in-app provenance graph browsing |
| Base SHA | b1c0354ea7f2efeaede4fb84077699677e46ebfc |
| Status | delivered — see "Last delivered product milestone" below for release/CI/PR/reachability detail |
| Specialists | hypatia-epistemics (graph read model) then hypatia-runtime (Brain intent + desktop wiring), implementation complete; hypatia-security: one Medium finding (missing epistemic-tentativeness caveats in the new Treeview), fixed and verified; hypatia-qa: full canonical gates green (6530 then 6542 tests after fixes) plus 4 coverage/defect findings, all fixed and verified (one architecture-wide pre-existing gap — no real Tk `Treeview` construction anywhere in the test suite — recorded as residual, not a regression); hypatia-release delivered v0.3.399 |
| Blockers | none |

Rationale (repository archaeology, 2026-09-22): Master_Roadmap.md was
reconciled at v0.3.395 and is stale relative to v0.3.396-398. Two apparent
"next in order" candidates were investigated and ruled out with evidence
before this milestone was chosen.

Evaluate -> Adapt v2 (bounded source-revalidation proposal): the fetch-based
`source_revalidation` plan step (v0.3.393) is a hard single-run construct at
three independent layers (`SourceRevalidationStepBinding`'s single
`research_run_id` field, `SourceRevalidationStepOperation.run()`'s explicit
same-run refusal, `ResearchRunManager`'s hardcoded
`earlier_run_id=later_run_id=run.run_id`), with a dedicated refusing test
(`tests/research/test_source_revalidation_step_operation.py::test_cross_run_provenance_is_refused_without_authority`).
Real cross-mission revalidation linking requires new cross-mission
authority/budget-boundary design — out of scope for autonomous execution
per this constitution's stop conditions.

Phase 7 persistence/cancellation/timeout hardening: confirmed already
substantially implemented and tested (`src/core/CancellationSignal.py`,
`ResearchPlanExecutionApplicationService.process_cancel`, distinct
`CANCELLED`/`INTERRUPTED` statuses, `cancelled != failed` and
`interrupted != failed` both directly proven by
`tests/research/test_research_plan_execution_state.py`,
`tests/research/test_concurrent_execution_state.py`,
`tests/research/test_research_plan_execution_snapshot.py`; real per-request
LLM/HTTP/Kali timeouts already exist). Master_Roadmap.md's Phase 7
"confirmed absent" language is wrong and should be corrected in a future
documentation pass. The only genuinely open residuals (WSL in-guest
process-tree cleanup on Kali timeout; a truncated-valid-prefix-on-load test
fixture) are each too narrow for a milestone alone, and a real unified
error taxonomy is either decorative or architecturally large (2,300+ raise
sites) — neither is a bounded next milestone.

Direct inspection of `src/research/ResearchMissionAudit.py` found a real,
still-open gap instead, matching Master_Roadmap.md Phase 4's `[ ]`
"Provenance visualization": `build_mission_audit`'s `_traceability()`
function already computes a complete provenance graph (claim -> evidence ->
source observation -> discovery candidate; contradiction -> claims ->
evidence; comparison review -> note -> evidence -> sources; revalidation ->
paired observations), but `ResearchMissionAuditApplicationService` only
exposes it through a 24,000-character-truncated flat Markdown preview
(`MAX_MISSION_AUDIT_PREVIEW_CHARACTERS`) and a two-file export-to-disk
action (`TkinterDesktopWindow.py`, no structured in-app traceability
browsing exists anywhere at milestone-lock time).
An operator must leave the app and open the exported files to see a
mission's actual provenance structure.

Scope: (1) a new typed, frozen, Tkinter-independent graph read-model type in
`src/research/` (hypatia-epistemics) that re-shapes `_traceability()`'s
existing output into explicit nodes/edges — zero new relations, zero new
inference, unresolved references stay explicitly unresolved exactly as
`_traceability()` already reports them; (2) a new read-only Brain intent on
`ResearchMissionAuditApplicationService` (hypatia-runtime) built from the
exact same `build_mission_audit(...)` call `render()`/`_preview()` already
use — no new computation path, no mutation, no network/model/provider call;
(3) a new read-only `ttk.Treeview` widget in the desktop app (hypatia-runtime)
letting an operator expand claim/evidence/source/contradiction/comparison-
review/revalidation chains in-app, reusing existing safe-text normalization
for untrusted source titles/URLs. Existing preview/save export behavior is
completely unchanged (strictly additive third way to see the same
already-computed data). Landed placement (confirmed during implementation):
the "3 Authored analysis" -> "Plan draft" sub-tab, directly beside the
pre-existing mission-audit export buttons it was scoped against — not
"4 Review & export" as originally assumed when this milestone was locked;
see CHANGELOG.md/PROJECT_STATUS.md v0.3.399 for the corrected location.

Non-goals: no new inference (no automatic independence/freshness/mirror/
syndication detection); no change to `build_mission_audit`'s computed
semantics or the existing Markdown/JSON export format; no new persistence,
store or schema version; no new authority/budget/approval primitive; no
cross-mission graph; no canvas/force-directed rendering (`ttk.Treeview` is
sufficient and avoids new rendering-security surface); no changes to
Evaluate -> Adapt, revalidation, cancellation or persistence-store code.

Permanent invariants affected: none. This is a pure read-only presentation
layer over already-computed, already-tested canonical data; it introduces
no authority, no budget, no target, no credential and no inferred
provenance.

## Last delivered product milestone

| Field | Value |
| --- | --- |
| Milestone | v0.3.399: mission audit traceability view — in-app provenance graph browsing |
| SHA | 650bfe486bb326635ea8aa4dd9c3b80dbc746c5b |
| Linux desktop CI (exact-SHA) | success (run 35717168075) |
| Windows desktop CI (exact-SHA) | success (run 35717170758) |
| Status | delivered |
| PR | #378, MERGED 2026-09-22T10:53:55Z, standard merge commit `bfc7fd82eb7588211816515f40f2c38c15d861a7` |
| origin/main reachability | verified: `git merge-base --is-ancestor 650bfe4 origin/main` succeeds; `origin/main` HEAD is the merge commit itself |

Post-merge verification (2026-09-22, hypatia-lead): PR #378 base `main`,
head `feature/structured-learned-memory-extraction-v0.3.118`, carried
exactly 3 commits (v0.3.399 plus the two already-reviewed prior dev-infra
guard-narrowing commits `2d7005b`/`b1c0354`, both also confirmed reachable
from `origin/main`), 17 files, `mergeStateStatus: CLEAN`, both PR-triggered
checks `SUCCESS`. Merged with `gh pr merge 378 --merge --subject "..."` —
the guard's narrowed auto-allow accepted this exact routine shape with no
interactive confirmation prompt, the first live test of that permission
change, and it passed. Author/committer identity on all three carried
commits confirmed unchanged (Songül Kızılay via GitHub noreply email).
Working tree clean after merge except this ledger edit.

Note: this row previously recorded v0.3.398 as last delivered. v0.3.398
(SHA `3cf726a6c16b181bf26ae4d67cea690e84f2ce9a`) and v0.3.397 (SHA
`aeff7713a8fea7efd247892272c78a80b9d16176`) both remain reachable from
`origin/main` as ancestors of v0.3.399 (this row), which is now the
current last-delivered product milestone.

Developer-infrastructure changes (for example the Claude team setup) are not
product milestones and do not bump the version.
