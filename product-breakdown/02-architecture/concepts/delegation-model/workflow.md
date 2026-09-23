# The Mandatory Workflow

Every agent except a leaf follows:

```
ANALYZE → DECOMPOSE → DELEGATE → VERIFY → SYNTHESIZE → TERMINATE
```

## Step 1: ANALYZE

Read the task description. Identify all separable concerns. If the task is
already narrow (one specific file, one command), skip to TERMINATE — you are a
leaf agent.

## Step 2: DECOMPOSE

Group the work into independent units. Each unit becomes one delegation. Assign
a **role** to each sub-agent that scopes its focus.

```
Task: "Audit the auth module for security and performance issues"

Decomposition:
  Unit A: Security audit → role: "Security Auditor"
  Unit B: Performance audit → role: "Performance Analyst"
```

Sequential dependencies stay as one unit. Independent units become parallel
delegations.

## Step 3: DELEGATE

Call `delegate()` for each unit. **All delegations in one turn** for maximum
parallelism. The delegate tool runs the child to completion before returning.

```
Turn 1: delegate(A), delegate(B)  ← Both in parallel
```

What the child sees:
- The delegation description (its entire world)
- The assigned role (scope constraint)
- The mission-command intent block, if the parent set it (intent / end state /
  constraints / authority) — baked into the child's system prompt so it survives
  compression and prune (the framework's context-management workflow erases the
  user message, not the system message)
- The baseline mission-command clause (honor intent, adapt, report deviations)
  from its own system prompt — always present, even on bare delegations
- Nothing from the grandparent or siblings

## Step 4: VERIFY

**This is the most frequently violated step.** After delegation returns:

1. Check the child's status — must be `completed`
2. Read the child's artifact file(s) — confirm they exist and are non-empty
3. Confirm the content satisfies the `end_state` you briefed — the requirement
   is the outcome, not the plan
4. If verification fails: re-delegate or escalate

**Never synthesize from assumed results.** Blind synthesis — reporting what you
asked for instead of what the child found — is the most harmful failure mode.

## Step 5: SYNTHESIZE

Combine verified artifact contents into a coherent result. Reference all child
artifact IDs.

## Step 6: TERMINATE

Call `report()` with a concrete, verifiable summary. Or `escalate()` if blocked.
Or `fail()` if unrecoverable.
