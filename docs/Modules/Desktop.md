# Desktop Application

## Status

The first local Tkinter shell is implemented for text chat, refreshable session
overview and explicit selection, selected-session details/recent/activity, and
explicit lexical/semantic recall, bounded cited knowledge context, and
semantic-runtime status. It also provides explicit local Markdown/text source
loading, source-catalog/graph views, source-relation controls, and guarded
session rename/delete flows. Users can choose a local text size between 10 and
20 points and toggle high contrast without affecting runtime state. One
explicitly entered public HTTPS research source can be validated, fetched, and
indexed through Brain without background traffic or conversation-memory writes.
The shell can also create/list persistent research runs and attach that source
to a selected run ID while leaving page content in the existing in-memory
knowledge boundary.
For a selected collecting run, `Find sources` explicitly queries the bounded
Crossref metadata provider and displays up to five persisted candidates.
`Use selected URL` only copies the chosen DOI URL into the existing source
field. `Preview & load` first renders a read-only decision for the exact run,
discovery, and candidate, then asks for confirmation before a separate request
revalidates and uses the existing guarded loader. Changing the run ID makes old
candidate selections unusable; stale or unlisted choices stop before network
access.
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
comma-separated evidence IDs. The runtime shows a no-write preview and the
window requests confirmation only when allowed; the separate record request
revalidates the open run, accepted source, and same-source evidence before an
atomic append. It never chooses evidence or generates a score.
The `Final status` selector offers only `completed`, `failed`, and `cancelled`.
`Preview status` shows the runtime decision first and requests a separate
confirmation only when allowed. A completed run requires source and evidence;
a failed run requires a failure record; every terminal outcome permanently
closes further run mutation.
Its first Windows onedir package and local-data boundary are defined in ADR
0002; broader MVP views remain planned.

## Purpose

Provide the first private, approachable place to interact with Hypatia's chat,
sessions, and explicitly requested memory status.

## Scope boundary

The implemented shell is deliberately narrow and delegates to `Brain`; it does
not add voice, a second data store, a browser, or automatic web discovery. See the
[Desktop MVP v0.1 design](../Design/Desktop_MVP_v0.1.md) and
[ADR 0001](../Decisions/0001-tkinter-desktop-shell.md).
