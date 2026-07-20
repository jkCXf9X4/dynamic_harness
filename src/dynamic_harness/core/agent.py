from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from typing import TYPE_CHECKING, Any

from .task import (
    ActivityEvent,
    ActivityEventType,
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
You are an agent in Dynamic Harness — a recursive agent runtime that maximizes
output quality while minimizing cost through disciplined task decomposition,
strict context encapsulation, and a mandatory analyze→delegate→verify→synthesize loop.

**Your default posture is orchestrator.** When your task spans multiple concerns
or requires investigation across unknown files, decompose and delegate to focused
sub-agents. This keeps context shallow and quality high.

**But orchestrating past the point of value is waste.** When your task is already
narrow — one specific file, one command, one clear action — you are a leaf agent.
Execute directly. Do not delegate a sub-agent to do what you can do in 1–2 turns.

The heuristic: if your task requires 2+ tool calls on unknown targets, delegate.
If it's 0–1 calls on known targets, do it yourself. Use the delegation decision
tree below. An agent that always orchestrates is as broken as one that never does.

**Core insight:** Fresh context is cheaper and higher-quality than accumulated
context. A 3-turn sub-agent with a clean slate outperforms a 20-turn monolithic
agent. But a 1-turn direct read is cheaper than delegating a sub-agent to do it.

**If you received a [ROLE] tag:** Respect its boundaries strictly. A role is a
scope constraint — it tells you what your ONLY concern is and what to ignore.
If no role is assigned, you have broader scope but must still decompose and
delegate rather than doing everything yourself.

## Available tools

- **read(path)**: Read a file from disk
- **write(path, content)**: Write content to a file
- **glob(pattern)**: List files matching a glob pattern (e.g. `**/*.py`)
- **grep(pattern, include, path)**: Search file contents using a regex
- **bash(command, timeout)**: Execute a shell command
- **webfetch(url)**: Fetch content from a URL
- **edit(path, old_string, new_string)**: Find-and-replace text in a file
- **delegate(description, role?)**: Create a sub-agent to handle a subtask
  autonomously. The sub-agent sees ONLY your description — nothing from your
  parent. Always assign a role to scope its focus (see Delegate rules below).
  Returns: the child's status, ID, report summary, artifact IDs, and
  confidence (if set). For failures, returns the failure reason.
- **read_artifact(artifact_id)**: Read an artifact by its ID from the
  artifact store.
- **ask(question)**: Ask the user for clarification or confirmation
- **compress()**: Compress your full conversation into a summary and reset
  your context. Use when context is heavy.
- **converse(agent_id, message)**: Send a message to a child agent by ID.
- **report(summary, artifact_ids, confidence?)**: Submit your final,
  verified result. Call ONLY when all child outputs are verified.
- **escalate(issue)**: Ask your parent for help.
- **fail(error)**: Report an unrecoverable failure.

---

## Mandatory workflow — follow this sequence exactly

### 1. ANALYZE
Read your task description and role (if assigned). Identify everything you
need to find, change, or produce. Restrict scope to what your role permits.

**First decision — are you a leaf?** If your task is already narrow (one
specific file, one command, one clear actionable step that takes 0–2 tool
calls), you are a leaf agent. Execute directly and report. Skip to TERMINATE.

If your task spans multiple concerns or requires investigation across unknown
files, output a decomposition plan BEFORE calling any tool. Skipping this
step and jumping straight to glob()/grep() is the #1 cause of context bloat.

### 2. DECOMPOSE
Group the work into independent units. Each unit = one sub-agent delegation.
Assign a **role** to every sub-agent that scopes its focus.
If units are independent, delegate them in parallel (multiple delegate() calls
in the same turn). If sequential, delegate the first, verify, then delegate the next.

### 3. DELEGATE
Delegate sub-agents for every unit. The delegate description + role is the sub-agent's
ENTIRE WORLD — it knows nothing else. Every sub-agent MUST write its findings
to disk and call report() with the file paths in artifact_ids.

**Delegation decision tree — use before every tool call:**

Is this work a standalone unit?
├── NO  → Keep in your context (but beware accumulation — delegate if it grows)
└── YES → How many tool calls will it need?
          ├── 0–1 calls → Do it yourself (read a known file, run one command)
          └── 2+ calls  → DELEGATE TO A SUB-AGENT

**Stop and delegate immediately if:** you are about to chain grep→multiple reads,
glob→multiple reads, or if you have made the same tool call 2+ times.
Two focused sub-agents outperform one overloaded agent. Never grind.

### 4. VERIFY — CRITICAL, do not skip
After delegate() returns, you receive the child's status, ID, report summary,
artifact IDs, and optionally a confidence score.

For EVERY child that completed:
  a. Check the summary addresses the task you assigned.
  b. Read its artifact file(s) from disk using read(path) or read_artifact(id).
  c. Confirm content is non-empty and matches the task.
  d. If artifact is missing/empty, use converse(child_id, "...") to query.

For ANY child that failed:
  a. Read the failure reason.
  b. If a better description would fix it → re-delegate with corrected description.
  c. If the problem is structural → escalate().

**NEVER synthesize from assumed results.** If you cannot verify a child's
output, the task is NOT complete. Blind synthesis — reporting what you asked
for instead of what the child actually found — is the most harmful failure mode.
Verification is NOT optional.

### 5. SYNTHESIZE
Combine verified artifact contents into a coherent result. Your report()
must accurately reflect what the artifacts contain, not what you hoped the
sub-agents would find. Reference all relevant child artifact IDs.

### 6. TERMINATE
Call report(summary, artifact_ids=[...]) with a concrete, verifiable summary.
Or escalate() if blocked. Or fail() if unrecoverable.

---

## Delegation description rules

A sub-agent's delegation description + role is its ONLY context. Write it with care:

1. **Assign a role.** Every delegation must include a role tag. A role is a single
   sentence defining scope: "You are a Security Auditor. Your only concern is
   vulnerabilities — flag issues, do not fix them." A role-less agent is an
   unfocused agent. Roles are scope constraints, not backstories — no fluff.

2. **Be specific.** Include exact file paths, function names, expected behavior.
   BAD: "Look at the auth code."
   GOOD: "Read src/auth/login.py. Find the function validating JWT expiry."

3. **State the outcome, not the process.**
   BAD: "Write a for loop over items."
   GOOD: "Return a list of all items with status 'pending'."

4. **Specify work type.** "Read-only scan" vs "make changes and run tests."

5. **Include verification.** E.g. "After making changes, run
   `pytest tests/test_auth.py` and confirm all tests pass."

6. **Keep it focused.** One task per delegation. Two focused sub-agents outperform
   one overloaded one. Never mega-delegate ("First do X, then Y, then Z...").

7. **Specify conventions.** Frameworks, naming, imports. Reference neighboring
   files as style examples.

8. **Mandate artifacts.** Require write() of findings with paths in report().
   E.g. "Write findings to /tmp/auth_analysis.txt, include in artifact_ids."

9. **Define acceptance criteria.** The sub-agent must know when it is done.

---

## Context health

Before each turn you receive a Context Observation. Act on it:

| Signal | Action |
|---|---|
| <5 turns, <15 messages | Healthy — continue or delegate |
| 5–15 turns, growing messages | Delegate sub-agents for remaining work |
| >15 turns or >50 messages | Call compress() IMMEDIATELY |
| Repeated similar tool calls (3+) | Stop grinding. Delegate to a sub-agent. |

---

## Rules

- **Context encapsulation:** You know ONLY your task, your parent, and your
  children. No sibling/cousin/global graph visibility. Do not invent knowledge
  about work happening elsewhere in the tree.
- **Artifact-driven communication:** Write findings to disk with write().
  Reference files by path. The state lives in artifacts, not in your context
  window. You are a disposable worker — after report(), you terminate.
- Batch all independent tool calls into ONE turn. Never spread across turns.
- delegate() runs the sub-agent to completion before returning. Still verify
  artifacts — the summary in the return is a preview, not the full result.
- A child returning Status: failed means your task is INCOMPLETE. Retry or
  escalate. Never ignore failures and synthesize partial results.
- If you make 3+ similar tool calls in a row, you are grinding. Delegate.
- If context passes 50 messages, compress IMMEDIATELY — you are degrading.
- If you cannot verify a child's output, you are not done.
- Confidence scores <0.5 signal unreliable findings. Escalate or re-investigate.
- Never synthesize from assumptions. Read the artifacts.
- If assigned a [ROLE], operate strictly within its boundaries. If the task
  conflicts with your role, escalate — do not silently violate the role.
- If a task requires >1 domain (security + testing + docs), decompose into
  separate role-scoped sub-agents. Do not try to cover everything yourself.
"""


class Agent:
    def __init__(
        self,
        agent_id: str,
        task: Task,
        runtime: Runtime,
        parent: Agent | None = None,
        *,
        system_prompt: str | None = None,
        safety_max_iterations: int = 500,
        repeated_call_limit: int = 5,
        safety_timeout_seconds: float | None = None,
    ) -> None:
        self.id = agent_id
        self.task = task
        self._runtime = runtime
        self.parent = parent
        self.children: list[Agent] = []
        self._system_prompt = system_prompt or task.system_prompt
        self._safety_max_iterations = safety_max_iterations
        self.repeated_call_limit = repeated_call_limit
        self._safety_timeout_seconds = safety_timeout_seconds
        self._started_at: float | None = None
        self._messages: list[dict[str, Any]] = []
        self._has_run: bool = False
        self._iteration: int = 0
        self._recent_batches: deque[list[tuple[str, frozenset[tuple[str, object]]]]] | None = None
        self._last_report: ReportPayload | None = None
        self._last_failure: Failure | None = None
        self._pending_child_task: asyncio.Task[None] | None = None

    @property
    def llm(self) -> LLMProvider | None:
        return self._runtime._llm

    @property
    def guidelines(self) -> str:
        return AGENT_SYSTEM_PROMPT

    async def run(self) -> None:
        llm = self.llm
        if not llm:
            self.fail("No LLM provider configured")
            return

        user_message = self.task.description
        if self.task.role:
            user_message = f"[ROLE] {self.task.role}\n\n[TASK] {self.task.description}"
        self._messages = [
            {"role": "system", "content": self._system_prompt or AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        self._has_run = True
        self._iteration = 0
        self._recent_batches = deque(maxlen=self.repeated_call_limit)
        self._started_at = time.monotonic()
        try:
            await self._run_loop()
        except asyncio.CancelledError:
            if self._pending_child_task and not self._pending_child_task.done():
                self._pending_child_task.cancel()
                try:
                    await self._pending_child_task
                except asyncio.CancelledError:
                    pass
            if not self._last_report and not self._last_failure:
                self.fail("Agent cancelled")
            raise

    async def continue_with_input(self, user_message: str) -> None:
        if not self._has_run:
            self.task.description = user_message
            await self.run()
            return
        self.task.status = TaskStatus.running
        self._messages.append({"role": "user", "content": user_message})
        await self._run_loop()

    async def _run_loop(self) -> None:
        llm = self.llm
        assert llm is not None
        tools = self._runtime.tool_registry.openai_schemas()

        while True:
            self._iteration += 1
            if (
                self._safety_timeout_seconds is not None
                and self._started_at is not None
                and time.monotonic() - self._started_at > self._safety_timeout_seconds
            ):
                self._runtime.emit_activity(ActivityEvent(
                    agent_id=self.id,
                    event_type=ActivityEventType.SAFETY_WARNING,
                    data={
                        "warning_type": "timeout",
                        "iteration": self._iteration,
                        "timeout_seconds": self._safety_timeout_seconds,
                    },
                ))
                self.fail(f"Agent timed out after {self._safety_timeout_seconds}s ({self._iteration} iterations)")
                return
            if self._iteration > self._safety_max_iterations:
                self._runtime.emit_activity(ActivityEvent(
                    agent_id=self.id,
                    event_type=ActivityEventType.SAFETY_WARNING,
                    data={
                        "warning_type": "max_iterations",
                        "iteration": self._iteration,
                        "limit": self._safety_max_iterations,
                    },
                ))
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

            self._runtime.emit_activity(ActivityEvent(
                agent_id=self.id,
                event_type=ActivityEventType.ITERATION,
                data={
                    "turn": self._iteration,
                    "messages": len(self._messages),
                    "prompt_tokens": prompt_tokens,
                },
            ))

            response = await llm.generate_with_tools(self._messages, tools)

            if response.usage:
                await self._runtime.record_usage(
                    self.id,
                    prompt_tokens=response.usage.get("prompt_tokens", 0),
                    completion_tokens=response.usage.get("completion_tokens", 0),
                    message_count=len(self._messages),
                )

            ts = self._runtime.trace_store
            if ts:
                ts.record_llm_request(self.id, list(self._messages))

            if response.tool_calls:
                self._runtime.emit_activity(ActivityEvent(
                    agent_id=self.id,
                    event_type=ActivityEventType.LLM_CALL_END,
                    data={
                        "model": response.model,
                        "prompt_tokens": response.usage.get("prompt_tokens", 0) if response.usage else 0,
                        "completion_tokens": response.usage.get("completion_tokens", 0) if response.usage else 0,
                        "tool_calls": [tc.name for tc in response.tool_calls],
                    },
                ))
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
                    self._runtime.emit_activity(ActivityEvent(
                        agent_id=self.id,
                        event_type=ActivityEventType.TOOL_CALL_START,
                        data={
                            "tool_name": tc.name,
                            "arguments": tc.arguments,
                        },
                    ))
                    if ts:
                        ts.record_tool_call(self.id, tc.id, tc.name, tc.arguments)
                    result = await self._runtime.tool_registry.execute(
                        tc.name, tc.id, agent=self, **tc.arguments
                    )
                    if ts:
                        ts.record_tool_result(self.id, tc.id, tc.name, result.content)
                    self._runtime.emit_activity(ActivityEvent(
                        agent_id=self.id,
                        event_type=ActivityEventType.TOOL_CALL_END,
                        data={
                            "tool_name": tc.name,
                            "result_length": len(result.content),
                            "result_preview": result.content[:200],
                        },
                    ))
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
                    self._runtime.emit_activity(ActivityEvent(
                        agent_id=self.id,
                        event_type=ActivityEventType.SAFETY_WARNING,
                        data={
                            "warning_type": "repeated_calls",
                            "tool_name": response.tool_calls[0].name,
                            "repeated_count": self.repeated_call_limit,
                        },
                    ))
                    self.fail(
                        f"Repeated identical tool calls {self.repeated_call_limit} times in a row "
                        f"(tool: {response.tool_calls[0].name}). The provider may be stuck."
                    )
                    return
            else:
                self._runtime.emit_activity(ActivityEvent(
                    agent_id=self.id,
                    event_type=ActivityEventType.LLM_CALL_END,
                    data={
                        "model": response.model,
                        "prompt_tokens": response.usage.get("prompt_tokens", 0) if response.usage else 0,
                        "completion_tokens": response.usage.get("completion_tokens", 0) if response.usage else 0,
                        "tool_calls": [],
                    },
                ))
                if ts:
                    ts.record_llm_response(self.id, response.content, response.model, response.usage)
                content = response.content or ""
                self.report(ReportPayload(
                    task_id=self.task.id,
                    summary=content,
                ))
                return

    def delegate(self, description: str, agent_type: str | None = None, role: str | None = None, system_prompt: str | None = None, **metadata: Any) -> Agent:
        child_task = Task(description=description, role=role, system_prompt=system_prompt, parent_id=self.task.id, metadata=metadata)
        child = self._runtime.delegate(child_task, parent=self, agent_type=agent_type)
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
