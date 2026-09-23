# Backlog — raw suggestion log

Raw idea/suggestion log for the evolution layer (moved from `breakdown/development/__undeveloped_sugestions__.md`). Disposition markers: **DONE** / **RESOLVED** / **PICKED UP** (with target); unmarked items are open. Canonical open work is tracked in [`roadmap.md`](roadmap.md); this file is the raw record, not the register.

## Open

- Encourage agents to plan before acting and persist intermediary results to disk in a structured way, to enable resume of aborted/failed tasks.
- Evaluate how referencing additional knowledge should work and fit the larger picture.
- Visualize token use better to the agents (did G10 improve it?); set a per-agent context goal under 50,000 tokens.
- Make the top agent unable to timeout; make the trace send and receive to simplify debugging.
- Enable parents to act on child events before all children are done.
- On hitting tool-call limits, incorporate a tighter fallback loop before failing the agent — point out that it is looping and see if it can recover.
- Check `trace.jsonl` to deduce the error and decide whether it is fixable or reasonable; use the session.
- Push agents further on persisting partial results and evaluations (models often fail or hallucinate during long runs).
- Ensure sub-orchestrators cannot time out as well.
- Parents should be able to evaluate whether children have crashed and kill them.
- Enable input during execution; the CLI token counter is way off — investigate.
- Add a tool to kill children and get their status.
- Ensure garbage collection of completed agents' unnecessary data (e.g. context) to clear memory and speed access to the rest.
- Extract generic learnings from a project-specific prompt that gave consistent results (trading-platform example) to improve the system prompt: ensure existing functionality before new items; move relevant working-directory information into the project and clean stale information (prefer removing to archiving, be strict); document evaluations well so future runs need not re-search the design space; use `roadmap.md` as the to-do list; treat `.dynamic-harness/` as a temp dir and clean up stray files; existing reports/artifacts under `.dynamic-harness/` may be useful.
- When an agent is close to its iteration limit (~50 left), inject a hard message to finish tasks and return remaining items/information to the parent.
- When a command failure leads to agent termination, is a warning injected before the failure to enable recovery?
- Can we use external agents for single-question context? Would it be a gain, and where best used? Ask external agents whether delegation is needed without polluting context.
- Enable `rg` and other commands on result handlers, to search results without re-running expensive commands.
- Evaluate the step from complicated development (problems broken into subparts) to complex development (parents set up multiple communicating children that solve problems together).
- Try delegating 4 small tasks to subagents — how are they doing?
- Enable Ctrl+C to exit the application.
- Child layer-by-layer collaboration: relate it to the orchestrators or make it a general capability all agents possess; core attributes relate to Hackman's five conditions, especially (1) a real team — clear membership, bounded, interdependent, shared responsibility; (2) a compelling direction — challenging, clear, consequential.
- Open a new investigation under `04-verification/` comparing how communication structures influence agent success: (1) all communication through the parent; (2) all children of a parent can communicate; (3) all nodes in one dedicated channel; (4) all nodes can register/create topic channels. **DONE** → `04-verification/communication-structures/`.
- Make communication visible and auditable; file-based traces enable post-exit and live audits/reviews.
- Critical review of the breakdown structure, filling in missing aspects so the development rationale is clear. **DONE** → this restructuring.

## Picked up

- Hang at a `tool_result` (bash, no output) → `investigations/watchdog.md` (threat model T1–T5, cheap gaps, design space, recommended composition).
- Main orchestrator still times out — evaluate why → `investigations/watchdog.md` (root-exempt backstop = whole-run guard §3.2/W1).
- Bash commands not completing and killing agents by timeout → `investigations/watchdog.md` (bash bound = cheap gap §3.1).
- Common interface for metric-reactive policies (plugin-centric architecture) → `../03-implementation/plugin/investigation/README.md` (seed `core/policies/interface.py`, `Runtime.register_reactive_policy`; interface economy; loader/late-injection explicitly out of scope).
- Investigate how a watchdog could be implemented cheaply and robustly → `investigations/watchdog.md` + `investigations/watchdog_w3_utilization.md`.

## Resolved / Done

- Set up use-cases under `01-product/use-cases/` — **DONE** (index + 7 families: repository-analysis, change-and-validation, documentation-and-knowledge, research-and-synthesis, pipelines-and-jobs, evaluation-and-qa, embedding-and-integration).
- Evaluate functionality and use from the use-cases — what is missing — **DONE** → `04-verification/gap-analysis/README.md` (P0: verify-not-enforced, delegate-boundary heal, non-progressive disclosure/dead `raw_data`, `artifact_ids` vs files; P1: sandbox doc drift, no LLM-spawnable custom agents, Layer-2 heal, dead budget plumbing; P2: cost, counters, docs drift). Needs fixes: implement G2, G3, G4, G5, G6, G10.
- Add a common config that acts as a base and is overridden by local configs, and confirm the defaults — **DONE** (layered XDG-base + local overlay; llm `provider_allow_fallbacks`/`verify_ssl`/`call_timeout_seconds`; safety `max_iterations` 400, `repeated_call_limit` 5, `repeated_recovery_attempts` 2, `repeated_call_exempt_tools`, `timeout_seconds` 7200, `disable_root_timeout`, `max_agents` 300, `max_depth` 15, `max_same_target_delegations` 0, `spawn_limit_warning_attempts` 2; agent `environment_notes`, `stream_children`).
- Move the status terminal/agent tree to separate files; keep the CLI to prompts only and persist all other data for traceability — **RESOLVED** (`agents.txt`, `agent_tree.json`, `stats.json`, `events.jsonl` in the run root; prompt-only CLI with a lightweight counter and final outcome; see `01-product/requirements/README.md`). A directional change to make the app usable in larger automated workflows.
- Always-available text insertion during a run (queue while busy, apply while the top agent waits) plus slash commands (`/tree`, `/agents`, `/provenance`, …) for live status — **RESOLVED** (`Agent.submit_input()`; see `01-product/requirements/README.md` FR-3.5).
