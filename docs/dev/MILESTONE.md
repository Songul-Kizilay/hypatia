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
| Status | planned |
| Specialists | hypatia-epistemics (graph read model, first) then hypatia-runtime (Brain intent + desktop wiring); hypatia-security and hypatia-qa independently after implementation; hypatia-release last |
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
action (`TkinterDesktopWindow.py` tab "4 Review & export" — confirmed by
direct grep, no structured in-app traceability browsing exists anywhere).
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
(3) a new read-only `ttk.Treeview` widget in the desktop's "4 Review &
export" tab (hypatia-runtime) letting an operator expand
claim/evidence/source/contradiction/comparison-review/revalidation chains
in-app, reusing existing safe-text normalization for untrusted source
titles/URLs. Existing preview/save export behavior is completely unchanged
(strictly additive third way to see the same already-computed data).

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
| Milestone | v0.3.398: close cleanup-failure exception masking in the remaining stores |
| SHA | 3cf726a6c16b181bf26ae4d67cea690e84f2ce9a |
| Linux desktop CI (exact-SHA) | success (run 35527021243) |
| Windows desktop CI (exact-SHA) | success (run 35527023066) |
| PR | #377, MERGED 2026-09-20T17:53:32Z, standard merge commit `6871311` |
| origin/main reachability | verified: `git merge-base --is-ancestor 3cf726a origin/main` succeeds |

Note: this ledger previously named v0.3.397 as "last delivered" even though
v0.3.398 (this row) had already been merged to `origin/main` via PR #377
before that entry was written. Corrected 2026-09-22 by hypatia-lead after
independent verification (`gh pr list`, `git merge-base --is-ancestor`,
`gh run list --branch ...`) — ground truth over a stale ledger entry, per
CLAUDE.md's "Ground truth before claims." v0.3.397 (SHA
`aeff7713a8fea7efd247892272c78a80b9d16176`, Linux run 35516821367, Windows
run 35516822640) is also reachable from `origin/main` as an ancestor of
v0.3.398.

Developer-infrastructure changes (for example the Claude team setup) are not
product milestones and do not bump the version.
