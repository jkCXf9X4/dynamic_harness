# Configuration

Settings (model, base URL, provider blacklist, safety limits) live in a
`harness.json`. Config is **layered** so one common base can be shared across
projects and overridden per-project:

- `~/.config/dynamic-harness/harness.json` — **common base**, shared across every project on this machine.
- `./harness.json` (project root, or `--config path`) — **local overlay**, overrides the base per-key.

The two are deep-merged: each section (`llm`, `safety`, `self_heal`, `agent`)
merges field-by-field, so a local config can override a single setting while
keeping the rest of the common base. Scalars and lists are replaced wholesale.
If no file exists at a level, it is skipped; with neither file, built-in defaults
are used.

## Common config (recommended)

Put shared settings in the common base so every project picks them up:

```bash
mkdir -p ~/.config/dynamic-harness
cat > ~/.config/dynamic-harness/harness.json <<'EOF'
{
  "llm": {
    "model": "deepseek/deepseek-v4-flash-0731",
    "base_url": "https://openrouter.ai/api/v1",
    "verify_ssl": false
  }
}
EOF
```

See [project-overrides.md](project-overrides.md) for per-project overrides and
`max_agent_tokens`.
