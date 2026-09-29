---
title: "Extending Tools"
category: guide
difficulty: advanced
summary: >
  How to register custom tools in the ToolRegistry. Covers tool definition
  schemas, implementation signatures, accessing the calling agent, and
  integration patterns.
related:
  - ../../../../docs/api/tools.md
  - ../../../../docs/api/runtime.md
  - ../programmatic-usage/README.md
---

# Extending Tools (Index)

Custom tools extend what agents can do. Tools are registered with the
`ToolRegistry` and become available to all agents the next time they enter the
tool-calling loop.

## Contents

<!-- pb:index:start -->
- **INFO-102** [Best Practices](best-practices.md) — A well-shaped tool is cheap for the LLM to select, call, and recover from. Keep the schema and description as tight as the implementation
- **INFO-103** [ToolContext & Terminal Tools](context-and-terminal.md) — The parameter gives access to everything a tool is allowed to see — it is a narrow public façade, so tools cannot reach into agent/runtime private sta…
- **INFO-104** [Example: Database Tool](example-database.md) — `python import sqlite3
- **INFO-105** [Example: Notification Tool](example-notification.md) — `python import json
- **INFO-106** [Minimal Custom Tool](minimal-tool.md) — `python from dynamic_harness.core.tools import ToolDef, ToolRegistry
- **INFO-107** [Registration & Unregistration](registration.md) — Tools can be registered at any time, but they only become visible to agents when the agent next enters (i.e., the next tool-calling turn). For agents…
- **INFO-108** [Tool Definition Schema](tool-def-schema.md) — The uses standard JSON Schema
<!-- pb:index:end -->
