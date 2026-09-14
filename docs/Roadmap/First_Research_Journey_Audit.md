# First research journey: implementation gaps and next boundary

Inspected source: `9c7592599e67f5ac1b7cf4a78f5326bb9be9bef5`, v0.3.322.
Date: 2026-09-08. This is a source-backed assessment, not a completion claim.
Windows run `34273389509` and Linux run `34273389534` both succeeded.

## Acceptance scenario

The user's first major milestone is: **Research indirect prompt injection
defenses.** A bounded research loop should complete the ten activities below
without requiring a separate click for every research operation. Approval for
persistence-sensitive or high-risk actions remains separate.

The current opening journey demonstrates a fixed two-step plan, exact human
authorization, zero-step start and bounded continuation. It is not the complete
ten-stage journey. A completed execution is not proof of research sufficiency.

Paths below are relative to the repository root. Proposed behavior is explicitly
labelled; it must not be read as an existing API or as permission to widen tools.

## Ten-stage evidence map

| Requested activity | Current source and behavior | Missing acceptance evidence |
| --- | --- | --- |
| 1. Create a research plan | `src/research/ResearchPlanDraftService.py::preview_question` creates local search + explicit provider discovery. `tests/e2e/test_question_research_handoff.py` proves exact digest survives approval/start. | General question decomposition and the remaining stages are not generated. The opening is a fixed template. |
| 2. Search trusted sources | `SourceDiscoveryStepOperation` selects a registered provider from the approved step and records unaccepted candidate metadata. Crossref/NVD selection is digest-bound. | A known provider does not make every returned claim trustworthy. No verified source-selection policy for the whole journey yet. |
| 3. Fetch a bounded number of sources | `SourceFetchStepOperation` fetches one explicitly authorized URL using `PlanSourceFetcher`. An authored multi-step plan can bound attempts using existing continuation. | Discovery does not create fetch authority. No reviewed candidate-batch handoff is connected; fetched text is discarded after an operation summary. |
| 4. Extract candidate evidence | `EvidenceRecordingStepOperation` resolves a real accepted document chunk and records evidence under exact authorization. | This is recording, not extraction of provisional evidence from unaccepted text. There is no demonstrated candidate-text-to-evidence-proposal path. |
| 5. Compare sources | `SourceComparisonStepOperation` records an authored note citing accepted sources, evidence and assessments. | Automatic candidate comparison is not demonstrated. Recording human-authored comparison text is not synthesis. |
| 6. Identify contradictions | `LLMResearchClaimContradictionProposalProvider` proposes bounded pairs of existing claims for review, with strict output parsing. | It consumes existing claim records, not freshly fetched source bodies. The autonomous journey has no proven source-to-claim connection into this provider. |
| 7. Detect information gaps | `ResearchKnowledgeGapDetector.detect` derives bounded gaps from a run and supplied hypotheses. Acquisition/coverage-gap tests exercise failures and provider coverage. | Integration with provisional research material and the journey's stop/replan decisions remains unproven. |
| 8. Perform additional searches | `CuriosityProposalBuilder.build` creates inert plans from accepted curiosity questions; existing authorization/execution components can run approved plans. | No proven automatic gap-to-requery loop under a single explicitly bounded research envelope. Do not bypass the existing digest checks to supply this. |
| 9. Generate candidate claims | `ClaimCreationStepOperation` records authored text, confidence and epistemic state with run-owned evidence references. | It does not generate candidate claims. A provisional proposal stage and review/promotion contract remain missing from this journey. |
| 10. Produce an evidence-backed report | Existing response composition renders run state; `ResearchRunCompletionStepOperation` closes a run without resolving uncertainty. The older explicit E2E test supplies claims and comparisons by hand. | No complete goal-to-cited-report scenario has been demonstrated. Run closure is not a report generator. |

## Decisive boundary: fetched text has no downstream handoff

`SourceFetchStepOperation.run` receives a `ResearchSource`, checks cancellation
and non-empty content, then returns only a factual acquisition summary.
`ResearchPlanStepOperationResult` has `performed`, `detail`, and `succeeded`;
`detail` is limited to 500 characters. It is not a source-content channel.
The test `test_detail_never_dumps_source_content` protects this separation.

