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
| Milestone | Deterministic gap-closing guidance on the mission goal explanation |
| Base SHA | 201b1af345f9b853b522bd3f219b886d9c719415 |
| Status | delivered — see "Last delivered product milestone" below for release/CI/PR/reachability detail |
| Specialists | hypatia-epistemics-scope work performed directly by hypatia-lead (single-file, narrowly-bounded literal mapping); hypatia-security: independent review, PASS, no findings; hypatia-qa: independent review, PASS, all seven required test behaviors verified with real differential/equality assertions, full 133-test integration suite re-run clean; hypatia-release delivered v0.3.403 |
| Blockers | none |

Rationale: user-directed. The user approved the prior turn's read-only
reconnaissance of `docs/Roadmap/Master_Roadmap.md`'s "Future direction:
bounded delegated research & evidence-quality completion" as the design
basis, and explicitly locked candidate D ("Confidence and uncertainty made
visible") as this milestone, explicitly excluding candidate A ("Bounded
delegated research continuation") because its authority-policy boundary
still requires a human design decision. Ground truth was re-verified
against the live checkout immediately before implementation (HEAD/upstream
unchanged at `201b1af`, the `ResearchEvidenceCompletionLimitation` enum
still exactly 8 values, `ResearchMissionGoalExplanation.summary()`
unchanged) before locking the milestone, per the user's instruction.

Scope: a private literal `_LIMITATION_GUIDANCE` mapping in
`src/research/ResearchMissionGoalExplanation.py` from each of the 8
existing `ResearchEvidenceCompletionLimitation` values to one bounded,
hand-written guidance sentence describing what recorded evidence gap it
names — no new enum value, no model-generated text, no confidence score.
A new additive `limitations: tuple[ResearchEvidenceCompletionLimitation,
...] = ()` field on the frozen `ResearchMissionGoalExplanation` dataclass,
validated in `__post_init__` exactly like the existing `caveats` field
(type/membership/uniqueness only), populated unchanged from the
already-computed `ResearchEvidenceCompletionEvaluation.limitations` inside
`explain_mission_goal_satisfaction`. `summary()` appends one further
sentence — explicitly labelled "(explanatory only; not a pending action or
a grant of budget/authority)" — only when limitations are non-empty, in
the same order the limitations tuple already carries.

Investigated and confirmed during implementation: this text was already
reachable through two existing, unmodified read paths with zero new
surface needed. `ResearchTeachingReport.teaching_report()` already
embeds `goal_explanation.summary()` verbatim (`ResearchTeachingReport.py:131`);
`ResearchMissionAudit.py`'s `build_mission_audit` already sets its
`report`/`teaching_report` field to that same `teaching_report(...)` call
unmodified (`ResearchMissionAudit.py:174`), and its markdown `_preview()`
quotes that field verbatim in a "## Teaching Report" section
(`ResearchMissionAudit.py:639-650`). So no new Brain intent and no new
desktop widget were added — confirmed necessary by hypatia-qa's
independent re-reading of that call chain, not merely assumed.

Non-goals: no change to `ResearchEvidenceCompletionLimitation` or any
other enum; no automatic/inferred/model-generated guidance text; no
numeric confidence score or percentage (the roadmap's own candidate D
explicitly forbids fabricated percentages without a defensible model); no
new Brain intent; no new desktop widget; no change to
`ResearchEvidenceCompletionEvaluation`, `evaluate_evidence_completion`, or
any authority/budget/target/credential primitive; does not implement
candidate A (bounded delegated research continuation), which remains
explicitly blocked on a human authority-policy decision.

Acceptance criteria (all independently verified by hypatia-qa against a
real test run, not merely read): every one of the 8
`ResearchEvidenceCompletionLimitation` values maps to exactly one
deterministic guidance statement; an empty/sufficiently-supported
`limitations` tuple adds no gap-closing text; multiple simultaneous
limitations render their guidance in the same stable order as the
existing limitations tuple; `ResearchTeachingReport` output changes only
by the appended guidance text (proved by a `dataclasses.replace(...,
limitations=())` differential, not a substring check); `ResearchMissionAudit`
output changes only by the same appended text (proved by construction,
since its `report` field is the same `teaching_report(...)` string
unmodified); existing summary content is byte-for-byte unchanged except
for the new appended section; the guidance path performs no model,
network, execution, persistence, budget, authorization, target, or
credential side effect; full canonical gates green (6620 tests, `OK
(skipped=3)`; Black, Ruff, MyPy, `git diff --check` all clean); the
pre-existing 133-test `tests/integration/test_learning_research_journey.py`
suite re-run clean and unmodified.

