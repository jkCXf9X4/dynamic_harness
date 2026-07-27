"""Run the test_optimize.prompt flow — small scale."""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.dynamic_harness.config import load_harness_config, merge_api_key
from src.dynamic_harness.core.runner import AgentRunner
from src.dynamic_harness.core.runtime import Runtime
from src.dynamic_harness.core.task import ActivityEvent, ActivityEventType, ReportPayload
from src.dynamic_harness.llm.openai_provider import OpenAIProvider

load_dotenv()


def on_report(agent_id: str, payload: ReportPayload) -> None:
    tag = agent_id[:8]
    print(f"[report][{tag}] {payload.summary[:200]}", flush=True)
    if payload.artifact_ids:
        for aid in payload.artifact_ids:
            print(f"[artifact][{tag}] {aid}", flush=True)


def on_failure(agent_id: str, fail) -> None:
    tag = agent_id[:8]
    print(f"[FAIL][{tag}] {fail.error[:200]}", flush=True)


def on_activity(event: ActivityEvent) -> None:
    et = event.event_type
    d = event.data
    aid = event.agent_id[:8]
    if et == ActivityEventType.DELEGATION_START:
        desc = d.get("description", "")[:80]
        print(f"  [{aid}] → delegate: {desc}", flush=True)
    elif et == ActivityEventType.DELEGATION_END:
        child = d.get("child_id", "")[:8]
        status = d.get("status", "?")
        print(f"  [{aid}]   {child} → {status}", flush=True)
    elif et == ActivityEventType.TOOL_CALL_START:
        name = d.get("tool_name", "?")
        args = d.get("arguments", {})
        if name == "read":
            print(f"  [{aid}] read({args.get('path','')})", flush=True)
        elif name == "write":
            print(f"  [{aid}] write({args.get('path','')})", flush=True)
        elif name in ("bash",):
            cmd = str(args.get("command", ""))[:80]
            print(f"  [{aid}] bash({cmd})", flush=True)
    elif et == ActivityEventType.ITERATION:
        print(f"  [{aid}] turn {d.get('turn','?')}, msgs {d.get('messages','?')}", flush=True)
    elif et == ActivityEventType.SAFETY_WARNING:
        print(f"  [{aid}] ⚠ SAFETY: {d.get('warning_type','?')}", flush=True)


async def main() -> None:
    config = load_harness_config()
    api_key = merge_api_key()
    if not api_key:
        print("Error: no API key found. Set OPENROUTER_API_KEY in .env")
        sys.exit(1)

    rt = Runtime(
        artifact_root=Path(".dynamic-harness/artifacts"),
        repo_root=Path(".dynamic-harness/repo"),
        trace_root=Path(".dynamic-harness/traces"),
        config=config,
    )
    llm = OpenAIProvider(
        model=config.llm.model,
        base_url=config.llm.base_url,
        api_key=api_key,
        verify_ssl=False,
        provider_ignore=config.llm.provider_ignore or None,
        provider_allow_fallbacks=config.llm.provider_allow_fallbacks,
    )
    rt.set_llm(llm)
    rt.on_report(on_report)
    rt.on_failure(on_failure)
    rt.on_activity(on_activity)

    prompt = Path("prompts/test_optimize.prompt").read_text()
    runner = AgentRunner(rt)

    print(f"LLM: {config.llm.model}", flush=True)
    print(f"Base: {config.llm.base_url}", flush=True)
    print(f"\nRunning test_optimize.prompt...\n", flush=True)

    await runner.run(prompt)

    print(f"\n=== RESULTS ===", flush=True)
    root = None
    for aid, agent in rt._agents.items():
        if agent.parent is None:
            root = agent
            break
    if root:
        if root._last_report:
            print(f"Report: {root._last_report.summary[:500]}", flush=True)
            print(f"Artifacts: {root._last_report.artifact_ids}", flush=True)
        if root._last_failure:
            print(f"FAILURE: {root._last_failure.error[:500]}", flush=True)

    print(f"\nAgents: {rt.agent_count()}", flush=True)
    print(f"Tokens: {rt.total_usage()['total_tokens']}", flush=True)
    print(f"Commits: {rt.repository.count()}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())