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
- A bounded session registry with atomic UTF-8 snapshots, deterministic order,
  and enforced default/active-session invariants
- A bounded general-memory store with atomic UTF-8 snapshots, validated record
  identity/content, and controlled metadata and tag aggregates
- Deterministic Brain request flow when the LLM runtime is disabled
- Deterministic English and Turkish standalone greetings; substantive messages
  that begin with a greeting continue through the normal conversation path
- OpenAI-compatible chat-completions provider with an optional system prompt
- Turkish and English user-message transport through the LLM conversation path
- Bounded, same-session multi-turn history with a configurable turn limit
- Opt-in learned-memory extraction with append-only corrections, bounded
  context, deterministic keyword selection, and ranked top-k selection
- A local, derived semantic-memory index core with validated embeddings and
  overflow-safe deterministic cosine ranking, capped vector dimensions, and
  bounded entry/identifier/aggregate live-memory use, available through the
  explicit semantic-recall request flow
- A shared 1,000,000-character semantic source limit and an 8 MiB exact UTF-8
  Ollama embedding-request boundary that rejects invalid or excessive payloads
  before network access while preserving lexical fallback
- A configurable cold semantic-rebuild provider-call budget (256 by default),
  with all cache misses counted before any local Ollama request
- Single-flight background semantic initialization and explicit retry, with
  observable safe states, lexical fallback during rebuilds, one dirty-snapshot
  retry, and shutdown-aware publication
- A bounded single-worker semantic update queue that keeps primary memory writes
  independent of Ollama latency, coalesces repeated record changes, and rejects
  stale in-flight results
- An opt-in, provider-scoped semantic-embedding cache with bounded UTF-8
  snapshots, entry/identifier/source/vector limits, deterministic ordering, and
  atomic rollback-safe replacement
- Deterministic Planner task generation
- Knowledge Foundation: `.txt` and `.md` document loading, paragraph parsing, in-memory chunk indexing, and case-insensitive search
- KnowledgeEngine orchestration for the full document-to-search pipeline
- A full automated test suite and shared code-quality standards
- A replaceable, explicit research source-discovery boundary that persists up
  to five ordered HTTPS metadata candidates without fetching, accepting, or
  indexing their content; the packaged runtime includes a bounded Crossref
  scholarly-metadata provider used only after an explicit action. Its fixed
  endpoint and redirects use the same public-address-pinned, hostname-verified
  TLS transport as explicit page loading
- A separate, versioned and atomically replaced accepted-source content store
  with exact UTF-8 byte count/SHA-256 validation, duplicate and storage bounds.
  Physical reads use the opened file descriptor and stop at 40,000,001 bytes;
  writes count exact UTF-8 output without constructing a second full snapshot.
  Sources accepted into a selected research run save content before provenance
  publication with compensating content/knowledge rollback. On startup, only
  records that exactly match accepted run provenance are restored into the
  knowledge index, without network access or persistent mutation. The explicit
  `Research content` desktop action reports only the captured startup state and
  restored document/paragraph counts; it does not reread persistence. Accepted
  paragraphs use the same opaque content-bound identity during initial indexing
  and startup restoration so newly recorded evidence retains its locator across
  restarts. The explicit `Evidence integrity` action compares recorded evidence
  with the current accepted paragraphs and reports only aggregate matched,
  missing, or changed counts without reading or writing persistence. The
  separate research-history snapshot is capped at 64 MiB and 20,000 aggregate
  nested collection entries before decode, serialization, or publication
- A read-only discovered-candidate acceptance preview followed by separate
  confirmation and final revalidation through the existing guarded HTTPS
  source loader
- A read-only accepted-source assessment preview that binds the exact run and
  document ID, then shows persisted provenance and only user-selected evidence
  without assigning a trust or quality score
- An append-only user-authored source-assessment record with explicit evidence
  IDs, a read-only confirmation preview, final revalidation, and atomic local
  persistence; no evidence or score is selected automatically
- An explicit user-authored information-trust label (`unassessed`, `low`,
  `medium`, or `high`) on each source assessment. Accepted external sources
  remain tainted as untrusted data with instruction authority fixed to `none`,
  regardless of the selected information-trust label
