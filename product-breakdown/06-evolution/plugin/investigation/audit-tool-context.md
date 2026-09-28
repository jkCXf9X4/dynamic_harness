---
title: "Plugin Direction — Tool-Call Contract Breadth Audit"
category: investigation
parent: "README.md"
summary: >
  Member-by-member consumers of ToolContext, the trimming rule, and the
  narrowing proposals.
---

# 1. Tool call contract (`ToolDef` / `ToolResult` / `ToolContext` + `ToolRegistry`)

The audit covers each of the ~7 interfaces: who consumes it, and how wide its
surface is. "Breadth" = members a consumer can see; the trimming rule is
*remove members no consumer uses* and *keep members used by ≥1 consumer*, even
if that consumer is a single tool.

`ToolContext` member → consumers (from `rg "ctx\."` across `core/tools/`):

| ToolContext member | Consumed by |
|--------------------|-------------|
| `artifact_store` | agents, artifacts |
| `generated_root` | filesystem, process, result_bash |
| `result_store` | registry, result_read, result_bash |
| `agent_id` | artifacts, context |
| `task_id` | agents, artifacts |
| `workspace_lock` | filesystem |
| `gitignore_filter` | filesystem |
| `repo_lock` | process |
| `llm` (→ `ctx.llm`) | context |
| `messages` | context |
| `usage_summary` | agents |
| `run_delegate_tool` | agents |
| `report` / `escalate` / `fail` | agents |
| `get_other_agent` | agents |
| `kill` / `resume_child` / `status` / `continue_with_input` | agents |
| `latest_assistant_message` | agents |
| `set_plan` / `checkpoint` | planning |
| `compress` / `prune` / `restore` | context |
| `emit_activity` | context |
| `record_archived_artifact` | artifacts |
| `message_count` | **NO tool** — dead surface (kept for tests/API symmetry); candidate for narrowing |

Observations:
- The `status`/`kill`/`resume_child`/`converse` cluster lives on the wide
  façade but **only the `agents` tool file consumes it** — a single consumer.
  Per the "keep members used ≥1" rule it stays; per narrowing it is the most
  self-contained slice (agent-authority actions), so if the façade is ever
  split by concern this cluster is the natural first facet.
- `message_count` is dead from the tools' perspective (the `usage` tool reads
  it through `usage_summary`, not directly) — remove or keep only for the
  public API symmetry.
