from __future__ import annotations

import json
from collections import deque
from typing import TYPE_CHECKING, Any

from .task import (
    BudgetRequest,
    Escalation,
    Failure,
    ReportPayload,
    Task,
    TaskStatus,
)

if TYPE_CHECKING:
    from ..llm.provider import LLMProvider
    from .runtime import Runtime


AGENT_SYSTEM_PROMPT = """\
You are an agent in a recursive tool-calling harness.
Your role is to decompose tasks, delegate to sub-agents, verify their output,
and synthesize results. You are NOT a doer — you are an orchestrator.

## Available tools

- **read(path)**: Read a file from disk
- **write(path, content)**: Write content to a file
- **glob(pattern)**: List files matching a glob pattern (e.g. `**/*.py`)
- **grep(pattern, include, path)**: Search file contents using a regex
- **bash(command, timeout)**: Execute a shell command
- **webfetch(url)**: Fetch content from a URL
- **edit(path, old_string, new_string)**: Find-and-replace text in a file
- **spawn(description)**: Create a sub-agent to handle a subtask autonomously.
  The sub-agent sees ONLY your description — nothing from your parent.
  Returns: the child's status, ID, report summary, artifact IDs, and
  confidence (if set). For failures, returns the failure reason.
  See "Spawn description rules" below.
- **read_artifact(artifact_id)**: Read an artifact by its ID. Use this to
  look up a child agent's report contents from the artifact store when you
  know the artifact ID but not the file path.
- **ask(question)**: Ask the user for clarification or confirmation
- **compress()**: Compress your full conversation into a summary and reset
  your context. Use when your context is heavy.
- **converse(agent_id, message)**: Send a message to a child agent by ID.
  Use to query a child's results or ask follow-up questions.
- **report(summary, artifact_ids, confidence?)**: Submit your final result.
  Include artifact_ids for any files written. Optionally include a
  confidence score (0.0–1.0). Call ONLY when verified and complete.
- **escalate(issue)**: Ask your parent for help. Use when you cannot
  resolve a problem yourself.
- **fail(error)**: Report an unrecoverable failure.

---

## Mandatory workflow — follow this sequence exactly

### 1. ANALYZE
Read your task description. Identify everything you need to find, change,
or produce. Output a decomposition plan before calling any other tool.

### 2. DECOMPOSE
Group the work into independent units. Each unit = one sub-agent spawn.
If units are independent, spawn them in parallel (multiple spawn() calls
in the same turn). If one unit depends on another, spawn the first, verify
its output, then spawn the second.

### 3. DELEGATE
Spawn sub-agents for every unit. The spawn description is the sub-agent's
ENTIRE WORLD — it knows nothing else. Every sub-agent MUST write its findings
to disk and call report() with the file paths in artifact_ids.

**Delegation rule:** If a sub-task requires 2 or more tool calls, SPAWN.
If it requires 0–1 calls (e.g. reading one known file path), do it directly.
Never accumulate turns grinding through search results yourself — spawn.

### 4. VERIFY — CRITICAL, do not skip
After spawn() returns, you receive the child's status, ID, report summary,
artifact IDs, and optionally a confidence score. Use this information
immediately — the summary tells you what the child found, but you still
need to verify the actual artifacts.

For EVERY child that completed:
  a. Read the child's summary from the spawn return. Check that it addresses
     the task you assigned.
  b. Read its artifact file(s) from disk using read(path). You can also use
     read_artifact(artifact_id) if you prefer to read from the artifact store.
  c. Confirm the content is non-empty and matches the task you assigned.
  d. If the artifact is missing or empty, use converse(child_id, "...")
     to query the child.
For ANY child that failed:
  a. Read the failure reason from the spawn return.
  b. Evaluate whether a better description would fix it → respawn.
  c. If the problem is structural → escalate().

**NEVER synthesize from assumed results.** If you cannot verify a child's
output, the task is NOT complete. Fabricating plausible-sounding conclusions
without reading the actual artifacts is the most common and harmful failure
mode. Verification is not optional.

### 5. SYNTHESIZE
Combine the verified artifact contents into a coherent result. Your
report() summary must accurately reflect what the artifacts contain,
not what you hoped the sub-agents would find.

### 6. TERMINATE
Call report(summary, artifact_ids=[...]) with a concrete summary and
references to all relevant child artifacts. Or escalate() if blocked.
Or fail() if unrecoverable.

---

## Spawn description rules

A sub-agent's spawn description is its ONLY context. Write it with care:

1. **Be specific.** Include exact file paths, function names, expected behavior.
   BAD: "Look at the auth code."
   GOOD: "Read src/auth/login.py and find the function that validates JWT
   expiry."

2. **State the outcome, not the process.** Say what should exist or be true
   when done, not which loops to write.
   BAD: "Write a for loop over items."
   GOOD: "Return a list of all items with status 'pending'."

3. **Specify work type.** Tell the sub-agent whether to write code, search,
   or report findings. "Read-only" vs "make changes and run tests."

4. **Include verification.** E.g. "After making changes, run
   `pytest tests/test_auth.py` and confirm all tests pass."

5. **Keep it focused.** One task per spawn. Split unrelated work into
   separate spawns. Two focused sub-agents outperform one overloaded one.

6. **Specify conventions.** Mention frameworks, naming conventions, imports.
   Reference neighboring files as style examples.

7. **Mandate artifacts.** Require the sub-agent to write() its findings
   and include paths in its report() artifact_ids. E.g.
   "Write your findings to /tmp/auth_analysis.txt and include that path
   in your report() artifact_ids."

8. **Define acceptance criteria.** The sub-agent must know exactly when it
   is done. E.g. "Your task is complete when auth_analysis.txt contains
   the function name, its line number, and whether the expiry check exists."

---

## Context health

Before each turn you receive a Context Observation with your turn count,
message count, estimated tokens, and original task. Act on it:

| Signal | Action |
|---|---|
| <5 turns, <15 messages | Healthy — continue or delegate |
| 5–15 turns, growing messages | Spawn sub-agents for remaining work |
| >15 turns or >50 messages | Call compress() IMMEDIATELY |
| Repeated similar tool calls (3+) | Stop grinding. Spawn a sub-agent. |

---

## Rules

- You do NOT know about siblings, cousins, or the global task graph.
  You see only your task, your parent, and your children.
- Write important data to disk with write(). Reference files by path.
- spawn() runs the sub-agent to completion before returning. The return
  includes the child's status, report summary, artifact IDs, and confidence
  (if set). For failures, it includes the failure reason.
  Still verify artifacts — the summary is a preview, not the full result.
- A child returning Status: failed means your task is INCOMPLETE.
  Retry with a better description or escalate. Never ignore it.
- If you make 3+ similar tool calls in a row, you are stuck. Spawn.
- If your context passes 50 messages and you haven't compressed, you are
  degrading. Compress.
- If you cannot verify a child's output, you are not done.
- Use confidence scores (<0.5) as signals that findings may be unreliable.
  Escalate or re-investigate low-confidence results.
- Never synthesize from assumptions. Read the artifacts.
"""


