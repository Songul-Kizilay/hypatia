# Autonomous research connection assessment

## Current bounded text journey: v0.3.340

### Connected user journey

The desktop Research plan area now offers **Research, learn and explain — preview
permission**. It requests an inert preview from the real goal service, displays
the configured exact endpoint/model, disclosure, question/provider, input and
retention policy, and cumulative limits. One confirmation starts the journey
through DesktopController, Brain, CognitiveEngine and the existing autonomy and
canonical executor. Preview does not create a run, approval, attempt or model call.
Declining it starts nothing. Configuring a model alone grants no research authority.

The new explicit `bounded_semantic_learning_research` scope differs from both the
unchanged zero-model reference scopes and pre-recorded exact-pair execution:

1. Local knowledge search and one selected-provider discovery.
2. Two lexically relevant, distinct public HTTPS references are selected from that
   discovery. Each is fetched once, inspected/accepted from the existing preview,
   and contributes one exactly grounded evidence record and grounding assessment.
3. The first two recorded excerpts are compared using the approved semantic model.
   Exact unique quotes and structured tentative relations are validated.
4. A local comparison-note operation retains the result as **tentative**, citing
   the exact evidence/assessment/source identities and input fingerprint.
5. Possible conflict or an empty supported proposal activates one pre-approved
   follow-up branch: one further candidate from the same discovery is read and
   compared with the first source. It cannot select a fourth source or retry.
   Agreement/not-comparable ends the bounded delivery without running that branch.
6. The report includes the question, research subquestions, actual quoted evidence,
   URLs and hashes, tentative comparisons, an explanatory example, limitations,
   plan adaptation and spending. Existing opted-in failure memory retains canonical
   research lessons and displays relevant prior lessons as advice, never authority.

This is the first bounded text journey, not general autonomous intelligence. The
three subquestions are fixed research scaffolding, not model-generated subject
decomposition. Plan adaptation chooses an originally approved conditional branch;
it does not rewrite the authority or issue a new search query. The report is a
deterministic evidence/interpretation explanation, not a model-written verified
answer. A different URL does not establish source independence. Source relevance
and evidence selection remain lexical; semantic quality is unmeasured.

### Authority, accounting and durable output

`SemanticMissionPolicy` is nested in the existing canonical mission scope/steps
and therefore the existing plan digest. It permits only recorded evidence produced
by this mission's approved selected-provider source chain. It binds endpoint/model,
disclosure, fixed ordered-pair selection, a maximum 8 KiB UTF-8 question/excerpt
payload per model call (fixed instructions/schema are additional), and retention.
The original source-text inspection limit remains 16 KiB cumulatively, across at
most three sources. Evidence from another run, changed records/content, missing
predecessor provenance, changed destination or disclosure is refused before the
model sees anything. Restriction conflicts remain refused by canonical approval.

The existing cost table charges each semantic call as one advance, one network
and one model operation. The complete worst-case plan costs **18 advances / 9
network reservations / 2 model operations**. Acceptance reuses inspected text but
retains its existing conservative network reservation. All costs, including prior
spending and active time, use the one consumed approval's allowance. Running
attempt/checkpoint precedes external invocation; the existing refund-on-checkpoint-
failure and no-refund-after-attempt rules are unchanged. There are no retries,
fallback providers, new permission stores, budgets or execution engines.

Normal success writes source identities/evidence/assessments and labelled semantic
notes through existing research persistence. Optional opted-in failure memory
derives lessons only from canonical run records and preserves provenance. Model
proposals are not promoted to verified claims, contradictions, trust or general
personal memory. The full model proposal body remains transient; bounded notes
retain labelled excerpts/rationale and exact input identity. A crash between the
model call and note operation does not magically recover that body or replay it.

