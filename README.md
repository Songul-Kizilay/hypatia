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
- A bounded no-write Research-plan draft editor in the desktop's authored-
  analysis area. It collects the explicit question, one ordered instruction per
  line, and optional comma-separated exact source document IDs on the matching
  line; sends only the existing structured preview intent; and displays the
  complete ready or rejected result without confirmation, persistence,
  `ResearchRun` mutation, provider/network/LLM access, automatic source choice,
  or execution
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
  Research workspace uses four ordered workflow tabs plus compact authored-
  analysis sub-tabs, and its three later steps repeat the selected question,
  status, exact run ID, and complete source/evidence/claim counts in a read-only
  current-run banner; the default
  eye-comfort palette, optional light/high-
  contrast themes, clear empty states, and grouped controls keep common tasks
  approachable. It delegates every action to the existing Brain runtime and adds
  no browser, cloud store, background crawler, or duplicate data store
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

Research is arranged as a left-to-right workflow: `1 Overview`, `2 Sources &
evidence`, `3 Authored analysis`, and `4 Review & export`. Authored analysis has
separate `Saved records`, `Comparison`, `Assessment`, `Claims & contradictions`,
and no-write `Plan draft` views so all controls remain available without one
screen-height form. Switching either set of tabs changes presentation only: it does not call
Brain, start a provider request, save data, or change a selected run or field.
The Sources & evidence, Authored analysis, and Review & export tabs each repeat
the selected question, status, and exact run ID in one read-only `Current
research run` banner. It comes from the already loaded run snapshot, and an
empty or invalid selection shows guidance instead of keeping stale identity.
The same banner also shows complete source, evidence, and claim counts so users
can see the selected run's progress without returning to Overview. These counts
come from the same snapshot and never start another read or action.
Overview also shows a compact workflow snapshot with complete source/evidence,
assessment/comparison-note/claim/contradiction counts and the current review
status. It reports existing records only; it does not decide readiness, truth,
or a research conclusion.
The already loaded run catalog can be filtered locally by bounded question
text, exact status, or exact run ID. Filtering does not request or change data;
no-match keeps the active run and authored fields intact, and `Clear` restores
the full immutable catalog.
The current loaded or filtered view can also be sorted locally by newest
update, oldest update, newest creation, or question. The current order remains
visible, deterministic run-ID ties are stable, and sorting preserves the full
catalog, filter membership, active run, and authored fields without requesting
or changing data.
If filtering hides the active run, `Show active run` clears only that local
filtering state, preserves the selected order and authored fields, and restores
the exact active row. Missing or invalid local state is refused without changing
data.
An explicit status choice can show all, collecting, completed, failed, or
cancelled runs. It combines locally with the bounded text filter and current
sort, reports visible/total counts, and never requests or changes data.
Beside those view controls, one compact catalog line always reports complete
all/collecting/completed/failed/cancelled counts from the full loaded snapshot.
Filtering and sorting do not change those totals, and an empty catalog shows
zero for every lifecycle without requesting data.
`Reset view` clears both local filters, returns to newest-update ordering,
re-shows the complete catalog, and reselects the loaded active run. It never
changes the run itself or user-authored research fields and starts no request.
Overview also shows the selected run's seconds-level timezone-aware creation
and update timestamps plus the complete safe-failure count. It never displays
failure stage or reason text and performs no additional read.
The same immutable selected snapshot supplies an evidence-coverage line with
accepted sources, sources represented by at least one evidence record, and
accepted sources without evidence. Repeated evidence for one source counts once;
the line makes no quality, completeness, or readiness decision.
An adjacent assessment-coverage line reports accepted sources with a current
user-authored assessment and the accepted remainder. Superseded history does
not count as current, source membership is deduplicated by exact ID, malformed
foreign references are ignored, and the line makes no quality or readiness
decision.
Sources & evidence can then show all accepted sources, only those without
recorded evidence, or only those without a current authored assessment. This is
a stable local exact-ID view: superseded-only history remains uncovered, the
active source is preserved even while hidden, and that exact source returns
with the all view without changing authored fields or requesting data.
One adjacent read-only catalog summary always shows the complete All, Without
evidence, and Without current assessment counts from the selected run. These
totals do not change when the local source view changes and make no quality or
readiness decision.
If a coverage view hides the active source, `Show active source` restores All
sources and that exact row, including its read-only evidence and assessment
records. Empty, stale, or unknown state is refused without changing authored
fields or requesting data.
The selected row also has a compact read-only record summary: exact evidence,
assessment-history, and current-assessment counts from the same immutable run.
Superseded assessments remain in history but not the current count; hidden or
invalid source state clears the summary, with no quality/trust conclusion or
additional request.
The same line includes a normalized bounded source title, exact source document
ID, and exact research-run ID. The complete source record must match canonical
run membership, so changed or foreign provenance cannot be paired with those
counts.
It also shows the persisted source safety boundary: external data remains
tainted as `external_untrusted_data` with instruction authority `none`. Even a
user-authored high information-trust assessment cannot grant that source command
authority, and displaying the boundary performs no additional request.
An adjacent fourth line counts current user-authored information-trust labels as
Unassessed, Low, Medium, and High. Superseded corrections remain in history but
not these current counts; foreign records cannot contribute, and the numbers do
not constitute a Hypatia-generated verdict.
The Records line also shows how many unique recorded evidence IDs are explicitly
cited by current assessments versus all evidence for that source. Repeated
citations count once, superseded/foreign/unknown IDs do not count, and no
completeness or quality judgment is made.
`Source details` opens a local read-only dialog for the exact selected source.
It shows bounded title, exact source/run IDs, content type, and timezone-aware
fetched/accepted times while deliberately excluding the source URL and content;
it performs no provider, storage, network, or mutation action.

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
already loaded snapshot. The three later workflow tabs repeat that exact
identity and the complete source/evidence/claim counts without another read.
Overview additionally summarizes every existing workflow record category and
the current status without another read. Later explicit actions use the
selected ID. The run
keeps timestamps and safe failure records, but does not duplicate downloaded
page text or make web research autonomous.
`Filter` narrows only that already loaded selector by a case-insensitive
question fragment, exact status, or exact ID, with a 200-character bound.
No-match does not change the active run or authored fields; `Clear` restores the
complete loaded catalog without another read.
The selected run's Overview metadata line shows its immutable created/updated
times with timezone offsets and only the aggregate safe-failure count. It never
shows failure details or opens another runtime path.
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
Persisted user-reviewed contradictions for that run appear beside the claims.
Each label retains its exact claim pair, bounded authored note, recorded time,
and exact contradiction ID. Selection edits nothing. `Use selected pair` copies
only the two claim IDs into the manual contradiction field, preserves the manual
note, and rejects stale or invalid run-bound presentation state locally.
Persisted source-comparison notes for the run also appear in a read-only selector.
The label shows bounded authored text, recorded time, and exact note ID, while a
separate summary keeps every exact source, evidence, and assessment reference
visible. Three explicit buttons copy only the chosen reference type to its manual
field; they preserve the comparison text and all other fields.
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
It does not yet include voice, PDF import, Research-plan persistence or
execution, multi-source research synthesis, general web search, browser tools,
automatic retrieval, automatic candidate acceptance, or automatic knowledge
mutations; those remain separate, test-first increments.

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

