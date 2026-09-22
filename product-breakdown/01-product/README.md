# Layer 01 — Product

**What is delivered, out of scope?**

The product is a recursive agent runtime with artifact-based communication, strict context encapsulation, and Git-like provenance. What is delivered: the runtime (agents, task graph, artifact store, repository/commit layer, 25 tools), a minimal prompt-only CLI, a benchmark suite with deterministic failable verifiers, configurable safety/self-healing machinery, and the embedding surface (`Harness` API). What is out of scope: chatbot/conversation features, predefined workflow engines, code generation, and shared-memory designs (see VISION "What This Is NOT").

This layer answers "what" — scope, capabilities, use cases, requirements, acceptance expectations. Architecture ("how") lives in `02-architecture/`; the CLI requirements doc below is the CLI sub-spec and belongs here because it defines the delivered terminal surface.

## Product Definition (GAP-6 fill)

### Capabilities (from README.md / AGENTS.md)
- **Recursive decomposition** — parent agents decompose work and delegate to focused sub-agents with fresh, isolated contexts; parent orchestrates, children implement.
- **Deterministic safety machinery** — repeated-call detection, fuzzy near-identical `bash` detection, opaque result handles (`result_read`/`result_bash`), spawn caps per-lineage, checkpoint resume — enforced in code, not prompt advice.
- **Blunt-vs-rot self-healing** — resume-once for blunt stops vs fresh worker for context rot, one shared heal budget per child.
- **Artifact-driven communication + progressive disclosure** — findings to disk as immutable artifacts; parents consume summaries (~300 tokens), detail loaded lazily.
- **Git-like provenance** — every completed task creates a Commit with parent/child links; runs are auditable and resumable.
- **Actor-model isolation** — agents know only parent, children, and task.
- **CLI + embedding** — minimal prompt-only terminal with always-available input; `Harness` programmatic API; 25 extensible tools; failable benchmark verifiers + prompt optimizer.

### Out of Scope (VISION "What This Is NOT")
- Not a chatbot framework — conversations are not state
- Not a predefined workflow engine — agents decide decomposition dynamically
- Not a code generation platform — agents use tool calls, not generated code
- Not a shared-memory system — no global context, no element registry accessible to workers

### Acceptance Criteria (VISION success criteria)
1. Every sub-agent's output **verified** (artifact read, content confirmed)
2. Synthesis accurately reflects artifact contents (no fabrication)
3. No failed child abandoned — all failures retried or escalated
4. Total context across all agents remains shallow
5. Cost proportional to task complexity, not context duration

Note: criterion 1 is the subject of open gap **G1** (`04-verification/gap-analysis.md`) — verification is currently prompt-discipline plus a file-existence gate, not mechanical acceptance checking; tracked in `06-evolution/roadmap.md`.

## Owns
- Scope, capabilities, out-of-scope, acceptance expectations
- Use cases and requirements (the CLI sub-spec below)
- Product-level glossary

## Excludes
- Organization, architecture, components, data flow → `02-architecture/`
- Implementation details, scripts, configs → `03-implementation/`
- Test mechanics, proof, gap analysis → `04-verification/`
- Runbooks, release steps → `05-operation/`
- Roadmap, backlog → `06-evolution/`

## Contents

- [requirements.md](requirements.md) — **CLI sub-spec**: FR-1…FR-6 (prompt-only terminal, persisted overview, always-available input, streaming replies), NFR-1…NFR-4 (composability). The runtime's product definition above is the canonical "what"; this doc pins the terminal surface.
- [use-cases/](use-cases/) — 7 use-case families (repository-analysis, change-and-validation, documentation-and-knowledge, research-and-synthesis, pipelines-and-jobs, evaluation-and-qa, embedding-and-integration) + index.