Security implications: verified by independent hypatia-security review —
the guidance path is read-only by construction (pure dict lookup plus
string join, no I/O); the new `limitations` field is inert typed metadata
that no other code path branches on to change what executes (grepped
every `.limitations` read repo-wide); all 8 guidance strings are literal,
hand-written text with no interpolation of source/model/note prose; the
file's own "does not interpret source/model prose... does not grant any
new authority" docstring invariant is preserved, reinforced by the new
sentence's own explicit "(explanatory only...)" qualifier.

Epistemic implications: none new — the guidance is a pure presentation
layer over already-computed, already-typed limitation state; it does not
assert that closing a named gap would produce a true or complete answer,
only names what recorded condition is absent, exactly matching this
file's existing reason/caveat rendering discipline.

Persistence/replay/restart implications: none — `ResearchMissionGoalExplanation`
is a derived, non-persisted projection recomputed on demand from canonical
state; the new field carries no status transition and is not written to
any store.

Authority/budget/target/credential implications: none — no primitive of
any kind is created, restored, or altered; this milestone only makes an
existing gap more legible to an operator.

Product-direction compatibility: this is explanation of a recorded
evidence gap, not an epistemic completion decision, a saturation
judgement, or a numeric confidence claim. Candidate A (bounded delegated
research continuation) remains explicitly out of scope and blocked on a
human authority-policy decision, per the user's instruction for this
milestone.

## Historical scope: v0.3.402 (delivered)

| Field | Value |
| --- | --- |
| Milestone | Persist budget-refusal reasons across a status refresh |
| Base SHA | 32d8376fc18a09d5f4beaa60a0fa9e230cbe529c |
| Status | delivered — see "Last delivered product milestone" below for release/CI/PR/reachability detail |
| Specialists | hypatia-runtime: implementation complete, including the critical anti-stranding safety design (rejecting the naive `block_step` reuse that would have permanently stranded refused executions); independent review (security/QA) surfaced three real findings during the implementation cycle — refusal reason not restored across `restored()`, a possible uncaught exception when the execution isn't cleanly running, and possible interference with an actively-running step — all three verified fixed directly against final code by hypatia-lead; hypatia-release delivered v0.3.402 (plus a follow-up test-fixture correction commit) |
| Blockers | none |

Rationale (repository archaeology, 2026-09-22): two candidates were
investigated fresh and in parallel before this milestone was chosen.

**Candidate A (chosen): budget-refusal-reason persistence.** Confirmed
still accurate against current code (hypatia-runtime): in
`ResearchPlanExecutionApplicationService.process_advance()`, the two
budget-refusal branches (`research_plan_execution_budget_refused`, lines
1293 and 1331) never call `state.block_step` or any other durable-state
mutation before returning — the refusal reason exists only in that one
response's `.message`, built from ephemeral in-memory data (the live
allowance). A subsequent `research_plan_execution_status` refresh on the
same execution shows the step still `pending` with no trace an advance
was attempted and declined. Zero existing test coverage of this gap
(confirmed by grep across `tests/` for `budget_refused`/"advance
refused" — the two existing tests that exercise this path,
`tests/integration/test_foreground_execution_control.py::test_an_exhausted_advance_budget_attempts_nothing`
and `::test_a_refusal_before_the_attempt_charges_nothing`, only assert
the one-shot response and allowance numbers, never a subsequent
`status()` call).

**Critical design correction found during investigation**: the naive fix
(reuse the existing `block_step`/`BLOCKED` mechanism genuine capability
failures already use) would be UNSAFE, not merely redundant. `block_step`
sets both the step AND the whole execution to `BLOCKED`, and the only
recovery path, `recover_blocked_step`, accepts exclusively a step whose
`resolution` is `PERFORMED_RESULT_UNKNOWN` — a budget refusal's step
never reaches that resolution (it was never attempted), so reusing
`block_step` would permanently strand the execution with no way back to
`RUNNING`, even after more budget is approved. This is a real behavioral
regression the milestone must not introduce. The correct shape is a NEW,
narrower, additive mechanism that records a step id + reason string
without touching `status`/`step.status` at all, so `_require_running()`
and `next_pending_step_id` keep working exactly as today and the very
next approved allowance lets the step proceed normally.

