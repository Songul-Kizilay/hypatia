# Research

## Status

Partially implemented: explicit public-HTTPS source acquisition, local
knowledge indexing, persistent research-run audit records, and a replaceable
source-discovery provider contract are available. User-selected evidence and
bounded candidate metadata are persistent. The packaged process-environment
runtime includes an explicit Crossref scholarly-metadata provider. An exact
persisted candidate can be previewed, confirmed, revalidated, and loaded through
the existing guarded HTTPS boundary. An accepted source also has a read-only
manual-assessment view and an append-only user-authored assessment record based
only on persisted provenance and explicitly recorded evidence. The manual
multi-source comparison also supports append-only user-authored notes with
explicit evidence and current-assessment references. Automatic evidence
extraction, multi-source synthesis, evidence ranking, and contradiction
detection remain planned.

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
- An explicitly injected discovery provider can receive the selected
  collecting run's question and return at most five ordered candidate records.
  Each candidate contains a credential-free HTTPS URL, bounded title, and
  bounded optional snippet. Discovery does not call the source fetcher, accept
  a candidate, index page content, or mark it as evidence.
- Each successful discovery, including an empty result, is atomically stored
  with a unique ID, exact query, bounded provider identity, ordered candidates,
  and timezone-aware timestamp. Closed and unknown runs stop before provider
  access. Provider failures retain only a generic safe run-failure record; a
  failed discovery snapshot leaves the prior run unchanged.
- Candidate acceptance begins with a read-only decision bound to one exact run,
  discovery ID, and persisted URL. It performs no fetch, indexing, LLM, graph,
  or memory operation. A separate confirmed request repeats the validation and
  only then delegates to the existing public-HTTPS loader and audit rollback.
  Unknown, unlisted, stale, and closed-run selections stop before the network.
- The standard process-environment runtime uses Crossref REST v1 for this
  explicit discovery action. Its fixed `api.crossref.org` HTTPS endpoint and
  redirects stay same-origin, system proxies are disabled, JSON responses are
  limited to 500 KB and ten seconds, and only DOI/title/venue/year metadata is
  transformed into candidates. No authentication secret or document content
  is sent or requested. Set
  `HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER=disabled` to remove this network
  capability from a process.
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
- One accepted source can be selected by exact run and document ID for a
  read-only assessment preview. The manager filters the run's persisted
  evidence and authored assessments to that source and reports honestly when
  no evidence exists. The preview reads no live source content, chooses no
  evidence, assigns no quality or credibility score, and remains available
  after a run reaches a terminal state.
- A collecting run can preview and then separately record one user-authored
  assessment. The user must provide the exact evidence IDs; every record is
  revalidated against the selected accepted source before an atomic append.
  Assessment text is bounded to 2,000 characters and no score or conclusion is
  generated by Hypatia.
- The same flow accepts an optional predecessor assessment ID. A correction is
  appended only when the predecessor belongs to the same run and source and has
  no existing successor. History remains ordered and immutable while the view
  labels current and superseded records.
- Schema v6 reads v1-v5 run snapshots with later collections absent and empty,
  v4 assessments carrying no supersession link, and v1-v5 snapshots carrying no
  comparison notes. A legacy snapshot is upgraded only on a later successful
  atomic save.
- A collecting run may be previewed and then explicitly closed as `completed`,
  `failed`, or `cancelled`. Completion requires at least one accepted source
  and evidence record; failure requires at least one failure record;
  cancellation may close an empty run. The
  update revalidates current state and persists before publishing the terminal
  status.
- Terminal runs are immutable and cannot be reopened, moved to another terminal
  status, or receive sources, evidence, assessments, or failures. A source request for a
  terminal run is rejected before network acquisition.
- If source indexing succeeds but the run snapshot cannot be saved, the newly
  indexed unlinked document is removed before a controlled failure is returned.
  Persistent failure reasons do not retain a rejected URL.
- Acquisition, discovery, and run management do not invoke an LLM, write
  conversation memory, crawl links, accept candidates unattended, or create
  graph relations automatically.
- A read-only manual comparison preview accepts two to five unique, explicitly
  ordered source document IDs already accepted into one run. Each column shows
  persisted provenance, that source's user-selected evidence, and only current
  user-authored assessments. The view works for collecting and terminal runs,
  performs no write or live provider work, and produces no verdict, trust
  score, or automatic evidence selection. It bounds each source column to 20
  evidence records and 10 current assessments and reports the full counts when
  additional persisted records are omitted from the display.
- A collecting run can preview and separately append one bounded, user-authored
  comparison note for the exact selected-source order. The user must cite
  persisted evidence and current assessment IDs covering every selected source;
  each assessment's own evidence must also be cited. Final recording revalidates
  all references and atomically replaces the run snapshot. The comparison view
  reads up to 20 matching notes after restart and reports the complete count.
  No provider, fetcher, LLM, memory, graph, or automatic scoring path is used.
- A completed, failed, or cancelled run can be rendered as a deterministic
  Markdown export preview from persisted state only. It includes accepted
  provenance, evidence, authored assessment history, comparison notes, and safe
  failures. The desktop view is bounded to 24,000 source characters while
  exposing the full length and full-content SHA-256. Remote and authored text is
  escaped as literal block-quoted data; no path is accepted and no file is
  written during preview.
- A separately confirmed save carries the preview's exact run ID, snapshot
  update time, full-content SHA-256, and explicit absolute `.md` destination
  back through Brain. The manager re-renders persisted state under its lock,
  rejects stale identities and collecting runs, writes complete UTF-8 bytes in
  the selected directory, and atomically publishes only when the destination
  does not already exist. No research record is changed.

## Next increment

Audit the completed preview-and-save workflow for a separately scoped,
read-only verification action that can compare a selected exported document
with a terminal run's current deterministic fingerprint without importing or
changing either record. Discovery and selection remain separate from fetching
and may not become unattended crawling.

## Known boundary

The current standard-library fetcher validates DNS immediately before each
request and redirect but does not yet pin the validated address to the TLS
connection. A hostile domain capable of DNS rebinding remains a residual risk;
address pinning is required before this boundary is exposed to autonomous or
unattended crawling.
