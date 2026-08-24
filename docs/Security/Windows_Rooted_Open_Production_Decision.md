# Windows Rooted-Open Production Boundary

**Status: IMPLEMENTED AS A PRODUCTION-INERT FOUNDATION.**

**Decision date:** 2026-08-24

**Runtime at decision:** `v0.3.175 (Genesis)`

**Foundation implementation:** `v0.3.176 (Genesis)`

**Sensitive-name integration:** `v0.3.177 (Genesis)`

**Capability state:** `FILESYSTEM_READ` remains unregistered. No file-content
read is authorized or implemented by this decision.

**Next boundary:** the still-unimplemented read contract is accepted separately
in [Windows_Content_Range_Read_Decision.md](Windows_Content_Range_Read_Decision.md).

## 1. Decision

Hypatia has moved the measured Windows rooted-open construction from the
isolated experiment into a production-owned, still-inert platform boundary.
That boundary:

1. use `CreateFileW` only to acquire the configured absolute root;
2. use `NtCreateFile` with `OBJECT_ATTRIBUTES.RootDirectory` to acquire exactly
   one relative component at a time;
3. set `FILE_OPEN_REPARSE_POINT` on every component acquisition;
4. hold the root and every intermediate directory handle until the final proof
   is complete;
5. prove non-reparse kind, final-handle containment, configured-root identity,
   and final-entry identity before exposing an opaque opened-file object;
6. support an NTFS volume only in the first production boundary;
7. fail closed when any required API, proof, or filesystem property is absent;
8. own and close every native handle inside the platform module; and
9. classify sensitive names before native acquisition and again from the final
   handle-derived relative components before yielding; and
10. expose no raw handle, absolute path, OS error text, content, Tool Layer
   capability, runtime registration, or presentation integration.

This is a *foundation module*, not `filesystem_read`. The implementation reads
zero content bytes and remains absent from `ToolRuntime`.

## 2. Evidence used

The isolated experiment in
`experiments/prototypes/windows_rooted_open` passes nine adversarial tests on
the development host:

- Windows 11 (`Microsoft Windows NT 10.0.26200.0`)
- Python 3.14.5
- local NTFS volumes for both the repository and temporary test data

It proves an ordinary component walk, parent-junction replacement refusal,
final containment failure after an open parent is moved outside the root,
configured-root and final-file replacement detection, exception-path handle
closure, and zero content bytes read.

The production decision also relies on these Microsoft contracts:

- [`NtCreateFile`](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile)
  is documented as the user-mode equivalent of `ZwCreateFile`. A non-null
  `RootDirectory` makes `ObjectName` relative to that held directory, and
  `FILE_OPEN_REPARSE_POINT` bypasses normal reparse processing.
- [`GetFileInformationByHandleEx`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex)
  documents `FileAttributeTagInfo` for handle-derived file attributes and the
  reparse tag.
- [`GetFileInformationByHandle`](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandle)
  documents the volume-serial plus 64-bit file-index comparison used by the
  measured NTFS identity proof.
- [`GetFinalPathNameByHandleW`](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)
  returns the final resolved path and supports the NT device-name form used for
  handle-to-handle containment comparison.
- [`GetVolumeInformationByHandleW`](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew)
  reports the filesystem associated with an acquired handle and does not
  support SMB volume queries. It is the decisive NTFS/local-volume gate.
- [`RtlNtStatusToDosError`](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-rtlntstatustodoserror)
  converts `NTSTATUS` to a system error code for internal bounded
  classification; neither value nor message crosses the boundary.
- [`CloseHandle`](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-closehandle)
  is the approved user-mode close operation for the acquired handles.

The official identity documentation also says the older 64-bit file index is
not guaranteed unique on ReFS. ReFS therefore cannot inherit the NTFS decision.
Supporting it later requires a separate measurement and a `FILE_ID_INFO`
128-bit identity contract.

## 3. Why this API surface is accepted

`CreateFileW` has no parent-handle parameter. Calling it repeatedly with a full
path would recreate the validate-then-open race this work exists to remove.
`NtCreateFile` is now documented in `winternl.h`, exports from `ntdll.dll`, and
provides the exact root-relative name contract the proof needs. The production
boundary therefore accepts this one native entry point rather than pretending a
path-only Win32 call can provide equivalent containment.

The acceptance is narrow:

- only the documented `NtCreateFile` signature is bound;
- only `FILE_OPEN` is permitted; create, overwrite, supersede, append, delete,
  write, execute, and backup-intent options are forbidden;
- root, intermediate, and final handles request attributes and synchronization
  only; no file-data access bit is requested even if a component changes kind;
- the final handle may request `FILE_READ_DATA` only in the later, separately
  authorized content-read milestone;
- all required functions are loaded lazily after an `os.name == "nt"` gate;
- the loader uses the Windows system-DLL search path and accepts no configured
  DLL name or path; and