When the configured provider exposes the optional `generate_json(...)`
capability, extraction requests one bounded structured response: a trusted
system instruction, a 512-token bound, and an exact JSON response schema that
mirrors the learned-memory parser. Providers exposing only `generate` keep their
previous plain call. The parser remains the final authority in both cases, so a
declared schema never bypasses validation; reasoning preambles and
Markdown-fenced payloads are still rejected.

When extraction fails, Hypatia emits one bounded
`brain.learned_memory.extraction_failed` event carrying only the request ID and
the cause class name. It never carries the user message, source text, candidate
values, or the raw model response. Ordinary chat still succeeds and the
conversation record is still persisted. No event is emitted for successful or
no-op extraction.

---

## Research execution persistence

Research-plan execution state is ephemeral by default. To persist it, set:

```text
HYPATIA_RESEARCH_EXECUTION_PERSISTENCE_ENABLED=true
```

The value must be exactly lowercase `true`. With the setting absent or any other
value, execution state stays in memory and is lost when Hypatia exits, exactly as
before.

When enabled, execution snapshots are written to `research_executions.json`
beside the research-run store, in a separate versioned document. `ResearchRun`
and its schema are untouched, so existing snapshots stay valid and no migration
runs. Deleting the execution file returns the runtime to ephemeral behavior.

Only execution bookkeeping is persisted: step identity, declared capability,
status, operation identity, the work flag, bounded detail, the plan question, and
the bound run identity. Authored step instructions, fetched page bodies, source
excerpts, notes, and claim text are never written, because those already live in
the research run.

On restart, an execution is restored for inspection, never resumed. A step
recorded as running when the process ended becomes `interrupted`, since what its
operation actually did is unknown; completed steps stay completed and pending
steps stay pending. Authorizations are not persisted, so a restored execution
cannot be advanced and nothing is replayed. A corrupt store raises at startup
rather than being replaced by an empty one.

