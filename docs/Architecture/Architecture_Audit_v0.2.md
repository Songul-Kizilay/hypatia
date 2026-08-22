# Hypatia Architecture Audit v0.2

**Audit date:** 2026-08-22  
**Repository baseline:** `main` at `b342286` / runtime `v0.3.110`  
**Authority:** Current tracked source, tests, runtime configuration, and CI
results take precedence over vision and roadmap documents.

## Executive Decision

Hypatia is a working, local-first Python application, not an empty architecture
prototype. Its present shape is a **single-process modular monolith** with two
thin entry adapters (terminal and Tkinter), deterministic request routing,
local validated persistence, optional local or OpenAI-compatible model access,
and an explicit user-directed research workflow.

The runtime is healthy at this checkpoint:

- 1,510 automated tests pass locally.
- Black, Ruff, and MyPy pass for all 331 Python source and test files.
- Windows and Linux GitHub workflows test, package, launch, and smoke-check the
  desktop application successfully at the audited commit.
- The default runtime source uses only Python's standard library and local
  packages. PyInstaller is the separately pinned desktop build dependency.

There is no release blocker in the audited baseline. The dominant development
risk is **responsibility concentration**, especially in the 4,631-line
`TkinterDesktopWindow` and 3,243-line `CognitiveEngine`. The next development
slice should therefore extract a tested, immutable Research workspace read
model from Tkinter before adding another broad research capability.

## Audit Scope and Method

This checkpoint inspected:

- tracked repository and package structure;
- terminal and desktop entry points;
- Bootstrap composition and dependency registration;
- Brain/CognitiveEngine routing;
- session, memory, knowledge, research, provider, and persistence boundaries;
- test organization and current local quality gates;
- Windows/Linux CI and packaging workflows;
- project-status, roadmap, release, and historical tag terminology.

This audit does not treat a directory name, `.gitkeep`, roadmap item, or target
architecture document as proof of an implemented capability.

## Delivery Terminology

Three naming systems coexist and must remain visibly separate:

| Label | Meaning at this checkpoint |
| --- | --- |
| Runtime release | `v0.3.110`, the current executable and packaged baseline |
| Historical sprint | A bounded engineering increment, such as Sprint 4.16.50 |
| Vision roadmap | Long-term product horizons under `docs/Roadmap/`; not executable-version claims |

The repository also contains a historical `v1.0.0` **prerelease** named
"Architecture Foundation" from 2026-08-03. It points to the architecture and
documentation foundation, not to a newer executable product than `v0.3.110`.
This is historically valid but easy to misread; current implementation claims
must use `pyproject.toml`, `PROJECT_STATUS.md`, the changelog, source, and tests.

## Repository Inventory

### Tracked implementation footprint

| Area | Tracked Python files | Purpose |
| --- | ---: | --- |
| `brain` | 7 | Request/response boundary and deterministic normalization |
| `cognition` | 3 | Application orchestration and LLM history building |
| `core` | 18 | Application lifecycle, configuration, logging, limits, exceptions, composition |
| `desktop` | 5 | Tkinter window, controller, data paths, presentation enums |
| `eventbus` | 3 | In-process lifecycle publication/subscription |
| `knowledge` | 19 | Local documents, chunks, lexical index, citations, graph, relation persistence |
| `llm` | 10 | Provider contract, OpenAI-compatible transport, endpoint policy, activation |
| `memory` | 38 | Persistent memory, learned-memory selection, embeddings, semantic index/cache |
| `planner` | 5 | Deterministic bounded plan construction |
| `research` | 51 | Source discovery/fetching, runs, evidence, assessments, claims, export, stores |
| `response` | 2 | Structured user response composition |
| `session` | 23 | Persistent session lifecycle and guarded operations |
| Source roots | 2 | Terminal and desktop launch entry points |
| **Total** | **186** | Active Python runtime source |

The repository has 287 tracked entries beneath `src` because it also preserves
future package directories and non-Python scaffolding. Only the 186 Python
files above are counted as executable source.

### Scaffold and target-architecture areas

Several top-level areas contain only `.gitkeep` placeholders or target
documentation. Examples include `analytics`, `cli`, `cloud`, `digital_twin`,
`extensions`, `firmware`, `marketplace`, `observability`, and `simulator`.
The `apps` tree currently contains desktop/mobile/robot/VR/watch placeholders;
the actual desktop entry point remains `src/desktop_main.py`.

