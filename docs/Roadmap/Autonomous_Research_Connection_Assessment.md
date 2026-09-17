# Autonomous research connection assessment

## Current bounded text journey: v0.3.387

The longer-term [autonomous cybersecurity mission direction](Autonomous_Cybersecurity_Mission_Direction.md)
is deliberately layered on this runtime. It does not turn the current bounded
text journey into autonomous target testing, vulnerability finding, monitoring,
or general tool orchestration.

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

### Evidence-only completion evaluation: v0.3.341

The teaching report now derives an explicit readiness evaluation from canonical
research-run records and the autonomous stop reason. It reports bounded support,
partial or materially unresolved evidence, source/budget limits, incomplete
execution, or an already-recorded claim contradiction. It also exposes only
coverage facts: accepted sources, evidence-bearing sources, grounded sources and
retained comparison notes.

This is not a lifecycle transition or a truth engine. The evaluation does not
close the collecting run, spend a budget unit, create a claim, interpret model
prose, or upgrade a tentative semantic comparison into a contradiction. A
recorded claim contradiction remains an explicit canonical record; the evaluator
does not infer one from a note. A “sufficiently supported” result means only
that the existing cited material can support this bounded teaching report, not
that the question is universally answered or independently corroborated.

### Mission outcome semantics: v0.3.342

The report now shows a read-only mission outcome that composes the existing
background/execution outcome with evidence readiness. It makes a key distinction
visible: a bounded execution can be delivered or completed while mission-goal
satisfaction remains **not declared**. Budget exhaustion, block, failure and
cancellation remain their existing execution outcomes rather than being relabelled
as evidence truth or mission success.

No new lifecycle, run transition, scheduler behavior or automatic closure exists
here. The separate future boundary is an evidence-grounded, scope-specific goal
satisfaction contract; it cannot be inferred from a completed step list or a
teaching report.

### Evidence-grounded goal satisfaction: v0.3.349

The teaching report now adds a read-only, bounded goal-satisfaction projection.
It composes the existing execution outcome, evidence-only completion evaluator
and the already persisted semantic contradiction-investigation outcome when the
mission has one. The result is one of `satisfied`, `partially_satisfied`,
`unresolved`, `blocked`, `budget_limited`, `failed` or `cancelled`.

`satisfied` is deliberately narrow: the existing bounded execution must have
completed and its canonical evidence must be sufficiently supported. It means
only that the mission deliverable is supported within the retained evidence; it
does not establish a universal answer, select a source winner or promote a
claim. A pending tentative conflict or a durable `unresolved` follow-up outcome
prevents full satisfaction. `structurally_clarified` changes no truth status.

This is not a lifecycle or planning feature. It creates no new authority,
budget, store, provider/model call, retry, follow-up or scheduler behavior; it
does not close the research run or mutate canonical evidence. The next Phase 2
decision remains whether to generalize bounded replanning safely, rather than
mistaking this evaluation for permission to create new work.

### Typed goal explanation in the teaching report: v0.3.350

The deterministic teaching report now renders an operator-facing explanation
of the existing mission goal-satisfaction projection. It exposes only typed,
bounded facts: accepted/evidence-bearing source coverage and a finite set of
reasons such as missing evidence or corroboration, unresolved tentative
contradiction, existing scope/authority block, cumulative budget exhaustion,
failure, cancellation or interruption.

The explanation is a read-only rendering of the existing execution outcome,
evidence-completion limitations and, when present, the durable contradiction
checkpoint. It is neither a semantic adjudicator nor a report parser: source
and model prose cannot alter it. It does not change mission lifecycle,
authorization, cumulative allowance, plan digest, source slots, provider/model
selection, retry behavior or run closure. An unchanged recovered state renders
the same explanation.

### Provenance foundation — discovery-candidate identity: v0.3.387

**Gap (confirmed by a failing test).** Discovery candidates had no identity, and
both selection points (the mission resolver ranking a discovery's candidates,
and manual candidate acceptance previewing one by discovery and URL) passed on
only the URL. Which candidate an accepted source came from could only be guessed
by URL equality, which the provenance rules forbid.

**Change.**

- *Candidate identity*: ResearchSourceDiscoveryRecord.candidate_ids, one
  generated ID per candidate in order, assigned when the discovery is recorded.
  Candidate value objects are unchanged.
- *Selection*: the mission resolver takes the ID of the exact candidate object it
  selected from the discovery record and passes it through the accept step's
  context; manual acceptance takes it from the revalidated preview. The source
  record stores it as discovery_candidate_id, the run's own observation.
- *Integrity* (ResearchRun, on every load): the ID must name exactly one
  candidate in this run's discoveries, the source must have a recorded requested
  URL, and that URL must equal the candidate's URL. Unknown, cross-run and
  mismatched references fail closed. One candidate may back several observations,
  because a later re-fetch is a new observation of the same candidate.
- *Persistence*: run store schema 17. Older discoveries load with no candidate
  IDs and older sources with no candidate; nothing is backfilled from URLs or
  ordering. No checkpoint change was needed: a fetch without acceptance is
  already refused at restart.
- *Audit* (schema 3): each source observation resolves its candidate by ID to its
  discovery, URL and title, or reports unrecorded or unresolved. The run export
  shows the candidate or "unrecorded".

