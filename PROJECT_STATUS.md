# Hypatia Status

## Runtime Version

`v0.3.324 (Genesis)`

This is the current source/package version. The milestone ledger is CHANGELOG.md;
the older capability narrative below is not a complete audit of this release.

### 2026-09-08 checklist reconciliation

The new user-supplied master checklist sets the product priorities. Its checked
and unchecked boxes are not implementation evidence. In particular, research
execution, bounded continuation, execution persistence and NVD provider code
already exist; they must be assessed and reused before introducing duplicate
AgentRun stores or a second executor.

See [the current priority assessment](docs/Roadmap/Master_Checklist_Reconciliation.md)
for source/test pointers, unresolved requirements, and the next acceptance
scenario. The full natural-language autonomous research/report journey remains
unproven. Autonomous target exploitation is not a development deliverable.

Version v0.3.320 passed Linux and Windows CI and
fixes the default-scope Kali timeout mismatch. Local validation completed:
5,787 tests OK with 3 platform skips, plus Ruff, Black, MyPy and diff checks.
Version v0.3.321 adds a question-to-opening-plan preview (local search followed
by explicitly selected provider discovery). The full autonomous research journey
remains open. Version v0.3.322 adds explicit desktop transfer into the existing
approval/start interface, preserving the exact typed opening and digest.
Local validation for v0.3.321 completed: 5,795 tests OK with 3 platform skips,
plus Ruff, Black, MyPy and diff checks. Remote CI must be checked against the
exact release commit; local results do not establish remote success.
Windows and Linux CI for v0.3.321 both completed successfully. Local validation
for v0.3.322 completed: 5,803 tests OK with 3 platform skips; Black, Ruff and
MyPy passed. Windows and Linux CI for v0.3.322 subsequently both passed.
Version v0.3.323 adds a bounded transient fetched-text result to ordinary advance
and foreground continuation. It is not yet a desktop reader or evidence extractor.
Local validation for v0.3.323 completed on 2026-09-10: 5,813 tests OK with
3 platform skips; 62 focused tests, Black, Ruff, MyPy and diff checks passed.
Remote CI must be checked against the exact release commit before claiming success.
Windows and Linux CI for v0.3.323 both subsequently passed at `abf06d0`.
Version v0.3.324 adds the desktop Source previews reader. Local validation:
5,822 tests OK with 3 platform skips; 203 focused desktop tests, Black, Ruff and
MyPy passed. Real Tk widget and execution-to-reader checks passed without target
traffic. Remote CI must be verified against this release's exact commit.

## Delivery Terminology

The repository has three intentionally separate naming systems:

- **Runtime release `v0.3.324`** is the current source/package release line.
  GitHub commit checks become authoritative after this working tree is pushed.
- **Sprint 4.16.50** is a completed historical engineering increment. Its
  semantic-memory runtime work is included in the history leading to the
  current main branch; it is not an unmerged or later release.
- **Vision-roadmap versions** describe intended product horizons only. They do
  not claim that desktop, voice, agent, robotics, or smart-home modules are
  implemented.

When two documents disagree, current source, tests, this status, and the
changelog take precedence over vision-oriented documentation.

## Current Source State

The current source tree provides a deterministic, local-first cognitive core
with optional OpenAI-compatible LLM conversation support.

### Implemented

- Application bootstrap, configuration, logging, and dependency injection.
- The security agent audits Hypatia's own persisted state against eight bounded
  properties the domain types do not already guarantee, including the same URL
  accepted twice, which would read as independent corroboration. It has no scan
  or probe intent, no target parameter, and opens no socket; it repairs nothing,
  and every report states its scope so a clean result stays interpretable.
- A vulnerability family graph records classes of weakness and authored,
  explained edges between them, answering what else shares a root cause or
  prevention. Behind `HYPATIA_VULNERABILITY_GRAPH_ENABLED`, default off. The
  safety property is structural: no domain type or stored document has a field
  for a target, host, payload, or proof of concept, so the taxonomy cannot
  become a list of things to attack.
- The hypothesis engine requires every conjecture to name what would count
  against it, keeps supporting and opposing evidence in separate never-netted
  lists, and offers no way to confirm one: there is no confirm intent and no
  status meaning true. Behind `HYPATIA_HYPOTHESIS_ENABLED`, default off. Status
  is derived rather than stored. Positive support now requires more than one
  explicitly independent source plus an active authored trust assessment of at
  least `medium` for every supporting source; unknown, derivative,
  likely-duplicate, or conflicting active independence judgements keep the
  hypothesis open. The appraisal reports trust and independence coverage on
  both sides. Any opposing evidence still moves a hypothesis off the supported
  track. Authored statement and discriminating-test text is rendered as one
  bounded line per label, so embedded line breaks cannot resemble forged status
  or evidence totals. Hypothesis History also normalizes and visibly bounds each
  operator-authored evidence note before placing it beside a relation, with the
  same protection at the final renderer. Canonical authored wording and evidence
  remain unchanged. If a hypothesis write fails, the response is explicitly
  unsuccessful, retains the in-process appraisal, and warns that restart may
  lose the change.
- Source reputation aggregates authored assessments by origin across runs and
  reports counts with a bounded standing, never a score. It is derived on every
  request with no store, so revising an assessment revises the reputation.
  Equivalent records of one canonical resource count as one assessed sample and
  retain the least-trusting active authored label regardless of run order. Below
  three assessments the standing is provisional, and no standing gates anything:
  no fetch refused, no evidence discounted, no source pre-assessed.
- Claim calibration compares each authored claim against the evidence structure
  behind it and reports overstatement, using stated ceiling rules rather than a
  hidden score. Strong evidence now requires every corroborating resource to be
  explicitly judged independent as well as assessed at medium trust or better;
  unknown, derivative, likely-duplicate, or conflicting active independence
  judgements cannot inflate the ceiling. Nothing supports `fact`. It is derived
  on every request with no store and no write path, it never edits a claim, and
  understatement is not treated as a problem.
- Failure memory derives eight bounded kinds of lesson from what a run
  recorded, each naming the persisted records it came from; a lesson without
  provenance is refused. Behind `HYPATIA_FAILURE_MEMORY_ENABLED`, default off.
  A lesson records that something did not work here, never that it cannot work,
  and recall is advisory: it blocks no plan, refuses no capability, downgrades
  no claim, and edits no run. A failed lesson-store write is reported as
  unsuccessful while keeping the lessons in memory; repeating the explicit
  store request retries the pending durable write. Only a superseded authored
  `hypothesis` is classified as a failed hypothesis; every other superseded
  epistemic state is a revised claim, not a disguised hypothesis failure.
  Explicitly superseded source assessments now produce one `invalid_assumption`
  lesson when trust, independence, or both changed; wording-only changes and
  parallel authored judgements do not pretend that a correction occurred.
  A separate explicit `failure_memory_hypothesis_store` command reads only
  durable hypotheses for the selected run: `weakened` derives a
  `disproving_evidence` lesson, `contradicted` derives a `failed_hypothesis`
  lesson, and `open`, `supported`, or `withdrawn` derives none. No event handler
  or background task creates these lessons automatically. The same command can
  additionally remember a source trust or independence correction only when a
  timed, currently standing support relation demonstrably predates the
  explicitly superseding assessment. A revision that changes both dimensions
  stays one lesson. Missing structured judgement, parallel judgements,
  unrelated sources, post-correction support, withdrawn hypotheses, and legacy
  untimed support derive no such lesson. Each lesson quotes the hypothesis in
  its own wording on a single bounded line, and the per-run limit keeps
  contradictions and weakened outcomes ahead of support-correction lessons
  while reporting any overflow.
- Looking back at a run is reachable from the desktop. A Review tab reports
  claim calibration, reflection, and curiosity gaps and questions, each kept
  surface gated on its own opt-in. Calibration needs none because it stores
  nothing. Nothing on the tab adjusts a claim, a confidence, or a run.
- The learning loop is reachable from the desktop. A Learning tab drives
  hypotheses and failure lessons, each half gated on its own opt-in, with the
  hypothesis-outcome command offered only where both stores exist. Listing
  hypotheses names each one in its own bounded wording rather than by record ID.
- The weakness taxonomy is reachable from the desktop when
  `HYPATIA_VULNERABILITY_GRAPH_ENABLED=true`. A Security tab records classes,
  relates them with a required reason, and reports a bounded neighbourhood. The
  tab is absent rather than disabled without a durable store, nothing on it can
  name a system, and a failed durable write is reported instead of swallowed.
- Creating a research run surfaces remembered lessons whose wording overlaps the
  new question. That path is read-only, consults no model, requires at least two
  shared words, and cannot fail the run it accompanies: the run is persisted
  before recall is consulted, and an advisory failure returns no lessons rather
  than an error about work that succeeded.
- Bounded reflection reports how a run went — what failed, what contradicted
  what, which beliefs were revised, what rests on thin evidence, what stayed
  uncertain, what effort went unused, what worked, and what to ask next — with
  problems ordered before successes. Behind `HYPATIA_REFLECTION_ENABLED`,
  default off. It now composes durable hypotheses for the selected run through
  the same gap detector and Curiosity generator, so unconfirmed source
  independence and unanswered discriminating tests remain visible as weak
  evidence and deterministic next questions. Source-assessment revisions name
  only the dimensions that changed; independence-only and wording-only updates
  no longer fabricate a trust change, and parallel judgements are not revisions.
  Claim revisions likewise name only changed epistemic state, authored
  confidence, linked sources, linked evidence, or wording; wording-only and
  identical replacements do not fabricate a belief change. Discovery effort is
  matched to accepted sources through the shared canonical resource identity,
  so harmless URL spelling differences do not fabricate unused work. Recorded
  provider attribution is retained on failure findings; legacy providerless
  failures stay providerless rather than being guessed. Every finding detail is
  normalized to one line at the shared record boundary, so embedded line breaks
  cannot masquerade as additional report entries. The visible one-line text is
  bounded after normalization, preserving useful wording that fits and marking
  genuine truncation with an ellipsis.
  Every finding describes the process and never the subject; no hypothesis is
  written or changed, and there is no recursive reflection: only a run can be
  reflected on.
