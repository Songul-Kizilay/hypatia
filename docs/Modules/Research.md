# Research

## Status

Partially implemented: explicit public-HTTPS source acquisition, local
knowledge indexing, persistent research-run audit records, and a replaceable
source-discovery provider contract are available. User-selected evidence and
bounded candidate metadata are persistent. The packaged process-environment
runtime includes explicit Crossref scholarly-metadata and NVD vulnerability-
record providers. An exact
persisted candidate can be previewed, confirmed, revalidated, and loaded through
the existing guarded HTTPS boundary. An accepted source also has a read-only
manual-assessment view and an append-only user-authored assessment record based
only on persisted provenance and explicitly recorded evidence. The manual
multi-source comparison also supports append-only user-authored notes with
explicit evidence and current-assessment references. Automatic evidence
extraction, multi-source synthesis, evidence ranking, and contradiction
detection remain planned. Explicit evidence-linked authored claims now persist
epistemic states, categorical confidence, and append-only correction history.
The operator can approve both providers for one canonical question as two
ordinary discovery steps and review derived provider-quality reports. The
same-question paired report includes only runs whose two recorded queries
exactly match the run question, keeps both assessment funnels separate, and
produces no winner or routing policy.

## Purpose

Help collect, assess, summarize, and connect sources while distinguishing evidence from inference.

## Implemented boundary

- The user explicitly supplies one HTTPS URL; Hypatia does not crawl or search
  automatically.
- The URL cannot contain credentials or use a nonstandard port. Every DNS
  answer and redirect destination must remain on public internet addresses.
  Each TCP connection uses addresses only from that validation, in order and
  at most once, while TLS continues to authenticate the normalized URL
  hostname and certificate. All attempts share one decreasing connection-time
  budget.
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
  redirects stay same-origin, require public-only DNS answers, and connect to
  an exact address from their own validation while TLS verifies the hostname.
  System proxies are disabled, JSON responses are limited to 500 KB and ten
  seconds, and only DOI/title/venue/year metadata is transformed into
  candidates. No authentication secret or document content is sent or
  requested. Set
  `HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER=disabled` to remove this network
  capability from a process.
- The audit snapshot does not duplicate downloaded page content. A separate
  schema-v1 source-content record/store validates
  exact extracted text against its UTF-8 byte count and SHA-256 plus persisted
  provenance. The JSON store atomically replaces a bounded snapshot of at most
  64 unique records, 32 MB total content, and a 40 MB physical file. Accepted
  content is saved transactionally before run provenance is published. Startup
  reconstructs only records that exactly match accepted run provenance and
  stable document identity, with a 20,000-paragraph aggregate bound.
- Initial indexing for a selected persistent run and startup restoration use
  the same opaque v1 paragraph identity derived from document ID, paragraph
  position, and exact-content SHA-256. New evidence locators therefore remain
  resolvable after restart when the accepted content is unchanged. Temporary
  run-free parsing remains ephemeral, and no persisted schema is changed.
- Bootstrap captures an immutable restoration status after validation. The
  explicit Brain/desktop request reports only ready or unavailable state plus
  restored document and paragraph counts. It does not reread persistence,
  fetch content, invoke an LLM, mutate runtime state, or expose record details.
- A separately requested evidence integrity audit accepts at most 20,000 runs,
  persisted evidence records, and indexed in-memory paragraphs.
  Matching requires document, paragraph position, opaque ID, and complete text
  fingerprint agreement. Missing and changed states are aggregate counts only;
  no content, record identifier, path, hash, or repair action is exposed.
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
- The authored assessment also carries one explicit information-trust label:
  `unassessed`, `low`, `medium`, or `high`. Hypatia never calculates it. Every
  accepted external source retains the fixed taint `external_untrusted_data`
  and instruction authority `none`, so an information-trust label cannot grant
  source text permission to issue instructions or use tools.
- The same flow accepts an optional predecessor assessment ID. A correction is
  appended only when the predecessor belongs to the same run and source and has
  no existing successor. History remains ordered and immutable while the view
  labels current and superseded records.
- A collecting run can preview and separately append one user-authored claim
  that cites one to 20 unique persisted evidence IDs. Its exact ordered source
  IDs are derived from the cited evidence and stored with the record. The user
  selects `fact`, `strong_evidence`, `likely`, `hypothesis`, `speculation`,
  `unknown`, or `contradicted` plus categorical confidence `unassessed`, `low`,
  `medium`, or `high`. No numeric probability or automatic truth decision is
  produced.
- Claim history is read-only for collecting and terminal runs. A correction
  appends an optional predecessor ID and leaves the predecessor immutable; one
  predecessor can have only one successor. Final recording revalidates run
  state, evidence/source provenance, categorical values, and supersession
  before an atomic snapshot replacement.
- Schema v8 reads v1-v7 run snapshots with later collections absent and empty,
  v4 assessments carrying no supersession link, and v1-v5 snapshots carrying no
  comparison notes. V1-v7 snapshots carry no claims. Legacy sources receive the
  fixed external-data taint and no instruction authority; legacy assessments
  receive `unassessed` information trust. A legacy snapshot is upgraded only on
  a later successful atomic save.
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
  provenance, evidence, authored assessment history, evidence-linked claims,
  comparison notes, and safe failures. The desktop view is bounded to 24,000
  source characters while
  exposing the full length and full-content SHA-256. Remote and authored text is
  escaped as literal block-quoted data; no path is accepted and no file is
  written during preview.
- A separately confirmed save carries the preview's exact run ID, snapshot
  update time, full-content SHA-256, and explicit absolute `.md` destination
  back through Brain. The manager re-renders persisted state under its lock,
  rejects stale identities and collecting runs, writes complete UTF-8 bytes in
  the selected directory, and atomically publishes only when the destination
  does not already exist. No research record is changed.
- One explicitly selected existing `.md` file can be verified against the
  current deterministic rendering of a terminal run. The manager streams the
  complete regular file, checks that descriptor and path identity plus size and
  timestamps remain stable, and returns observed/expected byte counts and
  SHA-256 values with an exact match flag. A mismatch does not import or repair
  the file. Unexpected input is bounded to 64 MiB, while an authentic larger
  run export remains eligible up to its exact expected length.
- The research-run JSON snapshot keeps schema v13 and legacy v1-v12 loading while
  limiting the complete UTF-8 file to 64 MiB and all nested list entries to an
  aggregate 20,000 items. Reads stop before oversized JSON decoding; writes
  count exact UTF-8 bytes in a temporary file and publish only a complete
  bounded snapshot through the existing atomic replacement.
- The separate accepted-source content store reads at most 40,000,001 bytes
  from its opened descriptor before decoding and streams exact UTF-8 JSON into
  its temporary file. The existing 64-record, 32,000,000-content-byte,
  fingerprint, rollback, and atomic publication rules remain unchanged.

## Next increment

Add explicit, user-reviewed contradiction relationships between persisted
claims. Any future automated analysis should return evidence-linked proposals,
not silently mutate claims or decide truth.

## Known boundary

The explicit research source fetcher and fixed Crossref discovery adapter share
one multi-address pinned HTTPS boundary. Failed TCP or TLS setup advances only
through the remaining addresses from that same validation within one deadline.
Accepted page content is saved in the separate validated content store when a
source is attached to a run. Startup restores only records that exactly match
accepted run provenance, with a 20,000-paragraph bound and no persistent write
or network call. Invalid content prevents partial restoration; no automatic
repair or quarantine path exists yet. Neither path authorizes autonomous or
unattended crawling.
