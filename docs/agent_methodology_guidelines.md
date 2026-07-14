# Agent Methodology: Guidelines & Priorities

Based on the architectural vision in [VISION.md](../VISION.md) and analysis of `AGENT_SYSTEM_PROMPT` in `src/dynamic_harness/core/agent.py`.

## Core Philosophy

Dynamic Harness maximizes LLM output quality while minimizing cost by enforcing disciplined task decomposition, strict context encapsulation, and a mandatory **analyze → implement → verify loop**. An agent's job is not to do work directly, but to break work into pieces and delegate. Deep context = degraded focus = wasted cost.

> **Golden rule:** If a sub-task requires more than 1–2 tool calls, delegate to a sub-agent. Never accumulate turn debt.

> **Vision alignment:** Every principle below serves the core insight — fresh context is cheaper and higher-quality than accumulated context. A 3-turn sub-agent with a clean slate outperforms a 20-turn monolithic agent.

---

## Mandatory Workflow

Every agent invocation must follow this sequence. Deviation is a methodology violation.

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. ANALYZE   →  Identify separable sub-tasks from your description │
│  2. DECOMPOSE  →  Group into independent units of work              │
│  3. DELEGATE   → Delegate sub-agents in parallel for each unit        │
│  4. VERIFY     →  Confirm each sub-agent's artifact exists & valid  │
│  5. SYNTHESIZE →  Combine verified results into your report         │
│  6. TERMINATE  →  report() / escalate() / fail()                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Step-by-step requirements

| Step | Action | Exit condition |
|------|--------|---------------|
| **ANALYZE** | Read your task description and role (if assigned). List what you need to find, change, or produce. Restrict scope to what your role permits. | You have a bullet-point decomposition. |
| **DECOMPOSE** | Group bullets into units. Each unit = one independent sub-agent. If a unit has sequential dependencies, it's still one sub-agent. Only independent units get separate delegations. Assign a **role** to each sub-agent that scopes its focus. | You have N delegation descriptions with roles assigned. |
| **DELEGATE** | Call `delegate()` for each unit. All delegations in one turn for maximum parallelism. | All sub-agents return `Status: completed`. |
| **VERIFY** | For each child: read its artifact file, confirm the output matches the delegation description. If a child returned `Status: failed`, re-delegate or escalate. | Every child's output is confirmed. |
| **SYNTHESIZE** | Combine verified results. Your report must reference each child's artifact IDs. | Ready to terminate. |
| **TERMINATE** | Call `report(summary, artifact_ids=[...])`. | Task status is `completed`. |

---

## Delegation Decision Tree

Use this tree **before every tool call** to decide whether to delegate or act directly:

```
Is this a standalone unit of work?
├── NO  → Keep it in your own context (but beware accumulation)
└── YES → How many tool calls will it need?
          ├── 0–1 calls → Do it yourself (read a file, run one command)
          └── 2+ calls  → DELEGATE TO A SUB-AGENT
```

**Exceptions where direct action is acceptable even with 2+ calls:**
- You are a leaf agent whose entire task is reading 2–3 specific files and reporting
- You have already been given file paths and just need to read them
- A single bash command with a follow-up read (2 calls total, tightly coupled)

**Delegation anti-signals — stop and delegate if:**
- You are about to call `grep` followed by `read` on multiple results
- You are about to chain `glob` → multiple `read`s
- You are about to run a test, see it fail, and open files to fix
- You just made the same tool call 2+ times in this task

---

## Priority Hierarchy

### P0 — Decompose First, Act Second

Before making any tool call, output the decomposition plan. Do not touch a tool until the plan is clear.

**Why:** Each turn you take adds to context history. Over many turns, earlier context grows stale and you lose sight of the original purpose. Sub-agents start fresh.

### P1 — Delegate Aggressively & In Parallel

- Delegate multiple sub-agents **in the same turn** so they explore independently.
- Each sub-agent should do **one thing well**.
- Prefer two parallel sub-agents over one agent with a two-part sequential task.
- The delegation description is the sub-agent's **entire world** — it knows nothing else.

### P2 — Keep Your Own Context Shallow

- Your role: decompose, delegate, verify, synthesize.
- If you read more than 1–2 files directly, you have accumulated too much noise.
- Read **summaries and artifact files** from sub-agents, not the raw source they already processed.
- Each raw source file you read is a failure of delegation.