- Live validation now covers the research pipeline end to end against real
  network sources, not only deterministic doubles: a real discovery request, a
  real HTTPS fetch, acceptance, and an evidence record, with assessment and
  claim correctly unperformed. Two manual diagnostics under `tools/diagnostics/`
  report each stage separately and distinguish same-session recall from durable
  learned-memory recall.
- Ordinary chat cannot narrate research it did not perform. A request that
  explicitly needs live web information never reaches the language model;
  Hypatia states deterministically that live research was not performed and
  reports canonical counts instead. Evidence questions are answered only from
  persisted research state, and a post-generation guard annotates any reply that
  claims research the canonical record does not support.
- Bounded curiosity detects eleven kinds of knowledge gap in a persisted
  research run, turns each into one deterministically templated and ranked
  question. Behind `HYPATIA_CURIOSITY_ENABLED`, default off. Accepting a
  question records intent only; a separate inert preview authors an exact
  local-first plan that searches existing knowledge with the canonical question
  before any outside source discovery. Authorization, zero-step foreground
  start, and every one-step Advance remain separate operator actions. The local
  step costs no network or model budget, discovery keeps its declared provider
  cost, and the proposal never fetches, accepts, judges, retries, or queues work.
  Gaps describe what our record is missing rather than what is true. A settled
  multi-source claim now remains visibly thin until every corroborating
  resource has an explicit active independent judgement; parallel conflicting
  assessments fail closed, while superseded claims and assessments are
  excluded.
- Background research scheduling queues approved executions behind
  `HYPATIA_BACKGROUND_RESEARCH_ENABLED`, default off. The scheduler owns
  queueing, pausing, retrying, and crash recovery only; every cycle drives the
  existing autonomy service, so it cannot invent a capability, weaken a budget,
  accept a source, or promote a claim. Work is demand-driven with no thread,
  polling, or busy loop, and task selection is oldest-first. Retries are typed
  from the autonomy stop reason: only budget exhaustion is retryable, and
  blocked, failed, interrupted, and cancelled runs are never retried. A cancelled
  task never restarts, a completed task is never re-run, and on restart a running
  task becomes interrupted rather than replayed.
- Bounded autonomous research loops over the existing execution service rather
  than adding a second engine. It runs only steps a human already authored and
  authorized, so it cannot invent a capability, infer one from instruction text,
  rewrite a plan, accept a source, or promote a claim. Network and model costs
  come from an exhaustive declared capability-cost table rather than from
  operation names, and budgets for step advances, network operations, model
  operations, and wall-clock time are enforced before each advance. Attempted
  advances are counted rather than successes, time uses an injected clock, and
  stopping within budget is reported as a normal outcome with a specific
  step-level reason where one applies.
- Research-execution persistence is wired behind
  `HYPATIA_RESEARCH_EXECUTION_PERSISTENCE_ENABLED`, default off. Bootstrap creates
  the store beside the research-run store and the execution service owns loading,
  restoring, and writing; `CognitiveEngine` only forwards the dependency.
  Restoring is inspection, never resumption: a step recorded as running becomes
  interrupted, completed stays completed, pending stays pending, authorizations
  are not persisted so a restored execution cannot be advanced, and no completed
  operation is replayed. A corrupt store raises at startup rather than being
  replaced by an empty one, and a failed write leaves live state intact while
  reporting a bounded failure event.
- Execution snapshots have a dedicated versioned store,
  `JsonFileResearchExecutionStore`, kept separate from the research-run store so
  `ResearchRun` and its schema are untouched and no migration is required. Writes
  use a bounded temporary file, fsync, and atomic replace, so a failed write
  leaves the previous document byte-identical with no temporary file behind. An
  absent file means no persisted executions; a malformed file raises rather than
  being treated as empty. Unknown schema versions, invalid documents, oversized
  files, execution-count limits, and duplicate identifiers are refused on both
  load and save, and the stored document carries execution bookkeeping only.
  Nothing is wired into the runtime yet.
- Research-execution persistence begins with a pure codec. A durable
  `ResearchPlanExecutionSnapshot` records step identity, declared capability,
  status, operation identity, work flag, bounded detail, the plan question, and
  the bound run identity, and nothing that already lives in the research run.
  Restoring marks a step recorded as running as interrupted rather than
  completed, so mid-flight work is never fabricated as finished; completed steps
  stay completed, pending steps stay pending, and terminal executions stay
  terminal. `INTERRUPTED` is deliberately distinct from `BLOCKED`. No file access
  or runtime wiring exists yet.
- Research-plan execution publishes bounded events for start, step start, step
  completion, step failure, step block, and cancellation from one focused
  emitter. Observability is visibility only: an absent event bus makes every call
  a no-op, and a test proves an observed and an unobserved engine produce
  identical execution snapshots. Payloads carry safe identifiers, capability and
  operation names, counts, and booleans; authored instructions, authorized URLs,
  research questions, and source bodies never appear, a bound run is reported as
  a boolean rather than an identifier, and a failure reports its exception class
  name rather than its message.
- One end-to-end scenario drives the whole explicit research chain through the
  real composition path, from question to closed run, using deterministic doubles
  only for the discovery provider and source fetcher. It asserts the boundaries
  hold together rather than merely that each step passes, and the closed run
  retains its unresolved hypotheses and its contradiction. Research-execution
  persistence remains deliberately unimplemented; a staged additive design
  proposal is documented in
  `docs/Architecture/ResearchExecutionPersistence_Proposal_v0.1.md` and awaits
  review because it involves persisted-schema decisions.
- The twelfth connected capability, `RESEARCH_RUN_COMPLETION`, closes a run
  through the existing lifecycle path and defines no completion rule of its own.
  Reaching the last execution step never closes a run: execution completing, the
  run completing, evidence being sufficient, claims being verified, and
  uncertainty being resolved remain five separate things. A refused transition is
  reported as performed work that did not succeed with the run left open, and a
  closed run retains its unresolved claims, contradictions, and failures, which
  are counted in the reported detail.
- The tenth and eleventh connected capabilities, `CLAIM_CONTRADICTION` and
  `SOURCE_COMPARISON`, record through the existing contradiction and comparison
  paths. A proposal is never a contradiction: previewing persists nothing, and a
  suggestion stays a proposal until a human authorizes it. Recording a
  contradiction leaves both claims byte-identical and decides neither true.
  Comparison is a description, not a verdict: no winner, no ranking, no trust
  promotion, no claim verification, and the existing 2-to-5 source bound is
  preserved. Both authorizations arrive as named draft fields rather than new
  positional elements.
- The ninth connected capability, `CLAIM_CREATION`, records one authored claim
  through the existing claim path. Epistemic state and confidence are authored,
  never inferred, and completing the operation promotes nothing: every one of the
  seven epistemic states is stored verbatim, and a high-trust assessment does not
  raise a hypothesis. The existing domain rule requiring at least one evidence
  reference for every claim, including hypothesis and speculation, is preserved
  rather than replaced. Evidence must belong to the bound run, supersession
  history is preserved, and existing contradiction state is untouched. The
  complete chain from acceptance through evidence and assessment to claim is
  covered by composition tests.
- Authored plan-step drafts normalize through the named immutable
  `ResearchPlanStepDraftInput` instead of a widening positional tuple, while
  legacy tuples remain accepted unchanged. The eighth connected capability,
  `SOURCE_ASSESSMENT`, records one authored assessment through the existing
  assessment path. Assessment text and information trust are authored and never
  derived from a successful fetch, acceptance, or completed operation, and no
  language model participates. At least one evidence reference is required, so an
  assessment is always grounded in recorded evidence; the source must already be
  accepted on the bound run; supersession history is preserved; and information
  trust never grants source text instruction authority.
- The seventh connected research capability, `EVIDENCE_RECORDING`, records one
  evidence entry through the existing evidence path. Evidence text is never
  supplied by a caller: the operation resolves a real chunk by exact document ID
  and chunk index, and the existing domain computes the excerpt, chunk identity,
  and hash from it, so evidence cannot be fabricated and no language model is
  involved. A fetched-but-unaccepted source cannot produce evidence, and unknown
  chunks are refused rather than guessed. Recording establishes evidence only: no
  assessment, no claim, no epistemic elevation, and no statement of source trust.
  The full production chain from source acceptance to evidence recording is
  covered by composition tests.
- The canonical source-acceptance transaction lives in one place. Extracted
  behavior-preservingly from the source-load route into
  `ResearchSourceAcceptanceService`, it is shared by that route and by the sixth
  connected capability, `SOURCE_ACCEPT`; `CognitiveEngine` shrank and now
  delegates. Acceptance requires an explicitly authorized URL, so discovery
  metadata alone never authorizes it and instruction text stays inert. A
  transaction that runs without accepting is recorded as performed work on a
  failed step rather than rendered as success. Rollback guarantees are unchanged
  and directly tested, no second content channel exists, and accepted means
  accepted into the run's source set only.
