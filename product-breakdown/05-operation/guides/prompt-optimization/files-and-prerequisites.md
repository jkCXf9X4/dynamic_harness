# Files & Prerequisites

## Files Involved

| Role | Path |
|---|---|
| Single task source | `src/dynamic_harness/benchmark/tasks.py` (`ALL_TASKS`) |
| Optimization runner | `scripts/run_optimize.py` |
| Prune/restore A/B test | `scripts/run_prune_ab.py` |
| Standalone metric CLI | `src/dynamic_harness/benchmark/run.py` |
| Variant-generation instructions | `prompts/generate_variants.prompt` |
| Refinement instructions | `prompts/refine_variants.prompt` |
| Baseline prompt (the thing being optimized) | `src/dynamic_harness/core/agent_system_prompt.txt` |
| Model/provider config | `harness.json` |
| Runtime output (artifacts/commits/traces) | `.dynamic-harness/` |
| Optimization output files | `.optimize_benchmarks/` |
| Prune/restore A/B output files | `.optimize_ab/` |

## Prerequisites

- Python 3.10+ with the package installed into the venv:
  ```bash
  source venv/bin/activate
  pip install -e .
  ```
- An OpenRouter API key set in the environment / `~/.bashrc`:
  ```bash
  export OPENROUTER_API_KEY=sk-...
  ```
- `harness.json` pointing at a model that can handle tool calls. The default
  uses DeepSeek flash and keeps the `provider_ignore` list to route around
  providers that cannot handle tool calling:
  ```json
  {
    "llm": {
      "model": "deepseek/deepseek-v4-flash",
      "base_url": "https://openrouter.ai/api/v1",
      "provider_ignore": ["gmicloud", "SiliconFlow", "Baidu"],
      "provider_allow_fallbacks": true
    },
    "safety": {
      "max_iterations": 500,
      "repeated_call_limit": 5
    }
  }
  ```