- An optional append-only assessment supersession link that preserves the old
  record, accepts only one active same-source predecessor, and shows current
  versus superseded history without rewriting an assessment
- Evidence-linked user-authored research claims with one explicit epistemic
  state (`fact`, `strong_evidence`, `likely`, `hypothesis`, `speculation`,
  `unknown`, or `contradicted`) and categorical confidence (`unassessed`,
  `low`, `medium`, or `high`). Exact evidence and ordered source provenance are
  persisted through a preview-confirm-record boundary. Corrections append a
  supersession link; Hypatia does not extract claims or calculate truth
- Explicit user-reviewed contradiction relationships between exactly two
  persisted claims. A preview displays both claims and their exact combined
  evidence before confirmation; the append-only record keeps the claim IDs,
  derived evidence IDs, and the user's own note. Reversed duplicate pairs are
  rejected, and Hypatia performs no automatic detection or truth decision
- An explicitly requested, read-only contradiction-candidate review over
  current claims. The configured LLM can suggest up to ten pairs, while Hypatia
  derives exact claim/evidence references itself, omits already recorded pairs,
  labels the rationale as untrusted, and records nothing automatically
- A read-only manual comparison preview for two to five explicitly selected
  sources accepted into the same run. It preserves selection order and shows
  provenance, user-selected evidence, and current user-authored assessments
  side by side without generating a verdict, score, or evidence selection. The
  view shows at most 20 evidence records and 10 current assessments per source
  while reporting the complete counts
- An append-only, user-authored comparison note for the exact selected-source
  order. It requires explicit evidence and current assessment IDs covering
  every source, uses a separate preview and confirmation, revalidates every
  reference before atomic persistence, and remains readable after restart
- A deterministic Markdown export preview for one terminal research run. It
  uses only the immutable persisted audit snapshot, includes provenance,
  evidence, assessment history, claims, user-reviewed claim contradictions,
  comparison notes, and failures, and exposes a
  full-content SHA-256 while bounding the desktop display. A separate confirmed
  save revalidates the exact preview and atomically creates a new `.md` file
  without replacing an existing destination. A read-only verification action
  compares an existing export's complete bytes with the current terminal run
- An initial local desktop shell for text chat, a refreshable session overview,
  explicit session selection, session details/recent conversations/activity,
  explicit lexical/semantic conversation recall, and semantic-memory runtime
  status, bounded cited local knowledge context/graph, a read-only local source
  catalog, explicit local-RAG questions, and user-initiated public HTTPS source
  loading. Chat, Knowledge, Research, and Appearance use separate tabs; the
  default eye-comfort palette, optional light/high-contrast themes, clear empty
  states, and grouped controls keep common chat tasks approachable. It delegates
  every action to the existing Brain runtime and adds no browser, cloud store,
  background crawler, or duplicate data store
- A single-flight desktop request worker for explicit chat, semantic recall,
  cited knowledge answers, research discovery, and approved HTTPS loading. It
  keeps Tkinter responsive, renders results only on the event thread, rejects
  duplicate submissions, preserves newly typed composer text, reports elapsed
  seconds without a fake percentage, and discards late results after close or
  an explicit cancellation request. Cancellation keeps other actions disabled
  until active timeout-bounded provider I/O returns; it does not kill that call.
  Crossref discovery and explicit HTTPS source loading additionally stop at
  safe post-network checkpoints before audit, indexing, or persistence changes

Roadmap modules listed above are product direction, not a claim that every module is
already implemented.

---

## Desktop shell (initial)

The first desktop window is a local Tkinter shell for normal text chat,
refreshing a read-only session overview, selecting an existing session, and
reading semantic-memory status. After choosing a session, its detail, recent,
and activity views are available as separate read-only actions. Start it from
the repository root after setting any desired local runtime environment
variables:

```powershell
.\.venv\Scripts\python.exe src\desktop_main.py
```