- The fifth connected research capability, `SOURCE_FETCH`, reuses the canonical
  source-fetch pipeline with every existing protection intact and adds no second
  HTTP path. A step may acquire only the one URL it explicitly authorizes through
  `authorized_source_url`; the URL is never inferred from instruction text nor
  taken from a discovery result. The operation is acquisition-only: nothing is
  indexed, accepted, stored as content, or turned into evidence, an assessment,
  or a claim, so cancellation after bytes arrive leaves no partial state.
  Fetched content stays untrusted, carries no instruction authority, is never
  sent to a language model here, and never appears in user-facing detail.
- The fourth connected research capability, `SOURCE_DISCOVERY`, reuses the
  existing discovery provider abstraction and run audit path rather than adding a
  second discovery engine. One step performs exactly one bounded query with no
  retry, crawling, or link following, and cooperative cancellation is checked
  before the query and again before the audit write. Provider results are
  validated for type and count, failures are recorded in the run audit and
  re-raised, and no substitute provider is ever used. Candidates persist only as
  an unaccepted provenance-preserving record: nothing is accepted, fetched, or
  turned into evidence or a claim, and zero candidates is a performed discovery
  rather than a failure.
- The third connected research capability, `EVIDENCE_INTEGRITY_CHECK`, runs the
  existing `ResearchEvidenceIntegrityAuditor` against the bound run. It is local,
  read-only, and deterministic, with no network, LLM, mutation, or event. A
  completed check proves only that the integrity operation ran and returned its
  result; every detail states that it does not establish truth, verify a claim,
  or make a source trustworthy. Zero evidence records still complete the audit,
  an unavailable audit reports no fabricated counts, and unknown or unbound runs
  fail safely without claiming work.
- Research-plan execution passes one small explicit `ResearchPlanExecutionContext`
  through the application-service boundary. Collaborators stay
  constructor-injected at composition time, so an operation never reaches a
  global, locator, container, `CognitiveEngine`, or unrelated store. The second
  connected capability, `ACCEPTED_SOURCE_LISTING`, reads accepted sources from
  canonical `ResearchRunManager` state without network, LLM, or mutation. Zero
  accepted sources is a performed listing rather than a failure; the detail states
  that no source content was read and no evidence was established; reported
  identifiers are capped; and unknown or unbound runs fail safely without claiming
  work. Every registered capability is covered by a composition-level test proving
  it is reachable through the real `CognitiveEngine` wiring.
- Research-plan execution selects operations through explicit typed capability
  registration. A step declares a `ResearchPlanStepCapability` separately from its
  authored instruction text, and `ResearchPlanOperationRegistry` binds each
  executable capability to exactly one operation. Instruction wording never
  selects a capability, an undeclared or unregistered capability blocks the step
  with a bounded reason instead of falling back, and the step state records which
  operation ran. Recorded work requires a recorded operation name. A completed
  operation means only that the operation ran; it is neither evidence nor a
  verified claim, and evidence, assessment, and claims remain in the existing
  research pipeline.
- Research-plan execution connects its first real capability in stage three. A
  `ResearchPlanStepOperation` boundary runs one bounded operation per advance
  request, and `LocalKnowledgeSearchStepOperation` performs the existing
  deterministic local knowledge search for an authored step instruction. Only an
  operation that actually executed can mark a step as backed by real work; with
  no operation connected, or one reporting that it performed nothing, the step is
  blocked with a bounded reason rather than reported as completed research. A
  failing operation fails the step and plan without claiming work, and a
  zero-result search is reported honestly as a search that matched nothing.
  Source discovery, fetching, evidence, assessment, and claims remain
  unconnected, and no network, LLM, or persistence path is used.
- Research-plan execution has an ephemeral coordination layer as its second
  stage. `ResearchPlanExecutionApplicationService` owns per-process execution
  state behind exact structured start, status, and cancel Brain intents;
  `CognitiveEngine` only routes. No research work runs in this stage: starting a
  plan records that execution began and advances no step, and source discovery,
  fetching, evidence, assessment, and claims are not performed. A step records
  whether a real operation backed it, so a bare state-machine advance is reported
  as zero research operations rather than as completed research. State is
  in-memory only, every status message says it is lost when Hypatia exits, and an
  unknown plan is reported as absent rather than as a resumable run. Duplicate
  starts are rejected deterministically, active executions are capped at 20,
  terminal executions reject further transitions, and cancellation preserves
  completed-step history.
- Research-plan execution has a pure immutable state machine as its first stage.
  `ResearchPlanExecutionStatus` and `ResearchPlanStepStatus` follow the existing
  `ResearchRunStatus` convention with an explicit terminal property, and
  `ResearchPlanExecutionState` exposes prepare, start, start_step, complete_step,
  fail_step, block_step, and cancel. Steps run in exact authored order, only one
  step may run at a time, and a plan reaches completed only when every step
  completed, so partial or failed work can never present itself as finished.
  Failure and cancellation preserve already-completed steps. This stage is
  domain-only: no network, LLM, provider, persistence, event-bus, `ResearchRun`,
  Brain, or desktop integration, and no user-reachable route can start execution.
- A read-only learned-memory audit reports deterministic bounded health metrics
  through the exact structured `learned_memory_audit` Brain intent: active and
  superseded counts, superseded share, distinct identities, identities with
  history, maximum versions for one identity, conflicting-history identities, and
  duplicate value candidates, with samples capped at 10 entries each. It never
  deletes, merges, compacts, rewrites, or normalizes stored memories, issues no
  LLM, semantic, or network call, reports kinds and keys without any stored
  value, and never runs on an ordinary chat turn. Duplicate candidates come only
  from exact value equality between active identities and are never treated as
  proof of equivalent meaning.
- Learned-memory context selection for one conversation turn is owned by
  `LearnedMemoryContextService`. `CognitiveEngine` delegates instead of branching
  inline over selector and limit combinations.
- Optional semantic relevance in ordinary chat is available behind
  `HYPATIA_CHAT_SEMANTIC_MEMORY_ENABLED=true`. It is off by default and inert
  unless the semantic-memory runtime is also enabled. With the flag absent,
  ordinary chat delegates to the existing deterministic loaders unchanged and
  issues no embedding call. When enabled, one turn performs at most one semantic
  query against the already built index, never starts a rebuild from the
  conversation path, and creates no second index, store, or cache. Candidates are
  fused with the deterministic keyword selection through the existing
  `HybridSemanticMemoryRanker`, deduplicated by learned-memory identity, and
  bounded. A semantic hit on a superseded record is rejected, so corrections are
  never resurrected. Absent, rebuilding, stopped, or failing semantic retrieval
  falls back to the deterministic bounded path, the conversation still succeeds,
  and one bounded `brain.chat_semantic_memory.query_failed` event reports the
  cause class name only. Retrieval performs no memory write, and explicit lexical
  and semantic recall are unchanged.
- Ordinary chat defaults to bounded, request-relevant learned memory. With
  `HYPATIA_LEARNED_MEMORY_SELECTOR` absent, Bootstrap builds the existing
  deterministic ranked keyword selector bounded to 8 memories, so only learned
  memories sharing a token with the current user message reach the prompt.
  `HYPATIA_RANKED_LEARNED_MEMORY_SELECTOR_LIMIT` overrides that bound, and the
  explicit `none` value restores the earlier unbounded no-selector behavior.
  Only the composition default changed; `CognitiveEngine` keeps its
  explicit-injection contract, and correction, supersession, explicit recall, and
  semantic recall are unchanged.
- Learned-memory candidate extraction detects providers exposing the optional
  `generate_json(...)` capability through a local runtime-checkable Protocol and
  then requests one bounded structured response with a trusted system
  instruction, a 512-token bound, and an exact JSON response schema mirroring the
  existing parser. Providers exposing only `generate` keep their previous plain
  call. The parser stays the final authority, so reasoning preambles and
  Markdown-fenced payloads remain rejected. Extraction failure now emits one
  bounded `brain.learned_memory.extraction_failed` event carrying only the
  request ID and cause class name; ordinary chat still succeeds and no event is
  emitted for successful or no-op extraction. The persisted memory schema, the
  global `LLMProvider` Protocol, and the learned-memory retrieval defaults are
  unchanged.
- An initial local Tkinter desktop shell for text conversation, explicit
  session selection, a refreshable read-only session overview, and
  semantic-runtime status. It also provides selected-session details, recent
  conversations, and activity through explicit read-only actions. Chat,
  Knowledge, Research, and Appearance are separated into dedicated tabs, with
  compact grouped controls, explanatory empty states, and a conversation-first
  opening view. It is a thin adapter over the existing Brain and does not create
  a second store, provider, or network channel.
- The desktop requests a 1,920-by-1,080-pixel initial client area, centers that
  size on larger displays, and clamps it to smaller screens without disabling
  ordinary resizing. The screen-safe minimum is bounded by the available
  dimensions; this sizing is presentation-only and opens no runtime path.
- The dense Research workspace is organized into four ordered presentation-only
  workflow tabs for run overview, sources/evidence, authored analysis, and
  review/export. Authored analysis is further divided into saved records,
  comparison, assessment, and claims/contradictions. The layout retains all 59
  existing command bindings and 41 field bindings, changes no runtime contract,
  and fits within the measured 1080p desktop height.
