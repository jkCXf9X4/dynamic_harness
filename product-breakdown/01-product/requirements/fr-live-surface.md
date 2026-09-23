---
title: "FR-3 — Live interactive surface"
category: requirement
summary: >
  The prompt line doubles as a live progress counter; input is always available
  during a run (queued when busy, immediate during a child-wait); the root
  agent's text replies stream above the prompt.
related:
  - direction.md
---

# FR-3. Live interactive surface

## FR-3. Visible "progress is happening"

While a run is active the terminal shows a lightweight live token counter whose
(optional) label reflects the latest activity (tool calls, delegations,
compression, self-heal). The counter is rendered as the **prompt line itself**
of the otherwise-prompt-only input (via `prompt_toolkit`), so it cannot corrupt
terminal output; the agent `ask` interaction swaps that prompt to
`[ask] <question>` and pauses the counter while prompting.

## FR-3.5. Always-available input during a run

- **FR-3.5.1** The operator can type into the same `>>>` line at any time during
  a run (commands or messages to the agent).
- **FR-3.5.2** A message typed while the agent is **busy** (mid-turn) is
  **queued** and lands as a fresh user turn when the agent finishes its current
  work.
- **FR-3.5.3** A message typed while the top agent is **waiting on its children**
  is **applied immediately** — it interrupts the wait so the agent reacts now.
  Interrupted children are not discarded: they are re-gathered and their results
  fold into the parent's context once they settle (still-running children
  continue in the background).
- **FR-3.5.4** Slash commands such as `/tree`, `/agents`, `/provenance` are
  available **during** the run to inspect live status, not only when idle.
  Mutating commands (`/resume`, `/reset`) are refused while a run is active.
- **FR-3.5.5** Non-TTY sessions (batch/pipelines) do not render the input line
  or token counter at all — output stays clean and machine-parseable.

## FR-3.6. Streaming the top agent's replies

- **FR-3.6.1** Each LLM call that produces text emits an `assistant_reply`
  activity event carrying that content (empty/tool-only turns stay silent).
- **FR-3.6.2** In interactive sessions the **root** agent's replies are printed
  above the live prompt as they happen (a printed line, not a dashboard — the
  input line itself is untouched), so the operator sees the top agent answer a
  mid-run question instead of talking to a silent terminal.
- **FR-3.6.3** Replies from delegated children are never printed; the operator
  only hears from the agent they talk to.
