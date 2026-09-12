# Autonomous research connection assessment

## Current connection: v0.3.333

Verified starting checkout: `d9ed83b` / v0.3.332, clean, equal to origin;
Windows and Linux checks for that SHA both passed.

The new desktop action **Research through evidence automatically** confirms a
reference mission once. It uses the original opening planner and extends that
inert plan with three bounded predecessor-dependent slots. The original plan's
digest includes `ResearchMissionScope`, provider, all five capabilities, question
and any typed restrictions. It is consumed once by the existing approval/start
path. The plan is never replaced as observations arrive: concrete operation
inputs are derived in those already-authorized slots, not newly human-approved
plans. This is bounded derivation, not general adaptive replanning.

The existing executor runs this sequence in one autonomy invocation:

1. Local knowledge search against the original question.
2. One query to the originally selected provider; return its canonical discovery ID.
3. Rank that discovery's candidates, choose one distinct lexical match, then
   fetch through the canonical public HTTPS reference transport. Retain and
   inspect its exact bounded preview, including run/step/URL/content identity.
4. Accept those exact bytes through `ResearchSourceAcceptanceService`, without
   refetching a potentially different version.
5. Propose one lexically matching canonical chunk, check its exact content/hash
   against the inspected source immediately before the existing evidence
   recording operation, then persist it in the canonical run.

The resolver owns only bounded transient observations; it cannot create
approvals, execute tools, or write research facts. Plan/execution/run identity
and the original allowance remain unchanged. Five step advances and three
network reservations are cumulative; acceptance conservatively retains its
existing reservation despite making no second fetch. Model spend is zero.
No caller-side Continue occurs. Repeated refused advances stop immediately.

Scope is reference research through one named provider's candidates, never
target testing. The UI refuses to discard a selected target binding or authored
constraints. Candidate URLs and source text cannot alter capability, provider,
question or scope. The canonical fetcher retains its public-address, redirect
and response-size checks. The 16 KiB bound applies to **retained inspected
text**, not a new total transport-byte quota. Time is checked between operations;
an in-flight blocking call still uses the existing provider timeout.

Evidence means a source-grounded excerpt, **not a verified fact**, semantic
understanding, corroboration, or a trusted source. Lexical matching can miss
synonyms or select a superficially related passage. No model reasoning is
claimed. A failed/empty/irrelevant discovery, missing preview, oversized text,
changed chunk, failed persistence, cancellation or spent allowance stops the
slice without retry or automatic widening.

The durable execution snapshot records the original mission digest and existing
spending ledger, without duplicating page bodies. Old snapshots remain readable.
Restart does not reconstruct transient source observations, restore a fresh
budget or replay a fetch; mission rebinding fails closed. Automated crash
resumption is still open.

**Next remaining human boundary:** after evidence recording, comparison and
contradiction investigation still require explicit authored operations. Follow-up
research, adaptive replanning, goal-completion evaluation and a cited final
answer are not yet autonomous. The run remains collecting and the response
explicitly says research is incomplete. The full North Star is not complete.

`tests/integration/test_research_mission_evidence.py` covers the one-confirmation
vertical path with real Brain/controller/planner/approval/executor/acceptance/
knowledge/run and JSON persistence, using deterministic discovery/fetch fakes.
It also covers cumulative spending and larger caller budgets, content tampering,
source instruction injection, provider/scope substitution, empty/failed results,
cancellation, checkpoint failure and refusal without retry. No live provider or
model call is part of this validation.

Local release gates: **5,938 tests OK, 3 existing platform skips**; 146 focused
tests (including 21 new mission tests), Black (846 files), Ruff, MyPy (514 source
files), whitespace checks and a real hidden-Tk layout smoke passed. The layout
contains exactly one mission-to-evidence action and dispatched no research.
Remote CI remains a separate exact-commit check, not implied by local gates.

## Historical assessment before v0.3.333

Inspected baseline: `9f6176d`, runtime v0.3.331; working tree was clean and
Windows/Linux CI passed for that exact commit. The new user brief prioritizes
one goal + scope + budget over manual operation-by-operation continuation.

## Actual architecture and missing connections