---

## Background research scheduling

Background research is disabled by default. To persist scheduled tasks, set:

```text
HYPATIA_BACKGROUND_RESEARCH_ENABLED=true
```

The value must be exactly lowercase `true`. Tasks are written to
`research_background_tasks.json` beside the research-run store, in a separate
versioned document; `ResearchRun` and the execution store are untouched.

A task is scheduling bookkeeping around an execution a human already approved.
Running one drives the existing autonomy service, which drives the existing
execution service, so a task cannot invent a capability, weaken a budget, accept
a source, or promote a claim. Only identifiers, status, the declared budget,
retry counters, a bounded outcome category, and timestamps are stored.

Work is demand-driven: one explicit worker cycle runs a bounded number of
runnable tasks and returns. There is no thread, no polling, and no busy loop.

Retries are typed, not guessed. Only budget exhaustion is retryable, because it
means the task did not fail — it ran out of allowance and more work remains. A
blocked, failed, interrupted, or cancelled run is never retried automatically.

On restart, a task recorded as running becomes `interrupted`, since what it
achieved is unknown, and it is not replayed. `interrupted`, `paused`, and
`blocked` remain three different things.

---

## Curiosity

Durable curiosity proposals are disabled by default. To persist them, set:

```text
HYPATIA_CURIOSITY_ENABLED=true
```

The value must be exactly lowercase `true`. Proposals are written to
`research_curiosity_questions.json` beside the research-run store, in a separate
versioned document.

Curiosity reads a research run and reports where our own record is thin:
a contradicted claim, an unresolved claim, a claim resting on a single source,
a question with no accepted sources, a low-trust source, an unassessed source,
or an accepted source nothing cites. A gap says what is missing from the record,
never what is true.

Each gap becomes exactly one question, generated from a fixed template rather
than by a model, so a proposal can only ask about a claim or source the system
already recorded. Ranking is a stated formula: gap severity dominates, recorded
claim confidence breaks ties.

With it set, the desktop's **Review** tab gains the curiosity commands: find
gaps, draft and keep ranked questions, list them, and rule on one. A failed
durable write is reported rather than announced as a stored proposal or a
recorded ruling.

Curiosity never acts. Detecting, previewing, storing, listing, accepting, and
dismissing all leave the run untouched; none of them starts research, drafts a
plan, queues a background task, or spends a network or model operation.
Accepting a question records that a human thinks it worth pursuing — turning it
into work stays a separate, explicit decision.

---

## Reflection

Durable reflection history is disabled by default. To keep it, set:

```text
HYPATIA_REFLECTION_ENABLED=true
```

The value must be exactly lowercase `true`. Reports are written to
`research_reflections.json` beside the research-run store, in a separate
versioned document.

With it set, the desktop's **Review** tab gains reflection: report how a run
went, optionally keeping the account, and list what was kept. If the durable
write fails, the response says so instead of reporting a stored reflection.

Reflection reports how a run went, in this order: what failed, what contradicted
what, which beliefs were revised, what rests on thin evidence, what stayed
uncertain, what effort went unused, what worked, and what to ask next. Problems
come before successes deliberately — a reflection that opens with what went well
is one nobody learns from.

Every finding describes the process, never the subject. "This claim rests on one
source" is a fact about our record; "this claim is false" would be a research
conclusion, and reflection cannot reach one. Producing or storing a report
performs no operation, mutates no run, establishes no evidence, and promotes
nothing.

Where reflection and curiosity ask the same question, reflection reuses
curiosity rather than duplicating it: the thin-record findings come from the gap
detector, and the "what next" section is curiosity's proposals, reported but
never stored.

There is no recursive reflection. Only a research run can be reflected on; a
stored report is not a run, and no intent accepts one. A system that reflects on
its reflections produces endless commentary and no new knowledge.

---

## Failure memory

Remembered lessons are disabled by default. To keep them, set:

```text
HYPATIA_FAILURE_MEMORY_ENABLED=true
```

The value must be exactly lowercase `true`. Lessons are written to
`research_failure_lessons.json` beside the research-run store, in a separate
versioned document.

With it set, the desktop's **Learning** tab gains the lesson half: preview what
a run's record would support, remember it, recall what overlaps a question, and
review everything kept. Without it that half is absent rather than disabled.