Restart preserves every link without rediscovery, reselection, calls or spend.
No authority, budget, lifecycle, goal or readiness change.

### Provenance foundation — resolved audit trace: v0.3.386

**Gap.** The mission audit's traceability section stopped at source document
IDs. A reader could not see, in one place, which exact source observation an
operator review or claim ultimately rests on, and nothing named the records the
goal evaluation actually reads.

**Change (audit schema version 2, additive).** Every hop follows a recorded ID:

- *Reviews and claims* list each evidence record with its chunk ID and SHA-256
  and resolve it to this run's own source observation: document (content
  version) ID, requested URL, final URL, observed content SHA-256, fetch and
  acceptance times. Claims are marked current or superseded.
- *Source observations* lists every source this run accepted, with the same
  fields; older sources show requested URL and content version as unrecorded.
- *Recorded basis of the goal evaluation* names the comparison notes the mission
  checkpoint recorded (initial comparison, contradiction initial and follow-up,
  evidence-gap follow-up) with their recorded relations and resolved evidence
  lineage, the contradiction and evidence-gap outcomes, and the operator review
  that supports the comparison, if any. It matches the evaluation's
  supported_by_review_id.

A reference that does not resolve (for example a checkpoint note that is not in
the run) is reported with esolved: false and no evidence; it is never matched
by URL, text or content hash. Generation stays deterministic and read-only. No
new persistence, authority, budget, goal or readiness change.

### Provenance foundation — inventory and requested-URL lineage: v0.3.385

**Inventory (read-only).** Within one run, canonical references are exact IDs and
ResearchRun validates them on every load, failing closed:

| Record | Proven links |
| --- | --- |
| Source | document ID = content version; final URL; observed content_sha256 (v0.3.381) |
| Evidence | accepted source; chunk ID/index; chunk SHA-256 |
| Assessment | source; evidence belonging to that source; supersession within the source |
| Comparison note | sources; evidence covering them; assessments citing that evidence |
| Claim | evidence; source IDs must equal the evidence's sources; supersession |
| Contradiction | two persisted claims; evidence equal to theirs |
| Operator review | retained note; evidence equal to the note's; supersession; one current |
| Mission | plan digest, run ID, approval consumption, checkpoint slot identities, stop reason |
| Audit bundle | all of the above as recorded, plus recomputed evaluation |

Cross-run: sources are per-run observations; shared storage is content-version
only (v0.3.381); evidence cannot reference another run's source.

**Gap found.** The requested URL, the root of *resource → fetch observation*,
was not recorded on accepted sources. The HTTPS fetcher records the final URL
after validated redirects. Missions kept the requested URL only in their
execution checkpoint; generic plan acceptance and manual source loads kept it
nowhere, so after a redirect it was unrecoverable. Replay and later revalidation
must request the original resource, and guessing it from the final URL is unsafe.

**Fix.** ResearchSourceRecord.requested_url stores the URL this run requested,
passed by both acceptance callers (plan/mission acceptance uses the step's
authorized URL; manual loads use the entered URL). Run store schema 16; older
sources load with equested_url = None, shown as "unrecorded" and never copied
from the final URL. Two runs sharing a content version keep their own requested
URLs. Mission sources now match their checkpoint slot exactly (requested URL,
final URL, content hash). Run and mission audit exports show both URLs.

**Recorded for later.** The audit's traceability section still stops at source
document IDs; resolving claims and reviews through to source observations, and
naming the decisive records behind a goal outcome, are the next candidates.

No authority, budget, lifecycle, goal or readiness change.

### False-refusal audit — resume after acceptance: v0.3.384

**Boundary.** A slot's fetch and acceptance completed, its evidence step did not
(step 4, 8 or 14: first slot, second slot, follow-up slot). Recovery refused
because evidence selection reads the fetched preview, which is transient.

**Why the refusal was false.** Acceptance makes the preview's content durable,
and since v0.3.381 it is exactly identifiable: the checkpoint records the slot's
requested URL, final URL and body SHA-256; the run holds this run's own source
record with the same final URL and content_sha256; and the knowledge index
holds that content version under its content-derived document ID. Evidence
selection is a deterministic function of that content.

**Fix.** Recovery rebuilds the preview only when all of these agree: the slot's
requested URL is recorded, evidence exists for every earlier slot and none for
this one, the run's source matches the final URL and body hash, the indexed
document exists, and the rebuilt text hashes to the body hash and to the
source's document ID. The mission then resumes, records evidence from the same
chunk a live run would choose, and finishes with the same fetches, model calls,
spend and stop reason as live. The accepted source is never fetched again.

**Still refused.** A checkpoint without requested URLs (legacy), a mismatched
body hash, a missing or different source record, or a missing indexed document
refuses with the original message. Fetch-without-acceptance and
model-without-note boundaries remain correctly refused.

The earlier test that pinned this refusal now asserts the corrected invariant:
the accepted URL is fetched exactly once and no source is duplicated. No
authority, budget, schema, goal or readiness change.

### False-refusal audit — learning mission restart boundaries: v0.3.383

The 18-step learning mission was stopped cleanly after every step and
restarted, for the agreement branch and the conflict branch (which runs the
pre-authorized third-source follow-up). Each restart was compared with the live
mission's fetches, model calls, discovery calls, spend and stop reason.

