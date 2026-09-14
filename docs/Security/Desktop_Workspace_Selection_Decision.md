# Desktop Workspace Selection Decision

**Status: ACCEPTED FOR A FUTURE IMPLEMENTATION. NOT IMPLEMENTED.**

**Decision date:** 2026-08-24

**Runtime at decision:** `v0.3.180 (Genesis)`

## 1. Decision

Hypatia's first graphical filesystem-workspace selector will be a Windows-only,
operator-controlled settings flow. It may stage one proven local NTFS directory
for the **next process start**. It must never replace, widen, or rebuild the
filesystem authority owned by the running process.

The selector is a convenience source for the same bounded `workspace` root; it
is not a second root, a tool argument, a generic file browser, or an authority
that a model can use.

The first implementation must provide:

- a local `Choose folder...` action;
- an exact local preview of the canonical absolute directory;
- a separate confirmation bound to that exact candidate and the current saved
  settings revision;
- one bounded, atomic local preference record;
- a `Use Hypatia data folder after restart` action with its own confirmation;
- a visible distinction between **active now** and **pending after restart**;
- fail-closed startup when a saved custom workspace is corrupt, missing,
  linked, too broad, remote, non-NTFS, or otherwise no longer provable; and
- an explicit restart-required state with no automatic relaunch.

The implementation must not add live root switching, multiple roots, recursive
search, globbing, content continuation, write/delete/rename, shell/process
access, Linux/POSIX content access, or any downstream use of file content.

## 2. Why restart is the authority boundary

The current desktop resolves one `FilesystemRoot`, constructs the optional
`WindowsRootedOpen` and `FilesystemReadTool` for that same root, and then builds
`ToolRuntime`. This construction makes the registered capabilities and their
scope stable for the process lifetime.

Changing the root inside a running process would require coordinated
revocation across:

- the Tool registry;
- the metadata tools;
- the content reader and held native identities;
- an in-flight desktop worker;
- open content confirmations;
- previously rendered content and provenance; and
- every controller that cached a scope label.

The selector therefore writes only a next-start preference. The running
`FilesystemRoot`, `WindowsRootedOpen`, `FilesystemReadTool`, `ToolRuntime`, and
`ToolConsoleController` remain untouched. A successful settings write performs
no filesystem Tool invocation and grants no current-process effect.

## 3. Authority-source precedence

At startup, exactly one source is considered in this order:

1. a non-blank `HYPATIA_FILESYSTEM_ROOT` environment override;
2. a valid saved desktop workspace preference on supported Windows;
3. Hypatia's local desktop data directory when no preference file exists or
   the saved mode is explicitly `default`.

The environment override remains the highest-precedence operator/admin source.
While it is present, the settings panel is read-only and explains locally that
the scope is externally managed. A saved preference may remain on disk, but it
is not consulted and cannot override the environment. The UI must state that
the saved preference becomes relevant again if the environment override is
removed.

A blank environment value is absent, preserving the current policy. An invalid
non-blank environment override remains an explicit configuration error; the UI
must not silently replace it with a saved or default root.

On non-Windows platforms, the saved desktop preference is not consumed and the
selector is not shown. Existing environment/default metadata behavior remains
unchanged. A separately proven POSIX rooted-open decision is required before
this selector can authorize Linux content access.

## 4. Local preference contract

The proposed preference lives below the already resolved desktop data root:

```text
<DesktopDataPaths.root>/settings/filesystem-workspace.json
```

The exact proposed schema is:

```json
{
  "schema_version": 1,
  "mode": "custom",
  "path": "C:\\Users\\person\\Documents\\one-project"
}
```

or:

```json
{
  "schema_version": 1,
  "mode": "default"
}
```

Rules:

- only schema version `1` is accepted;
- only `default` and `custom` modes exist;
- `custom` requires exactly one non-blank canonical absolute path;
- `default` forbids a `path` member;
- unknown, duplicate, missing, or wrong-typed members fail closed;
- booleans are not accepted as numbers or modes;
- the complete UTF-8 document is capped at 16 KiB plus one detection byte;
- the custom path is capped separately at 8 KiB of UTF-8;
- the path field is excluded from dataclass `repr` and all exception text;
- canonical compact JSON is written through a bounded temporary file in the
  destination directory, flushed, fsynced, and atomically published with
  `os.replace`; and
