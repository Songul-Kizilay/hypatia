# Research

## Status

Partially implemented: explicit public-HTTPS source acquisition and local
knowledge indexing are available. Source discovery, multi-source synthesis,
evidence ranking, contradiction detection, and research-run persistence remain
planned.

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
- Acquisition does not invoke an LLM, write conversation memory, persist a
  research run, or create graph relations automatically.

## Next increment

Define a replaceable source-discovery provider and a persisted research-run
model before adding synthesis. A run must keep the original question, source
queries, accepted/rejected sources, evidence records, failures, and completion
state so later summaries remain auditable.

## Known boundary

The current standard-library fetcher validates DNS immediately before each
request and redirect but does not yet pin the validated address to the TLS
connection. A hostile domain capable of DNS rebinding remains a residual risk;
address pinning is required before this boundary is exposed to autonomous or
unattended crawling.
