# Core Philosophy

Maximize output quality while minimizing cost through disciplined task
decomposition, strict context encapsulation, and a mandatory
**analyze → implement → verify loop**. An agent's job is to break work into
system elements and delegate. Deep context = degraded focus = wasted cost.

> **Golden rule:** If a sub-task requires 2+ tool calls, delegate to a
> sub-agent. Fresh context outperforms accumulated context.

## 15288 Lifecycle Mapping

Every agent invocation follows a mini-systems-engineering lifecycle:

| Phase | 15288 Process | Action |
|---|---|---|
| **ANALYZE** | Business/Mission Analysis | Define problem space, identify required outputs |
| **DECOMPOSE** | Requirements Definition → Architecture | Derive requirements, create system breakdown structure (sub-agent units), assign roles |
| **DELEGATE** | Implementation | Allocate requirements to system elements (sub-agents), execute in parallel |
| **VERIFY** | Integration + Verification | Confirm each element's output satisfies its allocated requirements |
| **SYNTHESIZE** | Validation | Confirm integrated result satisfies original stakeholder need |
| **TERMINATE** | Transition + Disposal | Deliver verified artifacts; agent terminates |