- The Research workspace's loaded-catalog filtering, status facets,
  deterministic sorting, selected-run summaries, evidence/assessment coverage,
  metadata, and canonical selected-source presentation are projected by one
  frozen, Tkinter-independent `ResearchWorkspaceReadModel`. The adapter keeps
  compatibility delegates but no longer owns those calculations. The read
  model imports no Brain, controller, manager, provider, persistence, path,
  network, or widget boundary and changes no visible string or runtime action.
- The read-only Research overview command family is isolated behind
  `ResearchOverviewApplicationService`. Research-run listing, one-run evidence
  listing, accepted-content restoration status, and evidence-integrity status
  retain their original routing precedence and exact Brain response contracts,
  while `CognitiveEngine` no longer owns their validation and composition flow.
  The service adds no write, provider, network, LLM, schema, or UI path.
- The existing authored-history read family is isolated behind
  `ResearchAuthoredHistoryApplicationService`. Claim history, accepted-source
  comparison, and accepted-source assessment previews retain their original
  validation, route precedence, and exact Brain response contracts. The service
  reads existing manager snapshots and adds no mutation, provider, network,
  LLM, schema, store, or UI path.
- The first user-authored Research planning domain contract is available as
  immutable `ResearchPlan` and `ResearchPlanStep` values. A plan preserves one
  bounded question and one to twenty explicit ordered steps. Each step preserves
  one bounded authored instruction and zero to twenty exact user-selected source
  document IDs; an empty selection never authorizes automatic source choice.
  This domain-only foundation has no execution, run-lifecycle, Brain, UI,
  persistence, provider, network, LLM, path, manager, or event-bus integration.
- A pure `ResearchPlanDraftService` now turns only an explicit authored question
  and ordered `(instruction, selected source IDs)` tuples into a complete
  immutable plan preview. Invalid structure or domain values return one bounded
  rejection reason without a partial plan. The service assigns plan-local step
  order identities but does not select sources, execute, persist, publish an
  event, access a manager/provider/network/LLM/path, or integrate with Brain,
  `ResearchRun`, or the desktop.
- Exact structured `research_plan_draft_preview` requests now route through a
  small Brain-facing application service. The structured response carries the
  entire immutable ready/rejected preview; its message shows ordered authored
  steps and selected source IDs or one bounded rejection reason, and explicitly
  states that no write or execution occurred. Routing changes no memory,
  knowledge document, event, `ResearchRun`, provider, network, or LLM state.
  There is no plain-message heuristic; the desktop can reach this route only
  through the explicit structured adapter described below.
- The Research workspace now includes one bounded `Plan draft` authored-analysis
  editor. It shares the visible authored question, accepts one ordered
  instruction per line, and accepts optional comma-separated exact source
  document IDs on the matching line. The adapter issues only the existing
  structured preview intent and shows the complete ready or rejected message in
  a read-only result area. It adds no confirmation, persistence, `ResearchRun`
  mutation, provider, network, LLM, event-bus, automatic source selection, or
  execution path; the four-step 1080p workflow remains unchanged.
- The Sources & evidence, Authored analysis, and Review & export workflow tabs
  repeat one read-only current-run banner with the selected question, status,
  and exact run ID. All three labels share one presentation value derived only
  from the already loaded immutable run snapshot. Empty or invalid selections
  show guidance instead of stale identity; no runtime request or mutation starts.
- The same three current-run banners also share complete source, evidence, and
  claim counts from that immutable snapshot. Empty and invalid selections clear
  stale progress. The Overview summary remains unchanged, and no additional
  read, provider, persistence, or mutation path exists.
- Research Overview adds a bounded workflow snapshot for the selected run. It
  reports complete sources/evidence, assessments/comparison notes/claims/
  contradictions, and the existing review status from the immutable object.
  It makes no readiness, truth, or conclusion inference and starts no action.
- The already loaded research-run catalog has a 200-character local filter.
  Question text matches case-insensitively; status and run ID require exact
  matches. The full immutable catalog remains intact, no-match/overlong states
  are explicit, clearing restores all rows, and the active run plus authored
  fields change only after an explicit visible selection.
- The current loaded or filtered research-run view has four explicit local
  orders: updated newest, updated oldest, created newest, and question A-to-Z.
  The selected order is visible, deterministic run-ID ties are stable, and
  sorting preserves the immutable catalog, filter membership, active run, and
  authored fields without opening a runtime or mutation boundary.
- When that local filter hides the active research run, `Show active run`
  clears only the local filtering controls, preserves the current sort and
  authored fields, and restores the exact active row in the selector. Empty,
  stale, or invalid local state is refused without changing the prior view or
  opening a runtime path.
- The same catalog has an explicit All/Collecting/Completed/Failed/Cancelled
  status view. It composes with bounded text matching and deterministic sort,
  reports visible/total counts with the selected status, and preserves active
  selection and authored fields without a runtime or mutation boundary.
- Research Overview also shows complete All, Collecting, Completed, Failed,
  and Cancelled catalog counts from the full immutable loaded tuple. Those
  counts remain unchanged by text/status filtering and sorting, show explicit
  zeroes for an empty catalog, and open no runtime or mutation boundary.
- One `Reset view` action clears both local filters, restores Updated-newest
  sorting, re-shows the complete loaded catalog, and reselects a loaded active
  row. It preserves exact active identity, authored fields, and catalog totals;
  empty/stale-active state is explicit and no runtime or mutation starts.
- Research Overview reports accepted sources, sources represented by one or
  more evidence records, and accepted sources without evidence for the selected
  immutable run. Repeated evidence counts a source once, no score/readiness is
  inferred, stale selection is cleared, and no runtime or mutation starts.
- Research Overview also reports accepted sources with a current authored
  assessment and those without one. Superseded history does not count as
  current, each accepted source counts once, malformed foreign references are
  ignored, and no quality/readiness inference or runtime action occurs.
- Sources & evidence can locally show All sources, accepted sources Without
  evidence, or accepted sources Without current assessment. Stable exact-ID
  membership preserves a visible or hidden active source and authored fields;
  switching back restores the exact source. Superseded-only assessment history
  remains uncovered, invalid/stale state changes nothing, and no runtime or
  mutation starts.
- The same selected immutable run supplies a compact complete accepted-source
  catalog summary with All, Without evidence, and Without current assessment
  counts. Those totals remain invariant while the local source view changes,
  deduplicate exact source membership, infer no quality, and open no runtime or
  mutation boundary.
- One `Show active source` action restores All sources and the exact active row
  when a coverage view hides it. Empty, stale, or unknown active state is
  refused; source-bound read-only records are restored while catalog totals and
  authored fields remain unchanged, with no runtime or mutation action.
- One adjacent selected-source record summary reports exact evidence,
  assessment-history, and current-assessment counts from the same immutable
  selected run. Superseded assessments remain part of history but do not count
  as current; foreign records do not count. Hidden or invalid source state
  clears the summary, no quality/trust conclusion is inferred, and no runtime
  or mutation boundary opens.
- That summary also presents the normalized bounded source title, exact source
  document ID, and exact immutable run ID. The complete source record must match
  canonical run membership before any counts are displayed, preventing changed
  or foreign provenance from being paired with the run's records.
- The canonical selected-source summary additionally exposes persisted data
  taint `external_untrusted_data` and instruction authority `none`. User-authored
  information-trust labels cannot grant instructions or change this boundary;
  the presentation remains read-only and disappears with hidden/invalid state.
- The same summary reports current user-authored information-trust distribution
  across Unassessed, Low, Medium, and High. Only non-superseded assessments for
  the exact source count; corrected history and foreign records cannot alter the
  distribution. Four explicit lines keep provenance, safety, records, and trust
  distinct without inferring a verdict or opening a runtime boundary.
- The Records line also reports unique valid evidence IDs explicitly cited by
  current assessments versus all evidence recorded for the selected source.
  Repeated citations count once; superseded, foreign, and unknown IDs cannot
  contribute. It is an audit inventory and makes no coverage-quality conclusion.
- One explicit `Source details` action presents safe canonical provenance for
  the selected accepted source: bounded title, exact source/run IDs, persisted
  content type, and timezone-aware fetched/accepted timestamps. It excludes URL
  and content, refuses noncanonical or missing selection, changes no authored
  field, and opens no runtime or mutation boundary.
- The selected run's immutable creation/update times and complete safe-failure
  count appear in Overview as a bounded metadata line. Timestamps retain their
  timezone offset at seconds precision; failure stage/reason text is never
  exposed. Empty or invalid selection cannot retain stale metadata.
- The Research tab has a read-only persisted-run selector labelled with the
  question, status, and exact ID. Refresh preserves a valid selection, creation
  selects the new run, and switching clears only stale candidate/export views.
  Selection itself starts no network, provider, or mutation action and leaves
  authored research fields unchanged.
- The selected run also exposes status and complete source, evidence, and claim
  counts beneath the selector. The summary uses only the already loaded
  immutable catalog object, distinguishes empty/invalid selection states, and
  starts no Brain, storage, provider, network, or mutation action.
- Explicit provider-backed desktop actions use one daemon request worker so
  Ollama and approved HTTPS waits do not block Tkinter's event loop. Results
  are rendered only by the event thread, all command buttons are single-flight,
  close discards late results, and unexpected failures expose no internal
  exception detail. The status line shows truthful elapsed seconds without a
  fabricated percentage. A dedicated cancellation request leaves ordinary
  controls disabled until active bounded I/O returns, then discards its value
  or error instead of presenting it. It does not claim to kill a provider call.
  Research discovery and explicit HTTPS source-loading requests additionally
  propagate a thread-safe cooperative signal. They stop before audit,
  knowledge-index, or persistence mutation when cancellation is observed after
  network return. Other provider paths remain presentation-only cancellation.
  The worker owns no provider or duplicate state.