| Journey | Existing implementation | Missing connection |
| --- | --- | --- |
| Goal -> plan | `ResearchPlanDraftService.preview_question` produces local search + one named discovery | A fixed opening is not an adaptive strategy; ordinary chat does not grant scope |
| Approval -> execution | `ResearchPlanAuthorizationApplicationService`, `start_for_plan`, `process_advance` | Approval binds one concrete plan, not a mission policy governing future derived plans |
| Automatic progression | `ResearchAutonomyApplicationService.process_run` drives the canonical executor | Only advances declared steps; does not select new work from results |
| Background/recovery | `BackgroundResearchSchedulerApplicationService`, execution/task stores, interrupted states, deferred grants | Demand-driven cycles are not an adaptive goal worker; restored transient text/disclosure are unavailable |
| Discovery -> fetching | `SourceDiscoveryStepOperation`, `ResearchAcquisitionBatchDraft`, `SourceFetchStepOperation` | Candidate selection is human-driven; unknown future URLs cannot spend an old concrete-plan approval |
| Reading -> proposals | Source previews, lexical passages, semantic request/fingerprint, semantic step | Runtime-owned transient input and automatic evidence-stage selection are missing; autonomy currently discards transient advance responses |
| Proposals -> evidence | `EvidenceRecordingStepOperation`, `ResearchRunManager.add_evidence` | Evidence requires accepted document/chunk identity; reviewed transient bytes do not yet enter that canonical path |
| Evidence -> findings | Existing assessment, claim, contradiction, comparison operations and stores | Authored typed payloads exist; goal-directed validated synthesis is not connected |
| Gaps -> follow-up | Curiosity, hypothesis and failure-memory services | Suggestions are not automatically converted into scope-checked, cumulatively budgeted follow-up plans |
| Completion -> report | Run transitions, completion operation, Markdown renderer | Plan terminal status is not goal satisfaction; existing export is an audit, not a sufficient cited executive answer |

The manual boundary is therefore not merely a button. The system lacks an
authority-preserving handoff from a mission to newly derived concrete plans,
and a result-feedback path that decides what is still needed. Pressing Continue
automatically or increasing a loop bound cannot supply either.

## First vertical connection: v0.3.332

The Brain gains `research_goal_start` through a narrow start-request handler.
`ResearchGoalStartApplicationService` owns only the initial orchestration: it
keeps approval access out of the autonomy runner and scheduler. One explicit human
action supplies a natural-language question, the exact opening-template scope,
one configured provider and an explicit budget. It creates an ordinary
ResearchRun, derives the existing opening, records its canonical approval,
starts the existing execution and invokes the existing autonomy loop once.
There is no new executor, planner, scheduler, run type or persistence store.

The desktop uses the existing background request worker and cancellation signal.
One initial confirmation describes the fixed scope and limits; no Continue is
required between local search and discovery. Manual controls remain available.
The result explicitly says research is incomplete, keeps candidates unaccepted,
and returns the canonical run/execution for inspection. No model call occurs.

Duplicate request IDs are blocked within the current process (capacity 50);
concurrent goal starts are refused. Restart loads existing audit state but does
not replay the goal. This is not durable goal-request idempotency or autonomous
crash resumption. An executor refusal without a state transition now stops the
autonomy loop immediately. Nonfinite wall-clock budgets are rejected.

## Next coherent connections, in order

1. Extend existing authorization/run state with a bounded mission policy that
   binds original goal, permitted providers/capabilities, disclosure, source
   selection constraints and cumulative spend. Distinguish derived authorization
   from a new human decision. Never invoke `record_for_plan` as if an unseen
   adaptive plan had been explicitly approved. Keep target testing excluded.
2. Inside the existing autonomy owner, observe persisted discoveries and retain
   bounded transient fetch results. Select distinct sources deterministically,
   derive concrete plans under that policy, and reuse the existing guarded fetch
   operation. Enforce cumulative source/byte/attempt limits and no repeat actions.
3. Reuse semantic proposals and exact quote validation, then connect exact
   reviewed content to canonical acceptance/chunks/evidence without silently
   refetching a different version or assigning trust. Persist provenance once.
4. Connect typed claims/comparison/contradiction and gap evaluation to bounded
   follow-up planning. Use a goal/evidence completion evaluator, not step count.
   Render a candidate cited report with unresolved conflict and limitations.
5. Persist mission authority/progress using the existing ownership/transaction
   conventions; connect its work to the existing scheduler. Test pause, cancel,
   crash ambiguity and safe resumption before enabling unattended recovery.

## Evidence and acceptance status

`tests/integration/test_research_goal_opening.py` uses the exact North Star
question with real Brain, controller, planning, approval, execution, local search
and JSON stores. External discovery is a fake. The caller makes one start call,
never Continue/Advance. Tests cover invalid scope/provider/capability fields,
budgets, cancellation, empty/failed discovery, duplicate requests, audit restart
and immediate stop on a refused advance. Desktop tests exercise one confirmation
and one cancellable worker submission; no hidden UI automation is involved.

The North Star is **not complete**. Fetch, evidence, conflicting-evidence
reasoning, bounded replanning and cited answer generation are not traversed by
this test. Their requested end-to-end acceptance cases remain open, not skipped
tests or claimed successes. No live model or live research network was tested.

Limits retained: the time budget is checked between operations; it does not
preempt a blocking provider call. Existing provider timeouts still apply. The
new opening does not add cumulative content accounting because it fetches zero
bodies. The original question alone is not authority: configured/confirmed scope
and budget are required. Broader mission autonomy remains the product goal.

Local release validation: 5,917 tests run, OK with 3 platform skips; 111 final
focused tests plus Black/Ruff/MyPy and whitespace checks passed. A real Tk
layout smoke found the single new action without dispatching research. Remote
CI is a separate check against the pushed commit, not implied by these results.