A lesson collapses its statement and context to a single line when it is
created. Lessons are listed one per line, and a failure reason is free text, so
a line break inside one would otherwise arrive in the report as an extra entry
carrying a lesson kind of its own choosing. The rule lives on the record rather
than in each renderer, because a rendering convention every composer has to
remember is one a composer eventually forgets.

If that durable write fails, the store request returns `success=false` and says
that the lessons exist only in the current process and may be lost on restart.
The lessons are not erased from memory. Repeating the explicit store request
retries the pending write; there is no background or unbounded retry loop.

Eight kinds of lesson are derived from what a run recorded: a claim named in a
contradiction, a hypothesis we stopped holding, another kind of claim we
revised, an assessment we revised, a source we accepted and then judged weak, a
confidence that moved, a search that returned candidates and accepted none, and
a stage that failed. Only an authored `hypothesis` becomes a failed-hypothesis
lesson; superseded facts, likely claims, speculation, unknowns, and other claim
states are recorded as revised claims.

Every lesson names the persisted records it came from, and one without
provenance is refused at construction and again on load. That rule is the whole
point of the store: an opinion with no provenance outlives the reasoning behind
it and quietly hardens into a belief nobody can audit.

The templates are careful about what they assert. A superseded hypothesis is
recorded as abandoned, not disproved, while another superseded epistemic state
is recorded as a revised claim rather than being mislabeled as a failed
hypothesis. A barren search is a result about that query, not a verdict on the
provider. A lesson records that something did not work here, never that it
cannot work.

An explicit `failure_memory_hypothesis_store` request can also remember the
current appraisal of hypotheses that are already in the durable hypothesis
store for one research run. `weakened` produces a `disproving_evidence` lesson
and `contradicted` produces a `failed_hypothesis` lesson; `open`, `supported`,
and `withdrawn` produce none. This is not an event listener or background
write. Repeating the request is idempotent, and a weakened hypothesis that is
later contradicted can retain both distinct, provenance-backed lessons without
either lesson claiming that the hypothesis is true or false.

Each such lesson quotes the hypothesis in the wording it was written in. An
outcome recorded only as a record ID is unreadable by the time anyone needs it,
and recall matches on shared words, so a lesson made entirely of fixed phrasing
would match every later question containing a word like "evidence". The
quotation is collapsed to one line and shortened before the sentence around it,
so a long or multi-line hypothesis can neither forge report lines nor push the
truth-neutrality disclaimer off the end.

Recall is advisory and stays advisory. Creating a research run surfaces the
remembered lessons whose wording overlaps the new question, and asking for them
directly returns the same thing ranked, bounded, and clearly labelled — it
blocks no plan, refuses no capability, downgrades no claim, and edits no run.
The run is persisted before recall is consulted and advice cannot fail it: a
recall that turned a saved run into a reported failure would be worse than no
recall at all. Relevance needs at least two shared words, because every lesson
shares some vocabulary simply by being a lesson, and advice nobody trusts is
worse than no advice — it teaches people to skip the part worth reading. A system that
stops trying things because something similar failed once has swapped research
for superstition. Matching is deliberately dumb word overlap rather than a model
deciding which past failures apply, because that judgement would be confident
and unauditable in exactly the way this project avoids.

---

## Claim calibration

Calibration compares what a claim asserts against the evidence structure behind
it. It needs no flag, because it writes nothing: the report is derived from
canonical state on every request, so there is no second copy to drift from the
record or be believed by mistake.

It is reachable from the desktop's **Review** tab, and needing no flag is why
that tab exists wherever runs do: reflection and curiosity add their sections
when kept, and calibration is there either way.

The ceilings are stated rules rather than a hidden score:

| Evidence structure | Supports at most |
| --- | --- |
| Contradicted | contradicted, unassessed |
| One source, not assessed | hypothesis, low |
| One source, assessed high | likely, medium |
| Two or more sources, not all assessed | likely, medium |
| Two or more sources, all assessed medium or better | strong evidence, high |

Nothing supports `fact`. No configuration of sources in our own record has ever
been enough to make a claim a fact, so calibration will not pretend otherwise.

A ceiling is not a verdict on truth. Meeting it does not make a claim true and
exceeding it does not make one false — it describes what our record can bear the
weight of. And the asymmetry is deliberate: claiming more than the record can
carry is reported, claiming less is not. Being careful is not an error, and
calibration has no business talking anyone into more confidence.

Calibration never edits a claim. An epistemic state is someone's judgement about
what they are willing to assert, and quietly downgrading it would be overruling
that judgement while presenting the change as bookkeeping.

---

## Source reputation

