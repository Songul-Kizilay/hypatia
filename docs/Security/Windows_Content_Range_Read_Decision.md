# Windows Content-Range Read Production Decision

**Status: ACCEPTED AND IMPLEMENTED AS A PRODUCTION-INERT PLATFORM PRIMITIVE.**

**Decision date:** 2026-08-24

**Runtime at decision:** `v0.3.177 (Genesis)`

**Implemented in:** `v0.3.178 (Genesis)`

**Capability state:** `FILESYSTEM_READ` remains unregistered. Production owns
one bounded raw `read_range` primitive and, as of `v0.3.179`, an isolated
platform-neutral text-policy Tool seam. No runtime, desktop, model, memory,
research, evidence, persistence, Linux/POSIX, or generic content-telemetry path
can invoke or receive them.

## 1. Decision

Hypatia's first Windows content read is one bounded, synchronous range
from the final NTFS handle already acquired by the production rooted-open
proof. It will:

1. perform the existing lexical admission, sensitive-name checks,
   root-relative component walk, reparse refusal, final containment and
   identity proof;
2. acquire the final component during that same walk with
   `FILE_READ_DATA | FILE_READ_ATTRIBUTES | SYNCHRONIZE` rather than reopening
   a path after proof;
3. allow only `FILE_SHARE_READ` on the final content handle, withholding write
   and delete sharing for the lifetime of the read;
4. keep the handle synchronous with `FILE_SYNCHRONOUS_IO_NONALERT` and use the
   documented Win32 `ReadFile` API with a non-null `OVERLAPPED` structure to
   supply the exact 64-bit byte offset;
5. issue exactly one native read for `max_bytes + 1`, where `max_bytes` is in
   `0..65_536`, so the native capacity is never more than 65,537 bytes;
6. retain at most the first `max_bytes`; the one-byte lookahead is used only to
   prove truncation, and is never returned, decoded, logged, persisted, or
   copied into a result;
7. compare handle-derived identity, size and last-write time immediately before
   and after the read; any observed change discards the buffer and fails;
8. treat EOF and positive short reads by the exact rules in §7 rather than
   retrying or automatically continuing;
9. close the final, parent and root handles before any decoded payload or
   successful `ToolResult` may be constructed; and
10. preserve the existing 64 KiB payload ceiling, strict UTF-8/BOM policy,
    binary refusal, local-only taint and generic-telemetry exclusion.

`v0.3.178` implements this production-*inert* platform primitive. `v0.3.179`
adds the separately tested, still-unregistered Tool text-policy seam. This
decision does not authorize registration, desktop control, model context,
memory, research, evidence, persistence, remote disclosure, automatic
continuation, or sensitive-file override.

## 2. Evidence and official contracts

The accepted boundary relies on the current production-inert
[`WindowsRootedOpen`](../../src/tools/WindowsRootedOpen.py) proof and these
Microsoft contracts:

- [`ReadFile`](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-readfile)
  reads at most the requested byte count. For a synchronous handle and a
  non-null `OVERLAPPED`, the call starts at the structure's offset and does not
  return until the read completes. A read that begins before EOF and crosses
  it succeeds with only the bytes before EOF; a non-null-overlapped read at or
  beyond EOF reports `ERROR_HANDLE_EOF`.