- a failed validation or write leaves the previous exact file unchanged.

Absence of the preference file means legacy/default behavior. Resetting does
not delete the file; it atomically writes `mode="default"`, so a failed reset
cannot ambiguously expose either the old or default scope.

The absolute path is intentionally present in this one local settings record:
the next process cannot apply an exact directory without retaining it. This is
not permission to place it in general configuration, logs, events, memory,
research, exports, crash text, or model context. On Windows the file inherits
the user's desktop-data-directory ACL. The first implementation does not claim
encryption at rest or protection from another process already running as the
same OS user.

## 5. Candidate admission

The folder picker is presentation only. Returning a path from
`filedialog.askdirectory(mustexist=True)` proves neither safety nor authority.

Before a custom candidate can be previewed, and again before it can be saved,
the application-owned boundary must:

1. require a Windows absolute path;
2. construct the existing `FilesystemRoot` with root ID `workspace` so the
   candidate exists, is a directory, and is not a link or junction;
3. apply the existing `is_too_broad` rule, refusing a filesystem/drive root,
   the home directory, and every ancestor of the home directory;
4. construct `WindowsRootedOpen` for that exact `FilesystemRoot`, proving the
   supported local NTFS root, no-final-reparse, handle-derived final path, and
   stable root identity boundary; and
5. discard the temporary proof without registering a Tool or reading content.

The validation must return fixed, bounded categories. Native errors, drive
letters, server names, usernames, absolute paths, handles, volume identities,
and Win32 details must not enter an exception or event.

Network/UNC roots, ReFS, FAT, exFAT, removable filesystems that do not satisfy
the current NTFS proof, and every link/reparse root are refused by this first
selector. This is stricter than the legacy environment/default metadata path
and prevents a new UI from silently turning a local-only control into network
access.

Selection validation is repeated at next startup. A directory accepted when it
was chosen may disappear or change before restart; saved acceptance is never a
permanent proof.

## 6. Preview and confirmation contract

The first click opens only the OS folder picker. Cancelling it changes nothing,
creates no pending object, writes no file, emits no event, and does not clear or
replace the running root.

An admitted candidate creates one immutable in-memory preview containing:

- a code-owned preview ID;
- the canonical absolute path, excluded from `repr`;
- the proposed mode;
- the opaque root ID `workspace`;
- a SHA-256 revision of the exact current preference bytes, or a code-owned
  sentinel for an absent file; and
- fixed text stating that the change applies only after restart.

The local confirmation must show:

```text
Use this workspace after restarting Hypatia?

Selected folder:
<exact canonical absolute path>

Active now:
<exact current local workspace path, or "No filesystem workspace is active">

This does not change the running workspace.
Hypatia will verify the folder again during its next start.
No file content is being read or sent anywhere.

[Cancel] [Save for next restart]
```

The absolute paths in this modal are local operator-facing disclosure and must
be inserted literally, never parsed as Markdown, links, commands, or file
references.

Saving accepts only the preview ID. The UI must not resubmit a mutable path.
The controller resolves the preview ID to its immutable candidate, re-reads the
preference, compares the saved revision, and re-runs candidate admission. A
missing, replaced, already-used, cancelled, or stale preview is rejected before
write. Every preview is single-use whether saving succeeds or fails.

The default-reset flow follows the same preview/revision/single-use contract.
Its modal names the exact active workspace and exact Hypatia data directory,
then states that default mode applies after restart.

## 7. Stale confirmations and concurrent state

The controller owns at most one pending workspace preview. Creating a new
preview invalidates the old one. Closing the settings view, closing Hypatia, or
cancelling the modal invalidates it as well.

Optimistic revision comparison detects ordinary external or second-window
changes before publication. Atomic replacement prevents a partial document.
This design does not claim multi-process serializability between the final
revision check and `os.replace`; two explicitly operated Hypatia processes may
race and the last complete atomic record may win. A future multi-process
settings service would require an OS-owned lock and is outside this milestone.

