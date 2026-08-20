# Changelog

All notable project changes are recorded here.

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
