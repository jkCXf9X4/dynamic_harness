---
title: "Plan — Switching Seams"
category: investigation / plan
parent: "README.md"
---

# Switching — the two seams

**Seam A — construction.** `HarnessConfig` gains a `communication` section:

```json
{
  "communication": {
    "topology": "topics",
    "registration": "parent",
    "shared_topic": "shared",
    "channels": ["findings", "qa"],
    "digest_mode": "pull",
    "digest_max_items": 5,
    "digest_max_tokens": 400
  }
}
```

`Runtime.__init__` builds the backend from it and wires `runtime.comms`; the tools
read only `runtime.comms`. A cell switch = one config value (`topology`).
Programmatic runs build the same via
`HarnessConfig(communication=CommsConfig(topology="..."))`. `topology: "off"`
(default) yields `comms=None`: the layer is deactivated and `converse` keeps
today's global by-ID behavior. `reset()` rebuilds the backend so a fresh run
starts empty.

**Seam B — the model's environment.** The runtime appends a one-time
`[Communication] topology=<name>` note to `EnvironmentInfo` (`core/runtime.py`)
telling the model which topology is active and how to use the tools. Live
directory lookups go through `channels`/`channel_info`.
