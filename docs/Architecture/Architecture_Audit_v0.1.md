# Hypatia Architecture Audit v0.1

**Audit date:** 2026-08-15
**Last verified:** 2026-08-21
**Authority:** Current repository source, tests, and runtime configuration take
precedence over vision and roadmap documents.

## Purpose

This audit separates the executable Hypatia runtime from the long-term AI
Operating System vision. It is a baseline for small, testable implementation
sprints; it does not declare vision-only modules complete.

## Delivery Terminology

Hypatia uses three different labels that must not be compared as one version
sequence:

- **Runtime releases** (`v0.3.73` in the current release candidate) are the
  executable package and GitHub release line. They are the source-backed
  implementation baseline.
- **Historical sprint labels** (including **Sprint 4.16.50**) identify bounded
  engineering increments. Sprint 4.16.50 is complete and is already in the
  ancestry of the current runtime; it is not a newer runtime release waiting
  to be merged.
- **Vision-roadmap versions** under `docs/Roadmap/` describe long-term product
  goals. They are not a statement that their named capabilities are currently
  executable.

For current implementation state, use this audit, `PROJECT_STATUS.md`, the
changelog, the active source tree, and its tests—in that order of increasing
specificity for a claimed behavior.

## Executable Baseline

Hypatia is a Python 3.14+ local-first runtime. Its active source packages are:

| Area | Implemented responsibility |
| --- | --- |
| `core` | Bootstrap, configuration, logging, dependency container, exceptions |
| `brain` and `cognition` | Request routing and deterministic orchestration |
| `memory` | Immutable records, JSON snapshots, TTL, learned-memory extraction and selection |
| `session` | Persistent session registry and targeted session operations |
| `knowledge` | Local `.txt`/`.md` loading, source catalog, chunks, lexical search, cited prompt context, structural graph |
| `research` | Explicit bounded HTTPS acquisition and persistent auditable research-run snapshots |
| `llm` | Optional OpenAI-compatible chat-completions provider and history assembly |
| `planner`, `response`, `eventbus` | Deterministic task planning, response composition, lifecycle events |
| `desktop` | Local Tkinter adapter for text chat, session views/selection, explicit recall/context, selected `.md`/`.txt` loading, source graph/catalog, and guarded mutations |

The current request flow is:

```text
User request
  -> Brain
  -> CognitiveEngine
  -> session / memory / knowledge / planner / optional LLM
  -> ResponseComposer
  -> Brain response
```