Using `SourceAcceptStepOperation` as an automatic replacement would not fill
the same requirement: it fetches again and invokes the persistent acceptance
transaction. `ResearchSourceContentRecord` describes explicitly accepted,
persisted text. Neither accepted-content storage nor operation detail should
be repurposed to hold unreviewed transient material.

This changes the implementation order: establish an explicit bounded provisional
content handoff before implementing an extractor or claiming multi-source reading.
There is no useful source body for such an extractor in the present fetch result.

## Proposed next implementation slice — not implemented here

Update for v0.3.323: the first backend handoff now exists as
`ResearchSourcePreview` carried by `ResearchPlanStepOperationResult` and the
immediate `BrainResponse`. Advance checks its execution/run/step/requested-URL
binding. Foreground continuation retains at most ten previews, each capped at
65,536 UTF-8 bytes. Status and restart do not restore text. This does not yet
implement batch candidate selection, a desktop reader, extraction or the full
slice below. The preceding summary-only finding describes the v0.3.322 baseline.

Update for v0.3.324: the Source previews desktop tab now presents the latest
transient batch literally, with provenance, source selection and explicit clear.
It is connected to the shared response presentation used by foreground and
desktop-worker continuation. It adds no acceptance, model request or refetch.
Candidate-batch planning and provisional evidence extraction are still missing.

Update for v0.3.325: explicit recorded-candidate batch planning now has a Brain
intent and desktop controller method. It resolves current run/discovery membership
and produces exact URL fetch steps with digest-covered origin receipts. Integration
tests traverse existing approval/start/continuation; a visual candidate selector
and typed handoff to desktop approval remain open. This is not yet the complete
interactive batch path or automatic provisional evidence extraction.

Update for v0.3.326: the Advanced research candidate basket connects exact batch
review to the ordinary approval/start form. Controller-side canonical revalidation
runs again before each authority action. Button-level integration exercises
candidate selection -> exact approval -> zero-step start -> two bounded fetches
with transient previews; real Tk construction/selection is smoke-checked separately.
This closes the manual batch handoff, not autonomous selection or evidence synthesis.

Update for v0.3.327: Source previews can propose exact passages locally using
distinct query-word overlap. Proposals carry original extracted-text character
ranges and preview provenance, not accepted-document IDs. This is a first lexical
candidate extraction path, with explicit limitations; it does not demonstrate
semantic evidence sufficiency, automatic synthesis, promotion or autonomous reports.

Update for v0.3.328: a strict semantic proposal adapter now validates one
structured response against exact temporary bodies, rejecting missing or
ambiguous quotations and retaining their original preview provenance. This is
only an adapter with fake-model contract tests, not a live desktop feature or
semantic quality evaluation. The next missing connection is an explicit
question/source-bound disclosure and budget gate before any configured model
receives the source text. Fetch approval and local display must not imply that
permission. No acceptance or synthesis follows from the generated rationale.

Update for v0.3.329: semantic inputs now have one immutable review contract and
fingerprint, used directly by the adapter. Changed question, limit, source order,
body or provenance invalidates a previously supplied fingerprint before any call.
This fingerprint is not a second authority or a substitute for plan_digest.
Inspection of the existing executor found no model operation in its registry and
no disclosure field in ResearchPlanExecutionContext. The existing accepted-claim
contradiction proposal path calls its provider directly, so copying that path
would not establish the intended per-plan disclosure/model-budget enforcement.
The next integration must bind this review into a typed ordinary plan step,
preserve explicit disclosure through the execution boundary, charge its declared
model cost before an attempt, and refuse lost transient input after restart
rather than refetching. No such execution is enabled by v0.3.329.

Update for v0.3.330: the live operation context now carries disclosure from the
successfully consumed approval through authored/derived Start and Advance/Continue.
This closes the live permission-handoff gap noted above. It does not register a
model capability, enforce endpoint locality or connect semantic input/results.
Restored contexts deliberately carry NONE because durable snapshots do not record
disclosure; restart is not permission to disclose. The next substantive connection
is the typed semantic operation with reviewed-input binding, endpoint/disclosure
enforcement and the existing pre-attempt model-cost accounting, then its desktop
review/approval action. Do not replace these with another review-only wrapper.

