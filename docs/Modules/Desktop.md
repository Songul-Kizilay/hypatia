# Desktop Application

## Status

The first local Tkinter shell is implemented for text chat, refreshable session
overview and explicit selection, selected-session details/recent/activity, and
explicit lexical/semantic recall, bounded cited knowledge context, and
semantic-runtime status. It also provides explicit local Markdown/text source
loading, source-catalog/graph views, source-relation controls, and guarded
session rename/delete flows. Chat, Knowledge, Research, and Appearance are
separate tabs so ordinary conversation is not crowded by specialist controls.
Within Research, four ordered workflow tabs separate overview, sources/evidence,
authored analysis, and review/export. Authored analysis uses four smaller tabs
for saved records, comparison, assessment, and claims/contradictions. This is a
presentation-only reparenting of the existing controls: all 59 command bindings
and 41 field bindings remain unchanged, and navigation starts no runtime work.
Sources/evidence, authored analysis, and review/export each show the same
read-only `Current research run` banner with bounded question, status, and exact
ID. It uses only the already selected immutable snapshot; empty or invalid
selection replaces stale context and starts no runtime action.
Each banner also repeats complete source, evidence, and claim counts from that
snapshot. All three labels share one presentation value; empty or invalid
selection clears stale progress without another read or action.
Overview presents one additional `Workflow snapshot` with complete source,
evidence, assessment, comparison-note, claim, and contradiction counts plus the
existing status. It reports records only and does not classify readiness, infer
truth, recommend a conclusion, hide controls, or start an action.
The run selector also has a bounded local filter over the already loaded
immutable catalog. It matches case-insensitive question text, exact status, or
exact ID and reports visible/total counts. No-match or overlong input does not
change the active run, authored fields, or run-bound views; `Clear` restores the
complete loaded catalog without another read.
The same loaded or filtered view has four explicit local sort choices: updated
newest, updated oldest, created newest, and question A-to-Z. The interface shows
the current sort and uses deterministic ascending run-ID ties. Sorting preserves
the immutable catalog, filter membership, active run, and authored fields and
starts no controller, provider, storage, or mutation action.
When filtering hides the active row, `Show active run` restores the complete
locally sorted selector and exact active choice by clearing only the text/status
filters while preserving authored fields. Missing selection, stale catalog
membership, or invalid sort leaves the existing view unchanged and starts no
runtime action.
The catalog also has an explicit All/Collecting/Completed/Failed/Cancelled
status view. It composes with bounded text matching and current sort, reports
visible/total membership, and preserves hidden active and authored state. An
invalid status leaves the prior view untouched and starts no runtime action.
One adjacent read-only catalog summary reports complete All, Collecting,
Completed, Failed, and Cancelled counts from the full immutable loaded tuple.
Filtering and sorting cannot change those totals; an empty catalog replaces
stale values with explicit zeroes and no additional read or action occurs.
`Reset view` restores all three local catalog controls in one action: blank
text, All statuses, and Updated-newest sorting. It re-shows the full tuple and
selects the active row only when that exact ID is loaded. Active identity,
authored fields, and catalog totals remain unchanged, including empty and stale
active states, and no controller or mutation action starts.
Overview adds one read-only evidence-coverage line from the same selected
immutable snapshot. It counts unique accepted source IDs represented by one or
more evidence records and reports the accepted remainder. Repeated evidence is
deduplicated, malformed foreign references cannot inflate counts, no quality or
readiness is inferred, and empty/invalid selections clear stale coverage.
One adjacent assessment-coverage line counts unique accepted source IDs having
at least one current authored assessment and reports the accepted remainder.
Superseded-only history does not count as current, malformed foreign references
cannot inflate membership, and empty/invalid selections clear stale coverage
without a quality, truth, completeness, or readiness inference.
Sources & evidence exposes All sources, Without evidence, and Without current
assessment views over that same snapshot. Current assessment membership excludes
superseded-only history and malformed foreign records. Source order is stable,
visible/total membership is explicit, and one exact active source ID survives a
hidden/no-match view and is restored when All sources returns. Source-bound
evidence/assessment presentation clears while hidden, authored fields remain
intact, and stale/invalid state is refused without another read or action.
One adjacent accepted-source coverage catalog summary reports the complete All,
Without evidence, and Without current assessment totals from that immutable
snapshot. Exact-ID sets deduplicate repeated records, correction history uses
only current assessments, malformed foreign membership is ignored, and facet
changes cannot alter the totals or open another read or action.
`Show active source` verifies the current run ID, run-bound source catalog, and
exact active source ID before restoring All sources and that row. It rehydrates
only source-bound read-only evidence/assessment selectors; authored fields and
catalog totals remain unchanged. Empty, stale, or unknown state is refused
without a controller, persistence, provider, or mutation call.
One adjacent selected-source record summary reports the exact evidence,
assessment-history, and current-assessment counts from the same immutable run.
Superseded assessments remain in history but do not count as current, foreign
records cannot count, and hidden/invalid source presentation clears the summary.
It makes no quality/trust conclusion and opens no runtime or mutation path.
The same wrapped line includes a normalized bounded source title, exact source
document ID, and exact immutable run ID. It presents them only when the complete
source record equals canonical run membership, preventing changed or foreign
provenance from borrowing the selected run's record counts.
It also shows canonical persisted data taint `external_untrusted_data` and
instruction authority `none`. These fields remain separate from user-authored
information trust—even `high` cannot grant command authority—and rendering them
starts no controller, storage, provider, network, or mutation action.
The fourth structured line reports complete Unassessed, Low, Medium, and High
counts for only non-superseded assessments of that exact source. Superseded
records remain in the history count, malformed foreign records do not
contribute, and the distribution is authored-label inventory rather than a
Hypatia-generated verdict.
Overview also renders one bounded metadata line from the selected immutable
run: seconds-level timezone-aware creation/update times and only the aggregate
safe-failure count. It cannot expose a failure stage/reason or retain stale
metadata after empty/invalid selection, and it opens no read or mutation path.
Users can choose a local text size between 10 and 20 points and select Eye
comfort, Light, or High contrast without affecting runtime state. Eye comfort
is the default; it uses softened dark surfaces while preserving explicit focus,
selection, disabled, and read-only states. One explicitly entered public HTTPS
research source can be validated, fetched, and indexed through Brain without
background traffic or conversation-memory writes.
The shell can also create/list persistent research runs and attach that source
to a selected run ID. The `Research content` action reports the accepted-source
content restoration state captured at startup plus aggregate restored document
and paragraph counts. It neither reads persistence again nor exposes content,
paths, source metadata, hashes, IDs, or internal errors.
All explicit provider-backed actions share one daemon single-flight worker. The
status line reports elapsed seconds without claiming a completion percentage.
`Cancel request` discards the eventual presentation while keeping other actions
disabled until active timeout-bounded I/O returns; it does not terminate the
provider call or its worker thread. For Crossref discovery, explicit HTTPS
source loading, and confirmed candidate loading, the same request also carries
a cooperative signal through Brain. If cancellation is observed when the
network call returns, the runtime stops before audit, indexing, or persistence
mutation. Other desktop provider actions remain presentation-only cancellation.
The research panel's `Evidence integrity` action performs a separate bounded
in-memory comparison of recorded evidence and current accepted paragraphs. It
reports only matched, missing, and changed totals and never repairs records.
For a selected collecting run, `Find sources` explicitly queries the bounded
Crossref metadata provider and displays up to five persisted candidates.
`Use selected URL` only copies the chosen DOI URL into the existing source
field. `Preview & load` first renders a read-only decision for the exact run,
discovery, and candidate, then asks for confirmation before a separate request
revalidates and uses the existing guarded loader. Changing the run ID makes old
candidate selections unusable; stale or unlisted choices stop before network
access.
`Research runs` fills a read-only selector from the local persisted catalog.
Labels include the question, current status, and exact ID; creating a run selects
it immediately. A valid selection is preserved across refresh, while an empty
catalog clears it. Switching runs starts no runtime action and clears only stale
source-candidate, contradiction-suggestion, and export-preview presentation
state. A compact line beneath the selector shows status and complete source,
evidence, and claim counts from the same loaded snapshot; it opens no additional
read or provider path. The later workflow tabs repeat the same exact selected
identity and complete source/evidence/claim counts through their shared current-
run banner without another read.
Accepted sources from that snapshot populate a read-only selector labelled with
bounded title text and exact document ID. Selection alone edits nothing. The
explicit assessment handoff replaces only the single-source document field; the
comparison handoff appends the exact ID once without exceeding five entries.
Stale cross-run selections are cleared, and neither handoff calls Brain,
persistence, a provider, the network, or any mutation boundary.
The chosen source also filters persisted evidence from the already loaded run
snapshot. Read-only labels show a bounded one-line excerpt and exact evidence
ID. Separate assessment, claim, and comparison handoffs append only that ID;
same-source/comparison-membership guards, duplicate refusal, and 20/100 limits
run locally. Selecting or handing off evidence performs no Brain, persistence,
provider, network, LLM, knowledge-index, event-bus, or mutation operation.
Authored assessments for that source are filtered from the same run snapshot.
Their labels distinguish current/superseded state and retain bounded text plus
the exact ID. Selection edits nothing; explicit correction-target and comparison
handoffs accept only current same-source records. Stale state, comparison source
membership, duplicates, and the 50-assessment limit are checked locally without
Brain, persistence, provider, network, LLM, or mutation work.
Authored claims for the selected run are also rendered from that immutable
snapshot. Labels distinguish current/superseded state and retain epistemic state,
categorical confidence, bounded text, and exact ID. Selection edits nothing;
separate predecessor and contradiction handoffs accept only current records.
Stale state, duplicates, and the exact two-ID contradiction bound are checked
locally without Brain, persistence, provider, network, LLM, event-bus, or
mutation work.
Persisted user-reviewed contradictions in that run populate another read-only
selector. Labels retain the exact claim pair, bounded authored note,
timezone-aware recorded time, and exact contradiction ID. Selection edits
nothing; an explicit handoff replaces only the manual pair field and preserves
the manual note. Stale or invalid selection state is refused locally without
Brain, persistence, provider, network, LLM, event-bus, or mutation work.
Persisted source-comparison notes in the selected run populate a read-only
selector with bounded authored text, recorded time, and exact note ID. An
associated summary exposes every exact source, evidence, and assessment ID.
Selection edits nothing; three explicit handoffs replace only their corresponding
manual reference field while preserving comparison text and non-target fields.
Stale state is cleared locally without Brain, persistence, provider, network,
LLM, event-bus, or mutation work.
For an attached source, `Save evidence` records one explicitly entered chunk ID
and note; `View evidence` displays the persisted bounded excerpt and locator.
Neither action extracts, ranks, or interprets evidence automatically.
`Preview assessment` uses the selected run and accepted source document ID to
display persisted provenance, that source's user-selected evidence, and its
authored assessment history. A
successful attached-source load fills the document field, but opening the view
is still explicit. The action performs no fetch, LLM, memory, graph, knowledge,
or persistence mutation and assigns no automatic trust or quality score.
`Preview & save assessment` requires the user's assessment text and explicit
comma-separated evidence IDs plus one user-authored information-trust label:
`unassessed`, `low`, `medium`, or `high`. The runtime shows a no-write preview
and the window requests confirmation only when allowed; the separate record request
revalidates the open run, accepted source, and same-source evidence before an
atomic append. An optional predecessor assessment ID creates a same-source
supersession link only after the preview and final write both verify that the
target is still current. The original remains visible; the desktop labels
current and superseded history without choosing evidence or generating a score.
The selected label describes information only: every accepted external source
remains tainted as untrusted data with instruction authority fixed to `none`.
`Compare sources` accepts two to five comma-separated accepted-source document
IDs for the selected run. It preserves the entered order and displays persisted
provenance, user-selected evidence, and only current authored assessments side
by side. It remains available for closed runs and performs no provider, network,
LLM, memory, graph, knowledge-index, event-bus, or persistence operation. It
does not identify a winner, select evidence, or assign trust scores.
Each comparison column displays at most 20 evidence records and 10 current
assessments, with complete counts visible so truncation is explicit and the
local transcript remains bounded.
`Preview & save comparison note` is available only for collecting runs. It
requires the user's note plus explicit evidence and current assessment IDs,
shows an exact no-write preview, and requests confirmation before a separate
record action revalidates and atomically appends the note. The comparison view
shows up to 20 notes for the exact entered source order after restart and reports
the complete count. The desktop never composes the note, chooses references, or
generates a winner or score.
`View contradictions` reads only persisted user-reviewed relationships for the
selected run and remains available after closure. `Preview & save
contradiction` requires exactly two distinct claim IDs and the user's own note,
then displays both persisted claims and their exact combined evidence before
confirmation. The separate record action revalidates the open run, references,
evidence, and unordered duplicate-pair guard before atomic append. It does not
detect contradictions, choose claims or evidence, decide truth, rewrite either
claim, invoke a provider or LLM, or change source instruction authority.
`Suggest contradictions` is a separate explicit, cancellable provider action.
It reads only bounded current claims, supplies no conversation history or tools,
and displays possible pairs with exact persisted evidence IDs and visibly
untrusted model rationale. Successful suggestions populate an ephemeral pair
selector tied to the exact run. `Use selected pair` copies only the two IDs into
the manual form; it leaves the authored note unchanged and performs no provider
or persistence operation. Starting another request, creating a run, or detecting
a run mismatch clears the selector. The user's own note, preview, confirmation,
and final runtime revalidation remain required.
`Export preview` is available for an explicitly selected terminal run. It
 renders persisted provenance, evidence, authored assessments, claims,
 user-reviewed claim contradictions, comparison notes, and failures as bounded
 Markdown, together with the immutable snapshot time,