The `desktop` package is deliberately a presentation adapter. Its controller
passes non-empty user text to `Brain`, maps a refreshable session overview to
the existing `session overview` command, maps explicit selection to `use
session`, maps selected-session details/recent/activity to their existing
read-only commands, and maps user-entered lexical/semantic recall plus status
to their existing commands. It additionally maps an explicit knowledge-context
or knowledge-graph query to bounded cited local commands without invoking an
LLM, exposes the existing read-only local source catalog, and maps an explicit
local-RAG question to `ask knowledge`. The latter retains the runtime's bounded
cited-source and unavailable/failure behavior. The desktop does not augment
ordinary chat. It visibly renders existing knowledge-response citations in
their response order without constructing or looking up new records. Its ordered
`SessionSummary` response data avoids parsing human-formatted output or reading
persistence directly. It owns neither persistent state nor a provider client;
the UI window does not add a browser, web server, provider client, or autonomous
network channel. Explicit provider-backed actions share one daemon request
worker; Tkinter polls results and alone updates widgets. Every command button is
disabled during that single flight, duplicate keyboard submission is rejected,
and close discards late presentation results. The status line reports elapsed
seconds without a fabricated completion percentage. An explicit cancellation
request discards the eventual completion but retains the single-flight boundary
until active timeout-bounded I/O returns; it does not terminate the worker or
provider transport. Crossref discovery and explicit HTTPS source loading carry
a thread-safe cancellation signal through Brain and check it after network
return and before audit, knowledge-index, or persistence mutation. Other
provider paths remain presentation-only cancellation. The worker delegates to
the same controller and Brain boundaries and owns no duplicate state.
Its explicit research-source action delegates one user-entered HTTPS URL to the
Brain-owned bounded fetcher and never runs implicitly. The default fetcher
tries only the ordered public addresses from its own validation, once each and
within one decreasing connection-time budget, while retaining hostname-based
TLS certificate checks; redirects repeat that boundary.
It can create/list a persistent research run and pass a selected run ID with
the source request. Bootstrap—not the UI—owns the atomic run and content stores.
The run snapshot records only question/status, source provenance, safe failures,
and timestamps; exact accepted page text is stored separately. Bootstrap
restores only records whose stable identity and source metadata exactly match
accepted run provenance. Initial accepted-source indexing and restoration use
the same content-bound paragraph identities, and Bootstrap captures only a
bounded aggregate restoration status for the explicit desktop view.
The separately requested evidence integrity audit compares persisted evidence
from the already loaded run snapshot with current in-memory paragraphs and
returns aggregate matched, missing, and changed counts. It performs no store,
network, LLM, memory, knowledge, or repair operation.
An explicit evidence action resolves one currently indexed chunk by ID and
accepts it only when its document is already attached to the selected run. The
v2 snapshot retains a bounded excerpt, full-chunk SHA-256 fingerprint, source
and paragraph locator, user note, and timestamp. A read-only action renders
that record after restart without an LLM or live knowledge lookup; no evidence
is selected or interpreted automatically.
Research lifecycle mutation also remains explicit. The desktop requests a
read-only transition preview and confirms only an allowed `completed`, `failed`,
or `cancelled` outcome; the update revalidates and atomically persists it.
Completion requires source plus evidence, while failure requires a recorded
failure. Every terminal run is immutable, and a closed-run source request is
rejected before the fetcher is called.
When launched as the desktop application, Bootstrap receives user-writable
memory, session, relation, research-run, and accepted-content paths beneath
`%LOCALAPPDATA%\Hypatia` on Windows or
`${XDG_DATA_HOME:-$HOME/.local/share}/hypatia` on Linux. Only absolute XDG and
explicit override paths are honored, and the application never writes beside
an installed executable. The terminal developer entry point remains unchanged.

The desktop also exposes the existing source-relation preview-and-apply contract
without weakening it: a user enters two source IDs, receives the current
read-only runtime preview, and must explicitly confirm before the desktop sends
the separate revalidating apply command. It does not retain a pending relation
locally, infer IDs, or apply a relation after a failed or declined preview.

The matching desktop relation-removal flow follows the same boundary: it asks
the runtime for a current removal preview and sends the separate revalidating
removal command only after an explicit confirmation. The desktop retains no
pending removal and cannot remove a relation after a declined or failed preview.

The desktop exposes the existing `list knowledge relations` command as its
read-only active-link catalog. It preserves the runtime's deterministic order
and persistence status without loading sources or changing graph, memory, or
provider state.

The desktop maps session rename to the existing transactional preview-and-rename
commands. It retains no rename plan, requires an explicit confirmation after
the runtime preview, and refreshes the session view from Brain only after a
successful result.