- Local desktop text-size controls bounded from 10 through 20 points plus Eye
  comfort, Light, and High contrast themes. Eye comfort is the default and
  avoids pure black/white surfaces; every theme defines explicit focus,
  selection, disabled, read-only, border, and scrollbar colors. These settings
  alter only presentation and do not persist a preference, invoke a provider,
  or change session, memory, knowledge, or research state. A full
  assistive-technology audit remains planned.
- Explicit desktop actions for normal lexical recall and opt-in semantic recall.
  Neither action augments ordinary chat, persists a recall result, or issues a
  provider request unless the user deliberately selects it.
- An explicit desktop `Knowledge context` action for bounded, cited local
  document context. It does not call an LLM or change conversation memory.
- Explicit `ask knowledge` local-RAG requests separate the user's question from
  source excerpts, label every excerpt as untrusted data, and add a code-owned
  per-request system instruction denying source text any instruction authority.
  That request receives no conversation history or tool capability. This is a
  bounded prompt-level defense, not a complete prompt-injection firewall.
- Separate desktop `Knowledge graph` and `Loaded sources` actions expose the
  existing bounded, cited source structure and read-only source catalog. They
  use only explicit user actions, do not call an LLM, and do not change
  conversation memory or the local knowledge store.
- A desktop `Load file` action chooses one local `.md` or `.txt` source and
  sends a structured request through Brain to the existing knowledge pipeline.
  It validates and indexes the selected source without an LLM call,
  conversation-memory write, or desktop-side source store.
- A desktop `Load source` action accepts one explicitly entered public HTTPS
  URL. The runtime validates the scheme, credentials, port, every resolved IP,
  and redirects, then connects to one exact validated address while retaining
  hostname-based TLS and certificate checks. A failed connection advances only
  to the next address from the same public-only answer set, with all attempts
  sharing one decreasing time budget. It bounds content type, response size,
  and text encoding before extracting readable HTML/plain text and
  indexing it through the existing knowledge pipeline. It preserves the final
  URL as provenance and does not invoke an LLM, write conversation memory, run
  in the background, or discover sources automatically.
- A desktop `Start research` action creates a persistent, auditable research
  run for one explicit question; `Research runs` lists the stored catalog, and
  `Load source` can attach an accepted source to the selected run ID. Each run
  stores its question, collecting status, source provenance, safe failures,
  and timestamps in a versioned atomic JSON snapshot. Downloaded page content
  and the in-memory knowledge index are not duplicated in that snapshot.
- The selected run exposes accepted sources from its already loaded immutable
  snapshot in a read-only title-and-exact-ID selector. Selection alone changes
  no manual field; separate assessment and comparison handoff buttons copy only
  the exact persisted ID, reject stale cross-run choices, and start no Brain,
  storage, provider, network, or mutation operation.
- The selected accepted source filters that snapshot's persisted evidence into
  a bounded-excerpt-and-exact-ID selector. Separate explicit handoffs append one
  exact ID to assessment, claim, or comparison fields only after source/run
  ownership checks. Duplicate, stale, over-20 claim, and over-100 comparison
  choices are refused without changing authored fields or invoking runtime work.
- User-authored assessments for that source are shown from the same snapshot
  with current/superseded audit state, bounded text, and exact ID. Only current
  same-source records can be explicitly copied as a correction target or added
  once to comparison assessment IDs; source membership, stale state, and the
  50-ID comparison limit are checked without a runtime request or form overwrite.
- User-authored claims for the selected run are shown from that immutable
  snapshot with current/superseded audit state, epistemic state, categorical
  confidence, bounded text, and exact ID. Separate predecessor and contradiction
  handoffs accept only current records; stale state, duplicates, and the exact
  two-ID contradiction bound are checked locally without a runtime request or
  authored-field overwrite.
- Persisted user-reviewed contradictions for the selected run are shown from the
  same snapshot with exact claim pair, bounded authored note, timezone-aware
  recorded time, and exact contradiction ID. A separate pair handoff replaces
  only the manual claim-ID field; selection, stale-state refusal, and handoff do
  not edit the note or start runtime work.
- Persisted source-comparison notes for the selected run are shown from the same
  snapshot with bounded authored text, recorded time, exact note ID, and a full
  read-only source/evidence/assessment reference summary. Three isolated handoffs
  replace only their matching manual field; selection and stale-state refusal
  preserve all authored fields and start no runtime work.
- A separate schema-v1 accepted-source content store validates exact
  document provenance, UTF-8 byte count, SHA-256, timestamps, duplicate IDs and
  URLs, and bounded per-record/total/file sizes before atomically replacing its
  complete JSON snapshot. A source accepted into a selected run saves its exact
  content after knowledge indexing and before provenance publication. Startup
  restores it only after stable document identity and all persisted source
  provenance match exactly, with no network or persistent write.
- Research-source attachment is transactionally guarded: a content-store
  failure removes the new unlinked knowledge document and publishes no source
  provenance. If the run snapshot then fails, Hypatia restores the prior
  content collection and independently removes the knowledge document before
  returning a controlled result. Rejected source URLs are not retained in
  persistent failure diagnostics.
- A replaceable research source-discovery provider boundary accepts one
  explicit collecting run and returns at most five ordered, credential-free
  HTTPS metadata candidates. The runtime atomically records the exact query,
  provider identity, timestamp, titles, URLs, and bounded snippets without
  fetching or indexing candidate content. Closed or unknown runs stop before
  provider access, and candidates are not accepted sources or evidence.
- The packaged process-environment runtime supplies a bounded Crossref REST v1
  provider for explicit discovery. Its fixed Crossref HTTPS API and same-origin
  redirects require public-only DNS answers and connect to one exact validated
  address while TLS verifies `api.crossref.org`. It inherits no proxy, retains
  a ten-second timeout and 500 KB JSON limit, and uses only
  DOI/title/venue/year metadata. The desktop shows persisted candidates and can
  copy one selected DOI URL into the existing load field, but selection never
  invokes source acquisition.
- The desktop can preview one exact persisted candidate before acceptance. The
  preview is read-only and performs no network or indexing work. After explicit
  confirmation, the runtime revalidates the run, discovery ID, and candidate
  URL before using the existing guarded source loader; stale, unlisted, or
  closed-run selections stop before network access.
- A desktop `Save evidence` action accepts the selected run ID, an indexed
  paragraph/chunk ID, and an explicit user note. The runtime permits the
  selection only when the paragraph belongs to a source already attached to
  that run, then atomically persists its source locator, paragraph position,
  bounded excerpt, truncation marker, full-paragraph SHA-256 fingerprint, note,
  and recording time. `View evidence` reads those records after restart without
  requiring the page content or an LLM.
- A separate accepted-source assessment preview binds the exact run and source
  document ID, then renders persisted provenance and only evidence explicitly
  recorded for that source, plus any persisted user-authored assessments. It
  works read-only for collecting and terminal runs, makes no live knowledge or
  provider call, performs no write, and assigns no automatic trust, quality,
  relevance, or credibility score.
- A collecting run accepts an authored assessment only through its own
  preview-confirm boundary. The user supplies assessment text and explicit
  evidence IDs; final recording revalidates that the run is open, the source is
  accepted, and every evidence record belongs to that source before atomically
  appending the audit record.
- An authored assessment may explicitly supersede one earlier assessment from
  the same run and accepted source. The new record points backward while the
  original remains immutable; read-only history labels current and superseded
  records. Missing, cross-source, already-superseded, and closed-run targets are
  rejected again at final recording time.
- Each authored assessment can carry one explicit information-trust label:
  `unassessed`, `low`, `medium`, or `high`. The desktop, source history,
  comparison view, committed response, and deterministic export show that
  label. A correction can replace the current label without changing the
  immutable predecessor. Hypatia never calculates the label or treats it as an
  automatic truth score.
- Every accepted external source carries the fixed taint label
  `external_untrusted_data` and fixed instruction authority `none`. Information
  trust and instruction authority are separate: even a user-authored `high`
  label cannot grant source text permission to issue instructions or use tools.
- A collecting run can preview and append one user-authored claim only when it
  cites persisted evidence. The record keeps the exact ordered source IDs
  derived from that evidence, one explicit epistemic state (`fact`,
  `strong_evidence`, `likely`, `hypothesis`, `speculation`, `unknown`, or
  `contradicted`), and categorical authored confidence (`unassessed`, `low`,
  `medium`, or `high`). Hypatia does not extract the claim, choose evidence,
  calculate truth, or create a numeric score.
- Claim history remains readable for collecting and terminal runs. A correction
  appends one backward supersession link while preserving its predecessor;
  missing, already-superseded, cross-run, closed-run, and mismatched-provenance
  writes fail before publication. The desktop uses a separate preview and
  confirmation before final revalidation and atomic persistence.
- A collecting run can preview and append one explicit user-reviewed
  contradiction relationship between exactly two persisted claims. The record
  keeps the selected claim order, the exact de-duplicated union of both claims'
  evidence IDs, the user's required note, its own ID, and audit timestamp.
  Reversed pairs count as duplicates. History remains readable after closure,
  while Hypatia performs no automatic contradiction detection, claim or
  evidence selection, truth decision, claim rewrite, provider call, or change
  to external source instruction authority.