**Candidate B (investigated, not chosen this cycle): richer
replanning/continuation diff.** Confirmed real but narrower and lower
blast-radius (hypatia-epistemics): a genuinely honest "diff" can only
ever be flat, same-field juxtaposition (`ResearchMissionContinuationProposal`'s
own docstring: "cites... nothing else" — no structural diff primitive
exists anywhere, `plan_digest` is a pure content hash, not a comparator).
Worse, nothing durably records that a new mission originated from a
given proposal — `_use_continuation_proposal_question` is deliberately a
pure client-side `StringVar` mutation with no Brain/persistence call
(v0.3.400's own design), so a genuinely useful "diff" is only honestly
derivable in a SESSION-SCOPED form (juxtapose already-live origin and
new-mission data immediately after the operator completes
preview -> authorize -> start in the same desktop session). A durable
"find it later" comparison would need one new citation-only field on
`ResearchPlanExecutionSnapshot` — confirmed a separate prerequisite
milestone, not something to fold into a "pure presentation, no schema
change" scope without misrepresenting its size/risk. Recorded as
residual/future work below, not discarded.

Also re-confirmed excluded, unchanged since the last check: Evaluate ->
Adapt v2 (still blocked on human cross-mission authority/budget design);
Tool registry + policy engine (still authority-adjacent per
`docs/Roadmap/Master_Roadmap.md`'s "Default development order").

Scope: a new state-transition method on `ResearchPlanExecutionState`
(e.g. `refuse_advance(step_id, detail)`) that records a bounded reason
string tied to the exact step and capability that was refused, WITHOUT
changing `status` or `step.status` — the execution stays exactly as
advanceable as it was before the refusal. A new optional field on
`ResearchPlanExecutionSnapshot` (and the matching field on
`ResearchPlanExecutionState`) following the exact `None`-default /
`.get(key, default)` legacy-load pattern already used for
`mission_stop_reason`/`revalidation_plan_digest` — no schema-version
bump needed, matching this codebase's established convention that
purely-additive-optional fields don't require one. The two budget-refusal
branches in `process_advance()` (lines 1293, 1331 at time of archaeology
— re-locate exact current lines before editing) call the new method
through the same commit/persist plumbing `_blocked()` already uses, and
attach `research_plan_execution=state` to the response (mirroring
`research_plan_execution_status`) so the retained reason renders on the
next status refresh. The field is cleared on the next successful
`start_step` so it never reads as stale. No desktop changes needed: the
existing `_append_response`/transcript path already renders whatever
`research_plan_execution_status.message` composes, so the retained
reason appears automatically once the response layer includes it.

Non-goals: no change to `block_step`/`BLOCKED`/`recover_blocked_step`
semantics; no change to how genuine capability-failure blocks behave;
does NOT extend to the broader, heterogeneous `research_plan_execution_rejected`
call sites (mission-authority mismatch, scope refusal, delivery-ready
refusal, interrupted-step refusal, no-pending-step) — several of those
fire BEFORE a step is even resolved, so "attach to a step" doesn't apply
uniformly, and deciding whether plan-level refusals belong on the
execution record vs. a step record is a separate, larger design question
explicitly deferred, not silently generalized into this milestone; no
new budget/authority/target/credential semantics of any kind; no change
to allowance accounting, `next_pending_step_id`, or the interrupted-step
replay-refusal check; does not implement Candidate B (session-scoped or
durable), which remains residual/future work.

Acceptance criteria: a test proving that BEFORE this fix,
`tests/integration/test_foreground_execution_control.py`'s existing
budget-refusal tests show no persisted trace of the refusal on a
subsequent `status()` call (characterizing the gap), and AFTER this fix,
the same subsequent `status()` call shows the retained reason; a test
proving the field is correctly `None`/absent on legacy snapshots that
predate it (no backfill, no inference); a test proving the field is
cleared on the next successful `start_step`; a test proving `status`
after a refusal remains exactly as advanceable as before (the step is
still `pending`, `next_pending_step_id` still resolves it, a subsequent
approved-allowance advance still succeeds normally) — this is the
regression test for the "would strand the execution" risk the naive fix
would have introduced; a restart/reload test proving the field survives
a `restored()` pass unchanged (or is reasonably cleared, matching
whichever behavior is chosen and documented) without affecting step
status reinterpretation; full canonical gates green.

Security implications: the critical property to verify is that this
field can NEVER be read as authority, budget, or a status signal by any
other code path — it must be provably inert metadata. Confirm nothing
downstream (recovery logic, replay logic, another consumer) branches on
its presence/absence in a way that could change what executes.

Epistemic implications: none — this is execution-state bookkeeping, not
research/evidence/provenance semantics; the reason string must remain a
literal citation of the refusal that occurred (capability, step id,
shortfall), never an inferred narrative about why the mission overall
failed or what should be done next.

Persistence implications: one new optional field, additive-only, no
schema-version bump per established convention; encode/decode follows
the exact pattern already used for `mission_stop_reason`.

Replay/restart implications: none — confirmed by construction: the new
field carries no status transition, so `restored()`'s existing
RUNNING-becomes-INTERRUPTED reinterpretation and all budget/allowance
accounting are completely unaffected. This is the one property every
review pass must re-verify independently, since the entire safety case
for the milestone rests on it.

Authority/budget/target/credential implications: none — no primitive of
any kind is created, restored, or altered. A refused advance remains
exactly as un-executed after this fix as before it; only the explanatory
record of the refusal becomes durable.

Product-direction compatibility: this record explains an execution refusal;
it is not an epistemic completion decision. Resource limits do not establish
evidence sufficiency or research saturation. Delegated continuation, source
independence, primary-source preference, contradiction analysis and uncertainty
remain existing or future concerns outside this milestone's locked scope.

## Historical scope: v0.3.401 (delivered)

The following retained scope is historical context, not part of the current
budget-refusal milestone.

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

## Historical scope: v0.3.400 (delivered)

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

## Historical scope: v0.3.399 (delivered)

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
| Milestone | v0.3.403: deterministic gap-closing guidance on the goal explanation |
| SHA | 848b37d23437a3adb038ef924fb1ca0a4c56455c |
| Linux desktop CI (exact-SHA) | success (run 35786167329) |
| Windows desktop CI (exact-SHA) | success (run 35786172103) |
| Status | delivered |
| PR | #382, MERGED 2026-09-22T21:33:20Z, standard merge commit `52e5223a604592d9cb0df2de8d18b794c43647c7` |
| origin/main reachability | verified: `git merge-base --is-ancestor 848b37d origin/main` succeeds; `origin/main` HEAD is the merge commit itself |

Post-merge verification (2026-09-22, hypatia-lead): PR #382 base `main`,
head `feature/structured-learned-memory-extraction-v0.3.118`, carried
exactly 3 commits (the documentation-only ledger-reconciliation commit
`c0b4134`, the documentation-only skip-count-correction commit `201b1af`,
and v0.3.403's release commit `848b37d`), 9 files, `mergeStateStatus:
CLEAN`, both PR-triggered checks `SUCCESS`. Merged with `gh pr merge 382
--merge --subject "..."` — no interactive confirmation prompt.
Author/committer identity on all three carried commits confirmed
unchanged (Songül Kızılay via GitHub noreply email). Working tree clean
after merge.

Note: this milestone's implementation, independent security review,
independent QA review, and release were all completed directly by
hypatia-lead in one continuous session (no delegated specialist agent for
the single-file literal-mapping implementation itself; hypatia-security
and hypatia-qa each ran one independent review pass as specialist
subagents, both PASS with no findings). Full canonical suite on the
release SHA: 6620 tests, `OK (skipped=3)` — this local skip count is
genuinely evidenced by this session's own full-suite run
(`full_suite_out.log`), for this exact commit only; it does not
retroactively validate or apply to the different, unevidenced v0.3.402
claim corrected in commit `201b1af`.

Note: v0.3.402 (SHA `793b5d70147438cad4a6a38590e61128a00aaa46`), v0.3.401
(SHA `32d8376fc18a09d5f4beaa60a0fa9e230cbe529c`), v0.3.400 (SHA
`ec1a6f0bc2f6c5b8d1a609b789c8c836d91fffd4`), v0.3.399 (SHA
`650bfe486bb326635ea8aa4dd9c3b80dbc746c5b`), v0.3.398 (SHA
`3cf726a6c16b181bf26ae4d67cea690e84f2ce9a`), and v0.3.397 (SHA
`aeff7713a8fea7efd247892272c78a80b9d16176`) all remain reachable from
`origin/main` as ancestors of v0.3.403 (this row), which is now the
current last-delivered product milestone.

Developer-infrastructure changes (for example the Claude team setup) are not
product milestones and do not bump the version.
