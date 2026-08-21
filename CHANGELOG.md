# Changelog

All notable project changes are recorded here.

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
