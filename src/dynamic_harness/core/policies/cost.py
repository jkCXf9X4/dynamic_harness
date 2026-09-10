"""Cost conversion policy as a composable policy object (G9).

``config.llm.price_input_per_mtok`` / ``price_output_per_mtok`` previously
fed ONLY the benchmark report — no runtime surface could express the USD cost
of a run. This policy owns the price → cost conversion so the same formula a
benchmark uses is available to the runtime, the CLI, and a plugin host.

Prices are USD per 1M tokens (``_per_mtok``); ``0``/``None`` price means
"unknown price" → cost 0 (uncounted, not free — the caller decides how to
report an unknown-price run).
"""

from __future__ import annotations


class CostPolicy:
    """USD cost of token usage, from configured per-1M-token prices.

    Host-agnostic: an embedded host or MCP cost-tracking service applies the
    same conversion without importing a runtime or agent.
    """

    def __init__(
        self,
        *,
        price_input_per_mtok: float | None = None,
        price_output_per_mtok: float | None = None,
    ) -> None:
        self.price_input_per_mtok: float | None = price_input_per_mtok
        self.price_output_per_mtok: float | None = price_output_per_mtok

    def input_cost(self, tokens_in: int) -> float:
        """USD cost of ``tokens_in`` prompt tokens at the input price."""
        return self._mtok_cost(self.price_input_per_mtok, tokens_in)

    def output_cost(self, tokens_out: int) -> float:
        """USD cost of ``tokens_out`` completion tokens at the output price."""
        return self._mtok_cost(self.price_output_per_mtok, tokens_out)

    def cost(self, *, tokens_in: int, tokens_out: int) -> float:
        """Total USD cost of a token pair (input + output)."""
        return self.input_cost(tokens_in) + self.output_cost(tokens_out)

    @staticmethod
    def _mtok_cost(price_per_mtok: float | None, tokens: int) -> float:
        if not price_per_mtok or tokens <= 0:
            return 0.0
        return round(float(price_per_mtok) * int(tokens) / 1_000_000, 6)