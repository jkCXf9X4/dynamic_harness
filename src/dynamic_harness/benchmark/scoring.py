"""Objective scoring and aggregation of per-run metrics into comparable totals.

The scoring model is explicit and weights are configurable. Correctness is the
primary gate: a prompt must pass a task to earn credit on it. Among correctness,
we score *efficiency* (lower cost/tokens/turns/depth is better) using inverse
normalization, plus a latency penalty.

This replaces the prior flow's "quality of prose" subjective ranking with a
fixed, deterministic, weighted rubric.
"""

from __future__ import annotations

from dataclasses import dataclass

from .metrics import RunMetrics


@dataclass
class ScoringWeights:
    # Correctness dominates; everything else is secondary efficiency.
    correctness: float = 0.60
    cost: float = 0.15
    tokens: float = 0.10
    turns: float = 0.07
    depth: float = 0.04
    latency: float = 0.04

    def total(self) -> float:
        return (self.correctness + self.cost + self.tokens
                + self.turns + self.depth + self.latency)


WEIGHTS = ScoringWeights()


def _inverse_normalize(values: list[float]) -> list[float]:
    """Turn 'lower is better' values into (higher = better) in [0, 1].

    Best (lowest) value maps to 1.0, worst (highest) to 0.0.
    If all values are equal, each maps to 1.0.
    """
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return [1.0] * len(values)
    return [(hi - v) / (hi - lo) for v in values]


def _forward_normalize(values: list[float]) -> list[float]:
    """Turn 'higher is better' values into (higher = better) in [0, 1]."""
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return [1.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


@dataclass
class PromptResult:
    prompt_id: str
    per_task: list[RunMetrics]
    # Derived aggregates
    tasks_passed: int = 0
    tasks_total: int = 0
    passed_fraction: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_turns: int = 0
    max_depth: int = 0
    total_latency: float = 0.0
    efficiency_score: float = 0.0
    final_score: float = 0.0


def aggregate(prompt_id: str, runs: list[RunMetrics]) -> PromptResult:
    """Aggregate all task runs for one prompt into a comparable PromptResult."""
    res = PromptResult(prompt_id=prompt_id, per_task=runs)
    res.tasks_total = len(runs)
    res.tasks_passed = sum(1 for r in runs if r.passed)
    res.passed_fraction = res.tasks_passed / max(1, res.tasks_total)
    res.total_tokens = sum(r.total_tokens for r in runs)
    res.total_cost = sum(r.cost_usd for r in runs)
    res.total_turns = sum(r.total_turns for r in runs)
    res.max_depth = max((r.max_depth for r in runs), default=0)
    res.total_latency = sum(r.latency_s for r in runs)
    return res


def rank(results: list[PromptResult], *, weights: ScoringWeights = WEIGHTS) -> list[PromptResult]:
    """Fill in efficiency + final scores and sort best-first.

    Efficiency is computed per-metric across prompts using inverse normalization
    over the corresponding metric sums; the passed-fraction is normalized too.
    Final score = correctness_weight*norm(passed_fraction)
                + sum(weight * inverse_norm(metric_sum) for efficiency metrics).

    This yields a deterministic 0..1 ranking where correctness dominates but
    cheaper/faster/shallower runs are rewarded within correctness tiers.
    """
    if not results:
        return results

    passed_fracs = [r.passed_fraction for r in results]
    costs = [r.total_cost for r in results]
    tokens = [r.total_tokens for r in results]
    turns = [r.total_turns for r in results]
    depths = [r.max_depth for r in results]
    lats = [r.total_latency for r in results]

    n_passed = _forward_normalize(passed_fracs)
    n_cost = _inverse_normalize(costs)
    n_tokens = _inverse_normalize([float(t) for t in tokens])
    n_turns = _inverse_normalize([float(t) for t in turns])
    n_depth = _inverse_normalize([float(d) for d in depths])
    n_lat = _inverse_normalize(lats)

    for i, r in enumerate(results):
        r.efficiency_score = (
            weights.cost * n_cost[i]
            + weights.tokens * n_tokens[i]
            + weights.turns * n_turns[i]
            + weights.depth * n_depth[i]
            + weights.latency * n_lat[i]
        )
        r.final_score = (
            weights.correctness * n_passed[i] + r.efficiency_score
        ) / weights.total()

    results.sort(key=lambda r: -r.final_score)
    return results


def format_scores(results: list[PromptResult]) -> str:
    lines = [
        "aggregate",
        f"{'prompt':<24}{'pass':>6}{'tokens':>10}{'cost$':>9}{'turns':>8}{'depth':>6}{'lat(s)':>8}{'eff':>6}{'score':>7}",
    ]
    for r in results:
        lines.append(
            f"{r.prompt_id:<24}{r.tasks_passed}/{r.tasks_total:>3}"
            f"{r.total_tokens:>10}{r.total_cost:>9.4f}{r.total_turns:>8}"
            f"{r.max_depth:>6}{r.total_latency:>8.1f}"
            f"{r.efficiency_score:>6.2f}{r.final_score:>7.3f}"
        )
    return "\n".join(lines)