The Chat tab opens first and keeps sessions, conversation history, and the
message composer together. Knowledge and Research are available only when their
tabs are chosen, while Appearance contains the 10-to-20-point text-size setting
and Eye comfort, Light, and High contrast themes. Eye comfort is the default and
uses softened dark surfaces instead of pure black or white. These controls alter
presentation only and are not persisted between launches.

The window uses the same Bootstrap and Brain as the terminal entry point. A
clicked session only fills the selection field; choosing it remains explicit.
The separate `Recall` and `Semantic recall` buttons require a user-entered
query; they never add retrieval automatically to ordinary chat. Semantic recall
uses the existing configured fallback behavior when its optional runtime is not
available.
`Knowledge context` is separately user-initiated and returns only the bounded,
cited local context already exposed by the runtime. It neither calls an LLM nor
changes conversation memory.
`Knowledge graph` uses the same explicit query to show the bounded, cited local
source structure, and `Loaded sources` shows the read-only catalog of currently
loaded local documents. Neither action calls an LLM or changes conversation
memory or local knowledge state.
`Load file` opens a native file picker for a single local Markdown (`.md`) or
plain-text (`.txt`) file. Its structured request passes through the same Brain
and knowledge pipeline as every other desktop action; a successful load reports
the source identity and indexed chunk count. It neither calls an LLM nor adds a
conversation-memory record. Unsupported, empty, missing, or already loaded
files return the existing safe runtime failure instead of a partial load.
`Load source` accepts one explicitly entered public HTTPS URL. Hypatia validates
the URL and every redirect against private-network access, then connects to an
exact validated public address while retaining hostname-based TLS certificate
checks. If that address fails, only the remaining addresses from the same
public-only DNS answer are tried within one decreasing connection-time budget.
It accepts only bounded HTML/plain-text/Markdown content, extracts
readable text, and indexes it through the same knowledge pipeline with its final
URL preserved. The explicit request runs on the desktop's single daemon worker
so the Tkinter event loop stays responsive; it does not search for sources,
call an LLM, or write conversation memory.
`Start research` creates a local audit record for one question. `Research runs`
fills a read-only selector with each question, status, and exact ID. Choosing a
run only changes the local workspace selection and starts no research action;
the selector also shows complete source, evidence, and claim counts from that
already loaded snapshot. Later explicit actions use the selected ID. The run
keeps timestamps and safe failure records, but does not duplicate downloaded
page text or make web research autonomous.
Accepted sources from that same loaded snapshot appear by bounded title and
exact document ID. Choosing a source does not edit the form or start an action;
`Use for assessment` copies only its exact ID into the single-source field, and
`Add to comparison` appends it once to the ordered manual comparison field while
preserving the five-source limit.
The source choice also filters recorded evidence from that same immutable run
snapshot. Each option shows a bounded single-line excerpt and exact evidence ID;
selection alone changes nothing. Separate handoffs append one exact ID to the
assessment, claim, or comparison evidence field. Source ownership is required
for assessment and comparison, duplicates are ignored, and the existing 20-ID
claim and 100-ID comparison-note limits remain enforced.
User-authored assessments for the chosen source appear from the same loaded run
snapshot with `current` or `superseded` audit state, bounded text, and exact ID.
Selection alone changes nothing. Only a current same-source record can be copied
as the next correction target or appended to the manual comparison assessment
field; comparison source membership, duplicate refusal, and the 50-ID limit are
enforced locally.
User-authored claims for the selected run also appear from that immutable
snapshot. Each label retains `current` or `superseded` audit state, epistemic
state, categorical confidence, bounded text, and exact claim ID. Selection edits
nothing. Separate handoffs accept only a current claim and either copy its ID as
the next predecessor or append it once to the manual contradiction field without
exceeding exactly two IDs.
`Find sources` sends the selected collecting run's question to Crossref and
connects its fixed endpoint and same-origin redirects only to an address from
their own public-DNS validation while TLS verifies `api.crossref.org`. It
records the query, provider, time, and at most five ordered DOI metadata
candidates. The desktop displays their titles and URLs; `Use selected URL`
copies one choice into the separate source-load field. `Preview & load`
revalidates the exact run, discovery, and candidate without network access,
then asks for confirmation and revalidates again before using the existing
source loader. Discovery and preview never download, accept, trust, index,
cite, or write candidate content to conversation memory. Set
`HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER=disabled` to disable discovery.
`Save evidence` records a user-selected indexed paragraph only when it belongs
to a source attached to the selected run. It keeps a bounded excerpt, source
and paragraph locator, full-paragraph fingerprint, note, and timestamp;
`View evidence` remains available after restart. Hypatia does not yet select or
interpret evidence automatically.
`Preview assessment` reads one accepted source by its selected document ID and
shows that source's persisted provenance plus only its already recorded
evidence and user-authored assessment history. A successful source attachment
fills the document ID field, but the preview remains a separate action. It
performs no network, LLM, memory, graph, knowledge-index, or persistence
operation and does not claim that the source is trustworthy, relevant, or high
quality. `Preview & save assessment` requires comma-separated evidence IDs and
the user's own assessment text and information-trust label. Hypatia verifies
that every cited record belongs
to the selected accepted source, shows an exact no-write preview, asks for
confirmation, and revalidates before appending the assessment to the atomic run
snapshot. Entering an optional previous assessment ID records a correction link
only when that target is from the same run and source and has not already been
superseded. Both records remain visible; Hypatia labels their audit state but
never chooses evidence or assigns a score automatically. `High` information
trust still leaves the source marked as external untrusted data with instruction
authority `none`.
`View claims` shows the selected run's persisted claim history. `Preview & save
claim` requires comma-separated evidence IDs, the user's own claim text, an
epistemic state, and categorical confidence. Hypatia derives and displays the
exact accepted sources from the cited evidence, then asks for confirmation and
revalidates before an atomic append. An optional predecessor claim ID creates a
single backward correction link without changing the old record. No LLM,
automatic claim extraction, evidence selection, or truth score is involved.
`View contradictions` shows only relationships already recorded for the
selected run. `Preview & save contradiction` requires exactly two
comma-separated claim IDs plus the user's own explanation. Hypatia resolves the
persisted claims and their exact combined evidence, shows a no-write preview,
asks for confirmation, and revalidates before atomic append. The relationship
is symmetric for duplicate detection, remains readable after restart, and does
not change either claim or decide which one is true.
`Suggest contradictions` is a separate optional read-only action. It sends only
the selected run's bounded current claims to the configured LLM, with no chat
history or tools, then displays possible pairs and exact persisted evidence IDs.
Suggestions are not facts or saved relationships. To record one, the user must
select it and choose `Use selected pair`, or enter the two IDs manually. The
handoff copies only the two claim IDs; it never copies model rationale into the
user's explanation. The existing preview and confirmation flow remains
mandatory.
`Compare sources` accepts two to five comma-separated document IDs from the
selected research run. It shows the sources in the entered order with persisted
provenance, explicitly recorded evidence, and only current user-authored
assessments. The preview works for collecting and closed runs and makes no
network, LLM, memory, graph, knowledge-index, event-bus, or persistence call. It
does not decide which source is correct or assign a trust score. To keep the
desktop responsive, it shows at most 20 evidence records and 10 current
assessments per source and reports both displayed and complete counts. For a
collecting run, `Preview & save comparison note` accepts the user's own note and
comma-separated evidence and current assessment IDs. The runtime requires both
reference types to cover every selected source, shows an exact no-write preview,
asks for confirmation, and revalidates before an atomic append. A later
`Compare sources` view shows up to 20 notes recorded for that exact source order
and reports the complete count; Hypatia does not write the note, choose its
references, or generate a verdict.
`Export preview` accepts the selected run ID only after that run is completed,
failed, or cancelled. It deterministically renders the persisted audit record
as Markdown and reports the exact snapshot time, safe suggested filename, full
character count, omitted preview count, and SHA-256 of the complete content.
Remote excerpts and authored text are escaped as literal quoted material. The
desktop shows at most 24,000 source characters and performs no file write,
network, provider, LLM, memory, graph, live-index, or event-bus operation.
`Save export` is enabled by the displayed preview rather than a fresh hidden
render. It asks the user for a new `.md` destination, shows the exact path and
fingerprint for confirmation, sends the preview's run ID, update time, and hash
back through Brain, and re-renders the immutable persisted run before atomically
publishing complete UTF-8 bytes. A changed preview, invalid path, or existing
destination is rejected without replacement. The save performs no network,
provider, LLM, memory, graph, live-index, event-bus, or research-audit mutation.
`Verify export` asks for an existing `.md` file and compares its complete byte
count and SHA-256 with a fresh deterministic rendering of the selected terminal
run. It reads one stable regular-file descriptor in bounded chunks, rejects a
file that changes during the read, and reports either `MATCH` or
`DOES NOT MATCH`. The file is never decoded, imported, repaired, or written;
research, memory, graph, live-index, event-bus, network, provider, and LLM state
remain untouched.
The `Final status` control previews `completed`, `failed`, or `cancelled` before
asking for separate confirmation. Completion requires at least one accepted
source and one evidence record, while failure requires a recorded failure. A
closed run is permanent and cannot accept
 more sources, evidence, assessments, claims, claim contradictions, or failure records; Hypatia rejects a closed-run source
request before opening the network connection.
`Ask sources` deliberately invokes the existing `ask knowledge` local-RAG path
only when its button is selected. It provides the configured runtime with up to
three bounded cited local chunks and never adds retrieval to ordinary chat or
changes conversation memory.
Whenever a knowledge response carries existing source records, the desktop
transcript shows them in returned order with title, local path, paragraph, and
chunk ID. It does not manufacture or persist source information.
To make an explicit local `related_to` link, enter two source IDs and select
`Preview and link`. Hypatia first shows the existing runtime preview and only
sends the revalidating relation command after a separate confirmation. Declining
or failing the preview leaves the local graph and conversation memory unchanged.
Use `Preview and remove` with the same two IDs to remove an existing local
relation. Hypatia first shows the runtime removal preview and sends the separate
revalidating removal command only after confirmation; declining or failing the
preview leaves the local graph and conversation memory unchanged.
`Active links` shows the existing read-only catalog of local source relations
and their persistence state. It does not load sources, call an LLM, or change
the graph or conversation memory.
To rename a session, select it, enter a new session ID, and use `Preview rename`.
Hypatia shows the existing runtime preview first and only sends the
transactional rename command after confirmation; on success it refreshes the
session list from Brain.
It does not yet include voice, PDF import, multi-source research synthesis,
general web search, browser tools, automatic retrieval, automatic candidate
acceptance, or automatic knowledge mutations; those remain separate,
test-first increments.

### Windows desktop package

The first distributable target is Windows. Build it from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop-build.txt
.\tools\build_desktop.ps1
```

