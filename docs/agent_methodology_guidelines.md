# Agent Methodology: Guidelines & Priorities

Based on analysis of `AGENT_SYSTEM_PROMPT` in `src/dynamic_harness/core/agent.py`.

## Core Philosophy

The harness implements a **recursive decomposition** methodology. An agent's job is not to do work directly, but to break work into pieces and delegate. Deep context = degraded focus = wasted cost.

> **Golden rule:** If a sub-task requires more than 1–2 tool calls, spawn a sub-agent. Never accumulate turn debt.

---

## Mandatory Workflow

Every agent invocation must follow this sequence. Deviation is a methodology violation.

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. ANALYZE   →  Identify separable sub-tasks from your description │
│  2. DECOMPOSE  →  Group into independent units of work              │
│  3. DELEGATE   →  Spawn sub-agents in parallel for each unit        │
│  4. VERIFY     →  Confirm each sub-agent's artifact exists & valid  │
│  5. SYNTHESIZE →  Combine verified results into your report         │
│  6. TERMINATE  →  report() / escalate() / fail()                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Step-by-step requirements

| Step | Action | Exit condition |
|------|--------|---------------|
| **ANALYZE** | Read your task description. List what you need to find, change, or produce. | You have a bullet-point decomposition. |
| **DECOMPOSE** | Group bullets into units. Each unit = one independent sub-agent. If a unit has sequential dependencies, it's still one sub-agent. Only independent units get separate spawns. | You have N spawn descriptions ready. |
| **DELEGATE** | Call `spawn()` for each unit. All spawns in one turn for maximum parallelism. | All sub-agents return `Status: completed`. |
| **VERIFY** | For each child: read its artifact file, confirm the output matches the spawn description. If a child returned `Status: failed`, spawn a replacement or escalate. | Every child's output is confirmed. |
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
          └── 2+ calls  → SPAWN A SUB-AGENT
