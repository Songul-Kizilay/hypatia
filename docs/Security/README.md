# Security Foundation

Hypatia currently runs as a local-first CLI. The initial security boundary is:

- local JSON memory and session snapshots are user-owned runtime data;
- optional LLM API keys remain in the process environment and are not stored in
  project configuration or memory files;
- external OpenAI-compatible LLM endpoints require HTTPS;
- plain HTTP is allowed only for loopback local runtimes (`localhost`,
  `127.0.0.1`, or `::1`);
- authenticated LLM completion requests do not follow HTTP redirects, so a
  bearer token cannot be forwarded to a redirect target;
- explicitly loaded public research pages connect to an exact address from the
  immediately preceding public-DNS validation while TLS still verifies the URL
  hostname and certificate; redirects repeat the same boundary;
- the fixed Crossref metadata endpoint and same-origin redirects share that
  address-pinned TLS boundary without widening explicit discovery into general
  search or page acquisition;
- connection fallback uses only the ordered public addresses from the same DNS
  validation and shares one decreasing timeout across TCP and TLS attempts;
- the accepted-source content store verifies complete UTF-8 byte
  counts and SHA-256 values, enforces bounded snapshots, and atomically replaces
  local data; physical reads consume at most 40,000,000 bytes plus one detection
  byte from the opened descriptor, and writes count exact UTF-8 output without
  retaining a second serialized copy; selected-run acceptance writes it
  transactionally before
  provenance publication, while startup restores at most 20,000 paragraphs only
  after exact run-provenance and stable-identity reconciliation and performs no
  network or persistent write; the explicit restoration-status view reads only
  the immutable startup snapshot and exposes aggregate counts rather than
  content, paths, source metadata, hashes, IDs, or internal errors;
- accepted-source paragraph locators are opaque versioned UUIDs bound to stable
  document identity, paragraph position, and exact-content SHA-256; changed
  text cannot silently inherit the prior locator, and no stored evidence is
  automatically rewritten or migrated;
- evidence integrity audit requests are capped at 20,000 runs, records, and
  indexed chunks and use only loaded in-memory snapshots; output contains
  aggregate matched, missing, and changed counts, with no persistence, network,
  content, path, identifier, hash, mutation, migration, or repair access;
- research-run JSON reads consume at most 64 MiB plus one detection byte before
  decoding; reads and writes reject more than 20,000 aggregate nested list
  entries, while writes count exact UTF-8 bytes and cannot publish a snapshot
  larger than 64 MiB;
- research-run schema v8 persists external-source taint, authored
  information-trust labels as separate fields. External source taint is fixed
  to `external_untrusted_data` and instruction authority is fixed to `none`;
  even a `high` information-trust label grants no instruction, tool, or policy
  authority. It also stores authored claims only with exact persisted evidence
  and ordered accepted-source provenance, categorical epistemic/confidence
  values, and single-successor append-only corrections. Invalid values fail
  closed, and v1-v7 snapshots load with safe defaults and no claims before any
  later atomic rewrite;
- explicit knowledge-relation snapshots are limited to 20,000 ordered records,
  1,024 characters per endpoint ID, and 64 MiB of UTF-8 JSON; opened-descriptor
  reads stop before oversized decoding, and bounded temporary writes preserve
  the prior snapshot on failure;
- session-registry snapshots are limited to 20,000 ordered sessions, 1,024
  characters per session ID, and 64 MiB of UTF-8 JSON; opened-descriptor reads
  stop before oversized decoding, and exact-byte atomic writes preserve the
  prior registry and its default/active-session invariants on failure;
- general-memory snapshots are limited to 20,000 ordered records, 1,024
  characters per ID, 1,000,000 characters per content value, 8 MiB and 100,000
  entries of aggregate metadata, 100,000 tags, 256 characters per tag, and 64
  MiB of UTF-8 JSON; invalid or excessive candidates fail before atomic
  publication and preserve the prior snapshot;
- optional provider-scoped semantic-embedding cache snapshots are limited to
  20,000 ordered entries, 1,024-character provider keys and memory IDs,
  1,000,000-character source values, 16,384 values per embedding, 4,000,000
  aggregate vector values, and 64 MiB of UTF-8 JSON; descriptor-bounded reads
  and exact-byte atomic writes preserve provider isolation and the prior cache
  after invalid, oversized, or failed updates;
