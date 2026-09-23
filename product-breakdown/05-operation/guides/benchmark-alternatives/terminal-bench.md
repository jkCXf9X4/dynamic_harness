# Terminal-Bench

- **What**: benchmark of terminal-computing tasks ("use the terminal to do X"),
  shipped as Docker images with a task dir (`/instruction`, `/workspace`, a
  `scripts/test.sh` and gold solution to verify). The agent interacts through a
  shell; success = the task's own `test.sh` passes against the achieved state.
  Used/initiated by terminal-focused agent tooling (e.g. Meta's CLI/agent
  efforts); MIT licensed, ~100+ tasks.
- **Fits this harness**: the `bash` tool is exactly the interaction the probe
  wants; verification is a file/dir state check, i.e. the same
  `verify(output_dir, scan_root)` contract.
- **Gaps**: each task is a container image (Docker required); some tasks do
  web/GUI things the harness's tools don't model; install + environment-heavy.
- **Verdict**: the closest external benchmark to this runtime's *operational*
  style (bash-first, artifact-on-disk), and worth building the mini version of:
  a checked-in corpus of ~5–10 single-fix tasks (`stub repo` + `test_issue.py`)
  evaluated by the identical `BenchmarkTask.verify()`.
