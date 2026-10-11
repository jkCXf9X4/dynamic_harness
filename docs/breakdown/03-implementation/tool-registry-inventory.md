---
id: INFO-199
type: info
title: Tool Registry Inventory
summary: The 34 registered tools and how they register
date: 2026-10-10
status: current
---

# Tool Registry Inventory

The runtime's tool surface. Source: `src/dynamic_harness/core/tools/`.

## Registry
- `ToolRegistry` (`registry.py`) maps tool name to (ToolDef, function).
- `ToolDef` carries `name`, `description`, `input_schema` (JSON schema).
- `register_default_tools()` (`registration.py`) registers all 34 tools.
- The registry is public: a host can register further tools.

## The 34 tools
- Filesystem: `read`, `write`, `glob`, `grep`, `edit`.
- Process: `bash`.
- Network: `webfetch`.
- Agents: `delegate`, `report`, `escalate`, `fail`, `ask`, `converse`, `kill`, `status`, `resume`, `read_artifact`, `usage`.
- Context: `compress`, `prune`, `restore`.
- Planning: `plan`, `checkpoint`.
- Artifacts: `archive`.
- Result store: `result_read`, `result_bash`.
- Skills: `skill_load`.
- Comms: `post`, `channel_read`, `channels`, `channel_info`, `subscribe`, `unsubscribe`, `message`.

## Notes
- `delegate`'s def is built by `make_delegate_def(model_profiles)`; the `model_profile` parameter appears only when profiles are configured.
- The interactive CLI overrides `ask` with a terminal prompt (`cli/terminal.py`).
- Comms tools are identical across topologies; `communication.topology` is a construction switch.

## Owns
- The tool inventory and registration mechanics.

## Excludes
- Per-tool behavior: each tool's docstring in `core/tools/`.
- Writing custom tools: `05-operation/` guides.
