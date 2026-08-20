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
  local data; selected-run acceptance writes it transactionally before
  provenance publication, while startup restoration is not yet enabled;
- semantic embeddings are opt-in and restricted to the local Ollama endpoint
  policy enforced at bootstrap.

The current full-repository security baseline is recorded in the Codex Security
scan completed for v0.3 planning. Before Hypatia gains a networked UI, plugins,
remote storage, or multi-user operation, this document must grow into a complete
threat model covering authentication, authorization, data sharing, retention,
audit logging, incident response, and vulnerability disclosure handling.