| Stopped after | Restart | Verdict |
| --- | --- | --- |
| step 1 (local search) | refused: discovery checkpoint unavailable | **false refusal, fixed here** |
| step 2, 5, 6, 9, 10, 12, 15, 16 | resumes; identical to live | correct |
| step 12 → third-source follow-up | follow-up runs exactly once; identical totals | correct |
| step 3, 7, 13 (fetched, not accepted) | refused: transient preview not durable | correct: accepting needs a refetch |
| step 11, 17 (model ran, note not saved) | refused: model output not retained | correct: needs a new model call |
| step 4, 8, 14 (accepted, no evidence yet) | refused: no durable evidence checkpoint | **false refusal, fixed in v0.3.384** |

**Fix.** After local search the checkpoint exists but has no discovery ID, and
recovery refused it. Recovery now resumes such a mission exactly as one with no
checkpoint, but only when the checkpoint is entirely empty, the run holds no
discovery, source, evidence, assessment or comparison note, and no step other
than local search completed. A checkpoint that lost its discovery ID while later
state exists is still refused, and an exhausted network budget still stops the
resumed mission before any provider call. No authority, budget, schema, goal or
readiness change.

### Manual-entry double-submit idempotency: v0.3.382

Manual evidence, assessment, claim and comparison-note entry goes through the
same ResearchRunManager write methods as plan steps. Assessments, claims and
notes use preview → modal confirmation → record; evidence records directly. The
v0.3.377–v0.3.379 replay guards lived only in the plan-step operations, so an
operator re-confirming an identical entry still created a second record.

The exact-repeat refusal now lives in the manager, the one write path:

- **Evidence**: same source, chunk index, stripped-content SHA-256 and note.
- **First assessment**: same source, evidence set, text, trust and all four
  structured judgements (superseding corrections are unaffected).
- **First claim**: same evidence set, text, epistemic state and confidence
  (superseding corrections are unaffected).
- **Comparison note**: same source, evidence and assessment sets and text.

Write previews report llowed = false with a reason naming the existing record,
so the operator sees it before confirming; recording refuses with the same
message, and the manual evidence route shows it instead of a generic failure.
The plan-step guards were removed in favour of this single implementation, and
their replay tests pass unchanged. Anything genuinely different, and every
explicit correction, is still recorded. No schema, authority, budget, goal or
readiness change.

### Version-safe cross-run source identity: v0.3.381

Product decision: content-versioned documents plus run-scoped observations;
knowledge is not isolated per run.

**Problem (confirmed by a failing test first).** A knowledge document's identity
was uuid5(url), the content store refused duplicate URLs, and restoration
rebuilt the URL identity. A second run accepting its own fetch of a URL another
run had indexed failed with "Knowledge document is already loaded", and reusing
that document would have attached content the second run never fetched.

**Model.**

- *Resource*: the URL, unchanged as resource identity (source-identity counting
  still joins on it).
- *Content version*: the document ID is now derived from a SHA-256 of the exact
  representation (URL, title, content type, content resource, acquisition and
  content SHA-256). The same URL with different text is a different version.
- *Observation*: each run's ResearchSourceRecord is that run's own fetch and
  acceptance, with its own etched_at/dded_at and a new content_sha256
  (run store schema 15).
- *Evidence* keeps pointing at the chunk of the exact version its run accepted.

**Behaviour.**

- Different content for the same URL: both versions are indexed and stored;
  each run's evidence resolves to its own text before and after restart.
- Identical content: the second run reuses the immutable stored version (one
  indexed document, one content record) and records its own observation. A
  failed attach never removes the shared version.
- A run that did not fetch a source still cannot record evidence from it; the
  same run accepting the same version twice is still refused at indexing.
- The content store keeps one record per version and no longer requires unique
  URLs. Restoration groups run records by version, requires each to agree on
  the version, accepts any recording run's fetch time, and refuses stored text
  that differs from a run's recorded content_sha256.
- Run and mission audit exports show each source's observed content SHA-256,
  or "unrecorded" for sources accepted earlier.

**Old data.** Documents indexed before versioning keep their URL-only IDs and
restore as legacy documents; their source records load with
content_sha256 = None and gain no version meaning. Nothing is migrated or
rewritten from current page contents.

**Not included.** Freshness, revalidation, HTTP caching, automatic reuse of
another run's content, or a provenance graph. No authority, budget, lifecycle,
goal or readiness change. The manual-entry double-submit gap remains open.

### Recovery false refusal before first evidence: v0.3.380

Found during the source-fetch audit (v0.3.376). Mission recovery validated the
checkpoint's recorded evidence unconditionally, and that validation requires at
least one evidence record. A mission that stopped after discovery but before
its first evidence was therefore refused at restart with "Mission evidence
changed or is missing", even though nothing about it was uncertain.

- **Clean boundary.** A mission stopped between discovery and its first fetch
  now resumes after restart and finishes exactly as a live mission would (same
  fetches and spend).
