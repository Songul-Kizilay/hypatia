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