Workspace staging also invalidates every not-yet-accepted filesystem-content
confirmation in the desktop adapter, clears any rendered content preview, and
updates the settings presentation to `Restart required`. This is defense in
depth: because there is no hot-swap, an already-running invocation still uses
only the old root. Its completion may be discarded but can never be retargeted
to the pending root.

The settings action is unavailable while the shared desktop single-flight
worker is active. It creates no second worker and cannot run concurrently with
Brain or Tool work through the UI.

## 8. Startup resolution and failure behavior

Startup distinguishes these states:

| State | Filesystem authority | Local settings presentation |
|---|---|---|
| environment override valid | exact override | `Managed by environment` |
| no preference file | Hypatia data root | `Default workspace` |
| saved `default` valid | Hypatia data root | `Default workspace` |
| saved `custom` valid and re-proven | exact saved root | `Custom workspace active` |
| saved custom missing/changed/unprovable | none | bounded `Saved workspace unavailable` |
| preference malformed/oversized/unknown | none | bounded `Workspace setting needs attention` |
| environment override invalid | none; explicit configuration failure | bounded `Managed workspace unavailable` |

For invalid saved custom state, startup must not fall back silently to the
Hypatia data directory. That would replace one explicitly selected authority
with another while making the UI appear usable. The application itself should
still start; filesystem capabilities are absent and the operator may choose a
new folder or explicitly reset to default for the next restart.

The persisted record is not automatically repaired, migrated, deleted, or
rewritten on read. Recovery always requires an explicit, separately confirmed
operator action.

## 9. Presentation states

The settings surface must keep three facts separate:

- `Active now`: the exact local path currently bound into `ToolRuntime`, or a
  bounded absent/unavailable state;
- `Saved for next start`: the exact local path or `Hypatia data folder`; and
- `Status`: `No restart needed`, `Restart required`, `Managed by environment`,
  or a bounded invalid-setting state.

The Tool Console may continue using the opaque `Scope: workspace` label. An
absolute root must never enter `ToolRunView`, `ToolResult`, audit lines, Tool
lifecycle events, generic status text, or content provenance.

The selector does not automatically close or relaunch Hypatia. It may offer an
ordinary `Close Hypatia` action only by reusing the existing close boundary,
but the first implementation does not require that convenience.

## 10. Privacy and data-flow exclusions

The canonical absolute path may exist only in:

- the local settings store;
- the in-memory settings controller/preview;
- the local folder picker and settings/confirmation widgets; and
- the startup composition boundary before it is reduced to the opaque root ID.

It must not enter:

- chat messages, provider prompts, model context, or model output;
- general memory, learned memory, semantic embeddings, or embedding cache;
- research runs, sources, evidence, assessments, claims, exports, or failures;
- knowledge documents or graph relationships;
- Tool arguments, results, audit lines, lifecycle events, or generic telemetry;
- logs, exceptions, crash summaries, clipboard, temp exports, or remote calls;
- filenames derived from the selected directory; or
- analytics, update checks, plugins, agents, or autonomous tasks.

The selector reads no file content and enumerates no entries. Candidate proof
touches only directory/root metadata required by the existing policy and
Windows rooted-open boundary.

## 11. Proposed production boundaries

The implementation should introduce narrow, testable components rather than
placing persistence or authority decisions in Tkinter:

```text
DesktopDataPaths
  -> workspace_selection_path

JsonFileFilesystemWorkspaceStore                 [PROPOSED]
  -> bounded strict JSON read / atomic exact write

FilesystemWorkspacePreference                    [PROPOSED]
  -> mode + optional repr-hidden canonical path

FilesystemWorkspaceService                       [PROPOSED]
  -> precedence, candidate proof, preview identity,
     stale-revision check, save/reset, startup state

desktop_main
  -> asks the service for one startup composition
  -> constructs ToolRuntime once

WorkspaceSettingsController                      [PROPOSED]
  -> plain desktop projections only

TkinterDesktopWindow
  -> picker, literal preview, modal confirmation, state rendering
```

The exact names may change during implementation if the current module naming
conventions demand it, but the responsibilities may not collapse into
`TkinterDesktopWindow` or `ToolRuntime`.

`ToolRuntime` receives only the already proven `FilesystemRoot` and optional
exact `FilesystemReadTool`; it must not read settings, open a picker, accept an
absolute path, or expose a root-changing method.

