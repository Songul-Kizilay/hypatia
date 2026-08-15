# Design

This area records user flows, interface concepts, accessibility requirements,
and technology decisions for user-interface increments.

## Current designs

| Design | Status | Purpose |
| --- | --- | --- |
| [Desktop MVP v0.1](Desktop_MVP_v0.1.md) | Initial shell implemented | Define the local desktop boundary and its next test-first increments. |

Tkinter is selected through [ADR 0001](../Decisions/0001-tkinter-desktop-shell.md).
The initial window provides only text chat, session selection, and semantic
status through the existing Brain. The current executable boundary remains the
[Architecture Audit v0.1](../Architecture/Architecture_Audit_v0.1.md) and
[`PROJECT_STATUS.md`](../../PROJECT_STATUS.md).
