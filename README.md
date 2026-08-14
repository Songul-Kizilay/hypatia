# Hypatia

**Documentation-first development:** Hypatia has a tested core runtime and a completed Knowledge Foundation. Product capabilities are introduced only after their behavior is covered by tests.

Start with the [project documentation](docs/README.md), including the [vision](docs/Bible/01_Vision.md), [architecture](docs/Architecture/README.md), [module map](docs/Modules/README.md), and [roadmap](docs/Roadmap/README.md).

> A local-first AI research companion.

Hypatia is an AI ecosystem designed to learn, research, teach and grow together with its user.

Its mission is not to replace human thinking.

Its mission is to become a lifelong research companion.

---

## Vision

To create the world's most capable personal AI research companion.

---

## Core Principles

- Local First
- Privacy First
- Human Centered
- Evidence Based
- Modular
- Lifelong Learning

---

## Modules

- Brain
- Memory
- Research
- Bug Bounty
- Sentinel
- Robotics
- Smart Home
- Vision
- Voice
- Career Intelligence
- Gaming
- Cinema
- Composer
- XR
- Mobile
- Watch

---

## Roadmap

- v0.1 Foundation: desktop, voice, memory, Ollama, and chat
- v0.2 Research
- v0.3 Security research
- v0.4 Sentinel
- v0.5 Smart home
- v1.0 Scout robot

---

## Current capabilities

- Application bootstrap, configuration, logging, and dependency injection
- Sessions and persisted structured conversation memory
- Session creation, activation, targeted overview/details/activity/recent views,
  conversation search, rename, and guarded deletion
- Deterministic Brain request flow when the LLM runtime is disabled
- OpenAI-compatible chat-completions provider with an optional system prompt
- Turkish and English user-message transport through the LLM conversation path
- Bounded, same-session multi-turn history with a configurable turn limit
- Opt-in learned-memory extraction with append-only corrections, bounded
  context, deterministic keyword selection, and ranked top-k selection
- A local, derived semantic-memory index core with validated embeddings and
  deterministic cosine ranking; it is not yet connected to the request flow
- Deterministic Planner task generation
- Knowledge Foundation: `.txt` and `.md` document loading, paragraph parsing, in-memory chunk indexing, and case-insensitive search
- KnowledgeEngine orchestration for the full document-to-search pipeline
- A full automated test suite and shared code-quality standards

Roadmap modules listed above are product direction, not a claim that every module is
already implemented.

---

## LLM runtime quickstart

Hypatia can use any provider that exposes an OpenAI-compatible chat-completions
endpoint. Set these values in the process environment before starting Hypatia:

```text
HYPATIA_LLM_ENABLED=true
HYPATIA_LLM_BASE_URL=<OpenAI-compatible chat completions endpoint>
HYPATIA_LLM_MODEL=<model name>
HYPATIA_LLM_API_KEY=<required for non-local endpoints>
```

An API key is required for every non-local endpoint. It is optional only when
the endpoint explicitly targets `localhost`, `127.0.0.1`, or `::1`, which lets
a local Ollama-compatible runtime run without a placeholder secret. In that
keyless local mode Hypatia sends no `Authorization` header. Use a placeholder
only in examples that need to show a non-local key; never commit a real secret.
To keep a configured key protected in transit, remote endpoints must use
`https://`. Plain `http://` is accepted only for an explicitly local endpoint.
Completion requests do not follow HTTP redirects, preventing a bearer token
from being forwarded to another endpoint.

For a standard local Ollama chat runtime, set the endpoint and model, omit
`HYPATIA_LLM_API_KEY`, then start Hypatia:

```text
HYPATIA_LLM_ENABLED=true
HYPATIA_LLM_BASE_URL=http://localhost:11434/v1/chat/completions
HYPATIA_LLM_MODEL=<your-installed-chat-model>
```

Optional process-environment settings:

```text
HYPATIA_LLM_SYSTEM_PROMPT=<custom prompt>
HYPATIA_LLM_HISTORY_MAX_TURNS=<positive integer>
HYPATIA_LLM_TIMEOUT_SECONDS=<positive finite seconds>
```