- A collecting or terminal run can explicitly request a read-only contradiction
  candidate review across at most 50 current, non-superseded claims. The
  configured LLM receives no conversation history or tools and returns at most
  10 schema-constrained pairs. Hypatia derives evidence only from the exact
  persisted claims, omits already recorded unordered pairs, revalidates the
  complete run snapshot, labels rationale as untrusted, and persists nothing.
- Successful candidates populate an ephemeral selector tied to the exact run.
  An explicit `Use selected pair` action copies only two claim IDs into the
  manual write form. It leaves the user's note unchanged, clears stale
  cross-run candidates, performs no provider or persistence operation, and does
  not bypass the existing preview-confirm-record boundary.
- A separate manual comparison preview accepts an ordered list of two to five
  unique accepted-source document IDs from one exact run. For each source it
  renders persisted provenance, only explicitly recorded evidence, and only
  current authored assessments. It remains read-only for collecting and
  terminal runs, performs no provider, network, LLM, memory, graph,
  knowledge-index, event-bus, or persistence work, and generates no verdict,
  trust score, or automatic evidence selection. Each source column carries at
  most 20 evidence records and 10 current assessments while exposing complete
  counts, preventing unbounded response rendering without hiding truncation.
- A collecting run can preview and separately append a user-authored comparison
  note that cites exact evidence and current assessment IDs covering every
  selected source. The existing comparison preview reads matching notes for the
  exact selected source order after restart. It displays at most 20 notes and
  reports the complete count. Hypatia generates no note text, verdict, score,
  or reference selection.
- Research-run schema v9 remains backward compatible with v1-v8 snapshots.
  Legacy runs load with absent evidence, discovery, or assessment collections
  represented as empty, v4 assessments load with no supersession link, and
  v1-v5 runs load with no comparison notes, v1-v7 runs load with no claims, and
  v1-v8 runs load with no claim-contradiction relationships.
  Every v1-v6 source receives the
  fixed external-data taint and no instruction authority, while every legacy
  assessment receives `unassessed` information trust.
  They are rewritten only after a later successful mutation; no eager or
  partial migration occurs.
- One terminal run can be explicitly previewed as deterministic Markdown using
  only its immutable persisted audit snapshot. The bounded view includes source
  provenance, evidence, authored assessment history, evidence-linked claims,
  user-reviewed claim contradictions, comparison notes, and safe
  failures; it reports the complete character count and full-content SHA-256.
  Authored and remote text is escaped as literal quoted material, and a safe
  suggested basename cannot contain a path. Hidden directional controls are
  neutralized. Collecting runs are rejected and no
  file, network, provider, LLM, memory, graph, live-index, or event-bus action
  occurs.
- A separate `Save export` action requires that exact displayed preview and an
  explicitly chosen absolute `.md` path. The final Brain request re-renders the
  terminal run and matches its immutable update time and full-content SHA-256
  before atomically publishing complete UTF-8 bytes. Existing destinations are
  never replaced, temporary-file cleanup is attempted, and no research, memory,
  graph, live-index, event-bus, provider, LLM, or network state changes.
- `Verify export` reads one explicitly selected existing `.md` file as complete
  bytes and compares its count and SHA-256 with a fresh deterministic render of
  the current terminal run. It requires a stable regular-file descriptor,
  reports exact expected and observed values plus `MATCH`/`DOES NOT MATCH`, and
  performs no decode, import, repair, write, research mutation, network,
  provider, LLM, memory, graph, live-index, or event-bus action.
- Research runs have a persisted terminal lifecycle. The desktop previews a
  requested `completed`, `failed`, or `cancelled` transition and requires a
  separate confirmation before the runtime revalidates and atomically saves
  it. Completion requires at least one accepted source and evidence record;
  failure requires a recorded failure; cancellation can honestly close an
  empty run. Closed runs cannot be
  reopened, retargeted, or receive further source, evidence, assessment, claim,
  claim-contradiction, or failure mutations. Closed-run source requests stop
  before network access.
- The Windows desktop entry point persists its own local runtime state beneath
  `%LOCALAPPDATA%\Hypatia` by default, avoiding writes beside an installed
  executable. A documented absolute-path override supports deliberate local
  backup/storage choices; no automatic data migration occurs.
- A reproducible Windows onedir package can be built with the pinned local
  PyInstaller tool and `tools/build_desktop.ps1`. The initial update policy is
  manual, with no self-update, bundled credentials, or telemetry channel.
- On Linux, installed desktop state follows the XDG data-directory contract:
  an absolute `XDG_DATA_HOME` maps to its `hypatia` child and otherwise falls
  back to `~/.local/share/hypatia`. The absolute cross-platform override still
  takes precedence, and Windows path behavior is unchanged.
- A reproducible Ubuntu 24.04 x64 onedir package can be built with the same
  pinned PyInstaller version and `tools/build_desktop.sh`. GitHub Actions runs
  the full suite, builds the package, opens it under Xvfb, verifies temporary
  local-state initialization, and publishes a short-retention Linux artifact.
  Linux and Windows updates remain manual with no telemetry, bundled
  credentials, or automatic data migration.
- An explicit desktop `Ask sources` action submits a user-entered question to
  the existing local-RAG command. When the configured runtime is enabled, it
  receives only up to three bounded cited local chunks; it does not augment
  ordinary chat or change conversation memory.
- The desktop transcript visibly renders the existing ordered source citations
  returned by any knowledge response, including title, source path, paragraph,
  and chunk identifier. It does not look up, fabricate, persist, or reorder
  source records.
- The desktop can now create one explicit local `related_to` source relation
  only through its existing two-stage runtime contract: it first shows the
  runtime preview, then issues the revalidated apply command only after a
  separate confirmation. Declining or failing the preview makes no mutation.
- The desktop can also remove an existing explicit local source relation only
  through its matching two-stage runtime contract. It first presents the
  removal preview and sends the revalidated removal command only after a
  separate confirmation; declining or failing that preview makes no mutation.
- The desktop `Active links` action exposes the existing deterministic catalog
  of active local source relations and their persistence state. It is read-only
  and does not load sources, call an LLM, or change graph or memory state.
- The desktop supports session renaming only through the existing transaction:
  it shows the exact read-only preview first, requires a separate confirmation,
  and calls the revalidating rename command only on approval. A successful
  response refreshes the session list from Brain; a declined or failed preview
  leaves all session and memory state unchanged.
- The desktop supports session deletion only through the structured existing
  delete preview: confirmation is available solely when runtime marks it
  allowed. Blocked or failed previews cannot issue deletion; a successful delete
  clears the selection and refreshes the session list from Brain.
- Deterministic English and Turkish standalone greetings. A substantive request
  that begins with a greeting remains a normal conversation request and reaches
  the configured LLM runtime when one is enabled.
- EventBus-backed lifecycle events.
- Session registry with local JSON persistence, active-session selection,
  targeted read-only views, rename, preview, and guarded deletion.
- Persistent structured memory with atomic JSON writes, TTL handling, explicit
  recall, and transactional mutation ordering.
- Learned-memory extraction, append-only correction history, bounded context,
  keyword selection, deterministic ranked selection, and optional top-k
  selection configured through the process environment.
- A derived, in-memory semantic retrieval core with validated embeddings, an
  embedding-provider boundary, overflow-safe deterministic cosine ranking, and
  a fresh-index builder for current active records. Embeddings are capped at
  16,384 values; a live index is capped at 20,000 entries, 1,024 characters per
  memory ID, and 4,000,000 aggregate vector values. Full rebuilds preflight
  population limits, and incremental failures preserve the last working index
  and optional cache. Cold rebuilds resolve every cache lookup before provider
  work and allow 256 provider calls by default; an ASCII whole-number process
  setting can select 0 through 20,000, where zero is cache-only. An excessive
  miss count fails before the first provider call, cache replacement, or
  semantic-runtime publication. Every full rebuild also shares a monotonic
  120-second deadline by default, configurable from greater than zero through
  3,600 seconds. The deadline starts before record/source/cache preflight, and
  each provider call receives the shorter of its request timeout and remaining
  rebuild duration. Expiry preserves the last complete index and prevents
  partial cache/runtime publication. Embedding source text is capped at
  1,000,000 characters and is preflighted across rebuild, incremental, and
  query paths.
  An explicit Ollama `/api/embed` adapter is available without third-party
  dependencies, rejects HTTP redirects, sends at most 8 MiB of exact compact
  UTF-8 JSON, rejects invalid or excessive bodies before opening the network
  request, and reads at most 1 MiB before parsing an embedding response. Opt-in
  Bootstrap wiring registers the runtime, publishes the primary container, and
  starts one daemon replacement build in the background. Cold or unavailable
  Ollama therefore does not hold primary startup. Full rebuilds are
  single-flight; a memory event marks an active snapshot dirty and permits one
  coalesced retry, while a second changing attempt publishes no stale result.
  Shutdown rejects new work and suppresses in-flight index publication. The
  exact `semantic recall retry` command schedules the same bounded background
  rebuild and a duplicate request reuses the active job. Once an index is ready,
  memory lifecycle events enqueue best-effort incremental work on that same
  daemon worker, bounded to 20,000 pending IDs. Repeated events coalesce by ID,
  stale in-flight results are rejected, and primary-memory completion never
  waits for the provider. An embedding failure never reverses a completed
  primary-memory write. Semantic results are
  used only by the explicit `semantic recall <query>` request path with
  deterministic lexical fallback. The runtime retains separate safe full
  rebuild and incremental-update diagnostics without exposing provider details.
