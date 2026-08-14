# Hypatia Architecture Audit v0.1

**Audit date:** 2026-08-15
**Authority:** Current repository source, tests, and runtime configuration take
precedence over vision and roadmap documents.

## Purpose

This audit separates the executable Hypatia runtime from the long-term AI
Operating System vision. It is a baseline for small, testable implementation
sprints; it does not declare vision-only modules complete.

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
  response validation. An opt-in Bootstrap runtime owner rebuilds and registers
  the index at startup, swapping only after a complete successful build, then
  follows memory lifecycle events with best-effort incremental updates.
- A bounded `semantic recall <query>` request path. It is session-filtered and
  uses reciprocal-rank fusion when both semantic and lexical candidates exist.
  Semantic-only responses retain cosine-similarity scores; unavailable or empty
  semantic retrieval uses deterministic lexical fallback.
- A versioned hybrid-ranking fixture corpus at
  `tests/fixtures/semantic_memory_hybrid_v1.json`. It verifies retained
  single-source candidates, duplicated-evidence promotion, deterministic ties,
  and limits used by the explicit semantic-recall path.
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
  guessing by title.
- An explicit `preview knowledge relation <source_document_id> --
  <target_document_id>` request. It accepts only two distinct catalogued
  documents and the first user-selectable relationship type, `related_to`; it
  creates a typed pending-change response without changing graph state, JSON
  memory, LLM context, or conversation memory.

Not implemented:

- Embedding persistence enabled by default.
- Automatic semantic augmentation of ordinary messages or generic Brain search.
- Knowledge-graph persistence, applied cross-document relations,
  cross-document semantic relation extraction, web retrieval, or automatic
  citations in ordinary model prompts.

## Quality Baseline

The current local verification baseline is:

- `python -m unittest discover -s tests -t .`: 853 tests passed. The top-level
  package setting ensures nested test directories are included without
  shadowing source packages.
- `python -m black --check src tests`: passed.
- `python -m ruff check src tests`: passed.
- `python -m mypy src tests`: passed with no issues in 223 files.

These checks verify the current local worktree; they do not create a release,
tag, pull request, or GitHub deployment.

The opt-in semantic runtime was also verified on 15 August 2026 against the
local Ollama service using `embeddinggemma`: Hypatia's adapter received a
768-dimensional vector, and an ephemeral Bootstrap instance indexed a new
conversation and returned it through the named semantic-recall path. Temporary
memory/session files were used, so this verification did not change project
data.

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

1. Expand hybrid-ranking fixtures with reviewed relevance expectations and
   monitor the bounded named semantic-recall path before considering reranking.
