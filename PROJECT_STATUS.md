# Hypatia Status

## Runtime Version

`v0.3.63 (Genesis)`

This is the version reported by the runtime and package metadata. It captures
the semantic-memory, ranked learned-memory, LLM transport-safety, explicit
local-RAG, local knowledge-graph, and quality-gate work merged after `v0.2.0`.

## Delivery Terminology

The repository has three intentionally separate naming systems:

- **Runtime release `v0.3.63`** is the current executable package and GitHub
  release line.
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
- An initial local Tkinter desktop shell for text conversation, explicit
  session selection, a refreshable read-only session overview, and
  semantic-runtime status. It also provides selected-session details, recent
  conversations, and activity through explicit read-only actions. It is a thin
  adapter over the existing Brain and does not create a second store, provider,
  or network channel.
- Local desktop text-size controls bounded from 10 through 20 points and an
  explicit high-contrast palette. They alter only presentation and do not
  persist a preference, invoke a provider, or change session, memory, or
  knowledge state. A full assistive-technology audit remains planned.
- Explicit desktop actions for normal lexical recall and opt-in semantic recall.
  Neither action augments ordinary chat, persists a recall result, or issues a
  provider request unless the user deliberately selects it.
- An explicit desktop `Knowledge context` action for bounded, cited local
  document context. It does not call an LLM or change conversation memory.
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
- Research-run schema v6 remains backward compatible with v1-v5 snapshots.
  Legacy runs load with absent evidence, discovery, or assessment collections
  represented as empty, v4 assessments load with no supersession link, and
  v1-v5 runs load with no comparison notes.
  They are rewritten only after a later successful mutation; no eager or
  partial migration occurs.
- One terminal run can be explicitly previewed as deterministic Markdown using
  only its immutable persisted audit snapshot. The bounded view includes source
  provenance, evidence, authored assessment history, comparison notes, and safe
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
  reopened, retargeted, or receive further source, evidence, assessment, or failure
  mutations. Closed-run source requests stop before network access.
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
  and optional cache. An explicit Ollama `/api/embed` adapter
  is available without third-party dependencies, rejects HTTP redirects, and
  reads at most 1 MiB before parsing an embedding response. Opt-in Bootstrap wiring builds
  and registers a replacement index at startup. After a successful startup it
  follows memory lifecycle events with best-effort incremental updates; an
  embedding failure never reverses a completed primary-memory write. Semantic
  results are used only by the explicit `semantic recall <query>` request path
  with deterministic lexical fallback.
  The runtime retains a safe diagnostic when its most recent incremental index
  update failed, without exposing provider-specific error details.
- Deterministic reciprocal-rank fusion for explicit semantic recall when both
  current-session semantic and lexical candidates exist. Hybrid responses use
  rank scores; semantic-only responses retain cosine-similarity scores.
- A read-only `semantic recall status` diagnostic. It reports the optional
  runtime's state, index size and dimension when ready, and only the safe
  latest incremental-update diagnostic; it does not generate an embedding or
  change conversation memory.
- An optional model-scoped local semantic-embedding cache. It is disabled by
  default, validates a source-content fingerprint before reuse, updates with
  memory lifecycle events, and remains separate from the primary memory schema.
  Its provider-scoped schema-v1 snapshot is capped at 64 MiB, 20,000 entries,
  1,024-character provider and memory IDs, 1,000,000-character source values,
  16,384-dimensional vectors, and 4,000,000 aggregate vector values. Reads and
  writes enforce exact byte and collection bounds while preserving the previous
  cache after an invalid or failed update.
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
  endpoints such as local Ollama receive 120 seconds while non-local endpoints
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

### Intentionally Not Implemented

- Automatic semantic augmentation of ordinary messages.
- General web discovery, automatic or unattended candidate acceptance,
  multi-source research
  planning/synthesis,
  contradiction detection, evidence ranking, automatic RAG augmentation, or
  cross-document semantic relation extraction.
- Agent execution, tool gateway, browser/OS control, voice, vision, robotics,
  and smart-home integrations.
- Encryption at rest, cloud synchronization, multi-process storage locking,
  and persistence schema migration.

## Verification

Last verified in the local development environment:

- 1,302 automated tests pass through package-aware discovery.
- Black and Ruff pass for `src` and `tests`.
- MyPy passes for `src` and `tests`.
- Whitespace validation (`git diff --check`) passes.

These checks describe the local working tree and do not create a GitHub
release, tag, commit, or pull-request approval.

### Live local semantic-runtime check

On 15 August 2026, the opt-in runtime was exercised against the local Ollama
service with the `embeddinggemma` model. Hypatia's own adapter received a
valid 768-dimensional embedding, then an ephemeral Bootstrap instance indexed
a newly created conversation and returned it through `semantic recall` as a
semantic result. This check used temporary memory/session files and did not
alter the project's persisted data.

### Live local chat-runtime check

On 15 August 2026, the published v0.3.9 chat runtime was exercised against
the local Ollama service with `llama3.2:latest`. An ephemeral Bootstrap
instance completed a Turkish greeting request through Hypatia's
OpenAI-compatible local chat path. Temporary memory/session files were used,
so this check did not alter the project's persisted data.

## Next Milestone

Define semantic source-text and outbound Ollama embedding-request payload
bounds. Persisted records and vector responses are bounded, but direct semantic
queries still need a shared character/UTF-8 request boundary before JSON body
construction and transport, without changing exact-text embedding semantics or
the deterministic lexical fallback.