- Deterministic reciprocal-rank fusion for explicit semantic recall when both
  current-session semantic and lexical candidates exist. Hybrid responses use
  rank scores; semantic-only responses retain cosine-similarity scores.
- A read-only `semantic recall status` diagnostic. It reports the optional
  runtime's disabled, initializing, refreshing, updating, unavailable, ready, or stopped
  state, index size and dimension when available, and separate safe rebuild and
  incremental-update
  diagnostics; it does not generate an embedding or change conversation
  memory.
- An optional model-scoped local semantic-embedding cache. It is disabled by
  default, validates a source-content fingerprint before reuse, updates with
  memory lifecycle events, and remains separate from the primary memory schema.
  Its provider-scoped schema-v1 snapshot is capped at 64 MiB, 20,000 entries,
  1,024-character provider and memory IDs, 1,000,000-character source values,
  16,384-dimensional vectors, and 4,000,000 aggregate vector values. Reads and
  writes enforce exact byte and collection bounds while preserving the previous
  cache after an invalid or failed update. Cache-read failure is attempted once
  per rebuild and a valid foreign-provider snapshot becomes a cached isolated
  empty view rather than being repeatedly decoded.
- Ordered local source citations for knowledge-search responses, preserving
  document identity, title, source path, paragraph index, and chunk ID.
- An explicit bounded `knowledge context <query>` flow that renders no more
  than three cited local chunks and does not persist a conversation-memory
  record.
- The OpenAI-compatible chat runtime now supports keyless activation only for
  explicit loopback endpoints (`localhost`, `127.0.0.1`, or `::1`), including
  a standard local Ollama endpoint. It omits the authorization header in that
  mode; every non-local endpoint still requires an API key and HTTPS.
- Chat-completion timeout is configurable through
  `HYPATIA_LLM_TIMEOUT_SECONDS`. Without an override, explicitly loopback
  endpoints such as local Ollama receive 300 seconds while non-local endpoints
  retain the 30-second default.
- An explicit `ask knowledge <query>` local-RAG flow. It sends only up to three
  cited chunks to an enabled local LLM runtime, bounds each source chunk in the
  prompt to 600 characters, retains citations on the answer, and does not
  augment ordinary conversation or persist a conversation-memory record.
- An explicit `knowledge graph <query>` view. For up to three matching local
  chunks it exposes the deterministic document-to-paragraph `contains`
  structure with source citations. The derived graph also maintains local
  paragraph order through `precedes` edges, remains in memory only, and never
  calls an LLM or changes conversation memory.
- An explicit `list knowledge` catalog that returns loaded local document IDs,
  titles, source paths, types, and chunk counts in deterministic load order.
  It is read-only and creates neither LLM traffic nor a conversation-memory
  record.
- Files loaded through the Knowledge Foundation receive a stable document ID
  derived from their resolved local source path. Reopening the same source
  retains its identity even if its content changes; different local sources
  receive different IDs. Programmatically created documents remain independent.
- An explicit `preview knowledge relation <source_document_id> --
  <target_document_id>` command. It validates distinct catalogued documents for
  a user-selectable `related_to` relationship and displays a pending change,
  without changing graph state, JSON memory, LLM traffic, or conversation
  memory.
- An explicit `apply knowledge relation <source_document_id> --
  <target_document_id>` command. It freshly validates the two documents and
  adds exactly one `related_to` edge to the current in-memory graph. Duplicate,
  unknown, self, and non-user-selectable relations fail without partial graph
  mutation. A relevant `knowledge graph <query>` view includes the applied
  edge. This does not write conversation memory or call an LLM.
- Explicitly applied `related_to` relations now have a separate local JSON
  store with schema validation and atomic replacement. The runtime records a
  relation only after the graph change can be rolled back on a storage failure.
  On a later startup, it restores the edge only after both matching stable
  local source IDs are loaded; no relation is inferred from a title or content.
- An explicit `preview remove knowledge relation <source_document_id> --
  <target_document_id>` command validates an existing applied relation without
  changing it. The separately confirmed `remove knowledge relation
  <source_document_id> -- <target_document_id>` command removes the graph edge
  and its persisted record when applicable. A relation-store failure restores
  the in-memory edge before reporting the failure.
- An explicit `list knowledge relations` catalog that returns only active
  explicit local links in deterministic application order. Each entry includes
  loaded source/target IDs, `related_to`, and whether the relation is persisted
  or in-memory only. It does not load missing sources or change any state.
- Deterministic Brain and CognitiveEngine routing for conversation, knowledge
  search, planning, lexical recall, semantic recall, and explicit session
  commands.
- Knowledge Foundation for `.txt` and `.md` loading, paragraph chunking,
  in-memory indexing, and case-insensitive lexical search.
- Optional OpenAI-compatible chat-completions transport, system prompt, and
  bounded same-session conversation history. Remote endpoints are required to
  use HTTPS; plain HTTP is limited to explicit loopback local runtimes so an
  API key is not sent over a remote unencrypted connection. Authenticated
  completion requests also reject redirects so a bearer token cannot cross to
  a different endpoint.
- A bounded `FilesystemContentPayload` contract fixes the local-file
  content boundary at 64 KiB per invocation with strict UTF-8/BOM byte
  accounting, canonical relative provenance, timezone-aware file/read times,
  explicit truncation, untrusted/no-instruction labels, and a local-only
  disclosure class. `ToolResult` carries it only through a separate success-only
  field, while `ToolExecutionService` requires an explicit
  `READS_FILESYSTEM_CONTENT` grant and matching descriptor. `FILESYSTEM_READ`
  and its effect are registered only by supported Windows desktop composition
  with the same bounded root. No model, memory, research, persistence, export,
  clipboard, remote, or generic telemetry content path exists.
- Every detailed Tool Layer outcome now carries the same code-owned request
  identifier used by its lifecycle events. The central service validates one
  bounded ASCII token before telemetry and carries it through success, refusal,
  cancellation, and failure. The identifier is absent from `ToolInvocation`,
  `ToolResult`, and `FilesystemContentPayload`, so neither a tool nor returned
  content can author its own provenance. The desktop projects that identity
  beside the payload without placing it inside file-authored data.
- The Windows rooted-open production boundary is implemented as the exact Tool
  Layer foundation. `WindowsRootedOpen` lazily binds fixed Windows system APIs,
  opens one component at a time relative to held parent handles, refuses every
  reparse point, supports only the proven local NTFS boundary, verifies root and
  final identities plus handle-derived containment, and closes every handle in
  reverse order. Its original opaque acquisition context still exposes no
  handle, path, or content.
- The first sensitive local-file name floor is implemented without content
  access. `FilesystemSensitivePathPolicy` classifies environment files, private
  keys, direct `.ssh` material, cloud/VCS/package credentials, browser/OS stores,
  and CI secrets using bounded categories. `WindowsRootedOpen` applies it to
  canonical admitted components before native acquisition and repeats it from
  final handle-derived components after containment but before identity proof.
  Windows trailing dots/spaces and case cannot disguise a class. This remains
  a floor, not complete secret detection; no override exists.
- The first Windows content-range boundary is the bounded platform primitive
  behind explicit desktop composition. `read_range` acquires the final file in
  the same rooted
  walk with data-read rights and read-only sharing, issues one synchronous
  `ReadFile` at an explicit 64-bit `OVERLAPPED` offset, caps native capacity at
  `max_bytes + 1`, and compares identity, size, and raw last-write time before
  and after the read. It returns an immutable raw observation only after every
  handle closes. No model, memory, research, evidence, persistence, Linux/POSIX,
  or generic content-telemetry path exists.
- The platform-neutral `FilesystemReadTool` is registered only when supported
  Windows desktop composition supplies the same root and rooted reader. It
  accepts one injected bounded range,
  requires the separate invocation-scoped content effect, refuses NUL/binary
  and invalid or split UTF-8, strips an exact UTF-8 BOM only at offset zero,
  maps platform failures to bounded Tool outcomes, and constructs the typed
  local-only/untrusted payload on success. It performs no path open, retry,
  continuation, persistence, telemetry-content, or downstream integration.
- The operator-facing content-preview contract is implemented in the existing
  Tool Console. Three required typed fields define one relative path and byte
  range; a second dialog repeats the exact scope, effect and arguments before
  one authorization. `FilesystemContentPreview` binds the central request ID
  beside provenance, while a dedicated read-only panel inserts text literally
  and labels it local-only, untrusted, and without instruction authority. The
  existing single-flight worker discards results after cancel or close, and old
  content is cleared before every new or non-success terminal state.

### Intentionally Not Implemented

- Automatic semantic augmentation of ordinary messages.
- General web discovery, automatic or unattended candidate acceptance,
  Research-plan execution/persistence, autonomous multi-source
  planning/synthesis,
  unattended/background contradiction review, automatic contradiction
  persistence or truth decisions, evidence ranking, automatic RAG augmentation, or
  cross-document semantic relation extraction.
- Agent execution, tool gateway, browser/OS control, voice, vision, robotics,
  and smart-home integrations.
- Any path that sends local-file content to a model, memory, research, evidence,
  persistence, export, clipboard, remote endpoint, or generic telemetry; any
  automatic continuation, multi-file read, sensitive override, or Linux/POSIX
  content reader.
- Encryption at rest, cloud synchronization, multi-process storage locking,
  and automated repair or unattended migration tooling.

## Current Local Hardware Baseline

