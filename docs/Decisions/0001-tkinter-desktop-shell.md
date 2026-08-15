# ADR 0001: Use Tkinter for the first desktop shell

## Status

Accepted

## Context

The [Desktop MVP v0.1](../Design/Desktop_MVP_v0.1.md) requires a first local
desktop surface for existing chat, session, and runtime-status flows. It also
requires that framework selection happen before UI code is merged.

Hypatia's executable core is Python 3.14+, has no UI dependency, and keeps
local persistence and optional provider configuration inside the existing
Bootstrap/Brain boundary. The selected environment provides Tkinter 8.6 with
the configured Python runtime.

The first shell must not create a web server, browser navigation surface,
separate local data store, telemetry channel, or packaging assumption that
would obscure the local-first boundary.

## Decision

Use Python's standard-library Tkinter toolkit for the first desktop shell.

The initial UI will be a thin adapter over an already constructed `Brain`. It
will start with text conversation, session selection, and explicit semantic
runtime status. It will not bypass Brain, call stores directly, or introduce
any new network client.

## Alternatives considered

- **Local web view / Electron-style shell:** deferred because it adds a browser
  security and navigation policy before the MVP has demonstrated user value.
- **Third-party Python toolkit:** deferred because it adds a packaging and
  dependency decision without a requirement that Tkinter cannot satisfy.
- **Keep only the terminal CLI:** retained as a supported developer entry
  point, but it does not satisfy the desktop MVP's approachable user surface.

## Consequences

- The first shell can run from the existing Python environment with no new
  runtime dependency.
- UI tests must separate controller/presentation behavior from real window
  creation so they run in headless environments.
- A future cross-platform packaging, visual system, web view, or richer
  accessibility requirement may supersede this ADR through a new decision.
- Voice, document import, agent tools, web research, and cloud features remain
  outside the first shell.
