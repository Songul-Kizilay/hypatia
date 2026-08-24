# Read-Only Filesystem Capability — Design Proposal

**Status: PROPOSED. NOT IMPLEMENTED.** No filesystem capability, effect, tool,
or code exists in the runtime as of `v0.3.167`. This document exists so that the
decisions below are reviewable before anything can act on them.

The findings in the Windows section were measured on the development machine
(Windows 11, Python 3.14.5, `D:\hypatia-main`), not recalled. Several of them
contradict what the obvious implementation would assume, which is the reason
this document was written before the code.

## 1. Why this is the hard one

The two existing tools are safe by construction. `ClockReadTool` reads a clock;
`TextStatisticsTool` counts what it was handed. Neither can be pointed at
anything. A filesystem tool is the first capability where **the argument selects
the target**, so for the first time the interesting question is not "what does
this tool do" but "what was it aimed at, and who aimed it".

That changes the threat model. Until now, a bad argument could produce a wrong
answer. Here, a bad argument can produce a *correct answer about the wrong
thing*, which is worse, because nothing looks broken.

## 2. Proposed capability names

Three capabilities, not one:

| Capability | Answers | Status |
| --- | --- | --- |
| `filesystem_list` | what entries exist directly under one authorized directory | proposed first |
| `filesystem_metadata` | size, kind, and timestamps of one named entry | proposed second |
| `filesystem_read` | file contents | **not proposed** |

A single `filesystem` capability would be a mistake that cannot be undone later.
Every grant of it would carry every future filesystem ability, including ones
added after the grant was written. Splitting them means a caller authorized to
enumerate a directory has not thereby been authorized to read what is in it —
and that is the whole difference between "there is a file called
`tax-return.pdf`" and knowing its contents.

`filesystem_execute`, or any capability that starts a process, is explicitly out
of scope permanently, not merely deferred. It is named here only so that its
absence is a recorded decision rather than an oversight.

## 3. Proposed effect model

**Add `READS_FILESYSTEM_METADATA`. Do not reuse `READS_LOCAL_STATE`.**

`READS_LOCAL_STATE` currently means "reads state this application owns" — a
clock, an in-process index. A filesystem listing reads state the *user* owns and
the application did not create. Collapsing the two would mean any existing grant
of `READS_LOCAL_STATE` silently becomes a grant to enumerate the disk, which is
authority acquired by renaming rather than by decision.

The tradeoff runs the other way too, and the goal is least privilege rather than
maximum enum granularity. So: one new effect covering both listing and
metadata, not one per capability. The capability split already separates listing
from reading; a second, parallel split in the effect vocabulary would add
ceremony without adding a decision anyone would actually make differently.

If `filesystem_read` is ever proposed, it must introduce its own effect. Content
is a different kind of secret from names.

## 4. Authorized root

