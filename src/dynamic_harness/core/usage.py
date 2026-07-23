from __future__ import annotations

import asyncio


class UsageTracker:
    def __init__(self) -> None:
        self._agent_usage: dict[str, dict] = {}
        self._usage_locks: dict[str, asyncio.Lock] = {}

    async def record_usage(
        self,
        agent_id: str,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        message_count: int = 0,
    ) -> None:
        lock = self._usage_locks.setdefault(agent_id, asyncio.Lock())
        async with lock:
            prev = self._agent_usage.get(
                agent_id,
                {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "message_count": 0,
                },
            )
            prev["prompt_tokens"] += prompt_tokens
            prev["completion_tokens"] += completion_tokens
            prev["total_tokens"] += prompt_tokens + completion_tokens
            prev["message_count"] = message_count
            self._agent_usage[agent_id] = prev

    def get_usage(self, agent_id: str) -> dict:
        return self._agent_usage.get(
            agent_id,
            {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "message_count": 0,
            },
        )

    def total_usage(self) -> dict:
        total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for u in self._agent_usage.values():
            total["prompt_tokens"] += u.get("prompt_tokens", 0)
            total["completion_tokens"] += u.get("completion_tokens", 0)
            total["total_tokens"] += u.get("total_tokens", 0)
        return total

    def clear(self) -> None:
        self._agent_usage.clear()
        self._usage_locks.clear()