- absence of any symbol is a bounded `api_unavailable` failure with no fallback.

## 4. Module ownership and shape

Version `v0.3.176` adds one flat Tool Layer platform module, consistent with the
existing repository layout:

```text
src/tools/WindowsRootedOpen.py
```

It owns:

- native constants and exact `ctypes` structures;
- lazy `kernel32.dll` and `ntdll.dll` bindings;
- the bounded Windows rooted-open failure enum and exception;
- native handle ownership;
- configured-root identity capture;
- component-relative acquisition;
- handle-derived filesystem, kind, reparse, identity, and final-path queries;
- final containment proof;
- the production-inert `FilesystemSensitivePathPolicy` preflight and final-name
  gates; and
- later, only after a separate milestone, the bounded read operation on the
  already-proven handle.

The public production types are deliberately few:

```text
WindowsRootedOpen
WindowsRootedOpenFailure
WindowsRootedOpenError
WindowsOpenedFile
```

`WindowsRootedOpen.acquire(relative)` is a context manager. It yields an opaque
`WindowsOpenedFile`, never an integer handle. The opened object has no public
`handle`, `path`, or content field. Any later bounded read method remains inside
the same module, checks that the context is still open, and cannot be called
after closure.

`FilesystemRoot.locate` remains the lexical/current-admission precedent. It
does not become the decisive content boundary and its returned `Path` is never
opened for content. The platform module repeats the decisive proof against
handles.

No generic `platform` abstraction is added yet. A POSIX implementation has not
been measured, and inventing a common interface before two real platforms exist
would hide rather than resolve their different guarantees.

## 5. Packaging decision

The first production foundation uses only Python `ctypes` and Windows system
DLLs already present on the host:

- no new PyPI dependency;
- no compiled extension;
- no vendored DLL;
- no WDK runtime dependency;
- no PATH lookup;
- no application-local DLL fallback; and
- no import-time native binding.

This keeps Linux/POSIX imports safe: importing the module does not touch a
Windows symbol. Construction on a non-Windows host returns the bounded
`not_windows` failure. The module is not imported by `ToolRuntime`.

Windows packaging verification must include:

1. a normal module import in the packaged smoke test;
2. lazy binding of every required symbol on a Windows host;
3. the existing native adversarial suite; and
4. a source guard proving no application-supplied DLL path exists.

## 6. Supported filesystem boundary

The first production boundary supports only a handle whose
`GetVolumeInformationByHandleW` filesystem name is exactly `NTFS`
case-insensitively.

This is a security support boundary, not a claim that other filesystems are
unsafe. It reflects what was measured and what the selected identity contract
can prove. In particular:

- ReFS needs a 128-bit `FILE_ID_INFO` measurement before support;
- SMB/network roots do not provide the selected handle-volume query and are
  unsupported;
- FAT/exFAT were not measured for identity, replacement, or containment; and
- third-party filesystems require their own adversarial evidence.

An unsupported filesystem fails before a final opened object can be yielded.
There is no path-based fallback and no “best effort” mode. Adding a filesystem
later requires an explicit allowlist change plus platform tests.

## 7. Handle lifetime and close semantics

Handle ownership is lexical and single-owner:

1. every successful native acquisition is wrapped immediately;
2. every wrapper is registered with an `ExitStack` before the next seam;
3. the root and all parent handles remain live through final containment and
   identity proof;
4. the final handle remains live only inside the `acquire` context;
5. close is idempotent and clears the stored numeric value;
6. no `__del__` or garbage-collection timing is part of correctness; and
7. every normal, declined, failed, cancelled, and exception branch closes all
   acquired handles in reverse order.

If `NtCreateFile` returns a non-success status with a non-null output handle,
the boundary closes that handle before classifying the failure. The
implementation accepts only the documented success result; warning-like status
values do not silently become success.

`CloseHandle` failure is bounded as `close_failed`. A future content tool must
not construct `FilesystemContentPayload` or a successful `ToolResult` until the
context has exited and all closes have succeeded. Bytes buffered during a read
are discarded if close fails. Close failure must not be hidden by a successful
content result.

## 8. Proof order

The production foundation must perform this order without a shortcut:

```text
1. FilesystemRoot.locate(relative) for lexical/current admission
2. split only the already-admitted relative components
3. classify those canonical components with Windows name normalization
4. capture admitted NTFS volume serial + 64-bit file index
5. open the configured absolute root with CreateFileW, no reparse following
6. query root attributes, NTFS filesystem, NT final path, and identity
7. compare root identity with the identity captured at acquirer construction
8. NtCreateFile one component relative to the held parent
9. query that handle; reject every reparse point
10. require directory kind for intermediates and regular-file kind for final
11. retain every parent handle and repeat until final
12. query root and final paths in VOLUME_NAME_NT normalized form
13. derive the final relative components and prove strict-root descent
14. classify the final handle-derived components with Windows normalization
15. compare admitted and final NTFS identities when the class is not refused
16. only then yield the opaque, still-owned opened-file object
17. close final, parents, and root before any successful result is built
```

