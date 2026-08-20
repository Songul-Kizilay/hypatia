# Research

## Status

Partially implemented: explicit public-HTTPS source acquisition, local
knowledge indexing, and persistent research-run audit records are available.
User-selected evidence records are also persistent. Source discovery,
automatic evidence extraction, multi-source synthesis, evidence ranking, and
contradiction detection remain planned.

## Purpose

Help collect, assess, summarize, and connect sources while distinguishing evidence from inference.

## Implemented boundary

- The user explicitly supplies one HTTPS URL; Hypatia does not crawl or search
  automatically.
- The URL cannot contain credentials or use a nonstandard port. Every DNS
  answer and redirect destination must remain on public internet addresses.
- Only HTML, XHTML, plain text, and Markdown are accepted, with a 1 MiB response
  limit and a ten-second timeout. The default fetch path does not inherit system
  proxy settings, so proxy-side DNS resolution cannot bypass the local address
  policy.
- HTML is converted to readable block text without executing scripts or styles.
- Final URL, title, content type, fetch time, and stable identity are preserved
  when the source enters the existing in-memory knowledge index.
- The user can create a persistent research run for one question, list runs,
  and attach an accepted source through an explicit run ID. The versioned JSON
  snapshot keeps collecting status, accepted source provenance, safe failure
  reasons, and timezone-aware creation/update times.
- The audit snapshot does not duplicate downloaded page content. Knowledge
  chunks remain in memory and therefore are not reconstructed from a run after
  restart.
- The user can select one currently indexed paragraph from a source attached
  to the run and add a required note. The evidence record stores the source and
  chunk IDs, paragraph position, at most 1,000 excerpt characters, whether the
  excerpt was truncated, a SHA-256 fingerprint of the complete paragraph, and
  its recording time. It does not infer whether the evidence proves a claim.
- Stored evidence can be viewed after restart without live page content. New
  evidence still requires its source paragraph to be loaded in the current
  in-memory knowledge index.
- Schema v2 reads v1 run snapshots as evidence-empty and upgrades them only on
  a later successful atomic save.
- If source indexing succeeds but the run snapshot cannot be saved, the newly
  indexed unlinked document is removed before a controlled failure is returned.
  Persistent failure reasons do not retain a rejected URL.
- Acquisition and run management do not invoke an LLM, write conversation
  memory, crawl links, discover sources, or create graph relations
  automatically.

## Next increment

Add explicit completion-state transitions, then define a replaceable
source-discovery provider before synthesis. Discovery queries,
candidate-source decisions, future claim/evidence links, and later summaries
must remain auditable; no unattended crawling should be enabled at this
boundary.

## Known boundary

The current standard-library fetcher validates DNS immediately before each
request and redirect but does not yet pin the validated address to the TLS
connection. A hostile domain capable of DNS rebinding remains a residual risk;
address pinning is required before this boundary is exposed to autonomous or
unattended crawling.