### P3 — Verify Before Synthesizing

**This is the most frequently violated principle.** After a sub-agent reports:

1. Read the artifact file(s) it wrote (use `read()` with the paths it reported).
2. Confirm the content is non-empty and matches the delegation description.
3. If verification fails — re-delegate or escalate. Never synthesize from assumed results.
4. When a child returns `Status: failed`, do not proceed — the task is incomplete.

### P4 — Use Artifact-Driven Communication

- Sub-agents **must** write findings to disk via `write()`.
- Reference files by path; do not pass large raw data in-memory.
- Sub-agents call `report(summary, artifact_ids=[...])`. The parent reads the artifact file.
- The delegate tool returns only `"Delegated to agent completed. Status: X. ID: abc123"` — you will **not** see the child's report contents automatically. You **must** read its artifacts.

### P5 — Monitor Context Health

Before each turn, a Context Observation shows:
- **Turn count** — how many LLM calls so far
- **Messages** — total messages in context window
- **Estimated tokens** — approximate prompt tokens consumed
- **Task** — original task description

Decision rules:
| Condition | Action |
|---|---|
| Low turns (<5), few messages (<15) | Continue or delegate |
| Medium turns (5–15), growing messages | Delegate sub-agents for remaining work |
| Many turns (>15) | Call `compress()` **immediately** |
| Context > ~50 messages | Call `compress()`, then re-evaluate |
| Repeated similar tool calls (3+) | Stop. Delegate to sub-agent. Do not grind. |

### P6 — Quality of Delegation Descriptions

A vague description produces a wandering sub-agent. Follow these rules:

1. **Be specific** — include exact file paths, function names, expected behavior
2. **State what, not how** — describe the desired outcome, not implementation steps
3. **Assign a role** — prepend a role tag that scopes the sub-agent's focus (see P8)
4. **Specify work type** — tell the sub-agent whether to write code, search, or just report
5. **Include verification** — e.g., "Run `pytest tests/test_auth.py` after making changes and confirm all tests pass"
6. **Keep focused** — one task per delegation, not a list of unrelated chores
7. **Specify conventions** — framework, naming, imports, neighboring files as examples
8. **Provide context** — include any task-level knowledge the sub-agent needs (it sees ONLY your delegation description, nothing from your parent)
9. **Clear acceptance criteria** — tell the sub-agent exactly what "done" looks like
10. **Required output format** — specify what artifacts to write and what `report()` should contain

### P7 — Terminate Clearly

| State | Method | When |
|---|---|---|
| Success | `report(summary, artifact_ids=[...])` | All sub-agents verified, synthesis complete |
| Blocked | `escalate(issue)` | Cannot proceed without parent intervention |
| Irrecoverable | `fail(error)` | Cannot proceed at all |

### P8 — Assign Roles to Scoped Focus

A role is a lightweight scope tag that **narrows the agent's solution space**. It pre-answers decisions the agent would otherwise burn tokens figuring out, reducing turns and context bloat.

**Role format:** A single sentence defining stance, scope, and boundaries.

```
"You are a Security Auditor. Your only concern is vulnerabilities — ignore style, performance, and architecture. Flag issues, do not fix them."
"You are a Test Writer. Your only concern is test coverage for the specified module. Do not modify implementation code."
"You are a Code Reviewer. Your only concern is correctness and readability. Do not run or write code."
```

**When to assign roles:**

| Situation | Role needed? |
|---|---|
| Sub-task has a clear, narrow domain (security, testing, docs) | **Yes** — role prevents scope creep |
| Sub-task crosses multiple domains | **No** — role would constrain needed flexibility |
| Leaf agent doing a single read/report | **No** — task description is sufficient |
| Agent needs to decide its own approach | Light role only (e.g., "You are an Analyst") |

**Role anti-patterns to avoid:**

- **Persona bloat:** `"You are a world-class senior engineer with 20 years of experience who..."` — this adds tokens without narrowing scope. A role is a scope constraint, not a backstory.
- **Conflict with task:** `"You are a Documentation Writer. Fix the login bug."` — role and task contradict. The agent will be torn.
- **Overly restrictive:** `"You are a Python 3.11 type checker."` when the agent also needs to read YAML configs — the role should not block necessary tools.

**Role propagation:** When a parent delegates to a child, the child inherits the role **only if the parent explicitly passes it**. Children do not automatically inherit the parent's role — the parent decides what each child needs to know.

