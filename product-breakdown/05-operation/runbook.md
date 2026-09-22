# Runbook — dynamic_harness

How authors run, test, benchmark, and release. Created 2026-09-21 (fills review GAP-5 — previously no runbook existed; onboarding had to reverse-engineer this). All commands run from the **repo root** unless noted. Python 3.10+ required.

## Environment & Config

- API key: `export OPENROUTER_API_KEY=sk-...` (or OpenAI key) — read from the environment.
- Config is **layered**: common base `~/.config/dynamic-harness/harness.json` merged field-by-field with local overlay `./harness.json` (or `--config <path>`); deep-merged per section, scalars/lists replaced wholesale. Neither file present → built-in defaults. `harness.json.example` is the template.
- Key safety knobs: `safety.max_iterations`, `max_agent_tokens` (force-fail an agent past a token cap), `timeout_seconds`, `disable_root_timeout`, `max_agents`, `max_depth`, `max_same_target_delegations`. `agent.stream_children` enables streaming fan-out (opt-in, not default).

## Install

```bash
# editable (recommended for development)
pip install -e .
# or with uv
uv sync
```

Entry point: `dynamic-harness` → `dynamic_harness.cli.terminal:main`. Programmatic: `python -m dynamic_harness` or the `Harness` API (see [guides/programmatic-usage.md](guides/programmatic-usage.md)).

## Tests

```bash
pytest            # from repo root; testpaths=["tests"]; asyncio_mode=auto
```

With coverage: `pytest --cov --cov-report=term-missing` (coverage config in `pyproject.toml`, source = `src/dynamic_harness`). The suite currently passes ~466 tests (plugin pilot seam check). AGENTS.md: "Run tests: pytest from repo root."

## Lint / Format (pre-commit)

`.pre-commit-config.yaml` installs:
- **ruff** (`check --fix`) — ruff config in `pyproject.toml`: target-version py310, line-length 500
- **trailing-whitespace**, **end-of-file-fixer** (pre-commit-hooks)

```bash
pip install pre-commit && pre-commit install   # one-time
pre-commit run --all-files                      # or: pre-commit run --files <path>
```

## Build

```bash
python -m build          # requires: pip install build
```

Build backend: `setuptools` (build-system in `pyproject.toml`), packages found under `src/` (`pip install -e .` uses the same layout). Artifacts land in `dist/`. **`build/` at the repo root is stale gitignored debris — do not confuse it with `dist/`; it should be removed.**

## Benchmark CLI (metric-driven prompt benchmark)

```bash
python -m dynamic_harness.benchmark.run          # compare SEED + variants
python -m dynamic_harness.benchmark.run --seed-only
python -m dynamic_harness.benchmark.run --report profile
```

Compares prompts against all tasks from the single canonical task source `src/dynamic_harness/benchmark/tasks.py` (`ALL_TASKS`), ranked by a weighted rubric; metrics written to `.optimize_benchmarks/metrics.json` / `.md`. Variants are read from a JSON file mapping `prompt_id -> system_prompt text` (or null = seed). Needs `OPENROUTER_API_KEY` + `harness.json` pointing at a tool-calling model (default: deepseek flash with a `provider_ignore` list).

Related optimization runners (see [guides/prompt-optimization.md](guides/prompt-optimization.md)):
```bash
python scripts/run_optimize.py      # two-round A/B prompt optimization
python scripts/run_prune_ab.py      # prune/restore A/B test
```

## Comms Benchmark (real-LLM topology comparison)

```bash
python -m dynamic_harness.benchmark.run_comms --smoke                      # sanity pass (1 cell)
python -m dynamic_harness.benchmark.run_comms                              # all cells, both tasks
python -m dynamic_harness.benchmark.run_comms --cells off,shared,topics_parent
python -m dynamic_harness.benchmark.run_comms --tasks interdependent --replicates 2
```

Each cell = one `communication.topology` value; everything else (task, LLM, workspace snapshot) identical. Unclean runs are re-attempted `--retries` times. Results (markdown report + raw `metrics-cells.json`) are written under `../04-verification/communication-structures/`. **Caution:** real-LLM runs cost tokens and time; the 2026-09-18 run took up to ~15 min / ~0.8–5.2M tokens per cell (per FINDINGS.md). Use `--smoke` first; treat small-n results as variance, not truth (n=1 caveat).

## Performance / Scaling Diagnostics

```bash
python -m dynamic_harness.benchmark.profile_scaling          # full grid
python -m dynamic_harness.benchmark.profile_scaling --quick  # fast sanity pass
```

Mock-LLM scaler isolating four axes (checkpoint cost, bytes/token sent per turn, CLI snapshot cost, end-to-end). See [guides/performance-diagnostics.md](guides/performance-diagnostics.md).

## Release Practice

The project's release practice is deliberately lightweight (solo/small project):

1. **Verify green first** — `pytest` passes, `pre-commit run --all-files` clean.
2. **Benchmark gate for prompt/runtime changes** — run `python -m dynamic_harness.benchmark.run --seed-only` (or the relevant cell set) and compare against the prior run; do not release a regression silently.
3. **Version** — bump `version` in `pyproject.toml` (currently `0.1.0`); keep it in sync with the package metadata.
4. **Build** — `python -m build`, sanity-install the wheel into a clean venv (`pip install dist/*.whl`) and smoke-run `dynamic-harness --help` / one benchmark cell.
5. **Document** — reflect any user-visible change in the layer docs (this runbook, `01-product/requirements.md` if the CLI changes, `06-evolution/roadmap.md` if open work moved).
6. **Ship** — tag with the version (`git tag v0.1.0`), push. License: MIT.

Release decisions (bumping, breaking changes) are operation decisions recorded as `OD`-prefixed ADRs per the product-breakdown convention.