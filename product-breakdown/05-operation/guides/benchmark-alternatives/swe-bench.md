# SWE-bench (Full / Verified / Lite)

- **What:** the canonical agent benchmark. Each instance = `(repo, base_commit,
  problem_statement, gold_patch, FAIL_TO_PASS, PASS_TO_PASS)`. Given the repo at
  `base_commit` + the issue text, the agent produces a patch; the harness applies
  it to a clean checkout and runs `pytest -k "F2P or P2P"` — resolved iff all
  FAIL_TO_PASS pass and no PASS_TO_PASS regress. MIT, maintained by
  Princeton-NLP, 2.3k+ instances (500 in Verified).
- **Fits the harness structurally**: the F2P/P2P pytest gate *is*
  `verify(output_dir, scan_root)`, and a fresh `Runtime` + staged root is the
  "apply to a clean env" protocol the runner already does per run.
- **Why it's gold-standard**: real repos, real deps, real regressions — the
  strongest signal that an agent can actually change software.
- **Ease of use (gap)**:
  - Staging needs `git clone`, checkout at `base_commit`, and `pip install` of
    the downstream package (best done as per-instance Docker images; the current
    SWE-bench CLI is container-driven and expects ~120 GB disk / 16 GB RAM).
  - Deliverable is a **patch applied to the tree**, not a file in
    `.optimize_benchmarks/`; the verifier must reset + `git apply` + run pytest.
  - Runs are hours (pip installs + pytest per instance) — a batch pipeline, not
    the per-run feedback the prompt optimizer wants.
- **Recommendation**: keep as an **opt-in, batch** pipeline
  (`scripts/run_swebench.py`) behind a `BaseRepoTask.verify()` that delegates to
  `swebench` when installed. Add **one or two mini-SWE-bench fixture repos**
  (checked-in, deps-free, one failing test) to `ALL_TASKS` to get the
  repo-bugfix shape without Docker (this is the "SWE-bench-mini" plan).
