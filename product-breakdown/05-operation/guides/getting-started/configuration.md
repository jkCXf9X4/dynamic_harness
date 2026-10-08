---
id: INFO-109
type: info
title: Configuration
summary: Settings (model, base URL, provider blacklist, safety limits) live in a dynamic_harness.json. Config is layered so one common base can be shared across projects and overr…
date: 2026-09-23
status: current
---

# Configuration

Settings (model, base URL, provider blacklist, safety limits) live in a
`dynamic_harness.json`. Config is **layered** so one common base can be shared
across projects and overridden per-project:

- `~/.config/dynamic_harness/dynamic_harness.json` — **common base**, shared across every project on this machine (`$XDG_CONFIG_HOME` is honored when set).
- `./dynamic_harness.json` (project root, or `--config path`) — **local overlay**, overrides the base per-key.

The two are deep-merged: each section (`llm`, `safety`, `self_heal`, `agent`)
merges field-by-field, so a local config can override a single setting while
keeping the rest of the common base. Scalars and lists are replaced wholesale.
If no file exists at a level, it is skipped; with neither file, built-in defaults
are used.

## Common config (recommended)

Put shared settings in the common base so every project picks them up:

```bash
mkdir -p ~/.config/dynamic_harness
cat > ~/.config/dynamic_harness/dynamic_harness.json <<'EOF'
{
  "root_model": "openrouter/deepseek/deepseek-v4-flash-0731",
  "llm": {
    "verify_ssl": false
  },
  "providers": {
    "openrouter": {
      "base_url": "https://openrouter.ai/api/v1"
    }
  }
}
EOF
```

See `INFO-113` for per-project overrides and
`max_agent_tokens`.
