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
- explicit knowledge-relation snapshots are limited to 20,000 ordered records,
  1,024 characters per endpoint ID, and 64 MiB of UTF-8 JSON; opened-descriptor
  reads stop before oversized decoding, and bounded temporary writes preserve
  the prior snapshot on failure;
- semantic embeddings are opt-in and restricted to the local Ollama endpoint
  policy enforced at bootstrap.

The current full-repository security baseline is recorded in the Codex Security
scan completed for v0.3 planning. Before Hypatia gains a networked UI, plugins,
remote storage, or multi-user operation, this document must grow into a complete
threat model covering authentication, authorization, data sharing, retention,
audit logging, incident response, and vulnerability disclosure handling.
