# Hypatia Status

## Runtime Version

`v0.3.7 (Genesis)`

This is the version reported by the runtime and package metadata. It captures
the semantic-memory, ranked learned-memory, LLM transport-safety, explicit
local-RAG, local knowledge-graph, and quality-gate work merged after `v0.2.0`.

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
  embedding failure never reverses a completed primary-memory write. Semantic
  results are used only by the explicit `semantic recall <query>` request path
  with deterministic lexical fallback.
  The runtime retains a safe diagnostic when its most recent incremental index
  update failed, without exposing provider-specific error details.
- Deterministic reciprocal-rank fusion for explicit semantic recall when both
  current-session semantic and lexical candidates exist. Hybrid responses use
  rank scores; semantic-only responses retain cosine-similarity scores.
- An optional model-scoped local semantic-embedding cache. It is disabled by
  default, validates a source-content fingerprint before reuse, updates with
  memory lifecycle events, and remains separate from the primary memory schema.
- Ordered local source citations for knowledge-search responses, preserving
  document identity, title, source path, paragraph index, and chunk ID.
- An explicit bounded `knowledge context <query>` flow that renders no more
  than three cited local chunks and does not persist a conversation-memory
  record.
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
- Web research, citation collection, automatic RAG augmentation, or
  cross-document semantic relation extraction.
- Agent execution, tool gateway, browser/OS control, voice, vision, robotics,
  and smart-home integrations.
- Encryption at rest, cloud synchronization, multi-process storage locking,
  and persistence schema migration.

## Verification

Last verified in the local development environment:

- 880 automated tests pass through package-aware discovery.
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

Define relationship-catalog filtering or direct inspection only if the current
local graph grows beyond a usable list. Automatic semantic extraction,
ordinary-conversation augmentation, and implicit graph writes remain out of
scope.
