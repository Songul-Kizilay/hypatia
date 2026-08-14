# Security

## Reporting a vulnerability

Do not include private conversation data, API keys, or exploit details in a public
issue. Report a suspected vulnerability privately to the repository owner with a
minimal reproduction, affected version or commit, impact, and any relevant logs
with secrets removed.

## Security baseline

Hypatia is currently a local-first CLI. Runtime conversation and memory files are
local data and must not be committed. Optional LLM credentials are supplied only
through `HYPATIA_LLM_API_KEY`; remote LLM endpoints must use HTTPS, while plain
HTTP is restricted to loopback endpoints for local runtimes.

Before enabling a networked UI, plugins, or remote storage, update the threat
model and add authentication, authorization, data-sharing, and audit controls.
