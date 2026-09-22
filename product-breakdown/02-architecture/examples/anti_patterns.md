# Anti-Patterns

The most common failure modes observed in agent behavior. **All of them are methodology violations.**

## AP-1: Skipping decomposition

**What it looks like:** Agent receives task → immediately calls `glob()` or `grep()`.

**Why it fails:** Without a plan, the agent grinds through search results turn-by-turn, accumulating context bloat without clear direction. By turn 15, the original task is diluted.

**Fix:** Output a decomposition plan as the first action. List sub-tasks, then delegate to sub-agents. If the LLM won't output a plan, the task description may be too vague.

## AP-2: Doing it all yourself

**What it looks like:** Agent makes 5, 10, 20+ tool calls itself without delegating.

**Why it fails:** Context accumulates. Turn 20 sees the task description buried under 18 system observations. Focus degrades. Cost scales with context length unnecessarily.

**Fix:** After 3 tool calls without a delegation, ask: "Could a sub-agent do this?" The answer is almost always yes.

## AP-3: Blind synthesis

**What it looks like:** Parent delegates to children → receives `"Status: completed"` → calls `report()` with a synthesis based on the delegation description, not the child's actual output.

**Why it fails:** The parent synthesizes what it *asked for*, not what the child actually *found*. The child's results are ignored. This produces correct-looking but factually wrong output.

**Fix:** After delegation returns, read the child's artifact file. Confirm it exists and its content is relevant. Only then synthesize.

## AP-4: Mega-delegation

**What it looks like:** `delegate(description="First, do X. Then check Y. After that, modify Z. Finally, run tests and report.")`

**Why it fails:** The sub-agent has a multi-step sequential task with no clear focus. It's essentially a root-level task masquerading as a sub-task. The sub-agent's context grows, it loses focus, and the parent can't verify intermediate steps.

**Fix:** Split into independent delegations. `delegate("Do X")` and `delegate("Check Y")` are better than one mega-delegation. If X and Y are sequential, Y should be delegated after X completes and its artifact is verified.

## AP-5: Abandoning failed children

**What it looks like:** Parent delegates to children → one returns `"Status: failed"` → parent ignores it and synthesizes from the successful children.

**Why it fails:** The parent produces a partial result, missing critical information. The task's original goal is not met, but the parent reports success.

**Fix:** When a child fails, evaluate: can another child be delegated with a better description? If yes, retry. If no, escalate with the failure context. Never report success with missing pieces.

## AP-6: Vague delegation descriptions

**What it looks like:** `delegate(description="Look at the auth code and fix issues")`

**Why it fails:** The sub-agent wanders. "Look at" is directionless. "Fix issues" has no acceptance criteria. The sub-agent has no way to know when it's done.

**Fix:** `delegate(description="Read src/auth/login.py and find the function that validates JWT expiry. If the expiry check is missing or incorrect (should reject tokens older than 3600 seconds), add the check. Run `pytest tests/test_auth.py` to verify. Write a summary of changes to outputs/auth_fix_summary.txt and call report() with that file path as an artifact.")`

## AP-7: Hallucinating sub-agent output

**What it looks like:** Parent delegates to children → receives status strings → in the `report()` summary, the parent describes detailed findings that the children never actually produced. The parent invents plausible content.

**Why it fails:** The parent's LLM fills in gaps with fabricated detail because it wasn't given the actual child results. The output sounds authoritative but is fiction.

**Fix:** The parent must read artifact files before synthesizing. If verification is enforced (see P3), this cannot happen.

## AP-8: Infinite context growth

**What it looks like:** Agent keeps calling tools, context grows to 80+ messages, agent shows no sign of terminating.

**Why it fails:** Beyond ~50 messages, context degradation accelerates. The agent starts repeating itself, forgetting early context, and making errors. Cost per turn grows linearly with context length.

**Fix:** Context observation triggers (see P5). At 50+ messages, call `compress()`. Do not wait.

## AP-9: Missing or conflicting roles

**What it looks like:** Delegating to sub-agents without role specifications, or assigning roles that contradict the task description.

Examples:
- `delegate(description="Analyze the repo")` — no role, agent has no scope boundaries
- `delegate(description="You are a Documentation Writer. Fix the login bug.")` — role says docs, task says code fix

**Why it fails:** Without a role, the agent treats every concern as its responsibility — leading to scope creep, context bloat, and unfocused output. With a conflicting role, the agent is torn between its role constraints and the task requirements.

**Fix:** Always assign a role that aligns with the task, following P8 guidelines. If a task genuinely crosses domains, either split it into multiple role-scoped sub-agents or use a light coordinator role (e.g., "You are an Orchestrator. Decompose and delegate, do not implement.").