```

**Exceptions where direct action is acceptable even with 2+ calls:**
- You are a leaf agent whose entire task is reading 2–3 specific files and reporting
- You have already been given file paths and just need to read them
- A single bash command with a follow-up read (2 calls total, tightly coupled)

**Delegation anti-signals — stop and spawn if:**
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

- Spawn multiple sub-agents **in the same turn** so they explore independently.
- Each sub-agent should do **one thing well**.
- Prefer two parallel sub-agents over one agent with a two-part sequential task.
- The spawn description is the sub-agent's **entire world** — it knows nothing else.

### P2 — Keep Your Own Context Shallow

- Your role: decompose, delegate, verify, synthesize.
- If you read more than 1–2 files directly, you have accumulated too much noise.
- Read **summaries and artifact files** from sub-agents, not the raw source they already processed.
- Each raw source file you read is a failure of delegation.

### P3 — Verify Before Synthesizing

**This is the most frequently violated principle.** After a sub-agent reports:

1. Read the artifact file(s) it wrote (use `read()` with the paths it reported).
2. Confirm the content is non-empty and matches the spawn description.
3. If verification fails — spawn a replacement or escalate. Never synthesize from assumed results.
4. When a child returns `Status: failed`, do not proceed — the task is incomplete.

### P4 — Use Artifact-Driven Communication

- Sub-agents **must** write findings to disk via `write()`.
- Reference files by path; do not pass large raw data in-memory.
- Sub-agents call `report(summary, artifact_ids=[...])`. The parent reads the artifact file.
- The spawn tool returns only `"Spawned agent completed. Status: X. ID: abc123"` — you will **not** see the child's report contents automatically. You **must** read its artifacts.

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
| Medium turns (5–15), growing messages | Spawn sub-agents for remaining work |
| Many turns (>15) | Call `compress()` **immediately** |
| Context > ~50 messages | Call `compress()`, then re-evaluate |
| Repeated similar tool calls (3+) | Stop. Spawn sub-agent. Do not grind. |

### P6 — Quality of Spawn Descriptions

A vague description produces a wandering sub-agent. Follow these rules:

1. **Be specific** — include exact file paths, function names, expected behavior
2. **State what, not how** — describe the desired outcome, not implementation steps
3. **Specify work type** — tell the sub-agent whether to write code, search, or just report
4. **Include verification** — e.g., "Run `pytest tests/test_auth.py` after making changes and confirm all tests pass"
5. **Keep focused** — one task per spawn, not a list of unrelated chores
6. **Specify conventions** — framework, naming, imports, neighboring files as examples
7. **Provide context** — include any task-level knowledge the sub-agent needs (it sees ONLY your spawn description, nothing from your parent)
8. **Clear acceptance criteria** — tell the sub-agent exactly what "done" looks like
9. **Required output format** — specify what artifacts to write and what `report()` should contain

### P7 — Terminate Clearly

| State | Method | When |
|---|---|---|
| Success | `report(summary, artifact_ids=[...])` | All sub-agents verified, synthesis complete |
| Blocked | `escalate(issue)` | Cannot proceed without parent intervention |
| Irrecoverable | `fail(error)` | Cannot proceed at all |

---

## Anti-Patterns

These are the most common failure modes observed in agent behavior. **All of them are methodology violations.**

### AP-1: Skipping decomposition

**What it looks like:** Agent receives task → immediately calls `glob()` or `grep()`.

**Why it fails:** Without a plan, the agent grinds through search results turn-by-turn, accumulating context bloat without clear direction. By turn 15, the original task is diluted.

**Fix:** Output a decomposition plan as the first action. List sub-tasks, then spawn sub-agents. If the LLM won't output a plan, the task description may be too vague.

### AP-2: Doing it all yourself

**What it looks like:** Agent makes 5, 10, 20+ tool calls itself without spawning.

**Why it fails:** Context accumulates. Turn 20 sees the task description buried under 18 system observations. Focus degrades. Cost scales with context length unnecessarily.

**Fix:** After 3 tool calls without a spawn, ask: "Could a sub-agent do this?" The answer is almost always yes.

### AP-3: Blind synthesis

**What it looks like:** Parent spawns children → receives `"Status: completed"` → calls `report()` with a synthesis based on the spawn description, not the child's actual output.

**Why it fails:** The parent synthesizes what it *asked for*, not what the child actually *found*. The child's results are ignored. This produces correct-looking but factually wrong output.

**Fix:** After spawn returns, read the child's artifact file. Confirm it exists and its content is relevant. Only then synthesize.

### AP-4: Mega-spawn

**What it looks like:** `spawn(description="First, do X. Then check Y. After that, modify Z. Finally, run tests and report.")`

**Why it fails:** The sub-agent has a multi-step sequential task with no clear focus. It's essentially a root-level task masquerading as a sub-task. The sub-agent's context grows, it loses focus, and the parent can't verify intermediate steps.

**Fix:** Split into independent spawns. `spawn("Do X")` and `spawn("Check Y")` are better than one mega-spawn. If X and Y are sequential, Y should be spawned after X completes and its artifact is verified.

### AP-5: Abandoning failed children

**What it looks like:** Parent spawns children → one returns `"Status: failed"` → parent ignores it and synthesizes from the successful children.

**Why it fails:** The parent produces a partial result, missing critical information. The task's original goal is not met, but the parent reports success.

**Fix:** When a child fails, evaluate: can another child be spawned with a better description? If yes, retry. If no, escalate with the failure context. Never report success with missing pieces.

### AP-6: Vague spawn descriptions

**What it looks like:** `spawn(description="Look at the auth code and fix issues")`

**Why it fails:** The sub-agent wanders. "Look at" is directionless. "Fix issues" has no acceptance criteria. The sub-agent has no way to know when it's done.

**Fix:** `spawn(description="Read src/auth/login.py and find the function that validates JWT expiry. If the expiry check is missing or incorrect (should reject tokens older than 3600 seconds), add the check. Run `pytest tests/test_auth.py` to verify. Write a summary of changes to /tmp/auth_fix_summary.txt and call report() with that file path as an artifact.")`

### AP-7: Hallucinating sub-agent output

**What it looks like:** Parent spawns children → receives status strings → in the `report()` summary, the parent describes detailed findings that the children never actually produced. The parent invents plausible content.

**Why it fails:** The parent's LLM fills in gaps with fabricated detail because it wasn't given the actual child results. The output sounds authoritative but is fiction.

**Fix:** The parent must read artifact files before synthesizing. If verification is enforced (see P3), this cannot happen.

### AP-8: Infinite context growth

**What it looks like:** Agent keeps calling tools, context grows to 80+ messages, agent shows no sign of terminating.

**Why it fails:** Beyond ~50 messages, context degradation accelerates. The agent starts repeating itself, forgetting early context, and making errors. Cost per turn grows linearly with context length.

**Fix:** Context observation triggers (see P5). At 50+ messages, call `compress()`. Do not wait.

---

## Verification Protocol

After each `spawn()` call returns, follow this protocol **for each child** before proceeding:

```
Child spawned: X
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
- [ ] Every spawned child has `Status: completed`
- [ ] Every child's artifact file has been read and its content confirmed
- [ ] The synthesis accurately reflects (not fabricates) the artifact contents
- [ ] Any child that failed has been retried or escalated
- [ ] The final `report()` includes all relevant child artifact IDs

