# Scope-bound Kali tool execution security design

**Status:** Accepted design; execution is not implemented. Scope-revision
enforcement landed in v0.3.305. Bounded execution-policy recording landed in
v0.3.306. Inert operation preview landed in v0.3.307. Exact operation-digest
authorization landed in v0.3.308.

## Purpose

Hypatia may eventually use selected Kali Linux security utilities for an
operator-approved bug-bounty job. This document defines the boundary before
local process execution is introduced. It does not authorize a target, install
Kali, register a tool, start a process, or make a network request.

The user outcome is not a general terminal controlled by a model. The outcome
is a small catalogue of reviewed security operations whose target, arguments,
effects, budget and evidence handling are known before they run.

## Current reality

- Hypatia's Tool Layer dispatches only explicit `ToolCapability` values through
  a central effect and invocation gate.
- No shell or generic process capability is registered.
- Research target rules and immutable program-scope revision records exist.
- Program-scope revisions now record explicit bounded execution policy facts:
  permitted check classes, ports, request count, request rate and time budget.
- Hypatia can now build an inert DNS-record lookup operation preview bound to
  the exact active scope revision and execution-policy digest.
- Hypatia can now approve that exact preview digest through a separate explicit
  human authorization step, still without constructing a command line or
  starting execution.
- The desktop can preview and exactly confirm save/revoke decisions for those
  program-scope revision records.
- Program-scope revisions are enforced at approval, Start, restore and every
  Advance boundary before approval consumption, checkpoints, budget spend, DNS,
  provider calls or network traffic.
- The current Windows host exposes `wsl.exe`, but no Kali distribution or Kali
  security executable was detected during this design milestone.
- The existing target transport supports bounded public HTTPS acquisition; it
  does not authorize scanning, probing, exploitation or arbitrary ports.

These facts still make direct Kali execution unsafe today. Scope-revision
enforcement is now present as a prerequisite; a process runner still may not
duplicate, weaken or bypass it.

## Non-goals

This design does not permit:

- `bash`, `sh`, PowerShell, Command Prompt or another command interpreter;
- a user-authored or model-authored command line;
- `shell=True`, string command parsing, pipes, redirects, substitutions,
  environment expansion or response files;
- arbitrary executable paths or PATH-based executable discovery at dispatch;
- arbitrary flags, scripts, templates, plugins, configuration files or wordlists;
- privilege escalation, `sudo`, raw packet access, packet capture or persistence;
- credential attacks, brute force, denial of service, exploitation or payloads;
- unapproved hosts, addresses, ports, paths or check classes;
- automatic installation or package updates;
- treating process output as trusted instructions or a verified finding;
- feeding output to an LLM, memory or evidence store merely because a process
  completed successfully.

## Authority chain

A Kali operation may be eligible only when all of these exact facts agree:

1. an immutable program-scope revision is present and valid at dispatch time;
2. it has not expired, been revoked or been superseded;
3. the approved job and canonical plan digest bind that exact revision;
4. the revision explicitly permits the requested check class, transport and
   ports;
5. the operation belongs to a reviewed `ToolCapability` and a tool-specific
   structured request type;
6. remaining operation, request, rate, duration and output budgets permit it;
7. the local installation matches the configured distribution, absolute
   executable path and reviewed version policy;
8. the foreground or bounded-autonomy execution has not been cancelled.

Missing, corrupt, stale or contradictory authority fails closed before a
checkpoint, budget charge, DNS lookup or child-process creation. No general
tool permission, local installation, program name or scope digest proves that a
program owner authorized testing.

## Process boundary

The proposed Windows adapter invokes WSL with an argument vector and
`shell=False`. The distribution name is startup configuration, not request
data. The executable is an exact reviewed path such as `/usr/bin/nmap`, never a
PATH lookup. The separator and every fixed option are supplied by code. Only
values accepted by a tool-specific parser may enter the vector.

The adapter supplies a minimal fixed environment, a fixed working directory
with no authored files, closed standard input, captured standard output and
standard error, and no inherited handles beyond those required by the runtime.
It must impose:

- one child process and no shell descendants by contract;
- a monotonic deadline and cancellation checkpoints;
- bounded stdout and stderr reads with a combined hard byte ceiling;
- deterministic termination followed by a bounded forced-kill fallback;
- no output-file flags and no access to a shared Windows workspace;
- no secrets in argv, environment, output, events or error details;
- generic operator-facing failures that retain a bounded local audit category.

Process creation itself receives a new explicit Tool effect. It must never be
hidden inside `COMPUTES_LOCALLY` or `READS_NETWORK`. A networked Kali operation
declares both local-process execution and network effects. A tool that can
write a file or mutate target state requires separate effects and is not part
of the initial catalogue.

