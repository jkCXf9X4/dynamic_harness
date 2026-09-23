# TheAgentCompany, GAIA & BigCodeBench

## TheAgentCompany

- **What**: full-fidelity "software company" multi-agent benchmark — GitLab,
  Plane issue-tracker, ownCloud, RocketChat backends pre-seeded; 175 tasks
  across software engineer, data scientist, PM, HR, finance, admin roles. Agents
  browse the web via a simulated web server, write code, run commands, chat with
  other agents (NPCs).
- **Why it could matter here**: it's fundamentally *multi-agent* — the
  delegation/actor model is the target architecture; the harness's `ask`,
  `converse`, concurrent children could be exercised.
- **Why it doesn't fit well now**:
  - needs 6 Docker services + 30 GB free space + network setup;
  - primary grading is LLM-based (an LLM judge reads the trajectory) — this
    clashes with the project's "every `BenchmarkTask` carries a *failable
    ground-truth verifier*" invariant ([evaluation-and-qa](../../../01-product/use-cases/evaluation-and-qa.md)).
  - adds all that infra for signal we can get cheaper from mini-fixtures.
- **Verdict**: skip as a *harness* task; if multi-agent-company signal is ever
  wanted, run `the-agent-company` externally and translate its deterministic
  subtasks into `BenchmarkTask`s.

## GAIA (HuggingFace `gaia-benchmark`)

- **What**: open-ended assistant benchmarks — questions like "Convert this
  wedding invitation to a CSV uploadable to Google Calendar, including the link",
  which require mixing web retrieval, tool use, and computation on real-world
  files. Grading is by exact-match string/human.
- **Why relevant here**: it's the "multi-source synthesis" case — exactly what the
  harness's `synthesis` task is a 1-file micro-version of; the
  parent-delegate-children-fuse structure is basically what GAIA rewards.
  `webfetch` + `bash` are already in-toolbox.
- **Cons**: needs network + a re-judge adapter (their exact-match strings are
  awkward against free-form agent output); pulls real-world file data.
- **Verdict**: the theoretical "best case" for this runtime's delegation story,
  but the automated verification is weak without building a judge.

## BigCodeBench

~1,140 independent function-generation tasks over 100+ real packages. **Pro**:
embarrassingly parallel — delegate per-function to parallel children. **Con**:
per-package dependencies mean the exact same env/Docker problem as SWE-bench;
and in this repo the `parallel` `ParallelSubtasksTask` probes the same property
much cheaper. **Verdict**: useful as an external sanity reference; overkill for
prompt optimization.