If `HYPATIA_LLM_SYSTEM_PROMPT` is absent, Hypatia uses its default system prompt.
If `HYPATIA_LLM_HISTORY_MAX_TURNS` is absent, the default is 8 conversation turns.
If `HYPATIA_LLM_TIMEOUT_SECONDS` is absent, chat requests use 120 seconds for an
explicit loopback endpoint such as local Ollama and 30 seconds for a non-local
endpoint. A configured positive finite value overrides either default.
A positive history limit sends only the most recent N structured turns from the
same resolved session to the model, in order. The current request is not included
in its own history.

Turkish and English user messages can travel through this conversational path.
Previous conversation turns from the same resolved session are supplied as
context. When the LLM runtime is disabled, Hypatia preserves its existing
deterministic behavior.

---

## Learned-memory runtime settings

Learned-memory extraction is opt-in. It is activated only when both the LLM
runtime is configured and this exact process-environment value is set:

```text
HYPATIA_LEARNING_ENABLED=true
```

The following optional settings control which learned memories are supplied to
the LLM as additional context:

```text
HYPATIA_LEARNED_MEMORY_CONTEXT_LIMIT=<non-negative integer>
HYPATIA_LEARNED_MEMORY_SELECTOR=keyword|ranked
HYPATIA_RANKED_LEARNED_MEMORY_SELECTOR_LIMIT=<non-negative integer>
```

`HYPATIA_LEARNED_MEMORY_CONTEXT_LIMIT` limits the final learned-memory context.
With no selector configured, Hypatia keeps its existing current-memory order.
`keyword` selects matching memories deterministically; `ranked` orders relevant
memories by deterministic keyword relevance. The ranked selector limit is
applied first, then the final context limit is applied. A ranked limit of `0`
therefore selects no learned memories. The ranked selector limit is ignored
unless `HYPATIA_LEARNED_MEMORY_SELECTOR=ranked`.

All numeric learned-memory limits must be non-negative integers. Invalid values
or a selector value other than the exact lowercase `keyword` or `ranked` cause
startup configuration to fail clearly instead of silently changing context.

The semantic-memory index is currently a tested, in-memory building block. An
explicit Ollama `/api/embed` adapter is available for a local Ollama service,
but Hypatia does not activate it automatically unless its opt-in settings are
set. It does not download a model, persist vectors, or change the response path
except through the explicit semantic-recall command documented below. See the
[Architecture Audit v0.1](docs/Architecture/Architecture_Audit_v0.1.md) for
its staged rollout boundary.

---

## Semantic-memory local runtime

Semantic memory is disabled by default. To build a derived in-memory index from
the active local memory records at startup, install and run Ollama locally, make
an embedding model available, then set:

```text
HYPATIA_SEMANTIC_MEMORY_ENABLED=true
HYPATIA_SEMANTIC_MEMORY_OLLAMA_ENDPOINT=http://localhost:11434/api/embed
HYPATIA_SEMANTIC_MEMORY_OLLAMA_MODEL=embeddinggemma
HYPATIA_SEMANTIC_MEMORY_OLLAMA_TIMEOUT_SECONDS=120
HYPATIA_SEMANTIC_MEMORY_PERSIST_EMBEDDINGS=true
```

The endpoint and model shown are defaults when their optional settings are
absent. No API key is used. Startup calls the configured local endpoint only
when the enabled value is exactly lowercase `true`. A successful refresh swaps
in a complete replacement index; if the first refresh fails, bootstrap stops
before publishing its dependency container. After a successful startup, local
memory add, update, delete, and expiry events update the derived index on a
best-effort basis. An embedding failure never undoes an already-completed
primary-memory operation. The vectors remain in RAM and are recreated from
local memory on the next successful startup.

The built-in local HTTP transport allows up to 120 seconds for each embedding
request by default. Set `HYPATIA_SEMANTIC_MEMORY_OLLAMA_TIMEOUT_SECONDS` to a
positive finite number when the local machine needs a different limit. This
accommodates a cold local model load without making Hypatia wait indefinitely
when the local service is unavailable.

