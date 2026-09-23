# Build & Release

## Build

```bash
python -m build          # requires: pip install build
```

Build backend: `setuptools` (build-system in `pyproject.toml`), packages found under `src/` (`pip install -e .` uses the same layout). Artifacts land in `dist/`. **`build/` at the repo root is stale gitignored debris — do not confuse it with `dist/`; it should be removed.**

## Release Practice

Deliberately lightweight (solo/small project):

1. **Verify green first** — `pytest` passes, `pre-commit run --all-files` clean.
2. **Benchmark gate for prompt/runtime changes** — run `python -m dynamic_harness.benchmark.run --seed-only` (or the relevant cell set) and compare against the prior run; do not release a regression silently.
3. **Version** — bump `version` in `pyproject.toml` (currently `0.1.0`); keep it in sync with the package metadata.
4. **Build** — `python -m build`, sanity-install the wheel into a clean venv (`pip install dist/*.whl`) and smoke-run `dynamic-harness --help` / one benchmark cell.
5. **Document** — reflect any user-visible change in the layer docs (this runbook, `01-product/requirements.md` if the CLI changes, `06-evolution/roadmap.md` if open work moved).
6. **Ship** — tag with the version (`git tag v0.1.0`), push. License: MIT.
