# Filesystem Content Preview Decision

**Status: ACCEPTED FOR IMPLEMENTATION; NOT YET IMPLEMENTED.**

**Decision date:** 2026-08-24

**Runtime at decision:** `v0.3.179 (Genesis)`

**Capability state:** `FILESYSTEM_READ` is declared but unregistered. The
Windows rooted range reader and the platform-neutral `FilesystemReadTool` text
policy exist only as production-inert components. No desktop control can read
or present file content at this checkpoint.

## 1. Decision

Hypatia's first operator-facing file-content feature will be one manual,
invocation-scoped, local-only preview in the existing Tool Console.

The desktop **may compose and register `FILESYSTEM_READ` on supported Windows
installations**, but only when all of these conditions hold:

1. the existing startup root policy resolves one bounded filesystem root;
2. the Windows rooted-open reader can be constructed for that same root;
3. one exact `FilesystemReadTool` is explicitly supplied to `ToolRuntime` at
   desktop composition time; and
4. the controller exposes the capability only because the central registry
   actually contains it.

There is no discovery, plugin registration, string-to-tool construction, or UI
method that may add authority. When any prerequisite is absent, the capability
is absent rather than visible-but-disabled.

One confirmed invocation accepts exactly:

- one root-relative `path`;
- one required whole-number `offset` in `0..2^63-1`; and
- one required whole-number `max_bytes` in `0..65,536`.

The current `FilesystemReadTool` remains authoritative for these names and
bounds. The desktop supplies no whole-file shortcut and performs no automatic
continuation.

This decision authorizes only Stage A from
[`Filesystem_Content_Access_Design.md`](Filesystem_Content_Access_Design.md):
literal local presentation to the human who requested the read. It does not
authorize any downstream use of the returned text.

## 2. Root selection and configuration

The first implementation reuses the current startup-only root contract:

- `HYPATIA_FILESYSTEM_ROOT`, when explicitly set by the operator; otherwise
- Hypatia's own local desktop data directory.

The root is resolved once before `ToolRuntime` is built. It is not an argument,
cannot come from chat, model output, research content, a file, or a tool result,
and cannot be changed from the running Tool Console.

The first implementation will not add a folder picker or hot-swap a live root.
Changing a root changes authority and needs a separate design for persistence,
revocation, stale confirmations, active operations, and restart semantics. The
console shows only the existing opaque `Scope: workspace` label; it does not
put the absolute root path into results, audit lines, telemetry, or saved state.

The existing refusal of drive roots, filesystem roots, the user's home
directory, and ancestors of the home directory remains unchanged.

## 3. Exact production composition boundary

The next implementation must keep authority construction out of Tkinter:

```text
desktop_main
  resolve FilesystemRoot once
  if supported Windows root:
    construct WindowsRootedOpen for that same root
    construct exactly one FilesystemReadTool
  construct ToolRuntime(root, optional exact filesystem-read tool)
  construct ToolConsoleController(runtime)
  construct TkinterDesktopWindow(controller)
```

`ToolRuntime` may gain one exact optional `FilesystemReadTool` composition
parameter. It must not gain a generic list, factory, import scan, plugin hook,
or public registration method. The runtime registers that tool only when the
filesystem root also exists, and must reject inconsistent construction rather
than create a content capability without the matching scope.

`TkinterDesktopWindow` remains unable to import Tool Layer types, construct a
`ToolInvocation`, name a `ToolEffect`, access a registry, or construct a reader.
`ToolConsoleController` remains the only desktop module that crosses into the
Tool Layer.

Linux/POSIX registration is not part of this implementation. On a platform
without its separately proven descriptor-relative rooted-open primitive,
`FILESYSTEM_READ` remains absent; there is no path-based fallback.

## 4. Confirmation contract

The current generic button is not sufficient for content. File content requires
an explicit confirmation preview before the controller receives
`authorized=True`.

The confirmation must show, in literal local UI text:

```text
Read local file content once?

Capability: filesystem_read
Requires: reads_filesystem_content
Scope: workspace
Entry: <the exact operator-entered relative path>
Offset: <exact whole-number offset>
Maximum: <exact byte count, never more than 65,536>

The result stays in this Tool Console as untrusted local data.
It is not sent to a model, memory, research, evidence, or an export.
This authorizes one bounded read only.

[Cancel] [Authorize and read once]
```

