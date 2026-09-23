# Layer 1 — Resume-once (the escape hatch)

Primitive: `Agent.continue_with_input(msg)` / `Runtime.run(msg, root_agent=...)`
(runtime.py:115-137, agent.py:163-171). Appends a user message and re-runs
`_run_loop()` on the **same** agent — `_run_loop` has no guard against a prior
terminal status, so it resumes cleanly.

Trigger: a single agent terminated *without* a normal report, or terminated with
a report but produced no deliverable (missing output file / empty artifact),
where its context is small and shows no repeated-call signature. It runs
**exactly once**. A second miss flips the diagnosis to rot.

The deliverable check is implemented in `Runtime._has_deliverable()`: if
`Runtime.run(..., expected_outputs=[...])` declared files the task must write,
they must all exist on disk; otherwise a report must declare `files_written` /
`artifact_ids`. A prose-only report (no files, no artifacts) is not a
deliverable and triggers Layer 1.

Example from practice: the optimizer generation agent answered in prose instead
of writing its JSON artifact — clean context, one turn, simply needed the nudge
"write the file now." Layer 1 fixes this for ~one extra LLM turn.