Persistent state is stored locally as validated JSON snapshots through
`JsonFileMemoryStore`, `JsonFileSessionStore`,
`JsonFileKnowledgeRelationStore`, `JsonFileResearchRunStore`, and
`JsonFileResearchSourceContentStore`. Snapshot writes are atomic. Accepted
research content is read through an opened-descriptor 40,000,000-byte bound
before JSON decoding and written through an exact UTF-8 byte counter without a
second complete serialized copy. It is saved after knowledge indexing and
before run provenance;
failure restores the prior content collection and removes the new unlinked
knowledge document where possible. Startup validates both snapshots before
reconstructing at most 20,000 paragraphs in the empty knowledge index. Orphans,
identity/metadata mismatches, conflicting provenance, or partial indexing fail
closed without changing either snapshot. The knowledge index remains in memory
and uses case-insensitive lexical matching.
Research-run schema v6 loads v1-v5 snapshots with absent evidence, discovery,
assessment, or comparison-note collections represented as empty and v4
assessments represented with no supersession link, rewriting a legacy snapshot
only on a subsequent successful mutation. Its complete UTF-8 file is capped at
64 MiB before JSON decoding or atomic publication, and all nested list entries
share one aggregate 20,000-item parsing and serialization budget. The
source-discovery boundary keeps
ordered candidate metadata auditable without accepting or fetching content.
The process-environment runtime provides a bounded Crossref REST v1 adapter
whose fixed endpoint and redirects share the public-address-pinned,
hostname-verified TLS transport used by explicit page acquisition, while the
desktop keeps candidate selection separate from source loading. Candidate
acceptance now uses a read-only run/discovery/URL-bound preview and a separately
confirmed request that revalidates before entering the existing guarded loader.
Accepted-source assessment is also read-only: an exact run/document binding
returns persisted provenance, explicitly recorded evidence, and authored
assessment history without a network, live-index, LLM, memory, graph, or
persistence side effect. A separate preview-confirm write boundary requires the
user to provide assessment text and exact evidence IDs, then revalidates the
open run, accepted source, and same-source evidence before an atomic append.
An optional predecessor ID creates a backward-only, same-source supersession
link. The original stays immutable; missing targets, cross-source targets,
forked successors, cycles, and stale-preview writes are rejected.
The ordered manual comparison is also the read boundary for append-only authored
comparison notes. A collecting run accepts a note only after an exact no-write
preview and separate confirmation. Evidence and current assessment IDs must
cover every selected source, every assessment's evidence must be cited, and all
references are revalidated before atomic persistence. Matching notes remain
readable after restart and are bounded to 20 displayed records with a complete
count; no text, reference, score, verdict, or provider result is generated.
One terminal research run also has a deterministic Markdown export preview.
The manager renders only the immutable persisted snapshot and returns a bounded
display plus the exact update time, safe filename, complete length, omitted
count, and SHA-256 of the full content. Remote excerpts and authored text are
escaped as literal block quotes. This read boundary performs no file, network,
provider, LLM, memory, graph, live-index, or event-bus operation; collecting
runs are rejected. A separate confirmed save carries the preview identity and
explicit destination through Brain, re-renders under the manager lock, and
atomically publishes complete UTF-8 bytes only when the absolute `.md` path
does not already exist. It changes no research, memory, graph, or event state.
An independent read boundary verifies one selected existing `.md` file against
the terminal run's current deterministic bytes. It streams a stable regular
descriptor, rechecks descriptor/path identity and metadata, and returns both
byte counts, both SHA-256 values, and an exact match flag. It never parses,
imports, repairs, or writes the selected file; unexpected input is bounded to
64 MiB unless the authentic current export itself is larger.

The optional OpenAI-compatible chat runtime supports keyless activation only
for explicit loopback endpoints (`localhost`, `127.0.0.1`, or `::1`), including
local Ollama. It omits the authorization header in that mode; non-local
endpoints continue to require an API key and HTTPS.

Chat requests use a validated, non-secret timeout setting. An explicit
`HYPATIA_LLM_TIMEOUT_SECONDS` override must be a positive finite number;
otherwise loopback endpoints receive 120 seconds while non-local endpoints
retain a 30-second default.

Standalone English and Turkish greetings remain deterministic. A substantive
request that begins with a greeting is classified as a normal conversation,
so it reaches the configured LLM runtime rather than losing the user's actual
question to the greeting shortcut.

## Memory State

Implemented memory capabilities:

- Immutable `MemoryRecord` values with metadata, tags, timestamps, and optional
  expiry.
- Atomic JSON persistence and expiry-aware reads.
- Learned-memory candidate extraction behind an optional LLM boundary.
- Append-only learned-memory corrections, latest-value resolution, bounded
  context, keyword selection, and stable ranked keyword top-k selection.