---

## Anti-Patterns

These are the most common failure modes observed in agent behavior. **All of them are methodology violations.**

### AP-1: Skipping decomposition

**What it looks like:** Agent receives task → immediately calls `glob()` or `grep()`.

**Why it fails:** Without a plan, the agent grinds through search results turn-by-turn, accumulating context bloat without clear direction. By turn 15, the original task is diluted.

**Fix:** Output a decomposition plan as the first action. List sub-tasks, then delegate to sub-agents. If the LLM won't output a plan, the task description may be too vague.

### AP-2: Doing it all yourself

**What it looks like:** Agent makes 5, 10, 20+ tool calls itself without delegating.

**Why it fails:** Context accumulates. Turn 20 sees the task description buried under 18 system observations. Focus degrades. Cost scales with context length unnecessarily.

**Fix:** After 3 tool calls without a delegation, ask: "Could a sub-agent do this?" The answer is almost always yes.

### AP-3: Blind synthesis

**What it looks like:** Parent delegates to children → receives `"Status: completed"` → calls `report()` with a synthesis based on the delegation description, not the child's actual output.

**Why it fails:** The parent synthesizes what it *asked for*, not what the child actually *found*. The child's results are ignored. This produces correct-looking but factually wrong output.

**Fix:** After delegation returns, read the child's artifact file. Confirm it exists and its content is relevant. Only then synthesize.

### AP-4: Mega-delegation

**What it looks like:** `delegate(description="First, do X. Then check Y. After that, modify Z. Finally, run tests and report.")`

**Why it fails:** The sub-agent has a multi-step sequential task with no clear focus. It's essentially a root-level task masquerading as a sub-task. The sub-agent's context grows, it loses focus, and the parent can't verify intermediate steps.

**Fix:** Split into independent delegations. `delegate("Do X")` and `delegate("Check Y")` are better than one mega-delegation. If X and Y are sequential, Y should be delegated after X completes and its artifact is verified.

### AP-5: Abandoning failed children

**What it looks like:** Parent delegates to children → one returns `"Status: failed"` → parent ignores it and synthesizes from the successful children.

**Why it fails:** The parent produces a partial result, missing critical information. The task's original goal is not met, but the parent reports success.

**Fix:** When a child fails, evaluate: can another child be delegated with a better description? If yes, retry. If no, escalate with the failure context. Never report success with missing pieces.

### AP-6: Vague delegation descriptions

**What it looks like:** `delegate(description="Look at the auth code and fix issues")`

**Why it fails:** The sub-agent wanders. "Look at" is directionless. "Fix issues" has no acceptance criteria. The sub-agent has no way to know when it's done.

**Fix:** `delegate(description="Read src/auth/login.py and find the function that validates JWT expiry. If the expiry check is missing or incorrect (should reject tokens older than 3600 seconds), add the check. Run `pytest tests/test_auth.py` to verify. Write a summary of changes to /tmp/auth_fix_summary.txt and call report() with that file path as an artifact.")`

### AP-7: Hallucinating sub-agent output

**What it looks like:** Parent delegates to children → receives status strings → in the `report()` summary, the parent describes detailed findings that the children never actually produced. The parent invents plausible content.

**Why it fails:** The parent's LLM fills in gaps with fabricated detail because it wasn't given the actual child results. The output sounds authoritative but is fiction.

**Fix:** The parent must read artifact files before synthesizing. If verification is enforced (see P3), this cannot happen.

### AP-8: Infinite context growth

**What it looks like:** Agent keeps calling tools, context grows to 80+ messages, agent shows no sign of terminating.

**Why it fails:** Beyond ~50 messages, context degradation accelerates. The agent starts repeating itself, forgetting early context, and making errors. Cost per turn grows linearly with context length.

**Fix:** Context observation triggers (see P5). At 50+ messages, call `compress()`. Do not wait.

### AP-9: Missing or conflicting roles

**What it looks like:** Delegating to sub-agents without role specifications, or assigning roles that contradict the task description.

Examples:
- `delegate(description="Analyze the repo")` — no role, agent has no scope boundaries
- `delegate(description="You are a Documentation Writer. Fix the login bug.")` — role says docs, task says code fix

**Why it fails:** Without a role, the agent treats every concern as its responsibility — leading to scope creep, context bloat, and unfocused output. With a conflicting role, the agent is torn between its role constraints and the task requirements.

