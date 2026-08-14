# Hypatia Status

## Runtime Version

`v0.2.3 (Genesis)`

This is the version reported by the runtime and package metadata. It captures
the semantic-memory, ranked learned-memory, LLM transport-safety, and
quality-gate work merged after `v0.2.0`.

## Current Source State

The current source tree provides a deterministic, local-first cognitive core
with optional OpenAI-compatible LLM conversation support.

### Implemented

- Application bootstrap, configuration, logging, and dependency injection.
- EventBus-backed lifecycle events.
- Session registry with local JSON persistence, active-session selection,
  targeted read-only views, rename, preview, and guarded deletion.
- Persistent structured memory with atomic JSON writes, TTL handling, explicit
  recall, and transactional mutation ordering.
- Learned-memory extraction, append-only correction history, bounded context,
  keyword selection, deterministic ranked selection, and optional top-k
  selection configured through the process environment.
- A derived, in-memory semantic retrieval core with validated embeddings, an
  embedding-provider boundary, deterministic cosine ranking, and a fresh-index
  builder for current active records. An explicit Ollama `/api/embed` adapter
  is available without third-party dependencies. Opt-in Bootstrap wiring builds
  and registers a replacement index at startup. After a successful startup it
  follows memory lifecycle events with best-effort incremental updates; an
  embedding failure never reverses a completed primary-memory write. Vectors
  are not persisted and semantic results are used only by the explicit
  `semantic recall <query>` request path with deterministic lexical fallback.
  The runtime retains a safe diagnostic when its most recent incremental index
  update failed, without exposing provider-specific error details.
- A pure reciprocal-rank fusion evaluator with versioned hybrid-ranking
  fixtures. It is not connected to semantic recall and does not change runtime
  ordering.
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

- Persisted vectors, hybrid ranking in the request flow, automatic semantic
  augmentation of ordinary messages, and a knowledge graph.
- Web research, citation collection, or a RAG pipeline.
- Agent execution, tool gateway, browser/OS control, voice, vision, robotics,
  and smart-home integrations.
- Encryption at rest, cloud synchronization, multi-process storage locking,
  and persistence schema migration.

## Verification

Last verified in the local development environment:

- 811 automated tests pass through package-aware discovery.
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

## Next Milestone

Review the bounded release scope, assign a release version, and publish
reconciled release notes. Before hybrid ranking enters the request path, grow
the fixture corpus and review relevance expectations; RAG remains a separate
milestone.