- A dependency-free semantic retrieval core: immutable validated embeddings, an
  embedding-provider boundary, and a derived in-memory cosine-similarity index
  keyed by existing memory IDs. Embeddings are capped at 16,384 values, and a
  live index is capped at 20,000 entries, 1,024 characters per memory ID, and
  4,000,000 aggregate values. A builder preflights a fresh index from the
  current active memory-record snapshot without changing persistence.
- An explicit stdlib-based Ollama `/api/embed` adapter with strict single-vector
  response validation and redirect rejection, keeping opted-in requests at the
  validated local endpoint. Semantic source text is capped at 1,000,000
  characters; outbound compact JSON is capped at 8 MiB of exact UTF-8 before
  network access, and responses are read at most 1 MiB before JSON parsing. An
  opt-in Bootstrap runtime owner attempts a complete index at startup. Failure
  keeps primary Bootstrap available and registers an attached unavailable
  runtime; success publishes only the complete replacement and then follows
  memory lifecycle events with best-effort incremental updates. An exact
  `semantic recall retry` command can deliberately retry the same bounded build.
- A bounded `semantic recall <query>` request path. It is session-filtered and
  uses reciprocal-rank fusion when both semantic and lexical candidates exist.
  Semantic-only responses retain cosine-similarity scores; unavailable or empty
  semantic retrieval uses deterministic lexical fallback.
- A read-only `semantic recall status` diagnostic. It exposes the optional
  disabled, initializing, unavailable, or ready runtime state; when ready its
  index size and embedding dimension; and separate safe full-rebuild and
  incremental-update diagnostics without generating an embedding, querying
  memory, or changing persisted state.
- Versioned hybrid-ranking fixture corpora at
  `tests/fixtures/semantic_memory_hybrid_v1.json` and
  `tests/fixtures/semantic_memory_hybrid_v2.json`. Together they verify
  retained single-source candidates, duplicated-evidence promotion,
  deterministic ties, result limits, Turkish and English query expectations,
  and a maintained relevance rationale for every retained candidate.
- An opt-in, model-scoped local embedding cache that is atomically replaced
  after a successful rebuild. It verifies a SHA-256 source-content fingerprint
  before reuse and does not alter primary memory persistence. Its schema-v1
  snapshot is bounded by physical UTF-8 size, entry and field counts, and
  per-vector and aggregate-vector limits while retaining provider isolation.
- Source attribution carried from loaded documents through paragraph chunks to
  ordered knowledge-search citations. This is a local explainability boundary,
  not an automatic RAG or prompt-augmentation feature.
- An explicit bounded `knowledge context <query>` retrieval flow. It selects at
  most three cited local chunks, limits display length, and does not mutate
  conversation memory or automatically augment an LLM prompt.
- An explicit `ask knowledge <query>` local-RAG flow. With an enabled LLM, it
  sends only up to three cited local chunks and the user question, with each
  source chunk bounded to 600 characters. The user question is separated from
  excerpts, every excerpt is labelled untrusted, and a code-owned per-request
  system instruction denies retrieved text instruction authority. It preserves
  citations on the answer, uses no conversation history or tool capability,
  and does not mutate conversation memory. This prompt-level boundary is not a
  complete prompt-injection firewall.
- A derived, in-memory local knowledge graph built from loaded documents and
  paragraph chunks. It uses typed `contains` and `precedes` edges, validates a
  whole document graph before changing state, and remains separate from the
  JSON memory schema. `knowledge graph <query>` exposes a bounded, cited,
  document-to-paragraph structural view without calling an LLM or mutating
  conversation memory.
- An explicit `list knowledge` source catalog. It presents stable local
  document IDs with title, source path, type, and chunk count in load order so
  a later user-controlled relationship command can identify documents without
  guessing by title. File-loaded IDs are deterministically derived from the
  resolved local source path, allowing the same local source to be identified
  after a restart even when its content changes.
