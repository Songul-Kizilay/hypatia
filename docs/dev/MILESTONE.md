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
| Milestone | Desktop wiring for source revalidation |
| Base SHA | ec1a6f0bc2f6c5b8d1a609b789c8c836d91fffd4 |
| Status | planned |
| Specialists | hypatia-runtime (draft type + controller/desktop wiring, single owner — no runtime/authority-layer change needed, `SourceRevalidationStepOperation`/`SourceRevalidationStepBinding`/`ResearchRunManager` all reused byte-for-byte); hypatia-security and hypatia-qa independently after implementation; hypatia-release last |
| Blockers | none |

Rationale (repository archaeology, 2026-09-22): v0.3.400's own residual list
named this as the strongest remaining candidate. Confirmed fresh, not
assumed: `SourceRevalidationStepBinding(...)` is still constructed nowhere
in `src/` outside its own module and three test files (grep re-run against
current HEAD) — the v0.3.393 `source_revalidation` capability remains
genuinely, completely unreachable from the desktop.

A dedicated read-only investigation (hypatia-runtime) resolved the one real
open question before scoping: source revalidation is not "one more step in
an in-progress multi-step plan draft" — it is a bounded, standalone,
single-purpose plan/approval/execution authored AFTER a source is already
accepted (by any earlier means), bound by `research_run_id` to that
pre-existing run, naming the source's real `observation_id`. This is
directly proven by `tests/integration/test_bounded_source_revalidation.py`'s
own scenario shape (accept a source into an existing run, then author a
SEPARATE one-step revalidation plan/approval/execution against that same
run). Critically, this is not a new mechanism to invent: the desktop
already does exactly this shape of work for a different capability — the
existing "Acquisition" feature (`src/desktop/AcquisitionResearchDraft.py`,
`src/research/ResearchAcquisitionBatchDraft.py::preview_acquisition_batch`)
already builds a new plan of steps bound to an already-existing,
already-populated run, and the generic four-call desktop flow
(`preview_research_plan_draft` -> `preview_plan_authorization` ->
`confirm_plan_authorization` -> `start_authorized_execution`, all in
`DesktopController.py`) already threads an explicit `research_run_id`
end-to-end and already accepts a typed `opening_draft` object to carry
richer `ResearchPlanStepDraftInput` values the free-text "Plan draft"
editor cannot express (confirmed: its legacy tuple format caps at 6
positional fields, `MAX_LEGACY_DRAFT_TUPLE_LENGTH = 6` in
`ResearchPlanStepDraftInput.py`, short of `source_revalidation_binding`).