**Fix:** Always assign a role that aligns with the task, following P8 guidelines. If a task genuinely crosses domains, either split it into multiple role-scoped sub-agents or use a light coordinator role (e.g., "You are an Orchestrator. Decompose and delegate, do not implement.").

---

## Verification Protocol

After each `delegate()` call returns, follow this protocol **for each child** before proceeding:

```
Child delegated to: X
  ├── Status is "completed"?
  │     ├── YES → Continue to verification
  │     └── NO  → Log the failure. Decide: retry with better description, or escalate?
  │
  ├── [Verification] Did the child report artifact_ids?
  │     ├── YES → Read each artifact file using read(path)
  │     │         ├── File exists and is non-empty → VERIFIED ✓
  │     │         └── File missing or empty → Verification FAILED
  │     └── NO  → Use converse(child_id, "What did you find?") to query the child
  │                └── If child's response is substantive → VERIFIED ✓
  │                └── If response is vague or missing → Verification FAILED
  │
  └── Is verification complete for all children?
        ├── YES → Proceed to synthesis
        └── NO  → Do NOT synthesize. Retry or escalate.
```

### Verification checklist

Before calling `report()`, confirm:
- [ ] Every delegated child has `Status: completed`
- [ ] Every child's artifact file has been read and its content confirmed
- [ ] The synthesis accurately reflects (not fabricates) the artifact contents
- [ ] Any child that failed has been retried or escalated
- [ ] The final `report()` includes all relevant child artifact IDs

---

## Good vs Bad: Concrete Examples

### Delegation descriptions

**BAD:**
> "Check the repo for security issues and fix them."

**GOOD:**
> "You are a Security Auditor. Your only concern is vulnerabilities — flag issues, do not fix them. Run `bandit -r src/ -f json` to scan for security issues. Parse the output and for each finding with severity HIGH, identify the file and line. Write the findings to `/tmp/security_findings.json`. Do NOT make code changes — this is a read-only scan. Call `report()` with a summary of HIGH-severity issues found and the artifact path."

**Why it's good:** Role scopes the agent to auditing only, specific tool, specific output file, clear scope (read-only, HIGH only), clear acceptance criteria.

---

**BAD:**
> "Improve the test coverage."

**GOOD:**
> "You are a Test Writer. Your only concern is test coverage — do not modify implementation code. Run `pytest --cov=src/dynamic_harness/core --cov-report=term-missing` to find untested lines. Focus on `runtime.py`. Identify the top 3 functions with the most uncovered lines. For each, write a test in `tests/test_runtime.py` following the existing test patterns (use the same fixtures and assert style). Run the new tests to confirm they pass. Write a summary of what you added to `/tmp/coverage_improvements.txt` and call `report()` with that file as an artifact."

**Why it's good:** Role prevents implementation changes, bounded scope (one file, top 3), existing conventions referenced, verification step included, output artifact specified.

---

### Execution patterns

**BAD execution:**
```
Turn 1: glob("**/*.py")
Turn 2: read("file1.py")
Turn 3: read("file2.py")
Turn 4: read("file3.py")
Turn 5: grep("pattern", ...)
Turn 6: read("file4.py")    ← context now 18+ messages, focus lost
Turn 7: read("file5.py")
...
Turn 20: report("I analyzed the codebase...")  ← synthesis from stale/buried context
```

**GOOD execution:**
```
Turn 1: [Analysis] "I see 3 sub-tasks: (A) find auth logic, (B) check error handling, (C) review tests"
         delegate(A), delegate(B), delegate(C)  ← all in one turn
Turn 2: [Verification] read("/tmp/auth_findings.txt") ✓
         read("/tmp/error_handling.txt") ✓
         read("/tmp/test_review.txt") ✓
Turn 3: [Synthesis + Termination] report("...", artifact_ids=[artA, artB, artC])
```
**Total: 3 turns. Context: 9 messages. Cost: minimal. Quality: verified.**

---

## Failure Recovery Patterns

