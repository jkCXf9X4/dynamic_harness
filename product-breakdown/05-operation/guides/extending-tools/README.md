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
