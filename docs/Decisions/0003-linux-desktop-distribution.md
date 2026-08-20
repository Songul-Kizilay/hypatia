# ADR 0003: Package the Linux desktop application with PyInstaller

## Status

Accepted

## Context

Hypatia's Tkinter desktop and installed-application data boundary are portable,
but the repository previously offered only a Windows package command and a
Windows release artifact. Linux users had no reproducible build or real startup
verification, and the existing XDG data-path behavior lacked direct tests.

## Decision

The first supported Linux target is **Ubuntu 24.04 x64**, built as a PyInstaller
`6.21.0` onedir package. The checked-in `tools/build_desktop.sh` script builds
`dist/Hypatia/Hypatia` from `src/desktop_main.py` using the repository `.venv`.
The package is distributed as `Hypatia-linux-x64-v0.3.44.tar.gz`.

Installed Linux desktop state follows the XDG data-directory convention:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/hypatia/memory/memory.json
${XDG_DATA_HOME:-$HOME/.local/share}/hypatia/sessions/sessions.json
${XDG_DATA_HOME:-$HOME/.local/share}/hypatia/knowledge/relations.json
${XDG_DATA_HOME:-$HOME/.local/share}/hypatia/research/runs.json
```

Only an absolute `XDG_DATA_HOME` is honored. The existing absolute
`HYPATIA_DESKTOP_DATA_DIR` override takes precedence on every platform.

GitHub Actions builds the Linux artifact on Ubuntu 24.04, runs the complete
automated and static-quality suite, launches the packaged Tkinter application
under Xvfb, and verifies that state initializes beneath a temporary explicit
data directory. The test leaves no persistent user data.

Updates remain manual. The package does not self-update, transmit telemetry,
bundle credentials, copy developer-checkout state, or change the Windows data
path and package contract.

## Consequences

- Linux users receive a reproducible archive that runs outside a source
  checkout while keeping state in a user-owned XDG directory.
- The package targets glibc-based Ubuntu 24.04 x64; other distributions and CPU
  architectures require separate verified builds.
- macOS packaging, signing, installers, automatic updates, and data migration
  remain separate increments.
