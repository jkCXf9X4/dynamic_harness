---
id: INFO-142
type: info
title: Benefits and costs — code-as-action evidence
summary: "Sources are the works mapped in INVESTIGATION.md; the headline numbers are cited inline. The paradigm's core evidence is CodeAct (ICML 2024, arXiv:240…"
date: 2026-09-28
status: current
---

# Benefits and costs — code-as-action evidence

Sources are the works mapped in `INFO-141`; the
headline numbers are cited inline. The paradigm's core evidence is **CodeAct**
(ICML 2024, arXiv:2402.01030), validated in production by Manus, OpenHands,
Hermes, and Microsoft's Agent Framework, and extended by the 2025–2026
self-evolution line (CodeMem arXiv:2512.15813, AgentFactory arXiv:2603.18000).

Evidence is strongest for **context/token economics** and **multi-tool trajectory
success**; weakest for determinism and security-neutrality.

## Benefits

| # | Claim | Evidence | Source | Relevance to this harness |
|---|-------|----------|--------|---------------------------|
| B1 | Fewer model turns: up to **30% fewer actions** on multi-tool tasks | M³ToolEval: 82 human-curated multi-turn, multi-tool tasks, 17 LLMs | CodeAct | Turn count is the dominant token-cost driver; aligns with the delegation-cost economics |
| B2 | Higher success on complex trajectories: up to **+20% absolute** vs JSON/text | Same study; gains most prominent on multi-tool trajectories | CodeAct | The benchmark suite can reproduce this comparison directly |
| B3 | Control/data flow: loop over N inputs in one action; compose tools with variables | Design argument + M³ToolEval ("one action can compose multiple tools") | CodeAct | Batch reads / delegates / transformations in one call |
| B4 | Only `print()` enters context; intermediate results never do | Hermes (script over RPC: "only the script's print() output is returned"), CodeMem | Hermes, CodeMem | Composes with ResultStore — both keep context lean |
| B5 | Zero-maintenance action space: "the number of tools the agent can call becomes infinite" | CodeMem motivation; CodeAct "leverage existing software packages" | CodeMem, CodeAct | Fewer ToolDefs to author/curate per capability |
| B6 | Self-debugging from tracebacks | All implementations (CodeAct, Hermes, Manus) | CodeAct et al. | Loop guards already bound this; no new mechanism |
| B7 | Self-evolution: validated code persisted as reusable skills | CodeMem `register_skill`; AgentFactory `create_subagent` + survivor skills; Voyager skill library | CodeMem, AgentFactory | Direct upgrade path for the skills layer |
| B8 | Portable, replayable, diffable actions — code is a deterministic artifact | CodeMem's reproducibility argument | CodeMem | Complements the commit/provenance design |
| B9 | One schema to learn — no tool-selection between schemas | Implied by the "single universal tool" frameworks | Manus, codeact projects | Kills a whole class of schema/selection errors on small models |

## Costs

| # | Claim | Evidence | Source | Relevance to this harness |
|---|-------|----------|--------|---------------------------|
| C1 | Security: arbitrary code is a wider surface than bash (imports, pickles, /proc, network libs) | Every serious deployment sandboxes: Manus = per-task VM (Firecracker microVM), CodeAct = docker-per-session, Hermes = child process + tool whitelist + env scrub | Manus, CodeAct, Hermes | Harness `bash` is already host-access by decision — `invoke` at equal trust is *not a new boundary*, but a wider capability surface; stdout caps + timeout still required |
| C2 | Prompt-injection → code execution: web-fetched content pasted into code runs it | Tool-use survey cites "Les Dissonances": payloads propagate across tool boundaries | arXiv:2603.22862 | `webfetch`/`read` results must be consumed as data (RPC / result pages), never copied into `invoke` source — a policy, not prompt advice |
| C3 | "Runs" ≠ correct: fewer typed contracts; verification shifts to the agent | CodeMem on probabilistic instability; the framework literature | CodeMem | Structured tools carry harness validation; terminal contracts must stay stub-enforced |
| C4 | No determinism: same task → different code each run | CodeMem's core motivation | CodeMem | Procedural memory (skills) must be built, or the harness loses today's reproducibility |
| C5 | No gain on simple/atomic tasks; abstraction overhead | "for small tasks with one or two tool calls, the added abstraction may not buy you much" | Microsoft Agent Framework | Measure turn/token delta per task class; do not blanket-replace |
| C6 | Coarse governance: approval is per-`execute_code`, not per-tool | Microsoft Agent Framework notes | MS AF | Budget lines, plan compliance, spawn caps must live in the RPC stub, not the raw tool |
| C7 | Audit trail is text, not typed ToolResults | Structural | — | Keep full executed source + stdout in the trace; ResultStore handle in the footer |

## Verdict

The benefit worth chasing for this harness is **B1+B4** (context/token economics)
composed with the existing ResultStore, plus **B7** (procedural skills) as the
leverage play. **C1–C4** define the design constraints carried into
`INFO-146`.