Reputation aggregates our own assessments by origin, across every run. Like
calibration it needs no flag and writes nothing: it is recomputed from the
assessments on every request, so revising one assessment revises the reputation
and a reputation can never outlive the judgements behind it.

Only authored assessments count. Nothing reads a model's opinion of a source or
infers quality from a URL, and acceptance is not approval — a source is accepted
because someone chose to read it, which says nothing about whether it was any
good.

There is no score. A single number would compress "we assessed three pages from
this host, two low and one high" into something that looks precise, travels
easily, and cannot be argued with. The counts stay separate so the reader can
see the sample they are being asked to generalise from.

Below three assessments the standing is `provisional` and says so. Two bad
experiences is a coincidence, and calling it a reputation would let one unlucky
pair of pages permanently colour how everything from that host is read.

Nothing a reputation says gates anything. A low standing refuses no fetch,
discounts no evidence, pre-assesses no new source, and changes no existing
assessment. Whether a source is worth reading stays a judgement someone makes
while looking at it. Reputation events deliberately carry no origin name, because
a log line pairing a host with a low standing is exactly the artefact that gets
quoted later without its sample size.

---

## Research plan approval

Recording approvals is disabled by default. To keep them, set:

```text
HYPATIA_PLAN_AUTHORIZATION_ENABLED=true
```

The value must be exactly lowercase `true`. Approvals are written to
`research_plan_authorizations.json` beside the research-run store, in a separate
versioned document bounded to 500 records.

With it set, the Research (Advanced) plan area gains an approval section that
uses the plan already on screen. Preview shows exactly what confirming would
record and writes nothing; confirming records that exact approval; listing
reports what has been approved and whether each is still valid.

An approval names the plan by content rather than by identifier. `plan_id` is
the preview someone is looking at and changes every time; `plan_digest` is the
question, the ordered steps, and everything each step declares. Both are shown
together, because approving one plan while believing you approved another is the
failure this whole boundary exists to prevent. Edit the plan after previewing
and confirmation refuses it rather than silently covering the change.

Confirming records permission. It does not exercise it. No research is started,
no source is fetched, no model is called, and nothing is queued — and nothing in
the runtime reads an approval, so no execution can happen because one exists.
Approvals expire, are never renewed, and are not consumed, because there is
still no execution to consume one. An expired approval stays listed for audit
and can never verify as valid.

The model-disclosure decision is recorded on every approval and defaults to
`none`. Being allowed to read something locally is not being allowed to send it
to a model endpoint. Nothing reads that decision yet: it is not wired into LLM
transport.

---

## Hypotheses

Hypotheses are disabled by default. To keep them, set:

```text
HYPATIA_HYPOTHESIS_ENABLED=true
```

The value must be exactly lowercase `true`. They are written to
`research_hypotheses.json` beside the research-run store, in a separate
versioned document.

With it set, the desktop's **Learning** tab gains the hypothesis half: propose
one with its defeater, enter recorded evidence on either side, withdraw, and
review derived standing. The two opt-ins are independent, so a build keeping
one shows only the half it can honour. Remembering hypothesis outcomes into
failure memory needs both, and is offered only where both are kept.

If a proposal, evidence entry, or withdrawal cannot be written durably, the
response returns `success=false`, keeps the updated appraisal in the current
process, and warns that restart may lose the change. Store paths and native
errors are never included in the response.

Every hypothesis must name what would count against it, before any evidence
exists, while it is still cheap to be honest about what would change your mind.
A conjecture that names nothing capable of counting against it is refused: it is
a belief with better manners, and it will survive any amount of evidence because
nothing was ever allowed to threaten it.

Supporting and opposing evidence go in separate lists and are never netted. A
count of three-for and two-against is a real situation someone has to read; a
score of "+1" is that situation destroyed. The same evidence cannot be entered
on both sides, and all evidence must already be recorded in the run.

The status rules are asymmetric on purpose:

| Evidence | Status |
| --- | --- |
| None, or one supporting source | open |
| Two or more supporting sources, but any is unassessed or low trust | open |
| Two or more supporting sources, all actively assessed medium/high, none opposing | supported |
| Opposing only | contradicted |
| Both | weakened |
| Withdrawn | withdrawn |

Any opposing evidence at all moves a hypothesis off the supported track, while
positive support needs more than one independent source and an active authored
trust assessment of at least `medium` for every supporting source. The appraisal
shows trust coverage and the lowest active trust on each side. Superseded
assessments do not count. That asymmetry is the whole reason a discriminating
test is required — softening it would make disconfirmation just another input
to be outvoted.