---

## Good vs Bad: Concrete Examples

### Spawn descriptions

**BAD:**
> "Check the repo for security issues and fix them."

**GOOD:**
> "Run `bandit -r src/ -f json` to scan for security issues. Parse the output and for each finding with severity HIGH, identify the file and line. Write the findings to `/tmp/security_findings.json`. Do NOT make code changes — this is a read-only scan. Call `report()` with a summary of HIGH-severity issues found and the artifact path."

**Why it's good:** Specific tool, specific output file, clear scope (read-only, HIGH only), clear acceptance criteria.

---

**BAD:**
> "Improve the test coverage."

**GOOD:**
> "Run `pytest --cov=src/dynamic_harness/core --cov-report=term-missing` to find untested lines. Focus on `runtime.py`. Identify the top 3 functions with the most uncovered lines. For each, write a test in `tests/test_runtime.py` following the existing test patterns (use the same fixtures and assert style). Run the new tests to confirm they pass. Write a summary of what you added to `/tmp/coverage_improvements.txt` and call `report()` with that file as an artifact."

**Why it's good:** Bounded scope (one file, top 3), existing conventions referenced, verification step included, output artifact specified.

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
         spawn(A), spawn(B), spawn(C)  ← all in one turn
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
| Sub-agent returns `Status: failed` | Read its last messages via `converse(child_id, "What went wrong?")`. If the issue is clearable (e.g., missing file, typo in the description), spawn a replacement with a corrected description. If the issue is structural (e.g., tool limitation), escalate. |
| Sub-agent reports success but artifact is empty/missing | `converse(child_id, "Your artifact at path X is empty. Did you write your findings?")`. If the child confirms it wrote to a different path, read that. Otherwise, respawn. |
| Sub-agent hit safety limits | It ran 500 iterations or 5 repeated calls. The task was too broad or ambiguous. Respawn with a narrower, more specific description. |
| Sub-agent returns `Status: escalated` | Its issue is now your issue. Read its escalation context, decide if you can resolve it or must pass it up via your own `escalate()`. |
| Multiple children all fail | The task decomposition is likely wrong. Escalate with a summary of what each child was asked to do and why they failed. |

---

## Cost-Effectiveness Heuristics

| Action | Approx. tokens | When to use |
|---|---|---|
| Read a known file path | ~500–2000 | File is small, path is specific |
| Spawn a sub-agent | ~2000–5000 overhead | Sub-task needs 2+ calls |
| Compress context | ~5000–15000 | Context > ~50 messages |
| Grind through many reads yourself | 0 + turn cost × N | **Never** — this is delegation failure |

**Rule of thumb:** A spawn costs ~3000 tokens overhead (system prompt + spawn description). If doing it yourself would take 3+ turns at 2000+ tokens/turn, spawning is cheaper **and** produces better quality (fresh context for each sub-task).

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
| Delegate | Spawn sub-agents, don't do it yourself |
| Verify | Confirm every child's output before synthesizing |
| Parallelize | Run sub-agents concurrently in one turn |
| Stay shallow | Keep your context lean; read summaries, not raw source |
| Write artifacts | Findings → disk, not in-memory |
| Monitor context | Compress or escalate when context grows heavy |
| Describe well | Specific, focused, verifiable spawn descriptions |
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