The resulting application is `dist\Hypatia\Hypatia.exe`. It uses local data
under `%LOCALAPPDATA%\Hypatia` rather than writing beside the executable:
conversation memory, sessions, explicit knowledge relations, and research-run
audit records remain on this device. Set `HYPATIA_DESKTOP_DATA_DIR` to an
**absolute** path only when you
deliberately need a different local data root. The initial package has manual
updates; it does not self-update or automatically migrate data from a developer
checkout.

### Linux desktop package

The first verified Linux target is Ubuntu 24.04 x64. Build it from the
repository root with Python 3.14 and Tkinter available:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-desktop-build.txt
tools/build_desktop.sh --clean
```

The resulting application is `dist/Hypatia/Hypatia`. It stores local state
beneath `${XDG_DATA_HOME:-$HOME/.local/share}/hypatia`; only an absolute
`XDG_DATA_HOME` is honored. The cross-platform absolute
`HYPATIA_DESKTOP_DATA_DIR` override still takes precedence. The published
`Hypatia-linux-x64-v<version>.tar.gz` archive is built and opened under Xvfb on
Ubuntu before release. Updates remain manual, and the package adds no telemetry,
bundled credentials, cloud store, or automatic data migration.

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
except through the explicit semantic-recall command documented below. The
embedding transport rejects HTTP redirects, so an opted-in request remains at
its validated local endpoint. It reads at most 1 MiB before parsing an
embedding response. See the
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
HYPATIA_SEMANTIC_MEMORY_REBUILD_MAX_PROVIDER_CALLS=256
HYPATIA_SEMANTIC_MEMORY_REBUILD_TIMEOUT_SECONDS=120
```