These directories are useful reservations for the long-term vision, but they
must not appear in current capability lists without source-backed runtime code.

## Technology Baseline

| Concern | Current technology |
| --- | --- |
| Language | Python 3.14+ |
| Application model | Single process, modular monolith |
| Desktop UI | Tkinter/ttk |
| Terminal UI | Standard input/output loop |
| Local persistence | Versioned JSON snapshots with atomic file replacement |
| In-memory retrieval | Case-insensitive lexical search and optional semantic index |
| Embeddings | Optional Ollama `/api/embed` adapter |
| Chat models | Optional OpenAI-compatible chat-completions endpoint, including loopback Ollama |
| Research discovery | Explicit bounded Crossref REST adapter |
| Network transport | Standard-library HTTP/TLS/DNS primitives with endpoint and size policies |
| Build | PyInstaller 6.22.2 onedir packages |
| CI | GitHub Actions on Windows Server 2025 and Ubuntu 24.04 |
| Quality | unittest, Black, Ruff, MyPy |

`pyproject.toml` declares no runtime dependency list. The audited source import
graph contains local packages and Python standard-library modules only. The
desktop build requirement is isolated in `requirements-desktop-build.txt`.

## Current Runtime Architecture

```text
Terminal user                         Desktop user
     |                                     |
src/main.py                      src/desktop_main.py
     |                                     |
     +---------------- HypatiaApplication -+
                           |
                       Bootstrap
                           |
                DependencyContainer
                           |
                         Brain
                           |
                   CognitiveEngine
          +---------+------+------+---------+
          |         |             |         |
       Session    Memory       Knowledge   Research
          |         |             |         |
          +---------+------+------+---------+
                           |
                   ResponseComposer
                           |
                 structured BrainResponse

Persistent boundary: validated atomic JSON snapshots
Derived boundary: in-memory knowledge graph/index and optional semantic index
Provider boundary: explicit bounded LLM, embedding, Crossref, or HTTPS actions
```

### Composition and lifecycle

`HypatiaApplication` owns start/stop. `Bootstrap` constructs and registers the
shared EventBus, managers, stores, provider adapters, CognitiveEngine, Brain,
and Planner in a small type-keyed `DependencyContainer`. The desktop adapter
receives the same Brain as the terminal; it does not build a parallel runtime.

### Request flow

`Brain` validates and normalizes an incoming string or `BrainRequest`, then
delegates it to `CognitiveEngine`. The engine selects explicit research,
knowledge, planning, recall, semantic, and session paths before falling back to
deterministic greeting or conversation handling. `ResponseComposer` provides
the structured presentation contract consumed by both adapters.

This boundary is deterministic and testable, but `CognitiveEngine` now contains
many command recognizers, validators, and handlers in one 3,243-line class.

### Persistence and derived state

The durable core consists of five local JSON store families:

- general memory;
- session registry;
- explicit knowledge relations;
- research-run audit snapshots;
- accepted research-source content.

Stores validate schema, collection sizes, identifiers, UTF-8/file bounds, and
duplicate/conflicting records before publication. Writes use temporary files
and atomic replacement. Transactional services restore prior in-memory or
stored state when a later step fails where the operation crosses boundaries.

The knowledge text index and structural graph are primarily derived in-memory
state. Accepted research content can rebuild matching knowledge paragraphs at
startup. The semantic index is optional derived state with a separate bounded
provider-scoped cache; embedding failure does not reverse primary-memory writes.

This design is local-first and failure-conscious, but it deliberately has no
multi-process locking, encryption at rest, cloud synchronization, unattended
repair, or background migration.

### Provider and trust boundaries

Provider activity is explicit rather than ambient:

- normal chat may use a configured OpenAI-compatible endpoint;
- semantic recall uses an opt-in embedding runtime and lexical fallback;
- `ask knowledge` sends bounded cited local context only after an explicit request;
- Crossref discovery records candidates but does not accept their content;
- HTTPS acquisition requires a separate user action and guarded public endpoint;
- optional contradiction suggestions are ephemeral proposals, not stored truth.

Accepted external text is persisted as `external_untrusted_data` with
instruction authority `none`. User-authored information-trust labels do not
grant source text authority. Mutating session, relation, research-lifecycle,
assessment, claim, contradiction, and export flows use explicit preview and/or
confirmation contracts with final revalidation.

