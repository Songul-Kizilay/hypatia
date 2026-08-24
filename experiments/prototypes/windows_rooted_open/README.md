# Windows Rooted-Open Safety Prototype

**EXPERIMENT ONLY — NOT A PRODUCTION CAPABILITY.**

This prototype tests the blocking open-time invariant in
`docs/Security/Filesystem_Content_Access_Design.md`. It registers no Tool Layer
capability, adds no `ToolEffect`, returns no live handle, and reads zero content
bytes.

The experiment:

1. reuses `FilesystemRoot.locate` for the existing lexical/current admission;
2. opens the configured root with reparse processing disabled;
3. opens exactly one path component at a time relative to the held parent handle;
4. checks every acquired handle for the reparse attribute;
5. proves the final handle path is beneath the held root handle path;
6. compares the admitted and opened file identities as defence in depth;
7. closes every handle before returning bounded proof metadata.

It uses the Windows native `NtCreateFile` `RootDirectory` contract because
`CreateFileW` has no parent-handle argument. The prototype is evidence, not a
decision that this native API belongs in production.

Pass criteria are deterministic tests for an ordinary file, root replacement,
parent replacement by a junction after admission, moving an already-open parent
outside the root, final-entry replacement, path refusal, and a source guard that
forbids content reads, writes, shell/process execution, Tool Layer registration,
and model integration.

## Measured result

On the development host (Windows 11, Python 3.14.5), all nine focused tests
pass. The prototype:

- acquires an ordinary file through a component-by-component root-relative walk;
- refuses a parent changed to a junction after admission;
- fails final containment when an already-open parent is moved outside the root;
- detects replacement of the configured root and of the final file;
- closes held handles when a deterministic seam raises; and
- returns bounded proof metadata with `content_bytes_read == 0`.

This result proves that the candidate construction is testable on this host. It
does not approve the native API wrapper for production, settle packaging and
support policy, prove behaviour on every Windows filesystem, or resolve the
separate POSIX strategy. `filesystem_read` therefore remains unimplemented.