Other v0.3.400 residuals were re-considered and not chosen: the
budget-refusal-reason-persistence gap touches execution state transitions
and needs more care about idempotency/restart-safety than this milestone's
budget allows; a richer "replanning diff" beyond already-shown proposal
provenance is a smaller, less user-visible increment; Evaluate -> Adapt v2
remains blocked on a human cross-mission authority/budget design decision
(unchanged since the last check); Tool registry + policy engine remains
authority-adjacent (unchanged since the last check, per
`docs/Roadmap/Master_Roadmap.md`'s "Default development order" item 3).

Scope: mirror `AcquisitionResearchDraft.py`'s exact shape for a new
`src/desktop/RevalidationResearchDraft.py` — a frozen, self-validating
dataclass built from `(run, prior_observation_id)` that revalidates itself
against canonical state via `plan_digest` equality (so a stale draft
against a run whose source count changed since preview is rejected, not
silently over-authorized) and exposes the single-step
`ResearchPlanStepDraftInput(capability="source_revalidation",
source_revalidation_binding=SourceRevalidationStepBinding(run.run_id,
prior_observation_id, requested_url, max_sources=len(run.sources) + 1))`.
A small pure builder analogous to `preview_acquisition_batch`. Mechanical
widening of the `QuestionResearchDraft | AcquisitionResearchDraft` union
to include the new draft type at its few call sites in
`DesktopController.py`/`TkinterDesktopWindow.py`. Desktop UI: an
eligible-source picker over the run's existing accepted-sources catalog
(`self._research_source_catalog`), filtering out any `ResearchSourceRecord`
with `observation_id is None` or `requested_url is None` (legacy/back-compat
records — binding them would fail `SourceRevalidationStepBinding`'s own
validation, so the UI pre-filters rather than surfacing an opaque refusal),
feeding the chosen source into the existing preview -> authorize -> start
sequence unchanged. The UI surfaces `SourceRevalidationStepBinding.lines()`'s
existing, already-reviewed wording verbatim ("one explicitly approved
re-fetch only", "not a freshness conclusion") rather than inventing new
copy.

Non-goals: no change to `SourceRevalidationStepOperation`,
`SourceRevalidationStepBinding`, `ResearchRunManager`, or any
authority/budget/execution semantics — all reused byte-for-byte; no
cross-run revalidation (same-run-only stays a hard structural constraint,
unchanged); no automatic or scheduled revalidation; no new eligibility
rule beyond the existing binding validation and the desktop's own
legacy-record pre-filter; no change to Evaluate -> Adapt, cancellation, or
persistence-store code; does not implement the budget-refusal-reason
persistence gap or a richer replanning diff (both remain residual/future
work, not discarded).

Acceptance criteria: the new draft type's `.metadata(...)` output produces
a `ResearchPlanStepDraftInput` that, when threaded through the existing
authorization/execution chain, behaves identically to a hand-constructed
one in `test_bounded_source_revalidation.py` (equality-tested at the
binding/step level); a stale draft (source count or observation state
changed since preview) is rejected via `plan_digest` mismatch, mirroring
`AcquisitionResearchDraft`'s own self-check; the eligible-source picker
never offers a source with a null `observation_id`/`requested_url`; the
desktop path performs a genuine end-to-end revalidation reachable only
through the full manual preview -> authorize -> start chain — no
convenience action skips or shortcuts approval; cross-run attempts (a
binding naming a different run than the one currently selected) are
refused by the existing, unchanged `SourceRevalidationStepOperation.run()`
check, exercised through the new desktop path; full canonical gates green.

Security implications: this is the first desktop feature that lets an
operator directly select a specific PRIOR OBSERVATION to bind into a new
plan step (as opposed to picking a fresh discovery candidate) — the
critical property to verify is that the desktop draft cannot construct a
binding naming an observation/run the operator didn't actually select
(source-identity substitution), and that the entire flow still requires
the full manual authorize/start walk, never auto-executing a revalidation
merely because a source was selected in a picker.

Epistemic implications: none new — revalidation's existing "content
relation, not a freshness conclusion" discipline
(`SourceRevalidationStepBinding.lines()`, `SourceRevalidationStepOperation`'s
own docstring) is unchanged and must be preserved verbatim in any new UI
copy, not paraphrased into something that could read as a freshness
verdict.

Persistence implications: none — no new store, no schema change; the
existing `source_revalidations()`/`recorded_revalidation(...)` durable
record path is unchanged and reused as-is.

Replay/restart implications: none new — `SourceRevalidationStepOperation`'s
existing `recorded_result` idempotency (a restarted execution recognizes
its own already-committed revalidation without refetching) is unchanged
and untouched by this milestone; the desktop draft itself is ephemeral,
nothing persisted.

Authority/budget/target/credential implications: none — no new primitive;
same-run-only enforcement is unchanged and structural (three independent
existing layers, per the prior milestone's archaeology); the ordinary
plan-step network/budget slot is reused exactly as `SourceRevalidationStepBinding`
already declares (`declared_cost=ResearchOperationCost(network_operations=1)`,
subject to the existing cumulative allowance, never a separate budget).

Rationale (repository archaeology, 2026-09-22): with Evaluate -> Adapt v1,
Phase 7 hardening and v0.3.399 all settled (see the prior documentation
reconciliation commit `f5710aa`), the roadmap's own "Default development
order" flags item 3 (Tool registry + policy engine) as authority-adjacent
and requiring an explicit human check-in before autonomous work — so it
was not picked. Two parallel investigations (hypatia-runtime,
hypatia-epistemics) evidenced two safely-boundable candidates instead:

1. A desktop-visible source-revalidation flow (Phase 5's "[ ] User-facing
   revalidation workflow"): confirmed genuinely, completely unreachable
   from the desktop today (not merely buried — `SourceRevalidationStepBinding`
   is constructed nowhere in `src/` outside its own plumbing and three test
   files), reusing 100% existing same-run authority/budget.
2. Wiring the already-delivered, already-tested Evaluate -> Adapt v1
   continuation-proposal mechanism (v0.3.396) into the desktop: confirmed
   `ResearchMissionAuditApplicationService.proposal_for` "is not wired to
   any `BrainRequest` intent or desktop action" (grep across `src/desktop`
   returns no matches for `proposal_for`/`ContinuationProposal`/
   `seed_question`), and CHANGELOG.md's own v0.3.396 entry says so
   explicitly: "No new desktop UI; this is a backend/service-layer seam
   only." Hypatia's current top-level roadmap priority (Phase 6) is
   therefore, today, completely unusable by an actual operator through the
   product — it exists only as a backend service plus an end-to-end test.

Chosen: **(2)**. It closes the more foundational gap — the flagship
capability of the current phase has zero access path — while (1) remains
a strong, independently-valid future candidate (recorded below as
residual/future work, not discarded).

Scope: (1) a new read-only Brain intent (e.g.
`research_mission_continuation_proposal_preview`) that calls the EXISTING,
UNMODIFIED `ResearchMissionAuditApplicationService.proposal_for(plan_id)`
for a selected closed mission and returns either the proposal (with its
existing provenance fields: `origin_run_id`, `origin_plan_digest`,
`origin_stop_reason`, `origin_goal_status`, `origin_evidence_status`,
`origin_evidence_limitations`, `seed_question`) or an explicit,
accurate "not eligible" explanation — never a fabricated proposal, never a
guessed reason; (2) a `DesktopController` method mirroring the existing
`preview_mission_audit_export`/`preview_plan_authorization` read-only
pattern; (3) a "View continuation proposal" button beside the existing
mission-audit controls in "3 Authored analysis" -> "Plan draft" (same
panel as v0.3.399's traceability view, for the same reason: that's where
an operator already reviews a closed mission's result) showing the
proposal read-only; (4) one convenience action, "Use this proposal's
question," that does nothing except `self._research_question.set(seed_question)`
on the desktop's existing question `StringVar` (the exact field
`_preview_question_plan`/`_start_research_goal`/`_select_question_plan`
already read from for manual entry) — zero Brain/network/authorization
calls of its own. After that, the operator walks the entire existing,
byte-for-byte-unmodified preview -> authorize -> start chain themselves,
exactly as if they had typed the question by hand.

Non-goals: no new authority/budget primitive; no auto-approval or
auto-start of a proposal — approving still requires the full manual
preview -> authorize -> start walk, unchanged; no new eligibility rule
(reuses `proposal_for`'s existing `unresolved`/`partially_satisfied`-only
gate exactly as-is; `blocked`/`budget_limited` stay ineligible, matching
the v0.3.396 product decision); no "replanning diff" computation beyond
showing the proposal's own already-existing provenance fields — no new
comparison/judgment logic invented; no change to
`ResearchMissionContinuationProposal`, `continuation_proposal_for`, or
`proposal_for` themselves; no change to Evaluate -> Adapt v2, revalidation,
cancellation, or persistence-store code; does not implement the
budget-refusal-reason-persistence gap or the desktop-visible
source-revalidation flow found during archaeology (both recorded as
residual/future work below, not discarded).

Acceptance criteria: for an eligible closed mission, the new intent
returns a proposal identical to calling `proposal_for(plan_id)` directly
(equality-tested, same idiom as v0.3.399's traceability-graph equivalence
test); for an ineligible mission, an explicit accurate explanation, never
a crash or a fabricated proposal; the convenience button triggers zero
Brain/network calls and, after it fires, the existing preview -> authorize
-> start chain behaves byte-for-byte identically to manual entry
(extending `tests/e2e/test_continuation_proposal_reentry.py`'s existing
proof to the desktop path); no existing Brain intent, `DesktopController`
method, or `TkinterDesktopWindow` behavior changes; full canonical gates
green.

Security implications: the new surface renders a proposal's
`seed_question` (verbatim operator-authored text from the ORIGIN mission,
not external/untrusted content) and typed provenance IDs — no new
untrusted-content-rendering surface beyond what v0.3.399 already
established a pattern for. The convenience button must be proven to make
no Brain call itself (pure `StringVar` population) — this is the one
specific thing hypatia-security must independently trace.

Epistemic implications: none new — `proposal_for`'s existing fail-closed
eligibility gate is reused unchanged; this milestone must not add a
second eligibility check that could disagree with it.

Persistence/replay/restart implications: none — the new intent is a pure
read reusing `proposal_for`'s existing pure-function, nothing-persisted
derivation; nothing new is written, so restart/replay is unaffected by
construction.

Authority/budget/target/credential implications: none — no new primitive
of any kind; the only executable path remains the existing, unmodified
authorization chain, reached only through the operator's own explicit
manual walk-through, exactly as today.

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
| Milestone | v0.3.400: desktop wiring for Evaluate -> Adapt v1 continuation proposals |
| SHA | ec1a6f0bc2f6c5b8d1a609b789c8c836d91fffd4 |
| Linux desktop CI (exact-SHA) | success (run 35744718371) |
| Windows desktop CI (exact-SHA) | success (run 35744722897) |
| Status | delivered |
| PR | #379, MERGED 2026-09-22T15:17:44Z, standard merge commit `d648044c8e82176e6c4d3796bfed6092c39fd804` |
| origin/main reachability | verified: `git merge-base --is-ancestor ec1a6f0 origin/main` succeeds; `origin/main` HEAD is the merge commit itself |

Post-merge verification (2026-09-22, hypatia-lead): PR #379 base `main`,
head `feature/structured-learned-memory-extraction-v0.3.118`, carried
exactly 2 commits (v0.3.400 plus the prior documentation-reconciliation
commit `f5710aa`, also confirmed reachable from `origin/main`), 13 files,
`mergeStateStatus: CLEAN`, both PR-triggered checks `SUCCESS`. Merged with
`gh pr merge 379 --merge --subject "..."` — no interactive confirmation
prompt, consistent with the guard's narrowed auto-allow proven on the
previous milestone. Author/committer identity on both carried commits
confirmed unchanged (Songül Kızılay via GitHub noreply email). Working
tree clean after merge except this ledger edit.

Note: v0.3.399 (SHA `650bfe486bb326635ea8aa4dd9c3b80dbc746c5b`), v0.3.398
(SHA `3cf726a6c16b181bf26ae4d67cea690e84f2ce9a`), and v0.3.397 (SHA
`aeff7713a8fea7efd247892272c78a80b9d16176`) all remain reachable from
`origin/main` as ancestors of v0.3.400 (this row), which is now the
current last-delivered product milestone.

Developer-infrastructure changes (for example the Claude team setup) are not
product milestones and do not bump the version.