There is no confirm intent and no status meaning true. Propose, support, oppose,
withdraw, and list are the entire vocabulary. `supported` means corroborated
positive evidence passed the explicit authored-trust boundary and none opposes
it, which is still where most abandoned theories stood right up until the
observation that undid them. A system that could mark something confirmed would
be asked to, and once something is filed as confirmed nobody goes looking for
what would have undone it.

Status is never stored, only derived, so it cannot disagree with the evidence
sitting beside it.

---

## Vulnerability family graph

The weakness taxonomy is disabled by default. To keep it, set:

```text
HYPATIA_VULNERABILITY_GRAPH_ENABLED=true
```

The value must be exactly lowercase `true`. It is written to
`vulnerability_families.json` beside the research-run store, in a separate
versioned document.

With it set, the desktop grows a **Security** tab: record a class, relate two
classes with a required reason, and ask what lies around one. Without it the tab
is absent rather than disabled, on the same rule the Tools tab follows — a form
that accepted weakness classes and forgot them at the next restart would be
worse than no form, because the work would look saved. For the same reason a
failed durable write is reported as a failure and the entry is kept for the
session, rather than being announced as recorded.

The graph answers one defensive question: given a class of weakness, what else
is worth thinking about? The usual mistake in security work is treating one
finding as one problem and missing the four siblings that come from the same
design decision.

Everything it holds is conceptual. A family is a class of weakness — "improper
access control", "server-side request forgery" — never a system. The record has
no field for a target, a host, an affected version, a payload, or a proof of
concept, so none of those can be carried even by someone who wanted to. A schema
that offers nowhere to put an exploit is a better guarantee than a rule asking
people not to, and the tests assert that shape directly.

Edges are authored and must say why they hold. Nothing infers a relationship
from similar names or co-occurrence: a graph that grows itself fills with
plausible connections nobody checked and then gets trusted anyway. An
unexplained edge is one nobody can evaluate or argue with later, so the
reasoning is required at the cheapest moment to demand it.

`specializes` builds the taxonomy and is kept acyclic. `enables` is directional
and is only ever followed forwards, because reading it backwards silently turns
"this can lead to that" into a different and often wrong claim.
`shares_root_cause`, `shares_mitigation`, and `related_to` are symmetric.

Traversal is bounded in depth and count. An unbounded neighbourhood query on a
well-connected taxonomy returns everything and means nothing.

---

## The security agent

The security agent audits Hypatia, and only Hypatia. It needs no flag because it
writes nothing: the report is derived from persisted state on every request.

There is no scan intent, no probe intent, no target parameter, and no field
anywhere in the component for someone else's system. An agent that reached
outward would need authorisation this software has no way to establish, so it
does not have the vocabulary to try. The audit opens no socket, and a test
asserts that by making every socket call raise.

The checks cover what the domain types do *not* already guarantee. `ResearchRun`
refuses evidence citing a missing source and claims citing missing evidence at
construction, so re-checking those here would be theatre that inflates the count
of things audited. What no type checks is the shape of a persisted source URL,
its content type, whether its timestamps are ordered, or whether the same page
was accepted twice:

| Check | Severity |
| --- | --- |
| Source claims instruction authority | high |
| Source lost its untrusted-data label | high |
| Source names a loopback or private address | high |
| Source URL carries embedded credentials | high |
| Source not obtained over HTTPS | medium |
| The same URL accepted more than once | medium |
| Stored content type the fetch boundary rejects | low |
| Fetched after it was added | low |

The duplicate-URL check matters more than it looks. Calibration and hypothesis
appraisal now collapse near-certain equivalent URLs to one resource before
counting corroboration, but the duplicate persisted records remain visible to
the audit because they still signal ingestion quality and provenance debt.

The address check is deliberately literal rather than resolved. Re-resolving a
hostname at audit time would be a network call the audit has no authorisation to
make, and a DNS answer today says nothing about the answer when the source was
fetched — the resolution that mattered already happened at the fetch boundary,
where it was pinned.

Every report states what it examined alongside what it found, because "no
findings" over nothing examined and "no findings" over four hundred sources are
very different sentences. A clean report says explicitly that these specific
properties held in the data just now, not that the system is safe.

Nothing is repaired automatically. A finding says what is wrong; deciding what to
do about a source already accepted, cited, and reasoned from is a judgement with
consequences the auditor cannot see.

---

## Ordinary chat never performs research

Hypatia can chat, and Hypatia can research. They are different subsystems, and
ordinary chat is not allowed to sound like the other one.