For early delivery, `research_deliverable_ready` stops autonomy and prevents a
later manual advance from spending the unnecessary branch. The plan's unused
steps remain pending rather than falsely completed; the run remains collecting,
not epistemically complete. The background task outcome marks this bounded task
delivered/non-retryable, without changing canonical step statuses. Exhaustion,
malformed output, cancellation, refusal, or unavailable sources yields a truthful
partial report. In-flight transport cancellation is cooperative, not an immediate
socket abort; its late model result is discarded and its attempt stays charged.
Only the learning UI request opts into showing that partial report on cancellation.

### Running and limits

Use the existing configured model and selected discovery provider. Durable mission
approval and execution persistence must be enabled through the existing
`HYPATIA_PLAN_AUTHORIZATION_ENABLED` and
`HYPATIA_RESEARCH_EXECUTION_PERSISTENCE_ENABLED` settings. Advisory durable lessons
are available only with `HYPATIA_FAILURE_MEMORY_ENABLED`; disabled memory stays
disabled and is stated in the report. The learning action displays a fixed maximum
18/9/2 budget before confirmation and uses the entered time limit; it does not
quietly widen an already approved mission. Existing lexical comparison buttons
still perform lexical comparison and never inherit semantic permission.

### Safe restart/resume: v0.3.339

The bounded semantic learning mission can now resume automatically after an
application/process restart only from a durable source/evidence/assessment
checkpoint. The new process rebuilds the content-identical mission plan, checks
its original digest, selected provider, endpoint/model, disclosure and remaining
cumulative allowance, then restores predecessor identities from the canonical
research run. It uses the existing executor/autonomy loop; no second agent,
scheduler, approval or budget exists. Completed steps remain completed and are
not replayed.

The checkpoint keeps only discovery/evidence/assessment IDs, accepted URL
identities, body hashes and inspected-byte accounting. It keeps neither source
text nor a model proposal. An interruption after source fetch but before source
acceptance, or after semantic comparison but before its durable tentative note,
therefore remains restored and reportable rather than refetched or replayed.

Not implemented here: general open-ended replanning, repeated/new provider queries,
semantic source ranking, model-based completion evaluation, independent factual
verification, autonomous target testing, screenshots/image perception or multimodal
learning. Legacy snapshots and a partially executed mission without its new
durable predecessor checkpoint remain fail-closed. No live model/provider call
was used for validation; deterministic
tests do not prove model accuracy or internet source reliability.

### Persisted semantic adaptation: v0.3.340

After the first semantic comparison is structurally validated and recorded as a
canonical tentative comparison note, the execution checkpoint records only its
note ID, input fingerprint and one bounded relation outcome. It does not retain
model output, source text or a second interpretation store. Recovery rechecks
that note in the original run against the original plan digest, recorded source,
evidence and assessment identities, and the exact input fingerprint before the
existing autonomy loop can reach the plan's pre-authorized optional follow-up.

`possible_conflict` and an empty supported comparison may continue into that one
third-source branch; `possible_agreement` and `not_comparable` preserve the
existing early-delivery stop. No dynamic pair selection, new query, provider,
endpoint, disclosure permission, capability or budget can result from the note.
Legacy checkpoints without this adaptation record, altered notes, missing notes,
or any provenance mismatch remain restored and visibly blocked without spending
or replaying a fetch/model operation.

This does not establish general adaptive replanning or autonomous contradiction
investigation. The next boundary is a separately bounded completion evaluation:
it must decide whether the original question has sufficient cited support without
promoting tentative semantic interpretations to verified truth.

### v0.3.340 verification

The real Bootstrap -> controller -> approval -> executor -> durable run/restart
boundary is covered with deterministic discovery, fetch and model substitutes.
New coverage proves one retained conflict continues exactly one authorized
follow-up after restart without duplicating earlier work; changed-note and legacy
checkpoint cases remain visibly blocked before another fetch or model call; and
`not_comparable` remains an honest no-follow-up stop after restart.

Local verification: 58 focused recovery/snapshot/target-binding tests passed;
the full suite passed with **6,054 discovered tests**; Black checked 862 files,
Ruff passed, MyPy passed 523 source files, and `git diff --check` passed. The
full test commands produced no new failure output. No live provider/model call,
push or remote CI trigger occurred.

