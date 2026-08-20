# ADR 0002: Package the initial Windows desktop application with PyInstaller

## Status

Accepted

## Context

The Tkinter desktop shell is useful only when it can start outside a developer
checkout. The repository did not yet define a reproducible Windows package,
update policy, or a user-writable persistence location. The source checkout's
`data/` directory is appropriate for development and tests, but an installed
application may not have permission to write beside its executable.

## Decision

The first supported distributable target is **Windows**, built as an onedir
package with PyInstaller `6.21.0`. The checked-in
[`tools/build_desktop.ps1`](../../tools/build_desktop.ps1) script builds
`dist/Hypatia/Hypatia.exe` from `src/desktop_main.py`; its only packaging
dependency is pinned in
[`requirements-desktop-build.txt`](../../requirements-desktop-build.txt).

The desktop entry point uses these user-owned paths by default:

```text
%LOCALAPPDATA%\Hypatia\memory\memory.json
%LOCALAPPDATA%\Hypatia\sessions\sessions.json
%LOCALAPPDATA%\Hypatia\knowledge\relations.json
%LOCALAPPDATA%\Hypatia\research\runs.json
```

`HYPATIA_DESKTOP_DATA_DIR` may override the root only with an absolute path.
This supports a deliberate backup or portable-storage policy without silently
falling back to the working directory. The terminal entry point intentionally
retains the existing repository `data/` defaults for developer compatibility.

Updates are manual in this first package: a user downloads a new published
release and replaces the installed package after closing Hypatia. The runtime
does not self-update, download code, transmit telemetry, bundle credentials, or
migrate data automatically. Existing developer-checkout data is not copied into
the desktop data directory automatically; migration/export needs a separately
reviewed user-facing flow.

## Consequences

- The package is reproducible with the project virtual environment and leaves
  build outputs in ignored `build/` and `dist/` directories.
- The first distribution is Windows-specific and intentionally remains an
  onedir package, so bundled Python/Tkinter files stay inspectable and updates
  are simple file replacement.
- macOS/Linux packaging, signing, an installer, automatic updates, backup,
  data migration, and a full accessibility audit remain separate increments.
- The package uses the same Bootstrap and Brain boundary as source execution;
  packaging adds no browser, web server, cloud service, or second data store.
