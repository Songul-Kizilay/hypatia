# Desktop Application

## Status

The first local Tkinter shell is implemented for text chat, refreshable session
overview and explicit selection, selected-session details/recent/activity, and
explicit lexical/semantic recall, bounded cited knowledge context, and
semantic-runtime status. It also provides explicit local Markdown/text source
loading, source-catalog/graph views, source-relation controls, and guarded
session rename/delete flows. Its first Windows onedir package and local-data
boundary are defined in ADR 0002; broader MVP views remain planned.

## Purpose

Provide the first private, approachable place to interact with Hypatia's chat,
sessions, and explicitly requested memory status.

## Scope boundary

The implemented shell is deliberately narrow and delegates to `Brain`; it does
not add voice, a second data store, or a web surface. See the
[Desktop MVP v0.1 design](../Design/Desktop_MVP_v0.1.md) and
[ADR 0001](../Decisions/0001-tkinter-desktop-shell.md).