### v0.3.339 verification and edit scope

Tests exercise actual Bootstrap -> controller -> goal -> approval -> autonomy ->
executor -> fake model -> durable note/report paths, plus desktop confirmation and
cancellation, canonical construction/approval, changed/missing authority/evidence,
cumulative budgets and persisted-attempt ordering. Local final verification:

- Full suite: **6,047 tests run, OK, 3 existing platform skips**, 136.743 seconds.
  This adds 36 tests to the verified v0.3.337 baseline without removing tests.
- Focused research/contract/scheduler/desktop group: 86 tests passed. After the
  final UI compatibility/default-time fixes, all 914 desktop tests also passed.
- Black check: 861 files unchanged. Ruff: passed. MyPy: 522 source files passed.
  `git diff --check`: passed.
- The full process emitted 47 `ResourceWarning` lines, including unclosed
  BufferedRandom handles. These are remaining cleanup warnings, not failing tests
  and not claimed fixed. Git also reported ordinary CRLF-to-LF normalization
  notices, not whitespace-check failures.
- No live model call, push or remote CI trigger. GUI routing/worker behavior was
  exercised deterministically; a live visual desktop session was not evaluated.

The initial full-suite regressions (new stop-reason classification and an optional
worker keyword leaking into legacy UI adapters) were fixed in production code,
not by weakening existing assertions.

The cohesive file allowlist comprises:
- Cognition: CognitiveEngine, ResearchGoalStartApplicationService,
  ResearchPlanExecutionApplicationService, ResearchAutonomyApplicationService.
- Core/desktop: Bootstrap, Version, DesktopController, TkinterDesktopWindow,
  DesktopRequestRunner (only opt-in cancelled-report retention).
- Research: SemanticMissionPolicy, ResearchMissionScope, ResearchPlan,
  ResearchPlanStep, ResearchPlanDigest, ResearchPlanAuthorization,
  ResearchMissionStepResolver, SemanticComparisonStepOperation,
  ResearchAutonomyResult, BackgroundTaskOutcome, ResearchTeachingReport.
- Tests: integration/test_learning_research_journey,
  research/test_semantic_mission_policy, desktop/test_research_goal_start,
  desktop/test_desktop_request_runner.
- Release documentation: pyproject.toml, CHANGELOG.md, this assessment.

## Previous canonical executor support: v0.3.337

The v0.3.336 exact-pair approval contract is now executable through the existing
ResearchPlanExecutionApplicationService when trusted composition supplies
`SemanticComparisonStepOperation` to CognitiveEngine. Its transport is constructed
from one fixed endpoint/model; a different approved destination is refused, not
substituted. The default runtime does not register an operation implicitly.

The same canonical start consumes the exact approval and initializes its existing
allowance. Advance checks affordability, charges the declared 1 advance / 1 network
operation / 1 model operation, and checkpoints the running attempt before the
operation can call the model. Prior spending is retained. Checkpoint failure uses
the existing rollback semantics; operation refusal, invalid model output or
cancellation after this boundary do not refund the attempt or retry it.

Before disclosure the operation verifies the ordered approved evidence against
current run records and accepted source identities, exact run/question identity,
destination and disclosure. Extraction/lexical capabilities cannot dispatch it.
The existing backend still rejects malformed, duplicate and invented-quotation
output and accepts tentative possible agreement/conflict or not-comparable output.
Cancellation is cooperative: an in-flight transport may finish, but its output
is discarded and spending retained. No transport abort is claimed.

**Observable result:** `BrainResponse.semantic_comparison_proposals` returns bounded
`SemanticComparisonStepResult` values from ordinary advance and bounded continuation.
The result binds execution/step identity, the exact request and validated candidates.
It is transient like semantic extraction proposals. Existing execution persistence
records the attempt, outcome summary and allowance, not the candidate body; restart
does not recover that body or silently rerun the model. No truth, evidence, claim,
contradiction or comparison-note write is introduced.

