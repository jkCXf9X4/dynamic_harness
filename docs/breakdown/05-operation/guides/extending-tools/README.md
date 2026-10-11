---
title: "Extending Tools"
summary: How to register custom tools in the ToolRegistry: definition schemas, implementation signatures, accessing the calling agent, and integration patterns.
---

# Extending Tools (Index)

Custom tools extend what agents can do. Tools are registered with the
`ToolRegistry` and become available to all agents the next time they enter the
tool-calling loop.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-102** [Best Practices](best-practices.md) — A well-shaped tool is cheap for the LLM to select, call, and recover from. Keep the schema and description as tight as the implementation
- **INFO-103** [ToolContext & Terminal Tools](context-and-terminal.md) — The `ctx` parameter is a narrow public façade over runtime services; terminal tools stop the agent loop via ctx.report, ctx.fail, or ctx.escalate.
- **INFO-104** [Example: Database Tool](example-database.md) — A complete read-only SQL query tool: ToolDef, async handler, and registration.
- **INFO-105** [Example: Notification Tool](example-notification.md) — A complete notification tool that writes to a JSONL log: ToolDef, async handler, and registration.
- **INFO-106** [Minimal Custom Tool](minimal-tool.md) — A minimal working tool, the required async function signature, and the key rules for tool functions.
- **INFO-107** [Registration & Unregistration](registration.md) — Tools register at any time but only become visible when an agent next enters the tool-calling loop; unregistration affects all agents.
- **INFO-108** [Tool Definition Schema](tool-def-schema.md) — ToolDef uses standard JSON Schema for input_schema, with a fixed set of supported types.
<!-- pb:index:end -->
