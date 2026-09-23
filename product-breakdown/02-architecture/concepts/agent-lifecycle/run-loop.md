# The Run Loop

`await agent.run()` initializes the conversation, then executes the tool-calling
loop until a terminal tool fires.

## Phase 1 — Initialization

```python
async def run(self) -> None:
    llm = self.llm  # Get LLM from runtime
    if not llm:
        # No-LLM mode: fail immediately
        self.fail("No LLM provider configured")
        return

    # Format the user message
    user_message = self.task.description
    if self.task.role:
        user_message = f"[ROLE] {self.task.role}\n\n[TASK] {self.task.description}"

    # Build initial messages
    self._messages = [
        {"role": "system", "content": self._system_prompt or AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    self._iteration = 0
    self._recent_batches = deque(maxlen=self.repeated_call_limit)
    await self._run_loop()
```

## Phase 2 — The Tool-Calling Loop

Each iteration:

```
┌─────────────────────────────────────────┐
│ 1. Increment turn counter               │
│ 2. Safety check: max iterations?        │ → fail() if exceeded
│ 3. Append Context Observation           │
│ 4. Call llm.generate_with_tools()       │
│ 5. Record usage, trace request          │
│                                         │
│ Has tool calls?                         │
│   YES → Execute each tool               │
│          ├── Feed results as messages   │
│          ├── Check for terminal status   │
│          └── Safety: repeated calls?    │ → fail() if 5 identical
│   NO  → Treat content as report         │
│          └── report(content)            │
└─────────────────────────────────────────┘
```

## Context Observation

Before each turn the agent appends a system message:

```
[Context Observation]
Turn: 7
Messages in context: 21
Estimated prompt tokens this agent: 12000
Your task: Audit auth.py for security issues
```

This observation lets the LLM monitor its own context health and choose between
delegation, continuation, and compression.