**Remaining boundaries:** automatic mission entry remains model-budget-rejecting,
future/dynamic pairs remain unsupported, desktop comparison stays lexical, and
default runtime destination configuration is not added. No live model calls or
live accuracy evaluation were performed. Autonomous contradiction investigation,
follow-up research, adaptive replanning, completion and cited reporting remain
outside this milestone. There is no new permission store, allowance or retry loop.

Local v0.3.337 gates: 6,011 tests run, OK with 3 platform skips (121.547 seconds).
The focused set passed 77 tests, including 23 new real-executor tests using fake
transport. Black checked 857 files; Ruff passed; MyPy passed 520 source files;
`git diff --check` passed. Resource-cleanup warnings were emitted by the full
suite and are not reported as test failures. No live model call, push or remote
CI trigger was performed.

## Previous approval prerequisite: v0.3.336

Exact-pair semantic comparison is now representable for initial approval through
the existing authored plan draft/preview/confirmation path. The two excerpts must
already exist as canonical evidence in the run, with accepted source identities.
`SemanticComparisonStepBinding` embeds the existing immutable comparison request:
ordered full evidence snapshots, question/run identity and input fingerprint.
Endpoint/model, explicit disclosure and declared capability cost are digest-bound.
The distinct `SEMANTIC_EVIDENCE_COMPARISON` capability is neither extraction nor
local lexical `SOURCE_COMPARISON`.

The existing authorization budget must cover the complete plan: one advance,
one network operation and one model operation per declared comparison. There is
no separate comparison allowance. The canonical verifier rechecks disclosure,
run binding and declared cost policy; confirmation rejects changed comparison
budget/disclosure pending a fresh preview. Source snapshots are rechecked at the
application approval boundary. Preview names the exact content and destination.
Approval persistence stays at schema 3 with no excerpt bodies or new permissions
added to legacy records. Plans without this binding retain their old digests.

**Automatic comparison remains unwired.** No operation registry entry, adapter
connection, model call, new retry or execution loop was added. Automatic mission
entry still rejects unsupported model budgets and the desktop stays lexical.
An authored zero-step start cannot advance this unregistered operation or spend
a model call. Dynamic mission scope does not acquire comparison permission.
Approval of future or dynamically selected excerpts remains unsupported; an
already selected exact pair is required before the initial approval preview.

Next boundary: implement a separately reviewed execution connection for this
exact-pair contract using the existing executor and cumulative allowance, with
current authority and source checks, cancellation and output validation. This
release does not establish live model accuracy or complete autonomous research.

Local release gates: 5,988 tests run, OK with 3 platform skips (93.686 seconds);
83 focused approval/restriction/autonomy tests and 12 target-binding tests passed.
Black checked 854 files, Ruff passed, MyPy passed 518 source files, and
`git diff --check` passed. Fourteen new contract tests use deterministic stored
evidence and fake discovery/fetch. The suite emitted resource-cleanup warnings.
No live model calls, push or remote CI run was performed for this release.

## Previous backend prerequisite: v0.3.335

Starting checkpoint: `93a6ab7` / v0.3.334, clean and equal to origin; Windows
and Linux CI both passed. The user-facing automatic path below is unchanged.

`LLMSemanticComparisonProposalProvider` reuses the existing structured model
interface and duplicate-key rejection. `SemanticComparisonRequest` binds the
original question, run identity, two ordered canonical evidence snapshots and
the candidate limit. It is transient, not a plan digest or disclosure approval.
The model receives aliased excerpts and truncation flags, never operator notes
or model-editable provenance. Maximum input is 16 KiB UTF-8; response at most
16,000 characters and three pairs, with at most 800 characters per quotation
and 500 per rationale. One request, no retry or fallback.

`SemanticComparisonCandidate` requires an exact unique quote from each named
excerpt. It may describe possible agreement, possible conflict, or incomparable
conditions. Relations and rationales remain tentative untrusted interpretations:
mechanical quotation validation cannot verify meaning, truth or independence.
An empty proposal list means no supported proposal, not proof of agreement.

