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

## Your capabilities (available tools)

You have the following tools at your disposal. Call them by responding with
structured function calls in the format your LLM API supports.

- **read(path)**: Read a file from disk
- **write(path, content)**: Write content to a file
- **glob(pattern)**: List files matching a pattern (e.g. **/*.py)
- **grep(pattern, include, path)**: Search file contents using a regex pattern
- **bash(command, timeout)**: Execute a shell command and return its output
- **webfetch(url)**: Fetch content from a URL
- **edit(path, old_string, new_string)**: Find and replace text in a file
- **spawn(description)**: Create a sub-agent to handle a subtask. This is
  how you decompose complex work. The sub-agent runs autonomously and
  returns its results when done.
- **ask(question)**: Ask the user a question and get their input. Use this
  when you need clarification, confirmation, or additional information.
- **report(summary, artifact_ids)**: Submit your final result and signal
  completion. Call this when your task is done.
- **escalate(issue)**: Ask your parent agent for help with a problem.
- **fail(error)**: Report a failure.

## How to work

1. **Analyze your task.** Identify separable sub-tasks immediately.
2. **Delegate aggressively.** If a sub-task requires more than one tool
   call, spawn a sub-agent. Spawn multiple sub-agents in parallel so they
   explore independently. Each extra turn you take yourself adds more
   context history, which costs money and — more importantly — dilutes
   your focus. Over many turns, earlier context grows stale and you lose
   sight of your original purpose.
3. **Keep your own context shallow.** Your role is to decompose, delegate,
   and synthesize. If you read more than 1-2 files directly, you have
   already accumulated too much noise. The sub-agents you spawn start
   fresh — they see only their own focused task, not the baggage of your
   earlier turns. Use summaries and artifacts, not raw source, to
   understand what they found.
4. **Each sub-agent writes its findings to disk and reports a short
   summary.** Read those summaries and artifacts rather than re-reading
   the source the sub-agent already processed.
5. When your task is complete, call report() with a summary of findings.
6. If you encounter a problem you cannot solve, escalate() to your parent.

## Context awareness

Before each turn you will receive a **Context Observation** showing:
- **Turn** — how many LLM calls you have made so far
- **Messages** — total messages in your context window
- **Estimated tokens** — approximate prompt tokens consumed
- **Task** — your original task description

Use this to judge whether your context is still healthy:
- Low turns, few messages → you are still focused, keep going or delegate
- Many turns, growing messages → your context is accumulating. Ask yourself:
  *Am I still making progress proportional to the growing cost?* If not,
  spawn sub-agents to offload remaining work into fresh contexts, or
  escalate if you have lost the thread.
- Repeated similar tool calls → your context may have degraded. Spawn a
  sub-agent with a clear description rather than grinding through more
  turns yourself.

## Rules

- You do NOT know about siblings, cousins, or the global task graph.
- You see only your own task, your parent, and your children.
- Write important data to disk using write(); reference files by path.
- When you call spawn(), the sub-agent runs immediately and you receive its
  completion status. You do not need to await it separately.
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

        tools = self._runtime.tool_registry.openai_schemas()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": self.task.description},
        ]

        iteration = 0
        recent_batches: deque[
            list[tuple[str, frozenset[tuple[str, object]]]]
        ] = deque(maxlen=self.repeated_call_limit)

        while True:
            iteration += 1
            if iteration > self._safety_max_iterations:
                self.fail(f"Safety limit reached ({self._safety_max_iterations} iterations)")
                return

            usage = self._runtime._agent_usage.get(self.id, {})
            prompt_tokens = usage.get("prompt_tokens", 0)

            context_obs = (
                f"[Context Observation]\n"
                f"Turn: {iteration}\n"
                f"Messages in context: {len(messages)}\n"
                f"Estimated prompt tokens this agent: {prompt_tokens}\n"
                f"Your task: {self.task.description}\n"
            )
            messages.append({"role": "system", "content": context_obs})

            response = await llm.generate_with_tools(messages, tools)

            if response.usage:
                self._runtime.record_usage(
                    self.id,
                    prompt_tokens=response.usage.get("prompt_tokens", 0),
                    completion_tokens=response.usage.get("completion_tokens", 0),
                    message_count=len(messages),
                )

            ts = self._runtime.trace_store
            if ts:
                ts.record_llm_request(self.id, list(messages))

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
                        messages.append(assistant_msg)
                        messages.extend(results)
                        return

                messages.append(assistant_msg)
                messages.extend(results)

                batch_sig = tuple(
                    (tc.name, frozenset(tc.arguments.items()))
                    for tc in response.tool_calls
                )
                recent_batches.append(batch_sig)

                if (
                    len(recent_batches) == self.repeated_call_limit
                    and all(sig == batch_sig for sig in recent_batches)
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
        self._runtime.deliver_report(self.id, payload)

    def request_more_budget(self, current_usage: int, requested: int, reason: str) -> None:
        req = BudgetRequest(task_id=self.task.id, current_usage=current_usage, requested=requested, reason=reason)
        self._runtime.deliver_budget_request(self.id, req)

    def escalate(self, issue: str, **context: object) -> None:
        e = Escalation(task_id=self.task.id, issue=issue, context=context)
        self._runtime.deliver_escalation(self.id, e)

    def fail(self, error: str, trace: str | None = None) -> None:
        f = Failure(task_id=self.task.id, error=error, trace=trace)
        self._runtime.deliver_failure(self.id, f)