class Agent:
    def __init__(
        self,
        agent_id: str,
        task: Task,
        runtime: Runtime,
        parent: Agent | None = None,
        *,
        safety_max_iterations: int = 500,
        repeated_call_limit: int = 5,
    ) -> None:
        self.id = agent_id
        self.task = task
        self._runtime = runtime
        self.parent = parent
        self.children: list[Agent] = []
        self._safety_max_iterations = safety_max_iterations
        self.repeated_call_limit = repeated_call_limit
        self._messages: list[dict[str, Any]] | None = None
        self._iteration: int = 0
        self._recent_batches: deque[list[tuple[str, frozenset[tuple[str, object]]]]] | None = None
        self._last_report: ReportPayload | None = None
        self._last_failure: Failure | None = None

    @property
    def llm(self) -> LLMProvider | None:
        return self._runtime._llm

    @property
    def guidelines(self) -> str:
        return AGENT_SYSTEM_PROMPT

    async def run(self) -> None:
        llm = self.llm
        if not llm:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary=f"Agent {self.id} executed: {self.task.description}",
            ))
            return

        self._messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": self.task.description},
        ]
        self._iteration = 0
        self._recent_batches = deque(maxlen=self.repeated_call_limit)
        await self._run_loop()

    async def continue_with_input(self, user_message: str) -> None:
        if self._messages is None:
            self.task.description = user_message
            await self.run()
            return
        self.task.status = TaskStatus.running
        self._messages.append({"role": "user", "content": user_message})
        await self._run_loop()

    async def _run_loop(self) -> None:
        assert self._messages is not None
        llm = self.llm
        assert llm is not None
        tools = self._runtime.tool_registry.openai_schemas()

        while True:
            self._iteration += 1
            if self._iteration > self._safety_max_iterations:
                self.fail(f"Safety limit reached ({self._safety_max_iterations} iterations)")
                return

            usage = self._runtime._agent_usage.get(self.id, {})
            prompt_tokens = usage.get("prompt_tokens", 0)

            context_obs = (
                f"[Context Observation]\n"
                f"Turn: {self._iteration}\n"
                f"Messages in context: {len(self._messages)}\n"
                f"Estimated prompt tokens this agent: {prompt_tokens}\n"
                f"Your task: {self.task.description}\n"
            )
            self._messages.append({"role": "system", "content": context_obs})

            response = await llm.generate_with_tools(self._messages, tools)

            if response.usage:
                self._runtime.record_usage(
                    self.id,
                    prompt_tokens=response.usage.get("prompt_tokens", 0),
                    completion_tokens=response.usage.get("completion_tokens", 0),
                    message_count=len(self._messages),
                )

            ts = self._runtime.trace_store
            if ts:
                ts.record_llm_request(self.id, list(self._messages))

            if response.tool_calls:
                assistant_msg: dict[str, Any] = {"role": "assistant", "content": response.content or ""}
                assistant_msg["tool_calls"] = []
                results: list[dict[str, Any]] = []

                tc_info = []
                for tc in response.tool_calls:
                    tc_info.append({
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                    })
                    assistant_msg["tool_calls"].append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    })

                if ts:
                    ts.record_llm_response(self.id, response.content, response.model, response.usage, tc_info)

                for tc in response.tool_calls:
                    if ts:
                        ts.record_tool_call(self.id, tc.id, tc.name, tc.arguments)
                    result = await self._runtime.tool_registry.execute(
                        tc.name, tc.id, agent=self, **tc.arguments
                    )
                    if ts:
                        ts.record_tool_result(self.id, tc.id, tc.name, result.content)
                    results.append({
                        "role": "tool",
                        "tool_call_id": result.tool_call_id,
                        "content": result.content,
                    })

                    if self.task.status in (TaskStatus.completed, TaskStatus.failed, TaskStatus.escalated):
                        self._messages.append(assistant_msg)
                        self._messages.extend(results)
                        return

                self._messages.append(assistant_msg)
                self._messages.extend(results)

                batch_sig = tuple(
                    (tc.name, frozenset(tc.arguments.items()))
                    for tc in response.tool_calls
                )
                assert self._recent_batches is not None
                self._recent_batches.append(batch_sig)

                if (
                    len(self._recent_batches) == self.repeated_call_limit
                    and all(sig == batch_sig for sig in self._recent_batches)
                ):
                    self.fail(
                        f"Repeated identical tool calls {self.repeated_call_limit} times in a row "
                        f"(tool: {response.tool_calls[0].name}). The provider may be stuck."
                    )
                    return
            else:
                if ts:
                    ts.record_llm_response(self.id, response.content, response.model, response.usage)
                content = response.content or ""
                self.report(ReportPayload(
                    task_id=self.task.id,
                    summary=content,
                ))
                return

    def spawn(self, description: str, agent_type: str | None = None, **metadata: object) -> Agent:
        child_task = Task(description=description, parent_id=self.task.id, metadata=metadata)
        child = self._runtime.spawn_agent(child_task, parent=self, agent_type=agent_type)
        self.children.append(child)
        return child

    def report(self, payload: ReportPayload) -> None:
        self._last_report = payload
        self._runtime.deliver_report(self.id, payload)

    def request_more_budget(self, current_usage: int, requested: int, reason: str) -> None:
        req = BudgetRequest(task_id=self.task.id, current_usage=current_usage, requested=requested, reason=reason)
        self._runtime.deliver_budget_request(self.id, req)

    def escalate(self, issue: str, **context: object) -> None:
        e = Escalation(task_id=self.task.id, issue=issue, context=context)
        self._runtime.deliver_escalation(self.id, e)

    def fail(self, error: str, trace: str | None = None) -> None:
        f = Failure(task_id=self.task.id, error=error, trace=trace)
        self._last_failure = f
        self._runtime.deliver_failure(self.id, f)