- An explicit `preview knowledge relation <source_document_id> --
  <target_document_id>` request. It accepts only two distinct catalogued
  documents and the first user-selectable relationship type, `related_to`; it
  creates a typed pending-change response without changing graph state, JSON
  memory, LLM context, or conversation memory.
- An explicit `apply knowledge relation <source_document_id> --
  <target_document_id>` command. It revalidates two distinct catalogue entries,
  then atomically adds one user-selected `related_to` edge to the derived
  in-memory graph. The graph view exposes the relation when either endpoint is
  selected. Duplicate, self, unknown, and derived relation requests fail before
  mutating the graph; the command neither writes primary conversation memory
  nor calls an LLM.
- A distinct, versioned `relations.json` store for explicitly applied document
  relations. It atomically replaces complete snapshots and validates every
  record before use. It accepts at most 20,000 ordered relations, 1,024
  characters per endpoint ID, and 64 MiB of exact UTF-8 JSON; oversized reads
  stop before decoding and bounded temporary output precedes publication. On a
  storage failure the in-memory edge is rolled back.
  On restart, a stored relation is restored only after both file-derived stable
  source IDs have been loaded again; it is never guessed from a source title or
  content.
- An explicit two-stage relationship-removal flow. `preview remove knowledge
  relation <source_document_id> -- <target_document_id>` is read-only, while
  `remove knowledge relation <source_document_id> -- <target_document_id>`
  removes an existing graph edge and any persisted record. If the replacement
  relation snapshot fails to save, the engine restores the graph edge before
  returning a failure.
- A read-only `list knowledge relations` catalog. It exposes only active graph
  relations in deterministic application order, together with loaded source and
  target IDs plus the persistence status. The command does not materialize a
  persisted relation whose sources are not loaded and does not mutate any state.

Not implemented:

- Embedding persistence enabled by default.
- Automatic semantic augmentation of ordinary messages or generic Brain search.
- Cross-document semantic relation extraction, automatic web discovery, or
  automatic citations in ordinary model prompts.

## Quality Baseline

The current local verification baseline is:

- package-aware `python -m unittest`: 1,362 tests passed. Explicit `tests.*`
  module names ensure nested test directories are included without shadowing
  source packages.
- `python -m black --check src tests`: passed.
- `python -m ruff check src tests`: passed.
- `python -m mypy src tests`: passed with no issues in 315 files.
- `git diff --check`: passed.

These checks verify the current local worktree; they do not create a release,
tag, pull request, or GitHub deployment.

The Ubuntu 24.04 x64 workflow separately creates the pinned PyInstaller Linux
onedir package, launches it under Xvfb with a temporary absolute data root, and
verifies local session-state initialization. This is the Linux executable
boundary; other distributions, CPU architectures, installers, and signing are
not implied by that result.

The v0.3.68 opt-in semantic runtime was also verified on 21 August 2026 against
the local Ollama service using `embeddinggemma:latest`: Bootstrap published the
primary container before the cold provider call completed, the background
worker built one 768-dimensional record, and an ephemeral instance returned it
through the named semantic-recall path. Temporary memory/session files were
used, so this verification did not change project data.

The published v0.3.9 local chat runtime was also exercised on 15 August 2026
against `llama3.2:latest`. An ephemeral Bootstrap instance completed a Turkish
greeting through Hypatia's OpenAI-compatible local chat path, using temporary
memory/session files and leaving project data unchanged.

## Architecture Risks and Boundaries

1. Several architecture documents describe desired modules as if they were
   current capabilities. This audit and `PROJECT_STATUS.md` are the current
   implementation boundary.
2. JSON memory records must remain readable during a semantic-memory rollout.
   An initial semantic index must be derived and rebuildable, rather than adding
   opaque vectors to the existing snapshot schema.
3. Local-first is a product constraint. No default network embedding provider or
   secret-bearing configuration should be introduced by the first semantic
   memory increment.
4. Existing deterministic keyword selection must remain an available fallback
   until semantic retrieval has independently verified relevance, ties, bounds,
   and failure behavior.