The development machine observed on 21 August 2026 has a 4-core/8-thread CPU,
approximately 16 GiB RAM, and a 4 GiB-class discrete GPU. Its local Ollama
0.32.14 installation currently includes 4B and 8B chat models plus a dedicated
embedding model. These details are a privacy-minimal engineering snapshot, not
a runtime requirement or performance benchmark. Hypatia should retain CPU
fallback and remain useful with locally hosted 4B/8B models while allowing
stronger hardware to scale the same provider boundaries.

## Verification

Last verified in the local development environment:

- 3,659 automated tests pass through package-aware discovery.
- Black and Ruff pass for `src` and `tests`.
- MyPy passes for all `src` files and the focused sensitive-path/rooted-open
  security tests. A full `src` + `tests` MyPy sweep still has separately
  recorded pre-existing test typing debt, so repository-wide test typing is not
  claimed as a passing gate.
- The local PyInstaller Windows onedir package builds successfully. The most
  recently generated `v0.3.180` executable's startup smoke is unverified
  because Windows Application Control blocked that new unsigned artifact
  before process start. No Windows security control was disabled or bypassed.
- Whitespace validation (`git diff --check`) passes.

These checks describe the local working tree and do not create a GitHub
release, tag, commit, or pull-request approval.

### Live local semantic-runtime check

On 21 August 2026, the v0.3.68 opt-in runtime was exercised against the local
Ollama service with `embeddinggemma:latest`. Bootstrap made the primary
container available before the cold embedding call completed; its background
worker then built one valid 768-dimensional record and explicit semantic recall
returned that temporary conversation as a semantic result. This check used
temporary memory/session files and did not alter the project's persisted data.

### Live local chat-runtime check

On 15 August 2026, the published v0.3.9 chat runtime was exercised against
the local Ollama service with `llama3.2:latest`. An ephemeral Bootstrap
instance completed a Turkish greeting request through Hypatia's
OpenAI-compatible local chat path. Temporary memory/session files were used,
so this check did not alter the project's persisted data.

### Live local structured-review check

On 21 August 2026, the v0.3.78 read-only contradiction proposal adapter was
exercised against local Ollama `qwen3:4b`. A schema-constrained request with
reasoning disabled returned one pair with exact code-derived evidence in about
four seconds. The ephemeral records were not stored and project data was not
changed.

## Next Milestone

One human-approved foreground execution is enforceable. Starting a research plan
requires one exact valid approval for that plan and run and spends it
permanently; capabilities, budget, and disclosure are enforced as upper bounds;
and an authorization problem is reported as not reached rather than as a failed
execution. The approval-to-execution handoff is not atomic and is not claimed to
be: a crash can leave an approval spent with no execution, and cannot leave an
execution running on an approval still available to spend again.

Autonomy is not enabled. Ten of the eleven autonomy intents remain unreachable,
the autonomy loop and the scheduler cannot reach an approval, and no background
task carries one.

A started execution is now answerable: the operator can read its canonical
state and remaining budget, advance it exactly one step at a time, and cancel
it. The approved budget is enforced arithmetic — checked before each attempt,
charged at the attempt boundary, and never refunded when an attempt fails.

Discovery results are now ranked before a person chooses among them.
Deterministic relevance ranking compares the words of the question against the
words of the record — weighted so an identifier counts for more than a common
word — and keeps the parts and reason codes that produced each score. There is
no model in the path, no network call, and no budget cost, so the same inputs
give the same order on any machine. Relevance stays separate from truth: a score
says the question's words are in the title, and never that the source is
reliable or correct.

Two limitations are recorded rather than left to be discovered. Matching is
lexical, so a paper about the same attack under another name does not score for
the name it does not use. And a title matching the one distinctive token of a
question while being about something else still ranks high; the evaluation set
contains that case and the test records the disagreement instead of reweighting
until it disappears.

A person can now record what they concluded about a source after reading it.
Four structured answers — usefulness, applicability to the question,
independence, and publication status — sit on the assessment record that already
existed, each defaulting to `unknown` because most sources are never appraised.
A retraction is expressible and deletes nothing: the source, its evidence, and
every claim that rested on it stay exactly as they were, and the assessment says
what happened.

The separation is the load-bearing part. A judgement moves no relevance score,
no rank, no reputation, no evidence, no claim, no confidence, and no acceptance,
and the panel shows all four dimensions as separate labelled lines so that
`Relevance: strong` cannot be read as a verdict on the source. Two limits are
stated rather than left to be found: an appraisal names the evidence it was made
about, so it follows acceptance rather than preceding it, and an assessment
written by an approved plan step carries `unknown` on all four dimensions
because a plan authorization names text and trust and nothing more.

Calibration now reads those judgements. A claim resting on a source the operator
marked retracted, withdrawn, corrected, not useful, unrelated, background-only
or not independent is reported as such, with the source and the assessment
named, and a separate claim-level warning is raised when apparent corroboration
rests on sources somebody said repeat each other. Equivalent stored records of
one canonical resource produce one warning per concern, with all claim-linked
evidence retained and no inflated warning count.

Those independence judgements now also bound the structural support ceiling.
Several distinct resources reach `strong evidence / high confidence` only when
every one has an explicit active `independent` judgement and medium-or-better
trust. Unknown or conflicting independence stays silent as a warning, but it
cannot be counted as proof of independence.

Curiosity applies the same boundary to hypotheses. When supporting evidence
comes from several canonical sources but their independence is unknown,
derivative, likely duplicated, or actively disputed, Hypatia reports a separate
hypothesis-independence gap and asks which independent source could corroborate
the hypothesis. The question can enter the existing local-first proposal flow,
but noticing or previewing it changes no hypothesis and starts no research.

It corrects nothing. No confidence is lowered, no claim withdrawn, no evidence
removed, no source rejected, no reputation moved, no relevance rank touched —
and the report says so in its own words. Silence stays silence: unknown
dimensions, unassessed sources and records predating these fields warn about
nothing, and a claim with no warnings is never shown as verified. Only the
structured fields speak, so a note worrying that a paper might be retracted
produces nothing, and neither does a source whose own title says it was.

Research can now reach vulnerability records. The NVD CVE API 2.0 is a second
discovery provider, verified against the live service rather than from
documentation: an exact CVE lookup returns the vulnerability itself, and
anything else becomes one bounded keyword search. Structured metadata comes with
it — record status, CWE identifiers, every CVSS metric kept with its own scorer
rather than collapsed into a maximum, bounded references, and the CISA
known-exploited fields when they are actually there.

The provider is part of what an approval covers. A plan aimed at Crossref and
the same plan aimed at NVD digest differently, so an approval for one cannot be
spent on the other, and the digest schema moved to v2 so that approvals recorded
before provider binding fail closed rather than quietly matching a plan whose
meaning changed. Both previews name the provider in words. One approved
discovery makes one request: no pagination, no retry, no sleep, and no silent
fallback to the other provider. References are stored and never fetched.

Provider experience can now be described. For each provider and question
category the report shows the funnel — discovery operations, candidates,
accepted sources, sources with evidence, assessed sources — and then what the
operator concluded across usefulness, applicability, independence and
publication status. The join runs through canonical resource identity, the same
one the panel uses to decide whether a discovered candidate was accepted, and a
resource both providers returned is credited to neither.

There is no provider score, no winner, and no recommendation. Every ratio shows
its numerator and denominator, every profile carries a sample band whose largest
value is still only `descriptive`, and an empty history says so instead of
showing 0%. Silence is never a negative vote: an unassessed source is missing
data and an `unknown` answer is an unanswered question. The report states in its
own text that these figures are observational and selection-biased, because the
operator chose the provider, the candidate, the acceptance and the appraisal.

The operator can now put one question to both providers. A comparison turned out
to be two ordinary discovery steps in one plan: the question already belongs to
the run rather than to a step, so both sides ask the same thing by construction;
the provider was already digest-bound; a discovery step already cost one network
operation; and one advance already attempted one step. No comparison execution
engine exists because none was needed.

The pair is covered by one digest, costs two network operations, and takes two
separate presses of Advance. The Compare button reaches a preview and never a
provider. The two result sets are shown side by side, each ranked within its own
provider and never merged, with provider rank travelling alongside relevance
rank. A side nobody advanced reads as pending rather than as an empty result.

One limitation is stated rather than hidden: a failed discovery is recorded
without naming the provider that failed, so an attempted-and-errored side is
indistinguishable from an unadvanced one. Both read as pending and the run's
failure count is reported separately.

Next, measure the paired comparisons that were actually run. The provider-quality
report describes each provider over whatever questions it happened to be asked,
and pairing finally removes that cause — when both providers answer one question,
the two samples line up and the operator's appraisals of each side become
directly comparable. Nothing reads them that way yet: the one genuinely
comparable slice of the data is still averaged in with everything else.

The accepted design keeps execution, autonomy, and scheduling unreachable from
the desktop, adds no filesystem, shell, or tool authority to research, keeps the
default model-operation budget at zero, and treats remote-model disclosure as a
permission separate from local readability. An unreachable dangerous capability
is preferable to a prematurely reachable one, and the unreachable-intent count
is not a number to improve for its own sake.

The restart-bound desktop workspace-selection design remains accepted and
unimplemented. Its staged implementation, beginning with the bounded strict
preference record and immutable types only, follows this milestone rather than
being mixed into it.

Do not wire content into model context, memory, research, evidence,
persistence, exports, clipboard, remote disclosure, automatic continuation,
generic telemetry content, or an operator override. POSIX/Linux rooted-open
remains a later platform milestone rather than being mixed into the workspace
selection boundary.