Update for v0.3.331: a semantic model operation now runs through the ordinary
registry and executor when explicitly composed. Tests traverse approval preview,
confirmation, zero-step Start, charged Advance and transient proposal results.
The typed binding includes reviewed input fingerprint, endpoint and model;
preview rendering makes them visible. A model-budget choice remains explicit
and defaults to zero. The operation enforces disclosure and destination, and
refuses changed/missing inputs, wrong run/question and cancellation. Existing
plan digests are unchanged when the new binding is absent.
This is an executable backend connection, not a live desktop feature: Bootstrap
registration and the desktop-owned bounded transient request lookup/approval
handoff remain to implement. No live-model quality claim is supported. Restart
still has no permission or automatic refetch. The next work should close that
interactive handoff and test it with the existing source reader and model setup.

An operator-reviewed **reference-source acquisition batch** should reuse the
ordinary plan, authorization and executor, rather than add a second HTTP engine.
Its first deliverable is useful provisional reading, not permanent evidence.

1. Select a bounded set of exact discovery candidates belonging to one run.
   Bind their canonical URLs and discovery provenance into a reviewed plan.
   Changing the set requires a new plan review; candidate text cannot grant URLs.
2. Run ordinary approved fetch steps under existing attempt/network/time bounds.
   Preserve public-HTTPS validation, redirect checks, routing and cancellation.
   Do not add target testing, terminal commands or implicit link following.
3. Carry unaccepted source text through a separate typed, bounded, transient
   result channel. Bind run, execution, step, URL, acquisition time, text digest
   and byte count. Keep bodies out of ordinary detail, logs and execution snapshots.
4. Bound both each document and the retained batch's aggregate UTF-8 bytes.
   Existing `ResearchAutonomyBudget` counts advances, network/model calls and
   elapsed seconds; it does not establish cumulative text/token accounting.
   Choose and test explicit limits before implementation, not after allocation.
5. Show a provisional text preview with provenance and a clear unaccepted label.
   A source body's instructions have no authority. No model call is implied by
   acquiring or displaying it; model disclosure authorization stays separate.
6. Make cancellation and cleanup explicit. Initially, restart may lose transient
   bodies, but must report them unavailable rather than silently refetching or
   accepting them. Persisting provisional content would be a separate decision.
7. Keep later acceptance distinct. Since current acceptance re-fetches, a future
   "accept reviewed content" action must either accept the exact reviewed bytes
   through the canonical transaction or require renewed review if they changed.
   Do not describe a newly fetched page as identical merely because its URL matches.

No new class names or public API signatures are mandated here. First locate a
compatible existing response/presentation seam; introduce a new type only for
the missing provisional-content semantics. Keep existing `source_fetch` callers
compatible and keep content-free durable audit records content-free.

## Required tests for that slice

- Exact approved candidate set; wrong run, stale selection, changed URL and
  duplicate candidates rejected before acquisition.
- Normal, empty, provider-error and cancellation paths; no automatic retries.
- Multi-byte UTF-8 per-document and aggregate bounds; overflow creates no partial
  accepted source, index entry, evidence, claim or hidden model request.
- One failed item is reported honestly without attributing another item's body
  or URL to it; provenance remains attached to each returned item.
- Cleanup/restart cannot turn lost transient text into a new network request.
- Source instructions cannot add capabilities, change the next URL or promote
  source trust. Display and logs do not reinterpret source text as commands.
- End-to-end question -> approved opening -> candidates -> separately reviewed
  acquisition batch -> provisional reader, with fake providers and no real traffic.

## Validation of the present assessment

At the inspected commit, 127 focused tests passed across question handoff,
source fetch, evidence recording, authored claim creation, contradiction
proposals, curiosity acquisition/coverage gaps, curiosity proposals and run
completion. The prior full suite at this same source checkpoint ran 5,803 tests
successfully with 3 platform skips. Those results prove the tested component
contracts, not the missing connections in the table.

This document changes no runtime behavior. The full first major milestone stays
open; no percentage of whole-project completion is inferred from test counts.