| Failure | Recovery |
|---|---|
| Sub-agent returns `Status: failed` | Read its last messages via `converse(child_id, "What went wrong?")`. If the issue is clearable (e.g., missing file, typo in the description), delegate again with a corrected description. If the issue is structural (e.g., tool limitation), escalate. |
| Sub-agent reports success but artifact is empty/missing | `converse(child_id, "Your artifact at path X is empty. Did you write your findings?")`. If the child confirms it wrote to a different path, read that. Otherwise, re-delegate. |
| Sub-agent hit safety limits | It ran 500 iterations or 5 repeated calls. The task was too broad or ambiguous. Re-delegate with a narrower, more specific description. |
| Sub-agent returns `Status: escalated` | Its issue is now your issue. Read its escalation context, decide if you can resolve it or must pass it up via your own `escalate()`. |
| Multiple children all fail | The task decomposition is likely wrong. Escalate with a summary of what each child was asked to do and why they failed. |

---

## Cost-Effectiveness Heuristics

| Action | Approx. tokens | When to use |
|---|---|---|
| Read a known file path | ~500–2000 | File is small, path is specific |
| Delegate to a sub-agent | ~2000–5000 overhead | Sub-task needs 2+ calls |
| Compress context | ~5000–15000 | Context > ~50 messages |
| Grind through many reads yourself | 0 + turn cost × N | **Never** — this is delegation failure |

**Rule of thumb:** A delegation costs ~3000 tokens overhead (system prompt + delegation description). If doing it yourself would take 3+ turns at 2000+ tokens/turn, delegating is cheaper **and** produces better quality (fresh context for each sub-task).

---

## Report Structure

A good `report()` call follows this structure. It makes the parent's job of verification and synthesis straightforward.

```
report(
    summary="[1–2 sentences summarizing the concrete finding or change]. "
             "Verified by: [how]. Artifacts written: [files].",
    artifact_ids=["/tmp/analysis_results.json", "/tmp/changes_summary.txt"]
)
```

### Report quality checklist

- **Concrete, not abstract:** "Added `expiry_check()` to auth.py, 3 tests pass" not "Improved auth security"
- **Self-verifying:** Include the verification method (e.g., "Confirmed via pytest")
- **Artifact-referenced:** Every output file is listed in `artifact_ids`
- **One topic:** The report covers the sub-task, nothing else
- **No fabrication:** Every claim is backed by actual tool output or artifact content

---

## Task Framing (for root-level tasks)

The quality of the root task description directly determines the entire tree's behavior. Follow these principles when writing the initial task:

1. **Be specific about scope** — What codebase? What directory? What problem?
2. **State the desired outcome** — What should exist or be true when done?
3. **Specify format** — How should the final report be structured?
4. **Set boundaries** — What should NOT be changed or investigated?
5. **Provide context** — File paths, conventions, constraints the agents can't discover

**BAD:**
> "Fix the bugs in my project."

**GOOD:**
> "The user reports that login fails with a 500 error when the password contains special characters. Investigate `src/auth/login.py` and `src/auth/password.py` to find the root cause. Apply a minimal fix. Verify by running `pytest tests/test_auth.py`. Do NOT modify the database schema or frontend code. Write a summary to `/tmp/fix_report.md`."

---

## Summary Table

| Principle | Essence |
|---|---|
| Decompose | Split work into independent sub-tasks first |
| Delegate | Delegate sub-agents, don't do it yourself |
| Verify | Confirm every child's output before synthesizing |
| Parallelize | Run sub-agents concurrently in one turn |
| Stay shallow | Keep your context lean; read summaries, not raw source |
| Write artifacts | Findings → disk, not in-memory |
| Monitor context | Compress or escalate when context grows heavy |
| Describe well | Specific, focused, verifiable delegation descriptions |
| Scope with roles | Assign a role to every sub-agent to narrow focus and prevent scope creep |
| Recover | Handle failures structurally, never ignore them |
| Terminate cleanly | report / escalate / fail — never hang |

---

## Guardrails

- Never try to re-read source that a sub-agent already processed — read its artifact.
- If you find yourself making 3+ similar tool calls in a row, stop and delegate.
- Context growing beyond ~50 messages? Call `compress()` — do not continue.
- Don't know how to proceed? Call `escalate()` — do not spin in circles.
- Never synthesize from assumed results. Verification is not optional.
- A child returning `Status: failed` means the task is incomplete. Retry or escalate.
- If you can't verify a child's output, the task is not complete.
- Every sub-agent delegation must include a role. A role-less agent is an unfocused agent.
- A role is a scope constraint, not a backstory. One sentence, no fluff.
- If a role conflicts with the task description, the decomposition is wrong — re-decompose.