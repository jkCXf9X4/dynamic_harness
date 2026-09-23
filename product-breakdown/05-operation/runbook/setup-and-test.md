# Setup & Test

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

Entry point: `dynamic-harness` → `dynamic_harness.cli.terminal:main`. Programmatic: `python -m dynamic_harness` or the `Harness` API (see [guides/programmatic-usage](../guides/programmatic-usage/README.md)).

## Tests

```bash
pytest            # from repo root; testpaths=["tests"]; asyncio_mode=auto
```

With coverage: `pytest --cov --cov-report=term-missing` (coverage config in `pyproject.toml`, source = `src/dynamic_harness`). The suite currently passes ~466 tests (plugin pilot seam check). AGENTS.md: "Run tests: pytest from repo root."

## Definition-State Check (node sizes)

```bash
python3 product-breakdown/tools/check_node_size.py --strict   # AD-009 node budget
```

Every markdown file under `product-breakdown/` is a node: index `README.md` ≤75 lines, leaf ≤75 lines (min ~10). Violations are resolved by trim → link → split. There are no exemptions. Run this after editing any `product-breakdown/` node.

## Lint / Format (pre-commit)

`.pre-commit-config.yaml` installs:
- **ruff** (`check --fix`) — ruff config in `pyproject.toml`: target-version py310, line-length 500
- **trailing-whitespace**, **end-of-file-fixer** (pre-commit-hooks)

```bash
pip install pre-commit && pre-commit install   # one-time
pre-commit run --all-files                      # or: pre-commit run --files <path>
```
