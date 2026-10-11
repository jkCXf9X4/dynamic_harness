---
title: "Getting Started"
summary: Quick start for Dynamic Harness: install, environment setup, first task, and output.
---

# Getting Started (Index)

Quick start for running Dynamic Harness end to end. Read in order; each leaf is
one step.

Next: [agent methodology](../../../02-architecture/methodology/README.md),

[programmatic usage](../programmatic-usage/README.md),

[custom agents](../custom-agents/README.md),

[custom tools](../extending-tools/README.md).

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-109** [Configuration](configuration.md) — Settings (model, base URL, provider blacklist, safety limits) live in dynamic_harness.json, layered so a common base is shared across projects and overridden per-project.
- **INFO-110** [Your First Task](first-run.md) — Run a first task in the interactive terminal, single-shot mode, or no-LLM mode.
- **INFO-111** [Install & Environment](install-and-setup.md) — Install Dynamic Harness with uv or pip and set the API key in the environment.
- **INFO-112** [Understanding the Output](output.md) — The CLI shows a compact outcome per agent and persists the full run overview to the run directory.
- **INFO-113** [Project-Local Overrides](project-overrides.md) — Copy the template into the project and edit only the keys you need — they override the common base
- **INFO-114** [Terminal Commands](terminal-commands.md) — Slash commands available in the interactive terminal
- **INFO-115** [Common Issues](troubleshooting.md) — Fix common issues: missing API key, missing config file, runaway agents, high token costs.
<!-- pb:index:end -->