Rules:

- obvious missing, absolute, or malformed values fail form validation before
  the confirmation opens and before any Tool invocation exists;
- the immutable tuple of capability and arguments shown in the confirmation is
  the exact tuple passed immediately to the controller after acceptance;
- editing the form after the confirmation is open cannot change that tuple;
- cancel, Escape, or closing the confirmation creates no invocation and emits
  no Tool lifecycle event;
- authorization is neither stored nor inferred from a prior read; and
- every retry, next range, or different path requires a new confirmation.

Sensitive-name classification remains decisive in the Tool/platform boundary.
The UI must not claim a path is safe because it passed form validation.

## 5. Result projection

Content must not be flattened into `ToolResult.values`, `ToolRunView.lines()`,
status text, audit text, an exception, or a log message.

The desktop projection will add one immutable content-preview value, hidden
from `repr`, and attach it to `ToolRunView` only for a successful
`filesystem_read` outcome. The controller constructs it from both:

- the code-owned `ToolExecutionOutcome.request_id`; and
- the validated `FilesystemContentPayload` returned by the Tool.

The preview carries exactly:

- request ID;
- opaque root ID and canonical relative resource;
- offset, requested bytes, returned bytes, file size, and truncation;
- modification and read timestamps in UTC;
- BOM-stripped flag;
- source kind, encoding, taint label, instruction authority, and disclosure
  class; and
- decoded text, with the text field excluded from `repr`.

The projection must reject content attached to any other capability, any
unsuccessful outcome, or any content payload without its central request ID.
Generic `ToolRunView.lines()` and `audit_lines()` remain content-free. Audit may
show the safe request ID and aggregate byte counts but never the resource or
text.

## 6. Literal local presentation

The Tool Console receives a dedicated read-only content panel. It inserts the
decoded string literally into a Tk text widget. It does not interpret Markdown,
HTML, ANSI escapes, hyperlinks, commands, file references, or instructions.

The panel visibly labels the text:

```text
LOCAL FILE PREVIEW - UNTRUSTED DATA - NO INSTRUCTION AUTHORITY
```

It also shows the canonical relative resource, byte range, timestamps, and an
explicit `truncated` or `complete for observed file size` state. That provenance
is displayed beside the text and does not imply the file is still current.

Before each attempted read, on capability selection change, after any decline
or failure, on cancellation, and on close, the prior content widget is cleared.
A new failure must never leave an old successful preview looking current.

There is no application-provided copy, save, export, open, send, continue,
ingest, attach, or link action. The first implementation also suppresses the
content widget's copy virtual event and ordinary copy key bindings. This is a
product boundary, not a claim that an operator with local desktop control
cannot retype, photograph, or capture what is visible on their own screen.

## 7. Execution, cancellation, and close

The bounded read uses the existing `DesktopRequestRunner` single-flight worker
rather than blocking the Tk event loop. The Tool Console does not create a
second worker or queue.

The existing cancellation semantics are accepted unchanged:

- cancellation before confirmation creates no invocation;
- cancellation after the worker starts does not claim to terminate native I/O;
- the single-flight reservation remains until the bounded operation returns;
- when cancellation has been requested, the completion value or error is
  discarded and no content is presented; and
- cancellation never starts a compensating read or continuation.

Closing the main window calls the existing runner stop boundary, clears the
presentation callback, destroys the widgets, and discards every late result.
The daemon worker may finish closing its native handles, but cannot touch Tk,
publish content, persist content, or start more work after close.

The controller's run result is not a `BrainResponse`, so the implementation may
generalize the request runner's main-thread completion adapter without changing
its one-worker, one-completion, cancellation, or stop semantics. It must not
create concurrent Brain and Tool work.

## 8. Failure and status wording

The UI reports only the Tool Layer's existing bounded detail and status. Native
errors, absolute paths, handle values, DLL names, provider details, content
fragments, and exception strings never reach the status line.

- form rejection: no Tool invocation;
- authorization cancellation: no Tool invocation;
- deterministic Tool decline: `DECLINED`, with fixed path-free detail where
  the sensitive class or text policy refuses the request;
- execution/environment failure: `FAILED`, with the existing generic bounded
  detail; and