The endpoint and model shown are defaults when their optional settings are
absent. No API key is used. When the enabled value is exactly lowercase `true`,
Bootstrap publishes the primary application first and starts one daemon
semantic rebuild in the background. A successful refresh swaps in a complete
replacement index. A cold, slow, or unavailable local provider therefore does
not hold the primary startup path; semantic retrieval reports `initializing`
and uses deterministic lexical fallback until a complete index is ready. If
the first refresh fails, the runtime reports a safe unavailable state. Local
memory add, update, delete, and expiry events enqueue best-effort derived-index
maintenance on the same single daemon worker. A primary-memory operation does
not wait for its embedding. Up to 20,000 distinct pending IDs are retained;
repeated events for one ID are coalesced and a later update or delete prevents
an older in-flight result from being published. An embedding failure never
undoes an already-completed primary-memory operation. The vectors remain in RAM
and are recreated from local memory on the next successful rebuild.

Only one full rebuild can run at a time. A memory event during rebuilding marks
the captured snapshot dirty and allows one coalesced rebuild attempt with a new
snapshot; a second changing attempt publishes neither a stale nor partial
index. Shutdown rejects new rebuilds, signals cancellation, and prevents an
in-flight job from publishing an index. An already-running local HTTP request
still completes or reaches its configured timeout before the worker can observe
that cancellation.