### Desktop boundary

The desktop has four top-level tabs: Chat, Knowledge, Research, and Appearance.
Long provider/network actions use one daemon request worker; Tkinter alone
updates widgets. A single-flight guard prevents duplicate command execution,
and cancellation truthfully means discard/cooperate rather than terminate an
arbitrary provider transport.

Research is already a substantial user-directed workspace: runs, candidates,
accepted sources, evidence, authored assessments, claims, reviewed
contradictions, comparisons, lifecycle, deterministic Markdown export, and
verification are present. Recent releases added local filtering, sorting,
coverage inventories, provenance, trust presentation, and safe selected-source
details without adding new provider or persistence paths.

The window currently owns layout, widget state, asynchronous presentation,
research catalog filtering/sorting, selected-run/source projection, label
formatting, handoffs, confirmations, and result rendering in one 4,631-line
class with 185 methods. `DesktopController` is another 1,038 lines. This is the
highest near-term change-coupling area.

## Capability Boundary

### Implemented now

- Local text conversation through optional loopback Ollama or another compliant endpoint.
- Persistent sessions, conversation history, rename, guarded deletion, and targeted search/views.
- Persistent structured memory, learned-memory extraction/selection/correction, TTL, and explicit recall.
- Optional bounded semantic memory index/cache and explicit semantic recall with lexical fallback.
- Local `.txt`/`.md` knowledge loading, lexical search, citations, graph views, and explicit relations.
- Explicit bounded local-RAG questions over cited local knowledge.
- Explicit Crossref discovery and public HTTPS source acquisition.
- Persistent research runs with provenance, evidence, authored analysis, reviewed contradictions, comparison notes, lifecycle, export, and export verification.
- Windows and Linux desktop packages with user-writable local data paths.
- Eye-comfort, light, and high-contrast themes plus bounded text sizing.

### Intentionally not implemented

- Automatic semantic or RAG augmentation of ordinary messages.
- General unattended web discovery, automatic source acceptance, evidence ranking, or truth decisions.
- Multi-source autonomous planning/synthesis or background contradiction persistence.
- Agent execution, tool gateway, browser/OS control, voice, vision, robotics, or smart-home control.
- Cloud sync, encryption at rest, multi-process persistence locking, automatic repair, or unattended migration.

## Quality and Delivery Evidence

### Local verification on 2026-08-22

| Gate | Result |
| --- | --- |
| Package-aware unittest discovery | 1,510 passed in 13.905 seconds |
| Black check | Passed; 331 files unchanged |
| Ruff | Passed |
| MyPy | Passed; 331 source files checked |
| Working-tree baseline | Clean before this documentation branch |

The test tree contains 145 tracked Python files organized mostly beside their
runtime areas: research (30), memory (30), session (17), knowledge (15), LLM
(11), cognition (6), desktop (5), core/integration (4 each), brain (3), and
smaller planner/response/root suites. The named `e2e`, `performance`,
`security`, and generic `unit` directories currently contain package
placeholders rather than executable test modules. This does not invalidate the
1,510 behavioral tests, but dedicated cross-process, performance, and security
campaigns remain absent.

### GitHub delivery gates at `b342286`

- Windows desktop: passed full tests, PyInstaller build, launch smoke test,
  local session-file initialization, and archive publication.
- Linux desktop: passed full tests, PyInstaller build, Xvfb launch smoke test,
  local session-file initialization, and archive publication.
- Dependency Graph: passed.

The CI evidence supports Windows and Linux. The target documentation's macOS
badge is not backed by a macOS workflow or package at this checkpoint.

## Strengths

1. **Repository truth is test-backed.** Core behaviors are protected by a
   large deterministic suite and three static quality gates.
2. **Local-first failure handling is concrete.** Durable state is bounded,
   validated, and atomically replaced; optional provider failures degrade
   rather than corrupt primary data.
3. **Trust and mutation boundaries are explicit.** External text cannot gain
   instruction authority, and important writes are previewed/revalidated.
4. **Provider interfaces are replaceable.** Chat, embeddings, discovery,
   fetching, and contradiction proposal are behind narrow contracts.
5. **Cross-platform delivery is real.** Windows and Linux packages are built
   and launched in CI, not merely listed as roadmap targets.
