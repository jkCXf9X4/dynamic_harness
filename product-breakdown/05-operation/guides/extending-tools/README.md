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

- [minimal-tool.md](minimal-tool.md) — a working custom tool and the function signature rules.
- [tool-def-schema.md](tool-def-schema.md) — `ToolDef` JSON Schema and type mapping.
- [context-and-terminal.md](context-and-terminal.md) — `ToolContext` services and terminal tools.
- [example-database.md](example-database.md) — read-only SQL query tool.
- [example-notification.md](example-notification.md) — task-completion notification tool.
- [registration.md](registration.md) — registration timing, per-agent tools, unregistering.
- [best-practices.md](best-practices.md) — naming, descriptions, validation.