5. Semantic and desktop provider work now have separate single-flight daemon
   boundaries. An active provider transport is not forcefully terminated;
   existing request deadlines remain the execution bound, while desktop close
   discards its eventual presentation result.

## Completed Increment: Responsive Desktop Provider Requests

- Chat, explicit semantic recall, cited knowledge questions, research discovery,
  and approved source acquisition use one daemon worker rather than the Tkinter
  event thread.
- Tkinter polls the bounded completion queue and is the only thread that updates
  widgets. All command buttons are disabled during the request, and keyboard
  submission cannot create a second queued or concurrent Brain operation.
- Closing stops new work and discards late results without touching destroyed
  widgets. Provider calls remain bounded by their existing timeouts instead of
  being unsafely force-killed.
- Expected validation messages are retained; all other worker or presentation
  exceptions become a generic desktop failure. Composer text typed after a
  request began is not erased when the earlier response arrives.

## Completed Increment: Background Semantic Incremental Maintenance

- Full rebuilds and incremental events share one daemon worker, preventing
  concurrent provider/cache streams and keeping primary-memory EventBus
  publication independent of embedding latency.
- The queue retains at most 20,000 distinct pending IDs. Repeated operations
  move the latest event to deterministic queue order; one in-flight generation
  is discarded when a later update or delete supersedes it.
- A requested full rebuild waits behind the active provider call, discards
  redundant queued events, and rebuilds from current primary memory.
- Status exposes `updating`; semantic queries use lexical fallback while the
  worker is busy. Failed IDs retain a safe diagnostic until specifically
  reconciled or cleared by a complete rebuild.
- Shutdown clears queued generations and prevents an in-flight incremental
  embedding from reaching the live index.

## Completed Increment: Background Semantic Initialization

Optional semantic rebuilding no longer holds the primary startup path.

- Bootstrap attaches and registers the optional runtime, publishes its primary
  dependency container, and then schedules one daemon rebuild. Conversation,
  sessions, lexical recall, and primary memory are immediately available.
- Startup and explicit retry share a single-flight boundary. Duplicate retry
  requests report the active job instead of creating a second provider stream.
- Status distinguishes initializing, refreshing, ready, unavailable, disabled,
  and stopped. Semantic queries use lexical fallback throughout a rebuild,
  including when an older complete index is retained.
- A memory event during rebuilding marks the snapshot dirty and permits one
  coalesced retry from a fresh snapshot. A second dirty attempt records only the
  generic safe failure and publishes no stale or partial index.
- Shutdown rejects new work and signals cancellation. The builder checks that
  signal after bounded provider calls and before derived-cache replacement;
  runtime publication is suppressed after shutdown.

## Completed Increment: Shared Semantic Rebuild Deadline

Every full semantic rebuild now has one aggregate monotonic time boundary.

- The default shared deadline is 120 seconds. The process environment accepts a
  positive finite override no greater than 3,600 seconds.
- The deadline begins before record, source, and provider-scoped cache
  preflight. Cache work that consumes the budget prevents all provider work and
  cache replacement.
- Every cache miss receives only the time remaining in the shared rebuild. The
  local Ollama transport selects the shorter of that value and its configured
  per-request timeout; a sequential call cannot renew the original allowance.
- Expiry before or after a provider call rejects the incomplete build before
  cache replacement or runtime publication. An initial build remains safely
  unavailable; a later rebuild or explicit retry preserves the last complete
  index and generic safe diagnostic.
- Exact-deadline completion remains deterministic, while invalid, non-finite,
  non-positive, and greater-than-3,600-second configuration is rejected before
  provider construction.

## Completed Increment: Degraded Semantic Startup and Explicit Retry

An optional semantic rebuild can now fail without making the primary
application unavailable.

- Bootstrap publishes its normal dependency container, registers and attaches
  the optional runtime, and schedules the refresh boundary in the background.
  Conversation, sessions, lexical recall, and primary memory remain available
  before the rebuild succeeds or fails.
