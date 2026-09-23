# Feeding the Optimized Prompt Back

The application loads its default system prompt **at import time**:

```python
# src/dynamic_harness/core/agent.py:26
AGENT_SYSTEM_PROMPT = (Path(__file__).parent / "agent_system_prompt.txt").read_text()
```

Any agent without an explicit `system_prompt` override uses this constant
(`agent.py:101`). Three ways to apply the winning prompt:

## Option A (recommended) — replace the seed file

```bash
cp .optimize_benchmarks/best_prompt.txt \
   src/dynamic_harness/core/agent_system_prompt.txt
```

The value is read once at module load, so the running process must be restarted
for the change to take effect. Back up the original:

```bash
cp src/dynamic_harness/core/agent_system_prompt.txt{,.bak}
```

## Option B — per-agent override (no file change)

```python
agent = Agent(agent_id, task, runtime, system_prompt=optimized_text)
```

For sub-agents created via the `delegate` tool, pass it via the tool's
`system_prompt` parameter. This keeps the global default untouched while testing
a candidate on specific agents only.

## Option C — programmatic task-level override

Set `Task.system_prompt = optimized_text` before delegating; the agent prefers
`task.system_prompt` over the module constant (`agent.py:48`).

## Important Caveat

`best_prompt.txt` begins with a `### VARIANT ...` header line (the generator
labels variants). If writing it verbatim into `agent_system_prompt.txt`, strip
that first label line so only the prompt body is used:

```bash
tail -n +2 .optimize_benchmarks/best_prompt.txt > src/dynamic_harness/core/agent_system_prompt.txt
```
