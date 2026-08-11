from __future__ import annotations

import json
from typing import Any

from ..llm.provider import LLMProvider


class AgentContext:
    """Owns an agent's turn accounting and conversation message buffer.

    Encapsulates the machinery for committing turns, pruning staleness,
    restoring pruned turns, and compressing the conversation. Keeping this
    state and its invariants in one place means the Agent run-loop and the
    context-management tools (`prune`, `restore`, `compress`) never have to
    reach into each other's private fields.
    """

    def __init__(self, *, active_turn_window: int = 50, max_pruned_retained: int = 100) -> None:
        self.active_turn_window = max(int(active_turn_window), 1)
        self.max_pruned_retained = max(int(max_pruned_retained), 0)
        self.reset(None, None)

    def reset(self, system_prompt: str | None, user_message: str | None) -> None:
        """Begin a fresh conversation (optionally seeding system + user)."""
        if system_prompt is None and user_message is None:
            self.messages: list[dict[str, Any]] = []
        else:
            self.messages = [
                {"role": "system", "content": system_prompt or ""},
                {"role": "user", "content": user_message or ""},
            ]
        self.turn_counter: int = 0
        self.turn_order: list[str] = []
        self.turns: dict[str, list[dict[str, Any]]] = {}
        self.pruned: set[str] = set()
        self.prune_markers: dict[str, dict[str, Any]] = {}
        self.in_flight_prune: set[str] = set()

    def append(self, message: dict[str, Any]) -> None:
        self.messages.append(message)

    # -- turn lifecycle ---------------------------------------------------

    def commit_turn(self, assistant_msg: dict[str, Any], results: list[dict[str, Any]]) -> str:
        pid = f"t{self.turn_counter}"
        self.turn_counter += 1
        self.turn_order.append(pid)
        self.turns[pid] = [assistant_msg] + list(results)
        if pid in self.in_flight_prune:
            self.in_flight_prune.discard(pid)
            self._mark_turn_pruned(pid)
        else:
            self.messages.append(assistant_msg)
            self.messages.extend(results)
        return pid

    def _mark_turn_pruned(self, pid: str) -> None:
        marker = {
            "role": "assistant",
            "content": self.make_prune_marker(pid),
        }
        self.messages.append(marker)
        self.pruned.add(pid)
        self.prune_markers[pid] = {"marker": marker, "index": len(self.messages) - 1}
        self.evict_overflow()

    def make_prune_marker(self, pid: str) -> str:
        turn_msgs = self.turns[pid]
        tool_names = ", ".join(
            tc.get("function", {}).get("name", "?")
            for tc in turn_msgs[0].get("tool_calls", [])
        ) if turn_msgs and turn_msgs[0].get("role") == "assistant" else "reply"
        tail = ""
        for m in reversed(turn_msgs):
            content = m.get("content")
            if content:
                tail = content
                break
        tail = tail[:200]
        suffix = "…" if len(tail) == 200 else ""
        return (
            f"[PRUNED {pid} ({tool_names}) — retained for restore(prune_id={pid!r}). "
            f"Tail: {tail}{suffix}]"
        )

    # -- read/observe helpers --------------------------------------------

    def turn_token_estimate(self, pid: str) -> int:
        total = 0
        for m in self.turns.get(pid, []):
            total += len(str(m.get("content") or ""))
            for tc in m.get("tool_calls") or []:
                total += len(json.dumps(tc.get("function", {}).get("arguments", "")))
        return max(1, total // 4)

    def turn_tool_names(self, pid: str) -> str:
        names: list[str] = []
        for msg in self.turns.get(pid, []):
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls", []):
                    name = tc.get("function", {}).get("name")
                    if name:
                        names.append(name)
        return ",".join(names) if names else "reply"

    def active_turn_ids(self) -> list[str]:
        active = [pid for pid in self.turn_order if pid not in self.pruned]
        return active[-self.active_turn_window:]

    def evict_overflow(self) -> list[str]:
        evicted: list[str] = []
        if self.max_pruned_retained <= 0:
            return evicted
        while len(self.pruned) > self.max_pruned_retained:
            candidate = next(
                (p for p in self.turn_order if p in self.pruned),
                None,
            )
            if candidate is None:
                break
            entry = self.prune_markers.pop(candidate, None)
            if entry is not None:
                marker = entry.get("marker")
                if marker is not None:
                    self.messages = [
                        m for m in self.messages if m is not marker
                    ]
            self.pruned.discard(candidate)
            self.turns.pop(candidate, None)
            evicted.append(candidate)
        return evicted

    # -- context management (used by prune/restore/compress tools) --------

    def prune(self, prune_ids: list[str] | str | None) -> dict[str, Any] | None:
        """Drop whole committed turns, replacing them with PRUNED markers.

        Returns a dict describing what happened, or None when there was no
        work to do (the caller should still surface a guidance message via
        ``message`` when provided).
        """
        if isinstance(prune_ids, str):
            prune_ids = [pid.strip() for pid in prune_ids.split(",") if pid.strip()]
        requested = [str(pid) for pid in (prune_ids or [])]

        if not requested:
            return {
                "action": False,
                "message": (
                    "prune(prune_ids=[...]) drops whole committed turns (assistant "
                    "message + tool results) and replaces them with a short PRUNED "
                    "marker. IDs are listed in your Context Observation as "
                    "'prune_id:tools'; use restore(prune_id=...) to bring one back."
                ),
                "turns_pruned": [],
                "chars_saved": 0,
                "evicted": [],
            }

        next_turn = f"t{self.turn_counter}"
        in_flight = [pid for pid in requested if pid == next_turn]
        for pid in in_flight:
            self.in_flight_prune.add(pid)

        if not self.turns and not in_flight:
            return {"action": False, "message": "No committed turns to prune.",
                    "turns_pruned": [], "chars_saved": 0, "evicted": []}

        invalid = [pid for pid in requested if pid not in self.turns and pid != next_turn]
        already = [pid for pid in requested if pid in self.pruned]
        pending = [pid for pid in requested if pid in self.turns and pid not in self.pruned]

        if not pending and not in_flight:
            notes = []
            if already:
                notes.append(f"already pruned (use restore): {already}")
            if invalid:
                notes.append(f"unknown ids (see Context Observation): {invalid}")
            return {"action": False,
                    "message": "Nothing to prune. " + "; ".join(notes),
                    "turns_pruned": [], "chars_saved": 0, "evicted": []}

        remove: dict[int, str] = {}
        for pid in pending:
            for m in self.turns[pid]:
                remove[id(m)] = pid

        existing_marker_by_id = {
            id(info["marker"]): pid
            for pid, info in self.prune_markers.items()
        }

        new_messages: list[dict[str, Any]] = []
        marker_for: dict[str, dict[str, Any]] = {}
        i = 0
        idx = 0
        messages = self.messages
        while i < len(messages):
            m = messages[i]
            pid = remove.get(id(m))
            if pid is None:
                new_messages.append(m)
                old_pid = existing_marker_by_id.get(id(m))
                if old_pid is not None:
                    self.prune_markers[old_pid]["index"] = idx
                i += 1
                idx += 1
                continue
            turn_len = len(self.turns[pid])
            marker = {
                "role": "assistant",
                "content": self.make_prune_marker(pid),
            }
            marker_for[pid] = {"marker": marker, "index": idx}
            new_messages.append(marker)
            i += turn_len
            idx += 1

        self.messages = new_messages
        for pid in pending:
            self.pruned.add(pid)
            self.prune_markers[pid] = marker_for[pid]

        chars_saved = sum(
            len(json.dumps(m)) for pid in pending for m in self.turns[pid]
        )
        evicted = self.evict_overflow()

        notes = []
        if invalid:
            notes.append(f"unknown ids (see Context Observation): {invalid}")
        if already:
            notes.append(f"already pruned (use restore): {already}")
        if evicted:
            notes.append(
                f"old retained turns permanently discarded "
                f"(retention cap {self.max_pruned_retained}): {evicted}"
            )
        if in_flight:
            notes.append(
                f"{next_turn} (this response's turn) will be pruned at commit — "
                f"its content stays recoverable via restore"
            )
        suffix = ("; " + "; ".join(notes)) if notes else ""
        return {
            "action": True,
            "message": (
                f"Pruned turns {pending} ({len(pending)} turns, ~{chars_saved} chars "
                f"removed from context). Replaced with PRUNED markers. "
                f"Use restore(prune_id=...) to bring one back.{suffix}"
            ),
            "turns_pruned": pending,
            "chars_saved": chars_saved,
            "evicted": evicted,
        }

    def restore(self, prune_id: str) -> str:
        prune_id = str(prune_id)
        entry = self.prune_markers.get(prune_id)
        if entry is None:
            return (f"Nothing to restore for {prune_id!r}: it is not currently pruned "
                    f"(or was evicted and is no longer retained).")
        turn_msgs = self.turns[prune_id]
        marker = entry["marker"]
        messages = self.messages
        target_idx: int | None = None

        stored_idx = entry.get("index")
        if stored_idx is not None and 0 <= stored_idx < len(messages) and messages[stored_idx] is marker:
            target_idx = stored_idx
        else:
            for j, m in enumerate(messages):
                if m is marker:
                    target_idx = j
                    break
        if target_idx is None:
            return (f"Cannot restore {prune_id!r}: its PRUNED marker is no longer present "
                    f"in the context (likely removed by compression or eviction).")

        self.messages = messages[:target_idx] + turn_msgs + messages[target_idx + 1:]
        for pid, info in self.prune_markers.items():
            if pid == prune_id:
                continue
            idx = info.get("index")
            if idx is not None and idx > target_idx:
                info["index"] = idx + (len(turn_msgs) - 1)
        self.pruned.discard(prune_id)
        self.prune_markers.pop(prune_id, None)

        chars = sum(len(json.dumps(m)) for m in turn_msgs)
        n_tools = len(turn_msgs) - 1
        return (
            f"Restored turn {prune_id} (assistant + {n_tools} tool result(s), "
            f"~{chars} chars) at its original position."
        )

    async def compress(self, llm: LLMProvider, compression_prompt: str) -> dict[str, Any]:
        compression_input = [
            {"role": "system", "content": compression_prompt},
        ] + self.messages[1:]

        response = None
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = await llm.generate_with_tools(compression_input, tools=[])
                break
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    continue

        if response is None:
            return {"ok": False,
                    "message": f"Compression failed after 2 attempts: {last_error}",
                    "summary": ""}

        summary = (response.content or "").strip()
        if not summary:
            return {"ok": False, "message": "Compression produced empty summary.", "summary": ""}

        before = len(self.messages)
        self.messages = [
            self.messages[0],
            {"role": "system", "content": f"[Context compressed] {summary}"},
        ]
        self.pruned.clear()
        self.prune_markers.clear()
        self.turn_order.clear()
        self.turns.clear()
        after = len(self.messages)
        saved = before - after
        return {
            "ok": True,
            "message": f"Compressed: {before} messages -> {after} messages ({saved} removed).",
            "before": before,
            "after": after,
            "saved": saved,
            "summary": summary,
        }