- semantic embeddings are limited to 16,384 finite values, and the live
  semantic index is limited to 20,000 entries, 1,024-character memory IDs, and
  4,000,000 aggregate vector values; full builds preflight limits before
  publication, incremental failures preserve the last working index and cache,
  and overflow-safe cosine math cannot emit a non-finite accepted score;
- semantic embedding source text is limited to 1,000,000 characters across
  rebuild, incremental, query, and Ollama-provider paths; outbound Ollama JSON
  is limited to 8 MiB of exact compact UTF-8, and invalid, recursive, or
  oversized payloads fail before a network request is opened;
- cold semantic rebuilds allow 256 cache misses/provider calls by default and
  accept an explicit 0-through-20,000 process setting; all cache results and
  misses are resolved before network work, so an excessive rebuild fails before
  provider access, cache replacement, or runtime publication;
- an initial semantic provider, cache, budget, or rebuild failure degrades only
  the optional semantic runtime; primary Bootstrap remains available, status
  exposes only a generic rebuild diagnostic, and only the exact explicit retry
  command can start another bounded full rebuild;
- every full semantic rebuild has one shared 120-second monotonic deadline by
  default, configurable only to a positive finite value through 3,600 seconds;
  each provider request is capped to the smaller of its request timeout and the
  remaining rebuild duration, and expiry prevents partial cache/index
  publication;
- semantic startup and explicit retry use one daemon single-flight worker;
  queries fall back lexically while it runs, one dirty snapshot can be
  coalesced, a second dirty attempt publishes no stale index, and shutdown
  rejects new work and suppresses in-flight runtime publication. Cancellation
  is observed between bounded provider calls and before derived-cache
  replacement rather than forcefully terminating an active HTTP request;
- incremental semantic maintenance shares that worker, retains at most 20,000
  pending IDs, coalesces repeated record events, rejects superseded embeddings,
  preserves per-record failure diagnostics, and never rolls back or delays an
  already-persisted primary-memory mutation;
- explicit desktop provider and HTTPS actions share one daemon single-flight
  worker; Tkinter alone consumes and renders completions, all command buttons
  are disabled while Brain is active, duplicate keyboard requests are rejected,
  close discards late results, and unexpected exceptions are reduced to a
  generic message without exposing provider or transport detail. An explicit
  cancellation request keeps the single-flight reservation until active
  timeout-bounded I/O returns and then discards its value or error; it does not
  forcefully terminate a thread or provider transport. Research discovery and
  explicit HTTPS source loading also propagate a one-way cancellation signal;
  when observed after network return, no discovery, failure audit, knowledge
  document, accepted-source record, or content snapshot is written;
- explicit local-RAG requests place a code-owned instruction in the system role,
  separate the explicit user question from retrieved text, and mark every
  retrieved excerpt as untrusted data with no instruction authority. That path
  receives no conversation history or tool capability. This is a defense in
  depth boundary, not a complete prompt-injection firewall or a guarantee of
  model compliance;
- semantic embeddings are opt-in and restricted to the local Ollama endpoint
  policy enforced at bootstrap.

- tool invocation is centrally gated. A tool declares its effects, and the
  execution service compares that declaration against the effects the single
  invocation authorized before the implementation is reached. There is no
  ambient grant, no trusted-tool shortcut, and no path to a tool that skips the
  gate. Lifecycle events carry counts, categories, and booleans, never argument
  values or returned values. Only two capabilities are registered — reading a
  clock and counting supplied text — and no module outside the tool layer can
  import it, name the execution service, or construct an invocation.

## Proposed, not implemented

- [Read-only filesystem capability design](Filesystem_Capability_Design.md).
  No filesystem capability, effect, tool, or code exists in the runtime. The
  document records the authorized-root model, measured Windows path behaviour,
  link policy, output bounds, telemetry rules, and the TOCTOU guarantee that
  cannot be made, so that those choices are reviewable before anything can act
  on them.

The current full-repository security baseline is recorded in the Codex Security
scan completed for v0.3 planning. Before Hypatia gains a networked UI, plugins,
remote storage, or multi-user operation, this document must grow into a complete
threat model covering authentication, authorization, data sharing, retention,
audit logging, incident response, and vulnerability disclosure handling.