When a plain chat message explicitly asks for something only research can
supply — the day's news, current events, recent papers, academic sources,
"search the internet", or "cite your sources" — the message does not reach the
language model at all. Hypatia answers deterministically instead: live research
was not performed, no network was reached, no candidate was discovered, no
source was accepted, no evidence was recorded, and here are the canonical
counts. It then points at the explicit research workflow, where each step is
authored and authorized separately.

The detector is a fixed phrase table, not a model and not a score. It grants
nothing: it cannot create a plan, authorize a capability, accept a source, or
spend a network operation. Its only possible effect is to make Hypatia describe
what it did not do, so an over-eager match costs a disclaimer rather than an
action.

Asking what evidence Hypatia collected is answered from persisted research state
and nothing else. Runs, discovered candidates, accepted sources, evidence
records, assessments, claims, and contradictions are reported as separate
counts, because a discovery is not an acceptance, an acceptance is not evidence,
and evidence is not a verified claim.

A system prompt cannot make a model honest, so a second, deterministic guard
runs after generation. If a reply claims research in the first person — "I
researched", "my sources show", "arastirdim" — it is annotated with a bounded
correction naming the canonical counts and stating that anything it called a
source is model output. The model text is never deleted: you should see both the
claim and the correction.

---

## Choosing a local model

Hypatia depends on no particular provider or model. Anything speaking the
OpenAI-compatible chat API works, and the model is configuration, never
architecture.

For local development the practical constraint is latency, not quality. On a
mid-range machine a 4B reasoning model can take around twenty seconds for a
trivial arithmetic question, and a full Hypatia turn — which also builds memory
context and runs extraction — noticeably longer.

A fast development profile:

```text
HYPATIA_LLM_MODEL=qwen3:1.7b
```

An even lighter fallback when that is still slow:

```text
HYPATIA_LLM_MODEL=gemma3:1b
```

A higher-quality profile for real work:

```text
HYPATIA_LLM_MODEL=qwen3:8b
```

Set the model deliberately; Hypatia does not change a configured model on your
behalf. Smaller models mix languages, over-explain, and drift from the newest
message more often. That is a model limitation, not something the runtime can
promise away — the guarantees Hypatia does make, about never claiming research
it did not perform, hold regardless of which model is configured.

Conversation history is bounded by default, at twelve turns. With a small
context window an unbounded transcript pushes the newest message toward the
truncation edge, which is how a model ends up answering the previous question.
To change it:

```text
HYPATIA_LLM_HISTORY_MAX_TURNS=24
```

The literal `unbounded` restores unlimited history.

---

## What a research fetch identifies as

Research fetches send a descriptive agent string naming the product and version
and nothing else — no browser markers, no tracking, no machine or user identity.

Some sites refuse non-browser clients that do not name a contact, and that
refusal is legitimate. The operator can append their own:

```text
HYPATIA_RESEARCH_USER_AGENT_CONTACT=https://example.org/your-project
```

Hypatia will not invent a contact on your behalf, and the override cannot
impersonate a browser: a value containing a browser marker is refused, as are
overlong values and anything carrying a line break. A 403 stays a 403. Dressing
up as Chrome to get past one is bypassing an anti-bot control, and the answer to
a site saying no is to identify honestly or accept the no.

### DOIs and publisher redirects

Crossref discovery works and returns real candidates. Loading one as a source
often does not, and that is usually correct behaviour rather than a bug: DOI
resolution redirects to a publisher, and those redirects frequently land on plain
HTTP or on a PDF, both of which the fetch boundary refuses.

Crossref metadata does carry a `link` field, and it was checked against the live
API rather than assumed. The links returned are plain-HTTP PDF URLs, so exposing
that field would not make DOI loading work under the current safety policy — it
would add surface for no benefit. The honest result stands: the candidate was
discovered, and its content could not be fetched safely.

A direct public HTTPS page travels the whole path. A live run against
`https://portswigger.net/web-security/web-cache-deception` fetched, indexed,
attached to the run, and recorded evidence, ending at one accepted source.

---

## Manual diagnostics

Two developer-only checks live under `tools/diagnostics/`. Neither is part of
the runtime, neither adds a dependency, and both default to temporary data.

### Durable memory

```bash
python tools/diagnostics/durable_memory_check.py
```

Runs three stages that do not prove the same thing. The first teaches a fact.
The second restarts the runtime and asks again in the same session — a weak
observation, because that session's transcript still contains the teaching turn
and the model can read the answer straight out of it. The third asks in a
session created empty, where the transcript is provably zero messages, so
persisted learned memory is the only channel left. Only the third result is
evidence of durable memory, and the report labels them accordingly.

