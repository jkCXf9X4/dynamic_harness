# Mapping a Use-Case to the Architecture

Every use-case family is built from the same load-bearing concepts:

1. **Decomposition** — the goal is split into independent, role-scoped
   sub-agents (`delegate` in one turn for parallelism). Parents orchestrate.
2. **Artifacts, not memory** — each sub-agent writes findings to disk and
   returns a compact summary + artifact ID (**progressive disclosure**). Parents
   read summaries first, load detail only on `read_artifact`.
3. **Verify before synthesize** — never report a child's output as if you had
   read it; confirm the artifact on disk first (delegation-model §VERIFY).
4. **Self-healing** — a blunt failure resumes; a poisoned context spawns a fresh
   worker; a structural failure escalates (`../../02-architecture/concepts/self-healing/README.md`).
5. **Provenance** — each completed task writes an immutable artifact + a Commit;
   every run is reproducible and auditable from the trace (`index.jsonl`).

## Tool Vocabulary

Typical tool choices per step (see `skills/tool-motivations/SKILL.md` for the
full rationale):

- Discover: `glob` (enumerate), `grep` (search contents by symbol/behavior)
- Read: `read` (read summaries first; page large files instead of one giant read)
- Change: `edit` (targeted first-occurrence), `write` (whole/new content)
- Act/verify: `bash` — but **no shell operators** (no `|`, `>`, `&&`); no sandbox escape (paths confined to `generated_root`/CWD)
- External: `webfetch` — restricted to public/non-private hosts, 200 KB cap
- Coordinate: `delegate`, `converse` (nudge an existing child), `read_artifact`, `ask`
- Context: `compress`, `prune`, `restore`
- Terminate: `report` (success), `escalate` (blocked), `fail` (unrecoverable)

## Family Doc Shape

Each family doc follows the same shape: (1) **Scenario** — a concrete operator
goal phrased as a root task; (2) **Why it fits** — which pillars/capabilities
are exercised; (3) **Decomposition** — the roles/delegations to spawn;
(4) **Tool flow** — what each sub-agent reaches for (and constraints);
(5) **Verification & acceptance** — how "done" is confirmed; (6) **Failure
mode** — how self-healing applies; (7) **Fit checklist & caveats** — when the
use-case strains the design.