No Brain, CognitiveEngine, model, memory, research, knowledge, agent, or plugin
module may import the settings service or store.

## 12. Required implementation tests

Before the selector can be called implemented, focused tests must prove:

### Preference record

- missing file means default mode;
- exact custom/default round trips;
- strict key, type, mode, schema, UTF-8, and byte limits;
- duplicate JSON keys are refused;
- malformed/oversized reads perform no rewrite;
- exact-byte atomic write and failed-write preservation;
- path fields are absent from `repr` and failure text; and
- reset writes explicit default mode rather than deleting state.

### Admission and precedence

- environment override wins and makes UI state managed/read-only;
- a blank override does not win;
- saved custom wins over default only on supported Windows;
- missing or corrupt saved custom yields no filesystem capability;
- drive root, filesystem root, home, home ancestor, link/junction, UNC/network,
  non-NTFS, missing, and unreadable candidates are refused without path leak;
- valid local NTFS custom root is re-proven at save and startup; and
- Linux/POSIX consumes neither the saved selection nor a content fallback.

### Confirmation and restart

- picker cancellation creates no preview and no write;
- confirmation shows the exact canonical candidate and current active root;
- confirmation cancellation creates no write or event;
- accepted confirmation saves the exact immutable preview candidate;
- modified settings revision, replaced directory, reused ID, and superseded
  preview all decline before write;
- saving never changes the running root or registered capabilities;
- restart applies a valid saved custom root exactly once during composition;
- invalid restart state starts Hypatia with filesystem capabilities absent;
- staging clears literal content and invalidates pending content confirmation;
  and
- no automatic restart, second worker, queue, or concurrent Tool action exists.

### Isolation

- source-level dependency tests keep the path out of Brain, cognition, memory,
  research, knowledge, Tool result/audit/event, export, and provider modules;
- event payloads contain only bounded categories/booleans and never paths;
- no clipboard, network, shell, process, plugin, or generic registration API is
  added; and
- existing filesystem list, metadata, content confirmation, cancellation,
  close, Windows package smoke, and Linux package smoke regressions remain
  green.

## 13. Implementation sequence

The accepted implementation should be split if any stage cannot remain small:

1. **Store and immutable preference types** — no UI, no runtime consumption.
2. **Startup selection service** — precedence and fail-closed state, still no
   picker.
3. **Read-only settings presentation and candidate preview** — no write.
4. **Separate confirmed save/reset** — still restart-bound.
5. **Startup consumption and package smoke** — exact composition only.

Every stage must keep the application usable when the preference is absent and
must preserve current byte-identical behavior outside the desktop filesystem
composition path.

## 14. Deferred decisions

This decision does not authorize:

- Linux/POSIX workspace selection for content;
- support for ReFS, FAT, exFAT, SMB, UNC, network, or cloud-mounted roots;
- live root hot-swap or automatic relaunch;
- more than one root, bookmarks, recent-folder history, or recursive browsing;
- multi-process settings locking;
- encryption of the local preference file;
- sensitive-path overrides or content-based secret scanning;
- file content in model context, memory, research, evidence, knowledge,
  persistence, exports, clipboard, remote calls, or generic telemetry;
- file writes, deletion, rename, move, shell, or process execution; or
- agents or autonomous tasks selecting, widening, or repairing a workspace.

## 15. Decision register

| Question | Decision |
|---|---|
| Does selection change the live root? | No; next process start only |
| Who selects? | Local human operator through explicit settings UI |
| Where is the exact path stored? | One bounded local desktop settings record |
| Is the path shown? | Only in exact local settings/confirmation UI |
| Root ID | Existing opaque `workspace` |
| Environment precedence | Highest; UI read-only while present |
| Missing preference | Legacy/default Hypatia data root |
| Corrupt or invalid saved custom root | Fail closed; no filesystem tools |
| Broad roots | Refused by current policy |
| First-platform support | Windows local NTFS only |
| Network/UNC/non-NTFS | Refused |
| Confirmation binding | Single-use preview ID + exact settings revision |
| Reset | Atomic explicit `default` record |
| Automatic repair/fallback | None |
| Automatic restart | None |
| Runtime hot-swap | Forbidden |
| Model or downstream path access | Forbidden |
