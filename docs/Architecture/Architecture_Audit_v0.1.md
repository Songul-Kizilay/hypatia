# Hypatia Architecture Audit v0.1

**Audit date:** 2026-08-15
**Authority:** Current repository source, tests, and runtime configuration take
precedence over vision and roadmap documents.

## Purpose

This audit separates the executable Hypatia runtime from the long-term AI
Operating System vision. It is a baseline for small, testable implementation
sprints; it does not declare vision-only modules complete.

## Delivery Terminology

Hypatia uses three different labels that must not be compared as one version
sequence:

- **Runtime releases** (`v0.3.14` today) are the executable package and GitHub
  release line. They are the source-backed implementation baseline.
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
| `llm` | Optional OpenAI-compatible chat-completions provider and history assembly |
| `planner`, `response`, `eventbus` | Deterministic task planning, response composition, lifecycle events |

The current request flow is:

```text
User request
  -> Brain
  -> CognitiveEngine
  -> session / memory / knowledge / planner / optional LLM
  -> ResponseComposer
  -> Brain response
```

Persistent state is stored locally as validated JSON snapshots through
`JsonFileMemoryStore` and `JsonFileSessionStore`. Snapshot writes are atomic.
The knowledge index is in memory and uses case-insensitive lexical matching.

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
  keyed by existing memory IDs. A builder produces a fresh index from the
  current active memory-record snapshot without changing persistence.
- An explicit stdlib-based Ollama `/api/embed` adapter with strict single-vector
  response validation and redirect rejection, keeping opted-in requests at the
  validated local endpoint. It reads at most 1 MiB before JSON parsing. An
  opt-in Bootstrap runtime owner rebuilds and registers
  the index at startup, swapping only after a complete successful build, then
  follows memory lifecycle events with best-effort incremental updates.
- A bounded `semantic recall <query>` request path. It is session-filtered and
  uses reciprocal-rank fusion when both semantic and lexical candidates exist.
  Semantic-only responses retain cosine-similarity scores; unavailable or empty
  semantic retrieval uses deterministic lexical fallback.
- A read-only `semantic recall status` diagnostic. It exposes the optional
  runtime state, and when ready its index size, embedding dimension, and safe
  last incremental-update diagnostic without generating an embedding, querying
  memory, or changing persisted state.
- Versioned hybrid-ranking fixture corpora at
  `tests/fixtures/semantic_memory_hybrid_v1.json` and
  `tests/fixtures/semantic_memory_hybrid_v2.json`. Together they verify
  retained single-source candidates, duplicated-evidence promotion,
  deterministic ties, result limits, Turkish and English query expectations,
  and a maintained relevance rationale for every retained candidate.
- An opt-in, model-scoped local embedding cache that is atomically replaced
  after a successful rebuild. It verifies a SHA-256 source-content fingerprint
  before reuse and does not alter primary memory persistence.
- Source attribution carried from loaded documents through paragraph chunks to
  ordered knowledge-search citations. This is a local explainability boundary,
  not an automatic RAG or prompt-augmentation feature.
- An explicit bounded `knowledge context <query>` retrieval flow. It selects at
  most three cited local chunks, limits display length, and does not mutate
  conversation memory or automatically augment an LLM prompt.
- An explicit `ask knowledge <query>` local-RAG flow. With an enabled LLM, it
  sends only up to three cited local chunks and the user question, with each
  source chunk bounded to 600 characters. It preserves citations on the answer,
  uses no conversation history, and does not mutate conversation memory.
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
  record before use. On a storage failure the in-memory edge is rolled back.
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
- Cross-document semantic relation extraction, web retrieval, or automatic
  citations in ordinary model prompts.

## Quality Baseline

The current local verification baseline is:

- `python -m unittest discover -s tests -t .`: 906 tests passed. The top-level
  package setting ensures nested test directories are included without
  shadowing source packages.
- `python -m black --check src tests`: passed.
- `python -m ruff check src tests`: passed.
- `python -m mypy src tests`: passed with no issues in 232 files.

These checks verify the current local worktree; they do not create a release,
tag, pull request, or GitHub deployment.

The opt-in semantic runtime was also verified on 15 August 2026 against the
local Ollama service using `embeddinggemma`: Hypatia's adapter received a
768-dimensional vector, and an ephemeral Bootstrap instance indexed a new
conversation and returned it through the named semantic-recall path. Temporary
memory/session files were used, so this verification did not change project
data.

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