- The runtime separately records a safe full-rebuild diagnostic. Failed initial
  builds retain no partial index; failed later builds retain the last complete
  index. A complete successful rebuild clears both rebuild and incremental
  diagnostics before publication.
- `semantic recall status` distinguishes disabled, initializing, refreshing,
  unavailable, ready, and stopped states. It reports separate safe rebuild and
  incremental-update fields without exposing provider, transport, cache,
  source, or budget details.
- Only the exact `semantic recall retry` request schedules another complete
  bounded rebuild. It is not triggered by ordinary chat, recall, or status;
  success publishes a complete replacement and failure leaves primary memory
  plus the last complete index unchanged.

## Completed Increment: Cold-Start Semantic Rebuild Budget

Optional semantic startup rebuilding now has a complete cache preflight and an
explicit provider-call boundary.

- The default budget is 256 calls. The process environment accepts an ASCII
  whole number from 0 through the 20,000-entry live-index limit; zero permits
  only empty or fully cached rebuilds.
- Every provider-scoped cache lookup is resolved before network work. If total
  misses exceed the budget, rebuilding stops before the first provider call,
  cache replacement, or semantic-runtime publication.
- At the exact budget, missing embeddings are generated in deterministic
  memory-record order. Cache replacement is attempted only after every provider
  result succeeds, and the runtime publishes only a complete returned index;
  cache-save failure preserves the prior cache without discarding that index.
- A cache-read failure is attempted once and conservatively treats the whole
  rebuild as uncached. A valid foreign-provider snapshot is retained as a
  cached isolated empty view, avoiding repeated file reads and decoding.

## Completed Increment: Semantic Request Bounds

Every semantic embedding path now shares a source-text boundary, and the local
Ollama transport has an exact outbound request-body boundary.

- Source text is capped at 1,000,000 characters without trimming or otherwise
  changing exact Turkish, English, whitespace, or Unicode content.
- Full rebuilds preflight every active source before cache lookup or provider
  work. Incremental updates validate before provider/cache changes, and an
  oversized direct query skips embedding and uses deterministic lexical
  fallback.
- Compact Ollama JSON is capped at 8 MiB of exact UTF-8. A bounded writer stops
  during serialization without constructing a complete intermediate JSON
  string, and Unicode is not expanded into ASCII escape sequences.
- Oversized, recursive, and non-serializable payloads fail before the request
  opener is called. The existing redirect rejection, timeout, and 1 MiB
  response boundary remain unchanged.

## Completed Increment: Live Semantic Index Bounds

Provider output and the derived in-memory semantic index now share explicit
resource boundaries without making primary-memory writes depend on embeddings.

- Every embedding is capped at 16,384 finite values. Ollama rejects a larger
  raw response vector before constructing its normalized tuple.
- Live indexes are capped at 20,000 entries, 1,024 characters per memory ID,
  and 4,000,000 aggregate vector values. Replacements do not consume additional
  capacity.
- Full rebuilds reject excessive record counts before provider requests and
  reject an excessive aggregate as soon as the first dimension is known,
  before cache replacement or runtime publication.
- Incremental limit failures retain the last working index and do not add the
  rejected record to the optional cache. Primary memory stays committed and
  exposes only the safe existing semantic-update diagnostic.
- Overflow-safe norms and normalized summation keep cosine scores finite and
  clamped to the mathematical range for every accepted finite vector while
  preserving deterministic score and memory-ID ordering.

## Completed Increment: Semantic Embedding Cache Bounds

The optional provider-scoped schema-v1 cache now has explicit resource and
save-time integrity limits without changing primary memory persistence.

- Complete UTF-8 snapshots are capped at 64 MiB; reads consume at most one
  detection byte beyond that limit from the opened descriptor before decoding.
- Snapshots are capped at 20,000 ordered entries, 1,024-character provider keys
  and memory IDs, 1,000,000-character source values, 16,384 values per vector,
  and 4,000,000 aggregate vector values.
