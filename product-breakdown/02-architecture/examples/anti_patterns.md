# Anti-Patterns

The most common failure modes observed in agent behavior. **All of them are
methodology violations.**

## AP-1: Skipping decomposition
**Looks like:** Agent receives task → immediately calls `glob()` or `grep()`.
**Why:** Without a plan the agent grinds through search results turn-by-turn,
accumulating bloat without direction; by turn 15 the task is diluted.
**Fix:** Output a decomposition plan first, then delegate. If the LLM won't plan,
the task description may be too vague.

## AP-2: Doing it all yourself
**Looks like:** Agent makes 5, 10, 20+ tool calls itself without delegating.
**Why:** Context accumulates; turn 20 sees the task buried under 18 system
observations. Focus degrades and cost scales unnecessarily.
**Fix:** After 3 tool calls without a delegation, ask "Could a sub-agent do
this?" The answer is almost always yes.

## AP-3: Blind synthesis
**Looks like:** Parent receives `"Status: completed"` → calls `report()` based on
the delegation description, not the child's actual output.
**Why:** The parent synthesizes what it *asked for*, not what the child *found* —
correct-looking but factually wrong output.
**Fix:** Read the child's artifact file; confirm it exists and is relevant. Only
then synthesize.

## AP-4: Mega-delegation
**Looks like:** `delegate(description="First, do X. Then check Y. After that,
modify Z. Finally, run tests and report.")`
**Why:** A multi-step sequential task with no focus — a root-level task
masquerading as a sub-task. Its context grows, it loses focus, and the parent
can't verify intermediate steps.
**Fix:** Split into independent delegations. Sequential steps are delegated after
the prior step's artifact is verified.

## AP-5: Abandoning failed children
**Looks like:** One child returns `"Status: failed"` → parent ignores it and
synthesizes from the successful children.
**Why:** The result is partial and missing critical information, yet the parent
reports success.
**Fix:** Can another child be delegated with a better description? Retry; else
escalate with the failure context. Never report success with missing pieces.

## AP-6: Vague delegation descriptions
**Looks like:** `delegate(description="Look at the auth code and fix issues")`
**Why:** "Look at" is directionless; "fix issues" has no acceptance criteria, so
the sub-agent can't know when it's done.
**Fix:** Name exact paths, the change, the verification command, and the artifact —
e.g. "Read src/auth/login.py, add the JWT-expiry (3600s) check, run
`pytest tests/test_auth.py`, write outputs/auth_fix_summary.txt, report() it."

## AP-7: Hallucinating sub-agent output
**Looks like:** Parent receives only status strings → in `report()` it describes
detailed findings the children never produced.
**Why:** The parent's LLM fills gaps with fabricated detail. The output sounds
authoritative but is fiction.
**Fix:** Read artifact files before synthesizing. Enforced verification (P3)
prevents this.

## AP-8: Infinite context growth
**Looks like:** Agent keeps calling tools, context grows to 80+ messages, no sign
of terminating.
**Why:** Beyond ~50 messages, degradation accelerates — repetition, forgotten
context, errors — and cost per turn grows linearly.
**Fix:** At 50+ messages, call `compress()`. Do not wait.

## AP-9: Missing or conflicting roles
**Looks like:** Delegating without roles, or roles that contradict the task —
`delegate(description="Analyze the repo")` (no scope) or "You are a
Documentation Writer. Fix the login bug."
**Why:** Without a role the agent treats every concern as its responsibility
(scope creep, bloat); a conflicting role tears it between role and task.
**Fix:** Assign a role aligned with the task (P8). If a task crosses domains,
split it into role-scoped sub-agents or use a light coordinator role.
