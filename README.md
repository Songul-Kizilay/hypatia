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
- Deterministic Brain request flow when the LLM runtime is disabled
- OpenAI-compatible chat-completions provider with an optional system prompt
- Turkish and English user-message transport through the LLM conversation path
- Bounded, same-session multi-turn history with a configurable turn limit
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
