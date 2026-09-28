---
title: "Investigation — Code-as-Action: the single invoke(code) tool"
category: investigation
status: open
summary: >
  Design-space investigation into the code-as-action paradigm: giving the agent a
  single `invoke(code)` tool that executes Python so it can set up and manage
  tools, subagents, memory, and agent communication from code (CodeAct lineage:
  arXiv:2402.01030, Manus, Hermes, CodeMem, AgentFactory). Question: where does
  this converge with or improve this harness — which already has a `bash`
  do-anything tool, a lean-context ResultStore, a ToolContext that is RPC-shaped,
  and a skills layer that is procedural-memory-shaped. Recommendation: the model
  contract may collapse to (at most) one code tool, but the runtime keeps its
  rich, policy-enforcing surface behind an RPC stub — see proposal.md.
---

# Direction: Code-as-Action — the single `invoke(code)` tool

## The step being investigated

From a **structured multi-tool action space** (today: 34 tools, each with a typed
schema and policy) toward a **code-as-action space** — one `invoke(code)` tool
that runs Python, letting the agent itself build and manage tools, subagents,
memory, and communication.

| Aspect | Structured tools (today) | Code-as-action (target) |
|--------|--------------------------|--------------------------|
| Model-facing surface | 34 typed tool schemas = 1 contract per capability | One `invoke(code)`; Python is the contract |
| Composability | One tool call per turn (batched); state lives in context | Control/data flow in the program; batch N inputs per call |
| New capability | New ToolDef + registration + prompt-token cost | `import` the ecosystem, or write a helper |
| Context economics | ResultStore + `result_read` paging + progressive disclosure | Only `print()` enters context; the harness returns a lean summary |
| Tool/memory/comm management | Fixed toolset; agent cannot author tools | Agent writes + persists tools and subagents (procedural memory) |

## The key reframing

"One tool" is a **model-facing contract** property, not a runtime property. Manus
still keeps ~29 tools behind its code-first surface; Hermes and Microsoft's Agent
Framework expose `execute_code` while keeping a host-side tool registry that the
sandbox reaches through an RPC `call_tool`. The honest design question is not
"one tool vs many" but **action-space granularity at the model boundary, and what
the runtime keeps behind it**. This harness already exposes one do-anything tool —
`bash` (`core/tools/process.py`) — so the code-as-action move is a *shift in that
boundary*, not a new category of execution.

## What already exists (implemented, reused by the proposal)

- `bash` tool — arbitrary shell, host-access by deliberate decision, process-group
  kill on timeout, read-only heuristic + `repo_lock`, workdir default = generated
  root (`core/tools/process.py`). The closest existing "do-anything" action.
- ResultStore + `result_read` / `result_bash` — cacheable results paged by opaque
  handle without re-executing the producer; over-cap outputs advertise the handle
  in the footer (`core/tools/result_bash.py`, `Agent._run_loop()`).
- `ToolContext` — the interface handed to tool functions; already the shape of an
  RPC stub (`core/tool_context.py`).
- Skills layer — `SkillRegistry` (frontmatter `name`/`description`/`roles`),
  `skill_load`, read-only skills-root sandbox + role gate across tools
  (`core/references.py`, `core/tools/skills.py`). Procedural-memory-shaped today.
- Delegation / comms — `delegate`/`ask`/`converse` (+ `kill`/`status`/`resume`),
  the comms layer (`post`/`channel_read`/`subscribe`/…), spawn caps enforced at
  the `Runtime.delegate()` gate (`core/tools/agents.py`, `core/comms/`,
  `core/policies/spawn.py`).
- Safety invariants in `Agent._run_loop()` — max iterations, repeated-call
  detection, near-identical bash detection (per-family budgets), wall-clock
  timeout, token cap, result caching, delegation caps.
- Checkpointing — `AgentCheckpoint` persisted after every committed turn;
  `Runtime.resume()` (`core/checkpoint.py`).
- Benchmark suite — `benchmark/tasks.py` ALL_TASKS + deterministic scoring
  (`python -m dynamic_harness.benchmark.run`); `register_agent_class` for new
  agent types.

## What the evidence supports (summary; details in benefits-and-costs.md)

- **Context/token economics** — the strongest, most-replicated benefit: fewer
  model turns (CodeAct: up to 30% fewer actions on multi-tool tasks) and only the
  *printed* summary entering context (Hermes, CodeMem). Directly attacks this
  harness's stated #1 motivation (cost) and composes with ResultStore.
- **Control/data flow** — loop over N inputs in one call; compose tools with
  variables; up to +20% absolute success on multi-tool trajectories (CodeAct,
  M³ToolEval).
- **Zero-maintenance action space** — the Python ecosystem instead of
  per-capability ToolDefs; self-debugging via tracebacks.
- **Self-evolution** — validated routines persisted as reusable skills (CodeMem
  `register_skill`, AgentFactory, Voyager) — the natural upgrade path for the
  skills layer.

## What the evidence does NOT support

- **No benefit on simple/atomic tasks** — CodeAct is merely comparable there; the
  gains are on multi-tool, multi-turn trajectories. Must be measured, not assumed.
- **No determinism win** — same task → different code each run (CodeMem): a
  procedural-memory layer is the fix and must be built, else the harness trades
  away reproducibility it has today via structured tools + checkpoints.
- **Not a security neutralizer** — arbitrary code is a wider capability surface
  than bash (imports, pickles, network libs); every serious deployment sandboxes
  (Manus VM, CodeAct docker-per-session, Hermes whitelist + env scrub).
- **Prompt-injection caution** — web-fetched content copy-pasted into code is an
  injection→execution channel (tool-use survey: "Les Dissonances").
- Manus, the marquee production example, has published no benchmark scores (GAIA /
  SWE-bench unsubmitted).

## Key open questions

1. **Trust posture** — run `invoke` at the same trust level as `bash` (host
   access, the harness's existing deliberate decision) or stricter (sandboxed
   Python) in v1?
2. **Model contract** — pure single-tool agent class (measurement) vs hybrid
   (`invoke` + existing tools + RPC stub) as the production shape?
3. **Stub surface** — which harness primitives are reachable from code, and over
   what transport (stdin/stdout JSON vs temp-file IPC)?
4. **Procedural skills** — which validated routines qualify to persist, under
   what frontmatter, and where (skills root `procedural/`)?
5. **Guards** — Python-family near-identical detection, stdout caps, default
   timeout; import allow-list on or off by default?
6. **Decision gate** — what measured delta (tokens at parity success, or success
   at parity cost) justifies promoting the prototype to an IMP?

## Design conclusions (canonical leaves)

- [benefits-and-costs.md](benefits-and-costs.md) — the evidence mapping.
- [proposal.md](proposal.md) — the hybrid design: `invoke` tool + `harness_tools`
  RPC stub (policy parity via `ToolRegistry` reuse) + procedural skill
  persistence + guard changes + benchmark measurement plan.

## Investigation next steps

- [x] Survey the paradigm and evidence (CodeAct, Manus, Hermes, CodeMem,
      AgentFactory, MS Agent Framework, tool-use survey)
- [x] Map the paradigm against existing harness mechanisms (above)
- [ ] Decide open questions 1–6
- [ ] Prototype `invoke` + RPC stub and run the benchmark comparison
      (codeact agent type vs default; batch-loop microbenchmark)
- [ ] If signal → file an IMP with a task contract (roadmap register)
- [ ] Extend near-identical detection to Python `invoke` families
- [ ] Specify procedural-skill persistence rules (frontmatter + validation)