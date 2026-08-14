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
HYPATIA_LLM_API_KEY=<required API key>
```

The API key is required whenever the LLM runtime is enabled. Use a placeholder in
documentation and scripts; never commit a real secret.

Optional process-environment settings:

```text
HYPATIA_LLM_SYSTEM_PROMPT=<custom prompt>
HYPATIA_LLM_HISTORY_MAX_TURNS=<positive integer>
```

If `HYPATIA_LLM_SYSTEM_PROMPT` is absent, Hypatia uses its default system prompt.
If `HYPATIA_LLM_HISTORY_MAX_TURNS` is absent, the default is 8 conversation turns.
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

Use `semantic recall <query>` to retrieve conversation records from the active
or explicitly selected session. When an indexed semantic result is available,
the response labels it as `semantic` and includes a three-decimal similarity
score. If semantic runtime is disabled, its index has no eligible record, or
the local provider fails, the same command falls back to deterministic lexical
conversation recall and labels the result `lexical fallback`.

Normal `recall <query>` remains lexical and does not call the semantic runtime.
Semantic recall does not add a conversation record, alter ordinary messages, or
search other sessions.
