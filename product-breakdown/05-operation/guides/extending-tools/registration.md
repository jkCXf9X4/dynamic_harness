# Registration & Unregistration

Tools can be registered at any time, but they only become visible to agents when
the agent next enters `_run_loop()` (i.e., the next tool-calling turn). For
agents already in a loop, new tools won't appear until they complete and restart.

## At Runtime Startup

```python
runtime = Runtime(...)
runtime.tool_registry.register(my_tool_def, my_tool_fn)
# All subsequent agents will have the tool
```

## Conditionally

```python
if feature_enabled:
    runtime.tool_registry.register(feature_tool_def, feature_tool_fn)
```

## Per-Agent

Register before delegating and deregister after. But the ToolRegistry is shared
— deregistering affects all agents. For per-agent tools, consider overriding the
agent's tool list via a custom Agent subclass.

## Unregistering Tools

```python
runtime.tool_registry.unregister("my_tool")

# Verify it's gone
assert "my_tool" not in runtime.tool_registry.list_tools()
```

The registry is shared across agents, so unregistering affects all agents. For a
fully custom set of defaults, build your own registry:

```python
from dynamic_harness.core.tools import ToolRegistry, register_default_tools

my_registry = ToolRegistry()
register_default_tools(my_registry)
my_registry.register(my_tool_def, my_tool_fn)
```