- **Interrupted first fetch.** It is rebound instead of refused: the step stays
  interrupted and charged, advance still refuses it, the stop reason
  step_interrupted is recorded, and the existing operator ruling ("not
  performed") is now reachable, after which one ordinary, newly charged fetch
  runs. Previously that ruling was unreachable because the mission never became
  live again.
- **Still refused.** A checkpoint with no evidence is accepted only when nothing
  past discovery exists: no acquired URLs, assessments or semantic note in the
  checkpoint, no sources, evidence, assessments or comparison notes in the run,
  and no completed step beyond local search and discovery. Anything else is
  refused as before.

No schema, authority, budget, goal or readiness change.

### Replay/idempotency audit — claims, contradictions, notes, reviews: v0.3.379

- **Claim contradictions (safe, unchanged).** The run manager refuses a second
  contradiction relationship for the same claim pair, so a replay cannot
  duplicate it.
- **Comparison reviews (safe, unchanged).** A note with a current review can be
  reviewed again only by superseding that exact review, so a replay is refused
  as stale.
- **Claims (fixed).** A superseding claim was already refused on replay; a first
  claim was not. The claim step now refuses when the run already holds the exact
  same first claim (evidence set, text, epistemic state, confidence), naming it.
- **Comparison notes (fixed).** No note write was guarded. The comparison step
  now refuses when the run already holds the exact same note (source, evidence
  and assessment sets, text). Mission semantic notes were already protected by
  recovery, which refuses a model comparison without its durable note step.

Every guard fails the step without performed work and names the existing
record; different text, state, confidence or references are still recorded.
Manual (non-plan) writes are unchanged. No schema, authority, budget, goal or
readiness change.

### Replay/idempotency audit — source acceptance and assessment: v0.3.378

**Source acceptance (characterized, no code change).** Acceptance indexes the
document, snapshots its content and attaches it to the run. Replaying it in the
same run is refused by dd_source ("already attached") with the index and
content snapshot rolled back; in the same process the knowledge engine also
refuses to load the document twice. It is duplicate-safe. One limitation was
recorded for a product decision rather than fixed: document identity is derived
from the URL alone, and knowledge is global, so a second run cannot accept a URL
another run already indexed. Reusing the indexed document could attach content
that run never fetched (for example after the page changed), so resolving it
needs content-versioned or run-scoped knowledge, not a narrow guard.

**Source assessment (gap found and fixed).** A superseding assessment is already
refused on replay once its target is superseded. A first assessment had no guard:
in the same crash window as evidence (write persisted, step interrupted, operator
ruling "not performed", retry) it added an identical second current assessment,
and a rebound mission could reach the same path. The assessment operation now
refuses when the run already holds the exact same first assessment (source,
evidence IDs, text, trust, and the four judgements this operation writes as
unknown), naming the existing assessment and failing without performed work.
A different text, trust or evidence set, or a manual assessment carrying other
judgements, is still recorded. No schema, authority, budget, goal or readiness
change; manual assessment entry is unchanged.

### Replay/idempotency audit — evidence recording: v0.3.377

Second capability of the one-at-a-time audit. Characterized behaviour:

- **Identity.** Evidence IDs are random per write. A record stores run, source
  document, chunk ID and index, excerpt, the SHA-256 of the stripped chunk
  content and the note; it stores no execution or step identity.
- **Mission path.** Safe already: recovery refuses a mission whose accepted
  source lacks its durable evidence step, and a mission's notes embed its plan
  digest and source hash, so separate observations never collide.
- **Gap found and fixed.** In a generic plan, dd_evidence persists before the
  step's completion is persisted. A crash between them restores the step as
  interrupted; an operator ruling of "not performed" returns it to pending, and
  the next advance recorded the same chunk and note again under a new ID —
  one observation counted twice. The evidence-recording operation now refuses
  when the run already holds the exact same observation (document, chunk index,
  content hash, note), naming the existing evidence ID. The step fails with no
  performed work; it is neither a duplicate nor a fabricated success.
- **Deliberate behaviour change.** A second, separately started plan that
  authorizes the identical observation in the same run now fails the same way
  instead of creating a duplicate record. A different note, a different chunk,
  or the same text in another run is still recorded.
- **Unchanged / remaining.** Manual evidence recording (a direct operator
  request, not a replayed plan step) is not deduplicated, so a double submit
  can still create two records. No authority, budget, schema, goal or readiness
  change.

### Replay/idempotency audit — source fetch: v0.3.376

First capability of the one-at-a-time replay audit. Characterized behaviour:

- **Operation identity.** A fetch is one authored plan step in one execution;
  the executor only starts the next pending step, so a completed or failed step
  is never started again. Mission slots take the URL from ranked discovery
  candidates, excluding every identity already attempted or acquired.
- **Crash windows.** The running step and its charge are persisted before the
  network is reachable. After restart a running step is interrupted: it stays
  charged, advance refuses it, and only an explicit operator ruling that it was
  not performed returns it to pending for an ordinary, newly charged attempt.
  A failed fetch fails the execution (not resumable) and keeps its run failure.
- **Gap found and fixed.** Live missions excluded the *requested* URL of each
  slot, but checkpoints kept only the validated *final* URL. After a redirect,
  restart lost the requested identity, so a later slot or follow-up could
  select the same candidate and fetch it again (charging network spend before
  the duplicate was detected). Checkpoints now carry equested_urls beside
  cquired_urls; restore uses them exactly as the live process does. A legacy
  checkpoint with acquired sources but no requested URLs refuses recovery while
  a fetch slot is still pending, instead of risking a duplicate fetch.
- **Unchanged.** URL security and redirect validation, authority, budget and
  cost, goal and readiness semantics. Another mission fetching the same URL is
  a distinct authorized operation and is not suppressed.
- **Found for later audits.** Recovery refuses a mission interrupted before its
  first evidence record ("Mission evidence changed or is missing"), a fail-closed
  false refusal; and accepting a source already indexed by another run fails at
  indexing. Both belong to the false-refusal and source-acceptance audits.

### Mission audit bundle: v0.3.375

An operator can now answer, from one exported artifact, what a mission did,
under which recorded approval and allowance, what it spent, which evidence and
reviews bear on its result, and why its derived status is what it is.

- **Sources.** The durable-form execution snapshot (live missions are captured
  exactly as persistence would; restored ones are their loaded snapshot), the
  linked run in its run-store document form, and the approval whose consumption
  names this execution. Goal satisfaction, explanation, readiness and the
  teaching report are recomputed by the existing functions and not persisted.
- **Formats.** mission-audit-<plan>.json (schema hypatia.mission_audit v1,
  sorted keys, typed enum strings, canonical IDs; the snapshot's write time is
  excluded so live and restored audits of the same state are byte-identical)
  and mission-audit-<plan>.md, rendered from the same data with the existing
  run export nested inside. Nothing parses Markdown.
- **Workflow.** Preview renders both files and their SHA-256 fingerprints and
  writes nothing. Saving requires an existing absolute directory, re-renders,
  refuses if either fingerprint changed, refuses if either file exists, and
  publishes both with the existing create-new atomic publisher, removing the
  Markdown file if the JSON file cannot be written.
- **Conservative gaps.** A missing stop reason, checkpoint, allowance, approval,
  run or request ID becomes a typed limitation with null values; no evaluation
  or report is produced without a recorded stop. Recorded URLs with credentials
  (rejected where URLs enter, but checked again here) make the export fail
  closed. The bundle never includes API keys or request headers, which are not
  recorded.
- **Not included.** Replay, provenance graphs and freshness; traceability only
  follows recorded IDs and says "unavailable" otherwise.

### Listing points to restored reports: v0.3.374

The recovered-missions listing is how an operator finds plan IDs after
restart. A terminal mission (for example completed or failed) is never
resumable, so it was listed only as "not resumed" with the rebind refusal, even
though v0.3.370 made its recomputed report available in execution status. Each
not-resumed entry now states either that its report, recomputed from the
recorded stop, is in execution status, or that no stop was recorded and no
report is available. Listing still reads only in-memory recovery outcomes and
durable snapshots; it resumes, renders and calls nothing.

### Export includes recorded judgements: v0.3.373

The deterministic run Markdown export predated operator comparison reviews and
the typed assessment judgements, so an exported audit omitted exactly the
records that can change a mission's goal status or caveats. The export now has
an "Operator Comparison Reviews" section (review, note, decision, evidence IDs,
current/superseded state, supersession and operator reason, with a statement
that a review is a bounded judgement rather than model output or truth) and
lists each assessment's usefulness, applicability, independence and
publication status. Comparison notes, which a mission may derive from a model,
are labelled tentative instead of user-authored. The export remains local,
read-only and deterministic; an earlier exported file no longer verifies
against the current rendering, as with any change to the run.

### Source-independence review of any named mission: v0.3.372

Source-independence review still reached only the last live mission or a
single recovered one. The window now keeps the plan-to-run pairs the runtime
reported (live results and the recovered listing) and reviews the run of the
execution named in the panel, falling back to the last live mission when the
panel is empty. A named execution with no reported run is refused instead of
silently reviewing another mission. The canonical run and the existing
assessment path are unchanged.

### Desktop review of any named mission: v0.3.371

The mission-bound comparison review bound a plan only after a live result or
when startup recovery listed exactly one mission, so with several restored
missions only execution status could reach them. The review now targets the
execution named in the execution panel (filled by the recovered listing, a
live result, or the operator), falling back to the last live mission. The
loaded plan is remembered with its run and note, so the preview names it and
the post-record reload uses it even if the panel is edited in between. The
backend still resolves the run, checkpoint note and report; no new authority,
persistence or execution is involved.

### Restored mission status report: v0.3.370

Execution status for a mission resumed at startup already showed the report
its recovery rendered. A restored mission that was not resumed showed only its
durable step record. Its status now appends the existing teaching report,
recomputed from the durable run, checkpoint, allowance and recorded stop reason
on every request, so an operator review recorded after restart is reflected
immediately. It is not cached or persisted, retains no lesson, resumes nothing
and calls nothing. A legacy snapshot without a recorded stop says so and shows
no goal status.

### Durable mission stop reason: v0.3.369

A mission's outcome, explanation, readiness and teaching report are derived
from its run, checkpoint, allowance and the typed autonomy stop reason. The
first three were durable; the stop reason lived only in process memory, so a
restored mission that was not resumed (completed, failed, cancelled or blocked
executions are never resumable, and a changed model destination refuses
recovery) could not show its result or be reviewed from it.

Execution snapshots now carry an optional `mission_stop_reason` using the
existing `AutonomyStopReason` enum. It is recorded after a live or recovered
mission's autonomy run and bound to the exact immutable execution state it
describes: any later state change makes it inapplicable, a snapshot restored
with a running step drops it, and a rebound (resumed) execution records its own
new stop. Missing values decode as absent and the mission report is refused;
unknown values fail the store load closed. No report prose, authority, budget,
source slot or goal status is persisted, and reading it never resumes work.

### Desktop access to comparison review: v0.3.368

The persisted-comparison-note selector now also exposes the one existing
operator-review action. It shows the selected note's exact source, evidence and
assessment IDs plus the current review state, then asks for explicit
confirmation before calling the existing canonical review service. If a current
review exists, its exact ID is supplied as the supersession target; the service
remains the enforcement boundary and rejects a stale or cross-run change.

This is not a new review system or automatic support path. It adds no authority,
budget, source fetch, model/provider call, lifecycle change or recovery replay.
The same selector works for a canonically reloaded run, so a recovered mission
does not require the operator to reconstruct comparison identities manually.

For a learning mission the desktop also offers a mission-bound review. A new
read-only intent, `research_mission_comparison_review`, resolves the plan's
canonical run and the checkpoint's exact semantic note and re-renders the
existing teaching report; the window previews plan, run, note, evidence IDs,
current review, decision and reason before any write, records through the same
service and reloads so the goal outcome is recomputed, never composed in the UI.
Reviews of other notes cannot satisfy the mission, conflicts and comparison gaps
stay unresolved, and a recovered mission binds the same run and note. A restored
mission not resumed this session has no stop reason to recompute from and is
refused rather than guessed.

### Operator review as the supported-comparison path: v0.3.367

The run already kept operator-authored, revalidated records, but none named one
exact comparison: assessments judge a source, claims judge a statement and claim
contradictions link two claims. v0.3.367 adds the smallest such record: an
operator comparison review of one retained note, with the note's exact evidence,
a typed `supported` or `not_supported` decision, the operator's reason and the
commit time, persisted in the run store (schema 14). A new review of a reviewed
note supersedes exactly its current review, so support is revocable and stale
views are refused.

`tentative comparison -> explicit operator review -> supported comparison`. A
tentative agreement is satisfied and ready only while the current review of the
checkpoint's note is `supported`; the report names the review. The model
relation, note text, trust, independence, claim confidence, source count and
completion never create support, and reviews never lift conflicts, clarified
conflicts or comparison gaps. Restart reloads reviews without authority, budget
or calls. Automatic verification remains out of scope.

### Tentative agreement is not a supported comparison: v0.3.366

The last satisfied comparison path was a first comparison whose relation was
`possible_agreement`. It became satisfied and ready on complete evidence alone,
although the relation is a tentative model interpretation, trust was unassessed,
independence unknown and no claim existed. The model has no supported or
verified agreement state, so learning missions with this relation are now
`unresolved` and not ready, and the explanation says the sources tentatively
agree without a sufficiently supported comparison. `tentative agreement !=
supported comparison`. A mission checkpoint with notes but no recorded relation
fails safe the same way. No learning mission with a mission checkpoint can
currently reach `satisfied`; a future supported-agreement contract would need an
explicit structured state rather than note prose.

### Clarified conflicts are not verified resolutions: v0.3.365

The follow-up branch compares the first source with one new source. When that
tentatively agreed, the outcome `structurally_clarified` previously satisfied the
goal and marked the mission ready, although nothing was verified. No mission
scope defines an objective that identifying the aligned side completes, so any
recorded tentative conflict now leaves the goal `unresolved` and the mission not
ready, and the explanation says the structure was clarified without a verified
resolution. `structural clarification != verified resolution`. Legacy
checkpoints that record the conflict only in `semantic_relation` fail safe the
same way; a mission whose initial comparison agreed remains satisfied.

### Not-comparable sources as an unresolved comparison gap: v0.3.364

When the first two sources were judged `not_comparable`, the mission skipped the
optional follow-up and reported a satisfied, ready goal. Goal satisfaction now
reads that durable relation as an unresolved comparison gap and the explanation
says no supported comparison was established. `not comparable != successful
comparison`: the finding is valid evidence but does not satisfy a comparison
goal. The follow-up remains skipped, so authority, spend and the plan digest are
unchanged. An unresolved conflict follow-up's explanation now also names its
durable follow-up relation.

### Empty-proposal follow-up as a typed comparison gap: v0.3.363

An empty initial proposal activates the pre-approved third-source branch. Its
final observation previously only accepted a contradiction follow-up, so the
authorized branch failed after spending its full budget. The observation now
records a durable `evidence_gap_outcome` (`no_supported_comparison`, or
`followup_comparison_recorded` for a tentative relation with the new source) and
restart validates it against the retained note's canonical provenance.

`follow-up executed != comparison established` and
`no supported comparison != execution failure`: goal satisfaction is
`unresolved` whenever the central comparison supported nothing, readiness stays
not ready, and a legacy checkpoint without the outcome never yields a satisfied
goal or an inferred result.

### Prior lessons before approval: v0.3.362

Failure memory recalled matching lessons only in the report after a mission had
already spent its budget. The inert learning preview now shows the same
read-only advice before the operator approves, so an earlier failure (for
example a query whose discovery returned nothing) is visible at the decision
point. `stored lesson != verified fact`: advice is labelled as not instructions,
authority or evidence, and the preview still writes and calls nothing.

### Clarified tentative conflicts stay visible: v0.3.361

When the follow-up branch compared a third source and did not conflict, the
durable outcome is `structurally_clarified` and the goal can be satisfied. The
explanation previously said nothing about the original tentative conflict. It
now adds a bounded reason from the checkpoint: the follow-up clarifies structure
only, does not resolve the original disagreement and does not show either source
wrong. `follow-up performed != contradiction resolved`; satisfaction and
readiness are unchanged.

### Independence review for recovered missions: v0.3.360

The operator source-independence review only knew the run of a mission started
in the current session, so a mission resumed after restart could not be
reviewed from the desktop. The recovered-missions listing now carries each
mission's canonical run ID, and a single listed mission names its run for the
existing review. `operator judgement != model truth` still holds: judgements go
through the unchanged assessment and supersession path.

### Startup recovery outcome shown on completion: v0.3.359

When deferred startup recovery finishes having resumed or refused a mission, the
desktop renders the existing read-only recovered-missions listing in the
execution panel and names a single mission for Refresh status. A launch with
nothing to recover changes nothing on screen. This is presentation of existing
in-memory state only.

### Cancellable desktop startup recovery: v0.3.358

The deferred recovery request now carries the desktop's cancellation token into
each resumed mission's existing cooperative autonomy cancellation. A cancelled
in-flight mission keeps its recorded charge and retains no new lesson; missions
not yet started stay restored with a visible cancellation reason. Cancellation
does not reopen the once-per-process pass and grants no authority.

### Non-blocking desktop startup recovery: v0.3.357

Startup recovery previously ran inside runtime initialization, before the
desktop window existed, so a resumed mission's bounded fetch and model calls
held up launch with no visible window or cancellation surface. The desktop now
defers that pass and runs it on its single request worker once the window is up.
`restart != fresh authority`: the deferred pass is the identical exact-mission
resume, runs at most once per process within recorded allowance, and a repeat
request does nothing. Headless composition is unchanged.

### Failure-lesson retention for resumed missions: v0.3.356

A live learning mission retains opted-in failure lessons after it reports; a
mission resumed by startup recovery previously did not. Recovery now uses the
same lesson-retention helper and failure memory whenever the resumed autonomy
run returns a result, appending prior advice and the retention result to the
recovered report. `recovered lesson retention != new execution` and
`restart != fresh authority`: stable lesson IDs make a repeated retention a
no-op, and refused recovery retains nothing.

### Discoverable startup mission recovery: v0.3.355

A recovered report is only useful if the operator can name its mission. The
desktop execution controls now list this session's startup recovery outcomes —
resumed with a teaching report, or refused with its reason — through a read-only
`research_plan_execution_recovered` request. A single listed mission fills the
execution field for the existing Refresh status. Listing performs no research
work and grants no authority.

### Teaching reports for missions resumed after restart: v0.3.354

Startup recovery previously discarded the autonomy result of a resumed learning
mission, so completed work had no visible cited report. Recovery now renders the
existing teaching report from the canonical run, durable checkpoint and
cumulative spend whenever the resumed autonomy run returns a result, and keeps it
in memory for that session. The mission's execution-status response appends it.

`restart recovery completed work != goal satisfied` and
`recovered report != new execution`. Refused or failed-closed recovery keeps its
refusal without a report; no report is persisted; retrieval performs no fetch,
provider or model call and changes no spend, lifecycle, plan digest, scope,
checkpoint, authority or run closure.

### Operator source-independence review: v0.3.353

The desktop mission result now offers **Review source independence**. It loads
the mission run from canonical state, lists only accepted evidence-bearing
sources with their current judgement, and records an operator's `independent`,
`derivative`, `likely_duplicate` or `unknown` judgement through the existing
assessment preview/confirmation/record path. The reviewed current assessment is
superseded exactly; a stale review is refused by the existing already-superseded
check, and other judgement dimensions are carried forward.

`operator judgement != model truth` and `caveat removal != goal upgrade`. The
review makes no provider/model call and changes no mission authority, plan
digest, checkpoint, cumulative allowance, source slot, lifecycle, goal
satisfaction or completion readiness. Restart shows the same current judgement.

### Source-independence uncertainty caveat: v0.3.352

The evidence-completion evaluation derives a secondary caveat from current
source assessments: `source_independence_unverified` when an evidence-bearing
source's independence is `unknown` or unassessed, and the stronger
`source_not_independent` for an explicit derivative or likely-duplicate
judgement. The goal explanation and teaching report show it beneath the goal
status.

`unknown independence = explicit uncertainty, not proof and not failure`. The
caveat does not change evidence readiness, goal satisfaction or completion
readiness, is recomputed from unchanged canonical state after restart, and adds
no persistence, authority, provider, model, budget or lifecycle effect.

### Mission completion readiness: v0.3.351

The mission outcome now also exposes a pure completion-readiness projection:
`ready`, or not-ready evidence, conflict, boundary, budget, execution, failure
or cancellation. This answers whether the user can consider the bounded
deliverable concluded; it remains separate from both execution completion and
the narrower evidence-grounded goal-satisfaction result.

`ready` requires existing `satisfied` goal state. It does not close the run,
promote a claim, infer truth, mutate checkpoint state, consume authority or
budget, choose a source/provider/model, retry, or create a follow-up. An
unchanged restored mission yields the same readiness result.

### Visible fail-closed restart refusals: v0.3.343

The narrow restart coordinator already refused a restored semantic mission when
its exact destination, durable research-run binding, cumulative allowance, or
semantic scope could not be re-established. That safe refusal is now visible in
the existing restored-execution status response instead of being an unexplained
startup skip. The restored execution is not rebuilt, retried, charged, or
advanced; it remains reportable with the bounded reason that no source or model
call was replayed.

This does not make restart recovery general. It adds no persistence field,
automatic repair, provider/model fallback, new approval, new budget, scheduler
behavior, or desktop control.

### Durable mission-start idempotency: v0.3.344

Once a bounded semantic mission has reached the existing durable execution
snapshot boundary, that snapshot now retains the caller request ID. A new
process restores those IDs into the goal-start duplicate guard, so replaying
the same request is refused before it can create another run, approval,
provider call, or model call. The ID is bookkeeping rather than authority and
never widens the original digest-bound scope, destination, disclosure, or
cumulative allowance.

This is deliberately not a new transactional start store. A crash before the
execution snapshot exists remains outside this guarantee, and legacy snapshots
without a request ID remain readable without fabricated duplicate protection.

### Fail-closed durable mission start: v0.3.345

A bounded semantic mission now confirms its initial execution snapshot before
it becomes a live execution or begins autonomy. If that write fails, the
in-memory execution, allowance, scope bookkeeping and request ID are removed;
no provider, source, or model operation can run from the failed start. The
caller request is not entered into the duplicate guard, because it never gained
the durable record on which v0.3.344's idempotency guarantee depends.

The authorization consumption record remains consumed rather than being
silently reversed. This preserves the existing fail-closed authority rule but
means the retry derives a new bounded run and approval. There is still no
cross-store transaction: a crash before the execution snapshot remains an
explicitly unsupported ambiguity rather than a claim of exactly-once start.

### Visible durable-start refusal: v0.3.346

The goal-start boundary now preserves the already bounded canonical
`ResearchPlanExecutionStartRefusal` reason in its public response. An operator
can therefore distinguish an initial durable-snapshot refusal from other safe
start refusals without receiving storage exception details. This is response
clarity only: it neither retries, reverses a consumed authorization, exposes a
provider/model fallback nor changes the recovery contract.

### Durable contradiction-investigation outcome: v0.3.347

When the first canonical semantic comparison is tentatively labelled
`possible_conflict`, the already-authorized third-source branch remains the
only possible follow-up. Once that branch has retained its canonical evidence,
assessment and comparison note, the existing mission checkpoint persists a
bounded investigation projection: the initial comparison-note/evidence/source/
assessment identities and fingerprint, the exact follow-up identities and
fingerprint, and either `unresolved` or `structurally_clarified`.

`structurally_clarified` is intentionally not a verdict. It records only that
the third source changed the bounded structure of the tentative comparison; it
does not identify a true source, reject another source, verify a claim, close
the run or declare the research goal satisfied. The projection carries no model
prose, source body, free-form rationale or additional authority.

Checkpoint decoding remains strict: a partially specified, contradictory or
tampered investigation record is rejected. Recovery rechecks both retained
notes, input fingerprints, evidence, source and assessment identities against
the canonical run before an interrupted mission can continue. Existing legacy
checkpoints without the new outcome remain readable and never fabricate one.
The original digest-bound scope, destination, disclosure and cumulative
allowance remain the only authority/accounting mechanisms; no second source
selection, retry, planner, store or agent loop is introduced.

### Typed decision for the existing fixed follow-up slot: v0.3.348

The semantic mission's one conditional third-source slot now has a small typed
decision projection in the existing mission resolver. It can state only that
the already-authorized `SOURCE_FETCH` slot is `proposed`, `not_needed`,
`blocked_predecessor`, `budget_limited`, `already_attempted`, or `completed`.
The projection carries the original plan digest plus existing canonical semantic
note/fingerprint binding; it does not contain a URL or a future provider/model
choice.

The executor reads that decision before its normal attempt boundary. Existing
cumulative allowance and inspected-text limits therefore block the third source
without a new fetch or charge. A retained outcome or attempted source cannot be
replayed. The decision is derived again from the existing restored mission
checkpoint rather than stored independently, so legacy checkpoints never gain
new routing state or authority.

This remains a bounded routing aid, not a general structured-gap planner. It
does not generate a new plan, select an arbitrary follow-up, change scope or
destination, promote a claim, close the run, declare the goal satisfied, or
treat a semantic label as truth. Broader follow-up planning and the separate
evidence-grounded goal-satisfaction contract remain future work.

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
investigation. Evidence-only completion evaluation now informs the report, but
mission-level completion semantics remain separate: an execution may finish or
deliver a bounded report without the research goal being declared satisfied.

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
