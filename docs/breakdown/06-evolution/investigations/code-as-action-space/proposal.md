---
id: INFO-146
type: info
title: Proposal — hybrid code-as-action surface
summary: RPC stub below) must route through so every code-driven action passes the same policies the tools enforce today — sandbox roots, spawn caps, plan/chec…
date: 2026-09-28
status: current
pb_exempt: true
---

# Proposal — hybrid code-as-action surface

## Positions

1. **Keep the runtime rich; collapse only the model contract.** `invoke` (and the
   RPC stub below) must route through `ToolRegistry.execute()` so every
   code-driven action passes the same policies the tools enforce today — sandbox
   roots, spawn caps, plan/checkpoint semantics, comms routing, budget lines.
2. **Trust parity with `bash` in v1** — same subprocess pattern, host-access per
   the harness's existing deliberate decision (`core/tools/process.py`). Hard
   sandboxing is a later, config-gated hardening. This keeps v1 a small,
   benchmarkable delta.
3. **Three pieces**: an `invoke` tool, a `harness_tools` RPC stub, and
   procedural-skill persistence — plus guard changes and a measurement plan.

## 1. `invoke` tool

- Definition + registration in `core/tools/code.py`, wired from
  `core/tools/registration.py` (mirrors `process.py`).
- Signature: `invoke(code: str, timeout?: int = 60000, workdir?: str)`.
- Execution: `python3` fed the source over stdin in a subprocess — same
  process-group kill, read-only heuristic + `repo_lock`, cwd default = generated
  root, and `CancelledError` handling as `process.py:bash`.
- Output: stdout+stderr captured; **over a cap →** replace with a lean summary
  `[output truncated — result_read <id>]` and store the FULL stdout in the
  ResultStore under the handle (same footer advertising `result_bash`).
- Cacheability: like `bash` — cacheable-by-handle, and the produced `result_id`
  never feeds back into the producer (fresh result = call `invoke` again).
- Loop guards: source-normalized near-identical family detection (strip comments
  and whitespace for the signature), counted per family with the
  warning→escalation ladder (`safety.near_identical_*`, `repeated_recovery_*`);
  repeated-call detection inherited as-is.

## 2. `harness_tools` RPC stub

- A generated stub module injected into the subprocess (pointed at by a
  `HARNESS_TOOLS` env var, like Hermes' generated `hermes_tools.py`), so code can
  write: `from harness_tools import read, grep, webfetch, delegate, ask,
  converse, post, channel_read, read_artifact, plan, checkpoint, usage, status,
  resume`.
- Transport: JSON-lines over a private temp file (or stdin/stdout handshake); the
  parent executes each request through `ToolRegistry.execute()` → **policy parity
  by construction** (delegation caps, sandbox roots, comms routing, budget
  lines).
- Contract to the model: only the printed summary and a `# result: <id|none>`
  footer marker enter context; tool payloads go to the ResultStore (same lean
  context as B4).
- Blocked inside the sandbox: recursive `invoke`, and direct terminal calls.
  `report`/`escalate`/`fail` are handled by *returning* a marker — the agent
  prints its terminal intent and the harness loop recognizes the terminal marker,
  keeping the terminal contract enforced. The host tool registry stays
  authoritative.

## 3. Procedural-skill persistence (self-evolution, B7)

- Extend the existing skills root + frontmatter: a validated routine is persisted
  as `skills_dir/procedural/<name>/SKILL.md` with `type: procedural`, the current
  `name`/`description`/`roles` frontmatter, plus `entrypoint: script.py` and the
  validated source as a sibling file.
- The read-only skills-root enforcement + role gate already apply (`skill_load`
  and the cross-tool path guards); procedural skills add a review rule: content
  must be non-secret, plain-text, and marked `provenance: agent-authored`.
- Reuse `SkillInjectionPolicy` for discovery — the authoring agent (and
  role-matched siblings) gets the same trigger-as-notice behavior as today.

## 4. Guard changes (config, `safety.*`)

- `invoke.stdout_cap` / `invoke.stderr_cap` (bytes; default e.g. 32 KiB) → cap +
  ResultStore handle on overflow.
- `invoke.timeout` default (shorter than bash, e.g. 60 s) + explicit param.
- `invoke.import_allowlist` — optional, default off (parity with bash); when on, a
  non-listed `import` returns an error instead of executing.
- **Code-not-data** (C2): if fetched/read content appears literally inside
  executed source, inject a `[notice]` and (v2) refuse-to-run. v1 rule is
  prompt-level + captured in the trace.
- All existing invariants (max iterations, token cap, wall-clock timeout, spawn
  caps) apply to `invoke` turns unchanged.

## 5. Measurement plan (the decision gate)

- Add a `codeact` agent type (`runtime.register_agent_class`) with toolset
  `[invoke, report, result_read, result_bash, usage, status]` (mirrors
  OpenHands' minimalist agent) vs. the default 34-tool agent on
  `benchmark/tasks.py` ALL_TASKS; compare success, turns, tokens, per-turn
  context size, and cost.
- Micro-ablation for B3: a batch task (N files → same transform) measuring turns
  and tokens vs the structured-tool path.
- Gate: promote to an IMP (with a task contract, per roadmap rules) only if the
  measured delta is a **token reduction at ≥ parity success**, or a **success
  gain at ≤ parity cost** — thresholds fixed before running.

## Out of scope (v1)

- Hard sandbox / containerization (Firecracker/Docker) — documented as the C1
  hardening path.
- Import allow-list default-on; per-import approval UX.
- Cross-run procedural-skill provenance (linking a skill back to its artifact /
  commit).
