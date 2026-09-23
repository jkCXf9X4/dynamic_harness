# Project-Local Overrides

Copy the template into the project and edit only the keys you need — they
override the common base:

```bash
cp harness.json.example harness.json
```

```json
{
  "llm": {
    "model": "deepseek/deepseek-v4-flash-0731",
    "base_url": "https://openrouter.ai/api/v1",
    "provider_ignore": ["gmicloud", "SiliconFlow", "Baidu"],
    "provider_allow_fallbacks": true
  },
  "safety": {
    "max_iterations": 500,
    "repeated_call_limit": 5,
    "max_agent_tokens": 50000
  }
}
```

`max_agent_tokens` (optional) force-fails an agent once its total cumulative
usage (prompt + completion) passes the cap. It is surfaced to agents as a static
budget line, and the `usage` tool lets any agent read its own live message/token
counters — so a tight per-agent goal (e.g. **under 50,000 tokens**) can be
communicated both up-front and as the agent runs, without adding a per-turn
observation message.

Every setting — safety, self-heal, agent, and more — is documented in the
[Configuration Reference](../../../../docs/api/config.md), with defaults and the
`0`/`null` "cap disabled" convention.