Pass `--real` to use the actual desktop memory file instead of a temporary one.

### Research pipeline

```bash
python tools/diagnostics/research_pipeline_check.py "your question"
```

Walks the real pipeline and reports each stage separately, because each is a
different claim: a network request is not a discovery, a discovery is not an
acceptance, an acceptance is not evidence, and evidence is not a verified claim.

Nothing is promoted automatically. With no flags nothing touches the network.
`--discover` performs one real discovery request. `--accept N` selects that
candidate, or `--url` names a source directly. `--evidence` records one evidence
record from the accepted source. Assessments and claims are never produced by
the diagnostic at all; they require authored steps.

Two things worth knowing before running it against real sources. Crossref
candidates are DOI URLs, and publisher redirects are frequently plain HTTP, so
the fetch is refused at the HTTPS boundary — that refusal is the boundary
working, not a failure of the run. And some sites, Wikipedia among them, reject
Hypatia's user agent with HTTP 403; the fetch fails honestly rather than
retrying under a disguise.

The following optional settings control which learned memories are supplied to
the LLM as additional context:

```text
HYPATIA_LEARNED_MEMORY_CONTEXT_LIMIT=<non-negative integer>
HYPATIA_LEARNED_MEMORY_SELECTOR=keyword|ranked|none
HYPATIA_RANKED_LEARNED_MEMORY_SELECTOR_LIMIT=<non-negative integer>
```

`HYPATIA_LEARNED_MEMORY_CONTEXT_LIMIT` limits the final learned-memory context.

With no selector configured, Hypatia defaults to the deterministic `ranked`
selector bounded to 8 learned memories. Ordinary chat therefore supplies only
memories whose keys or values share a token with the current user message, and
never more than 8 of them. `HYPATIA_RANKED_LEARNED_MEMORY_SELECTOR_LIMIT`
overrides that bound in the default case as well.

`keyword` selects matching memories deterministically; `ranked` orders relevant
memories by deterministic keyword relevance. The ranked selector limit is
applied first, then the final context limit is applied. A ranked limit of `0`
therefore selects no learned memories. The ranked selector limit is ignored when
`HYPATIA_LEARNED_MEMORY_SELECTOR=keyword`.

`none` disables request-specific selection and restores the earlier behavior of
supplying every current learned memory in its existing order. That path is
unbounded unless `HYPATIA_LEARNED_MEMORY_CONTEXT_LIMIT` is also set, so it is no
longer the default.

---

## Semantic memory in ordinary chat

Semantic retrieval during ordinary conversation is opt-in and off by default:

```text
HYPATIA_CHAT_SEMANTIC_MEMORY_ENABLED=true
```

It has no effect unless the semantic-memory runtime is also enabled through
`HYPATIA_SEMANTIC_MEMORY_ENABLED=true`. With the flag absent, ordinary chat is
byte-for-byte the deterministic bounded ranked-keyword path described above and
issues no embedding call.

When enabled, one user turn performs at most one semantic query against the
already built index. Hypatia does not build a second index, store, or cache, and
never starts an index rebuild from the conversation path. Candidates are fused
with the deterministic keyword selection through the existing
`HybridSemanticMemoryRanker`, deduplicated by learned-memory identity, and
bounded by `HYPATIA_LEARNED_MEMORY_CONTEXT_LIMIT` or 8 when that is unset.

Only the current value for a learned-memory key can enter the context. A
semantic hit on a superseded record is rejected, so a correction is never
resurrected.

If the semantic runtime is absent, rebuilding, stopped, or its embedding
provider fails, Hypatia falls back to the deterministic bounded path and the
conversation still succeeds. A failed query emits one bounded
`brain.chat_semantic_memory.query_failed` event carrying only the request ID and
the cause class name. Explicit lexical recall and explicit semantic recall are
unchanged.

All numeric learned-memory limits must be non-negative integers. Invalid values
or a selector value other than the exact lowercase `keyword`, `ranked`, or
`none` cause startup configuration to fail clearly instead of silently changing
context.

The semantic-memory index is currently a tested, in-memory building block. An
explicit Ollama `/api/embed` adapter is available for a local Ollama service,
but Hypatia does not activate it automatically unless its opt-in settings are
set. It does not download a model, persist vectors, or change the response path
except through the explicit semantic-recall command documented below. The
embedding transport rejects HTTP redirects, so an opted-in request remains at
its validated local endpoint. It reads at most 1 MiB before parsing an
embedding response. See the
[Architecture Audit v0.2](docs/Architecture/Architecture_Audit_v0.2.md) for
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