Before a startup rebuild opens any provider request, Hypatia resolves every
provider-scoped cache lookup and counts the misses. The default maximum is 256;
set `HYPATIA_SEMANTIC_MEMORY_REBUILD_MAX_PROVIDER_CALLS` to an ASCII whole
number from 0 through 20,000 when a different local policy is required. Zero is
cache-only. If the count exceeds the configured budget, the semantic rebuild
fails before the first Ollama call, cache replacement, or runtime publication;
the primary application remains available.

One monotonic deadline also covers the complete startup rebuild, including
memory/source/cache preflight and every sequential provider call. It is 120
seconds by default. Set `HYPATIA_SEMANTIC_MEMORY_REBUILD_TIMEOUT_SECONDS` to a
positive finite value no greater than 3,600 when a different local policy is
required. Each Ollama request uses the shorter of its normal request timeout and
the remaining rebuild time. Expiry rejects the incomplete build before cache or
runtime publication; the primary application retains the v0.3.66 degraded
semantic behavior.

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

Use `semantic recall status` to inspect the optional runtime without generating
an embedding or changing memory. It reports whether the runtime is disabled,
initializing, refreshing, updating, unavailable, ready, or stopped. A ready
runtime, and
a refreshing runtime with a previous complete index, also report indexed-record
count and embedding dimension. Separate safe rebuild and incremental-update
diagnostics never expose provider, endpoint, model, cache, source-text, budget,
or exception details.

Use the exact `semantic recall retry` command to schedule one complete bounded
background rebuild after an unavailable startup or later rebuild failure. It
returns immediately; another retry while work is active reports the existing
job and does not start a second one. It is never triggered by normal chat,
recall, or status. Success publishes only a complete replacement; failure
preserves the last complete index when one exists and otherwise leaves semantic
retrieval unavailable.

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
conversation-memory record. The user's question and source excerpts are
separated, each excerpt is labelled as an untrusted source, and a code-owned
per-request system instruction denies source text any instruction authority.
The request has no conversation history or tool capability. This reduces the
authority of prompt-injection text found in a document; it is not a guarantee
that a language model will always ignore adversarial content.

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
The complete ordered snapshot is capped at 20,000 relations and 64 MiB, with
1,024-character endpoint IDs and exact UTF-8 bounded atomic output.
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
