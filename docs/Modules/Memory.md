# Memory

## Status

Persistent structured-memory foundation implemented. Advanced user review,
export, provenance governance, and deletion controls remain planned.

## Purpose

Store and retrieve user-approved information with clear provenance, review, export, and deletion controls.

The current foundation provides transactional in-memory lifecycle operations,
schema-v1 local JSON persistence, bounded metadata and tags, deterministic
ordering, duplicate-ID rejection, TTL handling, keyword recall, and opt-in
derived semantic retrieval.

The optional provider-scoped semantic-embedding cache remains separate from
primary memory. Its schema-v1 snapshot has explicit physical-file, entry,
identifier, source-text, vector-dimension, and aggregate-vector bounds. Reads
stop before decoding oversized files; exact-byte atomic writes preserve the
previous file and in-memory cache after invalid or failed updates.

The derived live semantic index separately caps embeddings at 16,384 values,
index populations at 20,000 entries, memory IDs at 1,024 characters, and the
aggregate at 4,000,000 vector values. Full rebuilds preflight these limits;
incremental failures keep the previous index and cache while primary memory
remains committed. Overflow-safe cosine math retains finite deterministic
ranking for every accepted vector.

Semantic source text is capped at 1,000,000 characters before cache or provider
work. Full rebuilds validate all active sources first, incremental updates
validate before changing the index/cache, and excessive direct queries keep the
lexical fallback. The local Ollama transport serializes compact Unicode JSON
through an 8 MiB exact UTF-8 writer and rejects invalid or excessive payloads
before opening a network request.

Cold rebuilds also resolve all provider-scoped cache results before network
work and allow at most 256 provider calls by default. The process environment
can set an explicit ASCII whole-number budget from 0 through 20,000; zero is
cache-only. An excessive miss count fails before provider access, cache
replacement, or runtime publication. A cache-read failure is attempted once
and conservatively makes the rebuild fully uncached, while a valid
foreign-provider snapshot is cached as an isolated empty view.

An initial optional rebuild failure no longer stops the primary application.
The semantic runtime records only a safe rebuild diagnostic, remains attached
for later lifecycle updates, and reports unavailable until a complete index is
published. The exact `semantic recall retry` command is the only full-rebuild
retry path; failure preserves the last complete index when present and never
changes primary memory.

Every full rebuild now also shares one monotonic deadline: 120 seconds by
default and configurable from greater than zero through 3,600 seconds. The
deadline starts before record, source, and cache preflight. Every missing
embedding receives only the remaining duration, further capped by the normal
per-request timeout. Expiry prevents cache replacement and runtime publication,
while a prior complete index remains available.