- [`OVERLAPPED`](https://learn.microsoft.com/en-us/windows/win32/api/minwinbase/ns-minwinbase-overlapped)
  represents the file position through the `Offset` and `OffsetHigh` DWORDs.
- [`File security and access rights`](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights)
  documents that `FILE_READ_DATA` is the specific data-read right and that
  generic read also includes attributes and synchronization. The future native
  open requests only the specific rights it needs.
- [`CreateFile` sharing semantics](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
  document that a missing `FILE_SHARE_WRITE` conflicts with an already-open
  writer or writable file mapping, and a missing `FILE_SHARE_DELETE` prevents
  a compatible delete/rename open while this handle remains live.
- [`GetFileInformationByHandle`](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandle)
  returns one handle-derived structure containing the volume/file identity,
  size and last-write time used for the pre/post observation.
- [`BY_HANDLE_FILE_INFORMATION`](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/ns-fileapi-by_handle_file_information)
  defines the size, last-write, volume serial and 64-bit file-index fields.
- [`FILETIME`](https://learn.microsoft.com/en-us/windows/win32/api/minwinbase/ns-minwinbase-filetime)
  is a 64-bit count of 100-nanosecond intervals since 1601-01-01 UTC; its halves
  must be copied into an integer rather than pointer-cast.
- [`CloseHandle`](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-closehandle)
  remains the single close operation for every acquired handle.

The current production boundary supports only local NTFS and already rejects
directories and reparse points. Pipe, console, device, mailslot, network and
unsupported-filesystem `ReadFile` behaviours therefore do not become part of
the content contract.

## 3. Why `ReadFile` is selected

`ReadFile` is the narrow documented Win32 surface that fits the existing
synchronous handle. A non-null `OVERLAPPED` gives each call an explicit offset,
so the implementation does not depend on an earlier mutable seek.

The alternatives are rejected for the first boundary:

- `NtReadFile` adds another native NT contract without providing a required
  property that documented `ReadFile` lacks.
- `SetFilePointerEx` followed by `ReadFile(..., lpOverlapped=NULL)` creates a
  two-call pointer sequence. The handle is private, but an explicit per-call
  offset is clearer and easier to test.
- Python `open`, `Path.read_bytes`, `os.open` and `os.read` would require a path
  reopen or expose a raw descriptor outside the rooted-open owner.
- memory mapping may fault pages after the proof, has a different lifetime and
  sharing model, and makes a 64 KiB single-read bound harder to audit.
- asynchronous I/O introduces pending-operation, cancellation, event and
  buffer-lifetime states that a local 65,537-byte maximum does not justify.

No path-only or Python fallback is allowed when the native API is unavailable.

## 4. Final-handle access and sharing

Root and intermediate directory handles keep their current attribute-only
access and existing lifetime. Only the final component in a future content
acquisition changes:

```text
DesiredAccess = FILE_READ_DATA | FILE_READ_ATTRIBUTES | SYNCHRONIZE
ShareAccess   = FILE_SHARE_READ
Disposition   = FILE_OPEN
CreateOptions = FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT
```

The final handle is acquired once, relative to the held parent. There is no
attribute-only final open followed by a second content-capable path open.

Withholding `FILE_SHARE_WRITE` and `FILE_SHARE_DELETE` is intentional:

- a conflicting existing writer or writable mapping makes acquisition fail;
- a new write/delete/rename open cannot become compatible while the handle is
  live; and
- an editor actively holding the file for write may therefore make a manual
  read fail. Phase A prefers an honest retry after editing to a chunk that
  looks stable while it is being rewritten.

This is not an immutable snapshot guarantee. An already-created mapping,
filesystem filter, delayed timestamp update or lower-level storage behaviour
may still make an in-place change invisible. §8 states the residual limit.

## 5. Implemented API ownership

The implementation keeps the operation inside
`src/tools/WindowsRootedOpen.py`. Its shape is one bounded method on the owner,
not a handle method exposed to a tool:

```text
WindowsRootedOpen.read_range(relative, *, offset, max_bytes)
```

The method performs the rooted acquisition, one native read, pre/post checks
and all closes. Only after successful closure may it return one immutable
`WindowsContentRangeObservation`
containing:

- retained raw bytes, no more than `max_bytes`;
- the canonical relative resource already derived by the rooted proof;
- offset and requested count;
- exact raw returned count, excluding the lookahead;
- stable observed file size and last-write time; and
- explicit truncation.

It returns no handle, absolute path, raw final path, native status, system error
text, DLL path or unbounded buffer. The unregistered `FilesystemReadTool` now
owns NUL, UTF-8 and BOM interpretation and constructs
`FilesystemContentPayload`; the Windows platform module does not become a
presentation or Tool Layer module.

## 6. Range validation and the hard byte ceiling

The method validates before native acquisition:

- `offset` is an integer but not a boolean, in
  `0..MAX_CONTENT_OFFSET` (`2^63 - 1`);
- `max_bytes` is an integer but not a boolean, in
  `0..MAX_CONTENT_BYTES` (`65_536`);
- native capacity is computed only after those checks as `max_bytes + 1`;
- the resulting capacity is therefore in `1..65_537`, fits a DWORD, and is the
  exact buffer size and exact `ReadFile` request; and
- the offset is split without sign extension:
  `Offset = offset & 0xffffffff` and
  `OffsetHigh = (offset >> 32) & 0xffffffff`.

The entire `OVERLAPPED` structure is zero-initialized before those two offset
fields are assigned; `hEvent` remains null. A synchronous DWORD
`lpNumberOfBytesRead` is supplied. If the synchronous call ever reports
`ERROR_IO_PENDING`, the contract is violated and the read fails rather than
waiting on an operation this milestone did not authorize.

No arithmetic uses a caller-provided value before type and range validation.
No “read whole file” sentinel, negative offset, negative count, unlimited
count, default larger than the cap or automatic next range exists.

The one-byte lookahead is part of the authorized bounded implementation, but
not returned content. It exists only to cross-check whether content continues
after the caller's maximum. It is immediately dropped before text inspection.
For `max_bytes == 0`, the same rule reads at most one lookahead byte and returns
zero content bytes with an accurate truncation flag.

## 7. Exact `ReadFile`, EOF and short-read semantics

The implementation issues exactly one `ReadFile` call after the rooted
proof and pre-read snapshot. There is no hidden loop or retry.

Let:

```text
capacity = max_bytes + 1
raw_count = the native bytes-read output
```

The accepted terminal states are:

| Native outcome | Decision |
| --- | --- |
| `TRUE`, `0 <= raw_count <= capacity` | Continue to post-read validation |
| `FALSE` with `ERROR_HANDLE_EOF` and `offset >= pre_size` | Treat as zero bytes at EOF, then still run post-read validation |
| Any other `FALSE` | Bounded execution failure; return no bytes |
| Count outside `0..capacity` | Contract failure; return no bytes |

After the post-read snapshot proves the same identity, size and last-write
time:

- if `raw_count == capacity`, retain the first `max_bytes` and set truncation;
- otherwise retain all `raw_count` bytes;
- if `offset + raw_count < stable_file_size`, a positive or zero short read
  stopped before the stable EOF. It is `read_incomplete`, not success and not a
  reason to issue another call;
- if `offset >= stable_file_size`, the accepted result is empty and not
  truncated;
- if `offset + retained_count < stable_file_size`, `truncated` is true;
- otherwise `truncated` is false; and
- impossible combinations, including native bytes extending beyond the stable
  file size, fail rather than being normalized.

This distinguishes a real EOF-bounded short read from an unexplained partial
read. Automatic continuation would widen the authorized operation, complicate
cancellation and make the byte ceiling harder to prove, so Phase A does not do
it.

## 8. Pre/post observation and staleness

Immediately before `ReadFile`, and again immediately after it, the same final
handle is queried with `GetFileInformationByHandle`. The implementation compares:

- volume serial plus 64-bit file index;
- 64-bit file size; and
- raw 64-bit last-write `FILETIME`.

Any difference is a bounded `content_changed` execution failure. The buffer is
not decoded or returned. The stable raw `FILETIME` is converted to a
timezone-aware UTC `datetime` for `modified_utc`; no local-time conversion is
used.

The read timestamp is captured from an injected UTC clock after native read
completion and before handle closure. The clock is provenance, not a timeout
or an authorization source.

The raw 100-nanosecond `FILETIME` participates in the pre/post comparison.
Python `datetime` stores only microseconds, so `modified_utc` intentionally
drops the final sub-microsecond digit; this presentation limit does not weaken
the raw staleness comparison.

These checks detect observed change; they do not prove absence of change.
Matching identity, size and time can miss in-place replacement of bytes,
timestamp restoration, caching/delayed updates, identity reuse outside the
accepted NTFS assumptions, or a change that occurs after the post-read query.
The admitted `st_dev` value is narrowed to the Windows volume-serial width only
for the existing local-NTFS identity comparison; no collision-resistance claim
is made beyond that accepted boundary.
The returned payload therefore describes one observed moment and must never be
labelled “immutable”, “verified unchanged” or “snapshot”.

## 9. Text, binary and BOM order

Only the retained bytes enter the platform-neutral text policy. The discarded
lookahead byte must not affect binary classification, decoding or byte counts.

The unregistered Tool applies this order after successful handle closure:

1. if retained bytes contain NUL, decline as binary;
2. if `offset == 0` and the retained bytes start with the three-byte UTF-8 BOM,
   strip exactly that prefix and set `bom_stripped=True`;
3. otherwise keep the bytes unchanged and set `bom_stripped=False`;
4. decode as UTF-8 with `errors="strict"`;
5. decline invalid UTF-8, including a byte range that splits a multi-byte
   character; and
6. build `FilesystemContentPayload` with raw `bytes_returned`, the stable size
   and time, explicit truncation, and decoded text.

The tool does not read outside the authorized range to repair a character
boundary. It does not auto-detect an encoding, replace invalid bytes, return
base64/hex, or let an extension override content classification.

An empty range is valid UTF-8 text. A three-byte BOM-only retained range becomes
empty text with `bytes_returned == 3` and `bom_stripped == True`, matching the
current payload invariant.

## 10. Close-before-result ownership

The implementation preserves this ownership order:

```text
rooted admission and proof
    -> final content-capable handle owned by ExitStack
    -> pre-read observation
    -> one bounded ReadFile
    -> post-read observation and byte-count validation
    -> copy only the retained bounded bytes into an internal observation
    -> close final, parents and root in reverse order
    -> only after every close succeeds: return the observation
    -> only then: binary/UTF-8/BOM interpretation and ToolResult construction
```

If any close fails, no `FilesystemContentPayload` and no successful result are
constructed. The already-read buffer is abandoned without logging, telemetry,
persistence or fallback output. Python does not promise secure memory wiping,
so this is a disclosure/ownership guarantee, not a RAM-erasure claim.

Cancellation is checked at existing Tool Layer boundaries. This synchronous,
local, bounded native call cannot be made safely cancellable by closing its
handle from another thread in the first milestone; adding
`CancelSynchronousIo` would require a separate thread/lifetime design.

## 11. Bounded failures and current unregistered Tool mapping

The implementation adds exactly these low-level categories:

| Proposed low-level failure | Meaning |
| --- | --- |
| `read_failed` | `ReadFile` did not complete under an accepted EOF case |
| `read_incomplete` | One native call ended before the stable EOF and before the byte ceiling |
| `content_changed` | Identity, size or last-write observation differed across the read |

Existing rooted-open categories remain authoritative for platform, admission,
sensitive class, containment, identity, open and close failures. Raw Win32
codes and messages never cross the platform boundary.

The current unregistered Tool mapping is:

- invalid `offset`/`max_bytes`, non-file and initial path refusals:
  `INVOCATION_DECLINED`;
- sensitive class: `INVOCATION_DECLINED` with fixed class-only wording;
- NUL/binary or invalid UTF-8 after the bounded read:
  `INVOCATION_DECLINED`, no content payload;
- missing `READS_FILESYSTEM_CONTENT` authority: `UNAUTHORIZED_EFFECT`, tool not
  reached;
- API/open/share/read/incomplete/change/containment/identity/close failure:
  `EXECUTION_FAILED`, no content payload; and
- stable EOF, including offset at or past EOF: successful completed result with
  an empty bounded payload.

The mapping is structural. No caller reads an English detail sentence or raw
native error to decide disposition.

## 12. Implemented sequence

The first production-inert implementation performs this order:

```text
1. validate offset and max_bytes
2. FilesystemRoot lexical/current admission
3. admitted sensitive-name classification
4. capture admitted final identity
5. open and prove the configured NTFS root
6. acquire each component relative to the held parent
7. reject every reparse and wrong-kind component
8. acquire final with data-read rights and read-only sharing
9. prove final-handle containment
10. final handle-derived sensitive-name classification
11. compare admitted and acquired identity
12. take pre-read identity/size/last-write observation
13. build a capacity == max_bytes + 1 buffer and explicit 64-bit OVERLAPPED offset
14. issue exactly one synchronous ReadFile
15. classify the accepted EOF form or bounded read failure
16. take post-read identity/size/last-write observation
17. reject change, impossible count or unexplained short read
18. retain at most max_bytes and discard the lookahead
19. capture bounded provenance observation
20. close final, parents and root
21. only after close success: return the raw bounded observation
22. later Tool milestone only: NUL, BOM and strict UTF-8 interpretation
23. later Tool milestone only: construct successful payload and result
```

No step may reopen a path, expose a handle, perform a second read, or convert a
failed close into success.

## 13. Verification gates

Deterministic fake-API tests must cover:

- offsets 0, 1, `2^32 - 1`, `2^32`, and `2^63 - 1`;
- `max_bytes` 0, 1 and 65,536, proving native capacities 1, 2 and 65,537;
- invalid types, booleans, negative and over-bound values before native calls;
- full capacity with one-byte lookahead and no lookahead disclosure;
- exact EOF, crossing EOF, offset at EOF and offset past EOF;
- both accepted EOF forms where the injected API models them;
- positive and zero unexplained short reads becoming `read_incomplete`;
- impossible over-cap and beyond-size counts failing closed;
- pre/post identity, size and last-write changes independently;
- writer/share conflict with zero content bytes;
- read failure, observation failure and close failure on every seam;
- exact reverse handle closure and no result before close;
- source guards for one `ReadFile` call and no path/Python/mapping fallback; and
- no runtime, desktop, model, memory, research, evidence or telemetry-content
  registration.

Native Windows tests on local NTFS must cover ordinary, truncated, zero-length,
EOF, non-zero-offset, non-ASCII UTF-8, BOM, invalid UTF-8 and active-writer
cases. Packaging must bind `ReadFile` from the system `kernel32.dll` lazily and
repeat the normal startup smoke.

The implemented `v0.3.178` boundary has 64 focused rooted-open tests. The five
focused sensitive-path, rooted-open, payload, Tool-contract and text-policy
modules have 123 passing tests; the package-aware repository suite has 3,321
passing tests with three platform-dependent skips. Black, Ruff, the scoped
MyPy gate and whitespace validation pass. The local Windows onedir package builds and its
hidden-window startup smoke creates the isolated session registry without
disabling or bypassing a host security control. GitHub's Windows and Linux
package workflows remain the independent post-push gates for the exact commit.

The `v0.3.179` Tool seam separately tests NUL, strict UTF-8, range-split
multi-byte characters, payload invariants, effect authorization, lifecycle
privacy, single-call behavior and real Windows NTFS composition. Passing those
tests still does not authorize Tool registration.

## 14. Explicit non-decisions

This ADR does not authorize or design:

- `ToolRuntime` registration or product-facing composition of
  `FilesystemReadTool`;
- desktop preview or authorization controls;
- model, memory, RAG, research, graph, evidence or agent ingestion;
- persistence, export, clipboard, remote disclosure or generic content audit;
- POSIX/Linux descriptor-relative reading;
- ReFS, FAT, exFAT, SMB or third-party filesystems;
- binary, base64, hexadecimal or non-UTF-8 output;
- content hashing, secret scanning or sensitive-class override;
- automatic continuation, recursion, globbing or multi-file reads;
- asynchronous I/O, cancellation threads or memory mapping; or
- write, rename, delete, execute, shell or process authority.

Each remains a separate decision and separately authorized milestone.

## 15. Consequences

### Positive

- One documented Win32 data API is added to an already-owned handle boundary.
- Explicit offset and single-call capacity make the byte ceiling directly
  testable.
- Read-only sharing plus pre/post observation reduces the most ordinary
  concurrent-write ambiguity.
- The one-byte lookahead makes truncation independently observable without
  returning the extra byte.
- Close-before-result preserves the existing single-owner proof.

### Costs and residual risk

- Actively edited files may fail with a sharing violation.
- Synchronous I/O can block the calling thread; the initial local NTFS and
  65,537-byte boundary keeps that accepted risk narrow.
- A matching pre/post observation does not prove immutable content.
- A byte range can split UTF-8 and be declined even when the whole file is
  valid text.
- User-invocable Windows content reading remains unavailable until a later Tool
  milestone passes its separate gates, and Linux still needs its own measured
  descriptor-relative primitive.

These costs are accepted. The first content boundary should be small enough to
explain exactly, not broad enough to hide ambiguity.

## 16. Repository reality after implementation

At `v0.3.179`:

- `WindowsRootedOpen` is production-owned and production-inert;
- `WindowsOpenedFile` still exposes no handle, path or content;
- `read_range` acquires its final handle once, in the same root-relative walk,
  with exact data-read rights and read-only sharing;
- `WindowsContentRangeObservation` is immutable and carries no handle or
  absolute/native path;
- `FilesystemSensitivePathPolicy` runs before native acquisition and again on
  the final handle-derived name;
- `FilesystemContentPayload`, the separate content effect and the
  `ToolResult.content` channel exist as inert contracts;
- `FilesystemReadTool` applies the bounded text/failure policy to one injected
  observation but remains production-inert;
- `ToolRuntime` does not register `FILESYSTEM_READ`;
- desktop, model, memory, research, evidence and persistence receive no local
  file content; and
- the platform primitive binds one `ReadFile` call from fixed `kernel32.dll`;
  no `NtReadFile`, `SetFilePointerEx`, memory-map, Python content-open, retry,
  loop, or path reopen exists in this boundary.

The implementation is intentionally below the Tool boundary. Passing its
platform tests does not register or authorize `FILESYSTEM_READ`.