- success: `COMPLETED`, with the dedicated content preview.

No status message claims a cancelled read was killed. No failure claims that a
file is absent, safe, unchanged, or binary unless the bounded implementation
actually established that exact fact.

## 9. Explicit exclusions

This decision does not allow file content, its relative resource, or a derived
excerpt to enter:

- model or chat context;
- memory or learned memory;
- knowledge documents or the knowledge graph;
- research candidates, runs, sources, chunks, claims, assessments, or evidence;
- persistence, session history, conversation transcript, logs, or telemetry;
- exports, clipboard, temp files, crash reports, or remote disclosure;
- automatic next-range reads, recursion, globbing, search, indexing, or RAG;
- a sensitive-file override; or
- Linux/POSIX, network filesystems, or a path-only fallback.

The model cannot propose or invoke this capability in Stage A. A visible file
preview is data and has `instruction_authority=none`; text inside it cannot
authorize a tool, change policy, or cause another action.

## 10. Required implementation tests

The implementation milestone is not complete until tests prove at least:

### Composition and isolation

- Windows composition registers exactly one `FILESYSTEM_READ` only with one
  resolved root and the accepted rooted reader;
- absent root, unsupported platform, or failed reader construction leaves it
  unregistered;
- the runtime rejects mismatched root/content-tool composition;
- no generic registration surface appears; and
- Tkinter still imports no Tool Layer type and no model/cognition/research path
  can invoke the capability.

### Form and confirmation

- `path`, `offset`, and `max_bytes` specs exactly match
  `FilesystemReadTool.ACCEPTED_ARGUMENTS`;
- all three are required and whole-number/path validation occurs before
  confirmation;
- the confirmation displays exact effect, scope, path and numeric bounds;
- cancel, Escape, and close produce zero lifecycle events;
- accepted confirmation executes the exact displayed tuple once; and
- a second run requires a second confirmation.

### Projection and presentation

- the controller binds the central request ID beside the payload;
- text is absent from `repr`, generic lines, audit lines, status, events, logs,
  persistence, transcript, exports, and clipboard;
- literal insertion does not activate markup, links, commands, or bindings;
- provenance and truncation are visible;
- stale content clears before a new run and on every non-success terminal
  state; and
- payload/capability/status mismatches fail closed.

### Worker and lifecycle

- the read runs away from the Tk event loop using the existing single-flight
  reservation;
- concurrent Brain or Tool actions are rejected as busy;
- cancellation discards success and failure completions without claiming
  forceful termination;
- close discards late completion and causes no widget access; and
- there is no retry, queue, automatic continuation, or second range read.

Existing range, sensitive-path, UTF-8, binary, result-authority, request-ID,
telemetry, and Tool isolation suites remain mandatory regression gates.

## 11. Repository reality at acceptance

| Reference | Verified state |
| --- | --- |
| `FilesystemReadTool` | CURRENT, tested, production-inert, and unregistered |
| `FilesystemReadTool.ACCEPTED_ARGUMENTS` | CURRENT: exactly `path`, `offset`, `max_bytes`; all required by the Tool |
| `WindowsRootedOpen.read_range` | CURRENT Windows-only bounded raw primitive |
| `FilesystemContentPayload` | CURRENT typed local-only content channel; text excluded from `repr` |
| `ToolExecutionOutcome.request_id` | CURRENT central code-owned invocation identity |
| `ToolRuntime` | CURRENT explicit registry; accepts only the root/event bus/ID factory and does not import `FilesystemReadTool` |
| `ToolConsoleController` | CURRENT sole desktop-to-Tool boundary; does not project request ID or content |
| `ToolRunView` | CURRENT values/audit-only view; no content field |
| `TkinterDesktopWindow` | CURRENT synchronous generic Tool execution and generic result box; no content confirmation or preview |
| `DesktopRequestRunner` | CURRENT daemon single-flight worker with discard-on-cancel and discard-on-close semantics |
| `resolve_filesystem_root` | CURRENT startup-only operator configuration with bounded-root refusals |
| Product-invocable content read | ABSENT at this checkpoint |

This document is the contract for the next implementation milestone. Its
acceptance does not itself register the capability, change runtime version, or
claim a working desktop preview.