6. **Research artifacts are auditable.** Sources, evidence, authored records,
   immutable history, hashes, and exports preserve provenance instead of
   presenting generated conclusions as facts.

## Risks and Technical Debt

| Priority | Finding | Consequence | Required response |
| --- | --- | --- | --- |
| High | `TkinterDesktopWindow` has 4,631 lines and 185 methods | UI changes have a growing regression surface and mix view state with formatting/projection logic | Extract pure immutable Research read/projection models incrementally |
| High | `CognitiveEngine` has 3,243 lines | Command routing and domain orchestration are becoming one change hotspot | After desktop extraction, move one domain command family at a time behind tested application services |
| Medium | Runtime, historical sprint, roadmap, and old `v1.0.0` architecture labels coexist | Users and contributors can mistake vision or architecture completion for executable product maturity | Keep terminology block in audits/status and avoid unqualified architecture/version badges |
| Medium | Placeholder-heavy repository structure resembles implemented subsystems | Directory presence can create an architecture mirage | Mark scaffolds explicitly and add runtime code only with a bounded accepted slice |
| Medium | Dedicated e2e/performance/security directories have no executable suites | Cross-process, load, and adversarial guarantees are less directly measured | Add focused campaigns when a specific boundary needs them; do not create empty metric theater |
| Medium | Persistence is single-process and plaintext | Concurrent writers or device compromise exceed the current safety model | Keep the limitation explicit; design locking/encryption as separate migrations, not incidental patches |
| Medium | Python 3.14 is a strict floor | Library and platform availability is narrower | Retain while the zero-runtime-dependency strategy and both packaging workflows remain healthy; reassess before adding dependencies |
| Low | macOS appears in target documentation without CI evidence | Platform claims can outrun delivery proof | Label macOS as unverified/planned until a real build-and-smoke workflow exists |

No finding justifies a broad rewrite. The safe response is extraction through
existing contracts with focused regression tests.

## Architecture Decision: Next Broader Slice

### Selected: Research Workspace Read Model v0.1

Create one immutable, Tkinter-independent presentation boundary for the
already loaded research catalog and selected run/source.

Initial scope:

1. Move pure run filtering, status filtering, sorting, catalog counts, progress,
   workflow snapshot, and coverage calculations out of `TkinterDesktopWindow`.
2. Move canonical selected-source summary/details projection into the same
   read-only boundary or a narrowly paired source projection.
3. Return immutable presentation values; do not expose widgets, managers,
   Brain, providers, paths, or mutable collections.
4. Preserve every visible string, deterministic tie-break, bound, stale-state
   refusal, and current command/field binding.
5. Add focused model tests before switching Tkinter delegation, then run the
   full suite and both package workflows.

Explicit exclusions:

- no new user-facing feature;
- no persistence, schema, provider, LLM, network, or Brain change;
- no automatic analysis, scoring, recommendation, synthesis, or truth decision;
- no redesign of the entire desktop application;
- no Linux-specific side project—the existing shared adapter remains the target.

Acceptance criteria:

- the extracted model is usable without importing or creating Tkinter;
- current Research presentation behavior and exact safety bounds remain stable;
- `TkinterDesktopWindow` loses a meaningful coherent responsibility;
- focused tests cover empty, invalid, hidden, foreign, superseded, duplicate,
  tie, overlong-filter, and deterministic-order cases;
- full tests, Black, Ruff, MyPy, Windows CI, and Linux CI pass.

### Sequenced follow-on work

1. **Research Workspace Read Model v0.1** — selected above.
2. **Research application-service extraction** — move one cohesive research
   command family from `CognitiveEngine`, preserving Brain request/response contracts.
3. **User-authored research plan** — only after those boundaries are stable;
   explicit steps and source selection, no autonomous execution.
4. **Cited synthesis preview** — optional local-model preview over persisted
   user-selected evidence, never automatic truth or unattended persistence.

## Final Assessment

Hypatia has passed the "is there a real product core?" threshold. It can run,
remember, organize local knowledge, perform guarded research, preserve audit
history, converse through a local model, and ship tested desktop packages on
Windows and Linux. Its next maturity step is not another isolated button or an
agent framework. It is to preserve these working contracts while separating
the two largest orchestration/presentation hotspots into smaller, pure,
independently tested components.