- Collection, field, and vector limits are enforced before parsing, hashing, or
  serialization. One provider's entries must retain a consistent dimension;
  valid foreign-provider snapshots remain isolated without entry parsing.
- Atomic writes count exact UTF-8 bytes. Invalid, oversized, or failed updates
  preserve both the prior file and current in-memory cache and clean temporary
  files while deterministic entry ordering remains unchanged.

## Completed Increment: General Memory Snapshot Bounds

The schema-v1 general memory snapshot now has explicit resource and save-time
integrity limits without changing its persisted shape.

- Complete UTF-8 snapshots are capped at 64 MiB; reads consume at most one
  detection byte beyond that limit from the opened descriptor before decoding.
- Snapshots are capped at 20,000 ordered records, 1,024 characters per memory
  ID, and 1,000,000 characters per content value.
- Snapshot-wide metadata is capped at 100,000 top-level entries and 8 MiB of
  compact UTF-8 JSON without retaining a serialized copy. Tags are capped at
  100,000 total values and 256 characters per value.
- Record counts and ID/content bounds are enforced before parsing or
  serialization. Recursive, non-serializable, or excessive metadata and tags
  fail before a temporary write.
- Atomic writes count exact UTF-8 bytes, including the final newline. Invalid,
  oversized, or failed writes preserve the prior snapshot and clean temporary
  files; order, duplicate-ID rejection, and timezone-aware dates remain intact.

## Completed Increment: Session Registry Snapshot Bounds

The schema-v1 session registry now has explicit resource limits without
changing its persisted shape or transaction semantics.

- Complete UTF-8 snapshots are capped at 64 MiB; reads consume at most one
  detection byte beyond that limit from the opened descriptor before decoding.
- Registries are capped at 20,000 ordered sessions and each active or record
  session ID is capped at 1,024 characters.
- Collection and ID limits are enforced before record parsing or serialization,
  and boolean values cannot be coerced into schema version 1.
- Atomic writes count exact UTF-8 bytes, including the final newline. Oversized
  or failed writes preserve the prior snapshot and clean temporary files.
- Default-session presence, active-session membership, case-sensitive IDs,
  duplicate rejection, timezone-aware timestamps, and order remain unchanged.

## Completed Increment: Semantic Retrieval Core

This increment was deliberately limited to a reusable retrieval core, followed
by one named semantic-recall path. It does **not** augment ordinary requests or
generic knowledge search.

### Scope

- Define an embedding-provider boundary that can be implemented by a local
  model later and faked in tests now.
- Define immutable embedding values with finite-number and dimension checks.
- Implement a derived in-memory semantic index keyed by existing memory IDs,
  then keep it current after successful memory lifecycle events without making
  primary-memory writes dependent on embedding availability.
- Implement cosine-similarity query with deterministic tie-breaking and an
  explicit non-negative result limit.
- Add focused unit tests for validation, upsert/replacement, removal, empty
  index, zero-vector behavior, ordering, ties, and limits.

### Explicitly Deferred

- Downloading or bundling an embedding model.
- Remote embedding APIs, API keys, or new dependencies.
- JSON schema migration or embedding persistence enabled by default.
- Prompt augmentation, automatic retrieval, and generic knowledge-search
  changes.
- Reranking beyond reciprocal-rank fusion, generic RAG expansion, and
  cross-document semantic relation extraction.

### Acceptance Criteria

The increment is complete: the core is deterministic, has no external service
dependency, retains no stale entry after replacement/removal, rejects invalid
vectors clearly, and leaves existing runtime behavior unchanged. The full
package-aware test suite, Black, Ruff, MyPy, and diff checks pass.

## Follow-on Sequence

1. A read-only `semantic recall status` command now monitors the bounded named
   semantic-recall path. The versioned v2 hybrid-ranking corpus supplements the
   original rank-only fixtures with Turkish and English queries, maintained
   expected relevance ordering, and a rationale for each retained candidate.
   Treat these fixtures as the acceptance baseline before considering reranking.