full character count, omitted count, safe suggested filename, and full-content
SHA-256. It accepts no destination path and writes no file. `Save export` then
requires that exact displayed preview, opens a new-file chooser, and separately
confirms the selected path and fingerprint. Brain revalidates the snapshot time
and complete content before atomically publishing UTF-8 Markdown; an existing
destination is never replaced.
`Verify export` independently selects one existing `.md` file for the current
terminal run. The runtime hashes its complete bytes from one stable regular-file
descriptor and compares the byte count and SHA-256 with a fresh deterministic
render. `MATCH` and `DOES NOT MATCH` are both read-only results; the desktop does
not decode, import, repair, or modify the document.
The `Final status` selector offers only `completed`, `failed`, and `cancelled`.
`Preview status` shows the runtime decision first and requests a separate
confirmation only when allowed. A completed run requires source and evidence;
a failed run requires a failure record; every terminal outcome permanently
closes further run mutation.
Its Windows onedir package and local-data boundary are defined in ADR 0002. ADR
0003 adds an Ubuntu 24.04 x64 onedir package, XDG data paths, and a real
headless startup check; broader distribution targets and MVP views remain
planned.

## Purpose

Provide the first private, approachable place to interact with Hypatia's chat,
sessions, and explicitly requested memory status.

## Scope boundary

The implemented shell is deliberately narrow and delegates to `Brain`; it does
not add voice, a second data store, a browser, or automatic web discovery. See the
[Desktop MVP v0.1 design](../Design/Desktop_MVP_v0.1.md) and
[ADR 0001](../Decisions/0001-tkinter-desktop-shell.md).