The final-path comparison is a handle-derived secondary proof, not authority to
open another path. Neither final path is returned, logged, placed in an
exception, or copied into telemetry.

## 9. Failure and error mapping

The low-level boundary uses a bounded enum. Initial members are:

| Failure | Meaning |
| --- | --- |
| `not_windows` | Platform cannot provide the Windows proof |
| `api_unavailable` | A required system DLL symbol is absent |
| `unsupported_filesystem` | Handle is not on the explicitly supported NTFS boundary |
| `path_refused` | Existing `FilesystemRoot` policy refused the request |
| `entry_changed` | Admission and acquisition no longer describe one entry |
| `not_file` | The requested target is not a regular file |
| `root_changed` | Configured-root identity no longer matches |
| `open_failed` | A required handle could not be acquired |
| `reparse_point` | An acquired component is an indirection |
| `not_directory` | An intermediate component is not a directory |
| `containment_unproven` | Handle-derived final containment could not be proven |
| `identity_mismatch` | Admitted and opened file identities disagree |
| `sensitive_file` | Preflight or final handle-derived name belongs to one bounded sensitive class |
| `close_failed` | Native handle closure did not complete successfully |

The exception carries only the enum, the existing `FilesystemPathRefusal` for
initial admission, and exactly one `FilesystemSensitiveClass` only for a
`sensitive_file` refusal. It carries no relative path, basename, absolute path,
raw `NTSTATUS`, Win32 code, system error string, DLL path, or native handle.

`RtlNtStatusToDosError` and `GetLastError` may be used internally to select a
bounded enum. Their numeric values are not domain output and are not telemetry.
Unexpected codes map to the conservative existing category (`open_failed`,
`containment_unproven`, or `close_failed`) for the stage where they occurred.

The future tool mapping remains the one already decided in the content design:

- malformed or initially refused request: `declined`;
- initially admitted directory/non-file: `declined`;
- a structurally reported sensitive class: `declined`, with fixed wording naming
  the class rather than the path;
- entry changed after admission, unavailable proof, permission failure,
  identity mismatch, unsupported runtime/filesystem, or close failure: `failed`;
- missing content effect: `not_reached`; and
- no raw native detail crosses any result or lifecycle boundary.

## 10. Test and release gates for the foundation milestone

The production foundation is covered by tests for:

- ordinary local NTFS acquisition, zero bytes, and no raw handle/path output;
- import and bounded `not_windows` construction on a non-Windows test path;
- unavailable symbol and unsupported filesystem failure;
- initial traversal/link refusal;
- root replacement;
- parent replacement by junction after admission;
- final replacement by file and by junction;
- moving an already-open parent outside the root;
- intermediate non-directory and final directory;
- final-path query failure;
- identity mismatch;
- sensitive-name preflight before native open and final-name reclassification
  after containment/identity proof;
- `NtCreateFile` failure with a defensive close of a non-null output handle;
- close-on-success and close on every deterministic exception seam;
- close failure preventing successful proof output;
- no content read/write/process/ToolRuntime/model imports; and
- no production import from the experiment package.

The existing nine-test prototype remains passing independent evidence. The
production suite uses injectable API bindings and deterministic seams rather
than making release correctness depend on timing a race. Native Windows tests
repeat the ordinary, replacement, junction, containment, and closure checks
against the system APIs.

## 11. Explicit non-decisions

This ADR does not authorize or design:

- `filesystem_read` tool implementation or registration;
- `ReadFile`, `NtReadFile`, Python `open`, or any content bytes;
- a desktop file-preview control;
- model, memory, research, evidence, persistence, or telemetry content;
- POSIX/Linux descriptor-relative opening;
- ReFS, FAT, exFAT, SMB, or third-party filesystem support;
- sensitive-file override UX;
- remote-provider disclosure; or
- autonomous tool selection or chaining.

Those remain separate milestones with separate authority.

## 12. Consequences

### Positive

- The Windows foundation reuses a measured construction rather than inventing a
  second path policy.
- Every security-critical native dependency and failure boundary is explicit
  before production code exists.
- Packaging remains dependency-free and fail-closed.
- The raw handle stays in one module, which prevents future tools from bypassing
  containment or ownership.
- NTFS support is honest about the evidence available today.

### Costs

- Initial Windows support is narrower than the APIs could theoretically allow.
- Native `ctypes` declarations and lifetime tests become security-critical.
- A future POSIX implementation will be structurally different and cannot be
  inferred from this one.
- Real content access remains unavailable after the foundation milestone.

These costs are accepted. A broader but unproven filesystem boundary would make
Hypatia appear more capable while weakening the one property the capability
must never guess: which file it actually opened.