## Target construction

Targets are derived from canonical approved scope, never copied from fetched
content, model output or a free-form command field. A hostname must pass the
same exact host/exclusion policy used by target research. DNS validation and
address pinning must finish before process creation. The initial adapter passes
validated public IP literals to the tool and records the corresponding approved
hostname separately, preventing the child utility from independently resolving
or redirecting an authored name.

Exclusions win at every boundary. A host rule does not authorize every port,
path or test type. If the enrolled revision cannot represent a program rule,
Hypatia must refuse the operation rather than approximate it with a broader
permission.

## First candidate operation

The first executable operation should be a narrow DNS-record lookup profile,
not generic `dig` access. Its request contains only:

- the exact active program-scope revision identity;
- one canonical hostname already admitted by that revision;
- one reviewed record type from `A`, `AAAA` or `CNAME`;
- a code-owned timeout/retry profile;
- an approved operation and output budget.

The code-owned invocation fixes the resolver policy and every option. Zone
transfer, `ANY`, a user-supplied DNS server, arbitrary flags and output files
remain forbidden. A returned address is untrusted observation data and does not
authorize a subsequent connection. More active service inventory, including a
narrow Nmap profile, requires later port/check-class enrollment and a separate
reviewed capability.

Additional programs such as Nmap, SQLMap, Nuclei, FFUF, Gobuster, Nikto,
Metasploit, Netcat and scripting runtimes are not aliases for the first
capability. Each would require its own threat model, structured request, effect
declaration, scope semantics, budgets, parser, fixtures and operator-visible
evidence rules.

## Output and evidence

Child-process bytes are untrusted target/tool data. The raw payload is bounded,
not rendered with terminal control sequences, and never used as instructions.
The parser emits typed observations and preserves enough provenance to identify:

- tool capability and reviewed adapter version;
- executable identity/version policy without exposing a local path;
- program, scope revision, plan, execution, step and attempt identity;
- normalized target identity and permitted ports;
- start/end time, timeout/cancellation state and exit category;
- hashes and byte counts for retained bounded raw material.

An observation is not evidence until the existing evidence workflow explicitly
accepts it. An open port, banner or heuristic match is not automatically a
finding. Failed and inconclusive runs enter Failure Memory as bounded lessons
without becoming permanent target prohibitions.

## Required milestone order

1. Enforce exact active program-scope revisions at approval, Start, restore and
   every Advance, before side effects. **Done in v0.3.305.**
2. Extend enrollment with explicit permitted check classes, ports, rate limits,
   request counts and time budgets. **Initial policy recording done in
   v0.3.306.**
3. Add an inert structured Kali operation preview. It builds and displays no
   raw command string and starts no process. **Done for the DNS-record lookup
   profile in v0.3.307.**
4. Add explicit human authorization bound to the exact operation digest. **Done
   for the DNS-record lookup profile in v0.3.308.**
5. Add a fake-runner integration with deterministic fixtures and prove zero
   process creation on every refusal path.
6. Add an opt-in WSL/Kali installation boundary and the single first reviewed
   operation. Tests use a fake child-process adapter and local fixtures; no
   third-party target traffic is allowed.
7. Connect typed observations to evidence review and reporting.
8. Only then permit the bounded autonomous loop to select that exact capability
   inside an already approved job.

## Acceptance tests before real execution

The production runner is not acceptable until tests prove:

- no raw shell, command string, PATH lookup or unreviewed executable can enter;
- missing Kali/WSL, wrong distribution, wrong executable or version mismatch
  fails before budget or target traffic;
- missing, expired, revoked, superseded, mismatched or corrupt scope authority
  creates no process and spends no budget;
- host, address, port, path and check-class exclusions win;
- option-looking target data cannot become an argument;
- timeout, cancellation and output overflow terminate predictably;
- stderr, ANSI/control bytes, invalid encoding and malformed parser output stay
  bounded and untrusted;
- retries cannot exceed the approved attempt or time budget;
- restart cannot inherit authority from a changed plan or scope revision;
- reference research, chat, fetched pages and the model cannot invoke the Kali
  capability;
- fake DNS, fake process and local fixture tests generate no external traffic.

## Decision

Accepted: a separate opt-in, scope-bound, tool-specific Kali execution layer
may be built in the milestone order above.

Rejected: exposing a terminal, accepting arbitrary commands, wrapping a shell,
or registering a generic process-execution tool. Those designs make the model,
fetched content or a malformed argument capable of expanding authority and are
incompatible with Hypatia's local-first, explainable and fail-closed goals.