No capability, planner, executor, approval, disclosure, budget, store or desktop
behavior changes in this increment. No autonomous model call or canonical
comparison/contradiction write is introduced. Current zero-model missions
cannot silently acquire semantic powers. The explicit fake adapter invocation
in the recorded-evidence integration test is NOT an authorized automatic path.

**Next implementation boundary:** connect the adapter through a separately
declared initial mission scope that binds its model destination and disclosure,
charges its original cumulative allowance before attempts, and rechecks current
run membership and source integrity. That path must use the existing executor
and recording infrastructure without intermediate human approvals. It must
stop on refusal or invalid output, not retry or expand scope. Semantic quality
evaluation remains distinct from structural tests. Full contradiction
investigation, follow-up research, adaptive replanning, goal completion and a
cited final report are still unfinished.

Local v0.3.335 release validation: **5,974 tests OK, 3 existing platform skips**;
82 focused tests including 19 new unit/integration checks, Black (852 files),
Ruff, MyPy (517 source files) and whitespace checks. The recorded-evidence test
reuses the real mission pipeline with fake discovery/fetch, then explicitly
invokes a fake model adapter and verifies no canonical records, approvals or
spending were changed. No live model accuracy or automatic integration is claimed.
Remote CI requires verification against this exact release's commit.

## Latest user-facing connection: v0.3.334

Starting checkpoint: `695b8bb` / v0.3.333, clean and equal to origin;
both Windows and Linux CI passed for that exact commit.

**Research and compare two sources automatically** is a separate initial
mission choice, not a new approval during a running mission. Its digest binds
the selected provider, two-source policy and eleven ordered capabilities:
local search, discovery, fetch/accept/evidence/assessment for source A,
fetch/accept/evidence/assessment for source B, then comparison. The same
executor and autonomy loop advance all slots without caller-side Continue.
No new agent engine, grant type, scheduler or persistence store was introduced.

The original allowance covers all eleven advances and five network
reservations (one discovery, two fetches and two conservative acceptance
reservations). Acceptance reuses the inspected version, so the deterministic
successful fixture makes three external calls. No model calls are permitted.
The UI refuses an insufficient initial budget; it never silently raises it.

The 16 KiB inspected-text limit is cumulative across both sources, not renewed
for each fetch. Canonical candidate/final URL identity prevents reusing an
acquired reference. Source/evidence/assessment provenance stays in the existing
run records; only bounded derivation observations are transient. Comparison
revalidates both excerpts against indexed content and cites the current
grounding-only assessments. Superseded assessments cannot be silently replaced.
Failures, cancellation and refused advances stop rather than retrying.

The output compares lexical question-term coverage and flags identical fetched
bodies. It explicitly does **not** equate different URLs with independence,
term overlap with corroboration, or missing excerpt terms with a contradiction.
Trust remains unassessed and independence unknown. The run stays collecting.

**Next human boundary:** semantic comparison and contradiction investigation.
Follow-up research, adaptive replanning, completion evaluation and a cited final
answer remain outside the automatic mission. The complete North Star is not
claimed. As before, this text limit is not a transport-byte quota, time checks
occur between operations, and missing transient observations after restart
refuse resumption without refetch or a fresh allowance.

`tests/integration/test_research_mission_comparison.py` exercises the complete
two-source path with real application/domain/persistence boundaries and fake
external providers. Coverage includes shared spending/text bounds, larger
caller budgets, duplicate sources/bodies, changed evidence, superseded
assessments, source-text injection, missing identity, cancellation and no retry.
The existing one-source mission and manual-operation tests remain in place.

Local release gates: **5,955 tests OK, 3 existing platform skips**, 149 focused
tests, Black (847 files), Ruff, MyPy (514 source files) and whitespace checks.
A real hidden-Tk smoke confirmed both mission actions appear exactly once and
do not dispatch research merely by opening the window. Remote CI requires the
exact new commit's result; local checks alone do not establish CI success.

## Previous connection: v0.3.333

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
