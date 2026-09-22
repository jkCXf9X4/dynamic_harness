from __future__ import annotations

from dataclasses import dataclass, field

from ..core.runtime import Runtime

ID_CHARS = 8
TREE_DESC_CHARS = 40


def _clip(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[:n]


def _clip_description(text: str, n: int) -> str:
    """Clip a description to at most ``n`` chars, cutting at a word boundary
    and appending ``…`` when truncated so it never ends midline."""
    if len(text) <= n:
        return text
    cut = text[: n - 1].rstrip()
    cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def cache_hit_rate(prompt_tokens: int, cached_tokens: int) -> float:
    """Fraction of billed prompt tokens that the provider cache covered.

    ``cached_tokens`` counts tokens read from the cache within the billed
    prompt (``prompt_tokens``), so the ratio is ``cached / prompt``. A
    zero-denominator (no prompt tokens reported) yields ``0.0``.
    """
    if prompt_tokens <= 0:
        return 0.0
    return min(1.0, cached_tokens / prompt_tokens)


def fmt_usd(cost: float) -> str:
    """Compact USD formatting: whole dollars → 2dp, cents → 4dp, else 6dp."""
    if cost >= 1:
        return f"{cost:.2f}"
    if cost >= 0.01:
        return f"{cost:.4f}"
    return f"{cost:.6f}"


def fmt_int(n: int) -> str:
    """Thousands-separated with apostrophes: 1000000 → ``1'000'000``."""
    return f"{n:,}".replace(",", "'")


@dataclass
class AgentNode:
    """Tree node view-model: engine-agnostic representation of one agent."""

    agent_id: str
    description: str
    status: str
    tokens: int = 0
    messages: int = 0
    context_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    cum_cost_usd: float = 0.0
    artifact_ids: list[str] = field(default_factory=list)
    trace_path: str | None = None
    children: list[AgentNode] = field(default_factory=list)

    @property
    def short_id(self) -> str:
        return _clip(self.agent_id, ID_CHARS)

    @property
    def short_description(self) -> str:
        return _clip_description(self.description, TREE_DESC_CHARS)

    @property
    def cache_hit_rate(self) -> float:
        return cache_hit_rate(self.prompt_tokens, self.cached_tokens)

    @property
    def usage(self) -> str:
        if not (self.tokens or self.messages or self.prompt_tokens
                or self.completion_tokens or self.cost_usd or self.cum_cost_usd):
            return ""
        # Per-agent metrics in one scan line: `ctx` is the provider-billed input
        # of the LAST call (exact live context size, not an estimate); `msgs` is
        # the agent's live context message count. `in`/`out` are the cumulative
        # billed sums, `cache` the cached share of `in`. `$` is this agent's own
        # USD cost; `Σ$` adds all descendants so a delegator shows its sub-tree.
        parts = []
        if self.context_tokens:
            parts.append(f"ctx {fmt_int(self.context_tokens)}")
        if self.messages:
            parts.append(f"{fmt_int(self.messages)}msgs")
        if self.prompt_tokens or self.completion_tokens:
            parts.append(f"in {fmt_int(self.prompt_tokens)}")
            parts.append(f"out {fmt_int(self.completion_tokens)}")
            pct = round(self.cache_hit_rate * 100)
            parts.append(f"cache {pct}%")
        elif self.tokens:
            parts.append(f"{fmt_int(self.tokens)}t")
        if self.cost_usd:
            parts.append(f"${fmt_usd(self.cost_usd)}")
        if self.cum_cost_usd and self.cum_cost_usd != self.cost_usd:
            parts.append(f"Σ${fmt_usd(self.cum_cost_usd)}")
        return f" ({', '.join(parts)})"


@dataclass
class Stats:
    agents: int = 0
    commits: int = 0
    tokens: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    cache_hit_rate: float = 0.0
    cost_usd: float = 0.0


def build_agent_tree(runtime: Runtime) -> list[AgentNode]:
    """Walk runtime task graph into nested AgentNode view-models (roots only).

    Provenance (artifact ids, commit ids) is resolved in a single pass via
    ``runtime.provenance_index()`` instead of ``runtime.provenance()`` per node,
    so total cost stays linear in agent count rather than O(N·C log C) (the old
    per-node re-sort of every commit).
    """
    g = runtime.task_graph()
    agents = runtime.all_agents()
    prov = runtime.provenance_index()
    roots = [
        aid
        for aid in g
        if aid in agents and agents[aid].parent is None
    ]

    def trace_path(aid: str) -> str | None:
        if not runtime.trace_store:
            return None
        tp = runtime.trace_store.root / aid / "trace.jsonl"
        return str(tp) if tp.exists() else None

    def build(aid: str) -> AgentNode:
        agent = agents[aid]
        usage = runtime.get_usage(aid)
        p = prov.get(aid, {})
        children = [build(cid) for cid in g.get(aid, []) if cid in agents]
        # Prefer the provider-reported cost (OpenRouter bills per request at the
        # routed provider's price, so a preset per-1M-token price would be wrong);
        # fall back to the configured-price estimate only when none was reported.
        provider_cost = usage.get("cost", 0.0)
        cost_usd = provider_cost or runtime.cost_policy.cost(
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
        )
        return AgentNode(
            agent_id=agent.id,
            description=agent.task.description,
            status=agent.task.status.value,
            tokens=usage.get("total_tokens", 0),
            # Exact provider-billed input of the last call (live context size),
            # retained in the usage tracker so it survives agent GC.
            context_tokens=usage.get("last_prompt_tokens", 0),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            cached_tokens=usage.get("cached_tokens", 0),
            # Live context length (number of messages the agent is currently
            # working with), not the cumulative sum of context sizes across
            # LLM calls — so a long-running agent reads ~10² not ~10⁵. Survives
            # `_free_context()` via the agent's retained final count.
            messages=agent.live_context_messages,
            cost_usd=cost_usd,
            cum_cost_usd=cost_usd + sum(c.cum_cost_usd for c in children),
            artifact_ids=p.get("artifact_ids", []),
            trace_path=trace_path(agent.id),
            children=children,
        )

    return [build(aid) for aid in roots]


def build_stats(runtime: Runtime) -> Stats:
    total = runtime.total_usage()
    prompt = total.get("prompt_tokens", 0)
    cached = total.get("cached_tokens", 0)
    return Stats(
        agents=runtime.agent_count(),
        commits=runtime.repository.count(),
        tokens=total["total_tokens"],
        prompt_tokens=prompt,
        cached_tokens=cached,
        cache_hit_rate=cache_hit_rate(prompt, cached),
        cost_usd=total.get("cost", 0.0) or runtime.cost_policy.cost(
            tokens_in=prompt,
            tokens_out=total.get("completion_tokens", 0),
        ),
    )


def render_text_tree(nodes: list[AgentNode]) -> str:
    """Plain-text agent tree for quick operator evaluation.

    One line per agent showing id, status, description, live context message
    count, a compact token breakdown, and USD cost markers — own cost (``$``)
    and subtree cost including all descendants (``Σ$``), when the provider
    reports cost or prices are configured — enough to spot a stuck/looping
    agent without a live dashboard. Engine-agnostic (no terminal-library
    markup) so it can be persisted to disk.
    """
    if not nodes:
        return "(no agents)\n"

    lines: list[str] = []

    def walk(nodes: list[AgentNode], prefix: str, last: bool) -> None:
        for i, node in enumerate(nodes):
            is_last = i == len(nodes) - 1
            branch = "└" if is_last else "├"
            lines.append(
                f"{prefix}{branch} {node.short_id} [{node.status}] "
                f"{node.short_description}{node.usage}"
            )
            child_prefix = prefix + ("  " if is_last else "│ ")
            walk(node.children, child_prefix, is_last)

    walk(nodes, "", last=True)
    return "\n".join(lines) + "\n"