Embedding persistence is separately opt-in. With
`HYPATIA_SEMANTIC_MEMORY_PERSIST_EMBEDDINGS=true`, Hypatia keeps a derived
`semantic_embeddings.json` file beside the configured memory file. It contains
validated vectors and SHA-256 fingerprints of source text, scoped to the
configured local Ollama endpoint and model. A changed record, a deleted record,
or a different model never reuses an old vector. The derived cache uses atomic
writes, is not part of the primary-memory JSON schema, and a missing or corrupt
cache falls back to a fresh local embedding request instead of blocking the
primary memory flow. Leave it disabled when local embedding persistence is not
appropriate for the device's storage policy.

Use `semantic recall <query>` to retrieve conversation records from the active
or explicitly selected session. When both indexed semantic and lexical matches
exist in that session, Hypatia uses deterministic reciprocal-rank fusion and
labels the response `hybrid`; its three-decimal values are rank scores. When
only semantic matches exist, the response remains `semantic` and displays
cosine-similarity scores. If semantic runtime is disabled, its index has no
eligible record, or the local provider fails, the same command falls back to
deterministic lexical conversation recall and labels the result `lexical
fallback`.

Normal `recall <query>` remains lexical and does not call the semantic runtime.
Semantic recall does not add a conversation record, alter ordinary messages, or
search other sessions.

---

## Local knowledge sources

Knowledge search results retain their source identity. Alongside the existing
ordered result chunks, Hypatia returns an ordered citation record for each
match: document ID, title, local source path, paragraph index, and chunk ID.
This makes the current local search result explainable without adding automatic
prompt augmentation, web retrieval, or a RAG dependency.

Use `knowledge context <query>` for an explicit bounded local context view. It
returns at most three matching chunks, displays each with its source citation,
and limits displayed chunk text to 600 characters. It does not add a
conversation record, inject text into an LLM request, or affect ordinary
`search <query>` behavior.

With an enabled LLM runtime, `ask knowledge <query>` sends only the bounded,
cited local context to the model. It is explicit, limits each supplied source
chunk to 600 characters, keeps citations on the response, and does not add a
conversation-memory record.

Use `list knowledge` to show the local source catalog before inspecting a
specific source or creating a future explicit relationship. Every entry shows
its stable document ID, title, local source path, type, and chunk count; this
read-only command neither calls an LLM nor adds a conversation record.
For files loaded from disk, that ID is derived from the resolved local source
path, so reopening the same file retains its identity even if the file content
changes.

Use `preview knowledge relation <source_document_id> -- <target_document_id>`
to validate a proposed `related_to` link between two distinct catalogued local
documents. It produces a pending-change view only: the graph, JSON memory, LLM
context, and conversation memory remain unchanged.

Use `apply knowledge relation <source_document_id> -- <target_document_id>`
only when the proposed relation should take effect. It freshly validates the
same two document IDs, adds one `related_to` edge to the current in-memory
graph, and rejects duplicate or invalid links. The graph is still local and
ephemeral: this command does not write conversation memory, call an LLM, or
add a conversation record.

When running through Hypatia's standard Bootstrap runtime, an applied relation
is also saved in a separate local, versioned relation file. After restart it is
restored only when both original local source files have been loaded again.
If that file cannot be written, Hypatia removes the in-memory edge instead of
claiming success. This store is separate from conversation memory and is never
sent to an LLM.

Use `preview remove knowledge relation <source_document_id> --
<target_document_id>` to inspect an existing applied link without changing it.
Only `remove knowledge relation <source_document_id> -- <target_document_id>`
removes the link. When the relation is persisted, Hypatia removes the graph
edge and local record together; a relation-file write failure restores the
graph edge and returns a controlled failure instead.

Use `list knowledge relations` to inspect the active local links before
removing one. Each line includes the source and target IDs, the `related_to`
type, and whether it is persisted or in-memory only. This list never loads an
unopened source and never changes graph, relation-file, conversation-memory, or
LLM state.

Use `knowledge graph <query>` to inspect the deterministic structure of local
matching sources. It returns up to three cited document-to-paragraph
`contains` relationships plus any explicitly applied `related_to` edge touching
a matching document. This graph is derived in memory from loaded local
documents; it neither calls an LLM nor changes conversation memory, and it does
not infer semantic relationships between documents.
