# Changelog

All notable project changes are recorded here.

## [0.3.339] - 2026-09-14

### Added

- Safe restart/resume for the current bounded semantic learning mission after a
  durable source/evidence/assessment checkpoint. The existing mission plan,
  consumed approval, exact endpoint/model/disclosure, source scope and one
  cumulative allowance are reconstructed and verified before remaining approved
  work continues. Completed operations are never replayed.
- A non-content mission recovery checkpoint alongside execution persistence. It
  stores only canonical discovery/evidence/assessment identities, accepted URL
  identities, body fingerprints and inspected-byte accounting; source bodies,
  transient fetch previews and model proposals remain outside this snapshot.

### Boundaries

- A restart after a fetched-but-unaccepted preview, or after a model result that
  was not retained as its next durable note, remains fail-closed. Hypatia leaves
  that execution restored and reportable without refetching, re-calling a model,
  refunding budget or guessing an outcome.
- This is a narrow recovery path for the existing semantic learning mission, not
  a general scheduler, generic agent runtime, dynamic replanner or live-model
  validation. No provider/model fallback, retry loop, desktop change, push or
  remote CI is introduced.

## [0.3.338] - 2026-09-13

### Added

- First bounded text research journey from real Bootstrap and the desktop goal
  entry: inert permission preview, one confirmation, local search, one selected
  discovery provider, up to three reference sources, grounded recorded excerpts,
  approved semantic comparison, one conditional follow-up, and a cited teaching
  report. No intermediate Continue or new approval is required.
- Canonical digest-bound mission policy for later-selected mission-owned evidence:
  exact endpoint/model/disclosure, fixed input selection, per-call content limit,
  retention policy and existing cumulative capability costs. Maximum 18 advances,
  9 network reservations and 2 model operations; no allowance reset or retries.
- Destination-pinned comparison registration when existing model configuration
  is enabled. Existing executor checkpoints/accounting and source/evidence
  validation are retained. Tentative comparison notes use the existing durable
  research-note contract and do not become claims or verified facts.
- Existing opted-in failure memory retains and recalls provenance-linked advisory
  lessons. Unavailable retention does not discard the research report. The new
  desktop request explicitly preserves partial reports after cancellation;
  other desktop cancellation behavior remains unchanged.

### Boundaries

- Pair/source selection is deterministic lexical selection, not a general model
  planner. Adaptation selects one pre-approved conditional branch using one
  further candidate from the original discovery, not arbitrary recursive search.
  Agreement/not-comparable stops without retrying or spending the optional branch.
- Research runs remain collecting; tentative comparisons do not establish truth.
  Early delivery does not mark unused optional plan steps completed. Reports use
  quotes and labelled interpretations, not independently verified synthesis.
- Existing reference/exact-pair approvals gain no implicit model permission.
  Restart retains canonical records but does not replay interrupted missions.
  No vision, live model accuracy, target testing, paid call, push or remote CI.

## [0.3.337] - 2026-09-12

### Added

- Exact-pair semantic comparison operation for the canonical executor. Trusted
  composition can supply a destination-pinned operation to CognitiveEngine;
  default composition remains unregistered. Existing exact approval, cumulative
  allowance and durable pre-attempt checkpoint semantics are reused unchanged.
- Before model disclosure, the operation checks exact endpoint/model, disclosure,
  run/question identity, current ordered evidence snapshots and accepted sources.
  Refusal, failed validation and cancellation never fall back or retry.
- Typed transient comparison results reach BrainResponse through ordinary
  advance and bounded continuation. Attempt/outcome/spending use existing durable
  execution records; candidate bodies are not persisted as facts or evidence.

### Limits

- Automatic mission entry still rejects model budgets; desktop remains lexical.
  No future excerpt selection, default runtime model configuration, live model
  call, comparison acceptance or model accuracy claim is introduced.

## [0.3.336] - 2026-09-12

### Added

- Canonical authored-plan approval for semantic comparison of two already
  selected, recorded evidence excerpts. A distinct capability binds their full
  ordered snapshots, source identities, question, endpoint/model, disclosure and
  declared cost into the existing plan digest. Preview displays the exact inputs.
- Approval checks current run membership, accepted sources, disclosure and the
  existing cumulative budget. Declared cost is one advance, one network operation
  and one model operation. Changed comparison budget/disclosure requires a fresh
  preview; changed plan bindings invalidate the existing digest-bound approval.
- Legacy approvals gain no capability; absent bindings preserve legacy digests
  and the existing approval persistence schema remains unchanged.

### Limits

- Contract only: no comparison operation is registered or wired to automatic
  missions. Desktop comparison remains lexical. Future/dynamically selected
  excerpts cannot be approved by this contract. No live model calls or accuracy
  claim; no new permission store, comparison budget, retries or autonomous loop.

## [0.3.335] - 2026-09-12

### Added

- A bounded semantic-comparison proposal adapter using the existing structured
  model interface. It consumes two immutable evidence records and the original
  question, and returns at most three tentative pairs: possible agreement,
  possible conflict, or not comparable. Both quotations must occur exactly once
  in their respective recorded excerpts. No lexical overlap is required.
- A transient input fingerprint covers the question, run ID, ordered full
  evidence records and proposal limit. Models receive only aliased excerpts,
  truncation flags and the question, not operator notes or provenance IDs.
- Strict response schemas and all-or-nothing validation reject unknown fields,
  invented or ambiguous quotes, duplicate pairs, false-certainty relation labels,
  malformed JSON, duplicate keys, oversized output and invalid Unicode. One call
  only, no retry, no source/output text in failure diagnostics.

### Limits

- Backend prerequisite only: NOT wired to automatic missions or the desktop.
  Current missions retain their existing zero-model-call scope. The adapter
  neither grants permission nor charges budget, writes records, selects a model
  destination, or executes instructions. Its fingerprint is not authorization.
- Future execution wiring must check current run membership and chunk integrity,
  bind the model destination/disclosure in the initial mission, charge that
  mission's cumulative allowance, and label generated interpretations honestly.
  Model interpretation quality is not established by fake-response tests.
- A validated quote proves source grounding, not that the proposed relationship
  is correct. Empty output does not establish agreement or completeness. No
  contradiction, claim, source-trust or completion record is created here.
- The next user-facing boundary is unchanged: automatic semantic comparison and
  contradiction investigation, followed by follow-up research, adaptive
  replanning, completion evaluation and a cited final answer.

## [0.3.334] - 2026-09-12

### Added

- One initial comparison-mission confirmation drives local search, discovery,
  two distinct reference fetch/inspection/acceptance/evidence chains, two
  grounding-only assessments and one canonical cited lexical comparison.
  No intervening Continue or new per-step approval is required. Existing
  planner, executor, allowance, assessments and comparison records are reused.
- Comparison scope is part of the original digest and cannot be added to an
  already approved one-source mission. All eleven advances share the original
  cumulative allowance: five network reservations, zero model calls. The
  successful fixture makes three external calls (discovery plus two fetches);
  acceptance conservatively retains its reservation while reusing inspected text.
- A shared 16 KiB inspected-text limit spans both sources. Canonical URL identity
  prevents selecting the same reference twice; a redirect back to an acquired
  reference refuses the second acceptance. Identical bodies are flagged as
  possible duplicates, never independent corroboration.
- Comparison rechecks recorded evidence integrity and cites both canonical
  evidence and current assessments. Changed or superseded inputs, failed
  fetches, missing provenance, exhausted limits and cancellation stop without
  retry. Initial limits are never silently increased by the desktop action.

### Limits

- This compares question-term coverage, not semantic claims. Grounding-only
  assessments leave trust unassessed and independence unknown. Different URLs
  do not prove independence; absent excerpt terms do not imply absent source
  claims. No truth, agreement, contradiction, winner or completion is inferred.
- Next human boundary: semantic comparison and contradiction investigation,
  followed by follow-up research, adaptive replanning, completion evaluation
  and a cited final answer. The research run remains collecting.
- The shared text bound is not an aggregate HTTP-wire-byte quota. Existing
  transport limits remain. Missing transient observations after restart still
  refuse resumption; durable spending is not reset. No target or model traffic
  is enabled by this milestone.

## [0.3.333] - 2026-09-12

### Added

- One confirmed reference mission now proceeds through local search, named
  discovery, deterministic source selection, fetch/inspection, canonical source
  acceptance, lexical evidence proposal, grounding validation and recording.
  No caller-side Continue or per-step approval is required.
- Digest-bound mission scope permits one provider-derived public HTTPS source
  and one evidence record. Concrete URL/chunk inputs derive only from that
  mission's predecessor observations. Original plan, capability set, question,
  approval and execution identity remain unchanged. The existing executor and
  autonomy loop own all five steps; no parallel agent engine or store was added.
- The existing execution allowance is cumulative across derived steps and
  persists with the original mission digest. Larger caller loop budgets cannot
  enlarge it. Failed attempts remain charged; refusal stops the loop immediately.
- Acceptance reuses the exact inspected body rather than fetching a second
  version. Its existing network-cost reservation is conservatively retained:
  five advances and three reserved network operations, with two external calls
  (one discovery and one fetch) on the successful deterministic fixture.
- Discovery returns its canonical record identity, preserving provider/query
  provenance instead of inferring it from execution order or display text.

### Limits

- Selection and evidence proposals are lexical, not semantic model reasoning.
  Validation proves source grounding, not truth or corroboration. The run stays
  collecting; no claims, comparison or completion are invented.
- One source with at most 16 KiB of inspected text. This is a retained-preview
  limit, not a new aggregate HTTP-wire-byte quota; existing fetch limits and
  public-address/redirect protections remain. No target testing or model calls.
- Transient observations are not reconstructed after restart. Durable spending
  and audit survive; missing text refuses resumption without automatic refetch.
- Next human boundary: comparison/contradiction investigation and follow-up
  planning. Autonomous replanning, completion evaluation and a cited final
  answer are still pending; the complete North Star is not claimed.

## [0.3.332] - 2026-09-12

### Added

- One explicit goal-start request now derives the existing research opening,
  records its exact approval, starts its execution and performs local search
  plus selected-provider discovery through the existing autonomy service.
  A narrow goal-start handler retains approval access outside the autonomy
  runner and scheduler; their existing no-new-approval boundary is preserved.
  Desktop action uses one initial scope/budget confirmation and the existing
  cancellable worker. No manual Continue is needed between those two steps.
- Explicit opening-only scope, configured provider and zero-model-call budget
  are mandatory. Authored plans, target scope and additional capability fields
  cannot be smuggled through this action. Existing Manual controls remain.
- Same-process duplicate request and concurrent-start protection. Run,
  discovery, approval and execution audit reuse existing stores; the run stays
  collecting and the response explicitly reports research incomplete.

### Fixed

- Autonomy stops immediately when an advance is refused without a state change,
  instead of repeating that action until its outer attempt limit is exhausted.
- Nonfinite autonomous time budgets are rejected.

### Limits

- This is an autonomous opening, not the North Star research journey. Automatic
  candidate selection/fetch, canonical evidence recording, comparison,
  goal-scoped replanning and cited final answers remain open. No new mission
  authority, scheduler or execution store was introduced.
- Existing between-operation time limits are not hard provider preemption.
  Restart preserves audit but does not replay a goal; request deduplication is
  process-local, not durable idempotency. No live model/provider test is claimed.
- See `docs/Roadmap/Autonomous_Research_Connection_Assessment.md` for the actual
  architecture, missing connections and ordered implementation plan.

## [0.3.331] - 2026-09-11

### Added

- Executable semantic-evidence proposal operation for the existing typed research
  plan registry. An exact binding covers input fingerprint, endpoint and model
  in the canonical plan digest. The draft and approval previews display it.
  Existing non-semantic plans retain their original digest bytes.
- One attempt reserves one network operation and one model operation, including
  loopback inference. Approval metadata can explicitly choose a model-call limit;
  its default remains zero. The ordinary executor charges before dispatch and
  does not refund failed/declined attempts. A model step without an approved
  allowance is refused before dispatch.
- The operation checks disclosure, exact destination, model, current run/question,
  request fingerprint and cancellation. LOCAL_ONLY cannot reach a remote endpoint.
  Missing transient input is refused, never refetched. The configured destination
  constructs the provider itself; source text cannot select endpoints or tools.
- Validated proposals return through a bounded transient BrainResponse channel,
  including foreground Continue. They are not written as evidence, claims, source
  bodies, execution snapshot content or ordinary chat text. Status/restart does
  not restore them. Cancellation discards generated proposals.

### Limits

- Backend composition and approval/execution are tested with injected fake
  transport. The default Bootstrap and desktop do not yet register/expose this
  operation or own its transient input lookup. No live model call was made and
  semantic answer quality has not been evaluated. Next is the desktop-reviewed
  transient-input handoff and runtime registration, not another inert wrapper.
- Endpoint validation reuses the existing LLM policy. Production transport must
  retain redirect rejection and bounded timeouts. The cost counts one declared
  transport attempt, not tokens or model-internal work. Refusal may spend the
  declared attempt allowance without a transport call, as existing semantics do.
- Restored executions have no disclosure permission; they cannot silently call
  a model. Target-bound plans remain restricted to fetch/accept and cannot carry
  this semantic capability. No source acceptance or autonomous report is added.

## [0.3.330] - 2026-09-11

### Changed

- Live execution contexts now carry the exact typed disclosure value from the
  successfully consumed plan approval. Both authored and derived-plan Start
  paths propagate it; Advance and bounded Continue retain it per operation.
- A missing approval consumer or a restored execution has disclosure NONE.
  Start/Advance request metadata cannot supply or override this value. Restored
  snapshots do not contain disclosure, so rebind does not infer consent from
  remaining model budget, prior capability or an old approval.

### Limits

- This is permission propagation, not a new permission grant or model action.
  No model step is registered and no endpoint is contacted. A future semantic
  operation must enforce disclosure against endpoint locality and require its
  exact reviewed input plus the existing pre-attempt model budget charge.
- No snapshot schema or durable permission recovery is introduced. Future model
  work after restart must refuse missing permission/input instead of silently
  recreating it. Existing non-model operations retain their current behavior.

## [0.3.329] - 2026-09-11

### Added

- Immutable transient semantic-input review, preserving the exact question,
  ordered source previews and proposal limit. Its fingerprint includes every
  source-preview field, including the extracted text and acquisition provenance.
- The semantic adapter consumes this same validated request. A prepared-call
  boundary rejects a different expected fingerprint before invoking the model;
  the original propose method delegates through the shared input contract.
- Exact model-data projection remains question plus source aliases and bodies.
  Review provenance is bound locally but not added to model input. No persistence,
  endpoint selection, additional request or authorization mechanism is added.

### Limits

- A content fingerprint is not authorization and does not replace plan_digest.
  Runtime integration still needs a typed model operation, the reviewed input
  bound into the ordinary plan, explicit disclosure enforcement and model budget
  charging. The existing executor context does not yet carry disclosure, and the
  operation registry has no model operation. This release does not wire one.
- Tests establish immutable input and changed-review rejection using a fake
  model. They do not establish live semantic quality or a complete research loop.

## [0.3.328] - 2026-09-10

### Added

- An unconnected semantic evidence proposal adapter for transient source previews.
  One structured model response can propose at most five exact quotations from
  at most three sources totalling 16,384 UTF-8 bytes. Oversized input is rejected,
  not silently truncated. No transport, store, retry or tool runner is introduced.
- Model-facing source aliases resolve only against the supplied batch. Quotes
  must occur exactly once in the named source; invented, ambiguous, duplicate or
  malformed proposals reject the entire result. Exact offsets and original
  preview provenance are retained separately from the untrusted rationale.
- Strict response fields, Unicode and size checks; no generated authority,
  confidence, accepted-document IDs or actions are accepted. No history or source
  metadata is included in the prompt beyond aliases and literal bodies.

### Limits

- This adapter is not wired into Bootstrap, Brain or the desktop. It has no live
  model feature yet. Its tests use a fake structured model and do not establish
  semantic quality, prompt-injection immunity or the truth of model rationales.
- The next integration must explicitly bind model disclosure permission to the
  question and exact temporary source set and enforce the existing model budget
  before invocation. Fetch permission alone must not authorize model disclosure.
- Source acceptance, persistence, synthesis and the full research/report journey
  remain unfinished. The existing desktop Suggest passages stays local/lexical.

## [0.3.327] - 2026-09-10

### Added

- Source previews now offers a local Suggest passages action over the current
  transient batch. It ranks exact line/window quotations by distinct query-word
  overlap, with stable ties, at most ten displayed proposals, and no model call.
- Each proposed quotation retains its source preview, extracted-text digest and
  exact character range. Quotes are derived from that range, not supplied by a
  generator. Bounds are 800 characters per passage, ten sources per batch and
  twenty proposals maximum at the pure-function boundary.
- Results are read-only, kept out of chat and persistent evidence records, and
  cleared when the query changes, the batch changes, or the reader is cleared.

### Limits

- This is lexical candidate extraction, not semantic evidence evaluation. Terms
  shorter than three characters are ignored; there is no stemming or synonym
  matching. Long-line windows can split words/sentences. No match means no proposal.
- Keyword relevance is not confidence, truth, acceptance or source independence.
  Full-context human review, semantic synthesis, promotion and the complete
  autonomous research/report loop remain separate unfinished work.

## [0.3.326] - 2026-09-10

### Added

- Desktop candidate basket: Add to fetch batch, Clear batch, and Review fetch
  batch. One discovery and at most ten distinct resources are selected explicitly.
  Refreshing candidates clears the basket; selecting another run cannot reuse it.
- Review shows the exact URLs, run, discovery and plan digest, then transfers
  typed fetch steps into the existing approval form with locked instruction text.
  Review is not authorization. The existing previous-draft action restores prior
  text; targets, constraints and a different question are never silently replaced.
- Acquisition draft handoff preserves exact URLs and origin receipts through
  approval and zero-step start. The controller re-reads canonical discovery state
  and compares the plan digest before approval preview, confirmation and start.
- Button-level integration verifies two selected candidates reach bounded fetch
  results without implicit acquisition or persistent source acceptance. A real
  Tk desktop smoke check verifies selection and locked text with fake providers.

### Limits

- Candidate selection is still operator-driven. Automatic provisional evidence
  extraction, adaptive search and complete autonomous reports remain open.
- The existing `opening_draft` keyword now also accepts an exact acquisition
  handoff; manual and question-opening callers retain their current behavior.

## [0.3.325] - 2026-09-10

### Added

- An explicit acquisition-batch preview resolves one discovery from the current
  open research run and selects one to ten exact recorded candidate URLs. Wrong
  run/discovery, changed URLs, duplicate resource identities, mutable selection
  containers and authored-plan/constraint/target overrides are refused.
- The ordinary planner creates only `source_fetch` steps. A literal origin
  receipt (run, discovery, provider, discovery time) is included in the existing
  digest-covered instruction; titles/snippets are not used as instructions.
  No plan schema, digest algorithm, grant or execution engine changes.
- Brain routing and a desktop controller preview method are connected. Tests
  exercise exact approval, changed-URL refusal, zero-step start and two bounded
  fetches returning transient text without source acceptance or replay authority.

### Limits

- This exposes inert batch planning, not automatic acquisition. The visual
  candidate selector and exact typed handoff to desktop approval are still open.
- Membership is checked at preview time. The resulting plan must be separately
  reviewed and authorized; it does not grant authority to future discoveries.

## [0.3.324] - 2026-09-10

### Added

- Desktop Source previews tab for the latest transient research acquisition
  batch, with source selection, requested/source/acquisition URLs, timestamps,
  extracted-text byte counts and digests. Text is shown literally in a read-only
  widget, separately from chat and durable status messages.
- Clear previews releases the batch; close also clears it. A new execution
  response replaces the batch or reports no text, including restored status.
  Unrelated chat does not discard the currently displayed research text.
- Reader text and provenance follow the existing comfort/theme/font controls.
  The reader has no fetch, acceptance, export, model or command controls.

### Limits

- This is reading, not evidence extraction or automatic candidate selection.
  Only the latest batch is retained, with the existing ten-source bound; mixed
  execution/run identities or repeated step identities are refused.
- Status refresh does not recover old text. Nothing is silently refetched or
  accepted; the complete autonomous research/report journey remains unfinished.

## [0.3.323] - 2026-09-09

### Added

- Successful explicit source-fetch operations can return a typed transient text
  preview through the execution response, separately from the 500-character audit
  detail. Each preview binds execution, run, step, requested URL, acquired-source
  provenance, UTF-8 byte count and SHA-256 of the extracted text.
- A preview contains at most 65,536 UTF-8 bytes; oversize or invalid preview data
  yields an explicit unavailable notice, without truncating, retrying or claiming
  that the completed acquisition failed. Ten-step foreground continuation can
  return at most ten previews (655,360 content bytes); this is a response-retention
  bound, not a cumulative network-byte budget.
- Previews are not saved in execution snapshots, accepted into knowledge, sent to
  a model, or returned by later status requests. Restart status explicitly states
  that temporary previews are unavailable and no source was refetched.
- Regression tests cover byte boundaries, cancellation, restart, identity mismatch,
  content-free representations and bounded multi-step return values.

### Limits

- This adds the backend content handoff only. Desktop reading, discovery-candidate
  batch selection, evidence proposals and full autonomous reports remain open.
- Sources still require exact URL authorization. No authority, transport policy,
  persistent-source schema or plan digest has been widened.

## [0.3.322] - 2026-09-08

### Added

- Explicit desktop handoff from a question-opening preview to the existing
  approval and zero-step start controls. Typed capabilities and provider survive
  the transfer with the same canonical plan digest; display text is not parsed
  as capability authority. No authorization or execution occurs on selection.
- Previous editor contents can be restored. Target/constraint conflicts and
  changed opening fields are refused; switching drafts clears cached approval.
- A deterministic end-to-end test covers preview, explicit confirmation,
  zero-step start and bounded continuation to candidate discovery with a fake
  provider. Reusing the consumed approval is refused. No source is fetched or
  accepted by the opening; this is not yet a full research report generator.
- v0.3.321 Windows and Linux CI both completed successfully before this release.

## [0.3.321] - 2026-09-08

### Added

- An explicit question-to-opening-plan preview through the existing research
  draft service and Brain route. It produces local knowledge search followed by
  source discovery using the operator-selected Crossref or NVD provider.
- Research (Advanced) includes a Turkish opening-plan preview button. It leaves
  the authored editor intact and captures question/provider before worker dispatch.
- Question wording never adds capabilities, URLs, targets or authority. Mixed
  template and authored steps/constraints/target inputs are rejected rather than
  silently discarded. Generated plans retain the ordinary canonical digest.

### Limits

- This is the opening-plan connection, not complete autonomous research. Preview
  does not approve, run, select sources or generate a report. The generated plan
  is not copied into the editor or authorized automatically.
- v0.3.320 Linux and Windows CI both completed successfully before this release.

## [0.3.320] - 2026-09-08

### Fixed

- Run Kali operations with the smaller of the scope's time budget and the
  process adapter's 30-second ceiling. The default HTTPS scope allows 60 seconds;
  passing that unchanged previously consumed approval and then failed before
  process creation. Smaller scope budgets remain binding and the process limit
  is not increased.
- Added a desktop-to-real-adapter regression test with process creation mocked;
  it reproduces the old refusal without sending target traffic.

## [0.3.319] - 2026-09-08

### Added

- Added a Turkish Kali desktop tab when program-scope enrollment is available:
  select a registered scope and hostname, choose DNS lookup or HTTPS headers,
  then explicitly preview, authorize and run through the existing services.
- Form edits invalidate local preview/approval state; late responses cannot
  restore approval for a changed selection. Runs use the shared desktop worker.
- Controller and panel tests cover real approval persistence, both reviewed
  profiles with a fake process adapter, refusal, cancellation and stale results.

### Limits

- Live execution still requires the existing Kali runtime opt-in and a policy
  permitting the chosen operation. No live target request was used for validation.
- Output is displayed for review; it is not automatically recorded as evidence.

### Fixed

- Refresh the authorization service's persisted approvals before creating a new
  one. A stale service cache could otherwise write back an approval already
  consumed by the run service. Sequential desktop runs test that spent IDs stay
  absent and cannot be replayed after another approval is issued.

## [0.3.318] - 2026-09-08

### Added

- Added a second reviewed Kali operation profile for HTTPS response-header
  lookup using `/usr/bin/curl` through the existing WSL/Kali argv transport.
- Operation-run readiness now checks the executable required by the exact
  operation profile, so DNS uses `dig -v` and HTTPS headers use
  `curl --version`.

### Safety and limits

- The new HTTPS profile remains scope-bound, policy-bound, preview-bound,
  digest-bound, authorization-bound and opt-in before any process can run.
- No general terminal, shell command string, scanner, exploit tool, recursive
  crawl, automatic claim, evidence recording or memory write is introduced.

## [0.3.317] - 2026-09-08

### Added

- Added a review-only Kali operation evidence-candidate model derived from
  bounded stdout after an explicitly authorized operation run.
- `kali_operation_run` responses now expose the derived candidate and render
  it separately from raw stdout/stderr.

### Safety and limits

- Kali output remains untrusted process output. The candidate view records no
  evidence, creates no claim, accepts no source and writes no memory.
- Candidate lines are bounded and derived only from stdout; stderr remains a
  diagnostic channel and is not promoted into evidence candidates.

## [0.3.316] - 2026-09-08

### Added

- Added `HYPATIA_KALI_OPERATION_EXECUTION_ENABLED=true` as the explicit
  production opt-in for installing reviewed WSL/Kali runtime adapters.
- Bootstrap now installs and registers the WSL/Kali readiness probe and process
  adapter only when that exact opt-in is present.
- Added bootstrap tests proving the default runtime installs no Kali execution
  adapter and the enabled runtime starts no subprocess during initialization.

### Safety and limits

- The opt-in only installs adapters; it does not authorize a scope, approve an
  operation, run a command, start DNS traffic or record evidence.
- The accepted opt-in value remains strict lowercase `true`; values such as
  `True`, `1` or `yes` leave execution disabled.

## [0.3.315] - 2026-09-08

### Added

- Added a bounded `WslKaliOperationProcessAdapter` for running exactly one
  reviewed WSL/Kali command plan.
- The adapter invokes `wsl.exe -d kali-linux -- <reviewed argv>` with
  `shell=False`, closed stdin, a hard timeout and bounded stdout/stderr lines.
- Added adapter-level tests for exact argv construction, bounded output,
  timeout reporting and launcher/distribution refusal.

### Safety and limits

- Production bootstrap still does not install the process adapter by default.
- The adapter accepts no shell command string, no arbitrary executable profile
  and no model-authored command line.
- Process output remains untrusted and is not evidence.

## [0.3.314] - 2026-09-07

### Added

- Added the first reviewed `kali_operation_run` application boundary for the
  DNS-record lookup profile.
- The run boundary re-derives the current preview, checks the exact persisted
  authorization, verifies runtime readiness, consumes the authorization, then
  delegates only to an injected process adapter.
- CognitiveEngine refuses operation runs unless a runtime probe and process
  adapter are explicitly installed.

### Safety and limits

- Production bootstrap still installs no Kali process adapter, so the default
  app runtime remains fail-closed for real operation runs.
- Process output is rendered as untrusted output and is not recorded as
  evidence.

## [0.3.313] - 2026-09-07

### Added

- Added a reviewed WSL/Kali runtime probe adapter for the readiness boundary.
- The adapter uses a fixed argv tuple for `wsl.exe -d kali-linux --
  /usr/bin/dig -v`, with `shell=False`, closed stdin, bounded output and a hard
  timeout.
- Readiness can now distinguish missing WSL/Kali, non-zero probe exits and
  unexpected `dig` versions without running a target operation.

### Safety and limits

- This release still does not run the reviewed DNS lookup operation and sends
  no target traffic.
- CognitiveEngine continues to fail closed unless a host runtime probe is
  explicitly injected.

## [0.3.312] - 2026-09-07

### Added

- Added an explicit `kali_runtime_readiness` boundary for reviewed WSL/Kali
  runtime prerequisites.
- The readiness report is opt-in only and names the required transport,
  distribution, executable path and version prefix before any future real
  runner can be considered.
- CognitiveEngine can route readiness checks with a replaceable probe; the
  default production probe fails closed when no host adapter is configured.

### Safety and limits

- This release still adds no real Kali runner, terminal, shell, child process,
  DNS lookup or target network traffic.
- Missing operator opt-in refuses before even the readiness probe is called.

## [0.3.311] - 2026-09-07

### Added

- Added a deterministic fake-runner gate for authorized Kali operation
  previews.
- The fake runner reloads the persisted operation authorization, re-derives the
  current preview, verifies the exact operation digest and binding facts, then
  returns fixture output only.
- CognitiveEngine can now route the explicit `kali_operation_fake_run` intent
  when both program-scope revisions and Kali operation authorization storage
  are available.

### Safety and limits

- This release still adds no real Kali runner, terminal, shell, child process,
  DNS lookup or network traffic.
- Missing, expired, mismatched or stale operation authorization refuses before
  any simulated result is returned.

## [0.3.310] - 2026-09-07

### Added

- Added a reviewed, code-owned Kali command plan for the DNS-record lookup
  operation preview.
- The preview now exposes an inert argv tuple for `/usr/bin/dig` with fixed
  options, normalized in-scope hostname and reviewed DNS record type.
- The operation digest now includes the reviewed command-plan facts, so a
  human authorization binds the exact inert terminal plan that was previewed.

### Safety and limits

- This release still adds no Kali runner, terminal, shell, child process, DNS
  lookup or network traffic.
- No user-authored or model-authored command string is accepted; the plan is an
  argv tuple only and keeps `shell=False` with closed stdin.

## [0.3.309] - 2026-09-07

### Added

- Added atomic JSON persistence for Kali operation authorization records.
- Production bootstrap now wires a separate
  `kali_operation_authorizations.json` store so future runner gates can read
  exact operation approvals after restart.
- Authorization creation now fails closed if the approval cannot be durably
  recorded.

### Safety and limits

- This release still adds no Kali runner, terminal, shell, child process,
  generic command execution, DNS lookup or network traffic.
- Persisted operation approvals remain separate from plan approvals and do not
  start or resume any execution on their own.

## [0.3.308] - 2026-09-07

### Added

- Added explicit human authorization for the first reviewed Kali operation
  profile by binding approval to one exact inert operation digest.
- Kali operation authorization re-derives the preview from canonical active
  program-scope state before approval, so changed host, record type, scope
  revision, policy or operation facts refuse instead of inheriting approval.
- Authorization responses expose the operation digest, scope revision digest,
  execution policy digest, authorization window and human authorizer.

### Safety and limits

- This release still adds no Kali runner, terminal, shell, child process,
  generic command execution, DNS lookup or network traffic.
- Operation approval does not construct a command line and does not start
  execution; it is a bounded prerequisite for a future fake runner and then a
  reviewed WSL/Kali adapter.

## [0.3.307] - 2026-09-07

### Added

- Added an inert structured Kali operation preview for the first reviewed
  operation profile: DNS record lookup.
- The preview binds the exact active program-scope revision, scope revision
  digest, execution policy digest, target hostname, DNS record type, permitted
  ports and bounded operation budget into an operation digest.
- The preview is available only through an explicit structured intent and
  returns operator-visible facts without constructing a command line.

### Safety and limits

- This release still adds no Kali runner, terminal, shell, child process,
  generic command execution, DNS lookup or network traffic.
- Out-of-scope hosts, excluded hosts, missing scope history, inactive scope
  revisions, revision digest mismatch and policies without DNS lookup permission
  fail closed before any DNS, process, write or network side effect.

## [0.3.306] - 2026-09-07

### Added

- Program-scope revisions now carry an explicit bounded execution policy for
  future target operations: permitted check classes, permitted ports, request
  count, request rate and time budget.
- The policy is immutable, validated, persisted under program-scope revision
  schema v2, and protected by its own policy digest without changing existing
  scope revision identity.
- Scope enrollment preview can carry an exact policy while still performing no
  execution, DNS lookup, network request, model call or durable write until the
  existing explicit confirmation step.

### Safety and limits

- This release still adds no Kali runner, terminal, shell, process capability,
  scan, probe, exploit or arbitrary command execution. It only records the
  policy facts a later reviewed Kali-operation layer must enforce.
- Legacy schema-v1 scope histories remain readable and restore the existing
  HTTPS-only policy truthfully instead of widening authority.

## [0.3.305] - 2026-09-06

### Added

- Target-bound research plans now bind the exact active program-scope revision
  identity and digest into `ResearchPlanTargetBinding`, and the target-plan
  digest schema moved to v6 so this identity participates in approval and
  execution identity.
- Approval preview, approval confirmation, Curiosity proposal approval,
  execution Start, durable restore and every Advance now re-check the exact
  saved revision against the active local scope-revision history before any
  approval consumption, checkpoint, DNS lookup, provider call or network budget
  spend.
- The desktop target editor now requires a selected active saved scope record
  before using a target draft in a plan, and carries that revision ID/digest
  into the draft.

### Safety and limits

- This release still adds no Kali runner, terminal, shell, process capability,
  scan, probe, exploit, arbitrary port access or autonomous target operation.
  It is the prerequisite scope-authority gate for future reviewed Kali-tool
  milestones.

## [0.3.304] - 2026-09-06

### Added

- The desktop target-program editor now exposes the program-scope enrollment
  service: an operator can preview and exactly confirm a saved active scope
  record, refresh active records, and preview/confirm human revocation from
  the same bounded target-scope fields.
- Confirming a saved scope checks that the current form still matches the
  previewed program ID and target rules. Editing the form after preview clears
  the decision path instead of saving stale scope authority.
- The installed desktop runtime now keeps scope-revision history in the
  desktop-owned research data directory.

### Safety and limits

- The new UI writes only program-scope revisions after explicit confirmation.
  It does not approve a research plan, start or advance execution, run Kali,
  create a terminal, resolve DNS, open the network, call a model or register a
  new tool capability.
- Target plans still are not bound to an exact active scope revision at
  approval/Start/restore/Advance. That enforcement remains the next required
  integration before any Kali/process work.

## [0.3.303] - 2026-09-05

### Added

- A bounded program-scope enrollment application service with separate
  create/revoke preview and exact confirmation operations over the immutable
  v0.3.301 revision history.
- Confirmation names the exact pending revision ID and digest shown in the
  process-local preview. Caller-built revision objects are never accepted,
  previews are capped at 20, and replay or tampering is refused.
- Durable publication precedes in-memory publication. Failed persistence leaves
  the last published history unchanged; startup strictly revalidates even a
  non-JSON store through the canonical bounded codec.

### Safety and limits

- Enrollment performs no DNS, network, process, model or research execution.
  The service is not yet wired to the desktop, plan binding or dispatch gates.
- A program cannot receive a successor revision until its current revision has
  been explicitly previewed and confirmed as human-revoked.

## [0.3.302] - 2026-09-05

### Security design

- Accepted a future scope-bound Kali security-tool layer made of reviewed,
  structured capabilities; raw terminal access, command strings, shells,
  arbitrary executables and PATH-based dispatch are explicitly rejected.
- Defined exact active program scope, check-class/port/rate/time budgets,
  explicit operation authorization, process/output bounds, untrusted typed
  observations and fake-runner tests as prerequisites for execution.
- Recorded the required order: scope-revision enforcement first, then richer
  enrollment, inert operation preview, exact authorization, fake execution and
  finally one opt-in reviewed WSL/Kali operation.

### Safety and limits

- This release starts no process, registers no new Tool capability, installs no
  software and performs no network access. WSL is present on the inspected host,
  but no Kali distribution or Kali security executable was detected.

## [0.3.301] - 2026-09-05

### Added

- Immutable, human-confirmed program-scope revision records with exact target
  scope identity, fixed supported `source_fetch`/`source_accept` over HTTPS:443,
  a one-hour validity ceiling, and one-way human revocation.
- A strict bounded JSON codec and atomic local history store. Unknown, missing,
  duplicated, corrupt, reordered-authority, widened audit facts, history
  removal, and unrevoked replacement are rejected rather than repaired.

### Safety and limits

- This release establishes the durable enrollment record only. It grants no
  execution authority, performs no network access, and is not yet consulted by
  plan approval, Start, restored execution, or Advance.
- The next integration must bind an exact revision into target-plan identity
  and fail closed on missing, expired, changed, superseded, or revoked records
  before checkpoint, budget charge, DNS, or network dispatch.

## [0.3.300] - 2026-09-05

### Added

- A desktop target-program editor for one explicit bug-bounty program, bounded
  host/CIDR allow and exclusion rules, exact public HTTPS URLs, and a choice
  between read-only fetch and canonical source acceptance.
- Target drafts now travel through the existing plan preview, exact-digest
  approval, confirmation and zero-step Start flow. Editing or clearing the
  target invalidates the cached approval preview.
- Reference-provider comparison is refused while target mode is active, so a
  target-bound plan cannot silently turn into an unrelated discovery plan.

### Safety and limits

- Opening or applying the editor performs no DNS, network, persistence,
  approval or execution. Runtime scope validation remains authoritative.
- This is exact-page public HTTPS text acquisition, not crawling, scanning,
  authentication, exploitation or a general autonomous bug-bounty runner.

## [0.3.299] - 2026-09-03

### Added

- Exact program/target-scope binding in research-plan identity, authored draft
  and approval previews, confirmation and execution. Target-bound plans use
  only existing SOURCE_FETCH/SOURCE_ACCEPT public HTTPS text operations.
- Target acquisition always constructs the scoped canonical transport; the
  general reference fetcher is never its fallback. Scope applies to redirects,
  pinned connections and final responses as well as the initial target.
- Durable target-plan identity prevents restarted executions from changing
  program, rules, source URL or research run. Existing authorization/grant
  digest checks cover the binding without a second authority system.

### Compatibility and limits

- Unscoped reference plans keep their existing v2/v4 identity and behaviour.
  Target plans use v5 and cannot resume from digest-less legacy snapshots.
- No desktop program-enrollment surface, per-program revocation/rate policy,
  path restrictions, autonomous target selection or vulnerability checks are
  added. Program identity and scope rules alone are not proof of consent.
- Validation is offline; no target traffic or GitHub operations were used.

## [0.3.298] - 2026-09-03

### Added

- Strict versioned target-scope snapshots, a content digest covering all rule
  families, and bounded atomic local persistence. Restored exclusions remain
  effective in the scoped HTTPS validator.
- Regression coverage for changed/unknown/dropped/duplicate fields, malformed
  schemas, disk failures, bounded I/O and future model-field omission.

### Limits

- A snapshot and its digest grant no authority and are not an authenticated
  signature. Program enrollment, confirmation, job binding, revocation and the
  autonomous target runner remain separate required integration work.

## [0.3.297] - 2026-09-03

### Added

- Explicit bounded target-scope host/CIDR rules with exclusion precedence and
  an opt-in scoped validator for the existing public HTTPS text acquisition
  path, including redirect and connection-pinning validation.
- Offline scope-bypass regressions and an implementation roadmap toward the
  user's scope-bound autonomous bug bounty companion.

### Limits

- This is a composable target gate, not an autonomous scanner or authorization
  grant. No runtime/UI scope enrollment, target runner, path-limited program
  policy, new network capability or global research-fetcher behavior is added.

## [0.3.296] - 2026-09-03

### Fixed

- Failure Memory no longer recalls unrelated lessons or links them to authored
  plan steps solely because of long function words such as `which` and `does`,
  or generic medium names already present in the shared exclusion lists.
- Apply those existing exact-token exclusions at every length, while preserving
  subject words and technical identifiers such as XSS, SQL, C++, C#, HTTP/2,
  Next.js and CVE identifiers. Matching remains lexical and advisory only.
- No stored lessons, plan content, authorization rules or execution behavior
  are rewritten; only recall and explanation token selection changes.

## [0.3.295] - 2026-09-03

### Changed

- Hypothesis appraisals now show how many evidence records an operator has
  explicitly associated with the hypothesis's discriminating test.
- Hypothesis lists keep that test-addressing evidence count visible beside the
  separate supporting and opposing source counts.

### Safety

- The count reports an authored association only. It does not infer that a test
  ran, decide how an observation cuts, move evidence to either side or change a
  hypothesis status.
- This is a pure projection of existing hypothesis state: it writes nothing,
  performs no research, and invokes no provider or model.

## [0.3.294] - 2026-09-03

### Changed

- Inspecting a stored one-shot deferred run now shows the restrictions recorded
  by the exact grant ID that the schedule names, alongside its status and time.
- Revoked grants remain visible as historical authority records, while a missing
  or ambiguous referenced grant is reported as unavailable.

### Security

- Status lookup never substitutes whichever grant is currently active for the
  task. A later grant cannot rewrite the authority description of an earlier
  schedule.
- This is a read-only audit projection. It changes no schedule, grant, task,
  execution or budget, runs no work and performs no provider or model call.
- Unknown remains unknown: a schedule whose exact grant cannot be resolved is
  not rendered as unrestricted.

## [0.3.293] - 2026-09-03

### Changed

- Arming a one-shot deferred run now states the restrictions the exact grant
  already carries, beside the grant it names. This is the last control that asks
  a person to authorise something happening while they are not watching, and it
  identified the authority without describing it.
- The armed confirmation returned after scheduling describes the same grant.

### Security

- The displayed state is the grant's own recorded snapshot, never re-derived
  from the current plan. A grant describes the plan as it stood when the grant
  was made, and a plan can move afterwards; what the grant recorded is what the
  run is permitted under.
- The grant shown is the one whose id is shown. A second or revoked grant on the
  same task cannot supply the description.
- One wording for an existing grant, now owned by the grant itself and shared by
  every screen, so recorded-empty reads as "none" and a legacy record reads as
  "unavailable for legacy grant" wherever it appears. Unknown stays unknown.
- Display only. Opening the confirmation persists no schedule, mutates no grant,
  runs no task and spends no allowance; arming still requires the explicit call.
- Free-form constraint wording is still never interpreted. Only the persisted
  typed snapshot is rendered.

### Note

- Revoked and legacy-unrecorded grants remain ineligible and are refused before
  this screen renders at all, so the confirmation only ever describes a grant
  that is currently valid.

## [0.3.292] - 2026-09-03

### Fixed

- A deferred-grant document's declared schema version now decides which entry
  shape is legal. Shape was previously validated against "either known field
  set", so a document could call itself version 1 - the version written before
  restrictions were recorded at all - while carrying the version 2 restriction
  field, and be believed about it. The reverse passed too. A version marker that
  constrains nothing cannot tell a reader which format it is holding.
- The deferred-grant confirmation now states the restrictions the pending plan
  would bind, instead of answering "no grant". That was true and useless where
  somebody decides whether to authorise unattended execution: reporting the
  absence of the record reads as the absence of a restriction.

### Changed

- Three states are kept distinct and never borrow each other's wording:
  "Restrictions to be granted" before one exists, "Approved restrictions" for a
  grant that recorded them, and "unavailable for legacy grant" for one that
  never did.

### Security

- Strict per-version shape: a missing field, a newer field, an unknown extra
  field, a malformed restriction container and an unknown restriction value are
  each refused rather than ignored, stripped or reinterpreted. Readable versions
  are derived from the declared shapes, so a version added without one is
  unreadable rather than lenient.
- Unknown stays unknown. A legacy record still loads as unrecorded, never as an
  empty set, and reading one rewrites nothing: no upgrade, no fabricated
  snapshot, no implicit re-grant.
- The pending answer is derived from the exact plan through the same helper the
  grant is built with - never a caller-supplied argument, never read out of
  constraint wording. An existing grant is still described by its own record, so
  a stale plan cannot speak for it.
- Rendering only. Previewing creates no grant, writes nothing, spends no
  allowance and leaves the plan digest untouched. Eligibility, rebind,
  authorization, capability and budget binding, revocation and one-shot gating
  are unchanged.

## [0.3.291] - 2026-09-03

### Changed

- Claim calibration now renders the complete existing evidence-support profile
  for each active claim instead of hiding its trust range inside a compressed
  count summary.
- Operators can see distinct-source, evidence, assessment, independence,
  lowest/highest trust, contradiction and supersession facts beside the exact
  authored and supported confidence levels they influence.

### Safety

- Trust remains an authored source assessment and is not presented as a truth
  score. The calibration ceiling, verdict, warnings and claim state are
  unchanged.
- The report is still pure derivation: it performs no persistence, provider or
  model call and changes no claim, evidence, source or assessment.

## [0.3.290] - 2026-09-03

### Added

- Explicit Failure Memory recall now shows the exact normalized terms shared
  by each selected prior lesson and the operator's new research question.
- Recall responses carry the same bounded match trace as structured data for
  inspection without changing the existing lesson records.

### Changed

- The existing deterministic recall ranking now produces an explainable match
  projection while preserving its overlap threshold, weights, tie-breaks and
  result limit exactly.

### Safety

- Shared terms are labelled as lexical overlap only, never as proof that an old
  failure applies to the new question.
- Recall remains read-only and advisory: it changes no run, plan, hypothesis,
  claim, capability, authorization or provider activity.

## [0.3.289] - 2026-09-03

### Fixed

- Deferred execution eligibility now rejects a plan whose typed restriction
  forbids a capability declared by one of its own steps, even when the grant's
  restriction snapshot matches that contradictory plan exactly.
- Durable execution rebinding applies the same canonical restriction-conflict
  rule before restored work is made live again.

### Security

- Authorization, foreground Start, deferred eligibility and restored-execution
  rebinding now share `plan_restriction_conflicts` rather than maintaining
  separate rule tables.
- A rejected contradictory plan creates no deferred grant, becomes neither
  eligible nor live, reaches no provider and spends no execution allowance.
- Grant snapshot matching remains a consistency check, not proof that the plan
  itself is internally coherent.

## [0.3.288] - 2026-09-02

### Added

- A deferred execution grant now records the typed restrictions of the plan it
  was granted over, derived by the same `restrictions_of` the authorization
  snapshot uses. Auditing a grant no longer means rebuilding the plan behind
  its digest.
- Grant status and the grant confirmation state "Approved restrictions".

### Changed

- Eligibility cross-checks the snapshot against the plan and refuses on
  mismatch, exactly as it already cross-checks capabilities.

### Security

- The snapshot is derived at grant time from the exact plan, never supplied by
  a caller, and constraint wording is still never interpreted.
- It grants nothing. It adds no capability, enlarges no task budget or
  allowance, and does not alter the plan digest. Removing it makes a grant less
  usable, never more: an unrecorded grant is refused outright.
- A mismatch is refused in both directions and never reconciled by copying one
  side over the other. Refusal spends no allowance and reaches no provider.
- Revocation, lifetime, task binding, execution binding, capability binding and
  budget binding are unchanged.

### Compatibility

- The grant store moves to schema 2 and still reads schema 1. Those records load
  as **unrecorded**, not as an empty set. Typed restrictions existed for two
  releases before grants recorded them, so a stored grant may genuinely cover a
  restricted plan; reading it as "approved no restrictions" would invent
  history in the permissive direction.
- An unrecorded grant is therefore not eligible for deferred selection, and is
  rendered as "unavailable for legacy grant" rather than "none". An operator
  who still means it can grant again.
- An unknown future schema is refused rather than guessed at.

### Known limitation

- Legacy grants must be re-granted before they could ever be selected
  automatically. Nothing runs from grants today — no timer exists — so this
  costs nothing now, but it is a deliberate fail-closed break rather than a
  silent upgrade.

## [0.3.287] - 2026-09-02

### Added

- A recorded approval now names the typed restrictions it was approved under.
  Auditing one previously meant rebuilding the exact plan to learn whether it
  had been approved with no external source access; the record says so.
- Approval previews, confirmations and listings render "Approved restrictions",
  reporting "none" rather than staying silent when there are none.

### Changed

- The verifier cross-checks the snapshot against the plan and returns a
  dedicated `restriction_mismatch` verdict, exactly as it already cross-checks
  capabilities.

### Security

- The snapshot is derived, never supplied. `for_plan` builds it with
  `restrictions_of` from the exact confirmed plan and takes no restriction
  argument, so an approval cannot be typed wider than the plan it approves.
- Advisory constraint text contributes nothing to it, in either direction. A
  sentence forbidding external sources records no restriction; a permissive
  sentence with a typed restriction records it.
- It is evidence, not authority. A mismatch only ever produces a refusal, in
  both directions, and is never reconciled by copying one side over the other.
  Removing the snapshot cannot widen anything: a restricted plan still fails.
- A contradictory plan still receives no approval at all, so no misleading
  snapshot can exist for a plan nobody could run.
- The plan digest is unchanged by any of this, and still covers the restriction
  itself. Validity ceiling, single-use consumption, stale-plan refusal and human
  provenance are untouched.

### Compatibility

- The authorization store moves to schema 3. Version 1 and 2 records remain
  readable and load with no restrictions, which is what they truthfully had:
  nothing could record one when they were written. No restriction is ever
  inferred from stored text.

### Known limitation

- Deferred execution grants remain digest-bound but not self-describing: a
  grant names a plan digest and still does not say which restriction it was
  granted under. That was deliberately left out of scope here.

## [0.3.286] - 2026-09-02

### Added

- A plan constraint may now carry one typed restriction,
  `no_external_source_access`, which is mechanically enforced. Plan Draft has an
  enforcement selector; leaving it advisory is the default and preserves
  v0.3.285 behaviour exactly.
- A pure validator reports every contradiction between a plan and its own
  restrictions, naming the exact step, the exact declared capability and the
  exact restriction.

### Changed

- Approval refuses a self-contradictory plan before recording anything, and
  execution start asks the same shared validator again before any provider is
  reached. Neither boundary keeps a rule table of its own.
- Previews state enforcement for every constraint, so advisory wording is never
  left looking like it might block something.

### Security

- Wording is never interpreted. "Do not access external sources" enforces
  nothing on its own, in either direction: a constraint whose text sounds
  permissive still blocks when the operator typed a restriction. No model, no
  regex, no keyword rule, no provider-name inference.
- What counts as external comes from the declared capability cost table that
  already governs network budgets, so the restriction and the budget cannot
  disagree, and a capability added later with a network cost is forbidden
  automatically rather than slipping past a hand-written list.
- A restriction can only refuse. It adds no capability, budget, allowance or
  provider, and a refused plan is returned exactly as authored: no step
  removed, no capability lowered, no local or alternate provider substituted.
- Local-only work stays runnable under the restriction. It blocks source
  discovery, fetch and accept, and nothing else.

### Compatibility

- Plans with no constraints keep their historical v2 bytes and digest
  unchanged.
- Constraints that carry a restriction encode under a new v4 schema string,
  because the constrained encoding itself gained a field. A v3 digest can
  therefore never be reinterpreted as covering an enforced constraint; it stops
  matching, which is the fail-closed direction.
- No restriction is ever inferred for an existing constraint. Absent means
  advisory.

### Known limitation

- The enforcement selector applies one restriction to every constraint a plan
  declares. Per-row selection is deferred, and the vocabulary holds exactly one
  restriction, so this is not a policy engine.

## [0.3.285] - 2026-09-02

### Added

- Research plans now carry first-class non-executable constraints alongside
  their ordered steps. A line such as "Do not execute research or access
  external sources yet" is authored in its own field and stays a condition on
  the plan instead of becoming step 11 of 11.
- Plan Draft has a separate constraints box, and previews report Steps and
  Constraints separately, numbering constraints C1, C2 so they can never be
  read back as steps.

### Changed

- Constraints are bound into the plan digest, so an approval made for a plan
  that forbids external sources cannot be reused for the same plan with that
  sentence removed. Authorization, confirmation and execution start all rebuild
  the plan with its constraints through one shared metadata key.

### Compatibility

- A plan with no constraints encodes exactly as it did before they existed, byte
  for byte, and keeps its historical digest. The empty tuple is omitted rather
  than encoded, and a plan that has constraints declares a distinct canonical
  schema, so approvals and deferred grants made before this release still match
  the same plan re-authored today.

### Safety

- Constraints are never executable. They produce no step, receive no step ID,
  select no sources, spend no step, network or model budget, and reach no
  provider.
- Constraints grant nothing. Nothing reads their words and turns them into a
  capability; what a plan may do is still decided by its steps declared
  capabilities and the execution allowance.
- Which lines are steps and which are constraints is the author decision alone.
  No model and no keyword rule classifies them.
- The v0.3.284 failure-lesson trace still targets research steps only, so a
  constraint sharing wording with a prior lesson is never reported as step-N.

### Known limitation

- A constraint is an approved, displayed statement, not an enforced rule. This
  release separates the concepts and binds them into plan identity; it builds no
  constraint interpreter or policy engine, so a constraint saying "use NVD only"
  restricts nothing by itself.

## [0.3.284] - 2026-09-02

### Added

- Research-plan previews now explain which authored steps share meaningful
  wording with each displayed prior failure lesson, including the exact shared
  terms and stable step IDs.

### Safety

- The trace is deterministic, read-only and explicitly lexical. It does not
  claim that a lesson is addressed, score plan quality, change the authored
  plan or digest, authorize work, call a model, or start execution.
- A valid preview survives a trace that cannot be produced. The overlap is
  reported as unavailable rather than as an absence of overlap, so a failed
  computation is never read as a finding, and the preview itself is unaffected.

## [0.3.283] - 2026-09-02

### Added

- A valid authored research-plan preview now surfaces bounded, provenance-backed
  lessons remembered from similar prior questions before the operator confirms
  the plan.

### Safety

- Failure recall remains advisory and read-only. It cannot reject a valid plan,
  alter its steps or future digest, authorize capabilities, start execution, or
  turn a successful preview into a failure when recall is unavailable.

## [0.3.282] - 2026-09-02

### Added

- The trusted local desktop can schedule one exact queued task for one future
  attempt, up to seven days ahead. The durable record binds the exact active
  deferred-grant ID and is revalidated against live task, execution, plan,
  capabilities and allowance state when it fires.
- A single Tk wake-up is armed for the earliest pending record. It is cancelled
  and re-armed when durable state changes; there is no scheduler polling loop,
  recurrence, provider retry or startup worker cycle.

### Security

- A due schedule is durably claimed before research is attempted. A process
  crash after that claim cannot replay it on restart. A revoked/replaced grant,
  stale task, exhausted authority or busy desktop worker consumes the one-shot
  turn without falling back to another task or retrying.
- Scheduling and cancellation remain trusted-desktop control-plane actions,
  not Brain intents. They add no budget, capability, plan authorization or
  execution allowance, and cancellation changes only the pending schedule.

## [0.3.281] - 2026-09-02

### Added

- The trusted local desktop can record or revoke a durable deferred-execution
  grant for one exact queued research task. The record binds the task,
  execution, current plan digest, plan-derived capabilities and the task's
  outer bound; it is not a new research authorization or allowance.
- A pure deferred-eligibility decision checks that exact binding against live
  task, execution, plan and remaining allowance state. Manual and future
  deferred scheduler selection are now distinct modes, but no automatic cycle,
  timer, recurrence, polling or `run_at` exists.
- The desktop shows the exact binding before confirmation and states that the
  action adds no budget or capabilities and that no timer exists.

### Security

- Deferred grant and revocation are structurally absent from BrainRequest and
  CognitiveEngine intent dispatch. `source=desktop`, request metadata, task
  creation, Curiosity and the scheduler cannot mint trusted operator proof.
- Existing and legacy tasks with no separate grant remain manual-only after a
  restart. Revocation runs no research and changes neither task nor execution.
- `TRUSTED_LOCAL_OPERATOR` means confirmation through Hypatia's local desktop
  control plane. It is not cryptographic identity and does not defend against
  arbitrary malicious code already executing inside the Hypatia process.

## [0.3.280] - 2026-09-01

### Fixed

- Every canonical scheduler task transition is now serialized by one reentrant
  in-process lock. Create, pause, resume, cancel, worker selection, the RUNNING
  claim, the outcome commit, restore and the durable snapshot all take it. The
  service previously had no serialization at all, and was safe only because the
  desktop could make one call at a time.
- Selecting a runnable task and marking it RUNNING happen in a single lock
  acquisition. Split across two, both callers would come away holding their own
  PENDING snapshot, both would claim it, and both would run the same task.
- The whole-document task snapshot is taken under the lock. Building it from a
  dictionary another writer is mutating can drop a task or fail outright.

### Added

- A worker whose task moved on while it was running no longer writes its
  result. It re-reads the task, compares, and preserves the newer ruling.
- background_task.outcome_superseded reports that truthfully, so no completed,
  failed or retry event ever claims a transition that did not commit.

### Security

- The lock is never held across autonomy, a provider, the network or a model.
  Proven by calling back into the scheduler from inside a running task.
- A cancel landing mid-flight survives: the task stays CANCELLED, is not
  reopened, and the durable store agrees.
- A lock is not permission. Every BackgroundResearchTask transition rule is
  unchanged, pausing a RUNNING task is still refused, and terminal tasks stay
  terminal.
- Retry semantics are untouched: only budget exhaustion is retryable, and a
  failure is still never retried.
- Nothing wider was added - no file lock, no process-wide lock, no timer, no
  run_at, no recurrence, no startup run. Whole-runtime directory ownership
  continues to provide process-level exclusion.

### Known limitation

- A superseded worker result is dropped rather than kept. This milestone
  deliberately adds no second store to park an unwritten outcome in; the event
  records that it happened.

## [0.3.279] - 2026-09-01

### Fixed

- Scheduler task creation now binds only to an execution that exists and could
  still move. It previously accepted any identifier, so a durable task could be
  queued against nothing at all, sit PENDING looking ordinary, and only reveal
  itself when a cycle spent a slot discovering there was no such execution.

### Added

- A read-only `ReadsResearchExecution` port with one method. The scheduler can
  look an execution up; it still cannot advance, cancel, resolve, recover,
  authorize or touch a budget.
- `progress_block(state)` holds the part of autonomy's stop decision that
  depends on execution state alone. Autonomy now asks it too, so the rule the
  scheduler refuses on and the rule the cycle stops on cannot drift apart.

### Security

- Refusal happens before anything is written: no task, no store mutation, no
  authorization, no provider, no execution created, and no fallback to some
  other execution when the named one is absent.
- Executions that can never progress are refused - already finished, cancelled,
  failed, waiting on a human to resolve an interrupted or blocked step, or with
  no pending step left. Queueing them would record a task whose only possible
  outcome is to fail.
- Validation is read-only and takes no authority: the execution, its plan, its
  steps and its allowance are unchanged by a create, accepted or refused.
- Creation-time validation means "this was meaningful when queued", not "this
  will stay runnable". Nothing about execution state is copied into the task,
  and the worker cycle still decides against live canonical state.
- The desktop duplicates none of this. It reads no execution state and simply
  surfaces the scheduler's refusal.

### Known limitation

- The scheduler still serializes nothing internally. Queue mutations are safe
  only because the single-flight desktop worker cannot run a cycle and a
  mutation at once. This remains the prerequisite before any future-time or
  timer work, and no such work exists yet.

## [0.3.278] - 2026-09-01

### Added

- The background research task queue is now visible and operable. Creating,
  listing, pausing, resuming and cancelling all go through the five scheduler
  intents that already existed and already routed; the desktop builds no task
  record, keeps no queue of its own, and infers no status.
- A queued task's row names both the task and the execution it stands for, so
  the identifier a control needs is the one the operator can read.

### Security

- Queueing is not approving, and queueing is not running. Creating a task sends
  no budget and grants no authority: the scheduler's own default bounds one run,
  and what a task may spend stays the allowance the execution was already
  granted. Nothing here reaches a provider - only Run scheduler cycle does.
- Task identity and execution identity are kept in separate fields and separate
  controls. Cancelling a task stops the scheduler choosing it and leaves the
  execution exactly as it was; stopping that is still the separate execution
  control.
- Eligibility stays with the domain. The desktop predicts no refusal and hides
  none: an unknown task, or an illegal move on a terminal one, comes back as the
  scheduler's own refusal with no task state changed.
- Every queue mutation is confirmed first and every one is an ordinary request
  control, so none of them can run while a scheduler cycle holds the worker.

### Known limitation

- The scheduler serializes nothing internally. Queue mutations are safe here
  only because the single-flight worker cannot run a cycle and a mutation at the
  same time; a second caller outside the desktop would have no such protection.
- `process_create` does not check that the execution it names exists or is
  eligible. The desktop deliberately does not paper over this with a hidden
  check of its own.

## [0.3.277] - 2026-09-01

### Added

- A "Run scheduler cycle" control takes one turn of the existing background
  research scheduler, off the window's thread. The scheduler was already wired
  and durable with a worker cycle bounded to one task, but it is synchronous and
  demand-driven with no thread, timer or loop of its own, so without a caller it
  never turned. This is that caller and only that.

### Security

- One press is one cycle. Nothing schedules a second, nothing repeats, nothing
  runs at startup, and rebuilding the runtime restores the durable tasks without
  running any of them.
- No second scheduler was written. The desktop does not read the queue, choose a
  task, advance a step or invent a status; it reserves the one worker it already
  owns and hands the decision to the service that already makes it. The bound on
  a cycle is the scheduler's, and the desktop supplies no number of its own.
- The cycle grants nothing. No approval is created, no budget widened, no plan
  or capability changed, and the work still runs through the ordinary one-step
  advance under the approval's own allowance.
- An empty queue, a paused task and a cancelled task each perform no research at
  all and report so truthfully.
- Failure semantics are unchanged and untouched. Only running out of a run's own
  allotment returns a task to the queue; a failure, block, interruption or
  cancellation ends it, so no provider attempt is ever repeated.

## [0.3.276] - 2026-09-01

### Fixed

- Ownership now covers every directory the runtime writes canonical state into,
  not only the execution store. Sessions, memory, knowledge relations, research
  runs and the nine research stores kept beside them are all whole-file JSON
  stores with the same replace-the-document write, so a second process opening
  them loses records exactly as the execution store did.
- The claim is taken at the very start of `initialize()`, before a single store
  is opened. A second process is refused while it can still do no harm, rather
  than after it has loaded sessions and memory.

### Security

- The unit is the directory, because the files in one of these directories are
  written by one runtime as a set and are not independently shareable. Research
  keeps runs, executions, background tasks, curiosity questions, reflections,
  lessons, approvals, hypotheses and the vulnerability graph together, so one
  claim covers them.
- It is not one Hypatia per machine. Two runtimes on separate data directories
  both start, proven with real processes, and a test greps the ownership module
  to keep it from drifting toward a machine-wide claim.
- The mechanism is unchanged from v0.3.275: a kernel-held lock, released when the
  owning process ends however it ends, with a leftover lock file granting
  nothing. Killing an owner and then claiming the directory is proven.
- The execution store keeps its own claim as well, since callers can build it
  without going through `initialize()`. The two are separate lock files and
  neither waits on the other.
- A refused process writes nothing at all: no store, no fallback directory, no
  in-memory mode, and a message naming the directory without claiming corruption.

## [0.3.275] - 2026-09-01

### Fixed

- A writable research execution store now has one owning process. Two Hypatia
  processes pointed at the same store did not race over a field: each keeps its
  own picture in memory and each save replaces the whole document, so the later
  writer erased the other's executions outright. That was reproduced with two
  real processes, which is why the second one is now refused rather than warned.

### Security

- Ownership is an OS lock on a sidecar file, not the existence of that file. A
  file that merely existed would keep a dead owner's claim forever and leave
  somebody deleting it by hand after every crash; a kernel-held lock is released
  when the owning process ends, however it ends. Killing an owner outright and
  then claiming the store is proven in the tests.
- The claim is per store, never per machine. Two processes working on different
  stores are left alone, and within one process the same store may be claimed
  again so that rebuilding an application does not deadlock against itself.
- A refused process changes nothing: it does not touch the store, does not fall
  back to another file, in-memory mode or a copy, and says plainly that another
  Hypatia process owns the store without claiming corruption or interfering with
  the owner.
- No scheduler process was introduced. This makes sharing fail loudly; it does
  not make sharing safe, and the in-process guarantees from v0.3.274 are
  unchanged.

## [0.3.274] - 2026-09-01

### Fixed

- Every canonical execution transition now takes the same commit lock, closing
  the window v0.3.273 documented. Cancelling could previously land between the
  outcome commit's comparison and its write and be overwritten; the two can now
  only happen one after the other, and either order ends with the cancellation
  standing.
- Starting, cancelling, resolving, recovering, the pre-provider attempt commit
  and the post-provider outcome all commit under that lock, as do the rollbacks
  that undo a decision whose durable write failed — a rollback over somebody
  else's newer state was the same mistake in the other direction.
- A resolve or recover whose execution changed while the decision was being
  formed is now refused rather than forced over the newer state.
- An attempt superseded before it reaches a provider returns the charge it had
  just made, matching what the failed-checkpoint path already did: nothing was
  spent because nothing was tried. A superseded outcome *after* the provider ran
  still keeps its charge.

### Security

- The lock is never held across a provider call, and a test that deliberately
  holds it there deadlocks, which is how that guarantee is pinned.
- Two concurrent advances on one execution can no longer both reach a provider:
  the first commits its attempt, the second finds the execution is not what it
  planned from and stands down without calling anybody.
- Live and durable state agree after every contended transition tested.
- Cancel still spends nothing, refunds nothing already spent on a real attempt,
  creates no approval, and leaves the plan, digest and capabilities untouched.
- This is in-process serialization of a single owning service. It makes no claim
  about multiple processes sharing one store.

## [0.3.273] - 2026-09-01

### Fixed

- "Cancel execution" stays usable while a background continuation is running. It
  is now a control-plane action: every other desktop control is still disabled
  while the one worker is busy, because a second request would have nowhere to
  run, but a stop button that only appears once the work has stopped is not a
  stop button.
- The cancellation reaches the canonical service on the calling thread and
  returns without waiting for the in-flight provider, so the execution is
  CANCELLED both live and durably before the operation comes back. The returning
  provider cannot undo it, and no later step begins.

### Security

- The exemption is exactly one button wide. A second continuation, an advance,
  a start and an approval all remain blocked while the worker is busy, and the
  request runner itself was not touched or made concurrent.
- Cancel targets the execution named in the panel, never the running worker's.
  Cancelling a different identity leaves the running one alone, and a blank one
  refuses.
- Nothing about authority moves: no approval is created, the plan and its digest
  are untouched, and the in-flight attempt's spent budget stays spent.

### Known limitation

- One narrow window remains open. `process_cancel` does not take the commit lock
  that guards the attempt's outcome, so a cancellation landing between that
  comparison and its write is still overwritten. The window is two adjacent
  statements wide; a cancellation arriving at any other moment, including
  anywhere during the provider call, is preserved. The behaviour is recorded in
  `test_a_cancel_can_still_be_lost_in_the_commit_window` rather than left
  undocumented, and closing it means bringing every canonical writer under that
  lock. **Closed in v0.3.274.**

## [0.3.272] - 2026-09-01

### Fixed

- An attempt that finishes late can no longer undo what happened while it ran.
  `process_advance` read the execution before reaching the provider and wrote its
  outcome from that snapshot afterwards, so a cancellation landing mid-flight was
  silently overwritten: the operator was told they had cancelled, later steps ran
  anyway spending budget, and the durable record ended up saying completed.
- The outcome is now committed only if the execution is still the one the attempt
  started from. Execution states are immutable values, so equality answers that
  without a revision counter, and a newer state always wins — it was written by
  somebody who knew more at a later moment.

### Security

- The rule applies to every post-provider branch: success, structured provider
  failure, and blocking. Protection on the success path alone would have been no
  protection at all.
- Memory and the durable record cannot disagree. A superseded outcome persists
  the state that actually stands rather than the one the attempt was building.
- Attempt accounting is untouched. The charge was made for reaching out, reaching
  out happened, and a concurrent decision elsewhere does not refund it; the
  allowance is never reset by stale-write detection.
- The operation's having returned is still reported, as an event naming the
  status that stands rather than implying a transition nobody committed.
- The lock is held only around the compare-and-set, never across a provider call.

## [0.3.271] - 2026-09-01

### Added

- A "Continue in background" control runs the existing bounded continuation off
  the window's thread, so the desktop stays usable while steps run. It names the
  exact execution and an explicit finite bound, and asks first.

### Security

- Background here means off the Tk thread, not unattended. Nothing was scheduled,
  nothing recurs, and nothing relaunches after a restart; closing Hypatia stops
  the run while the execution stays durable and resumable.
- No second executor was written. The steps are the existing `process_continue`
  loop over the existing one-step advance, so the budget checks, the durable
  attempt checkpoint, the structured refusals and the stopping rules are the
  ones an ordinary press gets.
- The worker is the single-flight desktop runner the window already owned, which
  is also the guard against two clicks racing over one execution: the second is
  told Hypatia is busy rather than starting a second run.
- The run spends only the budget this execution was already granted. No approval
  is created, no capability widens, no plan or digest changes, no budget is reset
  or topped up, and nothing is retried.
- The confirmation states each of those plainly, and says the run stops on
  failure, blocking, interruption, cancellation or budget exhaustion.

## [0.3.270] - 2026-09-01

### Fixed

- Confirming an operator-authored approval now binds the budget as it stands at
  confirmation, not the one Preview happened to freeze. A number changed after
  previewing is the number recorded, with no second Preview required, which
  removes the last asymmetry with the Curiosity flow.
- The confirmation dialog shows those current values and no longer warns that
  later edits are excluded, because they no longer are.

### Changed

- Preview still settles the plan, and only the plan. The approval is built by
  replacing one field on the previewed record, which cannot reach the digest or
  the capabilities, so no amount of budget editing turns one approved plan into
  another. A refused budget leaves the preview standing, since the plan was
  never the problem.

### Security

- A current budget that is unusable or too small is refused, never substituted.
  Not by the previewed figure that happened to parse, not by the default unless
  the field is genuinely blank, and not by what the plan turns out to need.
- Confirming reaches no provider, no network and no model, spends no budget and
  starts nothing; declining the dialog records nothing.
- The Curiosity flow is unchanged, and remains the reference behaviour this
  milestone brought the other surface up to.

## [0.3.269] - 2026-09-01

### Fixed

- Approving a Curiosity proposal now re-reads the budget boxes at the moment of
  approving and recomputes the fit against that exact proposal. Values edited
  after Prepare are the ones described and the ones recorded, so nobody has to
  press Prepare again to be safe. Currently unusable or insufficient values
  refuse before any dialog opens, naming what is short.
- Confirming an operator-authored approval now shows its terms first. That path
  records the approval object Preview built, budget included, so the dialog shows
  that budget and says plainly that edits made since Preview are not part of it
  and need another Preview. Showing the current boxes there would have described
  a grant that is not the one recorded.

### Added

- Both approval surfaces render the authority through one shared helper, so the
  two cannot drift into describing the same grant differently, and the budget
  fit now travels on the response as structured state rather than only as text.

### Security

- A stale proposal is refused rather than moved to: the re-read proposal's digest
  must equal the one on screen, or nothing is approved.
- Re-reading a proposal to check its fit reaches no provider, no network and no
  model, records nothing, and runs no research step. Declining either dialog
  records nothing, and starting work remains a separate action.
- Seconds are still shown as granted authority only; no required duration is
  invented. No reactive machinery was added — the recomputation happens when a
  button is pressed.

## [0.3.268] - 2026-09-01

### Added

- The Curiosity approval surface now offers the same three budget controls the
  operator-authored panel has: step advances, network operations and seconds. A
  blank field grants the standing default.
- Preparing a Curiosity proposal now shows what the plan would need beside what
  is about to be granted, with the fit and any shortfall, before anybody
  approves. Preparing still reaches no provider, source or model.
- The confirmation says plainly that this is the authority being granted to a
  plan Hypatia proposed, and that Hypatia did not choose it for itself.

### Changed

- A budget too small for a Curiosity plan is now refused in the same shape as
  every other refusal there, rather than as an exception the caller had to know
  to expect.

### Security

- No second budget model was introduced. The Curiosity path reuses the one
  parser, the one requirement derivation, the one fit comparison and the
  existing `MAX_AUTONOMY_*` ceilings, and a test pins that only one module
  defines each.
- Model operations remain ungrantable on this surface too, because no registered
  capability can spend them.
- The refusals are the same ones: unreadable input refuses instead of falling
  back to a default, blank means "leave this bound alone" rather than zero, and
  negatives, fractions, infinities and above-ceiling values are all refused.
- What was typed is persisted exactly — not the default, and not the plan's
  requirement. Choosing changes no plan, no digest, no capability, and runs
  nothing.

## [0.3.267] - 2026-09-01

### Added

- The operator now chooses the budget an approval grants, rather than receiving
  a constant. Step advances, network operations and seconds can each be set at
  the authorization boundary; a field left blank keeps the standing default.
- The desktop states plainly that these are the authority being granted rather
  than what Hypatia decided it may use, and the preview shows what the plan needs
  beside what is being granted.

### Security

- Model operations are deliberately not offered. No registered capability
  declares a cost there, so a control for it would grant authority nothing can
  spend.
- Unreadable input refuses the approval instead of falling back to a default.
  The permissive direction is the dangerous one, and a value nobody typed must
  never become authority.
- Blank means "leave this bound alone" and never zero, while an explicit zero is
  accepted as the real and very tight answer it is.
- Refused by name: negatives, fractions, floats where a count belongs, booleans
  Python would read as one, infinities, not-a-number, None, and anything above
  the hard ceilings `ResearchAutonomyBudget` already enforces.
- The chosen budget is persisted exactly. It is not replaced by the default, and
  pointedly not by the plan's requirement; a different budget is a different
  approval record rather than an edit to an existing one.
- An insufficient grant is still refused, whoever chose it. Selecting a budget
  changes no plan, no capability and no execution, and performs no research.

## [0.3.266] - 2026-09-01

### Added

- A plan's nominal cost is now derived and shown before anybody approves it.
  It is the cost of attempting each authored step exactly once, summed from the
  same registry the executor charges against, compared dimension by dimension to
  the budget on offer: advances, network operations and model operations.
- The approval preview renders required beside approved, along with the fit and
  any shortfall, for a refused preview as well as a ready one.

### Security

- An approval whose budget cannot cover one clean pass of the plan is now
  refused rather than granted optimistically. The refusal records no
  authorization, reaches no provider, starts no execution and spends nothing.
- Knowing what a plan needs never becomes permission to have it. The requirement
  is calculated, displayed and compared, and at no point raises the budget to fit
  the plan; an insufficient plan is refused, not funded.
- The figure is a floor rather than a forecast, and says so. It counts no
  retries, no preparation, no approval, no start, and no human-only decision,
  because none of those are authored steps that execute.

## [0.3.265] - 2026-09-01

### Fixed

- Source reputation now combines active trust assessments across all equivalent
  records of one canonical resource before counting the resource once. A
  high-trust record encountered first can no longer hide an active low-trust
  assessment attached to an equivalent record.
- Reputation derivation is now invariant to research-run input order. Accepted,
  evidence, and run counts remain storage facts, while the single assessed
  resource sample uses the least-trusting active authored label.

### Security

- The correction is local, deterministic, derived, and advisory-only. It changes
  no source, assessment, evidence, claim, confidence, reputation store, provider
  choice, or research execution.

## [0.3.264] - 2026-09-01

### Fixed

- Assessment-aware claim warnings now group equivalent accepted document
  records by the same canonical resource identity used by support calibration.
  Accepting one page twice can no longer duplicate a warning or inflate warning
  telemetry for one underlying source concern.
- The grouped warning retains every claim-linked evidence ID for the resource
  and names the exact newest active assessment carrying that warning kind.

### Security

- The correction is derived, deterministic, and read-only. It changes no
  source, assessment, evidence, claim, confidence, provider choice, research
  operation, or persisted run state.

## [0.3.263] - 2026-09-01

### Fixed

- Hypothesis History now collapses an operator-authored evidence note to one
  display line before applying its 80-character bound. A line break in a note
  can no longer resemble another relation, standing, or withdrawal entry.
- The final history renderer applies the same boundary even when a view is
  constructed directly rather than through the normal builder.

### Security

- The normalized, bounded note is stored only in the derived read model; the
  canonical evidence record and hypothesis remain unchanged.
- The change performs no model call, network request, research operation,
  evidence mutation, retry, or background action.

## [0.3.262] - 2026-09-01

### Fixed

- Hypothesis appraisals now normalize the authored hypothesis statement and
  discriminating test to one bounded display line before adding their labels.
  Embedded line breaks can no longer manufacture a forged-looking `Status:` or
  `Supporting:` line in a proposal or later appraisal response.
- The canonical hypothesis keeps its admitted authored wording unchanged;
  normalization is confined to the read-only appraisal view.

### Security

- The existing statement and discriminating-test length limits remain the hard
  display bounds, and the shared one-line normalizer handles all whitespace.
- The change is deterministic and local and performs no model call, network
  request, research operation, evidence mutation, or background action.

## [0.3.261] - 2026-09-01

### Fixed

- Reflection now normalizes a finding to its one-line display form before
  applying the 300-character detail bound. Repeated whitespace can no longer
  consume the bound and hide useful wording that would fit visibly.
- A genuinely overlong visible detail ends with `...`, making the bounded
  omission explicit instead of silently cutting text.

### Security

- Bounding still happens before a finding enters a report, and the shared
  finding record continues to enforce one-line storage and the hard maximum.
- The change is deterministic and local and performs no model call, network
  request, research operation, retry, write to Failure Memory, or background
  action.

## [0.3.260] - 2026-09-01

### Fixed

- Reflection finding details now collapse embedded line breaks and other
  whitespace before they enter a report. One recorded failure therefore remains
  one visible finding instead of being able to resemble extra list entries.
- The guarantee lives on the shared reflection-finding record, so preview,
  durable storage, reload, and future renderers inherit the same boundary.

### Security

- Authored or persisted failure text cannot inject a forged-looking reflection
  label such as `[worked]` onto a new line. The original bounded wording remains
  visible as one normalized line rather than being silently discarded.
- The change is deterministic and local. It starts no research, model call,
  network request, retry, Failure Memory write, or background action.

## [0.3.259] - 2026-09-01

### Fixed

- Reflection now preserves a recorded provider on research failures instead of
  reducing every failure to its stage. Provider-attributed discovery failures
  therefore remain distinguishable in the report.
- Legacy failures without provider provenance remain under their recorded stage
  and are not attributed by execution order, error text, or any other guess.

### Security

- Provider text comes only from the canonical bounded failure record. Reflection
  does not infer provenance or treat the provider as instruction authority.
- The change remains deterministic and read-only and starts no research, model
  call, network request, retry, Failure Memory write, or background action.

## [0.3.258] - 2026-09-01

### Fixed

- Reflection now matches accepted sources back to discovery candidates through
  the shared canonical resource identity instead of comparing raw URL text.
- Equivalent HTTPS URLs that differ only by host case, `www.`, the default
  `:443` port, a trailing slash, or a fragment no longer make accepted work look
  unused. Mixed discovery results count only the genuinely unaccepted
  candidates.

### Security

- Canonical matching is conservative and reuses the existing `identity_of`
  policy; query strings and case-sensitive paths remain distinct resources.
- The change is bounded, deterministic, and read-only. It performs no fetch,
  model call, research operation, source acceptance, Failure Memory write, or
  background action.

## [0.3.257] - 2026-09-01

### Fixed

- Reflection now describes a superseding claim from the canonical dimensions
  that actually changed: epistemic state, authored confidence, linked sources,
  linked evidence, or authored wording.
- A confidence-only or provenance-only correction no longer implies that the
  claim's epistemic state changed. Wording-only and identical replacements are
  reported without inventing a belief change.

### Security

- Claim-revision reporting remains bounded, deterministic, read-only, and
  truth-neutral. It changes no claim, confidence, evidence, source, hypothesis,
  assessment, or research run.
- The corrected reflection path performs no model call, network request,
  research operation, Failure Memory write, authorization, or background work.

## [0.3.256] - 2026-09-01

### Fixed

- Reflection now describes a superseding source assessment from the dimensions
  that actually changed: information trust, usefulness, applicability,
  independence, publication status, or linked evidence.
- An independence-only correction no longer says source trust changed. A
  wording-only supersession is reported as authored wording with no structured
  judgement change, and parallel assessments remain parallel rather than being
  presented as revisions.

### Security

- Reflection still reads only canonical persisted records and emits bounded,
  deterministic process observations. It assigns no winner or truth value and
  edits no assessment, evidence, claim, hypothesis, confidence, or run.
- The corrected reporting path performs no model call, network request,
  research operation, automatic Failure Memory write, or background action.

## [0.3.255] - 2026-09-01

### Changed

- A timed hypothesis support relation can now remember an explicitly
  superseding source-assessment correction when information trust changed, as
  well as when independence changed.
- A single assessment revision that changes trust and independence together
  produces one `invalid_assumption` lesson with one stable identity and the
  same hypothesis, evidence, source, and two-assessment provenance chain.

### Security

- The sequence requirement is unchanged: the supporting relation must carry a
  recorded authoring time no later than the linked correction. Parallel
  assessments, unchanged supersessions, unrelated sources, later support,
  withdrawn hypotheses, and legacy untimed support produce no lesson.
- Trust labels are reported as operator-authored corrections, not converted to
  truth or instructions. Learning remains behind the explicit Failure Memory
  command and performs no event-driven write, model call, research operation,
  network request, claim edit, or hypothesis status change.

## [0.3.254] - 2026-09-01

### Added

- The explicit `failure_memory_hypothesis_store` command can now remember one
  `invalid_assumption` lesson when a timed, currently standing supporting-
  evidence relation lived through an explicitly superseding assessment that
  changed the same source's independence judgement.
- The lesson carries the hypothesis, evidence, source document, earlier
  assessment, and correcting assessment identifiers as provenance. Repeating
  the command keeps the same stable lesson rather than adding a duplicate.

### Security

- Missing or unknown independence is not a failure. Parallel assessments,
  wording-only supersessions, unrelated sources, support authored only after a
  correction, withdrawn hypotheses, and legacy support with no recorded
  authoring time produce no hypothesis-specific correction lesson.
- A provenance-only projector establishes the checkable record sequence before
  Failure Memory composes advisory text. It neither changes hypothesis status
  nor treats either independence label as true, and no event, background task,
  model call, research operation, or network request triggers this learning.

## [0.3.253] - 2026-09-01

### Changed

- Reflection now reads the selected run's durable hypotheses through the
  existing hypothesis-store boundary and passes them to the shared knowledge-gap
  detector and Curiosity question generator.
- An unanswered discriminating test or multi-source hypothesis support whose
  independence is not confirmed is shown as weak evidence, with the same
  deterministic next question Curiosity would surface.

### Security

- Reflection remains local, deterministic, read-only, and truth-neutral. It
  neither writes hypotheses nor changes their status, evidence, confidence, or
  source assessments, and it starts no research, model call, or network request.
- Only hypotheses belonging to the selected run are composed into a report. A
  missing or unreadable hypothesis store preserves the run-side reflection
  rather than exposing a storage error or inventing hypothesis state.

## [0.3.252] - 2026-09-01

### Added

- Curiosity now reports a dedicated knowledge gap when a hypothesis carries
  supporting evidence from several canonical sources but the active record
  does not confirm that every supporting source is independent.
- The gap produces one deterministic question asking for independent
  corroboration and can be prepared through the existing inert Curiosity plan
  path while preserving the hypothesis and discriminating-test provenance.

### Security

- Detection reuses `ResearchHypothesisAppraiser` resource identity,
  active-assessment, and fail-closed independence rules; it does not maintain a
  competing corroboration calculation.
- Unknown, derivative, likely-duplicate, or conflicting independence
  judgements keep the gap open. Detection and proposal preview remain local,
  deterministic, read-only, truth-neutral, and incapable of starting research.

## [0.3.251] - 2026-09-01

### Changed

- Failure Memory now derives an `invalid_assumption` lesson when an explicitly
  superseding source assessment changes the source's independence judgement,
  just as it already did for an information-trust correction.
- A supersession that changes trust and independence together produces one
  provenance-backed assessment lesson naming both changes. Each direction of
  an independence correction is retained without treating either value as a
  claim about truth.

### Security

- Parallel assessments remain parallel and do not fabricate a revision;
  wording-only or unrelated structured changes produce no new lesson.
- Derivation stays local, deterministic, explicit-command-only, advisory, and
  read-only. It does not call a model, open a network connection, change an
  assessment, block research, or alter claim support.

## [0.3.250] - 2026-09-01

### Added

- Curiosity now reports a dedicated knowledge gap when a settled claim has
  several distinct sources but the active record does not confirm that every
  corroborating resource is independent.
- The gap produces one deterministic question asking for independent
  corroboration, appears as weak evidence in Reflection, and can be previewed
  through the existing inert Curiosity proposal path.

### Security

- Gap detection reuses Claim Calibration's canonical resource identity,
  active-assessment, and fail-closed independence rules instead of maintaining
  a second corroboration calculation.
- Unknown, derivative, likely-duplicate, or conflicting active independence
  judgements keep the gap open. An explicit superseding correction can close
  it; detection remains local, read-only, deterministic, and truth-neutral.

## [0.3.249] - 2026-09-01

### Changed

- Hypothesis appraisal now requires every corroborating supporting resource to
  carry an explicit active `independent` judgement before the derived status can
  become `supported`.
- Appraisals expose separate independence-coverage counts for supporting and
  opposing evidence alongside the existing trust coverage.
- Unknown, derivative, likely-duplicate, or conflicting active independence
  judgements keep positive support `open`; an explicitly superseding correction
  replaces its predecessor as before.

### Security

- Distinct URLs can no longer make a hypothesis appear supported when the
  record does not establish that they are independent witnesses.
- Appraisal remains deterministic, local, derived, and truth-neutral. It does
  not call a model, open a network connection, edit evidence, rewrite a
  hypothesis, or introduce any status meaning proven or true.

## [0.3.248] - 2026-09-01

### Changed

- Claim calibration now requires every corroborating resource to carry an
  explicit active `independent` judgement before the evidence structure can
  support `strong evidence / high confidence`.
- The calibration profile and report expose the number of resources whose
  independence is confirmed, separately from distinct and assessed counts.
- Unknown, derivative, likely-duplicate, or conflicting active independence
  judgements cap support at `likely / medium`; they never rewrite the authored
  claim or delete any provenance.

### Security

- Distinct URLs can no longer inflate a claim's support ceiling when the record
  does not establish that they are independent witnesses.
- Independence remains deterministic, local, read-only, and operator-authored.
  No model, network request, score, automatic claim revision, source rejection,
  or evidence mutation is introduced.

## [0.3.247] - 2026-09-01

### Changed

- An accepted Curiosity question now produces a local-first research proposal:
  its first step searches existing local knowledge using the exact canonical
  question, and only later steps discover outside source candidates.
- The local search consumes no network or model budget. Each outward discovery
  remains a separate, explicitly advanced, budgeted provider attempt.
- Restart, failure, interruption, human resolution, and recovery records now
  preserve the two-stage plan truthfully without replaying completed local work
  or attributing provider outcomes to the local step.

### Security

- Proposal preview remains inert, authorization is still bound to the exact
  content-addressed plan digest, starting remains zero-step, and each explicit
  Advance performs at most one authored step.
- The plan still stops at source discovery. It does not fetch or accept a
  source, create evidence, judge a claim, call a model, schedule background
  work, or retry a failed or interrupted provider attempt.

## [0.3.246] - 2026-09-01

### Changed

- Local loopback chat-completion endpoints such as Ollama now receive a
  300-second default request timeout, allowing slower long-form generation to
  finish on modest local hardware. The non-local default remains 30 seconds.
- A positive finite `HYPATIA_LLM_TIMEOUT_SECONDS` value still overrides either
  endpoint default, so operators retain explicit control over the request
  boundary.

### Security

- The change widens only the duration of an already authorized local
  chat-completion request. Endpoint validation, redirect rejection, keyless
  loopback-only policy, response parsing, model selection, and provider
  architecture are unchanged.

## [0.3.245] - 2026-08-31

### Added

- An operator can ask for a bounded foreground continuation: run at most N
  research steps, where N is explicit and at most ten. It is a loop around the
  existing one-step advance and nothing else, so every budget check, capability
  check, durable attempt checkpoint and refusal is the one a single press gets.
- The result is structured rather than prose: execution identity, steps
  requested, steps attempted and their IDs in order, final status, a bounded
  stop reason, the next pending step and the remaining allowance.
- The desktop offers a typed step count and a "Continue bounded" control beside
  the existing Advance and Cancel, with a confirmation naming the bound and what
  ends the run early.

### Security

- A bound is a maximum, never a target, and a missing bound is refused rather
  than read as unlimited. Zero, negative, malformed and above-maximum are all
  refused before anything runs.
- It stops at the first problem and never steps over one. Completion, failure,
  blocking, interruption, cancellation, an unaffordable next step or any
  ordinary advance refusal ends the run where it stands.
- Nothing is retried and nothing is repaired. A failed or interrupted step ends
  the run; resolving or abandoning it remains an explicit human decision made
  afterwards.
- No budget is pre-charged, reserved or refunded in aggregate. Each step is
  charged by the ordinary one-step path, which decides affordability before its
  own attempt, and no capability is widened because more steps were requested.
- Each step keeps its own durable attempt checkpoint, so a crash mid-run leaves
  exactly the state a crash during a single advance would.

## [0.3.244] - 2026-08-31

### Added

- An operator can act on a step blocked as performed-with-unknown-result, in
  exactly two explicit ways: supply what they found by hand, or abandon the step.
  Both are recorded as a small bounded recovery on the step, carrying the
  decision, the moment, the human author, the operator's own account and the
  operation they claim produced it.
- The desktop offers both actions with confirmations that state the operation may
  have run, that the attempt is already charged, that anything supplied is the
  operator's account rather than a provider result, and that supplying it does
  not complete the step. There is no retry control.

### Security

- Human-supplied information never acquires provider provenance. It is a
  deliberately separate record rather than a `ResearchEvidenceRecord`, which is
  anchored to an accepted source document and would have lent it authority it
  does not have. The claimed operation is kept apart from the content and is
  never matched against the operation registry or written onto the step.
- Supplying a recovered result does not complete the step. Completion means
  Hypatia ran an operation and saw what came back, so the step stays blocked and
  carries the account alongside the attempt.
- Abandoning cancels the step, which claims neither success nor failure. The
  performed attempt, its operation and its ruling all remain observable, so the
  record still shows something may have happened.
- Neither decision reaches a provider, retries anything, advances anything,
  creates an approval, or moves any budget; the interrupted attempt stays spent.
  Nothing in the request can carry a capability, an approval or a budget.

## [0.3.243] - 2026-08-31

### Added

- An operator can explicitly resolve an interrupted attempt. Three bounded
  rulings are offered and no fourth: the operation ran but its result is
  unknown, the operation never ran, or it is still unknown. The ruling, who made
  it and when are canonical persisted state on the step, not wording, so they
  survive a restart.
- A running step now records the operation it called, so an interrupted record
  names the provider that may have run. Naming it asserts no work; the performed
  flag stays false until something is actually known.
- The execution status reports any operator ruling, and the desktop offers the
  smallest surface for making one: the interrupted step, the ruling, and a
  confirmation stating that the operation may have occurred, that its result is
  unknown, and that the attempt has already been charged.

### Security

- No ruling invents a provider result. "It ran" blocks the step with the work
  acknowledged rather than completing it, because completing would assert a
  result nobody has; "it never ran" returns the step to pending so a later,
  explicit advance is an ordinary new attempt at the ordinary price; "still
  unknown" changes no status and keeps ordinary Advance refused.
- Only an explicit human action resolves an attempt. Nothing is inferred from
  the provider, from failure memory, or from a restart, and an empty or
  unrecognised ruling is refused.
- Resolution reaches no provider, retries nothing, advances nothing, creates no
  approval, and charges no budget. The interrupted attempt stays spent, and a
  ruling that could not be persisted is not kept.

## [0.3.242] - 2026-08-31

### Fixed

- A step attempt is now durable before it can become observable. The step is
  marked running and the attempt is charged, and that state is written to the
  execution store, before any provider operation is invoked. Previously nothing
  was persisted between starting a step and recording its result, so a process
  that died mid-attempt left the step pending and unspent even though the
  operation may already have been performed.
- If the pre-attempt write does not land, the advance refuses and no operation
  runs. An attempt whose having happened could not be recorded is not one worth
  making.

### Security

- A crash never refunds and never erases evidence. The persisted record after a
  mid-attempt crash shows the step charged and running, which restores as
  INTERRUPTED with the execution INTERRUPTED alongside it.
- An interrupted outcome stays unknown. It is not recorded as completed, failed,
  or untried, nothing retries it, and an ordinary advance refuses the whole
  execution with an explicit reason rather than silently running the step again.
- Explicit resume already supported interrupted executions and still performs no
  operation, creates no approval, and neither refunds nor re-charges the attempt.
- The execution status now states plainly that an attempt was interrupted, that
  its outcome is unknown, that it was already charged, and that advancing will
  not run it again.

## [0.3.241] - 2026-08-31

### Added

- A durable research execution can be resumed after a restart. An execution that
  was proposed, approved, explicitly started and perhaps advanced is recovered by
  an operator naming it exactly, through a new "Resume after restart" control.
  Resuming performs no research: advancing remains a separate, explicit press,
  and one advance after a restart still means at most one step.
- The approval that permitted an execution is located by the execution identity
  its consumption recorded, so the plan rebuilt at resume time can be checked
  against the digest that was actually approved.

### Security

- Restarting creates no authority. No approval is created or un-spent by
  resuming; the consumed approval stays consumed, the persisted allowance is
  restored exactly with no refund, recorded step states are restored as recorded
  so finished work is never repeated, and cancelled or completed executions stay
  closed.
- Resume refuses rather than repairs. A missing durable record, a missing
  allowance, a plan that no longer matches the approved digest, steps that do not
  match the record, or a capability with no operation registered in this process
  each end in refusal, because an execution that had to be guessed at is not the
  one anybody approved.
- Restoration judges nothing new. The gap-currency check that gates proposing
  research is deliberately not applied when recovering work that was already
  approved and begun, so a closed gap cannot silently revoke an approval the
  operator already spent. Ending such an execution stays the operator's decision,
  made by cancelling.

## [0.3.240] - 2026-08-31

### Added

- A started Curiosity execution can now be advanced one step. Start records the
  execution's own identity in the operator's execution field, so the existing
  "Advance one step" and "Cancel execution" controls act on exactly what was
  started rather than on whatever was last typed. A refusal clears the field,
  because a stale identity there would point the next advance at an earlier
  execution.
- No execution semantics changed. The ordinary one-step advance already
  attempted exactly one step in authored order, checked the allowance before the
  attempt, charged it at the attempt boundary, recorded failures structurally and
  refused once cancelled. This milestone only connects the Curiosity-origin
  execution to it.

### Security

- One operator action remains at most one step attempt. A single advance never
  reaches the next step, never retries a refused provider, and never becomes a
  loop; a finished plan is refused rather than restarted.
- The step runs under the capability and budget the approval already carried. An
  exhausted allowance is refused before the provider is reached, so nothing is
  contacted and nothing is charged, and a cancelled execution performs no
  operation at all.
- Restored executions stay readable and not advanceable. Rebinding plan,
  context, allowance and consumption provenance durably is its own milestone, so
  the limitation is pinned by a test rather than quietly removed.

## [0.3.239] - 2026-08-31

### Added

- The Review surface can now prepare one exact current claim for a person's
  attention. The operator names both the research run and claim; Hypatia
  re-derives current calibration and shows the authored statement, verdict,
  support ceiling, warnings, and current evidence/source provenance together.
- The preparation exposes the exact existing claim ID that a separately
  authored replacement could supersede. It also shows the current evidence and
  source IDs for inspection, without treating either set as an automatic choice
  for a future claim.
- Preparation is available for an overextended or contradicted claim, and for a
  claim whose source assessments carry a warning even when its authored state
  remains within the structural support ceiling.

### Security

- Preparation is derived and inert. It drafts and records no replacement,
  chooses no epistemic state or confidence, changes no claim or provenance, and
  creates no plan, authorization, execution, provider request, network access,
  tool call, model call, Ollama call, or background work.
- Superseded and unknown claims are refused. Claims with neither a calibration
  mismatch nor an assessment-aware warning are also refused, so calibration
  cannot nudge a careful or supported claim toward a stronger assertion.
- The preparation event contains only the run ID, bounded verdict, warning
  count, and explicit zero-change flags. Claim text, claim/evidence/source IDs,
  questions, URLs, and assessment prose remain outside telemetry.

## [0.3.238] - 2026-08-31

### Added

- Claim calibration now identifies every active claim by both its durable ID
  and its exact authored text, so an operator can understand which statement a
  verdict concerns without cross-referencing a separate claim-history view.
- Each calibration carries and renders the exact evidence IDs and source
  document IDs already attached to the authored claim. Counts still describe
  the support profile, while the added identifiers make that profile auditable
  against canonical run state.

### Security

- Calibration remains derived and read-only. The added provenance creates no
  claim revision, confidence adjustment, source decision, plan, authorization,
  execution, provider request, network operation, tool call, model call, or
  background work.
- Claim text and provenance are shown only in the operator-facing response.
  Calibration telemetry remains bounded to run ID, counts, verdict categories,
  and warning kinds; it still carries no claim text, evidence ID, source ID,
  question, URL, or assessment content.

## [0.3.237] - 2026-08-31

### Added

- An operator can now start one exact, already-authorized Curiosity research
  proposal through a separate "Start authorized proposal" action. The request
  names the accepted question, the displayed plan digest, and the durable
  approval ID; no plan content or "latest approval" shortcut is accepted.
- Start re-derives the proposal from current canonical run state, repeats the
  staleness and digest checks, and then delegates to the ordinary foreground
  execution service. The existing approval consumer verifies and spends the
  exact human approval, and the existing execution store records the resulting
  state.
- The desktop keeps the returned approval ID in a read-only field and confirms
  the irreversible consumption before sending one start request. The result
  names the approval, execution, zero completed steps, and the separate action
  required before any actual research can occur.

### Security

- Start preserves the canonical zero-step boundary: execution becomes
  `RUNNING`, every authored step remains `PENDING`, and no provider, source,
  network operation, tool, model, Ollama call, or background task is reached.
  The first operation still requires a separate explicit Advance action.
- A malformed or changed digest, stale gap, unknown/expired/consumed approval,
  unavailable execution boundary, duplicate execution, or capacity refusal
  creates no new execution. Checks that can refuse run before approval
  consumption, and a successful approval is single-use.
- Curiosity receives only a narrow start port. It has no advance method and no
  operation registry, so this connection cannot silently turn a start into an
  executed research step.

## [0.3.236] - 2026-08-31

### Added

- A previewed curiosity proposal can now be approved by a person, and the
  approval binds to the exact plan digest they were shown. This crosses the
  authorization boundary once, deliberately, and stops before anything runs.
- The operator supplies two things — which question, and the digest from the
  preview — and neither is trusted as content. The proposal is derived again
  from current canonical state by the same code that produced the preview, and
  the digest they name has to equal the one that derivation produces. A request
  carrying plan content cannot widen what is approved: the capabilities recorded
  come from the re-derived plan.
- That one comparison catches every way the plan could have moved underneath
  them — a gap that closed, a hypothesis that gained evidence, a provider since
  asked — and each is refused with a bounded message rather than quietly
  approving the newer plan.
- Approvals are the ordinary `ResearchPlanAuthorization`, built by the same
  constructor, stored in the same store, and announced on the same event. No
  curiosity-specific approval record exists.
- The desktop Review surface gains a read-only plan digest field, captured from
  the canonical response rather than parsed from rendered text, and one
  "Authorize this proposal" control behind the established confirmation dialog,
  which names the digest being approved.

### Security

- An approval is permission, not a start. Nothing is consumed on creation, no
  execution exists, and beginning the work remains a separate action this
  milestone does not provide. No execution control was added.
- Approving reaches no provider, loads no source, runs no tool, and calls no
  model. The curiosity service holds no execution or provider port to reach
  with, and cannot write a hypothesis.
- A question dismissed while undecided cannot be approved through an older
  preview, and an approval names the human authorizer the existing architecture
  already records. Curiosity does not authorize anything; a person does.

## [0.3.235] - 2026-08-31

### Added

- An accepted curiosity question can be turned into a research proposal an
  operator can read. Curiosity could notice a gap and propose a question, and a
  person could keep it; there it stopped. This adds the next step and stops
  again.
- The proposal is an ordinary research plan — the same model an approved plan
  uses, drafted by the same service, carrying the same content digest — plus the
  curiosity provenance explaining why it is being shown. No second planning
  system exists, and no second digest scheme was invented.
- Two operator decisions stay separate. Accepting a question says it is worth
  keeping and remains entirely inert; preparing a proposal is a second explicit
  action naming one exact question by identifier. There is no "latest accepted"
  shortcut, and an ineligible question is refused rather than quietly accepted.
- The gap is re-derived from current state at preview time rather than trusted
  from the stored question. An accepted question outlives the situation that
  produced it, so a gap somebody has since closed — by recording the very
  evidence it was about — refuses the proposal instead of drafting work nobody
  needs.
- Provenance is carried, never reconstructed: the question, its gap, the run,
  and for a hypothesis gap the hypothesis and the discriminating test it named.
  Nothing is inferred from the wording of anything.
- The desktop Review surface gains one read-only "Prepare research proposal"
  control beside the existing keep and dismiss actions.

### Security

- A proposal holds no permission. `authorized` and `started` are properties that
  return False and cannot be set, because a proposal able to describe itself as
  authorized would be one keystroke from being believed. Execution still
  requires a separate human authorization against the plan's digest, which this
  preview neither creates, requests, nor implies.
- Preparing a proposal contacts no provider, loads no source, runs no tool,
  calls no model, and advances no plan. The steps describe future discovery and
  perform none of it, and the service holds nothing it could reach with.
- A failed acquisition does not become a proposal to try again, and a hypothesis
  gap does not become a proposal to run the discriminating test. The first
  proposes finding another source; the second proposes finding evidence someone
  could judge. Neither claims the hypothesis is true, false, or exploitable.

## [0.3.234] - 2026-08-31

### Fixed

- A guard asserting that the provider comparison request reaches no provider
  collected only attribute calls, so a bare-name reference to `open` could sit
  in the module while the test passed. Proven by mutation before and after: the
  same insertion passed the old guard and fails the repaired one, which now
  collects bare names alongside attribute calls. It was the difference between
  checking that nothing is reached and checking that nothing is reached through
  an attribute.

### Tests

- The two guard helpers are now tested directly, since several dozen invariant
  guards are only as good as what they collect. `module_vocabulary` is pinned on
  collecting bare identifiers, attribute names, imports, definitions, keywords
  and string constants while excluding docstrings, and on never being silently
  empty for real code. Attribute collection is asserted explicitly because a
  guard saying a module never reads a field is worthless against
  `object.field` if the collector only sees bare names.
- The v0.3.233 vacuity is pinned rather than quietly patched:
  `working_vocabulary` with no function names still collects nothing, which is
  the honest answer to a question nobody asked, and a suite-wide check now fails
  if any test returns to that form.
- Five security-sensitive guards were proven capable of failing by inserting the
  exact prohibited construct into the module each one inspects and confirming
  the test fails for the intended reason: network reachability, retry and fetch
  absence, timestamp recency in reasoning code, process execution in the
  filesystem tool, and prose matching in the hypothesis model. Every production
  file was restored and verified byte-identical.

## [0.3.233] - 2026-08-31

### Added

- A hypothesis evidence relationship now records when it was authored. Three
  milestones in a row had to work around the same gap: Hypatia knew when a
  relationship was withdrawn and never when it began.
- Membership stays where it was. The three collections remain the single answer
  to what currently stands, and the new record only annotates them with a time,
  so every consumer — appraiser, curiosity, events, failure lessons, history —
  reads current state exactly as before and none of them changed.
- Absence is represented as absence. A relationship carried forward from an
  older file has no recorded time and reads as unknown, because no number
  anywhere would truthfully stand in for one: the hypothesis's update time moves
  with every later change, a retraction's time is when a statement ended rather
  than began, and a load time is when a file was read.
- A retraction takes the time with the statement, so an authoring time can never
  be read for a relation that no longer stands, and a full cycle — authored,
  withdrawn, authored again — now records all three moments.
- The history view shows authoring times where they exist and names them as
  unrecorded where they do not, and states plainly that no complete ordering is
  claimed for a mixture of the two.

### Changed

- The hypothesis store is schema version 4. Versions 1, 2 and 3 remain readable
  and restore with unknown authoring times; reading an older file does not
  rewrite it.

### Fixed

- Seven test modules called `working_vocabulary(source)` with no function names.
  That form returns an empty set, so every guard built on it passed without
  checking anything — including guards asserting that no reasoning module reads
  a timestamp and that no ingestion module can retry or fetch. A companion
  `module_vocabulary` now reads a whole module, and the guards were switched to
  it. Every one of them passes, so the invariants held; they were simply not
  being tested.

### Security

- Timestamps are provenance and nothing else. They do not rank evidence, weight
  confidence, decide which side of a contradiction wins, or close a research
  gap. This is asserted as an equivalence rather than a promise: the same
  hypothesis with and without recorded times must appraise identically and
  produce identical curiosity, and the reasoning modules are checked not to
  mention an assertion time at all.

## [0.3.232] - 2026-08-31

### Added

- A hypothesis now has a readable history. Retraction gave the model one and
  nothing showed it, so an operator could see what currently stands but could
  not see that a relationship had been corrected without opening the store file.
  The new read-only projection puts current standing beside withdrawn
  statements, with the current appraisal and whether the discriminating test
  still has nothing recorded against it.
- The three meanings stay apart. Supporting, opposing and addressing the
  discriminating test are shown under their own headings and never collapsed
  into one list of linked evidence.
- A relationship that was retracted and later authored again reads as standing,
  with the earlier withdrawal still visible and marked as superseded by the
  current one. Showing it as retracted because an older cycle ended would have
  been a worse account than showing nothing.
- The desktop hypothesis panel gains a read-only "View history" control beside
  the existing mutations. It reads the identifier when pressed and asks afresh
  each time, so a correction made a moment ago is already in it, and it records
  nothing.

### Changed

- Nothing about hypothesis reasoning. No status, confidence, appraisal rule or
  curiosity semantics changed; this milestone only reads what the previous ones
  recorded.

### Security

- The view states only what canonical state proves. When a relationship was
  authored is recorded nowhere, so it is reported as unknown rather than filled
  in from the hypothesis's update time, the retraction's own time, or a file's —
  a printed number that looks like an answer and is not one would be worse than
  an admitted gap. No reason for a withdrawal is stored, so none is shown.
- Evidence is labelled by the operator's own note where one exists and never by
  reprinted source content, so an unread quotation cannot sit beside a
  withdrawal and be read as the reason for it.
- A long correction history is capped at the newest twenty and says how many
  were recorded, because a list that silently ends is a list that lies about its
  length.

## [0.3.231] - 2026-08-31

### Added

- All three hypothesis evidence relationships can now be taken back. Supporting,
  opposing, and addressing the discriminating test were append-only, so an
  operator who filed evidence on the wrong side had no way home: deleting the
  evidence would be wrong, deleting the hypothesis would be wrong, and quietly
  dropping the identifier would leave a record that looks as though the
  statement had never been made.
- One typed operation covers all three, because they are the same kind of
  statement and a correction path for only the newest would have left the older
  two uncorrectable for no reason anyone could name.
- The three collections remain the current projection — an identifier sits in
  one exactly while that relation stands — and a retraction record keeps the
  history. Every consumer already read those collections, so appraisal,
  curiosity, events and failure lessons follow current state without knowing
  this feature exists: no consumer changed.
- The desktop hypothesis panel gains a relation selector and one "Retract
  relation" control. It names the hypothesis, the evidence, the relationship and
  the word RETRACT before recording anything, refuses more than one evidence
  identifier because a retraction is about a single statement, and executes
  nothing.

### Changed

- The hypothesis store is schema version 3. Versions 1 and 2 remain readable and
  restore with no retractions, because that is what they say: their
  relationships were active when written and stay active on load. No retraction
  is invented to explain a collection that was simply never corrected.

### Security

- Retraction means one thing: the statement no longer stands. It does not mean
  the evidence was wrong, that it belongs on the other side, or that the
  hypothesis is settled either way. Nothing moves — correcting a mistake is two
  authored events, never one hidden flip — and no confidence, status or claim
  changes because a correction happened.
- Only a currently standing relation can be withdrawn, which keeps every
  retraction record matched to a relation that really existed and refuses a
  repeated request rather than writing the same correction down twice.
- The operation reads identifiers and a closed relation vocabulary. No wording
  is compared against any wording, and no evidence, source, claim or assessment
  is touched.

## [0.3.230] - 2026-08-31

### Added

- A hypothesis can now record which evidence an operator says addresses its
  discriminating test. Until now it could say only that evidence supported or
  opposed it, which is a weaker statement than it looks: a framework version
  number is good supporting context for "the middleware can be bypassed" while
  saying nothing about whether a protected route was ever reached without
  authorization. The hypothesis names that observation; nothing recorded which
  evidence, if any, made it.
- The relationship is authored and never inferred. It has exactly one way in —
  an explicit application operation and the desktop control that calls it — and
  no other path adds to it as a side effect. Entering evidence as supporting or
  opposing leaves it untouched, and recording it says nothing about which side
  the evidence takes; an observation can address the test and support the
  hypothesis, oppose it, or leave the direction unstated.
- The desktop hypothesis panel gains one control, "Addresses test", beside
  Support and Oppose. It reuses the hypothesis and evidence fields already
  there, records the association, and executes nothing.

### Changed

- The curiosity gap added in 0.3.229 now closes only on the authored
  association. Any supporting or opposing evidence used to close it, which meant
  a version number attached as context could silence a question about
  unauthenticated access. That coarseness was the limitation this milestone was
  written to remove.
- The hypothesis store is schema version 2. Version 1 records remain readable
  and are read as saying nothing about their test, because that is what they
  say: their supporting and opposing evidence keeps its existing meaning, and
  none of it is promoted into an association nobody authored. An open
  hypothesis carried forward will therefore surface the curiosity gap, which is
  truthful rather than a regression.

### Security

- No code decides that evidence addresses a test by reading text. Not by
  substring, token overlap, similarity, embedding, or model — the relationship
  is a person's judgement, and a wrong inference would be invisible once stored.
- Recording an association executes nothing. The discriminating test is inert
  prose describing an observation somebody would have to make; it is never
  parsed, planned, or acted on, and the association is bookkeeping after the
  fact.
- Appraisal is unchanged. An association says the test was examined, never that
  it passed, so no status, direction, or confidence moves because one exists.

## [0.3.229] - 2026-08-31

### Added

- Curiosity can now see a hypothesis nobody has answered. Every hypothesis
  already records the observation that would settle it — the model refuses one
  without it, on the grounds that a proposition with no discriminating test is
  a belief rather than a hypothesis — but hypotheses live in their own store, so
  a reading of one run never met them. An open, non-withdrawn hypothesis with no
  evidence recorded on either side is now a `hypothesis_evidence_gap`.
- Hypotheses are handed to the detector rather than fetched by it. Detection
  stays a function of its arguments, and composing the two aggregates belongs to
  the application service, which is the only layer that knows a store exists.
  Curiosity keeps working unchanged where no hypothesis store is configured, and
  a store that cannot be read costs the hypothesis half of a report rather than
  the whole of it.
- The gap ranks below all three claim gaps and above everything describing the
  run's breadth. Claims are positions the run already holds and their integrity
  comes first; a stated open question is the most answerable kind of
  incompleteness, but it is still an absence rather than a belief in trouble.

### Security

- The question names the hypothesis by its statement and never by its
  discriminating test. The test describes an observation somebody would have to
  make, and quoting that sentence into a question is how a description turns
  into an instruction. Nothing here runs a test, builds a payload, or reaches
  anything, and accepting the question decides nothing about the hypothesis.
- Missing evidence asserts nothing. A hypothesis nobody has answered is neither
  supported nor contradicted, and the gap says only that the requirement remains
  unresolved.
- No wording is compared against any other wording. A hypothesis carries one
  prose test and two lists of evidence identifiers, and nothing canonical links
  them, so the only condition reported is the unambiguous one — evidence exists,
  or it does not.

## [0.3.228] - 2026-08-31

### Added

- Curiosity now reads two things a run *attempted*, having previously read only
  what it holds. A refused source acquisition becomes a `failed_acquisition`
  gap, and a question put to some of the available providers and not the rest
  becomes a `provider_coverage_gap`. Both were already recorded on the run —
  in `failures` and `discoveries` — and neither needed a new aggregate, a new
  store, or a model to see.
- Neither gap becomes advice. A failed acquisition asks what information is
  still missing rather than proposing the same attempt again, and a
  single-provider run asks what other coverage would add rather than which
  provider answers better — that judgement belongs to the person reading the
  comparison, and a question implying it would be that judgement wearing a
  question mark. No retry, no fallback, and no provider preference is
  introduced anywhere.
- Failures are grouped by the provider they were attributed to, so repeated
  refusals are one gap that keeps one identity while the same thing keeps
  failing. A legacy failure carrying no provider is reported under its stage
  rather than dropped or guessed at.

### Fixed

- A generated question about a subject the run records without a title — the
  provider an acquisition was attributed to, for instance — fell back to the
  run's own question and so described the wrong thing entirely. The identifier
  is now used as the label when no recorded wording exists, while a gap naming
  no subject at all still speaks for the run.

## [0.3.227] - 2026-08-31

### Tests

- The research controls are now checked against the handlers they are supposed
  to call. Every research method in the window was already tested by calling it,
  which left the one thing an operator actually does — pressing a control —
  unproven: a button wired to the wrong method would have left every handler
  test green while the desktop did something else.
- The window is built by its own `__init__` and `_build_layout` with the tkinter
  widget classes replaced by recorders, so the bindings under test come from
  Hypatia's real construction code rather than from a fixture. No display, no
  GUI automation, and no real Tk root is involved.
- Preview & load is asserted by handler identity, because it is the control
  standing between a discovered candidate and a network fetch of it. Bound to
  the generic loader beside it, the same button would still load something —
  without the confirmation, and without the candidate being revalidated against
  the discovery that returned it. The contract was verified by temporarily
  misbinding it, which fails three tests including that one.
- The command each control carries is also lifted off the real widget and
  invoked against live state, so a provider switch is proven to act on the
  candidate selected when the button is pressed rather than one selected
  earlier. Every research command is a bound method rather than a layout-time
  lambda, which is the structural reason no stale run, provider or source can be
  captured.
- Shared labels are distinguished from shared handlers. The simple Research tab
  and Research (Advanced) both offer "Find sources" and "Start research", and
  three panels each contribute a different record type to a comparison; each
  resolves to its own handler, and no two research controls share one.
- No production code changed. Every binding was already correct, and the manual
  "Load source" control was confirmed to be a deliberately separate
  explicit-URL workflow rather than a way around candidate acceptance.

## [0.3.226] - 2026-08-31

### Tests

- The paired operator journey is now driven through the desktop controls
  themselves rather than service by service: a real window wired to a real
  controller over a real cognitive engine and real stores, with only the two
  discovery providers and the source fetcher faked. The tests press the methods
  the buttons are bound to, in the order a person presses them — discover
  Crossref, discover NVD, select a candidate, preview, confirm, accept, refresh,
  select the other provider, accept again, use for assessment, record evidence,
  author a claim, read the comparison.
- This closes the two limitations left open by the previous milestone: the
  journey had never been driven as one integrated desktop flow, and paired
  provider quality had only been exercised at the comparison-builder join rather
  than through a complete two-provider run with both sides accepted and assessed.
- Both halves of a paired run stay reachable and stay distinct. Neither
  candidate can be accepted under the other provider's discovery, the second
  acceptance neither hides nor replaces nor duplicates the first, the selected
  run never changes underneath the operator, and each provider keeps its own
  funnel with no winner, no recommendation and no combined score.
- A refused second side leaves the first source attached, records a visible
  failure, and is neither retried nor substituted — a failed provider is a
  failed provider, not a reason to undo the other one.
- Restoration is asserted across the paired journey: both sources come back,
  Crossref keeps its ordinary HTTPS acquisition, and the accepted CVE keeps both
  its API acquisition and its content resource.
- No production code changed. Nothing in the journey was defective, and the
  harness was verified to fail when the desktop's outcome reporting is removed,
  so the coverage is real rather than incidental.

## [0.3.225] - 2026-08-31

### Fixed

- An accepted CVE lost its provenance on restart. Startup rebuilds each indexed
  document from the persisted content record alone, and that record had nowhere
  to keep how the bytes were obtained, so a source materialized from the NVD CVE
  API 2.0 came back describing itself as an ordinary HTTPS read of the detail
  page — a page that serves an application shell and cannot produce those bytes.
  Document identity derives from the URL, so the restored document still
  matched, indexing still succeeded, and nothing reported that the provenance
  had changed. The content record now carries `content_resource` and
  `acquisition`, and restoration rebuilds the source with them.

### Changed

- The research source content store is schema version 2. Version 1 snapshots
  remain readable and are decoded with the defaults, which say exactly what
  version 1 was able to say: an ordinary HTTPS read whose content resource is
  the URL itself. That was true of every source that could exist when those
  records were written, so reading them this way states their provenance rather
  than inventing it. No historical record is rewritten or migrated.

### Tests

- The whole downstream operator journey is covered with a structured source:
  accepted into the run, previewed and assessed through the existing assessment
  vocabulary, chunked into readable evidence, cited by an ordinary claim, and
  joined back to its discovery candidate by the provider comparison. Confidence
  does not rise because the provider was NVD, an unassessed source stays
  unknown rather than authoritative, no reference is ever fetched or promoted to
  a source, and the Crossref path is asserted unchanged end to end.

## [0.3.224] - 2026-08-31

### Fixed

- A weakened-hypothesis Failure Memory lesson now names both the supporting and
  opposing evidence that made the weakened outcome possible. Previously its
  wording described both sides while its provenance named only opposition, so
  the remembered outcome could not be fully checked from the records it cited.
- Supporting and opposing evidence IDs are interleaved inside the existing
  provenance limit. Even when one side alone exceeds that bound, the lesson
  retains records from both sides; contradicted-hypothesis lessons remain
  unchanged and continue to cite only opposing evidence.

### Changed

- Three already-validated integer values from untyped provider and request
  metadata are now returned through an explicit integer conversion. Runtime
  behaviour is unchanged, while the full source tree again passes the current
  strict MyPy gate without relying on `Any` return values.

### Security

- The change is pure derivation at the explicit Failure Memory boundary. It
  does not mutate hypotheses, evidence, claims, assessments, or research runs,
  and it does not add autonomous recall or execution.

## [0.3.223] - 2026-08-31

### Added

- An accepted NVD candidate is materialized from the NVD CVE API 2.0 instead of
  from the page that names it. `nvd.nist.gov/vuln/detail/CVE-...` serves an
  application shell whose CVE is drawn by a browser afterwards, so the generic
  loader was right to refuse it and no improvement to that loader would have
  helped. Acceptance now performs one exact `cveId` lookup through the same
  pinned transport, fixed host and one-request discipline discovery already
  uses, and renders the record as bounded readable text: description, published
  and last-modified times, provider record status, weaknesses, every severity
  metric with its own scorer, CISA known-exploited fields where present, and the
  reference list. No browser, renderer, or bot-check workaround is involved.
- Source provenance distinguishes what a source *is* from where its bytes came
  from. A materialized CVE keeps the detail page as its URL — the resource a
  person opens, and the identity duplicate detection and provider comparison
  both join on — and records the API endpoint beside it as the content resource.
  Left empty, as it is for every ordinary HTTPS source, the two coincide exactly
  as before.

### Changed

- The candidate acceptance preview says what the load will actually do. A
  vulnerability candidate now discloses that its record will be retrieved from
  the API, that the linked page is not read, and that the references it lists
  are stored as text without being fetched. A confirmation is only meaningful
  if it names the real operation.

### Security

- Vulnerability data stays data. A materialized record carries the same
  `instruction_authority = none` every external source carries, its references
  are never fetched, and a description phrased as an instruction changes nothing
  about what is requested. The route is chosen by URL alone, with no fallback in
  either direction: a refused CVE lookup never silently loads the web page, and
  an ordinary DOI never reaches the vulnerability API.
- A lookup answering with a different CVE than the one accepted fails closed and
  attaches nothing, rather than filing one vulnerability's facts under another's
  identifier.

## [0.3.222] - 2026-08-30

### Fixed

- Confirming "Preview & load" appeared to do nothing. The load ran, and a
  refused fetch was reported for one instant before the canonical re-read that
  follows reselected the run and overwrote the report with "no action started" —
  beside a source count that had legitimately not moved. An operator therefore
  saw an unchanged run and a status line stating that nothing had been started,
  with no indication that their confirmation had been acted on at all. The
  outcome of the attempt is now restated after every refresh that could
  overwrite it, for successful and refused loads alike. The refresh itself is
  kept: a refused load records a failure on the run, which is a real change the
  operator should see counted.

## [0.3.221] - 2026-08-27

### Fixed

- Failure Memory now derives at most one false-positive lesson for multiple
  accepted document records that resolve to the same canonical resource. A
  duplicated low-trust page can no longer inflate one source-quality mistake
  into several remembered failures.
- The first accepted document remains the stable lesson subject, while the
  newest active low-trust assessment and its actual document remain in the
  lesson provenance for inspection.

### Security

- No source, assessment, evidence, or persisted research-run record is
  rewritten. The change only makes pure lesson derivation identity-aware and
  leaves recall advisory.

## [0.3.220] - 2026-08-27

### Fixed

- Failure Memory now matches accepted research sources to discovery candidates
  by canonical resource identity. Equivalent HTTPS URLs that differ only by a
  `www` prefix, default port, host casing, or trailing slash no longer create a
  false ineffective-strategy lesson after the source was actually accepted.

### Security

- The correction is local, deterministic, and advisory-only. It does not fetch
  a source, change provider selection, suppress a real zero-result discovery,
  mutate research records, or turn a recalled lesson into an enforcement rule.

## [0.3.219] - 2026-08-27

### Fixed

- Claim calibration now measures assessment coverage per canonical resource
  identity rather than per stored document. Multiple records of one page can no
  longer hide a different, unassessed source and falsely satisfy the
  fully-assessed evidence ceiling.
- When multiple assessed records resolve to the same resource, the resource's
  most cautious active trust value remains visible to the support calculation.

### Security

- The change is local, deterministic, and read-only. It does not alter authored
  assessments, evidence, claims, source records, provider routing, network use,
  or tool authorization.

## [0.3.218] - 2026-08-27

### Fixed

- Hypothesis proposal now refuses an identifier already present in the active
  hypothesis catalogue. A repeated injected or restored ID can no longer
  silently replace an earlier conjecture and its discriminating test.

### Security

- Collision refusal happens before in-memory mutation, event publication, or
  durable persistence. The existing hypothesis remains byte-for-byte unchanged,
  and no claim, research run, provider, network, or tool path is involved.

## [0.3.217] - 2026-08-27

### Fixed

- Advanced Research now re-reads the canonical persisted run catalog after a
  confirmed source-load attempt. A successfully attached candidate therefore
  appears immediately in the selected run's source count and accepted-source
  selector instead of leaving the pre-load snapshot on screen.
- The same refresh also exposes canonical failure records while preserving the
  exact selected run. It performs no second discovery or provider request.

### Security

- Candidate preview, explicit confirmation, exact run/discovery/URL binding,
  cancellation, and the guarded loader remain unchanged. The completion path
  only performs a local read of persisted research state.

## [0.3.216] - 2026-08-27

### Fixed

- Hypothesis appraisal now refuses a hypothesis paired with a different
  research run. Evidence identifiers can no longer be interpreted against the
  wrong run merely because their text happens to overlap.
- Supporting and opposing evidence identifiers must all exist in the bound
  research run. Missing provenance is surfaced as an error instead of being
  silently omitted and making a damaged hypothesis appear open.

### Security

- Appraisal remains local, deterministic, and read-only. The new checks fail
  closed on broken canonical relationships and do not rewrite hypotheses,
  evidence, trust assessments, claims, or research status.

## [0.3.215] - 2026-08-27

### Fixed

- Failure Memory recall now preserves short technical vocabulary such as
  `XSS`, `SQL`, `C++`, and `C#`. A prior lesson and a new question that share
  two such identifiers can now be matched instead of losing the most specific
  terms before relevance is measured.
- Closed-list function words and generic medium names remain excluded from the
  short-token path, and the existing two-shared-token threshold still applies.

### Security

- Recall remains deterministic, local, bounded, and advisory. The tokenizer
  performs no semantic inference, model call, research action, or automatic
  plan change; every surfaced lesson can still be ignored.

## [0.3.214] - 2026-08-27

### Fixed

- Failure Memory now records an ineffective-strategy lesson when a successful
  source discovery returns zero candidates. A zero-result search is no longer
  silently omitted from what Hypatia can remember about approaches that did not
  pay off for the exact question.

### Security

- The lesson is derived only from the persisted discovery audit record and
  explicitly remains about that query, not the provider in general. It performs
  no retry, provider selection, network request, or research-state mutation.

## [0.3.213] - 2026-08-27

### Fixed

- Simultaneous failure lesson disambiguation now reserves every raw failure
  identity before adding occurrence suffixes. A provider name that itself ends
  in an occurrence-shaped segment can no longer collide with the suffix used
  for another record, so all lessons remain distinct and durably storable.

### Security

- The collision check uses only already-persisted bounded failure metadata and
  performs no inference, retry, or provider selection. Failure Memory remains
  deterministic, local, read-only, and advisory.

## [0.3.212] - 2026-08-27

### Fixed

- Failure Memory now keeps distinct lessons when multiple recorded operation
  failures share the same stage, timestamp, and provider. The original stable
  identity remains unchanged for the first record; only later collisions gain
  a deterministic occurrence suffix, preventing duplicate lesson IDs and
  durable-store rejection.

### Security

- Failure reasons remain bounded safe diagnostics and are not embedded in
  lesson identities. Derivation stays local, deterministic, read-only, and
  advisory, and it performs no retry or research operation.

## [0.3.211] - 2026-08-27

### Fixed

- Failure Memory now derives one disproving-evidence lesson per claim when that
  claim participates in several distinct contradiction records. The newest
  recorded contradiction supplies exact provenance, so a legitimate
  many-claim conflict no longer creates duplicate lesson IDs or blocks durable
  lesson storage.

### Security

- Contradictions remain explicit operator-authored records. Lesson derivation
  stays local, deterministic, read-only, and advisory; it does not decide which
  claim survives or rewrite claims, evidence, confidence, or research state.

## [0.3.210] - 2026-08-27

### Fixed

- Failure Memory now derives one low-trust false-positive lesson per accepted
  source when several parallel active assessments judge that source low trust.
  The newest active low-trust assessment provides the lesson's exact
  provenance, so legitimate parallel judgements no longer manufacture
  duplicate lesson IDs or prevent durable storage.

### Security

- Explicit supersession remains the only correction mechanism. Lesson
  derivation stays local, deterministic, read-only, and advisory; it changes no
  assessment, source, claim, provider choice, or research execution.

## [0.3.209] - 2026-08-27

### Fixed

- Claim calibration now reads every active assessment for a source instead of
  letting the last appended record replace the others. Its evidence profile
  uses the lowest active authored trust, so a parallel high-trust judgement can
  no longer raise a claim's support ceiling over an unresolved low-trust one.
- Structured assessment warnings from parallel active judgements remain
  visible. The same warning kind is still grouped once per claim and source,
  with deterministic provenance from the newest active record carrying it.

### Security

- Explicit supersession remains the only correction mechanism. Calibration is
  still derived, read-only, local, deterministic, and unable to rewrite claims,
  assessments, confidence, provider choice, or research execution.

## [0.3.208] - 2026-08-27

### Fixed

- Source reputation now keeps the lowest active authored trust when one source
  has parallel assessments. A later high-trust entry no longer hides an active
  low-trust judgement merely because it was appended later.
- Explicit supersession remains the only way a correction removes the earlier
  trust label from the derived reputation.

### Security

- Reputation remains read-only and advisory. This change alters no assessment,
  source, ranking, provider choice, or network behavior; it only prevents record
  order from making a derived origin history look safer than its active inputs.

## [0.3.207] - 2026-08-27

### Fixed

- A Crossref discovery recorded itself as `crossref-rest-v1` while the provider
  comparison and paired-quality reports looked for `crossref`, the name the
  closed vocabulary and the plan digest use. A Crossref search that had genuinely
  run was therefore reported as never having happened: the comparison showed
  that side as pending with no candidates, and no run ever became an eligible
  same-question pair. Both provider names now derive from the closed vocabulary,
  so the identity a plan authorizes is the identity a discovery records.
- Only the newest discovery in a run could be selected. A paired comparison
  records one discovery per provider, so the other provider's candidates were
  readable in the comparison report and impossible to accept — a paired run
  could only ever be assessed on one half, which is the half the measurement
  needs both of. Every recorded discovery's candidates are now offered, each row
  naming the provider that returned it, and selecting a run offers them without
  a further network request.

### Changed

- Each candidate carries the discovery that returned it, so accepting a Crossref
  candidate cannot file it under an NVD search. The two sides are still ranked
  separately: one list is not one ranking, and no row is ranked against a row
  from the other provider.

## [0.3.206] - 2026-08-27

### Fixed

- Research gap detection now keeps a low-trust source gap visible while that
  low assessment remains active, even if a separate later assessment labels
  the same source high trust.
- An explicit superseding correction still removes the earlier assessment from
  the active trust view and can resolve the gap.

### Security

- Assessment insertion order can no longer hide a recorded weakness from the
  Curiosity Engine. The detector remains read-only and cannot change trust,
  create research, or act on a gap.

## [0.3.205] - 2026-08-27

### Changed

- Failure Memory recall now prefers the newer lesson only when two lessons have
  exactly the same lexical overlap and lesson-kind weight. Stable lesson ID
  ordering remains the final deterministic tie-breaker.

### Security

- Recency cannot make a less relevant or lighter lesson outrank a stronger
  match. Recall remains bounded, advisory, local, model-free, and unable to
  block or modify research.

## [0.3.204] - 2026-08-27

### Fixed

- Hypothesis appraisal no longer lets insertion order choose between multiple
  active trust assessments for one source. It conservatively keeps the lowest
  authored trust until an explicit superseding correction removes it.

### Security

- A later parallel high-trust assessment can no longer silently mask an active
  low-trust assessment and move a hypothesis to `supported`. No assessment is
  rewritten, merged, or inferred, and explicit supersession behavior is
  unchanged.

## [0.3.203] - 2026-08-27

### Changed

- Evidence support profiles now reject impossible trust summaries: trust with
  no assessed source, a lowest trust above the highest trust, and non-boolean
  contradiction or supersession states.
- Hypothesis appraisals now reject supporting or opposing trust labels when no
  source on that side has an authored assessment.

### Security

- These checks harden derived Evidence & Confidence records at their domain
  boundary. They do not change authored claims, source assessments, confidence
  ceilings, hypothesis status rules, or any stored research state.

## [0.3.202] - 2026-08-27

### Fixed

- Failure Memory now applies the same bounded lexical normalization to a new
  question and to stored lesson context. Trailing punctuation can no longer
  hide an otherwise relevant two-token lesson.
- Punctuation-only fragments are discarded after normalization instead of
  becoming meaningless recall tokens.

### Security

- Recall remains advisory, deterministic, local, bounded, and model-free. The
  change does not block research, store new information, alter lesson weights,
  or lower the existing two-shared-token threshold.

## [0.3.201] - 2026-08-27

### Added

- Optional bounded provider provenance on research failure audit records. New
  source-discovery failures record the exact provider selected by the approved
  step or explicit desktop request.
- Provider-aware comparison failure states. A failed NVD or Crossref attempt is
  shown on that side while a successful other side remains intact.
- Provider-aware Failure Memory lessons. A discovery failure lesson now names
  its recorded provider and includes that provider in its stable subject and
  provenance identity.

### Changed

- Research-run persistence is schema v13. Legacy v1-v12 failures load with no
  provider rather than receiving invented provenance; the optional field is
  written only on a later successful snapshot replacement.
- A provider-attributed failure is distinct from a pending side. Legacy
  provider-less discovery failures remain separately counted and unattributed.

### Security

- Provider provenance is captured from the already selected typed provider at
  the failure boundary, never parsed from an exception message or inferred from
  execution order, candidates, or later state.
- Raw provider errors remain absent. The stored reason stays the existing
  generic bounded message, and provider text is bounded, stripped, and rejects
  control characters.
- Cancellation before or after provider work still creates no discovery-failure
  record. No retry, routing, preference, automatic provider choice, or new
  network operation was added.

## [0.3.200] - 2026-08-27

### Added

- A read-only paired provider quality report. It includes only research runs
  where Crossref and NVD each recorded a discovery for the run's exact same
  canonical question, then shows the two assessment funnels separately.
- A `Paired quality` action in Review. It reads every persisted run, reports up
  to 40 qualifying same-question pairs, and exposes the complete qualifying
  count when the bounded view omits older pairs.
- Structural telemetry for report size only: paired-run, displayed-pair, and
  assessed-sample counts, with no question, provider result, document ID, or
  assessment content.

### Changed

- Nothing in persistence or execution. The report is derived from existing
  discovery, accepted-source, evidence, and current assessment records.

### Security

- Merely seeing both provider names in a run is insufficient. Each provider's
  recorded query must exactly equal the run's canonical question before the run
  is called a same-question pair.
- A source returned by both providers is excluded from both sides instead of
  being credited by order; an assessed source returned by neither is likewise
  reported separately rather than guessed.
- Aligned questions remove question-sample mismatch, but not operator selection
  bias. Every side retains its funnel denominators and sample-size caution.
- No winner, score, preferred provider, recommendation, routing, default,
  ranking, reputation, network, model, execution, authorization, or write path
  was added.

## [0.3.199] - 2026-08-27

### Added

- Operator-driven paired provider comparison. One button drafts a two-step plan
  — one Crossref discovery, one NVD discovery — and hands it to the ordinary
  preview. Approval and two separate presses of Advance still stand between that
  and any request.
- A derived side-by-side report for one run: each provider's candidates ranked
  within that provider, with provider rank and relevance rank both visible, and
  vulnerability metadata shown only on the side that has it.
- Partial comparison states. A side nobody advanced reads as pending rather than
  as an empty result, and a provider that answered with nothing says so.

### Changed

- Nothing. A comparison is two ordinary discovery steps, so no execution path,
  budget rule, or persistence schema changed.

### Security

- The pair is covered by one plan digest. Swapping the providers, changing the
  question, dropping a side, or replacing one provider all change it, so an
  approval for one pair cannot authorize another.
- Two providers mean two network operations, because each discovery step costs
  one. Nothing performs two requests under one charge and nothing widens a
  budget.
- The Compare button reaches a preview and never a provider; the comparison
  service holds no provider, no write path, and no execution path.
- The two result sets are never merged into one ranking, and no field names a
  winner, a preferred provider, or a provider score.
- A discovery failure is not attributed to a provider, because the audit record
  does not name one. Both unattempted and failed sides read as pending and the
  run's failure count is reported separately.
- Only the operator builds a comparison. Curiosity, reflection, calibration, the
  provider-quality report and the scheduler have no path to it.

## [0.3.198] - 2026-08-27

### Added

- A read-only provider quality report. For each provider and question category
  it describes the funnel — discovery operations, candidates discovered,
  accepted sources, sources with evidence, assessed sources — and then the
  operator's own judgements across usefulness, applicability, independence and
  publication status.
- Deterministic question categories: exact CVE lookup or keyword search, decided
  from the question by the same strict parser the NVD provider uses, never from
  the provider that answered it.
- A sample-size vocabulary — no data, very small, limited, descriptive — carried
  beside every profile, whose largest band is still only descriptive.
- A `Provider quality` button in Review. Unlike the others it is not scoped to
  one run, because provider experience accumulates and one run is never a
  sample.

### Changed

- Nothing. The report reads persisted runs and adds no field, no store, and no
  schema version.

### Security

- Measurement is not policy. The report selects no provider, changes no default,
  alters no ranking or ranking weight, updates no reputation, touches no
  assessment, evidence, claim or confidence, and creates no authorization.
- It performs no network request, no model call, no source fetch, no execution
  advance and no budget spend, and constructs no provider.
- There is no provider score and no winner. Every ratio carries its numerator
  and denominator; a report with no assessed samples says so rather than
  showing 0%.
- Silence is never a negative vote. An unassessed source is missing data and an
  `unknown` dimension is an unanswered question; both are shown and neither
  enters a rate.
- Attribution that cannot be made is reported rather than guessed. A resource
  both providers returned, and an assessed source no discovery proposed, are
  each counted apart from every profile.
- The report states in its own text that the figures are observational and
  selection-biased, because the number and the caveat have to travel together.
- Telemetry carries structural counts only: no question text, no source title,
  no assessment prose, no document identifier.

## [0.3.197] - 2026-08-27

### Added

- A second discovery provider: the official NVD CVE API 2.0. A question naming
  exactly one well-formed CVE becomes an exact `cveId` lookup; anything else
  becomes one bounded `keywordSearch`. An exact request is never degraded into a
  keyword search.
- Structured vulnerability metadata on discovered candidates: CVE identifier,
  record status, reporting source, last-modified time, CWE identifiers, every
  CVSS metric with its own version and scorer, bounded references with their
  tags, and the CISA known-exploited fields when the response carries them.
- An explicit provider choice. The audit discovery panel offers Crossref or NVD,
  and the plan step that will do the discovering can name which one.
- `HYPATIA_NVD_API_KEY`, optional. NVD answers unauthenticated requests at a
  lower allowance, so an absent key is a working configuration.

### Changed

- The research plan digest schema moved to v2 because a step can now name a
  discovery provider. Approvals recorded under v1 no longer verify.
- The research run store moved to schema 12 to persist the vulnerability record.
  A candidate written earlier decodes with none.
- Plan preview and approval preview both name the discovery provider in words.

### Security

- Provider identity is bound into the approved plan. The same plan aimed at
  Crossref and at NVD digests differently, so an approval for one cannot be
  spent on the other, and an approval predating provider binding fails closed.
- A provider name is a closed vocabulary and never a URL, at the draft boundary,
  the request boundary, and process configuration. A step naming an unavailable
  provider fails rather than substituting another.
- The NVD endpoint is fixed in code and reuses the existing pinned transport,
  redirect revalidation, and address checks. HTTPS only, one host, one path,
  bounded timeout, bounded response size.
- One approved discovery performs at most one request. No pagination, no retry,
  no sleep, and no fallback to the other provider. A rate-limit refusal is
  reported rather than slept through.
- References are metadata and are never fetched, followed, or granted authority.
  A link-local or loopback address in a response is stored and left alone.
- The API key travels only in the official `apiKey` header — never in a URL,
  never persisted, never in telemetry, never in an error message.
- Severity, known exploitation, and provider provenance change no relevance
  rank, no source reputation, no operator assessment, and no claim confidence.

## [0.3.196] - 2026-08-26

### Added

- Assessment-aware calibration warnings. A claim resting on a source the
  operator marked retracted, withdrawn, corrected, not useful, unrelated,
  background-only, or not independent is now reported as such, with the source
  and the assessment that raised it named.
- A separate claim-level warning when several sources appear to corroborate a
  claim but at least one was judged to repeat another. Two witnesses and one
  witness twice look identical from the outside.
- Three bounded attention levels — info, review, high attention — with
  retraction and withdrawal the only two that reach the top.

### Changed

- The calibration report shows warnings under each claim, alongside the verdict
  rather than folded into it, and states plainly that nothing was corrected. A
  claim with no warnings is shown as having none, never as verified.
- Calibration telemetry carries bounded warning counts and kind codes. It
  carries no note text, no source title, and no assessment prose.

### Security

- Warnings are read-only. Generating them changes no claim, confidence,
  epistemic state, evidence, source, assessment, reputation, relevance score or
  relevance rank; reaches no network and no model; accepts nothing; creates no
  evidence, claim, hypothesis or curiosity question; schedules nothing; and
  spends no budget.
- Only structured fields produce warnings. An operator note worrying that a
  paper might be retracted produces nothing, and neither does a source whose own
  title claims to be retracted. `publication_status = retracted` is the only
  thing that does.
- Unknown is never treated as negative. An unassessed source, an unanswered
  dimension, and a record predating these fields all warn about nothing.
- Warnings are derived and have no store, so a revised assessment cannot leave a
  stale warning behind claiming otherwise.

## [0.3.195] - 2026-08-26

### Added

- Structured operator judgement of a source, recorded on the assessment record
  that already existed rather than beside it. Four closed vocabularies —
  usefulness, applicability to this question, independence, and publication
  status — each defaulting to `unknown`, which means nobody was asked.
- Publication status makes a retraction expressible. Recording one preserves the
  source, its evidence, and every claim that rested on it, and marks the
  assessment visibly instead.
- Independence records what canonical identity cannot know: that a source is
  derivative of another, or is likely the same publication under a second URL.
- The research panel shows relevance, operator assessment, source reputation,
  and evidence status as four separate labelled lines, each naming what produced
  it.

### Changed

- The assessment history list shows which dimensions were answered alongside
  `[current]` or `[superseded]`. An unanswered dimension is left out rather than
  displayed as a verdict.
- The research run store moved to schema version 11 to persist the four
  dimensions. A version 10 assessment decodes as `unknown` on all of them, which
  is what those records truthfully hold.

### Security

- A judgement changes nothing else. It moves no relevance score, no relevance
  rank, no source reputation, no evidence, no claim, no claim confidence, and no
  acceptance — each asserted, and the ranker's inability to reach an assessment
  asserted structurally rather than assumed.
- Only a person authors one. Source text asking to be marked trustworthy has
  instruction authority `none` and changes nothing; an operator note is stored
  as data and never becomes an instruction; Curiosity, Reflection, the
  scheduler, and the background worker have no path to the write.
- An unrecognised judgement is refused on write and fails the load on read,
  rather than degrading to `unknown`. A judgement this build cannot read is one
  somebody made, and showing it as never made would be worse than refusing to
  open the file.
- A retraction rewrites no history. No source is deleted, no evidence removed,
  and no claim silently revised.

## [0.3.194] - 2026-08-26

### Added

- Deterministic relevance ranking of discovered sources. Results are ordered by
  how much of the question a title covers, weighted so an identifier counts for
  more than a common word, plus adjacent query words, a venue mention, and —
  only when the question asks for recent work — how the years compare within
  that one set of results.
- Every score keeps the parts that produced it and a closed vocabulary of
  reason codes, so an order can be interrogated rather than trusted. Simple mode
  shows the band in ordinary words; the audit view shows the exact codes.
- Query normalisation that keeps technical identifiers intact. `CVE-2026-12345`,
  `Next.js`, `ASP.NET`, `HTTP/2` and `C++` survive as single terms; nothing is
  stemmed to a root.
- The venue and publication year Crossref already returned are kept as fields
  instead of being flattened into a display snippet and lost. Source cards name
  the journal, which for a DOI provider is the only thing that tells two results
  apart.

### Changed

- Discovery lists are shown in relevance order by default, in both the simple
  panel and the audit view. The provider's own position travels with every row,
  so a fault in ranking stays distinguishable from a fault upstream.
- A result that repeats an earlier one is marked and sorted last rather than
  removed. Identity is the canonical resource identity; titles are never
  compared, because similar text is not identity.
- The research run store moved to schema version 10 to persist the venue and
  year. Version 9 candidates decode with neither, which is what they truthfully
  have.

### Security

- Ranking gained no authority. It accepts nothing, fetches nothing, records no
  evidence, rewrites no provenance, reaches no network, consults no model, and
  costs nothing from a research budget. A relevance score is a derived
  annotation on a record that already existed.
- Relevance is kept apart from truth in the vocabulary itself. A band says the
  question's words are in the title and never that the source is reliable,
  correct, or verified, and the phrasebook is asserted against those words.
- A venue that does not mention the subject is not penalised. Subtracting for it
  would systematically favour narrowly named journals over the venues serious
  work actually appears in.
- Recency applies only when the question asks for it, and is measured within the
  results rather than against a clock. The paper that first described an attack
  is usually the oldest one.

## [0.3.193] - 2026-08-26

### Added

- Operator-controlled bounded foreground execution. A started execution can be
  inspected, advanced one step at a time, and cancelled. `status`, `advance`,
  and `cancel` are reachable; every one of them is an act a person performs.
- Status reports canonical state alongside the approved, spent, and remaining
  budget, and names the capability the next advance would use — including
  whether it costs a network operation.
- The approved budget became enforced arithmetic. Each advance costs one step
  advance plus the declared cost of the step's capability, taken from the
  existing closed cost table.

### Changed

- Execution store schema version 2 persists the approved budget and what was
  spent against it. Version 1 records decode with no allowance, which is what
  they truthfully had; defaulting them to a full fresh budget would make an old
  execution look like it had everything left.

### Compatibility and safety

- One advance attempts at most one step and then stops. There is no loop, and a
  test asserts that `process_advance` names itself exactly once — in its own
  definition. The next step requires another explicit press.
- The budget check happens *before* the attempt, so an unaffordable step
  performs no operation at all. The charge happens at the attempt boundary, so
  nothing is refunded when an operation fails, blocks, or is cancelled: a budget
  that came back after a failure could be spent twice by failing once.
- Wall-clock counts time inside attempts, not time since the execution started.
  An execution stepped by a person is idle between advances and idle entirely
  while the application is closed. The limitation is stated rather than hidden:
  idle time is invisible to this counter, which is the only span the state can
  truthfully observe.
- Reading status advances nothing and spends nothing, asserted by repeating it
  and checking the counters have not moved.
- Cancelling is final and refunds neither the approval nor the spent budget,
  creates no replacement, and queues nothing.
- Restored executions remain read-only. Restarting resumes nothing, returns no
  approval, and resets no counter.
- Seven autonomy and background intents remain unreachable; neither the autonomy
  loop nor the scheduler can reach an approval. No new capability, no
  filesystem, shell, or tool authority, and `max_llm_operations` still defaults
  to 0.

### Verification

- One end-to-end test proves exact arithmetic against the real cost table: with
  three advances and one network operation approved, a local step and a network
  step both run, the second network step is refused before it is attempted, and
  the counters agree afterwards.
- Also covered: a refusal before the attempt charges nothing, a failed attempt
  is not refunded, spent budget survives a restart, and the allowance type
  refuses to represent an over-spend at all.
- Package-aware discovery passes 3,659 tests with 3 existing platform-dependent
  skips. Black, Ruff, and source MyPy pass for this release scope.

## [0.3.192] - 2026-08-26

### Added

- One human-approved foreground execution is enforceable. Starting a research
  plan now requires one exact valid approval for that plan and run, and spends
  it. `research_plan_execution_start` is reachable for the first time, and only
  because starting costs an approval.
- Single-use consumption. An approval carries at most one consumption naming
  the execution it was spent on and when, the transition is one-way, and a
  consumed approval can never cover anything again. Listing reports it.
- Five verdicts for what the store and the request can decide beyond the pure
  verifier: `unknown`, `already_consumed`, `budget_exceeded`,
  `disclosure_unsatisfied`, and `not_recorded`.

### Changed

- Authorization store schema version 2 records consumption. Version 1 documents
  still load, as unconsumed, which is what they truthfully were — nothing could
  spend an approval when they were written. Anything newer fails closed.
- The pure verifier now refuses an approval that has already been spent, which
  the record itself can answer.

### Compatibility and safety

- An authorization problem is *not reached*, never failed. No execution object
  is created, so nothing records a research failure for research that never
  began.
- **The handoff is not atomic and is not claimed to be.** The approval store and
  the execution store are separate files with no transaction spanning them.
  Everything is checked, the approval is durably written as spent, and only then
  does runnable execution state exist. A crash can leave an approval spent with
  no execution; it cannot leave a running execution whose approval is still
  available to spend again. That asymmetry is deliberate and asserted by test.
- A failed consumption write prevents the start entirely. There is no
  session-only spend that could execute anyway and still be available after a
  restart.
- Nothing refunds. An attempt that failed, blocked, was cancelled, or died still
  spent the approval, because the approval was for the attempt.
- Capabilities, budget, and disclosure are enforced as upper bounds, compared
  component-wise and by rank, never widened by union. Starting requests neither
  a budget nor a disclosure, so the surface cannot widen either.
- Ten of the eleven autonomy intents remain unreachable. The autonomy loop and
  the scheduler cannot reach an approval at all, and a background task still
  carries none — that binding is deliberately still open.
- No new capability, no filesystem, shell, or tool authority, no budget default
  or ceiling changed, and `max_llm_operations` still defaults to 0.

### Verification

- Coverage proves that a missing, unknown, expired, mismatched, or already-spent
  approval refuses without creating an execution or spending anything; that one
  approval cannot start two executions across a restart; that consumption is
  monotonic; and that the consumed event precedes the started event, which is
  the ordering the crash-window argument rests on.
- Composition is tested as the security claim it is: the consumer is attached
  exactly when approvals are kept, and the surface and the enforcement share one
  opt-in rather than two.
- Package-aware discovery passes 3,624 tests with 3 existing platform-dependent
  skips. Black, Ruff, and source MyPy pass for this release scope.

## [0.3.191] - 2026-08-26

### Added

- A person can approve one exact research plan and keep the approval. Preview
  shows what confirming would record — both plan identities side by side, the
  derived capabilities, the budget, the model-disclosure decision, the
  authorizer, and the validity window — and writes nothing. Confirming records
  that exact approval. Listing reports what has been approved and whether each
  approval is still valid.
- Three intents, named for approval and nothing else:
  `research_plan_authorization_preview`, `..._confirm`, and `..._list`.
- A bounded versioned approval store, capped at 500 records and 4 MB, validated
  back through the domain constructor on load and failing closed on a malformed
  or unsupported document.
- An approval section in the Research (Advanced) plan area, using the plan
  already on screen rather than a second copy, gated on
  `HYPATIA_PLAN_AUTHORIZATION_ENABLED`.

### Changed

- The two remaining runtime opt-ins that were still read inline —
  `HYPATIA_RESEARCH_EXECUTION_PERSISTENCE_ENABLED` and
  `HYPATIA_BACKGROUND_RESEARCH_ENABLED` — moved into the shared module
  alongside the new one.

### Compatibility and safety

- Nothing executes. The approval service imports no execution, autonomy, or
  scheduler service; no execution path reads an authorization; and both
  directions of that boundary are asserted by tests. All eleven autonomy
  intents remain unreachable.
- Confirmation is bound to a preview rather than a description. An edited plan,
  a different run, or an expired preview is refused and records nothing, and a
  refused preview cannot be retried.
- Approval identity and plan identity stay distinct: two approvals of the same
  plan coexist rather than overwriting one another.
- Loading renews nothing. An expired approval stays expired, remains listed for
  audit, and cannot verify as valid.
- Disclosure is recorded and still unwired. It defaults to `none`, is bounded to
  the existing enum, and reaches no LLM transport.
- Single use remains **unenforced**. Nothing marks an approval consumed, because
  no execution exists to consume one, and its absence is asserted rather than
  explained.
- No new capability, no filesystem or shell authority, no budget default or
  ceiling changed, and no migration.

### Verification

- Coverage proves that instruction text asking to authorize a plan, enable a
  capability, raise the budget, allow remote disclosure, or start background
  research changes none of those things.
- Also covered: preview writes nothing, confirmation records exactly what was
  previewed, persistence survives restart without extending expiry, malformed
  and unsupported documents fail closed, the store bound and duplicate
  identities are enforced, and a failed write is reported as a failure in both
  the response and telemetry.
- Package-aware discovery passes 3,582 tests with 3 existing platform-dependent
  skips. Black, Ruff, and source MyPy pass for this release scope.

## [0.3.190] - 2026-08-26

### Added

- A research plan now has a content identity. `plan_digest` is a SHA-256 over a
  canonical encoding of the question, the ordered steps, and everything each
  step declares — instruction, capability, authorized source URL, selected
  sources, and every per-step authorization it carries. `plan_id` keeps its
  original meaning as per-preview instance identity; the digest is a second
  identity, not a replacement.
- `ResearchPlanAuthorization`, an immutable record binding one approval to one
  exact plan digest, research run, capability set, budget, disclosure decision,
  and bounded validity window.
- `ResearchDisclosure`, so permission to read something locally stays separate
  from permission to send it to a model endpoint. Default `none`.
- `ResearchAuthorizer`, with the single value that is currently true.
- `verify_plan_authorization`, a pure function returning one bounded
  `ResearchPlanAuthorizationVerdict`: valid, digest mismatch, run mismatch,
  capability mismatch, or expired.

### Compatibility and safety

- Nothing consults any of this. No intent, service, desktop surface, or store
  reads an authorization, and a test asserts that no other module imports one.
  All eleven autonomy intents remain unreachable, which a test also asserts.
- Capabilities are derived from the approved plan rather than typed alongside
  it, so an approval cannot be constructed wider than what it approves. A
  hand-built record that disagrees with its plan fails verification.
- Validity is bounded by the existing 3,600-second autonomy ceiling and is
  terminal. There is no renewal, refresh, grace period, or extension.
- Single use is deliberately **not** implemented. Execution does not exist, so
  nothing could truthfully mark an authorization consumed, and a flag nothing
  set would read as a guarantee. Its absence is asserted.
- No new capability, no filesystem or shell authority, no budget default or
  ceiling changed, no persistence, no schema, and no migration.

### Verification

- The digest is tested against the failures a delimited encoding would have:
  authored text imitating a separator, embedded newlines, and a character
  shifted between neighbouring steps. Turkish and other Unicode text is tested
  for determinism and for distinguishing dotted from dotless letters.
- Coverage also proves that two independent previews of one plan digest
  identically while their identifiers differ, that every edited part of a plan
  changes the digest, and that verification mutates nothing and reaches no
  store, network, model, tool, or filesystem.
- Package-aware discovery passes 3,531 tests with 3 existing platform-dependent
  skips. Black, Ruff, and source MyPy pass for this release scope.

## [0.3.189] - 2026-08-26

### Added

- Looking back at a run is reachable from the application. A Review tab reports
  how far each claim outruns its evidence, reflects on how a run went and keeps
  the account, finds where a run's own record is thin, drafts and keeps ranked
  questions, rules on one proposal, and lists what was kept. All three engines
  had been runtime-only.
- `DesktopController` gained the ten corresponding commands, each refusing an
  empty run or question before the runtime is reached.

### Fixed

- A failed durable write is no longer reported as a stored reflection. The
  report stays in this process and the response says plainly it was not written
  down. This is the same defect fixed for failure memory, hypotheses, and the
  weakness taxonomy; reflection was the fourth service carrying it.
- The same fix for curiosity, on both paths: keeping ranked proposals and
  recording a ruling on one. Neither now claims success over a failed write.

### Changed

- The last two runtime opt-ins moved into the shared module. All five are now
  read through one predicate each, and no `HYPATIA_*` variable is read in more
  than one module.

### Compatibility and safety

- Calibration needs no opt-in and earns the tab on its own, because it stores
  nothing and derives its report from the run on every request. Reflection and
  curiosity each add their section only where their store exists.
- Nothing on the tab adjusts what it reports on. There is no control for a
  confidence or an epistemic state, calibration reports a mismatch and leaves
  the judgement where it was, and a ruling records an opinion without starting
  any research or reaching any source.
- No new intent, storage schema, migration, model judgement, autonomous write,
  tool capability, or filesystem access was added.

### Verification

- Coverage exercises all ten commands and their metadata, local refusal of an
  empty run or question, tab and section presence across both opt-ins, panel
  handlers including a refusal and an unsuccessful write, and runtime
  end-to-end paths — among them one proving a run is byte-identical after being
  calibrated, reflected on, and questioned.
- The absence check reads the code rather than the prose around it, and now has
  one implementation shared by the panels that need it.
- Package-aware discovery passes 3,480 tests with 3 existing platform-dependent
  skips. Black, Ruff, and source MyPy pass for this release scope.

## [0.3.188] - 2026-08-26

### Fixed

- Authored text can no longer forge a failure lesson in a report. Lessons are
  rendered one per line, and a failure reason is free text, so a line break
  inside one arrived in the report as a second entry carrying a lesson kind of
  its own choosing. One real lesson rendered as two, the invented one labelled
  `failed_hypothesis`. Reproduced, then closed at the record: a lesson collapses
  its statement and context to a single line at construction, so every producer
  inherits the guarantee rather than each renderer having to remember it.
- Collapsing rather than refusing, so an awkward failure reason becomes one
  line instead of an exception, and a lesson stored before this rule still
  loads. The text itself is unchanged; it simply stops being its own line.
- Listing remembered lessons now says which lesson each entry is. Entries had
  been identified only by record ID, the same unreadability fixed for the
  hypothesis listing in `0.3.187`, and it matters for the same reason: the
  reason to open the list is to decide what to do about what is in it.

### Changed

- The single-line rule now has one implementation shared by hypotheses and
  lessons, rather than one copy per record type.

### Verification

- Coverage pins the forgery across all three lesson renderings, the collapse at
  the record itself for both statement and context, that the forged text still
  survives inside its own entry rather than being silently discarded, and that
  listings name what they list.
- Package-aware discovery passes 3,449 tests with 3 existing platform-dependent
  skips. Black, Ruff, and source MyPy pass for this release scope.

## [0.3.187] - 2026-08-26

### Added

- The learning loop is reachable from the application. A Learning tab proposes
  a hypothesis with the observation that would count against it, enters
  recorded evidence on either side, withdraws, and lists derived standing; and
  previews, remembers, recalls, and lists failure lessons, including the
  explicit hypothesis-outcome command. Both halves had been runtime-only.
- `DesktopController` gained the ten corresponding commands. One typed field
  becomes the evidence list the runtime expects, separated by commas or spaces,
  and an incomplete entry is refused before the runtime is reached.

### Fixed

- Listing hypotheses now says which hypothesis each entry is. Entries had been
  identified only by record ID, which is unreadable by anyone deciding which
  hypothesis to act on — the reason to open the list at all. The statement is
  shown on one bounded line, so a long or multi-line hypothesis can neither
  forge entries nor make the catalogue unscannable.

### Changed

- The runtime opt-in rules moved into one module shared by the runtime and the
  desktop. Three capabilities are opt-in and each is read twice; separate
  copies of one environment rule eventually disagree, and the failure that
  follows is a person entering work into a panel that quietly forgets it.

### Compatibility and safety

- Each half of the tab follows its own opt-in. `HYPATIA_HYPOTHESIS_ENABLED` and
  `HYPATIA_FAILURE_MEMORY_ENABLED` are independent, a build keeping one shows
  only the half it can honour, and remembering hypothesis outcomes appears only
  where the durable hypothesis store exists.
- Nothing on the tab decides that anything is true. There is no confirm control
  and no status meaning confirmed; recall stays advisory; an unsuccessful
  response, including a failed durable write, is displayed unchanged rather
  than restated as success.
- No new intent, storage schema, migration, model judgement, autonomous write,
  tool capability, or filesystem access was added.

### Verification

- Coverage exercises all ten commands and their metadata, evidence-field
  parsing and refusal, tab presence across both opt-ins independently, panel
  handlers including a refusal and an unsuccessful response, and runtime
  end-to-end paths — among them one that would catch a metadata key the adapter
  and the runtime spelled differently, and one driving the whole loop from
  proposal through opposition to a remembered lesson recalled by question.
- Package-aware discovery passes 3,445 tests with 3 existing platform-dependent
  skips. Black, Ruff, and source MyPy pass for this release scope.

## [0.3.186] - 2026-08-26

### Added

- The weakness taxonomy is reachable from the application. A Security tab
  records a class of weakness, relates two classes with a required reason, and
  reports what else shares a root cause, is prevented by the same control, or
  tends to follow from one. The graph had been complete, tested, and callable
  only from tests since it was built.
- `DesktopController` gained the four corresponding commands, each refusing an
  incomplete entry before the runtime is reached.

### Fixed

- A failed durable write to the weakness taxonomy is no longer reported as a
  successful recording. The entry stays in this process and the response says
  plainly that it was not written down; recording it again retries the write,
  and because the store rewrites the whole document, a later success carries
  the earlier entry too.

### Compatibility and safety

- The Security tab appears only where the taxonomy is durable, following the
  Tools tab rule: absent rather than present-and-forgetful. The opt-in is the
  existing `HYPATIA_VULNERABILITY_GRAPH_ENABLED` variable, now read through one
  shared predicate so the runtime and the desktop cannot disagree about it.
- Nothing on the panel names a system. There is no field for a host, a product,
  an affected version, a payload, or a proof of concept, matching domain types
  that have nowhere to put them, and nothing on the tab scans, probes, or
  reaches anything.
- Relations remain authored and explained. Nothing infers an edge, and an edge
  without a reason is still refused.
- No new intent, storage schema, migration, model judgement, tool capability,
  or filesystem access was added.

### Verification

- Coverage exercises the four commands and their metadata, local refusal of
  incomplete entries, every relation kind, tab presence in both states, panel
  handlers including a refusal and an unsuccessful write, the opt-in predicate,
  and a runtime end-to-end path that would catch a metadata key the adapter and
  the service spelled differently.
- Absence checks read the code rather than the prose around it, and are pinned
  in both directions so they can still fail.
- Package-aware discovery passes 3,415 tests with 3 existing platform-dependent
  skips. Black, Ruff, and source MyPy pass for this release scope.

## [0.3.185] - 2026-08-25

### Added

- Creating a research run now surfaces previously remembered lessons whose
  wording overlaps the new question. Recall previously required someone to ask
  for it, which is the moment they are least likely to think of it.
- Hypothesis failure lessons now name the hypothesis in its own wording instead
  of fixed phrasing. A lesson identified only by record ID is unreadable by the
  time anyone needs it.

### Fixed

- The per-run hypothesis lesson limit no longer discards contradictions first.
  It had been ordered by recall weight, under which a `weakened` lesson
  outranks a `contradicted` one, so a run at the limit dropped exactly the
  outcome the command exists to remember. Retention is now ordered separately
  from recall, and lessons beyond the limit are reported instead of dropped
  silently.
- Failure recall now requires two shared words rather than one. Every lesson
  shares vocabulary simply by being a lesson, so a single overlap matched
  unrelated questions on words like "evidence" alone.

### Compatibility and safety

- Advisory recall cannot affect the run it accompanies. The run is persisted
  before recall is consulted, an unusable question returns nothing rather than
  raising, and any failure in the advisory path leaves the run reported as the
  success it was.
- Recall derives no lesson, writes nothing, consults no model, and leaves every
  run, hypothesis, claim, evidence record, and assessment byte-identical.
- Lesson identity still ignores wording, so lessons stored before this release
  keep the text they were written with. No storage schema changed and no data
  was migrated.
- A hypothesis is quoted on one line with whitespace collapsed and only the
  quotation shortened, so a long or multi-line hypothesis can neither forge
  report lines nor push the truth-neutrality disclaimer off the end.

### Verification

- Integration coverage exercises advisory recall at run creation, an unrelated
  question surfacing nothing, a raising advisor, absent failure memory, the
  read-only guarantee, model isolation, ordering of run before advice, the
  retention ordering and its reported overflow, hypothesis wording in lessons,
  bounded and single-line statements, and identity stability across rewording.
- Package-aware discovery passes 3,383 tests with 3 existing platform-dependent
  skips. Black, Ruff, and source MyPy pass for this release scope.

## [0.3.184] - 2026-08-25

### Added

- Failure Memory now has a separate explicit
  `failure_memory_hypothesis_store` command. It reads the durable hypothesis
  store fresh for the selected research run and derives a
  `disproving_evidence` lesson from a `weakened` appraisal or a
  `failed_hypothesis` lesson from a `contradicted` appraisal.
- `open`, `supported`, and `withdrawn` hypotheses produce no failure lesson.
  A hypothesis that is first remembered as weakened and later contradicted
  produces two stable, distinct lessons only after the two explicit commands;
  repeated commands remain idempotent.
- Hypothesis lesson identity, provenance, text, and per-run output are bounded.
  Provenance names the hypothesis and its opposing evidence without duplicate
  identifiers, and every statement remains truth-neutral.

### Compatibility and safety

- Hypothesis outcomes are never remembered from event callbacks or an
  in-memory-only change. Missing durable hypothesis support is refused, lesson
  persistence failure is reported honestly, and neither path mutates the run,
  hypothesis, claim, evidence, or assessment.
- The change adds no new lesson kind, storage schema, automatic lesson write,
  model judgement, truth decision, tool capability, or filesystem access.

### Verification

- Integration coverage exercises all five hypothesis statuses, cross-run
  isolation, stable identity, duplicate and bounded provenance, idempotency,
  the weakened-to-contradicted contract, persistence failure and restart,
  missing-store refusal, routing, and feature-off behavior.
- Package-aware discovery passes 3,368 tests with 3 existing platform-dependent
  skips. Black, Ruff, source MyPy, and whitespace checks pass for this release
  scope.

## [0.3.183] - 2026-08-24

### Fixed

- Failure Memory now derives `failed_hypothesis` only when the superseded
  authored claim was explicitly a `hypothesis`. Superseded facts, strong
  evidence, likely claims, speculation, unknowns, and contradicted claims are
  classified as `revised_claim` instead of being mislabeled as failed
  hypotheses.
- Revision wording continues to name the earlier and replacement epistemic
  states and explicitly says that replacement is not disproof. Both lesson
  kinds retain the previous belief-oriented recall weight, so the correction
  changes taxonomy rather than silently changing recall priority.

### Compatibility and safety

- The failure-lesson document remains schema v1. Existing
  `failed_hypothesis` records still load, and unknown kinds remain refused.
  Existing documents are not rewritten or migrated automatically.
- The change adds no truth decision, model judgement, hidden score, automatic
  lesson creation, research mutation, tool capability, or filesystem access.

### Verification

- Focused integration coverage parametrizes all seven epistemic states and
  verifies the kind, bounded statement, stable identity, belief classification,
  and legacy `failed_hypothesis` loading behavior.
- Package-aware discovery passes 3,356 tests with 3 existing platform-dependent
  skips. Black, Ruff, source MyPy, and whitespace checks pass for this release
  scope.

## [0.3.182] - 2026-08-24

### Fixed

- Hypothesis propose, evidence-entry, and withdrawal requests now return
  `success=false` when the hypothesis store rejects the durable write. The
  updated appraisal remains available in memory and in the response, but the
  message states that a restart may lose the change.
- Failure Memory store requests now return `success=false` when lessons cannot
  be written durably. The derived lessons remain in the current process, and an
  explicit repeated store request retries the pending write even when it adds no
  new lesson identifiers.
- A failed Failure Memory write no longer emits the normal `lessons_stored`
  event. Derivation remains observable, while durable storage is never claimed
  when it did not happen.

### Safety

- Persistence exceptions remain bounded: responses expose no exception text,
  native path, store path, or platform detail. Existing in-memory state is not
  erased or rolled back deceptively.
- The change adds no storage schema, migration, automatic retry loop, model
  judgement, research operation, filesystem/tool capability, or truth state.

### Verification

- Focused integration coverage exercises failed proposal, evidence, withdrawal,
  lesson storage, restart-loss visibility, missing success events, and an
  explicit successful retry.
- Package-aware discovery passes 3,354 tests with 3 existing platform-dependent
  skips. Black, Ruff, source MyPy, and whitespace checks pass for this release
  scope.

## [0.3.181] - 2026-08-24

### Changed

- Hypothesis appraisal now carries active user-authored trust coverage for the
  supporting and opposing source sets, including the number of assessed
  independent resources and the lowest active trust label on each side.
- A hypothesis reaches `supported` only with more than one independent
  supporting source, an active trust assessment of at least `medium` for every
  supporting source, and no opposing evidence. Unassessed or low-trust support
  remains visible but leaves the hypothesis `open`.
- Superseded source assessments no longer influence the hypothesis boundary;
  the newest active authored assessment controls each source record. Opposing
  evidence remains deliberately conservative and moves a hypothesis off the
  supported track regardless of its trust label.

### Safety

- The change derives status and trust coverage from existing persisted research
  records. It adds no model judgement, hidden numeric confidence, truth state,
  automatic assessment, storage schema, network access, or filesystem/tool
  capability.
- Supporting and opposing evidence remain separately reported and never netted;
  `supported` still never means true or confirmed.

### Verification

- Focused integration coverage includes medium-trust corroboration, unassessed
  support, low-trust support, superseded trust assessments, trust projection,
  and duplicate-resource counting.
- Package-aware discovery passes 3,351 tests with 3 existing platform-dependent
  skips. Black, Ruff, source MyPy, and whitespace checks pass for this release
  scope.

## [0.3.180] - 2026-08-24

### Added

- An explicitly composed Windows `FILESYSTEM_READ` capability in the existing
  Tool Console. It appears only when one bounded startup root and the proven
  NTFS rooted reader are both available; unsupported or failed composition
  leaves the capability absent.
- Required typed controls for one relative path, byte offset, and maximum byte
  count, followed by a second confirmation that repeats the exact scope,
  effect, path, and range before one invocation is authorized.
- A dedicated `FilesystemContentPreview` presentation contract that binds the
  central request ID beside local provenance and keeps decoded text out of
  generic values, audit lines, status text, event payloads, and `repr`.
- A literal read-only local preview panel with visible range completeness,
  timestamps, UTF-8/BOM state, untrusted-data taint, no instruction authority,
  and local-only disclosure status.

### Safety

- Root authority remains startup-only through `HYPATIA_FILESYSTEM_ROOT` or
  Hypatia's data directory. The UI exposes the opaque `workspace` identity,
  never the absolute root, and cannot hot-swap or widen it.
- The exact content tool is accepted by `ToolRuntime` only with a matching root
  identity. There is still no generic registration, discovery, factory, plugin,
  path fallback, or Linux/POSIX content implementation.
- The existing desktop single-flight worker owns execution. Cancellation and
  close discard late content without claiming to terminate native I/O; no
  retry, queue, second range, or automatic continuation is introduced.
- Prior content is cleared before a new read and after every non-success state.
  The preview uses literal Tk insertion, disables copy bindings, and offers no
  save, export, open, send, ingest, transcript, model, memory, research,
  evidence, persistence, telemetry-content, remote-disclosure, or sensitive
  override path.

### Verification

- Focused tests cover exact composition and scope matching, typed form
  validation, confirmation cancellation, exact tuple binding, request-ID
  projection, literal rendering, stale-content clearing, shared single-flight
  execution, cancellation/close disposal, and existing Tool isolation.
- Full-suite, formatting, lint, scoped typing, local package-build status,
  executable-smoke limitations, and whitespace results are recorded in
  `PROJECT_STATUS.md`. GitHub Windows/Linux checks remain commit-time evidence.

## [0.3.179] - 2026-08-24

### Added

- `FilesystemReadTool`, a production-owned but deliberately unregistered Tool
  seam that interprets one injected bounded range as strict UTF-8 text and
  returns a typed `FilesystemContentPayload` only after successful platform
  acquisition and closure.
- Explicit request parsing for one relative `path`, byte `offset`, and
  `max_bytes` within the existing 64 KiB and signed-64-bit boundaries.

### Safety

- NUL-containing ranges decline as binary; an exact UTF-8 BOM is stripped only
  at offset zero; invalid or range-split UTF-8 declines without guessing,
  replacement, retry, or automatic continuation.
- Platform refusal categories map to bounded Tool dispositions without leaking
  native errors, absolute paths, file bytes, or reader exception text.
- Corrupted non-text arguments and hostile observation access fail as bounded
  Tool results, while decoded payload text is excluded from dataclass `repr`.
- `READS_FILESYSTEM_CONTENT` remains an explicit invocation-scoped grant.
  Lifecycle events carry no path, detail, or content, and `ToolRuntime` plus the
  desktop still do not import or register `FILESYSTEM_READ`.
- Successful content remains `local_only`, `external_untrusted_data`, and has
  `instruction_authority="none"`; no model, memory, research, evidence,
  persistence, export, clipboard, remote disclosure, or operator override is
  added.

### Verification

- Focused tests cover argument bounds, authorization, lifecycle privacy,
  binary/BOM/strict-UTF-8 policy, EOF, truncation, platform failure mapping,
  source isolation, single-call behavior, and real Windows NTFS composition.
- The package-aware full suite, local Windows package build/startup smoke,
  formatting, lint, scoped typing, whitespace, and GitHub Windows/Linux gates
  are recorded in `PROJECT_STATUS.md` for the exact release commit.

## [0.3.178] - 2026-08-24

### Added

- `WindowsRootedOpen.read_range`, a production-owned but deliberately
  unregistered Windows NTFS primitive for one raw, bounded content range.
- Immutable `WindowsContentRangeObservation` provenance containing only the
  canonical relative resource, requested range, retained bytes, stable file
  size/time, truncation state and injected UTC read time.
- Bounded `read_failed`, `read_incomplete`, and `content_changed` native
  failure categories with fixed, path-free wording.

### Safety

- The final component is opened during the existing root-relative no-follow
  walk with exactly `FILE_READ_DATA | FILE_READ_ATTRIBUTES | SYNCHRONIZE` and
  `FILE_SHARE_READ`; it is never reopened from a path.
- Each invocation validates `offset` and `max_bytes` before acquisition, issues
  exactly one synchronous `ReadFile` with an explicit zero-initialized
  `OVERLAPPED` offset, and caps native capacity at `max_bytes + 1` (65,537 bytes
  maximum). The lookahead byte is discarded and never returned.
- Pre/post handle observations compare identity, file size and raw last-write
  `FILETIME`. Unexpected short reads, impossible counts, observed changes,
  native failures, and close failures return no observation.
- Every handle closes in reverse order before the raw observation returns. No
  decoded text, content payload, registered capability, desktop control, model,
  memory, research, evidence, persistence, Linux/POSIX, or content-telemetry
  integration is added.

### Verification

- Deterministic fake-API tests cover decisive offsets and byte ceilings,
  lookahead disposal, EOF forms, crossing EOF, short reads, impossible counts,
  every pre/post change dimension, bounded failures, clock validity, immutable
  observation invariants and close-before-return ownership.
- Native Windows tests cover raw ordinary/truncated/zero/EOF/non-zero ranges,
  BOM/non-UTF-8 bytes and active-writer sharing conflict. ABI tests prove the
  exact `OVERLAPPED` split and bounded EOF handling.
- The package-aware full suite, local Windows package build/startup smoke,
  formatting, lint, scoped typing and whitespace gates pass as recorded in
  `PROJECT_STATUS.md`. GitHub's Windows and Linux package workflows remain the
  independent post-push checks for the exact commit.

## [0.3.177] - 2026-08-24

### Added

- `FilesystemSensitivePathPolicy`, a filesystem-free classifier for the first
  explicit sensitive-name floor: environment files, private keys, SSH material,
  cloud and VCS credentials, package-manager authentication, browser/OS stores,
  and CI secrets.
- `FilesystemSensitiveClass`, a bounded categorical result with fixed operator
  wording and no path, basename, content, score, or raw platform detail.

### Safety

- `WindowsRootedOpen` classifies canonical admitted components before native
  acquisition and repeats the classification against components derived from
  the final safely-opened handle path after containment and identity proof.
- Matching is case-insensitive and removes Windows-ignored trailing dots and
  spaces. Contextual locations take deterministic precedence over generic file
  extensions so the future decline can name the most useful bounded class.
- A sensitive refusal carries exactly one code-owned class; every other rooted
  failure carries `NONE`. Error text names only the class and never interpolates
  the requested path or final handle path.
- Final-name classification precedes identity-mismatch reporting, so a safely
  opened sensitive name is structurally declined even when replacement also
  changed the file identity.
- The policy explicitly describes itself as a floor rather than complete secret
  detection. There is no operator override, content inspection, read API,
  capability registration, desktop control, model, memory, research, evidence,
  persistence, or telemetry integration.

### Verification

- Twenty-eight pure policy tests cover every initial class, case folding,
  Windows name normalization, contextual precedence, near misses, malformed
  internal components, fixed wording, and lack of filesystem/process authority.
- Four rooted-open integration tests cover pre-native refusal, final-handle
  reclassification and precedence, invalid final-name containment failure,
  bounded class/error consistency, and handle closure.
- The local PyInstaller build succeeds and its archive table contains both
  rooted-open and sensitive-policy modules. The final generated unsigned
  executable's local startup smoke is unverified because Windows Application
  Control blocked that artifact before process start; this gate is not reported
  as passing.
- The package-aware full-suite, packaging, formatting, lint, typing, and
  whitespace results are recorded in `PROJECT_STATUS.md` after local
  verification.

## [0.3.176] - 2026-08-24

### Added

- A production-owned `WindowsRootedOpen` foundation that opens one admitted
  relative component at a time beneath a held Windows root handle, without
  reading file content or registering a capability.
- A bounded `WindowsRootedOpenFailure` taxonomy and opaque
  `WindowsOpenedFile` context view exposing only the root identifier, component
  count, active state, and the invariant that zero content bytes were read.

### Safety

- Native APIs are loaded lazily from fixed Windows system-DLL names after the
  platform gate. The first supported boundary is local NTFS; unsupported
  filesystems and unavailable proofs fail closed with no path or OS message.
- Every component uses `NtCreateFile` relative to its held parent with reparse
  processing disabled. The root, intermediate directories, and final file stay
  open through reparse, kind, root-identity, final-containment, and
  final-identity proof.
- Root, intermediate, and final handles request attributes and synchronization
  only, so a component replaced by a file does not gain content-read authority.
  No content read/write/process API, content payload, Tool Runtime registration,
  desktop, model, memory, research, evidence, persistence, telemetry, or
  experiment dependency is introduced.
- Every acquired native handle is closed in reverse order. A close failure
  prevents a successful context exit, and a non-success `NtCreateFile` result
  carrying a handle is closed defensively before its bounded failure is raised.

### Verification

- Thirty-seven new deterministic and native tests cover ordinary acquisition,
  Windows API and NTFS gates, traversal, root/parent/final replacement,
  junctions, kind and identity changes, containment, handle lifetime,
  close-failure behavior, error privacy, lazy packaging, and runtime isolation.
- The nine-test isolated prototype remains green as independent evidence.
- The normal packaged-desktop startup imports the inert module before composing
  the application, proving PyInstaller includes it without constructing it or
  registering a capability.
- The local PyInstaller Windows onedir package builds successfully and its
  hidden-window startup smoke creates the expected session registry.
- The package-aware full-suite, formatting, lint, typing, and whitespace
  results are recorded in `PROJECT_STATUS.md` after local verification.

## [0.3.175] - 2026-08-24

### Added

- A required, immutable `request_id` on `ToolExecutionOutcome`, carried beside
  the tool-authored result rather than inside it.
- A shared request-identifier validator with a 100-character ceiling and a
  deliberately narrow ASCII token alphabet.

### Safety

- `ToolExecutionService` creates and validates one identifier before emitting
  any lifecycle event, then carries that exact value through successful,
  unknown-capability, unauthorized, cancelled, declined, and failed outcomes.
- Invalid identifier-factory output stops before an event is emitted or a tool
  implementation is reached. Validation errors contain no rejected identifier.
- `ToolInvocation`, `ToolResult`, and `FilesystemContentPayload` carry no
  request identifier, so a tool or local file cannot author its own provenance.
  The ordinary result-only execution API remains unchanged.
- No filesystem read, runtime registration, desktop presentation field, model
  context, memory, research, evidence, persistence, or telemetry content path
  is introduced.

### Verification

- Nine focused tests cover bounds and immutability, unsafe token refusal,
  success/event correlation, every terminal branch, per-invocation generation,
  fail-before-telemetry behavior, and result/payload isolation.
- The package-aware full local suite contains 3,198 passing automated tests,
  with the same three platform-dependent skips.
- Black and Ruff pass across production and test sources; whitespace validation
  passes. MyPy passes across all production sources and the focused request-ID
  contract test. The separately recorded pre-existing full-test typing debt
  remains outside this milestone.

## [0.3.174] - 2026-08-24

### Added

- `ToolCapability.FILESYSTEM_READ` and
  `ToolEffect.READS_FILESYSTEM_CONTENT` as explicit but still-unregistered
  declarations. Metadata authority does not imply content authority.
- An optional, typed `FilesystemContentPayload` field on `ToolResult`, separate
  from the existing bounded structured `values` channel.

### Safety

- Content is accepted only on a successful `COMPLETED` result for
  `FILESYSTEM_READ`; refusals, declines, failures, cancellations, every other
  capability, and results with structured values must carry no content.
- The content field is excluded from `repr`, `ToolResult.lines()`, and generic
  lifecycle events. Sentinel tests prove neither file text nor its relative
  resource enters those disclosure paths.
- `ToolExecutionService` revalidates the payload type and requires the content
  effect in both the resolved descriptor and this invocation's explicit grant.
  A metadata-only grant never reaches a content-declaring test tool, and a tool
  that returns content without declaring the effect is rejected centrally.
- `ToolRuntime` still registers no content capability. No file is opened or
  read; no desktop, model, memory, research, evidence, persistence, or telemetry
  content path is introduced.

### Verification

- Fifteen new focused tests cover declaration separation, runtime absence,
  success-only result construction, type-smuggling defence, central effect
  enforcement, metadata-grant isolation, representation privacy, lifecycle
  privacy, and unchanged structured results.
- The package-aware full local suite contains 3,189 passing automated tests,
  with the same three platform-dependent skips.
- Black and Ruff pass across production and test sources; whitespace validation
  passes. MyPy passes across all production sources and both focused content
  contract test modules. The separately recorded pre-existing full-test typing
  debt remains outside this milestone.

## [0.3.173] - 2026-08-24

### Added

- `FilesystemContentPayload`, an immutable and slotted contract for one future
  bounded local-file text range. It records the configured root identity,
  canonical relative resource, byte range, observed file size and modification
  time, read time, truncation state, and strict UTF-8/BOM interpretation.
- A 64 KiB per-invocation payload ceiling and a `2^63 - 1` maximum offset,
  independent of the existing structured `ToolResult.values` limits.

### Safety

- The payload is inert: no production module imports it, no capability or
  effect exists for content, and no tool, runtime, desktop, model, memory, or
  research path can construct or receive it.
- Source kind, file kind, UTF-8 encoding, `external_untrusted_data` taint,
  `none` instruction authority, and `local_only` disclosure class are fixed
  code-owned fields rather than constructor inputs.
- Raw byte count is cross-checked against strict UTF-8 text, including explicit
  three-byte BOM accounting. Invalid Unicode, mismatched counts, non-boolean
  flags, naive timestamps, non-canonical references, and inconsistent
  truncation fail at construction.
- A source guard asserts the contract contains no filesystem read, process,
  Tool Layer integration, model, or memory operation; another guard asserts no
  production module uses the contract yet.

### Verification

- Thirteen focused tests cover exact bounds, zero-byte EOF ranges, multi-byte
  UTF-8, BOM handling, immutable fixed labels, whole-number type strictness,
  timestamp provenance, canonical resources, truncation truth, taint alignment,
  and production isolation.
- The package-aware full local suite contains 3,174 passing automated tests,
  with the same three platform-dependent skips.
- Black and Ruff pass across production and test sources; whitespace validation
  passes. MyPy passes across all production sources and the new focused test.
  A broader MyPy sweep of the pre-existing test suite remains non-green with
  354 errors in 35 existing test files; this milestone introduces none of them
  and does not describe that gate as passed.

## [0.3.172] - 2026-08-24

### Added

- `filesystem_metadata`, reporting the kind, modification time and — for a
  regular file only — the byte size of one named entry in the authorized root.
- `FilesystemEntryKind.from_status` and `has_byte_size`, so directory scanning
  and single-entry lookup classify entries through one implementation.

### Safety

- Reuses the existing `READS_FILESYSTEM_METADATA` effect. No broader effect was
  introduced, and a `READS_LOCAL_STATE` grant does not authorize it.
- Reuses `FilesystemRoot.locate` for admission rather than re-deriving path
  policy. Tests assert the tool contains no second implementation.
- Model A for links: because `locate` checks every component including the last,
  a symlink or junction entry is refused rather than described. No target is
  ever followed, resolved, or reported.
- The reported stat is the stat that was checked. One `lstat` produces both the
  indirection re-check and the returned fields.
- No file contents. Source-level tests assert the implementation contains no
  open, read, hash, mime-sniff, mmap, walk, glob, scandir, mutation or process
  API, and no owner, ACL, inode or device field.
- A directory is given no size at all rather than a misleading one; `kind`
  explains the absence. No recursive size and no child enumeration.
- Outside-root requests are refused lexically, costing zero syscalls, so the
  existence of anything outside the root is never probed or disclosed. A
  missing entry *inside* the root stays distinguishable, which the operator
  could learn by listing anyway.
- Both filesystem capabilities register together under one configured root, or
  neither does.

### Taxonomy

- Refused paths, unknown arguments and already-missing entries are
  `INVOCATION_DECLINED`. An entry that vanished or changed after admission, and
  an unreadable one, are `EXECUTION_FAILED`.
- `modified_utc` is UTC ISO 8601 at whole-second precision, because filesystems
  disagree below a second and a volume-dependent field cannot be compared.

### Verification

- The package-aware full local suite contains 3,152 passing automated tests.
- One hundred and one new tests cover the descriptor and effect reuse, file and
  directory semantics, timestamp format, every delegated path refusal, the
  existence-oracle decision including a syscall count proving outside paths are
  never probed, real Windows junction behaviour, the post-admission re-check,
  the failure taxonomy, telemetry privacy with distinctive sentinels, bounding,
  console usage, and chat/research isolation.
- Three skips: two pre-existing symlink skips and one new one, all because
  creating a symlink on this machine needs elevation and fails with
  WinError 1314. Real junctions cover the unprivileged case.

## [0.3.171] - 2026-08-24

### Changed

- `ToolFailureKind.TOOL_FAILED` is replaced by `INVOCATION_DECLINED` and
  `EXECUTION_FAILED`. A tool that read a request and would not take it, and a
  tool that accepted it and could not finish, are no longer the same fact.
- `ToolResult` carries a `ToolDisposition`, so which of the two happened is
  declared by the tool rather than inferred at the seam.

### Added

- `ToolDisposition`: `NOT_REACHED`, `COMPLETED`, `DECLINED`, `FAILED`, with
  `entered_the_tool`, `attempted_the_work`, and `worth_reformulating`.
- `ToolResult.declined()` and `ToolResult.failed()` constructors.
- `ToolFailureKind.attempted_the_work`, `concerns_the_request`, and the single
  `for_disposition()` translation point.
- `ToolRunStatus.DECLINED` and `ToolRunStatus.EXECUTION_FAILED`, replacing the
  coarse `REFUSED`.

### Safety

- The category never comes from prose. Tests assert no classifier compares
  against `detail`, lowercases anything, or matches a message, and the test
  doubles for the two cases say exactly the same sentence so any implementation
  that read the wording would fail rather than pass.
- `performed` keeps its meaning — the implementation was entered — and is now
  defined against the disposition, so a result claiming to have failed without
  having been reached cannot be constructed.
- Authorization stays separate. An unauthorized invocation reports
  `NOT_REACHED`, `performed=False`, and still emits no `tool.started`.
- `filesystem_list` keeps every bounded refusal reason. Its path refusals are
  declines, and `UNREADABLE` is classified as a failed attempt, because the
  filesystem refusing a well-formed question is not the caller asking badly.
- A raised failure still drops its exception text. The result detail is a fixed
  sentence and no path, argument, or `WinError` reaches telemetry.

### Verification

- The package-aware full local suite contains 3,051 passing automated tests.
- Forty-two new tests cover the four canonical outcomes as mutually distinct
  states, the `performed`/`succeeded`/`disposition` matrix and its contradictory
  combinations, lifecycle fields, absence of prose classification, the real
  tools classifying themselves, and the console rendering declined and
  execution-failed as different statuses under identical wording.

## [0.3.170] - 2026-08-24

### Added

- A `Tools` desktop tab: the first way to run a capability in the running
  application. An operator selects a capability, reads its declared effects,
  fills in typed arguments, and authorizes one run.
- `ToolRuntime`, which composes the production registry and execution service
  by construction, and `FilesystemRootPolicy`, which decides the filesystem
  scope from operator configuration.
- `ToolConsoleController` plus `ToolConsoleEntry`, `ToolArgumentSpec`,
  `ToolArgumentKind`, `ToolRunStatus`, and `ToolRunView`.

### Changed

- `desktop_main` composes the tool runtime and passes a console to the window.
- The tool-layer isolation guard now names who may reach the layer instead of
  asserting nobody does. It gained assertions rather than losing them.

### Safety

- The operator is the only authority added. A model cannot authorize, a chat
  message cannot execute, research text cannot execute, and a capability name
  or filesystem path in prose executes nothing.
- Authorization is invocation-scoped and never stored. `run` takes an
  `authorized` flag defaulting to False; one press authorizes one run.
- There is no auto-approve, remembered grant, allow-all, or wildcard.
- The grant is exactly the resolved tool's declared effects, never a superset,
  and never carried between capabilities.
- Only registered capabilities appear and only registered names resolve.
  Selection is a lookup over the registry, never a constructor, an import, or
  a module path.
- Unknown, missing, and malformed arguments are rejected before an invocation
  exists. There is no free-form argument kind.
- The window imports no tool-layer type at all; the console passes plain data
  across that boundary. Two named modules hold tool authority, not a package.
- The filesystem scope comes from `HYPATIA_FILESYSTEM_ROOT` or the desktop's
  own data directory. A drive root, a filesystem root, and the home directory
  are refused. With no root, no filesystem capability is registered.
- Scope is shown as `root_id`. No absolute path reaches the catalogue, the
  audit view, or any lifecycle event.
- Results are read from the execution outcome, so a refusal keeps the tool's
  own words and is never presented as success.
- Paging stays explicit: one operator action is one bounded invocation, and
  `MAX_TOOL_VALUES` is unchanged at 20.

### Verification

- The package-aware full local suite contains 3,009 passing automated tests.
- One hundred and three new tests cover the catalogue against the real
  registry, effect disclosure, explicit and non-persisting authorization,
  argument validation, result fidelity, the audit view, paging, scope privacy,
  root policy, chat and research isolation, and execution with no model
  present.

## [0.3.169] - 2026-08-24

### Added

- `filesystem_list`, the first capability whose argument selects its target. It
  lists one directory level inside one operator-configured root.
- `ToolEffect.READS_FILESYSTEM_METADATA`, a separate effect rather than a reuse
  of `READS_LOCAL_STATE`.
- `FilesystemRoot`, `FilesystemPathRefusal`, and `FilesystemEntryKind`.

### Security

- The root is operator configuration and never an argument. `root` is not an
  accepted argument name, and a tool cannot be constructed without a root.
- Containment is decided on the resolved path. A sibling directory whose name
  merely begins with the root's name passes a string prefix check and is
  refused here.
- Absolute, rooted, drive-qualified, UNC, extended-length, device-namespace,
  NTFS stream-syntax, reserved-device, and over-deep paths are all refused,
  under both Windows and POSIX path semantics regardless of host.
- Links are never followed, and the check runs on every component rather than
  the last. What counts as a link is the reparse-point attribute, not
  `is_symlink`: a Windows junction answers False to that question while
  `scandir` reports it as an ordinary directory, and creating one needs no
  privilege while creating a symlink needs elevation.
- Reusing `READS_LOCAL_STATE` would have turned every existing grant of it into
  authority to enumerate the disk. A local-state grant is refused.
- No detail quotes the requested path, the root path, or any `OSError` text,
  whose Windows form interpolates the path it failed on.

### Bounding

- A listing returns a page: five values describe the directory and fifteen carry
  entries, which is exactly the existing `MAX_TOOL_VALUES` budget.
  `MAX_TOOL_VALUES` was not raised, because that bound protects every tool.
- Directory-level and page-level incompleteness are reported separately as
  `entries_exceeded` and `more_pages`, so neither can be read as the other.
- The whole directory level is collected before sorting, so paging is stable:
  an entry's page does not depend on the order the filesystem returned names in.

### Privacy

- No lifecycle event carries a path, a path fragment, or an entry name. Verified
  against a real listing and by sentinel-named directories on both the success
  and refusal paths.

### Verification

- The package-aware full local suite contains 2,906 passing automated tests.
- Eighty-seven new tests cover root configuration, listing, non-recursion,
  paging determinism and completeness, every rejected path form, real directory
  junctions, effect authorization, error disclosure, and telemetry privacy.
- Two symlink tests skip with a stated reason where the platform refuses to
  create one without elevation; real junctions cover the unprivileged case.
- No test requires a network.

## [0.3.168] - 2026-08-24

### Added

- A Simple research mode: one question box, a guided status ladder, readable
  source cards, and a single `Use this source` action. It is the default
  Research tab.
- `SimpleResearchStep`, `SimpleResearchActivity`, `SimpleSourceCard`,
  `SimpleResearchPhrasebook`, and `SimpleResearchReadModel` — a Tk-free,
  read-only projection over canonical research state.
- A `Research this` offer in Chat, shown only after chat has reported that it
  did not research something.

### Changed

- The existing detailed Research tab is now labelled `Research (Advanced)`.
  Nothing was removed from it.

### Safety

- No second research engine. Every state change goes through the existing
  controller, the existing candidate preview, the existing confirmation, and
  the existing guarded loader.
- A step is derived from a persisted run and has no setter, so no button press
  can advance it. In-flight work is a separate `SimpleResearchActivity` type
  whose values cannot collide with a step.
- After a load, the run is re-read from the store rather than inferred from the
  response, and only the run matching the Simple context is adopted.
- `INDEXED_WITHOUT_RUN` renders as "Indexed locally, but not added to this
  research" and never as "Loaded"; the ladder does not advance for it.
- A discovered candidate is never shown as fetched, an accepted source is never
  shown as evidence, and evidence is never shown as a verified claim.
- Candidate cards are deduplicated by canonical resource identity, so one
  resource listed twice is not presented as two sources.
- Simple mode keeps its own run context, separate from the Advanced selector,
  so a source can never attach to a run the user did not create here.
- `Research this` creates nothing and fetches nothing. It fills the question
  box, leaving the start as an explicit press, so conversational text never
  becomes authority to run anything.
- All failure text is deterministic table lookup in English and Turkish. No
  model phrases any of it. Technical codes are moved to Advanced details, not
  hidden.

### Verification

- The package-aware full local suite contains 2,819 passing automated tests.
- One hundred new tests cover step derivation, activity separation, card
  projection and deduplication, every load stage's plain sentence in both
  languages, identifier hiding and exposure, run-context isolation, the
  preview-confirm-load routing, canonical refresh after a load, and the chat
  handoff creating nothing.
- No test requires a network. Discovery and fetching are controlled doubles.

## [0.3.167] - 2026-08-24

### Added

- `TextStatisticsTool`, the first tool that takes an argument. It reports four
  counts over text supplied with the call and reads nothing else.
- A structural guard asserting that no module outside `src/tools` imports the
  tool layer, names the execution service, or constructs an invocation.

### Safety

- The tool is pure: no file, clipboard, network, environment, process state, or
  model, and nothing mutated. It declares only `COMPUTES_LOCALLY`.
- Purity earns no exemption. An empty grant refuses it before it starts, and a
  grant of an unrelated effect refuses it too.
- It accepts exactly one argument name. No alias for `text` is recognised.
- Result details are fixed sentences. Neither the text nor the name of an
  unexpected argument is quoted back, because a message is the easiest place for
  input to escape and the hardest place to notice it did.
- The result carries derived counts only. A sentinel string is asserted absent
  from result values, result details, and every lifecycle payload.
- Bad arguments are a tool failure, not an authorization refusal: the tool ran,
  so the outcome reports `performed=True` and the event reports
  `refused_before_execution=False` after `started`.
- A non-string argument is refused when the invocation is built, and the tool
  independently declines to coerce one that bypasses construction.

### Counting

- `character_count` is Unicode code points, `word_count` is whitespace-separated
  non-empty segments, `line_count` is Python line boundaries, and
  `non_whitespace_character_count` is code points that are not whitespace.
- Line counting treats a newline, a carriage return, and a CRLF pair identically
  on every platform, so the same text counts the same on every machine.

### Verification

- The package-aware full local suite contains 2,719 passing automated tests.
- Fifty-five new tests cover the descriptor and its truthful effects, the empty
  string, spaces, tabs, trailing and lone newlines, blank lines, CRLF, Turkish
  and non-Latin text, missing and unknown and aliased arguments, non-string
  values on both sides of construction, result and telemetry sentinel absence,
  both lifecycle orderings, registry ordering across two tools, and the
  isolation guard.
- An application-level run confirms all four paths: success, missing argument,
  unknown argument, and refusal under an empty grant.

## [0.3.166] - 2026-08-24

### Added

- `ToolEffect.COMPUTES_LOCALLY`, so a tool that only transforms data it was
  handed can declare that truthfully instead of borrowing an effect it does not
  have.

### Changed

- `ToolInvocation` and `ToolResult` now check that argument and value pairs are
  actually strings. A length bound alone admitted an empty list or dict, because
  both have a length.

### Safety

- The blank-declaration guard in `ToolDescriptor` is kept, not relaxed. An empty
  effect set is a subset of every grant, so making it legal would turn the
  declaration nobody filled in into the only one no authorisation could refuse.
- Declaring purity explicitly keeps "authorise nothing" and "authorise pure
  computation" different sentences. A pure tool is refused under an empty grant.
- `COMPUTES_LOCALLY` is neither irreversible nor observable outside the machine,
  so a tool declaring only it is read-only and reaches nothing.
- Granting computation grants nothing else: a clock tool declaring
  `READS_LOCAL_STATE` is refused under a computation-only grant.
- Rejecting a non-string argument is a construction-time refusal, so a
  mistyped value never reaches a tool and is never coerced into text.

### Verification

- The package-aware full local suite contains 2,664 passing automated tests.
- Fourteen new tests cover the retained empty-set refusal, the new effect's
  authorization behaviour in both directions, the closed empty-container hole,
  non-string names and values on both the argument and result side, and the
  still-valid empty string.

## [0.3.165] - 2026-08-24

### Added

- `ClockReadTool`, the one concrete tool of this milestone. It reports the
  current UTC time as four structured values through the full tool path.

### Removed

- `ToolFailureKind.INVALID_ARGUMENTS`, which had no producer. Malformed
  arguments are refused when the invocation is constructed, and unsupported ones
  are a tool discovering by looking, which is a failure rather than a refusal.

### Safety

- The tool declares exactly what it does: it reads local state and nothing else.
  Tests assert each absent effect individually — no write, no network, no model.
- It touches no network, no filesystem, no process, and no model, and mutates
  nothing.
- The clock is injected, so no test depends on the second it ran in. A naive
  datetime from the clock source is refused rather than guessed at, and a
  non-UTC one is normalised.
- It accepts no arguments. An unsupported argument yields a
  performed-but-unsuccessful result, because the tool was reached and declined.
- The clock tool is not exempt from the gate. A test invokes it with an empty
  grant and asserts it is refused before starting, since a trusted-tool shortcut
  for something harmless is the shortcut a later tool would inherit.
- Only `clock_read` is registered. No filesystem, terminal, process, browser,
  network, or generic execution capability exists, and nothing is wired into
  ordinary chat.

### Verification

- The package-aware full local suite contains 2,650 passing automated tests.
- Eighteen new tests cover the descriptor and its truthful effects, injected and
  normalised clocks, refused ambiguous times, argument rejection, and the
  end-to-end path including lifecycle order, the gate applying to the clock
  tool, cancellation, unknown capabilities, and telemetry carrying no time
  value.
- An application-level run confirms the path: granted, it emits requested,
  authorized, started, completed and returns the injected time; ungranted, it
  emits requested and failed with `unauthorized_effect` and never reaches the
  tool.

## [0.3.164] - 2026-08-24

### Added

- `ToolEvents` publishes six lifecycle events on the existing event bus:
  `tool.requested`, `tool.authorized`, `tool.started`, `tool.completed`,
  `tool.failed`, and `tool.cancelled`. No second event system was created.

### Safety

- The events are required to be true. `authorized` is emitted only after the
  gate allowed the call and `started` only when the implementation is about to
  run, so a refused invocation produces neither — tests assert the absence of
  both, since those are the two events that would make a refusal read as a run.
- A cancelled invocation reports cancellation rather than failure, and a tool
  that ran and failed reports failure after starting with `performed` true.
- Payloads are bounded now, while the only tool reads a clock. Arguments and
  returned values are counted, never carried. Tests plant a secret in an
  argument, a returned value, and a raised error, and assert none of the three
  appears in any payload.
- What is carried: a request id correlating one invocation, the capability, the
  declared and authorized effects, `performed`, `succeeded`, and a bounded
  failure kind.

### Verification

- The package-aware full local suite contains 2,632 passing automated tests.
- Nineteen new tests cover the exact event order for success, unknown
  capability, unauthorized effects, cancellation, a raising tool and a failing
  tool, once-only emission, request correlation, a service without a bus, and
  the bounded-payload rules.

## [0.3.163] - 2026-08-24

### Added

- `ToolRegistry` binds each invocable capability to exactly one tool, reading
  the capability from the tool's own descriptor.
- `ToolExecutionService`, the single seam every invocation passes through:
  resolve, authorize, invoke, report.
- `ToolFailureKind` and `ToolExecutionOutcome`, which keep refusals and failures
  apart and carry resolution and authorization alongside the result.
- The existing Tool Layer abstractions — `ToolCapability`, `ToolEffect`,
  `ToolDescriptor`, `ToolInvocation`, `ToolResult`, and the `Tool` protocol —
  are adopted unchanged as the foundation.

### Safety

- Authorization is central and fail-closed. A tool never checks its own grant;
  the service compares declared effects against the invocation's authorized
  effects before the implementation is reached.
- There is no bypass, no trusted-tool shortcut, and no ambient permission. A
  grant applies to one invocation and does not carry into the next.
- The registry has no fallback. An unregistered capability resolves to `None`,
  never to a similar tool, and the registry cannot invoke anything itself.
- A refused invocation never reaches the implementation, proven by a tool that
  counts its calls rather than by inspecting the returned result.
- Failure kinds are bounded and a raised error becomes `TOOL_FAILED` with a
  fixed sentence, so no exception text reaches a consumer.
- The outcome refuses to disagree with itself: no performed work without
  authorization, no performed work after a pre-execution refusal, and no
  failure kind on a successful result.
- No concrete tool is registered, nothing is wired into ordinary chat, and no
  filesystem, process, network, or model capability exists.

### Verification

- The package-aware full local suite contains 2,613 passing automated tests.
- Twenty-five new tests cover registration, duplicates, `NONE`, unknown
  capabilities, the absence of fallback, determinism, exact and partial
  authorization, empty grants, unreached implementations, cancellation, bounded
  failure kinds, the performed/succeeded distinction, and the absence of bypass
  methods.

## [0.3.162] - 2026-08-24

### Added

- Knowledge reconciliation classifies every indexed resource as attached,
  knowledge-only, or a broken reference, and reports counts for resources,
  documents, and each classification.
- `knowledge_reconciliation_report` and `knowledge_only_list` intents, and one
  bounded `knowledge_reconciliation.reported` event.

### Safety

- Read only. There is no delete, prune, or garbage-collect path, and tests
  assert neither the reconciler nor the service exposes a method whose name
  contains one, and that the run store and index are byte-unchanged after
  repeated reconciliation.
- Knowledge-only is presented as a normal state rather than a cleanup list. The
  user-facing report never calls it an orphan; that word is reserved for a run
  naming a document the index does not hold, which is the only genuine
  structural breakage here.
- Resources are keyed by identity, so the same page stored twice is one resource
  holding two documents rather than two resources.
- A record cannot contradict its classification: an attached resource must name
  its runs, a knowledge-only one must name none, and a broken reference names a
  run but no document.
- Event payloads carry counts plus explicit `documents_removed` and
  `references_repaired` zeroes, and deliberately no identity or title.

### Verification

- The package-aware full local suite contains 2,588 passing automated tests.
- Twenty-eight new tests cover the vocabulary and its consistency rules, empty
  machines, attached and knowledge-only classification, duplicated resources,
  broken references and their exclusion from indexed counts, shared resources
  across runs, read-only behaviour, the absence of removal methods,
  presentation, events, and engine routing with and without research
  persistence.

## [0.3.161] - 2026-08-24

### Fixed

- Displayed research counts did not refresh after a source was accepted. The
  interface now re-reads the affected run when the event bus reports canonical
  acceptance.

### Added

- `ResearchStateRefreshSignal` records which runs changed canonically and never
  records a count. It is thread-safe, because events arrive on the worker thread
  while the interface drains on its own event-loop thread.

### Safety

- The event says which run changed; every number shown is read back from the
  store. A payload can never put a count on screen that the store does not hold.
- Only canonical acceptance marks a run. A local index, a refused attachment,
  and a cancellation change no run, so none of them refresh anything — tests
  assert each case leaves the displayed count unchanged.
- The `attached_to_run` flag is checked as well as the event name, so a payload
  that does not claim acceptance cannot trigger a refresh under an acceptance
  name.
- Draining is destructive and idempotent, so a retry after a failed attachment
  refreshes exactly once and a duplicate load does not double-count.
- No polling was added. The existing Tk event-loop poll drains the signal.

### Changed

- Two tests encoded obsolete proxies rather than guarantees. One built bare
  windows through `object.__new__`; the signal is now declared at class level so
  focused tests stay safe. The other asserted exactly one container resolution;
  it now asserts the Brain and the event bus both come from the same container.

### Verification

- The package-aware full local suite contains 2,560 passing automated tests.
- Sixteen new tests cover signal semantics, self-subscription, and the full
  chain driven through the real ingestion pipeline: zero to one, index-only,
  failed attachment, retry, duplicate load, two acceptances, and a replay
  asserting no event order can show a count the store lacks.

## [0.3.160] - 2026-08-24

### Added

- `SourceIngestionEvents` publishes every real transition of a source load:
  validation, fetch, index, and research-run attachment each start and complete,
  and a stop is announced as cancelled or failed.
- Every event of one load shares an attempt identifier, so a subscriber can
  follow a single ingestion without inferring which events belong to it.

### Safety

- The stage vocabulary is reused, not duplicated. Events carry `SourceLoadStage`
  values, so the stream cannot drift from the transaction it describes.
- An event fires only after the transition it names, except the `*_started`
  events, which claim nothing about outcome.
- The payload is machine-readable only: identifiers, a stage, a status,
  booleans, and a bounded failure kind. No prose, no translation, no exception
  message.
- Indexed locally still does not mean accepted into a run. The two facts are
  separate fields, only `ACCEPTED_INTO_RUN` carries `attached_to_run`, and a
  test asserts no event of an index-only load claims attachment.
- Safe-failure metadata reports what happened: a refused fetch with a bound run
  reports the recorded failure, and the same refusal without a run reports that
  none was recorded.
- Evidence recording is deliberately outside this pipeline. It is a separate
  authored transaction, and announcing it here would invent progress.

### Changed

- One existing test asserted zero events as a proxy for "no side effects". It
  now asserts the guarantee it meant — no conversation, memory, or model work —
  by requiring the absence of `brain.*` events and that every emitted event
  belongs to the ingestion subsystem.

### Verification

- The package-aware full local suite contains 2,544 passing automated tests.
- Twenty-five new tests cover the full successful order, exactly-once emission,
  attempt correlation, index-only distinctness, refused fetch, index failure,
  attach failure, duplicate documents, cancellation, retry, safe-failure
  reporting, payload shape, and a service constructed without a bus.

## [0.3.159] - 2026-08-24

### Added

- `HYPATIA_RESEARCH_USER_AGENT_CONTACT` lets an operator append their own
  contact to the research agent string, for sites that ask non-browser clients
  to name one. Hypatia does not invent a contact on anyone's behalf.

### Safety

- The override cannot impersonate a browser. A value containing a browser marker
  is refused, as are overlong values and anything carrying a line break, so the
  header cannot be used for injection either.
- The default agent string was inspected and left unchanged: it names the
  product and version, carries no browser marker, no tracking, and no machine or
  user identity. A 403 remains a 403; no anti-bot control is bypassed.

### Verification

- The package-aware full local suite contains 2,519 passing automated tests.
- Eight new tests cover the default string, the absence of impersonation and
  identity, contact appending, blank contacts, browser impersonation, overlong
  values, and header injection.
- Live network validation, run against the real internet rather than doubles: a
  direct public HTTPS page travelled the whole ingestion path — validation,
  fetch of 32,585 characters, local index, canonical acceptance, evidence
  record — ending at one accepted source, with assessment and claim correctly
  unperformed. Crossref discovery returned five real candidates including a 2026
  paper.
- Crossref's `link` metadata was checked against the live API rather than
  assumed. It returns plain-HTTP PDF URLs, which the HTTPS and content-type
  boundaries refuse, so exposing it would not make DOI loading work under the
  current safety policy and was deliberately not added.

## [0.3.158] - 2026-08-24

### Fixed

- The same resource stored under two document IDs read as two independent
  sources to everything that counted support, so a claim resting on one page
  could satisfy the corroboration ceiling and a hypothesis could look supported
  by sources it did not have. Support is now counted over resource identities.

### Added

- `SourceIdentity`, a conservative canonical identity for a source URL:
  lowercased scheme and host, dropped default port, dropped `www.` prefix, one
  dropped trailing slash. The query string is kept, path case is kept, and
  titles are never compared.

### Safety

- Storage stays history-preserving. No record is merged, rewritten, or deleted;
  only counting changed. A test asserts both records and both evidence entries
  survive.
- Normalisation is conservative because the errors are asymmetric: a missed
  merge overcounts support, which the audit flags, while a wrong merge silently
  discards a genuinely independent source, which nothing would flag.
- Claim calibration, hypothesis appraisal, and thin-claim detection count
  resources. Two different pages on one host still corroborate; the same page
  twice does not.
- Source reputation counts a resource once toward its standing, so a duplicate
  cannot reach a standing on its own. Accepted-record counts stay as stored.
- The audit's duplicate finding stays and now matches on identity rather than
  exact URL. It is redundant with the protection above, which is why it is worth
  keeping: a check that is redundant today is the one that notices a regression.

### Verification

- The package-aware full local suite contains 2,511 passing automated tests.
- Twenty-one new tests cover identity equivalence and non-equivalence
  table-driven, calibration and hypothesis corroboration for duplicated versus
  distinct pages, thin-claim detection, reputation sample counting and standing
  thresholds, audit detection of equivalent forms, and the preservation of every
  stored record.

## [0.3.157] - 2026-08-24

### Fixed

- An evidence reply printed "Sources accepted: 0" and then said "Sources exist
  but no evidence record does". The branch tested whether anything at all had
  been recorded, so a run with no sources fell past the empty case. The prose is
  now chosen from the same two counters the reply prints.
- Deterministic honesty responses were composed in English regardless of the
  question, so a Turkish request received a wall of English that read like a
  developer diagnostic. The sentences are now looked up per language, with the
  plain statement first and the counters under a details heading.
- Asked whether it could reach a URL, ordinary chat let the model answer and the
  model claimed the page was not accessible — a claim about someone else's server
  made without contacting it. Such a message is now recognised and answered
  deterministically.

### Added

- `ResponseLanguage` and `detect_response_language`, a bounded hint table with
  English as the fallback.
- `HonestyPhrasebook`, the fixed honesty sentences per language, with a missing
  key falling back to English rather than being approximated.
- `LiveInformationRequestKind.URL_ACCESS`, matched only when a message contains
  a URL *and* asks about reaching it.

### Safety

- The honesty statements remain composed in code and are never phrased by a
  model. Only their translation is looked up.
- The URL reply says three separate things: the link was not opened in this
  turn, whether the site is reachable is unknown because nothing tried, and the
  Research workflow is how to check. A test asserts no phrase in any language
  contains inaccessible, unavailable, offline, blocked, or their Turkish
  equivalents.
- Both signals are required before a turn is treated as a URL request. A pasted
  link used as context is not hijacked, and tests cover both directions.
- Ordinary chat still reaches no network; the new kind changes what is said, not
  what is done.
- Language hints are restricted to tokens absent from the other language, after
  an early version turned English questions containing "site" or "var" into
  Turkish answers.

### Verification

- The package-aware full local suite contains 2,490 passing automated tests.
- Twenty-eight new tests cover language detection including the shared-word
  regression, phrasebook completeness and fallback, the five evidence-state
  combinations table-driven, URL access detection in both languages, the
  refusal to judge reachability, and statement-before-counters ordering.

## [0.3.156] - 2026-08-24

### Fixed

- A source load with no research run bound indexed the document into local
  knowledge and reported "Research source loaded" with a real document ID, while
  the run's canonical state correctly showed zero accepted sources and zero safe
  failures. Nothing had failed; one word was covering two different outcomes.
  Every load now reports the stage it reached, and an indexed-only load says
  plainly that no research run accepted it.

### Added

- `SourceLoadStage` names how far a load got: fetch refused, index failed,
  content persist failed, run attach failed, indexed without run, accepted into
  run, cancelled. It distinguishes a stage that created a local document, one
  that rolled its work back, and the single stage that means the run accepted
  the source.
- `ResearchSourceAcceptanceResult.stage` and `attached_to_run`, which is the
  question callers asking "was it accepted?" actually mean.
- `BrainResponse.source_load_stage`, so a caller can branch on the stage rather
  than parse prose.

### Safety

- The acceptance result refuses a stage that disagrees with it: reporting
  acceptance into a run without a run, carrying a run without the accepted
  stage, or naming an indexed document that does not exist.
- The reply leads with the stage rather than the presence of a document. An
  indexed-only load is headed "Indexed locally, but NOT accepted into a research
  run", labels the identifier as a local document ID, and states that no
  evidence can be recorded from it.
- Partial transaction points are covered end to end: index succeeds and
  attachment fails leaves the run byte-honest and rolls the local document back;
  content persistence failure names its own stage; a retry after a failed
  attachment still succeeds exactly once.
- A test asserts no evidence can be recorded against a run from a document that
  was only indexed.
- The desktop guard that selects an accepted source only when the returned run
  confirms it now has a regression test.

### Verification

- The package-aware full local suite contains 2,462 passing automated tests.
- Thirty new tests cover the stage vocabulary, result consistency, every partial
  transaction point, reporting for each successful and failed stage, and the
  desktop capture guard.

## [0.3.155] - 2026-08-23

### Added

- Security agent. `SecurityPostureAuditor` checks Hypatia's own persisted
  research state against eight bounded properties and reports findings with a
  bounded `SecurityFindingSeverity`.
- `SecurityFinding`, `SecurityPostureReport`,
  `SecurityAgentApplicationService` with an audit intent, and one bounded
  `security_agent.posture_audited` event.

### Safety

- The agent audits this system and has no vocabulary to audit another. There is
  no scan intent, no probe intent, no target parameter, and no field for an
  external system. Tests assert those method names are absent and that the audit
  opens no socket, by making every socket call raise.
- The address check is literal rather than resolved, so the audit never becomes
  a network client. The resolution that mattered happened at the fetch boundary,
  where it was pinned.
- Checks cover what the domain types do not already guarantee. Referential
  integrity is enforced by `ResearchRun` at construction, so it is not audited
  again; a test asserts the type refuses those states rather than the auditor
  claiming credit for them. The two taint checks are declared as defence in
  depth via `covered_by_a_type`.
- A newly detected class of problem: the same URL accepted twice. Two records
  sharing a URL read as independent corroboration to calibration and to the
  hypothesis appraiser, and no type checked for it.
- Every report states its scope alongside its findings, and a clean report says
  explicitly that specific properties held just now rather than that the system
  is safe.
- Nothing is repaired. Tests assert the run store is byte-identical after
  repeated audits and that no file is created.
- Event payloads carry counts, bounded kinds, and the worst severity, plus
  explicit `external_systems_contacted: 0` and `records_modified: 0`. Tests
  assert no URL or research question appears in any payload.

### Verification

- The package-aware full local suite contains 2,432 passing automated tests.
- Forty new tests cover each check and its severity, loopback and private
  address forms, public addresses not being misreported, duplicate and distinct
  URLs, content types, timestamp ordering, worst-first ordering, empty scope,
  the socket assertion, inertness, bounded events, and production composition
  wiring.

## [0.3.154] - 2026-08-23

### Added

- Vulnerability family graph. `VulnerabilityFamily` records one class of
  weakness with a prevention note, `VulnerabilityRelation` records one authored
  edge with its reasoning, and `VulnerabilityFamilyGraph` answers bounded
  neighbourhood and ancestor queries.
- `JsonFileVulnerabilityGraphStore`, `VulnerabilityGraphApplicationService` with
  record, relate, neighbourhood, and list intents, and three bounded
  `vulnerability_graph.*` events.
- `HYPATIA_VULNERABILITY_GRAPH_ENABLED` opts into keeping the taxonomy, default
  off.

### Safety

- The safety property is structural, not filtered. Neither a family nor a
  relation has a field for a target, host, URL, payload, proof of concept,
  affected version, or CVE, and tests assert those field names are absent from
  both the domain types and the persisted document.
- A family describes a concept and never a system. `describes_a_target` and
  `asserts_exposure` are asserted false for every family and every relation
  kind, and every response repeats that recording or relating one says nothing
  about whether any system, product, or person is affected.
- The neighbourhood response says explicitly that its suggestions are about what
  to read next, not what to attack.
- Edges are authored and require a rationale. An unexplained edge is refused at
  construction and again on load.
- `specializes` is kept acyclic so the taxonomy stays one, and a hand-edited
  file introducing a cycle, a self-relation, or an edge to a family that does
  not exist is refused on load because loading replays the same checks.
- `enables` is directional and only followed forwards; a test asserts it is not
  read backwards into the reverse claim.
- Traversal is bounded in both depth and result count.
- Event payloads carry identifiers, bounded kinds, and counts only. Tests assert
  no family summary, prevention note, or relation rationale appears in any
  payload.

### Verification

- The package-aware full local suite contains 2,392 passing automated tests.
- Fifty-one new tests cover the absent-target schema shape, rationale
  enforcement, self-relations, duplicate families and edges, acyclic
  specialisation, symmetric versus directional traversal, depth and kind
  filtering, ancestor chains, persistence and restart, hand-edited documents,
  bounded events, and production composition wiring.

## [0.3.153] - 2026-08-23

### Added

- Hypothesis engine. `ResearchHypothesis` records one authored conjecture, the
  observation that would count against it, and the evidence entered on each
  side; `ResearchHypothesisAppraiser` derives a bounded `HypothesisStatus`.
- `JsonFileHypothesisStore`, `HypothesisApplicationService` with propose,
  support, oppose, withdraw, and list intents, and three bounded `hypothesis.*`
  events.
- `HYPATIA_HYPOTHESIS_ENABLED` opts into keeping hypotheses, default off.

### Safety

- A hypothesis without a discriminating test is refused at construction and
  again on load. A conjecture that names nothing capable of counting against it
  is a belief, and a stored one that lost its defeater would be
  indistinguishable from a belief.
- There is no confirm intent and no status meaning true. `HypothesisStatus`
  contains no confirmed, proven, true, or false value, `means_true` is asserted
  false for every status, and the service is asserted to expose no confirm
  method.
- Supporting and opposing evidence are never netted. Both counts are reported
  separately, the same evidence cannot be entered on both sides, and all
  evidence must already be recorded in the run.
- The status rules are asymmetric: any opposing evidence moves a hypothesis off
  the supported track, while support requires more than one source. A test
  asserts one opposing source weakens two supporting ones rather than being
  outvoted.
- Status is derived, never stored, so it cannot disagree with the evidence
  beside it. A test asserts no status field is written to the document.
- A hypothesis creates no claim and changes no run.
- Event payloads carry identifiers, bounded statuses, and per-side counts, plus
  an explicit `asserts_truth: false`. Tests assert the statement, its defeater,
  the research question, and URLs appear in no payload.

### Verification

- The package-aware full local suite contains 2,341 passing automated tests.
- Forty-nine new tests cover defeater enforcement, evidence on both sides,
  withdrawal, every status rule and its asymmetry, separate counting,
  persistence and restart including the defeater surviving, unknown hypotheses,
  unrecorded evidence, bounded events, store validation including a stripped
  defeater, and production composition wiring.

## [0.3.152] - 2026-08-23

### Added

- Source reputation. `SourceReputationLedger` aggregates authored assessments by
  origin across every run, and `SourceReputation` reports the counts with a
  bounded `SourceStanding` — unknown, provisional, mixed, consistently low, or
  consistently trusted.
- `SourceOrigin` normalises a URL host minimally: lowercase, no leading `www.`,
  no port, and no public-suffix guessing, so subdomains stay separate.
- `SourceReputationApplicationService` with a report intent for all origins or
  one named origin, and one bounded `source_reputation.reported` event.

### Safety

- Reputation gates nothing. A low standing refuses no fetch, discounts no
  evidence, pre-assesses no new source, and changes no assessment. Tests assert
  a later source from a consistently-low origin is still accepted and still
  arrives unassessed, and `SourceStanding.decides_anything` is asserted false
  for every value rather than merely intended in a comment.
- There is no store and no write path. The ledger is rebuilt from assessments on
  every request, so revising an assessment revises the reputation; a test
  asserts exactly that.
- There is no score. Counts per trust label stay separate so the sample is
  visible, rather than compressed into a number that looks precise and cannot be
  argued with.
- Below three assessments the standing is `provisional`. Two low assessments
  produce provisional, not consistently low.
- Only authored assessments count. Acceptance alone leaves the standing unknown,
  and superseded assessments stop counting.
- Event payloads carry counts and bounded standing categories but deliberately
  never an origin name, since a log line pairing a host with a low standing gets
  quoted later without its sample size.

### Verification

- The package-aware full local suite contains 2,292 passing automated tests.
- Thirty-nine new tests cover origin normalisation, every standing rule and its
  threshold, aggregation across runs, superseded assessments, acceptance without
  judgement, ordering, single-origin lookup, the absence of gating, derivation
  rather than storage, bounded events, and production composition wiring.

## [0.3.151] - 2026-08-23

### Added

- Claim calibration. `ResearchClaimCalibrator` builds an `EvidenceSupportProfile`
  for each active claim — distinct sources, evidence records, how many sources
  carry an assessment, the lowest and highest trust, and whether anything
  contradicts it — and compares the authored state and confidence against the
  ceilings that structure supports.
- `CalibrationVerdict`, `ResearchClaimCalibration`, `ResearchCalibrationReport`,
  `CalibrationApplicationService` with a report intent, and one bounded
  `calibration.reported` event.

### Safety

- Calibration never edits a claim. An epistemic state is the author's judgement
  about what they are willing to assert, and quietly adjusting it would overrule
  that judgement while presenting the change as bookkeeping. Tests assert an
  overstated claim keeps its authored state and confidence, and that the run
  store is byte-identical across repeated calibration.
- There is no calibration store and no write path. The report is derived on
  every request, so it cannot drift from the record it describes.
- The ceilings are stated rules, not a score, and nothing supports `fact`. No
  configuration of sources in our own record makes a claim a fact.
- Overstatement is reported; understatement is not treated as a problem. Being
  more careful than the record requires is never an error, and calibration does
  not nudge anyone toward more confidence.
- A ceiling is explicitly not a verdict on truth, and the response says so:
  meeting it does not make a claim true, exceeding it does not make one false.
- Superseded claims are excluded, and a contradicted claim supports nothing
  until the contradiction is resolved.
- The event payload carries the run identifier, bounded verdict counts, and a
  `claims_modified` count that is always zero. Tests assert no claim text,
  research question, or URL appears in it.

### Verification

- The package-aware full local suite contains 2,253 passing automated tests.
- Thirty-one new tests cover every ceiling rule, contradiction, understatement,
  superseded claims, empty runs, profile validation, verdict properties,
  inertness over claims and the run store, derivation rather than storage,
  bounded events, and production composition wiring.

## [0.3.150] - 2026-08-23

### Added

- Failure memory. `ResearchFailureLessonDeriver` reads a persisted run and
  derives seven bounded lesson kinds — disproving evidence, failed hypothesis,
  invalid assumption, false positive, confidence change, ineffective strategy,
  and operation failure — each naming the records it came from.
- `ResearchFailureLesson`, `JsonFileFailureLessonStore`, `FailureMemoryAdvisor`,
  `FailureMemoryApplicationService` with preview, store, list, and recall
  intents, and three bounded `failure_memory.*` events.
- `HYPATIA_FAILURE_MEMORY_ENABLED` opts into remembering lessons, default off.

### Safety

- A lesson without provenance is refused at construction and again on load, so
  no opinion can outlive the reasoning behind it. Repeated and empty provenance
  entries are refused too.
- The templates never overstate. A superseded hypothesis is recorded as
  abandoned rather than disproved, a contradiction leaves open which claim
  survives, and a barren search is a result about that query rather than a
  verdict on the provider.
- Recall is advisory and enforces nothing. It blocks no plan, refuses no
  capability, downgrades no claim, and edits no run, and the response says so
  explicitly. Tests assert research state is byte-identical after recall.
- Matching is deterministic word overlap weighted by lesson kind, not a model
  deciding which past failures apply to present work.
- Deriving, storing, listing, and recalling all leave every run byte-identical.
  Lesson identities are stable, so re-deriving remembers nothing new.
- Event payloads carry identifiers, bounded kind counts, and provenance counts
  only — never a lesson statement, research question, claim text, or URL. The
  provenance is counted, never listed.
- Persistence follows the proven atomic pattern, with unknown schema versions,
  unknown kinds, duplicate IDs, stripped provenance, and oversized documents
  refused, and a failed write leaving the previous document byte-identical.

### Verification

- The package-aware full local suite contains 2,222 passing automated tests.
- Fifty-nine new tests cover provenance enforcement, each lesson kind, the cases
  that correctly produce no lesson, weight ordering, identity stability, bounded
  counts, advisory recall and its bounds, chat-free inertness over research
  state, bounded events, store validation including stripped provenance, and
  production composition wiring.

## [0.3.149] - 2026-08-23

### Added

- Bounded reflection. `ResearchReflectionGenerator` reads a persisted run and
  reports eight bounded finding kinds — failed, contradiction, revised belief,
  weak evidence, uncertain, unused effort, worked, and next question — ordered
  with problems before successes.
- `ResearchReflectionReport`, `ResearchReflectionFinding`,
  `JsonFileReflectionReportStore`, `ReflectionApplicationService` with preview,
  store, and list intents, and two bounded `reflection.*` events.
- `HYPATIA_REFLECTION_ENABLED` opts into durable reflection history, default
  off.

### Safety

- Every finding describes the process, never the subject. Reflection reports
  that a claim rests on one source; it has no way to report that a claim is
  true. Tests assert an uncertain claim is still uncertain afterwards and that
  the run store is byte-identical across repeated reflection.
- There is no recursive reflection. The generator accepts a research run and
  nothing else; passing a report raises, and reflecting on a stored report ID is
  refused as an unknown run. Both are asserted.
- Generation is deterministic and template-driven rather than model authored, so
  a reflection cannot narrate work it did not inspect.
- Reflection reuses curiosity for the questions it proposes and the gap detector
  for thin-record findings, rather than adding a second engine. It reports those
  questions without storing them.
- Successes and proposed questions are excluded from lessons, so a run with
  nothing to learn from reports nothing to learn from, and an empty run reports
  no success at all.
- Event payloads carry identifiers, bounded kind counts, and canonical counts
  only. Tests assert no claim text, finding detail, research question, or URL
  appears in any payload.
- Persistence follows the proven atomic pattern, with unknown schema versions,
  unknown finding kinds, duplicate report IDs, and oversized documents refused,
  and a failed write leaving the previous document byte-identical.

### Verification

- The package-aware full local suite contains 2,163 passing automated tests.
- Forty-six new tests cover each finding kind, report ordering, bounded counts,
  reflection inertness, the recursion guard, preview without storing,
  persistence and restart, repeated reflection, listing, disabled persistence,
  failed writes, bounded events, store validation, and production composition
  wiring.

## [0.3.148] - 2026-08-23

### Fixed

- The desktop transcript displayed raw Markdown markers, so a reply containing
  a bolded word showed the asterisks around it. Bold, italic, and inline code
  are now drawn with Tk text tags and the markers are removed.

### Added

- `MarkdownTextSegments` splits a reply into styled segments. It imports no Tk,
  makes no rendering decision beyond which span carries which style, and is
  fully testable without a display.

### Safety

- Presentation cannot change content. Stripping the marker characters from the
  input and from the rendered text yields the same string, asserted over every
  sample, so no character of a reply can be lost to styling.
- The parser is conservative by design: it never spans a line break, and an
  unclosed marker, an empty span, or an underscore inside an identifier is left
  literal rather than guessed at. Showing a stray asterisk is preferable to
  swallowing text.
- Styling degrades rather than fails. If the platform cannot derive a bold or
  italic font the tags are simply not configured and the transcript reads
  exactly as it did before. No browser or webview dependency was added.

### Verification

- The package-aware full local suite contains 2,117 passing automated tests.
- Thirteen new tests cover content preservation across every sample, bold,
  italic with either marker, inline code left unparsed, bold winning over
  italic, unclosed and empty spans, identifiers keeping their underscores, spans
  never crossing a line break, and empty or invalid input.

## [0.3.147] - 2026-08-23

### Added

- `tools/diagnostics/research_pipeline_check.py` walks the real research
  pipeline and reports each stage separately: network request, candidate
  discovery, discovery record, explicit selection, HTTPS fetch, acceptance, and
  evidence. Nothing is promoted automatically and each stage runs only when
  named by flag. Assessments and claims are never produced by the diagnostic.
- `tools/diagnostics/durable_memory_check.py` gained a third stage that asks in
  a session created empty. The same-session result is now labelled weak, because
  that session's transcript already contains the taught fact; only the
  empty-transcript result is evidence of durable learned memory.

### Verification

- Live validation now covers the research pipeline end to end, not only
  deterministic doubles. A real Crossref discovery request returned five
  candidates; a real HTTPS fetch, acceptance, and evidence record completed; and
  assessment and claim correctly remained unperformed.
- Two real-world boundary observations from that run, both correct behaviour: a
  Crossref DOI candidate was refused at the HTTPS boundary because the publisher
  redirect was plain HTTP, and Wikipedia refused Hypatia's user agent with HTTP
  403. Both fail honestly rather than retrying or degrading.
- Seven new tests separate same-session recall from durable learned-memory
  recall, asserting that a fresh session carries an empty transcript and that
  the fact still reaches the model through injected learned-memory context. A
  negative control asserts that without a learned record no channel carries it.
- The package-aware full local suite contains 2,104 passing automated tests.

## [0.3.146] - 2026-08-23

### Fixed

- Ordinary chat could answer a request for live web information as though
  research had happened, inventing authors, journals, outlets, and dates, and
  could then describe those inventions as collected evidence. Both are now
  structurally prevented rather than discouraged.
- The default conversation instruction told the model to always answer in
  English and never in Turkish, which produced mixed and malformed output for
  users writing in Turkish. It now asks for the language the user wrote in,
  forbids mixing languages, asks for proportionate answers, and states that
  browsing is unavailable. No language is hardcoded.
- Conversation history was unbounded when `HYPATIA_LLM_HISTORY_MAX_TURNS` was
  unset. With a small local context window that pushes the newest message toward
  the truncation edge, so history is now bounded to twelve turns by default. The
  literal `unbounded` restores the previous behaviour.

### Added

- `LiveInformationRequestDetector` and `LiveInformationRequestKind` classify a
  plain chat message against a fixed phrase table in English and Turkish. The
  classification authorizes nothing.
- `ResearchHonestyApplicationService` answers such requests deterministically,
  without calling any model, and answers evidence questions from
  `CanonicalResearchSummary` counts derived from persisted runs.
- `ConversationResearchClaimGuard` annotates a generated reply that claims
  research in the first person with a bounded correction naming the canonical
  counts. It never deletes the model output.

### Safety

- A detected live-information request never reaches the language model, so
  there is nothing left that could fabricate a source. Tests assert zero
  provider calls across the real failing prompts.
- Detection cannot become an authorization path: it is gated on the absence of a
  declared intent, it returns only a category, and no capability, plan, run, or
  network operation follows from it.
- Evidence questions are answered only from persisted state, with discoveries,
  acceptances, evidence, assessments, claims, and contradictions counted
  separately so no stage is collapsed into another.
- Ordinary chat provably mutates no research state. Tests assert the run store
  is byte-identical after talking about evidence, sources, claims, and
  contradictions.
- The unsafe-URL boundary is now exercised end to end rather than only at the
  validator. Tests drive the real fetcher and the real authorized-fetch step
  with a recording opener and assert loopback, `127.0.0.1:11434`, private
  ranges, link-local metadata, embedded credentials, plain HTTP, non-standard
  ports, and non-HTTPS schemes are all refused before any connection is opened,
  and that a refusal records no source, evidence, or claim and leaks no
  credential.

### Verification

- The package-aware full local suite contains 2,097 passing automated tests.
- Fifty-two new tests cover live-information detection on the real failing
  prompts and on ordinary conversation, refusal without a model call, canonical
  evidence reporting, the post-generation guard, chat inertness over research
  state, the end-to-end fetch boundary, and bounded conversation history.

## [0.3.145] - 2026-08-23

### Added

- Bounded curiosity. `ResearchKnowledgeGapDetector` reads a research run and
  reports seven bounded gap kinds; `ResearchCuriosityQuestionGenerator` turns
  each gap into one ranked question; `CuriosityApplicationService` exposes
  detect, preview, store, list, accept, and dismiss intents.
- `JsonFileCuriosityQuestionStore` and `HYPATIA_CURIOSITY_ENABLED`, default off.
- Five bounded `curiosity.*` events.

### Safety

- Curiosity notices and proposes; it never acts. No curiosity intent starts
  research, drafts a plan, queues a background task, or spends a network or
  model operation, and accepting a question records intent only. Tests assert
  the run is unchanged after every intent.
- Detection is pure reading of persisted state. A gap reports what our own
  record is missing, never what is true: an unassessed source is not a bad
  source and an unresolved claim is not a wrong claim.
- Question generation is deterministic and template-driven rather than model
  authored, so a proposal cannot smuggle in an assertion. Every generated
  string is interrogative.
- Ranking is a stated formula: declared gap severity dominates and recorded
  claim confidence breaks ties. Gap and question identities are stable, so
  re-detecting proposes the same thing rather than duplicating it, and storing
  never reopens a question a human already decided.
- Superseded claims and superseded assessments are excluded, so a replaced
  record cannot resurface as a gap.
- Event payloads carry identifiers, bounded kinds, counts, and integer ranks
  only. Tests assert no claim text, question text, research question, or URL
  appears in any payload.

### Verification

- The package-aware full local suite contains 2,045 passing automated tests.
- Fifty-seven new tests cover each gap kind, severity ordering, bounded counts,
  superseded records, identity stability, question generation and ranking,
  preview-without-storing, persistence and restart, idempotent storing,
  decision transitions, unknown runs and questions, bounded events, disabled
  persistence, malformed and oversized stores, atomic write failure, and
  production composition wiring.

## [0.3.144] - 2026-08-23

### Added

- Background research scheduling. `BackgroundResearchTask` and its status
  domain, `JsonFileBackgroundTaskStore`, and
  `BackgroundResearchSchedulerApplicationService` with create, pause, resume,
  cancel, list, and worker-cycle intents.
- `BackgroundTaskOutcome` classifies each autonomy stop reason, and nine bounded
  `background_task.*` events.
- `HYPATIA_BACKGROUND_RESEARCH_ENABLED` opts into durable task storage, default
  off.

### Safety

- The scheduler owns queueing only. Every cycle drives the existing autonomy
  service, which drives the existing execution service; there is still one
  research-driving loop and this is not it. Tests assert an instruction naming
  fetch and accept completes no step and performs no research work.
- Budgets pass through unweakened. A task carries a `ResearchAutonomyBudget` and
  a test asserts a two-step budget completes exactly two steps.
- Retries are typed from the stop-reason enum, never from exception messages.
  Only budget exhaustion is retryable; blocked, failed, interrupted, and
  cancelled runs are never retried. The classification table is exhaustive, so a
  new stop reason without a declared outcome raises rather than defaulting to a
  retry.
- Work is synchronous and demand-driven: one cycle runs a bounded number of
  tasks and returns, with no thread, polling, or busy loop. Task selection is
  oldest-first so a retried task cannot starve the queue.
- A cancelled task never restarts and a completed task is never re-run; both are
  refused at the domain level.
- On restart a running task becomes `interrupted` and is not replayed.
  `INTERRUPTED`, `PAUSED`, and `BLOCKED` remain distinct.
- Persistence follows the proven atomic pattern: bounded temporary file, fsync,
  and `os.replace`, with a failed write leaving the previous document
  byte-identical. Unknown schema versions, malformed documents, duplicate task
  IDs, and oversized task counts are all refused.
- Stored documents and event payloads carry identifiers, statuses, counters, and
  an exception class name only. Tests assert the research question and authored
  instruction appear in neither.

### Verification

- The package-aware full local suite contains 1,988 passing automated tests.
- Thirty-one new tests cover task creation and persistence, a completed worker
  cycle, no re-running of completed tasks, pause and resume, cancellation and
  refusal to resume, bounded retry, the retry limit, non-retryable failure,
  budget pass-through, per-cycle and active-task bounds, cycle cancellation,
  restart interruption, no auto-replay, capability invention, bounded events,
  disabled persistence, malformed stores, atomic write failure, schema and
  duplicate rejection, task-count limits, absence of research content, the
  exhaustive outcome table, and production composition wiring.

## [0.3.143] - 2026-08-23

### Added

- Bounded autonomous research. `ResearchAutonomyApplicationService` loops over
  the existing execution service through the exact structured
  `research_autonomy_run` intent; no second execution engine exists.
- `ResearchAutonomyBudget` bounds step advances, network operations, LLM
  operations, and wall-clock seconds, each with a hard ceiling.
  `ResearchAutonomyResult` reports the stop reason, counters, and elapsed time.
- `ResearchOperationCost` and an exhaustive `CAPABILITY_COSTS` table declaring
  each capability's network and model cost.
- Two bounded events, `research.autonomy.started` and `.stopped`, emitted only at
  the boundaries of a run.

### Safety

- Autonomy runs only steps a human already authored and authorized, advanced
  through the same `process_advance` path, registry, operations, and run manager.
  It cannot invent a capability, infer one from instruction text, rewrite a plan,
  fabricate an authorization, accept a source, promote trust, promote a claim, or
  resolve a contradiction. Tests assert an instruction naming search and fetch
  still blocks, and that a discovery run leaves sources, evidence, assessments,
  claims, and contradictions empty.
- Network and model accounting come from the declared capability cost table, not
  from operation names or authored text. A test asserts exactly which
  capabilities declare network cost, so a new capability cannot quietly consume
  an unaccounted call.
- Budgets are enforced before each advance, never after. A zero network budget
  performs no network operation at all, and a zero step budget attempts nothing.
- `max_step_advances` counts attempted advances rather than successes, so a plan
  that keeps blocking cannot loop forever by never succeeding.
- Stopping is not failure. Step-level reasons are reported ahead of the generic
  terminal reason, so a failed, blocked, or interrupted step explains itself
  rather than being flattened into "terminal".
- Time comes from an injected clock; no test sleeps.
- A restored execution cannot be driven by autonomy, and a missing live execution
  is refused rather than started.
- Autonomy telemetry carries identifiers, declared budgets, counters, and a stop
  category only. A test asserts the authored instruction and the research
  question never appear.

### Verification

- The package-aware full local suite contains 1,957 passing automated tests.
- Twenty-one new tests cover completion within budget, exact step-budget
  stopping, network-budget stopping, zero network and zero step budgets, LLM
  accounting from declared cost, injected-clock time exhaustion, cancellation,
  blocked and failed steps, capability invention, absence of source acceptance
  and claim promotion, absence of duplicate side effects, unchanged manual
  execution, refusal without a live execution, bounded events, budget validation,
  and exhaustive capability-cost declaration.

## [0.3.142] - 2026-08-23

### Added

- Stages 3 and 4 of research-execution persistence. `Bootstrap` creates a
  `JsonFileResearchExecutionStore` beside the research-run store when
  `HYPATIA_RESEARCH_EXECUTION_PERSISTENCE_ENABLED` is exactly `true`, and the
  execution service owns loading, restoring, and writing.
- `research.plan.execution.restored` and
  `research.plan.execution.persistence_failed` events, both bounded.
- A restored-execution response that reports durable state without implying a
  resumable run.

### Safety

- Default off. With the flag absent or set to any other value, no store is
  created and behavior is identical to a runtime without persistence; a test
  asserts no file is written and status still reports ephemeral loss.
- Restoring is inspection, never resumption. A step recorded as running becomes
  `interrupted`, completed steps stay completed, and pending steps stay pending.
  Authorizations are deliberately not persisted, so a restored execution cannot
  be advanced and no completed operation is replayed. A test asserts the research
  run is unchanged after attempting to advance a restored execution.
- A corrupt store raises at startup rather than being replaced by an empty one,
  because silently discarding it would erase execution history on the next write.
- A failed write never erases live state: the in-memory execution continues and a
  bounded `persistence_failed` event reports the cause class.
- Persisted content is bookkeeping only. A test asserts the stored document
  contains neither the authored step instruction nor any source content.
- `CognitiveEngine` receives the store and forwards it, and gained no persistence
  logic.

### Verification

- The package-aware full local suite contains 1,936 passing automated tests.
- Thirteen new integration tests cover completed work surviving a restart without
  replay, a mid-flight step restoring as interrupted, the bounded restore event,
  refusal to advance a restored execution, terminal and cancelled executions
  surviving, disabled persistence keeping ephemeral behavior, a corrupt store
  refusing, duplicate identifiers refusing, a failed write preserving live state,
  the stored document duplicating no research content, and the Bootstrap flag
  requiring an exact value.

## [0.3.141] - 2026-08-23

### Added

- Stage 2 of research-execution persistence: `JsonFileResearchExecutionStore`, a
  dedicated versioned store for execution snapshots.

### Safety

- Deliberately separate from the research-run store. `ResearchRun` and its schema
  are untouched, every existing snapshot stays valid, and no migration of
  existing data is required. Deleting the execution file returns the runtime to
  purely ephemeral behavior.
- Writes follow the existing run-store discipline exactly: a bounded temporary
  file in the destination directory, flushed and fsynced, then moved into place
  with `os.replace`. A failed replace, a failed encode, and an oversized document
  all leave the previous snapshot byte-identical, and no temporary file is left
  behind.
- An absent file means no persisted executions, matching a runtime with
  persistence disabled. A malformed or unreadable file raises rather than being
  silently treated as empty, because discarding it would hide execution history.
- The document is versioned and an unknown `schema_version` is rejected outright.
  Unexpected or missing document fields, non-list executions, malformed entries,
  oversized files, too many executions, and duplicate execution IDs are all
  refused on load and on save.
- The stored document carries execution bookkeeping only. A test asserts it holds
  no excerpt, claim, or instruction content, so research facts are never
  duplicated out of the research run.
- Nothing is wired into the runtime yet; execution state remains ephemeral.

### Verification

- The package-aware full local suite contains 1,923 passing automated tests.
- Twenty-one new tests cover the absent file, lossless round trips, interrupted
  round trip, clearing the document, schema versioning, corrupted JSON, unknown
  schema version, invalid documents, oversized files, execution-count limits on
  load and save, duplicate identifiers on load and save, non-snapshot values,
  malformed entries, failed replace preserving the previous document, no
  temporary file left behind, no partial document when encoding fails, parent
  directory creation, and absence of research content in the stored document.

## [0.3.140] - 2026-08-23

### Added

- Stage 1 of research-execution persistence: a pure codec. `ResearchPlanExecutionSnapshot`
  is the durable record and `ResearchPlanExecutionCodec` converts it to and from
  its document form. No file access, no runtime wiring, and no restore policy
  yet.
- `INTERRUPTED` step and execution statuses, distinct from `BLOCKED`. Blocked
  means a human must decide; interrupted means the process died mid-flight and
  what the operation did is unknown. Neither is terminal.

### Safety

- A snapshot records what happened, never a running execution. `restored()`
  turns a step recorded as running into interrupted, never completed, so a
  mid-flight operation can never be fabricated as finished after a restart.
  Completed steps stay completed and pending steps stay pending.
- Terminal executions stay terminal across a restore, and restoring is
  idempotent.
- `work_performed` is never inferred at load time. A record claiming performed
  work without naming its operation is rejected by both the value object and the
  decoder.
- The document is deliberately narrow: step identity, declared capability,
  status, operation identity, work flag, bounded detail, the plan question, and
  the bound run identity. Authored step instructions, fetched page bodies, source
  excerpts, notes, claim text, and authorization payloads are never written, so
  no research fact is duplicated out of the research run.
- Malformed documents are refused rather than repaired: unknown or missing
  fields, empty or oversized step lists, unknown enum values, naive timestamps,
  and non-string identifiers all raise.

### Verification

- The package-aware full local suite contains 1,902 passing automated tests.
- Fifteen new tests cover capability pairing, work and operation preservation,
  interrupted restore, completed and pending steps surviving, terminal
  executions, restore idempotence, the blocked/interrupted distinction, lossless
  round trips with and without a bound run, absence of authored instructions in
  the document, rejection of work without an operation, and malformed execution
  and step documents.

## [0.3.139] - 2026-08-23

### Added

- Bounded observability for research-plan execution. `ResearchPlanExecutionEvents`
  publishes `research.plan.execution.started`, `.step_started`, `.step_completed`,
  `.step_failed`, `.step_blocked`, and `.cancelled` from one focused emitter that
  owns the event names and payload bounds.
- `ExecutionBlockReason` gives a blocked step a bounded category rather than free
  text: `no_declared_capability`, `unregistered_capability`, or
  `operation_performed_nothing`.

### Safety

- Visibility only. No event changes behavior, and an absent event bus makes every
  emitter call a no-op, so execution runs identically without observability. A
  test drives the same plan through an observed and an unobserved engine and
  asserts identical execution snapshots.
- Payloads carry safe identifiers, capability and operation names, counts, and
  booleans. A test asserts the authored instruction, the authorized URL, the
  research question, and the fetched source body never appear in any payload.
- A bound research run is reported as a boolean, not as an identifier.
- A failed step reports its exception class name, never the exception message.
- A step that genuinely ran without succeeding is distinguished from one that
  never ran, through the `work_performed` field on the failure event.

### Verification

- The package-aware full local suite contains 1,887 passing automated tests.
- Ten new tests cover the started-then-completed sequence with exact payloads,
  absence of authored content, boolean run binding, both block reasons, failure
  cause without message, cancellation reporting surviving progress, behavioral
  equivalence without an event bus, and bounded block categories.

## [0.3.138] - 2026-08-23

### Added

- One end-to-end explicit research-execution scenario driving the whole chain
  through the real `CognitiveEngine` composition path in a single narrative:
  question, discovery, explicit authorization, fetch, acceptance, evidence,
  assessment, two conflicting claims, contradiction, comparison, and honest
  closure.
- A research-execution persistence design proposal documenting why execution
  state stays ephemeral, what a migration would require, and a staged additive
  plan. It is a proposal only; nothing was implemented and no schema changed.

### Safety

- The scenario uses deterministic doubles only for the discovery provider and
  source fetcher, so no network is required. Every other component is real,
  including the run manager, knowledge engine, acceptance transaction, and
  epistemic domain.
- It asserts the chain's boundaries hold together, not merely that each step
  passes: discovery accepts nothing and fetches nothing, acquisition accepts
  nothing, only authorized URLs are ever contacted, recording a contradiction
  leaves both claims byte-identical, and both claims remain hypotheses with
  unassessed confidence at the end.
- The closed run retains its unresolved claims and its contradiction, and the
  completion detail reports them rather than implying resolution.
- Research execution writes no conversation memory.

### Verification

- The package-aware full local suite contains 1,877 passing automated tests.
- Black, Ruff, and MyPy pass for all 407 Python source and test files.
- Live-model and live-network validation remain separate manual diagnostics and
  are still pending.

## [0.3.137] - 2026-08-23

### Added

- `RESEARCH_RUN_COMPLETION` capability and `ResearchRunCompletionStepOperation`,
  closing a run through the existing `transition_status` path.
- `ResearchCompletionAuthorization` carries the one explicitly declared terminal
  status and rejects a non-terminal target.

### Fixed

- The draft service did not carry `completion_authorization` through to the
  plan step, so the capability was unreachable from an authored draft. The
  composition test caught it before release; the passthrough is now covered.

### Safety

- The operation defines no completion rule of its own. Every condition comes
  from the existing lifecycle: completion requires at least one accepted source
  and at least one evidence record, a failed run requires a failure record, and a
  closed run cannot change status. A refused transition is reported as performed
  work that did not succeed, with the run left open.
- Reaching the last execution step never closes a run. A composition test
  advances an execution to `completed` and asserts the run is still
  `collecting`.
- Closing a run resolves nothing. Unresolved claims held as hypothesis,
  speculation, unknown, or contradicted, together with contradictions and
  failures, survive into the final state and are counted in the reported detail.
  The detail states plainly that closing verifies no claim, settles no
  contradiction, and asserts no certainty.
- Missing authorization, an unknown run, a missing run binding, and cancellation
  all close nothing.

### Verification

- The package-aware full local suite contains 1,876 passing automated tests.
- Thirteen new operation tests cover domain-enforced refusal for missing sources
  and evidence, successful closure, reporting and preservation of unresolved
  claims and failures, contradictions surviving closure, the failure-record rule,
  refusal to reclose, missing authorization, cancellation, unknown and unbound
  runs, bounded detail, and authorization validation.
- The composition suite now covers twelve capabilities, and proves that finishing
  execution leaves the run open, that the capability respects domain rules
  through real wiring, and that a closed run retains its unresolved hypothesis.

## [0.3.136] - 2026-08-23

### Added

- `CLAIM_CONTRADICTION` capability and `ClaimContradictionStepOperation`,
  recording one confirmed contradiction through the existing
  `record_claim_contradiction` path.
- `SOURCE_COMPARISON` capability and `SourceComparisonStepOperation`, recording
  one authored comparison note through the existing
  `record_source_comparison_note` path.
- `ResearchContradictionAuthorization` and `ResearchComparisonAuthorization`,
  both arriving as named fields on `ResearchPlanStepDraftInput`. No positional
  draft element was added.

### Safety

- A proposal is never a contradiction. Previewing a contradiction persists
  nothing, and a suggestion, including a language-model one, stays a proposal
  until a human authorizes it through the canonical path.
- Recording a contradiction never rewrites either claim. A test captures both
  claims before and after and asserts they are byte-identical, with their
  epistemic states unchanged, so the contradiction never decides which claim is
  true.
- Exactly two distinct current claims from the bound run are required. Foreign
  and non-existent claim references are rejected with no mutation, and a
  duplicate relationship for the same pair is refused.
- Comparison is a description, not a verdict. It selects no winner, produces no
  ranking, promotes no trust, and verifies no claim; a test asserts assessments
  and claims are unchanged and contradictions stay empty afterwards.
- The existing 2-to-5 accepted-source bound is preserved rather than replaced,
  and evidence and assessment references must belong to the run.
- Authored notes and comparison text stay bounded, and user-facing detail stays
  within the bounded operation limit.
- Missing authorization, a closed run, an unknown run, a missing run binding, and
  cancellation all record nothing for both capabilities.

### Verification

- The package-aware full local suite contains 1,860 passing automated tests.
- Seventeen new operation tests cover confirmed recording, claims left
  unrewritten, proposals persisting nothing, duplicate refusal, foreign and stale
  references, source-count bounds, trust and claim state left untouched, missing
  authorization, cancellation, closed and unknown runs, bounded detail, and
  authorization validation for both capabilities.
- The composition suite now covers eleven capabilities with production route
  tests for both new ones.

## [0.3.135] - 2026-08-23

### Added

- `CLAIM_CREATION` capability and `ClaimCreationStepOperation`, recording one
  authored claim through the existing `ResearchRunManager.record_claim` path. No
  second claim implementation exists.
- `ResearchClaimAuthorization` carries the exact evidence a claim rests on, the
  authored claim text, an explicit epistemic state, an explicit categorical
  confidence, and an optional superseded claim.
- `ResearchPlanStepDraftInput` gains a named `claim_authorization` field; no
  positional draft element was added.

### Safety

- Epistemic state and confidence are authored, never inferred. Completing the
  operation promotes nothing: a claim is recorded in exactly the state a human
  declared. A test records every one of the seven epistemic states and asserts
  each is stored verbatim.
- A high-trust assessment does not raise a claim. A composition test records a
  high-trust assessment and then a hypothesis, and asserts the claim stays a
  hypothesis with unassessed confidence.
- The existing domain requires at least one evidence reference for every claim,
  including a hypothesis or speculation. That exact rule is preserved rather than
  replaced, so no claim can exist without evidence.
- Evidence must belong to the bound run. Foreign and non-existent evidence
  references are rejected with no mutation.
- Claim text stays bounded, evidence references stay unique and bounded, and
  confidence remains categorical with no fabricated number.
- Supersession history is preserved: the superseded claim remains in its original
  state and the replacement records the exact predecessor identity.
- Existing contradiction state is untouched; recording a claim never resolves or
  clears a contradiction.
- Missing authorization, a closed run, an unknown run, a missing run binding, and
  cancellation all record nothing.

### Verification

- The package-aware full local suite contains 1,840 passing automated tests.
- Fifteen new operation tests cover authored recording, non-promotion of a
  hypothesis, verbatim recording of every epistemic state, the evidence
  requirement for speculation, rejection of foreign and stale evidence,
  supersession history, untouched contradictions, missing authorization,
  cancellation, closed and unknown runs, bounded detail, and authorization
  validation.
- The composition suite now covers nine capabilities and drives the complete
  chain through real `CognitiveEngine` wiring: acceptance, evidence, assessment,
  and claim.

## [0.3.134] - 2026-08-23

### Changed

- Authored plan-step drafts now normalize through the named immutable
  `ResearchPlanStepDraftInput`, replacing a widening positional tuple whose
  fifth element could only be understood by counting. Legacy positional tuples
  are still accepted unchanged, so existing callers, the desktop adapter, and the
  plan domain are unaffected and no persisted schema changed.

### Added

- `SOURCE_ASSESSMENT` capability and `SourceAssessmentStepOperation`, recording
  one authored assessment through the existing
  `ResearchRunManager.record_source_assessment` path. No second assessment
  implementation exists.
- `ResearchAssessmentAuthorization` carries one exact accepted-source document,
  its evidence references, the authored assessment text, an authored
  information-trust label, and an optional superseded assessment.

### Safety

- Assessment text and information trust are authored, never derived. Nothing
  about a successful fetch, a successful acceptance, or a completed operation can
  set them, and no language model participates in this milestone.
- At least one evidence reference is required, matching the existing domain rule,
  so an assessment is always grounded in recorded evidence and can never rest on
  a successful fetch alone.
- The source must already be accepted on the bound run; a source accepted on a
  different run is rejected, as is a foreign evidence reference.
- Supersession history is preserved: the superseded assessment remains, and the
  replacement records the exact predecessor identity.
- Information trust describes confidence in what a source says. It is not
  evidence, not claim verification, not proof the source is correct, and it never
  grants the source's text instruction authority.
- Missing authorization, a closed run, an unknown run, a missing run binding, and
  cancellation all record nothing.

### Verification

- The package-aware full local suite contains 1,822 passing automated tests.
- Fourteen new operation tests cover authored recording, absence of evidence or
  claim creation, unassessed trust defaulting, supersession history, rejection of
  unaccepted sources and foreign evidence, missing authorization, cancellation,
  closed and unknown runs, bounded detail, normalization, evidence grounding, and
  authorization validation.
- The composition suite now covers eight capabilities, proves the named draft
  input works through real wiring alongside legacy tuples, and drives the chain
  from source acceptance through evidence recording to assessment.

## [0.3.133] - 2026-08-23

### Added

- `EVIDENCE_RECORDING` capability and `EvidenceRecordingStepOperation`, recording
  one evidence entry through the existing `ResearchRunManager.add_evidence`
  path. No second evidence domain exists.
- `ResearchEvidenceAuthorization` groups one exact document ID, one exact chunk
  index, and one authored note, so capability-specific authorization stays
  cohesive instead of spreading across flat step fields. Draft steps accept it
  as an optional fifth element.

### Safety

- Evidence text is never supplied by a caller. The operation resolves a real
  `Chunk` by exact document ID and chunk index, and the existing evidence domain
  computes the excerpt, chunk identity, and hash from that chunk. A caller may
  authorize which chunk and what a human noted about it, never the excerpt, so
  evidence cannot be fabricated.
- No language model is involved at any point.
- A fetched-but-unaccepted source cannot produce evidence: the run manager
  independently requires the chunk's document to belong to an accepted source. A
  composition test drives fetch-without-accept and confirms the recording fails.
- An unknown document or chunk index is refused rather than guessed or
  approximated to a nearby chunk.
- Missing authorization, a closed run, an unknown run, a missing run binding, and
  cancellation all record nothing.
- Recording evidence establishes evidence only. It performs no assessment, forms
  no claim, elevates no epistemic state, and makes no source trustworthy; tests
  assert assessments, claims, and contradictions all stay empty.
- Excerpt truncation is reported rather than hidden, and user-facing detail stays
  within the bounded operation limit even with a maximum-length note.

### Verification

- The package-aware full local suite contains 1,805 passing automated tests.
- Twelve new operation tests cover recording from an accepted chunk, provenance
  computed from the real chunk, absence of assessment or claim, refusal for
  unaccepted sources and unknown chunks, missing authorization, cancellation,
  closed and unknown runs, bounded detail, and authorization validation.
- The composition suite now covers seven capabilities and proves the full
  production chain: `SOURCE_ACCEPT` then `EVIDENCE_RECORDING` through real
  `CognitiveEngine` wiring, plus the fetched-but-unaccepted refusal.

## [0.3.132] - 2026-08-23

### Changed

- The canonical source-acceptance transaction is extracted from
  `CognitiveEngine._process_research_source_load` into
  `ResearchSourceAcceptanceService`. The extraction is behavior-preserving: the
  same indexing, content persistence, `add_source`, and layered rollback flow
  runs, and every existing failure message is byte-identical. `CognitiveEngine`
  shrinks by 73 net lines and now delegates instead of owning the transaction.
  Exactly one acceptance implementation exists.

### Added

- `SOURCE_ACCEPT` capability and `SourceAcceptStepOperation`, fetching the one
  authorized URL through the canonical fetcher and then running the extracted
  acceptance transaction.
- `ResearchSourceAcceptanceResult` reports `accepted` and
  `transaction_attempted` as separate flags, and refuses to represent an
  accepted source that was never attempted.
- `AcceptsResearchSource` is the research-layer protocol for the transaction, so
  research operations never import the cognition layer.
- `ResearchPlanStepOperationResult.succeeded` distinguishes an operation that
  genuinely ran from one that achieved its outcome, and
  `ResearchPlanExecutionState.fail_step` can now record performed work on a
  failed step.

### Safety

- A transaction that runs and does not accept is recorded as performed work on a
  failed step, never rendered as a successful acceptance. The detail states that
  no source was added to the run.
- Authorization stays explicit. The URL comes only from the step's
  `authorized_source_url`; discovery metadata alone never authorizes acceptance,
  and instruction text remains inert. Tests assert zero fetches in both cases.
- No second content channel exists. Content flows only through the canonical
  knowledge engine and source-content store, and no page content enters the
  execution context.
- Cancellation before the fetch prevents all work; cancellation after the fetch
  prevents every acceptance mutation, leaving knowledge, content, and run state
  untouched.
- Rollback guarantees are unchanged and now directly tested: content failure
  rolls back indexing, `add_source` failure rolls back content and indexing, and
  a failed content rollback is reported precisely rather than glossed over.
- Duplicate sources remain deterministic, surfacing as an indexing error with no
  partial state, exactly as before.
- Accepted means accepted into the run's source set only. No evidence,
  assessment, claim, trust, or conclusion follows, and tests assert those
  collections stay empty.

### Verification

- The package-aware full local suite contains 1,790 passing automated tests.
- Ten acceptance-service tests cover success, all rollback branches, duplicate
  handling, unknown runs, indexing failure, and knowledge-only acceptance.
- Eleven operation tests cover authorized-only acceptance, attempted-but-not-
  accepted reporting, refusal of unauthorized and discovery-only sources,
  cancellation before and after the fetch, audited fetch and indexing failures,
  closed and unknown runs, and detail that never dumps content.
- The composition suite now covers six capabilities and additionally proves the
  existing source-load route and the `SOURCE_ACCEPT` operation share one
  acceptance service instance, and that the legacy route still accepts a source.

## [0.3.131] - 2026-08-23

### Added

- `SOURCE_FETCH` capability and `SourceFetchStepOperation`, reusing the canonical
  `ResearchSourceFetcher` pipeline. No second HTTP path was added.
- `ResearchPlanStep.authorized_source_url` is the one exact source a step may
  acquire, bounded to 2,048 characters and rejecting embedded control
  characters. Draft steps accept it as an optional fourth element.

### Safety

- The URL is never chosen by the operation. It comes only from the step's
  explicit authorization: never inferred from instruction text, never taken from
  a discovery result, never guessed from ranking. Tests assert zero network calls
  when a URL appears only in instruction text or only in a discovery record.
- Every existing protection stays in force through the reused pipeline: public
  HTTPS only, credential rejection, port restrictions, DNS and IP validation,
  public-address enforcement, redirect validation, TLS and hostname validation,
  response-size, content-type, and encoding bounds. A composition test drives the
  real `HttpResearchSourceFetcher` and confirms plain HTTP, a loopback address,
  and embedded credentials are all still rejected.
- The operation is acquisition-only. It performs no acceptance: nothing is
  indexed, no accepted-source record is written, no content snapshot is stored,
  and no evidence, assessment, or claim is created. Accepting a source remains a
  separate explicit contract.
- Because nothing is persisted, cancellation after bytes arrive leaves no partial
  research state. Cancellation before the fetch prevents any network call.
- A closed run, unknown run ID, or missing run binding is rejected before any
  network call.
- Blank content never becomes a successful fetch; the domain rejects it at
  `ResearchSource` construction and the operation guards it again.
- Fetched content is untrusted data with no instruction authority and is never
  sent to a language model here. User-facing detail reports only the bounded URL,
  content type, and character count, never source contents.

### Verification

- The package-aware full local suite contains 1,764 passing automated tests.
- Fifteen new operation tests cover authorized-only fetching, refusal of
  instruction-text and discovery URLs, cancellation before and after the fetch,
  acceptance of nothing, audited pipeline rejection, blank-content refusal at
  both layers, closed and unknown runs, content never appearing in detail,
  bounded hostile URLs, and step-level URL validation.
- The standing composition table now covers five capabilities.

## [0.3.130] - 2026-08-23

### Added

- `SOURCE_DISCOVERY` capability and `SourceDiscoveryStepOperation`, reusing the
  existing `ResearchSourceDiscoveryProvider` abstraction and the
  `ResearchRunManager` discovery audit path. No second discovery engine exists.
- `ResearchPlanExecutionContext.cancellation_token` carries the request's
  cooperative cancellation signal as per-execution state. The application
  service forwards the current request's token on every advance.

### Safety

- One step performs exactly one bounded provider query: no retry, no crawling,
  no link following, and no unbounded concurrency. A test asserts the provider
  is contacted exactly once even when it fails.
- Cancellation is checked before the query and again before the audit write.
  Cancelling first prevents provider contact entirely; cancelling during the
  query prevents the discovery record from being written.
- A closed run, an unknown run ID, and a missing run binding are all rejected
  before the provider is contacted.
- Provider results are validated for type and count. An oversized or malformed
  result is rejected and no discovery record is written.
- Provider failure records a `source_discovery` failure in the run audit and
  re-raises, so the step fails honestly rather than reporting partial success.
  No substitute provider is ever used; when no provider is configured the
  capability stays unregistered and a declaring step blocks.
- Candidates are persisted only as an unaccepted, provenance-preserving audit
  record. Nothing is accepted, fetched, turned into evidence, or turned into a
  claim. Every detail states that candidates are not accepted sources, not
  evidence, not trusted, and not a conclusion, and a composition test asserts
  that sources, evidence, claims, and assessments all remain empty afterwards.
- Zero candidates is a performed discovery, not a failure.

### Verification

- The package-aware full local suite contains 1,745 passing automated tests.
- Fourteen new operation tests cover the stable name, unaccepted candidate
  recording, zero-candidate completion, bounded query parameters, single-query
  behavior, failure auditing, oversized and malformed result rejection,
  cancellation before and after the query, closed and unknown runs, limit
  validation, and bounded detail.
- The standing composition table now covers four capabilities, with route tests
  proving discovery runs through real `CognitiveEngine` wiring, accepts nothing,
  and stays unregistered without a provider.

## [0.3.129] - 2026-08-23

### Added

- `EVIDENCE_INTEGRITY_CHECK` capability and `EvidenceIntegrityCheckStepOperation`,
  running the existing `ResearchEvidenceIntegrityAuditor` against the bound run
  through constructor-injected collaborators.

### Safety

- The check is local, read-only, and deterministic: no network, no LLM, no
  persistence mutation, and no event emitted. Repeated runs return an identical
  result, and the run is byte-identical afterwards.
- Only the bound run is audited, never the whole catalog.
- A completed check proves only that the integrity operation ran and returned
  its result. Every rendered detail states that it does not establish truth,
  verify a claim, or make a source trustworthy. Matched, missing, and changed
  counts describe structural and provenance consistency only.
- Zero evidence records still complete the audit, reporting that no evidence
  records were available to inspect.
- An `unavailable` audit is reported as a performed operation with an explicit
  state and no fabricated counts.
- An unknown run ID or a missing run binding fails the step safely with
  `work_performed` left false.
- The capability is registered only when both a run manager and an integrity
  auditor exist; otherwise it stays unregistered and a declaring step blocks.
- Detail stays within the bounded 500-character operation limit.

### Verification

- The package-aware full local suite contains 1,728 passing automated tests.
- Ten new operation tests cover the stable name, zero-evidence completion,
  reconciliation counts, single-run scoping, unavailable reporting, unknown-run
  and missing-binding failure, absence of mutation, bounded detail, and
  determinism.
- The standing composition table now covers three capabilities, with new route
  tests proving the check runs through real `CognitiveEngine` wiring, fails
  safely without a run, and stays unregistered without an auditor.

## [0.3.128] - 2026-08-23

### Added

- `ResearchPlanExecutionContext` is the smallest explicit typed context for one
  execution, currently one optional bounded `research_run_id`. It is passed
  through the application-service boundary to an operation.
- `ResearchPlanStepOperation.run` now receives that context. Collaborators stay
  constructor-injected at composition time, so an operation never reaches a
  global, service locator, dependency container, `CognitiveEngine`, or an
  unrelated store.
- `ACCEPTED_SOURCE_LISTING` capability and `AcceptedSourceListingStepOperation`,
  reading accepted sources from the canonical `ResearchRunManager` state.
- The start request accepts an optional explicit `research_run_id` binding.

### Safety

- Listing is read-only: no network, no LLM, no persistence mutation, and no
  event emitted. A test asserts the run is byte-identical afterwards.
- Zero accepted sources is a successfully performed listing, not a failure.
- The detail states explicitly that no source content was read and no evidence
  was established. Listing establishes neither evidence, nor trustworthiness,
  nor a verified claim; those remain in the existing research pipeline.
- Reported document identifiers are capped at three with a remainder count, so a
  large accepted-source catalog is never dumped into step detail.
- An unknown or stale run ID, and a missing run binding, fail the step safely
  with `work_performed` left false.
- The capability is registered only when a run manager exists. Without one it
  stays unregistered and a declaring step blocks rather than failing obscurely.
- Capability authorization stays separate from execution context: the step
  declares what it may run, the context describes what it runs against.

### Verification

- The package-aware full local suite contains 1,715 passing automated tests.
- Sixteen new tests cover the stable operation name, zero-source listing,
  identifier-only reporting, bounded large catalogs, unknown-run and
  missing-binding failure, absence of mutation, and context validation.
- A new composition-level suite proves every registered capability is actually
  reachable through the real `CognitiveEngine` wiring, covering the 0.3.126
  bug class where a capability worked in a directly constructed service while
  production wiring silently lacked it. This check is now required for every
  newly connected capability.

## [0.3.127] - 2026-08-23

### Added

- `ResearchPlanStepCapability` is the explicit typed authorization a plan step
  may declare, defaulting to `none`. `ResearchPlanStep.capability` keeps that
  authorization separate from the authored instruction text.
- `ResearchPlanOperationRegistry` binds each executable capability to exactly one
  operation. Selection is a table lookup, never a heuristic over instruction
  text, and `CognitiveEngine` registers the local knowledge search explicitly
  rather than growing conditional routing.
- `ResearchPlanStepState.operation` records which operation ran, so a completed
  step can always answer which operation was selected and what produced it.
- `ResearchPlanDraftService` accepts an optional explicit capability name as a
  third draft element. Two-element drafts remain valid and declare no capability.
- `ResearchPlanExecutionState.snapshot()` returns a minimal deterministic
  inspection tuple of step id, status, operation, and work flag.

### Fixed

- The 0.3.126 engine wiring for the local knowledge search silently did not
  apply, so the advance route reached no operation. The registry is now wired and
  covered by a test that drives the route through `CognitiveEngine`.

### Safety

- A step declaring no capability, or declaring a capability with no registered
  operation, is blocked with a bounded reason. Neither falls back to another
  operation.
- Instruction wording never selects a capability. A step whose instruction says
  "run a local knowledge search" still blocks unless the capability is declared.
- Recorded work now requires a recorded operation name: constructing a step state
  with `work_performed` true and no operation is rejected.
- Rendering states that a completed operation means the operation ran, and that
  it is neither evidence nor a verified claim. Evidence, assessment, and claims
  are not established by execution and remain in the existing research pipeline.
- Registering the `none` capability, registering a capability twice, or passing a
  non-capability value is rejected.
- The snapshot is an inspection aid only. It is not persistence and cannot resume
  an execution.

### Verification

- The package-aware full local suite contains 1,699 passing automated tests.
- Fifteen new tests cover capability defaults and validation, registry
  resolution, rejection of `none` and duplicate registration, blocking for
  undeclared and unregistered capabilities, instruction text never selecting a
  capability, recorded operation identity, draft capability parsing and
  rejection, and deterministic snapshots.
- Black, Ruff, and MyPy pass for all 372 Python source and test files.

## [0.3.126] - 2026-08-23

### Added

- Stage 3 of research-plan execution connects the first real research
  capability. `ResearchPlanStepOperation` is the structural boundary for one
  bounded operation, `ResearchPlanStepOperationResult` reports whether work
  actually ran plus one bounded 500-character summary, and
  `LocalKnowledgeSearchStepOperation` runs the existing deterministic local
  knowledge search for an authored step instruction.
- The exact structured `research_plan_execution_advance` Brain intent advances
  the next pending step by running that one operation.

### Safety

- Only an operation that actually executed can mark a step as backed by real
  work. When no operation is connected, or a connected operation reports that it
  performed nothing, the step is blocked with a bounded reason instead of being
  reported as completed research.
- A failing operation fails the step and the plan, leaves `work_performed` false,
  and preserves earlier completed steps.
- One advance request runs at most one operation for one step, in authored
  order. Advancing past the last pending step is rejected.
- A zero-result search is reported honestly as a performed search that matched
  nothing, so a step never implies evidence that was not located.
- The connected operation reads only already loaded local knowledge. Source
  discovery, source fetching, evidence extraction, assessment, and claims remain
  unconnected, and no network, LLM, or persistence path is used.
- Reported document identifiers are capped at three with an explicit remainder
  count.

### Verification

- The package-aware full local suite contains 1,684 passing automated tests.
- Thirteen new tests cover the stable operation name, real findings, honest
  zero-result reporting, bounded detail, result validation, blocking when no
  operation is connected, running one operation per step, blocking when an
  operation performed nothing, failure handling, completing a plan across
  advances, rejection past the last step, and advancing an unknown plan.
- Black, Ruff, and MyPy pass for all 369 Python source and test files.

## [0.3.125] - 2026-08-23

### Added

- Stage 2 of research-plan execution: `ResearchPlanExecutionApplicationService`
  owns ephemeral per-process execution state and exposes exact structured
  `research_plan_execution_start`, `research_plan_execution_status`, and
  `research_plan_execution_cancel` Brain intents.
- `ResearchPlanStepState.work_performed` records whether a real research
  operation backed a transition. `ResearchPlanExecutionState` adds
  `steps_with_research_work` and `performed_research_work`.
- `BrainResponse.research_plan_execution` carries the complete immutable state.

### Safety

- No research work runs in this stage. Starting a plan records that execution
  began and advances no step. Source discovery, fetching, evidence, assessment,
  and claims are not performed, and the rendered message says so.
- `work_performed` defaults to false and never becomes true on its own, so a
  bare state-machine advance can never be presented as completed research. A
  step completed without a backing operation is reported with
  `Research operations performed: 0` and an explicit no-research-ran line.
- Execution state lives in the application service, never in `CognitiveEngine`,
  which only routes.
- State is in-memory and per-process. Every status message states that it is
  lost when Hypatia exits, and an unknown plan reports absent state that is not
  resumed after a restart rather than inventing a resumable run.
- Duplicate start requests are rejected deterministically and leave existing
  state untouched. Active executions are capped at 20 per process.
- Terminal executions reject further transitions, and cancellation preserves
  completed-step history including its work flag.
- No persistence, schema change, second `ResearchRun` store, network call, or
  LLM call. Execution routes write no memory record.

### Verification

- The package-aware full local suite contains 1,671 passing automated tests.
- Seventeen new tests cover intent recognition, start without step advance,
  absence of reported research work, the ephemeral-boundary message,
  deterministic duplicate-start rejection, absent-state reporting, cancellation
  of unfinished steps, preservation of completed history, a manual advance being
  reported as no research, terminal rejection, invalid drafts leaving no state,
  missing plan IDs, bounded capacity, fresh-process statelessness, engine
  routing without owning state, and execution routes writing no memory.
- Black, Ruff, and MyPy pass for all 365 Python source and test files.

## [0.3.124] - 2026-08-23

### Added

- Stage 1 of research-plan execution: a pure immutable state machine. New
  `ResearchPlanExecutionStatus` (ready, running, completed, failed, cancelled,
  blocked) and `ResearchPlanStepStatus` (pending, running, completed, failed,
  cancelled, blocked) follow the existing `ResearchRunStatus` convention with an
  explicit `terminal` property.
- `ResearchPlanStepState` carries one step identity, its bounded status, and one
  bounded 500-character detail. `ResearchPlanExecutionState` tracks the whole
  plan and exposes `prepare`, `start`, `start_step`, `complete_step`,
  `fail_step`, `block_step`, and `cancel`.

### Safety

- Every transition returns a new immutable state and never mutates its input.
- A plan reaches completed only when every step reached completed. Constructing a
  completed state with unfinished steps is rejected, so partial or failed work
  can never present itself as finished.
- Steps run in exact authored order, and only one step may run at a time. Both
  are enforced at construction and at transition.
- Failure and cancellation preserve already-completed steps rather than rewriting
  history. Cancellation touches only unfinished steps.
- Blocked is deliberately non-terminal and carries a bounded reason for review.
- Terminal states reject all further transitions. Unknown step IDs, invalid
  statuses, duplicate step IDs, empty step tuples, and over-long details are
  rejected with one bounded `ResearchError`.
- Stage 1 is domain-only: no network, LLM, provider, persistence, event-bus,
  `ResearchRun`, Brain, or desktop integration, and no schema change. Execution
  cannot yet be started by any user-reachable route.

### Verification

- The package-aware full local suite contains 1,654 passing automated tests.
- Twenty-four new tests cover terminal-status membership, inert preparation,
  authored ordering, single-running-step enforcement, full success, fabricated
  completion rejection, failure preserving progress, terminal immutability,
  blocking and cancelling a blocked plan, cancellation preserving finished steps,
  non-mutation of prior states, unknown steps, transitions outside a running
  plan, and bounded detail.
- Black, Ruff, and MyPy pass for all 363 Python source and test files.

## [0.3.123] - 2026-08-23

### Added

- `DesktopController.audit_learned_memory` issues the existing structured
  `learned_memory_audit` intent as one read-only request, so the desktop adapter
  can surface learned-memory health without new runtime behavior.

### Safety

- The adapter adds no persistence, provider, network, LLM, or mutation path. It
  is a thin pass-through to the Brain route added in 0.3.122.
- The Tkinter window is unchanged in this increment; the bounded report is
  already fully rendered in the Brain response message.

### Verification

- The package-aware full local suite contains 1,630 passing automated tests.
- One new test locks the exact structured message, source, and metadata.
- Black, Ruff, and MyPy pass for all 357 Python source and test files.

## [0.3.122] - 2026-08-23

### Added

- A read-only learned-memory audit. `LearnedMemoryAuditor` computes deterministic
  bounded metrics from learned-memory records: total records, active and
  superseded counts, superseded share, distinct identities, identities with
  history, maximum versions for one identity, conflicting-history identities, and
  duplicate value candidates.
- `LearnedMemoryAuditReport` carries those metrics plus bounded samples capped at
  10 entries each, with an explicit `samples_truncated` flag.
- `LearnedMemoryAuditApplicationService` exposes the audit through the exact
  structured `learned_memory_audit` Brain intent, following the established
  no-write preview routing pattern.
- `BrainResponse.learned_memory_audit` carries the complete immutable report.

### Safety

- The audit is strictly read-only. It never deletes, merges, compacts, rewrites,
  normalizes, or reorders stored memories, and performs no persistence mutation
  or schema change.
- Duplicate value candidates are derived only from exact value equality between
  active identities. Equal text is never asserted to mean equivalent meaning, and
  nothing is merged. The rendered message states that no equivalence was decided.
- Superseded values never produce duplicate candidates, so historical records
  cannot inflate review noise.
- The rendered message reports kinds, keys, and counts only. It never includes a
  stored learned-memory value.
- The audit issues no LLM call, no semantic query, and no network request. It
  runs only on an explicit structured request, never on an ordinary chat turn.
- Repeated audits over unchanged records return identical reports and emit no
  events.

### Verification

- The package-aware full local suite contains 1,629 passing automated tests.
- Eighteen new tests cover the empty store, active-only stores, single and
  repeated corrections, repeated identical values as history without conflict,
  same-value-different-key candidates, superseded values excluded from
  candidates, bounded truncated samples, determinism, input immutability,
  exclusion of ordinary conversation records, absence of writes and events,
  structured-intent recognition, value omission from the message, and absence of
  LLM or semantic-runtime calls on the audit route.
- Black, Ruff, and MyPy pass for all 357 Python source and test files.

## [0.3.121] - 2026-08-23

### Added

- Optional semantic relevance in ordinary chat behind
  `HYPATIA_CHAT_SEMANTIC_MEMORY_ENABLED=true`, off by default and inert unless
  the semantic-memory runtime is also enabled. A semantically related question
  can now recover a durable memory whose wording differs from the message.
- `LearnedMemoryContextService` owns learned-memory context selection for one
  user turn. `CognitiveEngine` delegates to it instead of branching inline over
  selector and limit combinations.
- One bounded `brain.chat_semantic_memory.query_failed` event reports a failed
  semantic query, carrying only the request ID and the cause class name.

### Safety

- With the flag absent, ordinary chat delegates to the existing deterministic
  loaders unchanged and issues no semantic query or embedding call.
- One user turn performs at most one semantic query. The conversation path never
  starts an index rebuild.
- No second semantic index, store, or cache exists. The service reuses
  `SemanticMemoryIndexRuntime` and `HybridSemanticMemoryRanker`.
- A semantic hit on a superseded learned-memory record is rejected, so latest-wins
  correction behavior is preserved and stale values are never resurrected.
- Absent, rebuilding, stopped, or failing semantic retrieval falls back to the
  deterministic bounded path and the conversation still succeeds.
- The fused context is deduplicated by learned-memory identity and bounded by
  `HYPATIA_LEARNED_MEMORY_CONTEXT_LIMIT` or 8 when that is unset.
- Retrieval performs no memory write. Explicit lexical recall and explicit
  semantic recall are unchanged. No persisted schema, `LLMProvider`, or
  `LearnedMemorySelector` contract changed.

### Verification

- The package-aware full local suite contains 1,611 passing automated tests.
- Twenty-one new tests cover disabled-path equivalence, semantic recovery of
  differently worded memories, exclusion of unrelated memories, the fused bound,
  keyword/semantic deduplication, rejection of superseded records, empty-result
  and provider-failure fallback, exactly one query per turn, absence of rebuilds
  from the conversation path, no memory write on retrieval, unchanged explicit
  semantic recall, and fusion against a reloaded persistent store.
- A local harness measured the fusion overhead at roughly 0.4 ms per turn over
  the lexical path with 200 learned memories and 16 semantic candidates,
  excluding the embedding call itself.
- Black, Ruff, and MyPy pass for all 352 Python source and test files.

## [0.3.120] - 2026-08-23

### Verification

- Added an end-to-end regression proving the primary natural-memory product
  behavior across a full runtime restart: a stated preference is extracted and
  persisted to the local memory file, a second Bootstrap reading the same file
  loads it, and the durable value reaches the provider prompt for a later
  question without any explicit recall command.
- The same suite asserts that an unrelated durable memory stays out of that
  prompt, that a corrected value supersedes the stale one across the restart,
  and that non-JSON extraction output leaves chat working while emitting exactly
  one bounded failure event with a `ValueError` cause.
- The tests assert the deterministic context and prompt boundary rather than any
  model-specific generated wording, so they do not depend on a particular local
  Ollama model.
- The package-aware full local suite contains 1,590 passing automated tests.
- Black, Ruff, and MyPy pass for all 349 Python source and test files.

## [0.3.119] - 2026-08-23

### Changed

- Ordinary chat now defaults to bounded, request-relevant learned memory. When
  `HYPATIA_LEARNED_MEMORY_SELECTOR` is absent, Bootstrap builds the existing
  deterministic `RankedKeywordLearnedMemorySelector` bounded to 8 memories
  instead of supplying every current learned memory unbounded.
- `HYPATIA_RANKED_LEARNED_MEMORY_SELECTOR_LIMIT` now also overrides that bound in
  the default case.

### Added

- `HYPATIA_LEARNED_MEMORY_SELECTOR=none` explicitly restores the earlier
  unbounded no-selector behavior for callers that depended on it.
- `DEFAULT_LEARNED_MEMORY_SELECTOR_LIMIT` names the default bound in one place.

### Safety

- Only the Bootstrap composition default changed. `CognitiveEngine` keeps its
  explicit-injection contract, so a directly constructed engine behaves exactly
  as before.
- Learned-memory correction and supersession are unchanged; the latest value for
  a key still wins and stale values stay out of the prompt.
- Explicit recall and semantic recall commands are unchanged.
- No persisted schema, provider, network, or retrieval-mechanism change. No
  vector database was introduced.

### Verification

- The package-aware full local suite contains 1,587 passing automated tests.
- Seven new integration tests lock relevant inclusion, unrelated exclusion, the
  bound under overflow, correction supersession, plain conversation with no
  learned memory, unchanged explicit recall, and the `none` escape hatch.
- Three existing bootstrap tests now pin the legacy unbounded path behind the
  explicit `none` value rather than absent configuration.
- Black, Ruff, and MyPy pass for all 348 Python source and test files.

## [0.3.118] - 2026-08-23

### Added

- `LLMLearnedMemoryCandidateExtractor` now detects providers that expose the
  optional `generate_json(...)` capability through a local runtime-checkable
  Protocol, matching the pattern already used by
  `LLMResearchClaimContradictionProposalProvider`.
- When that capability is present, extraction requests a bounded structured
  response: a trusted system instruction, `max_tokens=512`, and an exact JSON
  response schema whose allowed `kind` values, required fields, and
  `additionalProperties: false` constraints mirror the existing parser.
- The learned-memory prompt boundary now also owns
  `LEARNED_MEMORY_EXTRACTION_SYSTEM_INSTRUCTION`, `EXTRACTION_MAX_TOKENS`, and
  `build_learned_memory_candidate_response_schema()`, which returns a fresh
  dictionary per call so no caller can mutate shared schema state.
- Ordinary chat now emits one bounded `brain.learned_memory.extraction_failed`
  event when learned-memory extraction fails, replacing a fully silent swallow.

### Safety

- The existing parser remains the final authority. A declared schema never
  bypasses validation, so reasoning preambles and Markdown-fenced payloads are
  still rejected.
- The failure event payload carries only `request_id` and the cause class name.
  It never carries the user message, source text, candidate values, or the raw
  model response.
- No event is emitted for successful or no-op extraction, so the established
  exact conversation event order is unchanged.
- Chat still succeeds when extraction fails, and the conversation record is
  still persisted.
- `TypeError` from an incompatible provider `generate_json` signature keeps
  propagating instead of being normalized into an extraction failure.
- Providers exposing only `generate` keep their exact previous call, with no
  system instruction and empty history.
- The persisted memory schema, the global `LLMProvider` Protocol, semantic chat
  retrieval, and the learned-memory retrieval defaults are all unchanged.

### Verification

- The package-aware full local suite contains 1,580 passing automated tests.
- Twelve new focused tests lock structured-capability routing and exact
  arguments, unchanged `generate`-only fallback, `LLMError` normalization with
  preserved cause, `TypeError` propagation, parser rejection of reasoning and
  fenced output, schema freshness and parser agreement, bounded failure-event
  payload, `unknown` cause categorization, and absence of the event on both
  successful and no-op extraction.
- Black, Ruff, and MyPy pass for all 347 Python source and test files.

## [0.3.117] - 2026-08-22

### Added

- The Research workspace now exposes a dedicated `Plan draft` authored-analysis
  tab without changing the established four-step workflow or its 1080p height.
- The editor shares the explicit authored question, collects one ordered
  instruction per line, and binds optional comma-separated exact source document
  IDs from the matching line.
- `DesktopController.preview_research_plan_draft` converts only those visible
  fields into the existing structured `research_plan_draft_preview` request. The
  editor shows the complete ready or rejected Brain message in its own read-only
  result area and in the ordinary transcript.

### Safety

- Empty, duplicate, excessive, or misaligned authored rows are not silently
  repaired into a different plan. They remain visible to the existing bounded
  domain validation and return a no-write rejection.
- The desktop adds no confirmation, persistence, `ResearchRun` mutation,
  provider, network, LLM, event-bus, tool, automatic source selection, or plan
  execution path. Changing tabs and editing fields remain presentation-only.
- The new instruction, source, and result text controls follow the selected Eye
  comfort, Light, or High contrast palette and the existing 10-to-20-point text
  setting.

### Verification

- The package-aware full local suite contains 1,568 passing automated tests.
- Four new focused tests lock exact structured metadata and order, preservation
  of invalid row alignment for runtime rejection, non-text rejection before
  Brain, and complete desktop rejection rendering without confirmation.
- Black, Ruff, and MyPy pass for all 346 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory. A direct 1920-by-1080 Tkinter
  smoke check maps both aligned editors and the complete preview area, exercises
  ready and rejected Brain responses, and observes no temporary-data change.

## [0.3.116] - 2026-08-22

### Added

- The explicit structured `research_plan_draft_preview` intent now reaches the
  pure draft service through `ResearchPlanPreviewApplicationService`.
- `BrainResponse` carries the complete `ResearchPlanDraftPreview`, while
  `ResponseComposer` renders either all authored ordered steps and exact selected
  source IDs or one bounded rejection reason.
- Ready output states that explicit confirmation is still required, persistent
  writes were not used, and execution was not started. Rejected output contains
  no partial plan and makes the same no-write/no-execution guarantees.

### Safety

- The route accepts only exact structured metadata and has no plain-message
  heuristic. It does not add persistence, `ResearchRun` mutation, provider,
  network, LLM, event-bus, tool, automatic source selection, or execution work.
- Direct cognition coverage proves that preview routing leaves memory, knowledge
  documents, and published events unchanged. No desktop binding is added.

### Verification

- The package-aware full local suite contains 1,564 passing automated tests.
- Focused ResponseComposer coverage contains 66 passing tests and focused
  cognition coverage contains 267 passing tests. Six new tests lock exact ready
  and rejected messages, structured-intent recognition, metadata delegation,
  bounded missing-metadata behavior, and side-effect-free engine routing.
- Black, Ruff, and MyPy pass for all 346 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory.

## [0.3.115] - 2026-08-22

### Added

- `ResearchPlanDraftService` converts only an explicit authored question and an
  immutable ordered tuple of `(instruction, selected source IDs)` drafts into
  the stable `ResearchPlan` domain contract.
- Valid drafts receive deterministic plan-local `step-1` through `step-20`
  identities plus an injected or local plan identity and creation time.
- `ResearchPlanDraftPreview` returns either one complete immutable plan ready
  for a future explicit confirmation or one bounded validation reason with no
  partial plan.

### Safety

- Invalid question, step shape, instruction, source selection, generated plan
  identity, or creation time is converted from `ResearchError` into a no-write
  rejected preview. Unexpected programming or factory errors are not hidden.
- The service has no Brain, response, manager, store, `ResearchRun`, desktop,
  provider, network, LLM, path, event-bus, or execution integration. It does not
  persist a draft or authorize automatic source selection.

### Verification

- The package-aware full local suite contains 1,558 passing automated tests.
- Eight direct tests cover exact ordered construction, normalized plan-local
  step identities, empty source selections, input immutability, structural and
  domain failures, invalid generated values, and exclusive ready/rejected
  preview invariants.
- Black, Ruff, and MyPy pass for all 343 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory.

## [0.3.114] - 2026-08-22

### Added

- `ResearchPlan` provides the first immutable user-authored Research planning
  contract: one bounded question, one to twenty explicitly ordered steps, and a
  timezone-aware creation time.
- Each immutable `ResearchPlanStep` keeps one bounded authored instruction and
  zero to twenty exact user-selected source document IDs. An empty tuple means
  no source was selected for that step; it grants no automatic source choice.
- Plans expose only the deduplicated first-selected source order derived from
  their steps. They contain no execution status, provider instruction, or run
  lifecycle state.

### Safety

- Plan, step, instruction, and source identifiers are normalized and bounded;
  duplicate step IDs and duplicate per-step source selections are rejected.
- The domain-only slice imports no Brain, manager, store, provider, network,
  LLM, desktop, path, event bus, or execution boundary. It does not alter the
  existing `ResearchRun` schema or persistence format.

### Verification

- The package-aware full local suite contains 1,550 passing automated tests.
- Nine direct domain tests cover normalization, immutable ordered steps, explicit
  empty source selection, first-selection order, strict character/count limits,
  duplicate refusal, typed tuples, and timezone-aware creation.
- Black, Ruff, and MyPy pass for all 340 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory.

## [0.3.113] - 2026-08-22

### Changed

- Existing claim-history, accepted-source comparison, and accepted-source
  assessment previews now live behind the dedicated read-only
  `ResearchAuthoredHistoryApplicationService` application boundary.
- `CognitiveEngine` delegates those three routes at their original precedence
  points. Its size falls from 3,157 to 3,054 lines without changing any Brain
  request, response, message, persistence, provider, or UI contract.

### Safety

- The extracted service reads only existing persisted Research snapshots through
  `ResearchRunManager`. It adds no mutation, schema, store, network, provider,
  LLM, UI, or automatic-analysis behavior.
- Missing or invalid identifiers, duplicate or out-of-bound comparison source
  selections, unavailable persistence, unknown runs, and unaccepted sources
  retain their exact bounded failure responses.

### Verification

- The package-aware full local suite contains 1,541 passing automated tests.
- Focused cognition coverage contains 263 passing tests, including eight direct
  service contract tests for exact recognition, validation, dependency absence,
  domain failures, raw identifier delegation, and successful composition.
- Black, Ruff, and MyPy pass for all 337 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory.

## [0.3.112] - 2026-08-22

### Changed

- Research-run listing, one-run evidence listing, accepted-content restoration
  status, and evidence-integrity status now live behind the dedicated read-only
  `ResearchOverviewApplicationService` application boundary.
- `CognitiveEngine` delegates those four existing routes at their original
  precedence points. Its size falls from 3,243 to 3,157 lines without changing
  any Brain request, response, message, persistence, provider, or UI contract.

### Safety

- The extracted service only composes already supported read results. It adds no
  mutation, schema, persistence, network, provider, LLM, UI, or automatic-
  analysis behavior.
- Missing persistence and audit dependencies, invalid or missing run IDs,
  unknown runs, and `ResearchError` audit failures retain their exact bounded
  failure or unavailable responses.

### Verification

- The package-aware full local suite contains 1,533 passing automated tests.
- Focused cognition coverage contains 255 passing tests, including 11 direct
  service contract tests for recognition, exact delegation, validation,
  dependency absence, successful snapshots, and safe audit degradation.
- Black, Ruff, and MyPy pass for all 335 Python source and test files.
- The pinned Windows onedir package builds and initializes its local session
  snapshot in a fresh temporary data directory.

## [0.3.111] - 2026-08-22

### Changed

- Research catalog filtering, status facets, deterministic ordering, run
  progress/coverage/metadata, and canonical selected-source presentation now
  live in one immutable `ResearchWorkspaceReadModel` outside Tkinter.
- `TkinterDesktopWindow` delegates those existing values through frozen run and
  source read views. Its size falls from 4,631 to 4,437 lines while adding the
  requested startup sizing, without changing
  any visible text, command, field, provider, persistence, or runtime contract.
- The desktop now requests a 1,920-by-1,080-pixel initial client area, centers
  that size on larger displays, and clamps both dimensions to smaller screens.
  The window remains resizable and retains a screen-safe bounded minimum.

### Safety

- The read model accepts only already loaded immutable snapshots and imports no
  Tkinter, Brain, controller, manager, provider, path, network, or store boundary.
- Exact canonical source membership, external-data taint, instruction authority
  `none`, current/superseded assessment handling, unique evidence membership,
  deterministic ties, and URL/content exclusion remain unchanged.
- Initial sizing is presentation-only and opens no runtime boundary. Invalid
  screen dimensions are rejected by the pure sizing helper.

### Verification

- The package-aware full local suite contains 1,522 passing automated tests.
- Focused desktop coverage contains 163 passing tests, including direct frozen
  read-model coverage for empty catalogs, exact filtering, deterministic ties,
  duplicate evidence, hidden source membership, superseded/foreign records,
  canonical-source refusal, safe URL-free details, exact 1,920-by-1,080 sizing,
  smaller-screen fitting, and invalid-dimension refusal.
- Black, Ruff, and MyPy pass for all 333 Python source and test files.
- A real Tk check reports `1920x1080+0+0` on the current 1,920-by-1,080
  display. The pinned Windows onedir package builds and initializes its local
  session snapshot in a fresh temporary data directory.

## [0.3.110] - 2026-08-22

### Added

- Sources & evidence now provides one explicit `Source details` action for the
  selected accepted source without adding another layout row.
- The read-only dialog shows normalized bounded title, exact source/run IDs,
  persisted content type, and timezone-aware fetched/accepted timestamps at
  seconds precision.

### Safety

- Details require complete canonical source-record membership in the selected
  immutable run. Changed, foreign, empty, or stale selection is refused.
- The dialog deliberately excludes source URL and content, changes no authored
  field, and opens no controller, provider, persistence, network, or mutation
  boundary.

### Verification

- The package-aware full local suite contains 1,510 passing automated tests.
- Focused desktop coverage contains 151 passing tests, including exact safe
  fields, timezone precision, URL exclusion, canonical-record refusal,
  no-selection refusal, field isolation, and zero controller calls.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one `Source details`
  button in the established 954-by-973-pixel requested window.

## [0.3.109] - 2026-08-22

### Added

- The selected-source summary now reports unique recorded evidence explicitly
  cited by current assessments beside the source's complete evidence count.
- The existing Records line keeps evidence, assessment history/current totals,
  and current cited-evidence coverage together without adding window height.

### Safety

- Citation membership uses only non-superseded assessments for the exact source
  and only evidence IDs present in that source's immutable evidence records.
  Repeated IDs count once; superseded, foreign, or unknown IDs cannot contribute.
- The count is an audit inventory, not a completeness or quality verdict. It
  opens no controller, provider, persistence, network, or mutation boundary.

### Verification

- The package-aware full local suite contains 1,506 passing automated tests.
- Focused desktop coverage contains 147 passing tests, including repeated
  citations, corrections, foreign/unknown IDs, zero evidence, exact provenance,
  safety separation, and hidden-source restoration.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the four-line summary
  preserves the established desktop window boundary.

## [0.3.108] - 2026-08-22

### Added

- The selected-source summary now reports the complete distribution of current
  user-authored information-trust labels: Unassessed, Low, Medium, and High.
- Provenance, persisted safety boundary, record totals, and current trust
  distribution are separated into four explicit read-only lines for clarity.

### Safety

- Distribution membership includes only non-superseded assessments for the
  exact selected source. Superseded history remains in the history total but
  not the trust counts; foreign-source records cannot contribute.
- Counts describe authored labels only. They infer no verdict or quality and
  cannot change the source's independent instruction authority `none`; no
  controller, provider, persistence, network, or mutation boundary opens.

### Verification

- The package-aware full local suite contains 1,505 passing automated tests.
- Focused desktop coverage contains 146 passing tests, including all four trust
  labels, corrected/superseded history, foreign-record isolation, zero counts,
  safety-boundary separation, and hidden-source restoration.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the structured four-line
  summary preserves the established desktop window boundary.

## [0.3.107] - 2026-08-22

### Added

- The selected-source summary now exposes the canonical persisted safety
  boundary beside provenance: data taint `external_untrusted_data` and
  instruction authority `none`.

### Safety

- Safety text is derived only from the complete canonical source record already
  bound to the immutable run; it makes no new trust, quality, or authority
  decision and opens no controller, provider, persistence, network, or mutation
  boundary.
- A user-authored high information-trust assessment cannot alter or obscure the
  source's untrusted-data taint or grant instruction authority. Hidden/invalid
  state continues to clear the entire source summary.

### Verification

- The package-aware full local suite contains 1,504 passing automated tests.
- Focused desktop coverage contains 145 passing tests, including canonical
  safety-boundary presentation, high-information-trust isolation, exact
  provenance/counts, canonical-record refusal, and hidden-source restoration.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the wrapped safety line
  preserves the established desktop window boundary.

## [0.3.106] - 2026-08-22

### Added

- The selected-source record summary now keeps a normalized bounded source
  title, exact source document ID, and exact immutable research-run ID visible
  beside the evidence and assessment counts.

### Safety

- Summary binding requires the complete selected source record to match one
  canonical source in the selected immutable run. A changed or foreign record
  is refused rather than presenting counts under misleading provenance.
- Untrusted title whitespace is normalized and display length is bounded while
  both identity fields remain exact. Hidden/invalid state still clears the
  summary, no quality or trust is inferred, and no runtime or mutation boundary
  opens.

### Verification

- The package-aware full local suite contains 1,503 passing automated tests.
- Focused desktop coverage contains 144 passing tests, including exact source/
  run provenance, canonical-record refusal, whitespace normalization, title
  bounds, record counts, correction history, and hidden-source restoration.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one wrapped provenance/
  record-summary label in the existing desktop window.

## [0.3.105] - 2026-08-22

### Added

- Sources & evidence now shows one compact read-only record summary for the
  selected accepted source: exact evidence count, authored assessment-history
  count, and current authored-assessment count.

### Safety

- The summary derives only from the already loaded immutable run and selected
  exact source ID. Correction records remain visible in history while only
  non-superseded records count as current; foreign malformed records cannot
  inflate the selected source.
- Hidden, empty, or invalid source presentation clears the summary instead of
  retaining stale data. The summary infers no quality or trust and opens no
  controller, provider, persistence, network, or mutation boundary.

### Verification

- The package-aware full local suite contains 1,501 passing automated tests.
- Focused desktop coverage contains 142 passing tests, including exact
  evidence/history/current counts, correction history, foreign-record
  isolation, zero records, and hidden-source clearing/restoration.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one bound selected-source
  summary label in the existing desktop layout.

## [0.3.104] - 2026-08-22

### Added

- Sources & evidence now provides one explicit `Show active source` recovery
  action beside the accepted-source coverage catalog summary.
- The action restores All sources and reselects the exact active source when a
  local coverage view has hidden it.

### Safety

- Recovery requires the current run ID, loaded immutable run, source catalog,
  and active source ID to agree exactly. Empty, stale, or unknown identity state
  is refused without changing the prior view.
- Restoring the source rehydrates only its read-only evidence and assessment
  presentation. Catalog totals, authored fields, and persisted state remain
  unchanged, and no runtime or mutation boundary opens.

### Verification

- The package-aware full local suite contains 1,499 passing automated tests.
- Focused desktop coverage contains 140 passing tests, including hidden-source
  restoration, exact identity and read-only record rehydration, empty/stale/
  unknown state refusal, catalog-summary invariance, and field isolation.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one recovery button in
  the existing 954-by-973-pixel requested window.

## [0.3.103] - 2026-08-22

### Added

- Sources & evidence now shows one compact read-only accepted-source coverage
  catalog summary for the selected immutable run.
- The summary reports complete All, Without evidence, and Without current
  assessment counts independently of the active local source view.

### Safety

- Repeated evidence and current assessment records count one source once.
  Correction chains exclude superseded history, while malformed foreign records
  cannot inflate or hide accepted-source membership.
- Source-view changes cannot alter the catalog totals, exact active identity, or
  authored fields. Empty/invalid selection clears stale totals, no quality or
  readiness is inferred, and no runtime or mutation boundary opens.

### Verification

- The package-aware full local suite contains 1,495 passing automated tests.
- Focused desktop coverage contains 136 passing tests, including repeated and
  foreign records, correction/superseded-only history, empty catalogs, selected
  run binding, facet invariance, identity preservation, and field isolation.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one bound summary label
  in the existing 954-by-973-pixel requested window.

## [0.3.102] - 2026-08-22

### Added

- Sources & evidence now provides a third local accepted-source view: Without
  current assessment.
- The view derives stable source membership from the selected immutable run and
  shares the same current-assessment definition as the Overview coverage line.

### Safety

- Superseded-only assessment history remains uncovered, repeated current
  assessments count a source once, and malformed foreign assessment records
  cannot hide an accepted source.
- A visible or hidden active source keeps its exact identity and is restored by
  All sources. Authored fields remain unchanged; invalid or stale state leaves
  the prior view intact and no runtime or mutation boundary opens.

### Verification

- The package-aware full local suite contains 1,492 passing automated tests.
- Focused desktop coverage contains 133 passing tests, including correction
  chains, repeated current records, foreign/superseded-only history, stable
  order, visible and hidden active identity, restoration, and no-match state.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one read-only three-choice
  selector in the existing 954-by-973-pixel requested window.

## [0.3.101] - 2026-08-22

### Added

- Research Overview now shows one read-only current-assessment coverage summary
  for the selected immutable run snapshot.
- The summary reports accepted sources, sources having a current authored
  assessment, and accepted sources without a current assessment.

### Safety

- Superseded assessment history does not count as current, and multiple current
  records for one accepted source count that source once. Malformed foreign
  assessment references cannot inflate coverage.
- Empty and invalid selections replace stale coverage with explicit guidance.
  The summary infers no quality, truth, completeness, or readiness and opens no
  Brain, controller, storage, provider, network, LLM, index, event-bus, or
  mutation boundary.

### Verification

- The package-aware full local suite contains 1,488 passing automated tests.
- Focused desktop coverage contains 129 passing tests, including correction
  chains, source deduplication, superseded-only history, malformed foreign
  references, empty runs, valid selection binding, and stale-state clearing.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the additional bound
  coverage label remains within the existing 954-by-973-pixel requested window.

## [0.3.100] - 2026-08-22

### Added

- Sources & evidence now provides an explicit local accepted-source view with
  All sources and Without evidence choices.
- The view derives stable membership from the selected immutable run, reports
  visible/total counts, and preserves a visible or hidden active source ID.

### Safety

- Repeated evidence for one source does not affect membership, and malformed
  foreign evidence cannot hide an accepted source. Hidden active sources are
  restored exactly when All sources is selected again.
- View changes preserve run/source identity and authored fields and open no
  Brain, controller, storage, provider, network, LLM, index, event-bus, or
  mutation boundary. Invalid or stale local state leaves the prior view intact.

### Verification

- The package-aware full local suite contains 1,485 passing automated tests.
- Focused desktop coverage contains 126 passing tests, including stable order,
  repeated/foreign evidence, visible and hidden active identity, restoration,
  no-match, empty catalog, invalid facet, and stale-snapshot isolation.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one read-only two-choice
  selector in the existing 954-by-973-pixel requested window.

## [0.3.99] - 2026-08-22

### Added

- Research Overview now shows one read-only evidence-coverage summary for the
  selected immutable run snapshot.
- The summary reports complete accepted-source, represented-source, and
  accepted-source-without-evidence counts without a score or readiness claim.

### Safety

- Multiple evidence records for one source count that source once. A malformed
  foreign evidence reference cannot inflate represented membership.
- Empty and invalid selections replace stale coverage with explicit guidance.
  Selection opens no Brain, controller, storage, provider, network, LLM,
  index, event-bus, or mutation boundary.

### Verification

- The package-aware full local suite contains 1,479 passing automated tests.
- Focused desktop coverage contains 120 passing tests, including repeated
  evidence for one source, empty coverage, malformed foreign references,
  selection binding, empty catalogs, and invalid-selection clearing.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one bound coverage label
  in the existing 954-by-973-pixel requested window.

## [0.3.98] - 2026-08-22

### Added

- Research Overview now provides one explicit `Reset view` action for the
  local run-catalog controls.
- Reset clears the bounded text and status filters, restores Updated-newest
  sorting, re-shows the complete catalog, and reselects a loaded active run.

### Safety

- Reset changes presentation state only. It preserves the immutable loaded
  catalog, exact active run identity, authored assessment/claim fields, and the
  complete catalog summary and opens no runtime or mutation boundary.
- Empty catalogs and stale active IDs are explicit. Neither case selects a
  different row, and invalid local filter/sort state can be safely recovered.

### Verification

- The package-aware full local suite contains 1,476 passing automated tests.
- Focused desktop coverage contains 117 passing tests, including hidden active
  restoration, default sort, authored-field preservation, empty catalogs,
  stale active identity, and controller isolation.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the action in the
  existing 1080p-safe desktop layout.

## [0.3.97] - 2026-08-22

### Added

- Research Overview now shows one compact complete catalog summary with All,
  Collecting, Completed, Failed, and Cancelled counts.
- Counts are derived from the full already loaded run tuple and remain truthful
  while text filtering, status filtering, or local sorting changes the view.

### Safety

- The summary is presentation-only. It preserves the immutable catalog, active
  run, visible selection, and authored fields and opens no Brain, controller,
  storage, provider, network, LLM, index, event-bus, or mutation boundary.
- Empty catalogs show explicit zero counts for every lifecycle instead of stale
  values. Filtering changes neither the summary nor its source tuple.

### Verification

- The package-aware full local suite contains 1,473 passing automated tests.
- Focused desktop coverage contains 114 passing tests, including every
  lifecycle, repeated lifecycle membership, the empty catalog, and
  text/status-filter invariance.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the read-only catalog
  summary in the existing 1080p-safe desktop layout.

## [0.3.96] - 2026-08-22

### Added

- Research Overview now provides an explicit local status view with All,
  Collecting, Completed, Failed, and Cancelled choices.
- The status choice composes with the bounded text filter and current
  deterministic sort. Visible/total feedback includes the selected status.

### Safety

- Status filtering reads only the immutable loaded run catalog. It preserves
  the active run and authored fields and opens no Brain, controller, storage,
  provider, network, LLM, index, event-bus, or mutation boundary.
- Clearing the text filter preserves the status choice. `Show active run`
  clears both presentation filters while preserving sort; invalid status state
  leaves the prior visible tuple unchanged.

### Verification

- The package-aware full local suite contains 1,471 passing automated tests.
- Focused desktop coverage contains 112 passing tests, including every exact
  lifecycle, text/status/sort composition, status-preserving text clear,
  no-match active/authored-field preservation, and invalid-state isolation.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms the read-only five-choice
  status selector in a 954-by-973-pixel requested window.

## [0.3.95] - 2026-08-22

### Added

- Research Overview now provides an explicit `Show active run` action when the
  local filter hides the currently active research run.
- The action restores the complete loaded view in the already selected order,
  makes the active run visible in the selector, and reports the exact outcome.

### Safety

- Showing the active run clears only the presentation filter. It preserves the
  selected sort, immutable loaded catalog, active run, and authored fields and
  opens no Brain, controller, storage, provider, network, LLM, index, event-bus,
  or mutation boundary.
- Missing, stale, or invalid local selection/sort state leaves the prior filter
  and visible tuple unchanged and replaces ambiguous behavior with guidance.

### Verification

- The package-aware full local suite contains 1,467 passing automated tests.
- Focused desktop coverage contains 108 passing tests, including hidden active-
  run restoration, sort and authored-field preservation, no-selection and
  stale-catalog isolation, and invalid-sort refusal.
- Black, Ruff, and MyPy pass. A real Tk smoke confirms one working action and
  its empty state in a 954-by-973-pixel requested window.

## [0.3.94] - 2026-08-22

### Added

- Research Overview can sort the current loaded or filtered run view by newest
  update, oldest update, newest creation, or question text.
- One explicit current-sort line remains visible beside the read-only selector.
  Equal timestamps and equal case-folded questions use ascending exact run IDs
  as deterministic tie breaks.

### Safety

- Sorting reorders only the current presentation tuple. It does not change the
  immutable loaded catalog, filter membership, active run, or authored fields,
  and it opens no Brain, controller, storage, provider, network, LLM, index,
  event-bus, or mutation boundary.
- Refresh and filter application reuse the selected sort. Invalid local sort
  state leaves the visible view untouched, and hidden active runs remain active
  until the user explicitly chooses another visible run.

### Verification

- The package-aware full local suite contains 1,463 passing automated tests.
- Focused desktop coverage contains 104 passing tests, including all four sort
  modes, deterministic ties, filter-membership isolation, active-selection and
  authored-field preservation, and invalid-state isolation.
- Black, Ruff, and MyPy pass. A real Tk measurement confirms the read-only sort
  selector in a 954-by-973-pixel requested window.

## [0.3.93] - 2026-08-22

### Added

- Research Overview now shows the selected run's immutable creation and update
  timestamps as seconds-level timezone-aware ISO-8601 text.
- The same metadata line reports the complete count of persisted safe failures.
  Empty and invalid selection states replace stale metadata with guidance.

### Safety

- Metadata is derived only from the already selected immutable `ResearchRun`
  snapshot. Failure stage/reason details are never presented, and no Brain,
  controller, storage, provider, network, LLM, index, event-bus, or mutation
  boundary is opened.
- Filtering and hidden/no-match active-run behavior remain presentation-only;
  all authored fields and existing run-bound views are preserved.

### Verification

- The package-aware full local suite contains 1,460 passing automated tests.
- Focused desktop coverage contains 101 passing tests, including timezone-aware
  bounded formatting, exact failure count, failure-detail hiding, and selected,
  empty, and invalid metadata states.
- Black, Ruff, and MyPy pass. A real Tk measurement confirms one metadata label
  in a 954-by-973-pixel requested window.

## [0.3.92] - 2026-08-22

### Added

- Research Overview can filter the already loaded run catalog by case-
  insensitive bounded question text, exact status, or exact run ID.
- A persistent local result summary reports matching/total counts, an explicit
  no-match state, or an overlong-filter refusal; `Clear` restores the full
  loaded catalog.

### Safety

- Filtering is presentation-only and capped at 200 characters. It never opens
  a Brain, controller, storage, provider, network, LLM, index, event-bus, or
  mutation boundary and never modifies the immutable full catalog.
- A still-visible active run remains selected. A hidden or no-match active run
  remains active until the user explicitly chooses another visible run; all
  authored fields and run-bound presentations remain unchanged.

### Verification

- The package-aware full local suite contains 1,459 passing automated tests.
- Focused desktop coverage contains 100 passing tests for question/status/exact-
  ID matching, partial-ID refusal, visible selection preservation, no-match
  field preservation, clear restoration, and overlong input isolation.
- Black, Ruff, and MyPy pass. A real Tk measurement confirms one filter field
  and its Filter/Clear controls in a 954-by-973-pixel requested window.

## [0.3.91] - 2026-08-22

### Added

- Research Overview now includes one compact `Workflow snapshot` for the
  selected run: complete source/evidence counts, authored assessment/comparison-
  note/claim/contradiction counts, and the existing review status.
- Empty and invalid selections replace stale stage records with direct guidance.

### Safety

- The snapshot reads only the already selected immutable `ResearchRun` object.
  It does not infer readiness or truth, recommend a conclusion, change status,
  hide controls, or open a Brain, controller, manager, provider, persistence,
  network, LLM, index, event-bus, or mutation boundary.
- Existing fields, commands, confirmations, schemas, and provider paths remain
  unchanged.

### Verification

- The package-aware full local suite contains 1,455 passing automated tests.
- Focused desktop coverage contains 96 passing tests, including every displayed
  stage count/status plus selected, empty, and invalid snapshot states.
- Black, Ruff, and MyPy pass. A real Tk measurement confirms one workflow-
  snapshot label in a 954-by-973-pixel requested window.

## [0.3.90] - 2026-08-22

### Added

- The shared current-run banner on Sources & evidence, Authored analysis, and
  Review & export now includes complete source, evidence, and claim counts.
- Empty or invalid run selections replace stale counts with explicit progress-
  unavailable guidance.

### Safety

- Progress is calculated only from the already selected immutable `ResearchRun`
  snapshot. It opens no Brain, controller, manager, storage, provider, network,
  LLM, knowledge-index, event-bus, or mutation boundary.
- The three tabs share one presentation value; all existing fields, commands,
  confirmations, schemas, provider paths, and mutation contracts remain intact.

### Verification

- The package-aware full local suite contains 1,454 passing automated tests.
- Focused desktop coverage contains 95 passing tests, including complete count
  formatting and selected, empty, and invalid presentation states.
- Black, Ruff, and MyPy pass. A real Tk measurement confirms three context and
  three progress labels in a 954-by-973-pixel requested window.

## [0.3.89] - 2026-08-22

### Added

- Sources & evidence, Authored analysis, and Review & export now show the same
  read-only `Current research run` banner with the selected question, status,
  and exact run ID.
- Empty and invalid selections replace stale context with direct guidance to
  return to Overview, refresh the catalog, or start a research run.

### Safety

- The banner is derived only from the already selected immutable `ResearchRun`
  snapshot. It opens no Brain, controller, storage, provider, network, LLM,
  knowledge-index, event-bus, or mutation boundary.
- Existing fields, commands, tab navigation, confirmation boundaries, provider
  paths, persistence schemas, and mutation contracts remain unchanged.

### Verification

- The package-aware full local suite contains 1,453 passing automated tests.
- Focused desktop coverage contains 94 passing tests for exact run identity,
  bounded long questions, selected/empty/invalid states, and existing workflow
  behavior.
- Black, Ruff, and MyPy pass, and a real Tk measurement confirms three bound
  context labels in a 954-by-973-pixel requested window.

## [0.3.88] - 2026-08-22

### Changed

- The dense desktop Research workspace is now presented as four ordered workflow
  tabs: Overview, Sources & evidence, Authored analysis, and Review & export.
- Authored analysis has four compact sub-tabs for saved records, comparison,
  assessment, and claims/contradictions so the complete workspace fits a 1080p
  desktop without hiding controls below the screen.
- Each section includes concise guidance while retaining every existing field,
  selector, button, confirmation boundary, and keyboard-reachable control.

### Safety

- Changing workflow or analysis tabs is presentation-only and starts no Brain,
  controller, storage, provider, network, LLM, knowledge-index, event-bus, or
  mutation work.
- The exact multisets of 59 existing command bindings and 41 field bindings are
  preserved from v0.3.87; no research contract or persisted schema changes.

### Verification

- The package-aware full local suite contains 1,452 passing automated tests.
- Focused desktop coverage contains 93 passing tests, including the exact ordered
  workflow and analysis section labels.
- A real Tk layout measurement confirms a 973-pixel requested window height on a
  1080-pixel desktop, down from the initial 1,110-pixel intermediate layout.

## [0.3.87] - 2026-08-22

### Added

- The selected desktop research run now exposes its persisted user-authored
  source-comparison notes from the already loaded immutable run snapshot.
- Each selector label retains bounded authored text, timezone-aware recorded
  time, and exact note ID; a separate read-only summary shows every exact source,
  evidence, and assessment reference.
- Three separate explicit actions can copy only the selected note's source,
  evidence, or assessment references into the matching manual field.

### Safety

- Selecting a comparison note never edits form fields or starts Brain, storage,
  provider, network, LLM, knowledge-index, event-bus, or mutation work.
- Each handoff preserves the authored comparison text and all non-target fields;
  stale or invalid selections are cleared or refused locally.

### Verification

- The package-aware full local suite contains 1,451 passing automated tests.
- Focused desktop coverage contains 92 passing tests for immutable-snapshot
  rendering, bounded labels, complete exact-reference summaries, selection-only
  behavior, isolated handoffs, field preservation, and stale-run guards.

## [0.3.86] - 2026-08-21

### Added

- The selected desktop research run now exposes its persisted user-reviewed
  claim contradictions from the already loaded immutable run snapshot.
- Contradiction labels retain the exact claim pair, bounded authored note,
  timezone-aware recorded time, and exact contradiction ID.
- A separate explicit action can copy one recorded exact pair into the manual
  contradiction field while preserving the authored note field.

### Safety

- Selecting or handing off a persisted contradiction never starts Brain,
  storage, provider, network, LLM, knowledge-index, event-bus, or mutation work.
- Stale and invalid selections are cleared or refused locally without changing
  either manual contradiction field.

### Verification

- The package-aware full local suite contains 1,447 passing automated tests.
- Focused desktop coverage contains 88 passing tests for immutable-snapshot
  rendering, exact pair/time/ID labels, bounded notes, field preservation,
  explicit pair handoff, invalid selection, and stale-run guards.

## [0.3.85] - 2026-08-21

### Added

- The selected desktop research run now exposes its user-authored claims from
  the already loaded immutable run snapshot.
- Claim labels distinguish `current` and `superseded` audit state while showing
  bounded authored text, epistemic state, categorical confidence, and exact ID.
- Separate explicit actions can copy one current claim ID into the manual
  predecessor field or append it to the two-ID contradiction field.

### Safety

- Selecting a claim never edits authored fields or starts Brain, storage,
  provider, network, LLM, knowledge-index, event-bus, or mutation work.
- Superseded, stale, duplicate, and over-two contradiction selections are
  refused locally without changing form values.

### Verification

- The package-aware full local suite contains 1,443 passing automated tests.
- Focused desktop coverage contains 84 passing tests for audit-state rendering,
  uncertainty labels, current-record preference, exact-ID handoff, duplicate and
  two-ID limits, field preservation, and stale-selection guards.

## [0.3.84] - 2026-08-21

### Added

- The accepted source currently selected in the desktop now exposes its
  user-authored assessments from the already loaded immutable run snapshot.
- Assessment labels distinguish `current` and `superseded` audit state while
  retaining bounded authored text and the exact assessment ID.
- Explicit actions can copy one current assessment ID into the manual
  correction-target field or append it to comparison-assessment IDs.

### Safety

- Selecting a source or assessment never edits authored fields or starts Brain,
  storage, provider, network, LLM, knowledge-index, or mutation work.
- Superseded, stale, cross-source, duplicate, non-comparison-source, and over-50
  comparison selections are refused locally without changing form values.

### Verification

- The package-aware full local suite contains 1,439 passing automated tests.
- Focused desktop coverage contains 80 passing tests for audit-state rendering,
  current-record preference, exact-ID handoff, ownership, duplicate/limit, and
  stale-selection guards.

## [0.3.83] - 2026-08-21

### Added

- The accepted source currently selected in the desktop now exposes only its
  persisted evidence from the already loaded research-run snapshot.
- Evidence labels show a bounded single-line excerpt and the exact evidence ID.
- Separate explicit handoffs append the exact ID to the manual assessment,
  claim, or comparison evidence field.

### Safety

- Selecting a source or evidence record edits no manual field and starts no
  Brain, store, provider, network, LLM, knowledge-index, or mutation operation.
- Assessment handoff requires the same accepted-source ID. Comparison handoff
  requires that source in the manual comparison, while claim and comparison
  limits remain 20 and 100 evidence IDs. Duplicate and stale cross-run/source
  selections cannot overwrite authored fields.

### Verification

- The package-aware full local suite contains 1,435 passing automated tests.
- Focused desktop coverage contains 76 passing tests for source filtering,
  exact-ID handoff, ownership guards, duplicate prevention, limits, and stale
  selection rejection.

## [0.3.82] - 2026-08-21

### Added

- The selected research run now exposes its accepted sources in a read-only
  desktop selector labelled with bounded title text and the exact document ID.
- Separate `Use for assessment` and `Add to comparison` actions copy only the
  selected exact ID into the corresponding existing manual field.

### Safety

- Merely selecting or refreshing a run never overwrites either manual source
  field and starts no Brain, store, provider, network, or mutation operation.
- Accepted-source choices are tied to one exact loaded run snapshot. Stale
  cross-run choices are cleared and refused, duplicate comparison IDs are not
  added, and the existing five-source comparison limit is preserved.

### Verification

- The package-aware full local suite contains 1,430 passing automated tests.
- Focused desktop coverage verifies snapshot-only rendering, exact-ID handoff,
  manual-field isolation, duplicate prevention, and stale-run rejection.

## [0.3.81] - 2026-08-21

### Added

- The selected research run now has a compact read-only summary directly below
  the desktop selector: status plus complete source, evidence, and claim counts.
- Empty and invalid selection states provide explicit guidance instead of
  retaining a stale summary.

### Safety

- The summary is computed only from the already loaded immutable catalog
  snapshot. It opens no Brain, storage, provider, network, or mutation path.
- Counts are complete collection sizes, not model estimates or silently
  truncated detail counts.

### Verification

- The package-aware full local suite contains 1,425 passing automated tests.
- Focused coverage verifies collecting/completed summaries, selection changes,
  empty catalogs, invalid selection, and zero side-effect catalog behavior.

## [0.3.80] - 2026-08-21

### Added

- `Research runs` now populates a read-only desktop selector whose labels show
  each persisted question, run status, and exact run ID.
- Creating a run immediately places the new record in the same selector, so
  ordinary research actions no longer require manual run-ID copy and paste.

### Changed

- Refresh preserves the current run when it still exists; otherwise it selects
  the first persisted result. An empty catalog clears the selected run.
- Changing runs clears only stale presentation state tied to the prior run:
  source candidates, contradiction suggestions, and export preview.

### Safety

- Catalog refresh and selection are local, read-only presentation actions. They
  start no discovery, source load, provider, network, or research mutation.
- User-authored research fields remain untouched, and the status line explicitly
  reports that selection started no action.

### Verification

- The package-aware full local suite contains 1,424 passing automated tests.
- Focused coverage verifies catalog rendering, created-run selection,
  empty-catalog clearing, run switching, and absence of runtime side effects.

## [0.3.79] - 2026-08-21

### Added

- Successful contradiction suggestions now populate a read-only desktop pair
  selector for the exact research run that produced them.
- `Use selected pair` copies only the chosen two persisted claim IDs into the
  existing manual contradiction form.

### Changed

- Starting a new suggestion or creating a different research run clears the
  ephemeral candidate selector. A run mismatch also discards stale candidates
  before refusing the handoff.

### Safety

- Selecting a pair never copies model rationale into the user's note, invokes a
  provider, records a relationship, or bypasses preview, confirmation, and final
  runtime revalidation.
- The user's existing note remains untouched and the interface states that
  nothing was recorded.

### Verification

- The package-aware full local suite contains 1,422 passing automated tests.
- Focused coverage verifies successful handoff, unchanged authored notes,
  cancellable generation, stale-run rejection, and selector clearing.

## [0.3.78] - 2026-08-21

### Added

- An explicit desktop action can ask the configured LLM for up to ten possible
  contradiction pairs among at most fifty current, non-superseded claims.
- Every read-only candidate cites exactly two persisted claim IDs and the exact
  ordered evidence union derived by Hypatia from those claims; model-authored
  rationale remains visibly labelled as an untrusted review suggestion.

### Changed

- The OpenAI-compatible provider supports bounded JSON-schema completions with
  reasoning disabled and deterministic sampling for this structured review
  task. Providers without that extension retain the existing strict JSON
  fallback contract.
- Already recorded unordered claim pairs are omitted, and a changed research
  run invalidates the provider result before it can be displayed.

### Safety

- Candidate generation runs only after the user selects `Suggest
  contradictions`. It receives no conversation history, tools, or instruction
  authority from research data and performs no persistence.
- Hypatia still does not decide truth, rewrite claims, select evidence from
  model output, create a relationship automatically, or bypass the existing
  user-authored note, preview, confirmation, and final revalidation boundary.

### Verification

- The package-aware full local suite contains 1,420 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 331 source files.
- The focused suite was also exercised against local Ollama `qwen3:4b`; one
  ephemeral contradictory pair returned in about four seconds without changing
  project data.

## [0.3.77] - 2026-08-21

### Added

- A collecting research run can preview and append one explicit user-reviewed
  contradiction relationship between exactly two persisted claims.
- Each append-only relationship stores the selected claim order, the exact
  de-duplicated evidence union derived from both claims, a required
  user-authored note, its own ID, and a timezone-aware audit timestamp.
- Brain, the desktop Research tab, read-only history, committed responses, and
  deterministic Markdown exports expose the persisted relationship.

### Changed

- Research-run schema v9 persists claim contradictions while loading v1-v8
  snapshots with an empty contradiction collection and rewriting them only
  during a later successful atomic save.
- A reversed claim pair is treated as the same relationship, so the same two
  claims cannot receive duplicate contradiction records.

### Safety

- Preview is read-only. Recording requires a separate desktop confirmation and
  final runtime revalidation of the open run, both claims, their evidence, the
  duplicate-pair guard, and atomic persistence.
- Hypatia does not detect contradictions automatically, choose claims or
  evidence, decide truth, rewrite either claim, or grant external source text
  instruction authority.

### Verification

- The package-aware full local suite contains 1,403 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 326 source files.

## [0.3.76] - 2026-08-21

### Added

- The desktop now separates Chat, Knowledge, Research, and Appearance into
  dedicated tabs so ordinary conversation is not crowded by specialist tools.
- A soft eye-comfort theme is the default, with separate light and high-contrast
  choices plus the existing 10-to-20-point text-size controls.
- Empty session lists, unavailable session data, the conversation transcript,
  and the message composer now provide concise guidance instead of blank space.

### Changed

- Session, recall, knowledge, and research controls use clearer labels and more
  compact grouped layouts. Session actions share consistent widths, and the
  message composer advertises its `Ctrl+Enter` shortcut.
- Tkinter uses a style backend and explicit active, focused, disabled,
  read-only, selection, border, and scrollbar colors so native Windows widgets
  remain readable in every supported theme.

### Accessibility

- The default palette avoids pure black and pure white while retaining visible
  focus and selection states. High contrast remains an explicit opt-in mode.
- Theme and text-size changes remain presentation-only: they do not invoke a
  provider or change conversation, session, memory, knowledge, or research
  state.

### Verification

- The package-aware full local suite contains 1,388 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 322 source files.

## [0.3.75] - 2026-08-21

### Added

- Research runs can store explicit user-authored claims with one epistemic
  state: `fact`, `strong_evidence`, `likely`, `hypothesis`, `speculation`,
  `unknown`, or `contradicted`.
- Every claim cites persisted evidence IDs and the exact ordered accepted
  source IDs derived from that evidence. It also carries one categorical
  authored confidence label: `unassessed`, `low`, `medium`, or `high`.
- The Brain, desktop, and deterministic Markdown export expose claim history
  through read-only previews and a separate preview-confirm-record boundary.

### Changed

- Research-run schema v8 persists evidence-linked claims while loading v1-v7
  snapshots with an empty claim collection and rewriting them only during a
  later successful atomic save.
- Claim corrections append a backward supersession link. The predecessor
  remains immutable and can have at most one successor.

### Safety

- Hypatia does not extract claims automatically, select their evidence,
  calculate truth, or turn authored confidence into a numeric score.
- Final recording revalidates the collecting run, every evidence/source
  relationship, categorical values, and any supersession target. External
  source text retains instruction authority `none` regardless of claim state.

### Verification

- The package-aware full local suite contains 1,384 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 322 source files.

## [0.3.74] - 2026-08-21

### Added

- User-authored source assessments can carry one explicit information-trust
  label: `unassessed`, `low`, `medium`, or `high`.
- Accepted external sources persist the fixed taint label
  `external_untrusted_data` and fixed instruction authority `none`.
- The desktop assessment preview-confirm flow, source comparison, committed
  response, and deterministic Markdown export display the new trust metadata.

### Changed

- Research-run schema v7 stores source taint, instruction authority, and
  assessment information trust while loading v1-v6 snapshots with safe
  defaults and rewriting them only during a later successful atomic save.
- Assessment corrections may replace an earlier authored information-trust
  label through the existing append-only supersession link; the original audit
  record remains immutable.

### Safety

- Information trust describes the user's assessment of source content only.
  It never grants an external source instruction authority, tool access, or
  permission to override trusted code-owned instructions.
- Hypatia does not calculate the label, choose evidence, or convert it into an
  automatic truth, credibility, or execution score. Invalid labels and any
  attempt to elevate source authority fail closed before persistence.

### Verification

- The package-aware full local suite contains 1,366 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 316 source files.

## [0.3.73] - 2026-08-21

### Added

- A thread-safe, one-way cancellation signal can travel with an in-process
  `BrainRequest` without appearing in its representation or equality contract.
- Desktop Crossref discovery, explicit HTTPS source loading, and confirmed
  candidate loading now attach that signal to their existing Brain request.

### Changed

- Research discovery checks cancellation before provider access, after the
  bounded network call returns, after provider-contract validation, and before
  discovery persistence.
- Research source loading checks cancellation before acquisition, after the
  bounded fetch returns, and immediately before knowledge indexing begins.

### Safety

- A cancelled network result creates no discovery, failure audit, knowledge
  document, accepted-source record, or content-store write. A provider call
  already in progress is still bounded by its timeout and is never forcefully
  terminated.
- Desktop result suppression remains valid even if an optional cooperative
  callback fails. Closing the window signals cooperative cancellation and
  continues to discard late presentation results.
- Other LLM and desktop actions retain presentation-only cancellation; this
  release does not claim that every provider path can stop between stages.

### Verification

- The package-aware full local suite contains 1,362 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 315 source files.

## [0.3.72] - 2026-08-21

### Added

- The desktop status line reports elapsed whole seconds for the one active
  request without inventing a completion percentage or provider stage.
- A dedicated `Cancel request` control lets the user discard the active
  request's eventual value or error presentation.

### Safety

- Cancellation never claims to terminate an in-flight Ollama or HTTPS call.
  Normal command controls remain disabled until that bounded operation returns,
  and the late result is then replaced with one generic cancelled completion.
- A completed-but-undrained result retains the single-flight reservation, so a
  keyboard submission cannot replace its presentation handler before the
  Tkinter event thread consumes it.
- Closing the window still rejects new work and discards every late completion;
  provider and transport timeouts remain the hard bound on active I/O.

### Verification

- The package-aware full local suite contains 1,357 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 313 source files.

## [0.3.71] - 2026-08-21

### Added

- LLM providers accept one optional, trusted per-request system instruction
  without changing ordinary conversation calls or persisted configuration.
- Explicit `ask knowledge` requests use a code-owned system instruction that
  treats every retrieved source excerpt as untrusted evidence rather than an
  instruction.

### Changed

- The explicit user question is separated from bounded source excerpts, and
  every supplied excerpt is visibly labelled `UNTRUSTED SOURCE` before it is
  sent to the configured model.

### Safety

- Retrieved text is told that it has no authority to change roles or rules,
  reveal secrets, request tools or files, or override other instructions. The
  local-RAG path still receives no tool capability and uses no conversation
  history.
- This is a prompt-level instruction-authority boundary, not a claim that a
  language model can never be influenced by adversarial text. Existing source,
  response-size, transport, and user-initiation limits remain in force.

### Verification

- The package-aware full local suite contains 1,353 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 313 source files.

## [0.3.70] - 2026-08-21

### Changed

- Explicit desktop chat, semantic recall, cited knowledge questions, research
  discovery, and approved HTTPS source loading now run through one daemon
  request worker instead of holding the Tkinter event thread.
- Tkinter polls completed responses and performs every widget update on its own
  event thread. All command buttons are disabled while the single request is
  active, and a second keyboard submission is rejected instead of queued.
- Text entered in the composer while a response is pending is preserved; only
  the exact submitted text is cleared after its response is presented.

### Safety

- Window close stops accepting work, discards late results, and destroys the UI
  without forcefully terminating the provider call. Existing provider and
  transport timeouts remain the hard bound on that daemon operation.
- Expected input-validation errors remain visible. Unexpected worker,
  provider, and presentation exceptions produce one generic desktop failure
  without exposing internal transport or credential details.

### Verification

- The package-aware full local suite contains 1,350 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 313 source files.

## [0.3.69] - 2026-08-21

### Changed

- Semantic add, update, delete, and expiry maintenance now uses the same daemon
  single-worker boundary as full rebuilds. A successful primary-memory write
  returns without waiting for the local embedding provider.
- Pending incremental work is bounded to 20,000 memory IDs and deterministically
  coalesces repeated events so the last operation for one record wins.
- `semantic recall status` reports `updating` while incremental work is active;
  semantic queries use lexical fallback until the worker is idle.

### Safety

- Per-record generations reject an embedding result superseded by a later
  update or delete. A queued full rebuild runs after any in-flight incremental
  provider call and replaces queued updates from one fresh memory snapshot.
- Failed or rejected record IDs retain the generic incremental diagnostic until
  that record is successfully reconciled or a complete rebuild succeeds.
  Shutdown clears queued work and suppresses in-flight publication.

### Verification

- The package-aware full local suite contains 1,341 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.68] - 2026-08-21

### Changed

- Opt-in semantic-index initialization now starts as one daemon background job
  after Bootstrap publishes the primary dependency container. A cold or
  unavailable Ollama service no longer holds the primary startup path.
- `semantic recall status` now reports `initializing`, `refreshing`, `ready`,
  `unavailable`, `disabled`, or `stopped` without generating an embedding.
- The exact `semantic recall retry` command schedules the same bounded
  background rebuild and reports an already-running job without starting a
  duplicate. Semantic queries use deterministic lexical fallback while a
  rebuild is active.

### Safety

- Full rebuilds are single-flight. Memory events during a build mark its
  snapshot dirty and permit at most one coalesced retry; a second changing
  snapshot is rejected without publishing a partial or stale index.
- Shutdown rejects new semantic work, signals the builder to cancel, and
  suppresses index publication from in-flight work. Cancellation is checked
  after provider calls and before derived-cache replacement; the provider call
  itself remains bounded by the existing request and shared rebuild deadlines.

### Verification

- The package-aware full local suite contains 1,334 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.
- A temporary-data live smoke check against local Ollama
  `embeddinggemma:latest` built one 768-dimensional record through the
  background worker and returned it through explicit semantic recall.

## [0.3.67] - 2026-08-21

### Changed

- Full semantic-index rebuilds now share one monotonic 120-second deadline by
  default. `HYPATIA_SEMANTIC_MEMORY_REBUILD_TIMEOUT_SECONDS` accepts a positive
  finite override through 3,600 seconds.
- Each missing embedding receives only the time remaining in the shared rebuild
  budget. The Ollama transport uses the shorter of that remainder and its
  configured per-request timeout, so a rebuild cannot renew the full request
  timeout for every sequential cache miss.

### Safety

- The shared deadline begins before memory, source, and cache preflight work.
  Expiry before or after a provider call rejects the incomplete build before
  cache replacement or runtime publication.
- A cache-preflight overrun skips all provider work. A failed startup remains
  semantically unavailable, while a failed later rebuild or explicit retry
  preserves the last complete index and exposes only the existing safe rebuild
  diagnostic.

### Verification

- The package-aware full local suite contains 1,324 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.66] - 2026-08-21

### Changed

- An initial optional semantic-index failure no longer stops primary Bootstrap.
  Hypatia publishes its normal dependency container, attaches the semantic
  lifecycle listener, and keeps conversation, sessions, lexical recall, and
  primary memory available while semantic retrieval is unavailable.
- `semantic recall status` now distinguishes `unavailable` from `disabled` and
  reports separate safe full-rebuild and incremental-update diagnostics.
- An exact `semantic recall retry` request explicitly retries one complete
  rebuild through the existing source, cache, index, and provider-call bounds.

### Safety

- Rebuild failures retain the last complete index, record only the generic
  `Semantic index rebuild failed.` diagnostic, and never expose provider,
  cache, transport, or budget details through status or retry responses.
- Retry is never automatic and does not run for ordinary chat, recall, status,
  or memory events. A failed retry leaves either the previous complete index
  available or the runtime safely unavailable without changing primary memory.

### Verification

- The package-aware full local suite contains 1,317 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.65] - 2026-08-21

### Changed

- Cold semantic-index rebuilds now allow at most 256 embedding-provider calls
  by default. `HYPATIA_SEMANTIC_MEMORY_REBUILD_MAX_PROVIDER_CALLS` can set an
  explicit whole-number budget from 0 through the 20,000-entry index limit;
  zero permits only empty or fully cached rebuilds.
- Rebuilds resolve the complete provider-scoped cache view before any network
  work. Exact-budget misses are embedded in deterministic memory-record order,
  the cache is replaced only after the full build succeeds, and the live index
  is published only after the builder returns a complete replacement.

### Safety

- A rebuild whose cache misses exceed its budget fails before the first
  provider call, cache replacement, or runtime publication. Cache-read failure
  is attempted once and conservatively treats the whole rebuild as uncached.
- A valid foreign-provider cache snapshot is retained as an in-memory empty
  provider view, preserving isolation without repeatedly reading or decoding
  the same file for every active memory record.

### Verification

- The package-aware full local suite contains 1,312 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.64] - 2026-08-21

### Changed

- Embedding source text is capped at 1,000,000 characters across full rebuilds,
  incremental updates, direct semantic queries, and the Ollama provider.
- Outbound Ollama embedding JSON is capped at 8 MiB of exact compact UTF-8.
  A bounded writer streams serialization into the request body without first
  constructing a complete JSON string.

### Safety

- Full rebuilds validate every active source before cache lookup or provider
  work. Oversized semantic queries skip the provider and retain deterministic
  lexical fallback behavior.
- Oversized, recursive, or non-serializable request payloads fail before the
  network opener is called. Turkish and other Unicode input remains exact and
  is sent without ASCII escape expansion.

### Verification

- The package-aware full local suite contains 1,306 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.63] - 2026-08-21

### Changed

- Every `Embedding` is capped at 16,384 finite values. The derived live semantic
  index accepts at most 20,000 entries, 1,024 characters per memory ID, and
  4,000,000 aggregate vector values.
- Full index rebuilds reject excessive record populations before provider work
  and reject an excessive aggregate after the first dimension is established.
  Ollama responses reject oversized raw vectors before constructing a second
  normalized representation.
- Cosine ranking now uses overflow-safe norms and normalized summation, keeping
  scores finite and within `[-1.0, 1.0]` even for very large finite values.

### Safety

- Rejected incremental updates preserve the last complete live index and do not
  add the rejected entry to the optional cache. Primary memory writes remain
  successful and the existing safe semantic-update diagnostic is retained.
- Exact-limit inserts and replacements remain deterministic; failed new-entry
  attempts do not establish a dimension or partially change the live index.

### Verification

- The package-aware full local suite contains 1,302 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.62] - 2026-08-21

### Changed

- The optional schema-v1 semantic embedding cache now accepts at most 20,000
  ordered entries, 1,024 characters per provider key and memory ID, 1,000,000
  characters per source value, 16,384 values per embedding, 4,000,000 values
  across the snapshot, and 64 MiB of complete UTF-8 JSON.
- Reads consume at most one byte beyond the physical limit from the opened file
  descriptor before decoding. Atomic writes count exact UTF-8 bytes before
  publishing the deterministic provider-scoped snapshot.

### Safety

- Oversized collections, fields, and vectors are rejected before entry parsing,
  hashing, or serialization. Embedding dimensions must remain consistent within
  one provider cache, while a valid foreign-provider snapshot remains isolated
  without parsing its entries.
- Invalid candidates, oversized output, and failed replacements preserve the
  previous on-disk snapshot and in-memory entries and clean partial temporary
  files.

### Verification

- The package-aware full local suite contains 1,296 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.61] - 2026-08-21

### Changed

- The schema-v1 general memory snapshot now accepts at most 20,000 ordered
  records, 1,024 characters per memory ID, 1,000,000 characters per content
  value, and 64 MiB of complete UTF-8 JSON.
- Snapshot-wide metadata is capped at 100,000 top-level entries and 8 MiB of
  compact UTF-8 JSON. Tags are capped at 100,000 total values and 256
  characters per value.
- Reads consume at most one byte beyond the physical limit before decoding;
  atomic writes count exact UTF-8 bytes before publication.

### Safety

- Oversized collections and fields are rejected before record parsing or
  serialization, boolean schema values are not coerced to schema v1, and
  recursive or non-serializable metadata fails before a temporary write.
- Invalid save candidates, duplicate IDs, timezone-naive timestamps, failed
  replacements, and oversized output preserve the previous memory snapshot and
  clean partial temporary files.

### Verification

- The package-aware full local suite contains 1,287 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.60] - 2026-08-21

### Changed

- The schema-v1 session registry now accepts at most 20,000 ordered sessions,
  1,024 characters per session ID, and 64 MiB of complete UTF-8 JSON.
- Reads consume at most one byte beyond the physical limit from the opened file
  descriptor before decoding. Atomic writes count exact UTF-8 bytes in the
  temporary file before publication.

### Safety

- Oversized files are not decoded, excessive session collections and IDs are
  rejected before record parsing or serialization, and boolean schema values
  are not coerced to schema v1.
- Failed or oversized writes preserve the previous registry and clean partial
  temporary files. Session order and the default/active-session invariants
  remain unchanged.

### Verification

- The package-aware full local suite contains 1,277 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.59] - 2026-08-21

### Changed

- The explicit knowledge-relation schema-v1 snapshot now accepts at most 20,000
  ordered relations, 1,024 characters per endpoint document ID, and 64 MiB of
  complete UTF-8 JSON.
- Reads consume at most one byte beyond the physical limit from the opened file
  descriptor before decoding. Atomic writes count exact UTF-8 bytes in the
  temporary file before publication.

### Safety

- Oversized files are not decoded, excessive collections and endpoint IDs are
  rejected before record parsing or serialization, and boolean schema values
  are not coerced to schema v1.
- Failed or oversized writes preserve the previous relation snapshot and clean
  partial temporary files. Relation order, duplicate rejection, graph rollback,
  and schema v1 remain unchanged.

### Verification

- The package-aware full local suite contains 1,272 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.58] - 2026-08-21

### Changed

- The accepted-source content store now reads at most its 40,000,000-byte
  physical limit plus one detection byte directly from the opened descriptor
  before JSON decoding.
- Atomic writes stream JSON through an exact UTF-8 byte counter instead of
  constructing a second complete serialized snapshot in memory.

### Safety

- The existing schema-v1, 64-record, 32,000,000-content-byte, SHA-256, rollback,
  and atomic replacement contracts are unchanged.
- Oversized input is never decoded. Oversized or incomplete temporary output is
  not published, the previous snapshot is preserved, and partial files are
  removed.

### Verification

- The package-aware full local suite contains 1,267 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.57] - 2026-08-21

### Changed

- Research-run schema v6 now limits the complete UTF-8 JSON snapshot to 64 MiB
  and all nested collection entries to an aggregate 20,000 items.
- Reads consume at most one byte beyond the physical limit before JSON decoding.
  Writes count exact UTF-8 bytes while producing the temporary snapshot and
  stop before atomically replacing the current file.

### Safety

- Oversized input is rejected before decoding, and oversized in-memory
  collections are rejected before record parsing or serialization.
- Failed bounded writes preserve the previous snapshot and remove partial
  temporary files. Schema v1-v6 compatibility and successful atomic replacement
  remain unchanged.

### Verification

- The package-aware full local suite contains 1,265 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.56] - 2026-08-21

### Added

- A bounded read-only evidence integrity auditor compares persisted research
  evidence with the current accepted-content paragraphs by document, paragraph
  position, opaque identity, and exact-content SHA-256.
- Brain and the desktop expose an explicit `Evidence integrity` action that
  reports only recorded, matched, missing, and changed aggregate counts.

### Safety

- The audit is limited to 20,000 runs, evidence records, and indexed chunks.
  Ambiguous or oversized state returns a safe unavailable result.
- Audit requests use only already validated in-memory runs and chunks. They do
  not read or write persistence, access the network, invoke an LLM, mutate
  memory or knowledge, reveal content, paths, IDs, hashes, or repair records.

### Verification

- The package-aware full local suite contains 1,258 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 311 source files.

## [0.3.55] - 2026-08-21

### Changed

- Paragraphs indexed for an explicitly selected persistent research run now
  receive an opaque versioned identity derived from document ID, paragraph
  position, and exact-content SHA-256.
- Startup restoration opts into the same identity contract, so evidence
  recorded after this release can resolve the same accepted paragraph after a
  restart.

### Safety

- Temporary or run-free knowledge parsing retains its existing ephemeral
  identity behavior. Research-run and content-store schemas are unchanged.
- Existing evidence records are not rewritten, remapped, deleted, or migrated.
  A changed paragraph receives a different identity rather than silently
  inheriting an old evidence locator.

### Verification

- The package-aware full local suite contains 1,246 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 306 source files.

## [0.3.54] - 2026-08-21

### Added

- Bootstrap now captures an immutable accepted-content restoration status after
  startup validation, including only availability plus restored document and
  paragraph counts.
- Brain and the desktop expose that captured snapshot through an explicit
  read-only `Research content` action.

### Safety

- Status requests never read or write the content store, refetch a source,
  invoke an LLM, mutate memory, or change the knowledge index. An engine without
  a captured startup status reports a bounded unavailable state.
- The response excludes content, source metadata, paths, hashes, record IDs,
  and internal error details. Existing fail-closed startup validation remains
  unchanged.

### Verification

- The package-aware full local suite contains 1,243 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 306 source files.

## [0.3.53] - 2026-08-21

### Added

- Bootstrap now restores accepted research source content into the existing
  in-memory knowledge index after both the research-run and content snapshots
  have been fully validated.
- A dedicated `ResearchSourceContentRestorer` reconciles stable document ID,
  final URL, title, content type, and fetch time against accepted run
  provenance before constructing any knowledge document.

### Safety

- Orphaned content, conflicting run provenance, mismatched metadata,
  noncanonical text, or a document ID that does not match the stable URL-derived
  identity fails closed before indexing. Historical run provenance without a
  content record remains valid but cannot be restored.
- Restoration requires an empty startup index, performs no persistent writes or
  network requests, and is bounded to 20,000 paragraphs across the validated
  snapshot. An unexpected indexing failure clears every document added during
  that attempt before startup reports a controlled research error.
- Startup does not refetch, repair, delete, migrate, or quarantine either
  snapshot and does not invoke an LLM or change the research-run schema.

### Verification

- The package-aware full local suite contains 1,236 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 303 source files.

## [0.3.52] - 2026-08-21

### Changed

- A research source accepted into a selected collecting run now saves its exact
  extracted text to the separate schema-v1 content store after knowledge
  indexing and before research provenance is published.
- Bootstrap owns and registers the content store. Installed Windows and Linux
  desktop runtimes place it at `research/content.json` beneath the existing
  user-writable data root.

### Safety

- Content loading, validation, record construction, and atomic snapshot writing
  are part of the source-acceptance transaction. Failure removes the new
  unlinked knowledge document and publishes no accepted-source provenance.
- If provenance persistence fails after content is saved, Hypatia first
  restores the exact prior content collection and independently attempts to
  remove the new knowledge document. Controlled responses distinguish partial
  rollback failures without exposing source content or storage details.
- Direct source loads without a research run retain their existing in-memory
  behavior. Startup content restoration, refetch, crawling, LLM calls, and
  research-run schema changes remain outside this increment.

### Verification

- The package-aware full local suite contains 1,227 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 301 source files.

## [0.3.51] - 2026-08-21

### Added

- A separate `ResearchSourceContentRecord` contract binds one explicitly
  accepted source's exact extracted text to document ID, URL, title, content
  type, fetch/storage times, complete UTF-8 byte count, and SHA-256.
- A replaceable `ResearchSourceContentStore` boundary and strict schema-v1 JSON
  implementation can load or atomically replace the complete ordered content
  snapshot. Missing storage reads as an empty collection.

### Safety

- One record is limited to 4 MB of UTF-8 content. A snapshot is limited to 64
  unique document IDs/URLs, 32 MB of total content, and a 40 MB serialized file.
  Oversized files are rejected before JSON parsing.
- Loading revalidates exact fields, schema type/version, timezone-aware and
  ordered timestamps, byte count, and content fingerprint. Unknown fields,
  duplicate IDs/URLs, tampering, malformed Unicode, and stale fingerprints fail
  before a record is returned.
- Writes serialize and validate the complete snapshot before creating a
  same-directory temporary file, flush and fsync it, then atomically replace the
  destination. A failed replace preserves the prior snapshot and removes the
  temporary file.
- This release does not wire the store into Bootstrap, source acceptance, Brain,
  or desktop startup. It performs no automatic restore, refetch, indexing, or
  migration and does not change the research-run schema.

### Verification

- The package-aware full local suite contains 1,221 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 301 source files.

## [0.3.50] - 2026-08-21

### Changed

- The shared pinned HTTPS transport now carries the complete ordered set of
  public addresses from one DNS validation into the connection boundary.
- If an address fails during TCP or TLS setup, the transport closes that socket
  and tries the next already validated address exactly once. It never performs
  a new resolution while selecting a connection target.
- All address attempts and TLS handshakes share one decreasing connection-time
  budget. Exhausting that budget stops further attempts, and a successful TLS
  socket receives only the remaining timeout.

### Safety

- Every attempt retains hostname-based TLS SNI and certificate verification.
  Proxy tunnels remain rejected, address order remains deterministic, and
  complete failure returns one controlled message without address-specific
  transport details.
- The fallback applies to the existing explicit page loader and fixed Crossref
  metadata provider only; it adds no crawling, automatic acceptance, provider
  expansion, LLM call, or persistence.

### Verification

- Tests cover first-address TLS failure with second-address success, failed
  socket cleanup, ordered attempts, a decreasing shared deadline, deadline
  exhaustion before an untried address, and safe all-address failure.
- The package-aware full local suite contains 1,212 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 296 source files.
- Live bounded page acquisition and one-result Crossref metadata discovery both
  completed through the multi-address transport.

## [0.3.49] - 2026-08-21

### Security

- Address-pinned HTTPS connection and TLS handling now live in one shared
  research transport boundary instead of inside the explicit page fetcher.
- The fixed Crossref REST v1 discovery provider uses that boundary for its
  initial request and every same-origin redirect. It validates that the exact
  HTTPS origin and `/v1/works` path are retained, requires public-only DNS
  answers, and connects to an address from the same validation.
- Hostname-based TLS SNI, certificate verification, disabled system proxies,
  ten-second timeout, 500 KB JSON limit, and explicit-only discovery remain
  unchanged. No general search, crawling, or automatic acceptance is added.

### Verification

- Offline tests cover exact Crossref destination resolution, public-address
  propagation, private-address rejection, and wrong-origin rejection.
- The package-aware full local suite contains 1,209 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 296 source files.
- A live one-result Crossref metadata query completed through the shared pinned
  transport without fetching or accepting the returned paper.

## [0.3.48] - 2026-08-21

### Security

- The standard public-HTTPS research source fetcher now carries the exact
  validated public DNS address into its TCP connection instead of resolving
  the hostname again inside the transport. This closes the previously
  documented DNS-rebinding gap for explicit source acquisition.
- TLS still authenticates the normalized URL hostname with certificate and
  hostname verification enabled; the pinned IP address never replaces the
  HTTP host or TLS server name.
- Every redirect destination is normalized, resolved, and checked for public
  addresses again before its separate connection is pinned. Proxy tunnels
  remain rejected and the default source-fetch path still ignores system
  proxy configuration.

### Verification

- Tests prove exact address-to-socket propagation, hostname-based TLS,
  certificate-verification settings, proxy-tunnel rejection, and independent
  redirect resolution.
- The package-aware full local suite contains 1,206 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 295 source files.
- A live bounded acquisition of `https://example.com/` completed through the
  pinned default transport without changing the explicit-only research scope.

## [0.3.47] - 2026-08-21

### Added

- The desktop adds a separate `Verify export` action for one explicitly
  selected terminal research run and existing local `.md` file.
- Brain asks the research manager to re-render the current immutable run and
  compare its complete UTF-8 byte count and SHA-256 with the selected file.
  Both exact values and an honest `MATCH` or `DOES NOT MATCH` result are returned
  in a structured verification response.
- Verification hashes the selected file as a stream from one open descriptor
  and confirms that its identity, size, modification time, and change time stay
  stable through the read.

### Safety

- Verification accepts only an absolute `.md` path resolving to a regular file.
  Relative paths, wrong extensions, directories, missing files, collecting
  runs, mid-read changes, and unexpectedly large inputs are rejected.
- Unexpected local input is bounded to 64 MiB; a legitimate deterministic
  export larger than that remains verifiable up to its exact expected byte
  length. The complete accepted file is hashed rather than decoded or parsed.
- A mismatch is a successful read-only result, not an import or repair action.
  No file, research record, memory, graph, live index, or event is changed, and
  no provider, network, or LLM call occurs.

### Verification

- The package-aware full local suite contains 1,201 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 295 source files.

## [0.3.46] - 2026-08-21

### Added

- The desktop now offers a separate `Save export` action after a successful
  terminal-run Markdown preview. The user chooses the destination and confirms
  the exact path and full-content SHA-256 before the final request.
- The final Brain request carries the preview's run ID, timezone-aware snapshot
  update time, full-content fingerprint, and explicit destination path. The
  research manager re-renders persisted state under its lock and revalidates
  both snapshot identity values before any filesystem operation.
- Successful saves return a structured result containing the run ID, immutable
  snapshot time, absolute destination, byte count, and verified SHA-256.

### Safety

- Exports require an absolute `.md` destination inside an existing directory.
  Relative paths, other extensions, missing directories, collecting runs,
  malformed metadata, and stale preview identities are rejected before a
  destination is published.
- Complete UTF-8 bytes are written to a temporary file in the selected
  directory, flushed, and atomically linked to the final name. An existing
  destination is never replaced, including when it appears between selection
  and publication; temporary-file cleanup is attempted after success or
  failure.
- Saving performs no provider, network, LLM, memory, graph, live-index, event,
  or research-audit mutation. Controlled failures do not expose internal
  filesystem errors.

### Verification

- The package-aware full local suite contains 1,187 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 293 source files.

## [0.3.45] - 2026-08-21

### Added

- One explicitly selected terminal research run can be rendered as a
  deterministic, read-only Markdown export preview from its immutable persisted
  snapshot.
- The export includes run identity and lifecycle, accepted-source provenance,
  bounded evidence excerpts and user notes, complete assessment history with
  current/superseded labels, comparison notes, and safe failure records in
  persisted order.
- The desktop adds `Export preview` beside the existing terminal-status action.
  It requires only the selected run ID and passes no destination path.
- The Linux verification workflow now derives its archive name from package
  metadata so each release receives a correctly versioned build artifact.
- The preview carries the exact snapshot update time, a sanitized suggested
  filename, complete character count, omitted character count, and SHA-256 of
  the full deterministic Markdown content for a later revalidating save flow.

### Safety

- Collecting runs cannot be exported. The preview performs no file write,
  provider or network request, LLM call, live knowledge lookup, event
  publication, graph change, or conversation-memory mutation.
- Display is bounded to 24,000 source characters with an explicit omitted
  count. The SHA-256 still describes the complete content rather than the
  bounded display.
- Persisted remote excerpts and user-authored text are rendered as escaped
  block quotes so headings, raw HTML, image references, and Markdown control
  characters remain literal report data instead of active document structure.
  ASCII controls and directional-override characters are made visible rather
  than retained as hidden display instructions.
- Suggested filenames are reduced to a bounded basename and cannot carry a
  directory separator. No document is saved in this release.

### Verification

- The package-aware full local suite contains 1,174 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 291 source files.

## [0.3.44] - 2026-08-21

### Added

- The installed Linux desktop now has direct tests for its XDG data-directory
  contract: an absolute `XDG_DATA_HOME` resolves beneath `hypatia`, while an
  absent or invalid relative value falls back to `~/.local/share/hypatia`.
- `tools/build_desktop.sh --clean` creates a pinned PyInstaller onedir package
  at `dist/Hypatia/Hypatia` from the same desktop entry point used on Windows.
- `tools/smoke_desktop_linux.sh` starts the packaged Tkinter application under
  Xvfb with a temporary explicit data root and verifies local session-state
  initialization without leaving user data behind.
- A least-privilege GitHub Actions workflow runs the full suite, builds and
  smoke-tests the desktop on Ubuntu 24.04 x64, then publishes a bounded-retention
  Linux archive artifact. Third-party actions are pinned to exact commits.
- ADR 0003 records the Ubuntu 24.04 x64 package, XDG storage, manual-update,
  no-telemetry, no-bundled-credential, and supported-platform boundaries.

### Changed

- POSIX absolute-path validation now uses POSIX path semantics even when the
  platform behavior is exercised from a Windows test host. Windows data paths
  and the absolute `HYPATIA_DESKTOP_DATA_DIR` override remain unchanged.

### Verification

- The package-aware full local suite contains 1,162 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 287 source files.
- The Linux package build and packaged startup smoke check are verified by the
  Ubuntu workflow before release rather than inferred from Windows behavior.

## [0.3.43] - 2026-08-21

### Added

- A collecting research run can preview and separately append one
  user-authored comparison note for two to five explicitly ordered accepted
  sources.
- Each note cites exact persisted evidence IDs and exact current assessment
  IDs. Every selected source must be covered by both reference types, and every
  cited assessment's evidence must also be cited explicitly.
- The existing comparison preview is the read boundary after restart: it shows
  matching notes for the exact selected source order, bounded to 20 notes while
  reporting the complete count.
- Research-run schema v6 stores comparison notes append-only and loads v1-v5
  snapshots with an empty comparison-note collection until a later successful
  mutation rewrites the snapshot.

### Safety

- Preview performs no write. Confirmed recording revalidates the open run,
  accepted sources, evidence ownership, current assessments, assessment
  evidence, and complete per-source coverage before atomically replacing the
  research snapshot.
- Hypatia does not generate the note, choose references, score sources, produce
  a verdict, call an LLM or provider, fetch content, write conversation memory,
  or change knowledge and graph state through this flow.
- Existing notes remain immutable when a cited assessment is corrected later;
  the correction is appended separately and historical note references remain
  intact.

### Verification

- The package-aware full local suite contains 1,158 passing automated tests.

## [0.3.42] - 2026-08-20

### Added

- A read-only manual comparison preview now accepts an ordered selection of two
  to five unique sources already accepted into the same research run.
- Each comparison column shows persisted source provenance, only evidence the
  user explicitly selected for that source, and only current user-authored
  assessments. Superseded assessment text remains in the audit history but is
  not presented as current comparison material.
- The desktop adds a comma-separated `Comparison source IDs` field and an
  explicit `Compare sources` action. The preview remains available after a run
  reaches a terminal status.

### Security

- Comparison validates the exact run and every source ID before rendering. It
  rejects missing, duplicate, unaccepted, cross-run, or out-of-bounds source
  selections and preserves the caller's explicit order.
- The preview performs no network, discovery, fetch, LLM, memory, graph,
  knowledge-index, event-bus, or persistence operation. It assigns no verdict,
  trust score, or automatic evidence selection.
- Comparison rendering is bounded to the first 20 persisted evidence records
  and first 10 current assessments per selected source. It reports complete and
  displayed counts so large valid histories remain honest without generating
  an unbounded desktop response.

### Verification

- The package-aware full local suite contains 1,142 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 284 source files.

## [0.3.41] - 2026-08-20

### Added

- A new user-authored source assessment may explicitly supersede one earlier
  assessment from the same research run and accepted source. The earlier record
  remains intact and the new immutable record stores its exact predecessor ID.
- Assessment preview, confirmation, committed response, and read-only history
  now show the optional supersession link. History marks records as `current`
  or `superseded` without deleting or rewriting either record.
- The desktop adds an optional `Supersedes assessment ID` field to the existing
  preview-confirm-save flow.

### Security

- Preview and final recording independently reject missing, cross-source, or
  already superseded targets. A target must appear earlier in the same run and
  may have only one direct successor, preventing forks and cycles.
- Corrections remain user-authored, collecting-run-only, evidence-explicit,
  append-only, and atomically persisted. They invoke no network, provider, LLM,
  memory, graph, or event-bus side effect.
- Research-run schema v5 reads v1-v4 snapshots; v4 assessments receive a null
  supersession link and are rewritten only on a later successful atomic save.

### Verification

- The package-aware full local suite contains 1,129 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 281 source files.

## [0.3.40] - 2026-08-20

### Added

- A collecting research run can now persist an append-only, user-authored
  assessment for one accepted source. The record stores the source document
  ID, the exact evidence IDs explicitly entered by the user, bounded assessment
  text, a unique assessment ID, and its timezone-aware recording time.
- The desktop adds separate assessment-evidence and assessment-text fields plus
  `Preview & save assessment`. It displays the runtime preview and requests
  confirmation before sending a distinct record request.
- The accepted-source assessment view now includes the source's persisted
  authored-assessment history after restart.

### Security

- Preview performs no write. Final recording revalidates the exact run, accepted
  source, and every evidence ID; missing, cross-source, duplicate, or closed-run
  selections are rejected before persistence.
- The assessment is user-authored and evidence selection is explicit. Hypatia
  assigns no automatic trust, credibility, relevance, support, or quality score
  and invokes no source fetcher, discovery provider, LLM, memory, graph, or
  event-bus side effect.
- Research-run schema v4 reads v1-v3 snapshots with missing collections treated
  as empty and upgrades only on a later successful atomic save.

### Verification

- The package-aware full local suite contains 1,121 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 281 source files.

## [0.3.39] - 2026-08-20

### Added

- One accepted source can now be selected by exact run and document ID for a
  read-only manual-assessment preview. The preview displays persisted
  provenance and only evidence records explicitly selected by the user for
  that source.
- The desktop includes a separate source-document field and `Preview
  assessment` action. A successful attached-source load selects its returned
  document ID for this view without invoking the preview automatically.

### Security

- Assessment rejects unknown, unaccepted, or cross-run document IDs and never
  consults the live knowledge index, source fetcher, LLM, conversation memory,
  event bus, or graph.
- Missing evidence is reported honestly: no trust, credibility, relevance, or
  quality score is inferred. The read-only view remains available for terminal
  research runs and performs no persistence write.

### Verification

- The package-aware full local suite contains 1,103 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass across 278 source files.

## [0.3.38] - 2026-08-20

### Added

- A discovered source candidate now has a read-only acceptance preview that
  proves the exact run, discovery record, and persisted candidate URL before
  any source content is fetched.
- The desktop adds `Preview & load`: it displays the runtime decision, asks for
  explicit confirmation only when allowed, and then sends a separate acceptance
  request through the existing guarded public-HTTPS source loader.

### Security

- Final acceptance revalidates the candidate against current persisted run
  state. Unknown discoveries, unlisted or stale URLs, and closed runs are
  rejected before network access.
- Preview performs no network, indexing, LLM, graph, or conversation-memory
  operation. Existing source-audit failure rollback remains authoritative.

### Verification

- The package-aware full local suite contains 1,091 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in an isolated local tool
  environment.

## [0.3.37] - 2026-08-20

### Added

- The packaged process-environment runtime now enables an explicit Crossref
  REST v1 scholarly-metadata discovery provider by default. It can be disabled
  with `HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER=disabled`.
- The desktop can discover up to five candidates for the selected collecting
  run, display their title and DOI URL, and copy one explicitly selected URL
  into the separate source-load field.

### Security

- Crossref discovery is restricted to the fixed `api.crossref.org` HTTPS
  endpoint and same-origin redirects, does not inherit proxy settings, accepts
  only JSON, reads at most 500 KB, and uses a ten-second timeout.
- Discovery retrieves bibliographic metadata only. Selecting a candidate does
  not fetch, trust, accept, index, cite, or write it to conversation memory.
  A candidate from a different run cannot be copied through the desktop view.

### Verification

- The package-aware full local suite contains 1,079 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.36] - 2026-08-20

### Added

- A replaceable source-discovery provider boundary can return at most five
  ordered HTTPS metadata candidates for an explicit collecting research run.
- Every successful discovery is atomically stored with its query, provider
  identity, timestamp, ordered title/URL/snippet metadata, and a unique audit
  ID. Empty result sets remain auditable.
- Brain and the desktop controller expose a structured discovery request
  without accepting, fetching, indexing, or trusting candidate content.

### Changed

- Research-run JSON schema v3 persists discovery records while continuing to
  load v1 and v2 snapshots without eager migration.
- Closed or unknown research runs are rejected before the discovery provider
  is called. Controlled provider failures retain only a bounded safe failure
  reason, and failed snapshot writes do not publish candidate state.

### Verification

- The package-aware full local suite contains 1,064 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.35] - 2026-08-20

### Added

- Research runs now have explicit `collecting`, `completed`, `failed`, and
  `cancelled` lifecycle states. A completed run requires at least one accepted
  source and one evidence record; a failed run requires a failure record;
  cancellation may close an otherwise empty run honestly.
- The desktop uses a read-only preview followed by a separate confirmation for
  every terminal transition. The update revalidates current state before its
  atomic snapshot write.

### Changed

- Terminal research runs are immutable: they cannot accept further sources,
  evidence, or failure records, and they cannot transition to a different
  status. A source request for a closed run is rejected before network access.

### Verification

- The package-aware full local suite contains 1,047 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.34] - 2026-08-20

### Added

- A user can explicitly select an indexed paragraph from a source already
  attached to a research run and persist it as evidence with a bounded note,
  source/chunk locator, paragraph index, up-to-1,000-character excerpt,
  truncation marker, and SHA-256 fingerprint of the complete paragraph.
- The desktop exposes separate `Save evidence` and read-only `View evidence`
  actions. Evidence recording/listing remains inside the Brain boundary and
  does not call an LLM, write conversation memory, or infer a claim.
- Research-run JSON schema v2 persists evidence and loads v1 snapshots with an
  empty evidence collection, rewriting them as v2 only on the next successful
  save.

### Verification

- The package-aware full local suite contains 1,034 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.33] - 2026-08-20

### Added

- Persistent, versioned research runs now retain the user's original question,
  collecting status, accepted source provenance, safe failure records, and
  timezone-aware creation/update times without duplicating downloaded page
  content.
- The desktop can start a research run, list stored runs, and attach an
  explicitly entered HTTPS source to the selected run. These structured Brain
  actions remain user initiated and do not call an LLM or write conversation
  memory.
- Research-run snapshots use validated atomic JSON replacement under the
  desktop's user-owned local data directory. A failed audit write rolls back a
  newly indexed knowledge document so the two runtime views cannot silently
  diverge.

### Verification

- The package-aware full local suite contains 1,017 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.32] - 2026-08-20

### Added

- The first real internet-research acquisition slice: the desktop can load one
  explicitly entered public HTTPS page into the existing in-memory knowledge
  pipeline with its final URL, title, content type, fetch time, and stable
  source identity preserved.
- External source acquisition is provider-independent and bounded: credentials,
  non-HTTPS URLs, nonstandard ports, private/loopback/link-local DNS answers,
  unsafe redirects, unsupported content types, responses over 1 MiB, and
  unreadable encodings fail before indexing.
- Standard-library HTML extraction removes active and non-readable content and
  keeps readable block text. Plain-text and Markdown HTTPS sources are also
  accepted.

### Verification

- A live bounded fetch of `https://example.com/` returned its final source URL,
  page title, and readable text.
- The package-aware full local suite contains 990 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.31] - 2026-08-20

### Added

- The local desktop shell now offers user-controlled text size from 10 through
  20 points and a high-contrast toggle. These are presentation-only settings:
  they do not persist data, call an LLM, or alter session, memory, or knowledge
  state.

### Changed

- The default LLM system prompt now asks Hypatia for calm, warm, natural
  English responses, including when a user writes in Turkish.

### Verification

- The package-aware full local suite contains 966 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.30] - 2026-08-15

### Added

- The desktop entry point now uses user-writable persistence paths instead of
  an installed application directory: `%LOCALAPPDATA%\Hypatia` on Windows by
  default, with an absolute-only `HYPATIA_DESKTOP_DATA_DIR` override. The
  terminal developer entry point keeps its repository data-path behavior.
- The first Windows desktop packaging path is defined by ADR 0002: a pinned
  PyInstaller `6.21.0` dependency and `tools/build_desktop.ps1` produce an
  inspectable onedir package at `dist/Hypatia/Hypatia.exe`. Updates remain
  manual; the package does not self-update, migrate data, or bundle secrets.

### Verification

- The package-aware full local suite contains 963 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.
- The Windows build script produced `dist/Hypatia/Hypatia.exe` and its bundled
  Tcl/Tk runtime assets. A sandbox policy prevented an automated background GUI
  launch, so this release does not claim an executable-startup smoke test.

## [0.3.29] - 2026-08-15

### Added

- The desktop shell now provides `Load file` for one explicitly selected local
  Markdown (`.md`) or plain-text (`.txt`) source. The selected path reaches
  `KnowledgeEngine` only through a structured Brain request, avoiding command
  parsing of Windows paths. The runtime validates the source before indexing it
  and returns its title, source path, type, chunk count, and stable ID.
- Cancelling selection, an empty path, unsupported/missing/empty files, and an
  already loaded source return controlled outcomes. The load path does not call
  an LLM, write conversation memory, emit a conversation event, or maintain a
  desktop-side source store.

### Verification

- The package-aware full local suite contains 957 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass with the documented
  project virtual environment.

## [0.3.28] - 2026-08-15

### Added

- The desktop shell now provides `Search this session`, delegating only to the
  existing explicit selected-session conversation search. Empty session IDs and
  queries are rejected locally; successful or empty search responses remain
  read-only and do not change sessions, memory, or provider state.

### Verification

- The package-aware full local suite contains 949 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter session-search
  smoke test pass with the documented project virtual environment.

## [0.3.27] - 2026-08-15

### Added

- The desktop shell now exposes `Preview delete` for a selected session. It
  opens confirmation only when the existing structured runtime preview marks
  deletion allowed; blocked or failed previews cannot show confirmation or
  issue a delete request. A successful delete clears the selection and refreshes
  the session list from Brain.

### Verification

- The package-aware full local suite contains 947 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and real Tkinter allowed/blocked
  session-delete smoke tests pass with the documented project virtual environment.

## [0.3.26] - 2026-08-15

### Added

- The desktop shell now exposes `Preview rename` for the selected session and a
  user-entered replacement ID. It shows the existing transactional runtime
  preview, calls the revalidating rename command only after confirmation, then
  refreshes the session list from Brain after a successful rename. A declined
  or failed preview makes no session or memory change.

### Verification

- The package-aware full local suite contains 946 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter preview-and-
  confirm session-rename smoke test pass with the documented project virtual
  environment.

## [0.3.25] - 2026-08-15

### Added

- The desktop shell now exposes `Active links`, delegating only to the existing
  deterministic read-only local source-relation catalog. It reports active
  links and their persistence state without calling an LLM or changing source,
  graph, or conversation-memory state.

### Verification

- The package-aware full local suite contains 941 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter active-links
  smoke test pass with the documented project virtual environment.

## [0.3.24] - 2026-08-15

### Added

- The desktop shell now exposes a `Preview and remove` source-relation flow.
  It delegates first to the existing read-only removal preview, shows that
  exact preview for confirmation, and calls the existing revalidating removal
  command only after approval. Cancellation and a failed preview make no
  relation change.

### Verification

- The package-aware full local suite contains 940 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter preview-and-
  confirm relation-removal smoke test pass with the documented project virtual
  environment.

## [0.3.23] - 2026-08-15

### Added

- The desktop shell now exposes a `Preview and link` source-relation flow. It
  first delegates both entered source IDs to the existing read-only runtime
  preview, displays that exact preview for confirmation, and calls the existing
  revalidating apply command only after the user confirms. Cancellation and a
  failed preview make no relation change.

### Verification

- The package-aware full local suite contains 934 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter preview-and-
  confirm relation smoke test pass with the documented project virtual
  environment.

## [0.3.22] - 2026-08-15

### Added

- The desktop transcript now renders source records already returned on a
  knowledge response, in their existing order. Each visible citation keeps its
  title, local path, one-based paragraph, and chunk ID; the UI performs no
  additional lookup or citation construction.

### Verification

- The package-aware full local suite contains 928 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter citation-
  rendering smoke test pass with the documented project virtual environment.

## [0.3.21] - 2026-08-15

### Added

- The desktop shell now exposes `Ask sources`, an explicit user-initiated local
  RAG question action. It delegates to the established `ask knowledge` command,
  passes only the entered question, and preserves the runtime's controlled
  unavailable/failure result. It never augments ordinary chat or changes
  conversation memory.

### Verification

- The package-aware full local suite contains 926 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter unavailable-
  runtime `Ask sources` smoke test pass with the documented project virtual
  environment.

## [0.3.20] - 2026-08-15

### Added

- The desktop shell now provides explicit `Knowledge graph` and `Loaded
  sources` actions. They delegate to the existing bounded, cited graph and
  read-only local source-catalog commands; neither action calls an LLM nor
  changes conversation memory or local knowledge state.

### Verification

- The package-aware full local suite contains 924 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter knowledge-view
  smoke test pass with the documented project virtual environment.

## [0.3.19] - 2026-08-15

### Added

- The desktop shell now provides an explicit `Knowledge context` action for a
  user-entered query. It delegates to the existing bounded, cited local context
  command, rejects an empty query locally, and does not call an LLM or change
  conversation memory.

### Verification

- The package-aware full local suite contains 921 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter knowledge-
  context smoke test pass with the documented project virtual environment.

## [0.3.18] - 2026-08-15

### Added

- The desktop shell now has separate user-initiated lexical `Recall` and
  opt-in `Semantic recall` actions. They reject an empty query locally and
  delegate only the explicit existing Brain command; ordinary chat remains
  free of automatic retrieval or prompt augmentation.

### Verification

- The package-aware full local suite contains 919 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter recall-window
  smoke test pass with the documented project virtual environment.

## [0.3.17] - 2026-08-15

### Added

- The desktop shell now provides explicit, read-only actions for the selected
  session's details, five most recent conversations, and first/last activity.
  Each action delegates to the existing Brain command and rejects an empty
  session selection before any runtime call.

### Fixed

- The project virtual environment now uses the complete local Python 3.14
  installation, allowing the documented Tkinter desktop command to create a
  real window instead of failing to locate Tcl/Tk runtime files.

### Verification

- The package-aware full local suite contains 916 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a real Tkinter session-views
  smoke test pass with the documented project virtual environment.

## [0.3.16] - 2026-08-15

### Added

- The desktop shell now refreshes a read-only session overview, displaying the
  ordered session IDs, active-session marker, and conversation counts returned
  through the existing Brain boundary. Selecting a listed ID only fills the
  input; the existing explicit activation action still performs the change.
- `BrainResponse` now carries ordered `SessionSummary` values for existing
  session-list and session-overview responses, so presentation adapters do not
  need to parse formatted text or read session persistence directly.

### Verification

- The package-aware full local suite contains 912 passing automated tests.
- Black, Ruff, MyPy, whitespace validation, and a Windows Tkinter session-list
  smoke test pass locally.

## [0.3.15] - 2026-08-15

### Added

- The first local Tkinter desktop shell. It starts the existing Hypatia
  application lifecycle and delegates text chat, explicit session selection,
  and read-only semantic-runtime status to the already constructed `Brain`.
- A headless-tested desktop controller prevents empty input locally while
  preserving non-empty conversation text and without creating a second store,
  provider, or network client.

### Verification

- The package-aware full local suite contains 911 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass for the full repository.

## [0.3.14] - 2026-08-15

### Security

- The local Ollama embedding transport now reads at most 1 MiB before JSON
  parsing, rejecting oversized responses before they can consume unbounded
  process memory.

### Verification

- The package-aware full local suite contains 906 passing automated tests.

## [0.3.13] - 2026-08-15

### Security

- The local Ollama embedding transport now rejects HTTP redirects, keeping an
  opted-in semantic request at its validated local endpoint.

### Verification

- The package-aware full local suite contains 905 passing automated tests.

## [0.3.12] - 2026-08-15

### Fixed

- Knowledge loading now rejects a source that is already loaded before parsing
  or indexing it, so a failed duplicate load cannot leave orphaned chunks in
  the search index.

### Verification

- A versioned v2 hybrid semantic-ranking corpus adds Turkish and English query
  cases with explicit expected ordering and relevance rationales. The runtime
  ranking algorithm remains unchanged.
- The package-aware full local suite contains 904 passing automated tests.

## [0.3.11] - 2026-08-15

### Added

- A read-only `semantic recall status` command that makes the opt-in local
  semantic-memory runtime observable without embedding a query or changing
  conversation memory. It reports disabled, initializing, or ready state; a
  ready runtime also reports its index size, embedding dimension, and safe
  latest incremental-update diagnostic.

### Verification

- The package-aware full local suite contains 902 passing automated tests.

## [0.3.10] - 2026-08-15

### Fixed

- Requests that begin with an English or Turkish greeting but contain a
  substantive question now use the normal conversation path instead of being
  reduced to a standalone greeting response.
- Standalone `merhaba` and `selam` greetings now receive a deterministic
  Turkish response.

### Verification

- The package-aware full local suite contains 897 passing automated tests.
- The local Ollama runtime was exercised with a Turkish substantive greeting;
  it reached the LLM conversation path and returned a successful response.

## [0.3.9] - 2026-08-15

### Added

- A validated `HYPATIA_LLM_TIMEOUT_SECONDS` setting for the optional
  OpenAI-compatible chat runtime. It accepts only positive finite seconds.
- A 120-second default for explicitly loopback chat endpoints such as local
  Ollama, while non-local endpoints retain their established 30-second default.

### Safety

- Invalid timeout settings fail during configuration rather than silently
  altering network behavior. The configured value is non-secret and never
  changes the keyless-loopback or remote HTTPS/API-key policy.

### Verification

- The package-aware full local suite contains 893 passing automated tests.

## [0.3.8] - 2026-08-15

### Added

- Keyless chat-runtime activation for explicitly loopback OpenAI-compatible
  endpoints such as local Ollama. In this mode Hypatia deliberately omits the
  `Authorization` header instead of sending an empty bearer token.

### Safety

- Non-local endpoints continue to require an API key and HTTPS. Plain HTTP is
  still restricted to `localhost`, `127.0.0.1`, and `::1`; redirects remain
  rejected for chat-completion requests.

### Verification

- The package-aware full local suite contains 885 passing automated tests.

## [0.3.7] - 2026-08-15

### Added

- A read-only `list knowledge relations` catalog for active explicit local
  document links. Each entry exposes loaded source and target document IDs,
  the `related_to` type, and whether the link is persisted or in-memory only.

### Safety

- The catalog reports only relations active in the current graph. It does not
  infer endpoints, materialize an unloaded persisted relation, change graph or
  relation-store state, write conversation memory, or call an LLM.

### Verification

- The package-aware full local suite contains 880 passing automated tests.

## [0.3.6] - 2026-08-15

### Added

- A read-only `preview remove knowledge relation <source_document_id> --
  <target_document_id>` command for an existing explicit local relation.
- An explicit `remove knowledge relation <source_document_id> --
  <target_document_id>` command. It removes the derived graph edge and, when
  present, its separate persisted relation record.

### Safety

- Removal requires an existing relation, rejects a repeated request, and makes
  no conversation-memory or LLM call. If the relation snapshot cannot be
  written, the removed graph edge is restored before the failure is returned.

### Verification

- The package-aware full local suite contains 875 passing automated tests.

## [0.3.5] - 2026-08-15

### Added

- A separate, versioned, atomically replaced local JSON store for explicitly
  applied `related_to` document relations. The Bootstrap runtime wires the
  store beside its other local data.
- Restart-safe relation restoration: a persisted link is restored to the
  derived graph only after both of its stable local source identities have been
  loaded again.
- Transactional relation application: if the local relation file cannot be
  written, the just-added in-memory graph edge is removed again.

### Safety

- The store accepts only distinct `related_to` document IDs, rejects duplicate
  records and unsupported schemas, and never writes conversation memory or
  sends a request to an LLM.

### Verification

- The package-aware full local suite contains 869 passing automated tests.

## [0.3.4] - 2026-08-15

### Added

- Stable document IDs for files loaded through the local Knowledge Foundation.
  The ID is deterministically derived from the resolved local source path, so
  reopening the same source retains its identity even when its content changes.
  Distinct local source paths retain distinct identities.

### Verification

- The package-aware full local suite contains 861 passing automated tests.

## [0.3.3] - 2026-08-15

### Added

- An explicit `apply knowledge relation <source_document_id> --
  <target_document_id>` command. It freshly validates the two documents, then
  adds one `related_to` edge to the derived, in-memory local graph. Duplicate,
  self, unknown, and non-user-selectable relations are rejected without a
  partial change.
- `knowledge graph <query>` now shows an explicitly applied `related_to` edge
  when either selected document endpoint is relevant to the query.

### Safety

- Applying a relation changes only the current in-memory graph. It does not
  write JSON memory, create a conversation-memory record, call an LLM, or
  persist across restart.

### Verification

- The package-aware full local suite contains 858 passing automated tests.

## [0.3.2] - 2026-08-15

### Added

- An explicit, read-only `preview knowledge relation <source_document_id> --
  <target_document_id>` command. It validates two distinct catalogued local
  documents for the first user-selectable `related_to` relationship, but does
  not alter graph state, JSON memory, or conversation memory.

### Verification

- The package-aware full local suite contains 853 passing automated tests.

## [0.3.1] - 2026-08-15

### Added

- An explicit `list knowledge` catalog for loaded local sources. It returns
  stable document IDs, titles, source paths, document types, and chunk counts
  in load order, without LLM use or conversation-memory mutation.

### Verification

- The package-aware full local suite contains 846 passing automated tests.

## [0.3.0] - 2026-08-15

### Added

- An explicit `knowledge graph <query>` view for locally loaded sources. It
  exposes deterministic document-to-paragraph `contains` relationships with
  visible source citations, without LLM use or conversation-memory mutation.
- A derived, in-memory local knowledge-graph foundation. It keeps document and
  paragraph nodes plus `contains` and `precedes` edges separate from the JSON
  memory schema, and indexes each source atomically.

### Verification

- The package-aware full local suite contains 840 passing automated tests.

## [0.2.10] - 2026-08-15

### Fixed

- Reconciled the runtime version, current verification baseline, and explicit
  local-RAG boundary across the project status and architecture-audit documents.

### Verification

- The package-aware full local suite contains 830 passing automated tests.

## [0.2.9] - 2026-08-15

### Fixed

- Bound each source chunk in an `ask knowledge` LLM prompt to 600 characters,
  matching the visible context limit and preventing an oversized local prompt.

### Verification

- The package-aware full local suite contains 830 passing automated tests.

## [0.2.8] - 2026-08-15

### Added

- Explicit `ask knowledge <query>` local RAG answers. The LLM receives only up
  to three cited local chunks and the answer retains those citations in its
  response model; normal conversation is never automatically augmented.

### Verification

- The package-aware full local suite contains 828 passing automated tests.

## [0.2.7] - 2026-08-15

### Added

- An explicit `knowledge context <query>` command that composes up to three
  local knowledge chunks with visible ordered source citations. It does not
  alter normal search or conversation behavior and does not create a memory
  record.
- Bounded context display: each rendered chunk is limited to 600 characters,
  while the complete selected result remains available in the response model.

### Verification

- The package-aware full local suite contains 825 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.6] - 2026-08-15

### Added

- Stable local source citations for knowledge-search results. Every response
  now carries a matching ordered citation with document ID, title, local source,
  paragraph index, and chunk ID, without changing the existing search text or
  raw result list.
- Parser propagation of source-document identity into indexed chunks, forming
  the explainability boundary required by later local RAG work.

### Verification

- The package-aware full local suite contains 822 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.5] - 2026-08-15

### Added

- An optional, model-scoped local embedding cache for semantic memory. When
  `HYPATIA_SEMANTIC_MEMORY_PERSIST_EMBEDDINGS=true`, unchanged local memory can
  be indexed after restart without calling Ollama again.
- Atomic cache replacement, source-content SHA-256 invalidation, strict cache
  validation, and lifecycle updates for added, changed, expired, and deleted
  memory records. The cache is separate from the primary memory schema and is
  never required for a successful primary-memory operation.

### Verification

- The package-aware full local suite contains 819 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.4] - 2026-08-15

### Added

- Connected reciprocal-rank fusion to the explicit `semantic recall <query>`
  path when both current-session semantic and lexical candidates are present.
  The response labels this mode `hybrid` and clearly identifies its displayed
  values as rank scores rather than cosine-similarity scores.
- Preserved semantic-only results, deterministic lexical fallback, and
  current-session isolation when hybrid evidence is unavailable.

### Verification

- The package-aware full local suite contains 812 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.3] - 2026-08-15

### Security

- Disabled automatic HTTP redirect following for authenticated LLM completion
  requests, so an `Authorization` bearer token cannot be forwarded to a
  redirect target.

### Verification

- The package-aware full local suite contains 811 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.2] - 2026-08-15

### Security

- Added a validated endpoint policy for optional authenticated LLM runtimes:
  remote providers must use HTTPS, while plain HTTP is limited to explicit
  loopback endpoints (`localhost`, `127.0.0.1`, and `::1`).
- Rejected malformed endpoint URLs and URLs containing embedded credentials
  before the provider factory can receive an API key.
- Added an initial responsible-disclosure and runtime-security baseline in the
  repository security documentation.

### Verification

- The package-aware full local suite contains 810 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.1] - 2026-08-15

### Added

- Local JSON persistence for structured memory and session registry snapshots,
  including atomic writes and explicit failure handling.
- Session creation, activation, overview, details, activity, recent-history,
  conversation search, rename preview/commit, delete preview/commit, and
  guarded transactional deletion.
- Deterministic cognitive orchestration for knowledge search, planning,
  explicit recall, session commands, and optional LLM conversations.
- Learned-memory candidate extraction, append-only correction history,
  bounded context composition, keyword selection, deterministic ranking, and
  configurable ranked top-k selection.
- OpenAI-compatible chat-completions transport with an optional system prompt
  and bounded same-session conversation history.
- A dependency-free semantic retrieval core: validated immutable embeddings,
  an embedding-provider boundary, and a derived in-memory cosine-similarity
  index with deterministic ordering and a fresh-index builder for active
  memory records.
- An explicit stdlib-based Ollama `/api/embed` adapter with strict single-vector
  response validation, opt-in Bootstrap activation, and atomic replacement of
  the last successful derived index. After startup, lifecycle events keep the
  derived index current without allowing embedding failures to disrupt primary
  memory writes.
- A validated configurable local embedding-transport timeout with a 120-second
  default for cold local-model startup.
- A bounded `semantic recall <query>` path that exposes similarity scores only
  for current-session conversation records and falls back to deterministic
  lexical recall when semantic retrieval is unavailable or empty.
- A pure reciprocal-rank fusion evaluator with a versioned hybrid-ranking
  fixture corpus; it is evaluation-only and does not alter runtime ordering.

### Changed

- Restored a complete MyPy quality gate for both `src` and `tests` by making
  package-base discovery explicit and aligning test doubles with their runtime
  contracts.
- Made the full unittest command package-aware so nested test directories are
  included without shadowing source packages.

### Verification

- The package-aware full local suite contains 806 passing automated tests.
- Black, Ruff, MyPy, and whitespace validation pass in the local development
  environment.

## [0.2.0] - 2026-08-03

### Added

- Knowledge Foundation pipeline from document loading to search.
- `.txt` and `.md` document loading.
- Paragraph parsing into ordered chunks.
- In-memory chunk indexing and case-insensitive text search.
- KnowledgeEngine orchestration for loading, indexing, searching, and clearing.

### Tests

- Added 37 Knowledge Foundation tests.
- Expanded the full suite to 68 passing unit tests.
- Verified Black, Ruff, MyPy, unittest, and whitespace checks.

## [0.1.7] - 2026-08-03

### Changed

- Standardized project formatting and static analysis configuration.
- Improved logger output format.
- Standardized core exception types.
- Updated README and project status documentation.

### Tests

- Expanded the core test suite to 31 passing unit tests.
- Verified Black, Ruff, MyPy, unittest, and whitespace checks.
