---
id: INFO-147
type: info
title: Worker formation and option load
summary: lets any agent set up groups of collaborating workers — or standalone subagents — cheaply and structurally, addressing both complicated (breakdown/dec…
date: 2026-09-28
status: current
---

# Worker formation and option load

## The question

`invoke(code)` lets any agent set up groups of collaborating workers — or
standalone subagents — cheaply and structurally, addressing both **complicated**
(breakdown/decomposition) and **complex** (collaborative) development. Does that
wider option space confound the agent? Considered for **frontier** and
**modern/weaker** models.

## Reframe: "too many options" is two different loads

| Load | Structured tools today | With `invoke(code)` |
|---|---|---|
| **Expression** — "which of 34 tools, which schema, what order?" | High: every turn is a tool-selection decision; dynamic fan-out costs N turns | Low: a `for`-loop over subagents is one program; selecting one tool is trivial |
| **Intention** — "should I orchestrate at all, and how big a group?" | Already present (`delegate`, `stream_children`) but expensive to express ⇒ rare/casual | Same decision, cheaper to act on ⇒ the model reaches for it more often |

**Key claim — the option-overload risk is inverted relative to model
capability:**

- **Small/weaker models choke on open action spaces** — they cannot triage well,
  grab the first plausible option, and loop. Untuned small models were worse with
  code actions (CodeAct's tuning finding); OpenHands switches to *short* tool
  descriptions for weak models; Manus routes cheap parallel subtasks to
  fine-tuned Qwen.
- **Frontier models choke on cluttered *closed* spaces** — long tool lists and
  schemas — and are stronger at *writing the program* than *picking from 100
  buttons* (CodeAct's big-model gains, the Manus/Codex/Claude-Code experience,
  and why Hermes/Microsoft collapse the surface to one `execute_code`).

So the same capability per model class: **frontier agents rarely get confounded
by options per se; weaker agents genuinely are, and need a narrower surface.**

## Failure modes (all measurable)

1. **Deliberation tokens** — turns spent dithering over orchestration *shape*
   (one group vs three vs none).
2. **Over-engineering / woke-up-dead workers** — spawned-and-wired groups that
   are never used, or whose coordination chatter costs more than their output.
   AgentSpawn (arXiv:2602.07072) built an adaptive complexity heuristic because
   *naive spawning is lossy*: it pays off roughly past ~15 min of single-agent
   time.
3. **Graph drift** — the worker graph the parent announced diverges from what
   actually runs; no current map exists.
4. **Mis-triage on weak models** — broadcast when point-to-point suffices; a
   group when a solo subagent was the unit.

The guardrail skeleton already exists: spawn caps (`max_agents` 300,
`max_depth` 15) and the `Runtime.delegate()` choke point — loop-spawned workers
pass the same gate. Code-as-action changes the *ease* of expression, not the
*authority* check. Expression is freed; authorization is unchanged.

## Mitigation: rails, tiering, visible economics

The answer to "too many options" for frontier agents is not fewer capabilities —
it is **rails, capability-tiering, and economics made visible**:

- **Capability-tiering by model** — the harness already supports per-agent-class
  toolsets (`register_agent_class`): default `invoke` + group-forming for
  frontier agents; keep the structured-34 surface as the *only* surface for weak
  models. One runtime, two contracts.
- **Pattern library as procedural skills, not raw freedom** — surface
  group-formation as a *pattern skill* with role-scoped triggers (existing
  `SkillInjectionPolicy` mechanism): "standalone subtask workers vs a
  collaborating group — and the cost rule". The model is pointed at the pattern,
  not left to improvise an exotic one; mission-command / delegation-guidelines
  already encode the brief contract it inherits.
- **Terminal contracts stay enforced** — however freeform the group,
  `report` / `escalate` / `fail` still settle through the RPC stub as today, so
  unusual formations converge through the same verification path.
- **Economics as a cue** — delegation overhead (~3K tokens / fresh context),
  spawn-to-work ratio, and the ~15-minute rule encoded in the skill/trigger, so
  the "should I" decision answers itself from a number rather than taste.

## Measurement (extends proposal §5 decision gate)

Add to the gate: spawned-but-unused worker setups, coordination-to-work token
ratio, deliberation turns on orchestration shape, and results split per model
class. "Risk of too many options" then becomes a benchmark row instead of a
design opinion.

## Related

- `INFO-146` — the hybrid design; §5 decision gate
- `INFO-144` — the communication
  variant probe surface this composes with
- capability-scope (`product-breakdown/06-evolution/multi-agent-coordination/capability-scope.md`) —
  founding boundary-scoped, participation universal (who may form groups)
- AgentSpawn arXiv:2602.07072 — adaptive spawning economics