# Hypatia Architecture Audit v0.1

**Audit date:** 2026-08-14
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
| `knowledge` | Local `.txt`/`.md` loading, chunks, in-memory lexical search |
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
- A bounded `semantic recall <query>` request path. It is session-filtered,
  returns scored semantic matches only for conversation records, and uses
  deterministic lexical recall when semantic retrieval is unavailable or empty.
- A pure reciprocal-rank fusion evaluator and fixture corpus at
  `tests/fixtures/semantic_memory_hybrid_v1.json`. It verifies retained
  single-source candidates, duplicated-evidence promotion, deterministic ties,
  and limits without changing any runtime path.

Not implemented:

- Persisted vectors.
- Automatic semantic augmentation of ordinary messages or generic Brain search.
- Knowledge graph, RAG, web retrieval, or citations.

## Quality Baseline

The current local verification baseline is:

- `python -m unittest discover -s tests -t .`: 810 tests passed. The top-level
  package setting ensures nested test directories are included without
  shadowing source packages.
- `python -m black --check src tests`: passed.
- `python -m ruff check src tests`: passed.
- `python -m mypy src tests`: passed with no issues in 211 files.

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
- JSON schema migration or persisted vectors.
- Prompt augmentation, automatic retrieval, and generic knowledge-search
  changes.
- Hybrid lexical-plus-semantic ranking, reranking, RAG, and knowledge graph
  work.

### Acceptance Criteria

The increment is complete: the core is deterministic, has no external service
dependency, retains no stale entry after replacement/removal, rejects invalid
vectors clearly, and leaves existing runtime behavior unchanged. The full
package-aware test suite, Black, Ruff, MyPy, and diff checks pass.

## Follow-on Sequence

1. Expand hybrid-ranking fixtures with reviewed relevance expectations before
   deciding whether to add hybrid ranking to the named semantic-recall path.