The root is **operator configuration, never an argument**. If the root could be
passed in the invocation, the tool would have unrestricted filesystem authority
with extra steps: the caller would simply supply `C:\` as the root.

Proposed representation:

- A frozen value object holding one already-resolved absolute directory.
- Resolution and existence checked once, when it is constructed, not per call.
- A stable opaque `root_id` (for example `root-1`) minted at construction, used
  in telemetry in place of the path. See §8.
- No default. A runtime with no configured root has no filesystem capability
  registered at all — not a registered tool that refuses everything, because a
  registered-but-refusing tool is one config mistake away from working.

The invocation supplies only a **relative** path within that root.

## 5. Canonicalization — measured behaviour

Proposed algorithm, in order:

1. Reject the argument outright if `PureWindowsPath(arg)` has a drive, has an
   anchor, or `is_absolute()`. This rejects `C:\Windows`, `C:src`,
   `\\server\share\x`, `\\?\D:\...`, `\\.\PhysicalDrive0`, and `\Windows`.
2. Join to the root and call `.resolve()`.
3. Require `resolved.is_relative_to(root)`.
4. Require the entry to exist, via `strict=True` resolution or an `lstat`.
5. Apply the link policy in §6 to **every** component, not only the leaf.

Step 3 is not optional even though step 1 already rejects the obvious escapes,
and step 1 is not redundant even though step 3 catches everything: the two
disagree about *why* a path was refused, and the error taxonomy in §10 depends
on the distinction.

### What was measured

| Input | Resolves to | Inside root? |
| --- | --- | --- |
| `src` | `D:\hypatia-main\src` | yes |
| `..\..\Windows` | `D:\Windows` | **no** |
| `src\..\..\Windows\System32` | `D:\Windows\System32` | **no** |
| `/Windows` | `D:\Windows` | **no** |
| `C:\Windows` | `C:\Windows` | **no** |
| `src/core` (forward slashes) | `D:\hypatia-main\src\core` | yes |

`resolve()` plus `is_relative_to()` handles `..`, mixed separators, and rooted
paths correctly. Note the third and fourth rows: a leading `/` is **not**
absolute on Windows — it inherits the root's drive and lands in `D:\Windows`.
An implementation that special-cased `..` and forgot rooted paths would let that
through.

### String prefixes are provably wrong

```
str(r"D:\hypatia-main-secrets\notes.txt").startswith(r"D:\hypatia-main")  -> True
Path(r"D:\hypatia-main-secrets\notes.txt").is_relative_to(r"D:\hypatia-main") -> False
```

A sibling directory whose name merely begins with the root's name passes a
prefix check. This is the single most likely implementation mistake and it is
silent, so it must be a named test.

## 6. Windows-specific findings

These were measured, and three of them are traps.

### Names that are not the name

All four of these resolve to `D:\hypatia-main\src` and report `exists=True`:

| Argument | Resolves to |
| --- | --- |
| `SRC` | `D:\hypatia-main\src` |
| `src.` (trailing dot) | `D:\hypatia-main\src` |
| `src ` (trailing space) | `D:\hypatia-main\src` |
| `src::$INDEX_ALLOCATION` | `D:\hypatia-main\src` |

Windows silently strips trailing dots and spaces, and NTFS accepts stream syntax
on a directory. **Consequence: any policy that compares the argument text
against a name is defeatable.** All decisions must be made on the resolved path,
never on the string that was passed. A denylist of names would be worse than
useless, because it would look like it worked.

### Alternate data streams

| Argument | `Path.name` | Resolves to | Exists |
| --- | --- | --- | --- |
| `README.md` | `README.md` | `...\README.md` | yes |
| `README.md:hidden` | `README.md:hidden` | `...\README.md:hidden` | no |
| `README.md::$DATA` | `README.md::$DATA` | `...\README.md` | **yes** |

`README.md::$DATA` resolves to the plain file and exists, while `Path.name`
still carries the stream syntax. So `name` is not trustworthy for policy either.
**Proposal: reject any argument containing `:` after the drive-letter check has
already run.** At that point a colon can only be stream syntax, since a legal
relative path inside a root has no other use for one.

### Reserved device names

`NUL` reports `exists=True` in any directory, including inside the root. `CON`,
`COM1`, and `con.txt` reported `exists=False` here, but the device namespace is
reachable by name from every directory and does not correspond to a real entry.

For a listing-and-metadata tool this is a correctness problem rather than a
disclosure one — `os.scandir` will not enumerate them, so they can only arrive
as an explicit argument. **Proposal: reject the reserved set by resolved stem,
case-insensitively.** Not because metadata on `NUL` is dangerous, but because
returning a confident answer about a device that is not a file is exactly the
"correct answer about the wrong thing" failure from §1.

### Case insensitivity

`SRC` and `src` are the same directory. This is not a bypass by itself — both
resolve inside the root — but it means the tool must never assume the name it
returns matches the name it was given, and comparisons between the two must be
case-insensitive or, better, not happen at all.

## 7. Symlink and junction policy

The invariant, stated precisely:

> A path is admissible only if its **fully resolved** target is inside the
> authorized root, and no component traversed to reach it was a link that
> pointed outside the root.

Lexical containment is not containment. `root\link -> C:\Users\...` is
lexically inside and actually outside.

Python 3.14 on this machine provides everything needed: `Path.resolve()`
follows links, `Path.is_symlink()` and `Path.is_junction()` both exist, and
`os.stat_result` exposes `st_file_attributes` and `st_reparse_tag`.
`os.scandir` entries answer `is_dir(follow_symlinks=False)` and `is_symlink()`
without a second syscall.

Proposed policy for the first tool: **do not follow links at all.** A listing
reports a link as a link — kind `link`, no target, no metadata about whatever it
points at — and metadata on a link describes the link itself. Following is
strictly more useful and strictly more dangerous, and the first version does not
need to make that trade.

Required tests, all of which need a real link created in a temporary directory
(not a mock, since the entire question is what the filesystem does):

- a symlink inside the root pointing outside it is refused as a traversal
  target and reported as a link when listed;
- a junction inside the root pointing outside it, tested separately, because
  junctions and symlinks are different reparse types and an implementation can
  easily handle one and not the other;
- a link *inside* the root pointing *inside* the root is still not followed;
- a link as a non-final component (`root\link\file.txt`) is refused, proving the
  check runs per component rather than on the leaf only;
- a directory that merely shares a name prefix with the root is refused.

If the test environment cannot create links without elevation, the test must
skip loudly with a stated reason, never pass silently.

## 8. Telemetry privacy

Paths are the most sensitive thing this capability touches, and a directory name
can disclose more than a file's contents — `private-investigation`,
`layoff-list-final`, a client's name, a diagnosis. The existing event contract
already carries counts rather than contents, and filesystem events must not be
the exception that breaks it.

**Proposal: no lifecycle event ever carries a path, a path fragment, or an entry
name.** The existing payload keys stay as they are, plus:

| Key | Meaning |
| --- | --- |
| `root_id` | opaque stable id of the authorized root, never the root path |
| `path_depth` | integer component count of the requested relative path |
| `entry_count` | number of entries returned |
| `truncated` | whether a bound was hit |

`path_depth` is a deliberate compromise: it is a small leak of shape and no leak
of content, and it is the one signal that makes "why is this slow" answerable
without an audit trail of what the user looked at.

The `ToolResult` **does** carry entry names — that is the answer the caller
asked for. The distinction is the point: results go to whoever invoked the tool,
events go to logs, subscribers, and eventually a screen. Conflating the two is
how the interesting parts of a private directory end up in a log file that
outlives the question. A sentinel-named directory should be asserted absent from
every payload, exactly as `TextStatisticsTool` asserts for its text.

## 9. Output bounds

| Bound | Proposed | Reason |
| --- | --- | --- |
| `MAX_ENTRIES` | 200 | the root of this repository already holds 54 entries; `node_modules` or `.git` internals would be thousands |
| `MAX_NAME_LENGTH` | 255 | the NTFS component limit, so no legal name is truncated |
| depth | 1 | one directory, one level |
| recursion | none | see below |

Existing `ToolResult` bounds (`MAX_TOOL_VALUES = 20`,
`MAX_TOOL_VALUE_LENGTH = 300`) are far too small to carry 200 entries as
individual values. **This is an unresolved design question and the main reason
the listing tool is not trivial.** Three options, none free:

1. Return one value per entry and raise `MAX_TOOL_VALUES` — but that bound
   protects every other tool, and raising it for one capability weakens it for
   all of them.
2. Return a single joined value — but 300 characters holds only a handful of
   names, and a separator can appear in a filename.
3. Return counts plus a bounded page of names, with explicit `truncated` and
   `entry_count` values — the caller learns the true total and sees some of it.

Option 3 is the recommendation. It keeps every existing bound intact and it is
honest about the gap between what exists and what was returned, which is the
same distinction the research layer already draws between "discovered" and
"accepted". Truncation must be reported, never silent: a listing that quietly
stopped at 200 is a listing that says a directory is smaller than it is.

No recursion in the first tool. A recursive listing is an unbounded traversal
wearing a bound, and every one of the link problems in §7 recurs at every level.

## 10. Error taxonomy

All of these are **tool failures**, not authorization refusals:
`performed=True, succeeded=False`, following the semantics
`TextStatisticsTool` established. The gate refuses; the tool declines.

| Condition | Fixed detail |
| --- | --- |
| argument missing | requires a `path` argument |
| unknown argument | accepts only a `path` argument |
| absolute, rooted, drive-relative, or UNC | must be relative to the authorized root |
| contains stream syntax | not a valid path |
| escapes the root after resolution | outside the authorized root |
| link component | not followed |
| reserved device name | not a file |
| does not exist | no such entry |
| not a directory (`filesystem_list`) | not a directory |
| permission denied by the OS | could not be read |

Two rules carry over unchanged. **No detail may quote the argument**, for the
same reason `TextStatisticsTool` quotes nothing: an error message is the easiest
place for input to escape and the hardest place to notice it did — and here the
input is a path. **No raw `OSError` text may cross the boundary**, since
`WinError` strings interpolate the full path.

One deliberate ambiguity: "does not exist" and "outside the root" should arguably
be the same message, because distinguishing them lets a caller probe for the
existence of paths it cannot reach. The recommendation is to keep them distinct
anyway — the caller already knows the root, so the oracle tells it nothing it
could not compute — but this should be an explicit decision when the tool is
built, not a side effect of writing the error list.

## 11. TOCTOU — what cannot be promised

The sequence is inherently racy:

```
validate path  →  [filesystem may change]  →  read metadata
```

Between resolution and `scandir`, a directory can be deleted, replaced, or
turned into a junction pointing anywhere. Python offers no atomic
validate-and-open for a directory listing, and `O_NOFOLLOW` equivalents on
Windows do not close the window for a multi-component path.

**What the implementation can promise:** the path was inside the root at the
moment it was checked; no component was a link at that moment; results are
bounded; an entry that vanishes mid-listing is reported as gone rather than
guessed at.

**What it cannot promise:** that the path was still inside the root when it was
read. An attacker with write access to the root directory can win the race.

That last sentence is the honest statement and it should appear in the module
docstring, not only here. The mitigating fact is that such an attacker already
has write access to the user's project directory, so the filesystem tool is not
the weakest thing available to them. That is a reason to accept the risk for a
read-only metadata tool — it is **not** a reason to accept it for
`filesystem_read`, where the prize is contents rather than names.

## 12. What the first filesystem tool will explicitly NOT do

- read file contents
- write, create, delete, rename, or move anything
- follow symlinks or junctions
- recurse
- accept an absolute path, a drive letter, a UNC path, or an extended-length path
- accept the root as an argument
- resolve environment variables or `~` in the argument
- return owner, ACL, or security-descriptor information
- put any path into any lifecycle event
- execute anything, ever

## 13. Recommended first milestone

`filesystem_list` alone, with `READS_FILESYSTEM_METADATA`, an operator-configured
root, no link following, no recursion, and option 3 bounded output.

`filesystem_metadata` should follow separately even though it is smaller, because
it is the capability that answers questions about a *named* entry and therefore
carries the probing-oracle concern in §10 on its own terms.
