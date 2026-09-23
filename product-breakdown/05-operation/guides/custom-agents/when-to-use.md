# When to Use Custom Agents

- **Logging/metrics** — override `run()` with pre/post hooks.
- **Task preprocessing** — override `run()`, modify the task, call `super().run()`.
- **Domain specialization** — custom system prompt.
- **Different safety thresholds** — override `safety_max_iterations`.
- **Retry logic** — custom `run()` with a loop around `super().run()`.

Custom agent classes let you encode reusable behavior patterns without modifying
the core `Agent` implementation.
