# Dynamic Harness — Critical Review Action Items

## CRITICAL

### C1 — Shell command injection in `_tool_bash`
- **File:** `src/dynamic_harness/core/capabilities.py:468-474`
- **Rationale:** `asyncio.create_subprocess_shell(command)` passes LLM-controlled input directly to the shell. Any agent (or malicious prompt) can inject arbitrary commands (e.g., `read; rm -rf /`). This is a remote code execution vulnerability since the `bash` tool is advertised as a generic execution tool.
- **Evidence:**
  ```python
  # capabilities.py:471-474
  proc = await asyncio.create_subprocess_shell(
      command,
      stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.PIPE,
  )
  ```
  No input sanitization, no command whitelist, no sandboxing.
- **Fix:** Use `asyncio.create_subprocess_exec(*shlex.split(command))` to avoid shell interpolation, or sandbox with a whitelist and cgroup/namespace confinement.
- **Status:** [ ] 

### C2 — SSRF via `_tool_webfetch`
- **File:** `src/dynamic_harness/core/capabilities.py:351-355`
- **Rationale:** No URL validation. An agent can fetch `http://169.254.169.254/latest/meta-data/` (AWS metadata), `file:///etc/passwd`, or probe internal services behind the firewall.
- **Evidence:**
  ```python
  # capabilities.py:351-355
  async with self._http_session.get(url, ...) as resp:
      ...
  ```
  No scheme restriction, no IP range blocking, no domain allowlist.
- **Fix:** Reject non-http(s) schemes, block private/reserved IP ranges, add a configurable allowlist of domains.
- **Status:** [ ]

### C3 — No cancellation safety in agent `_run_loop`
- **File:** `src/dynamic_harness/core/agent.py:280-453`
- **Rationale:** If the asyncio task driving `_run_loop` is cancelled mid-execution, state is corrupt: messages partially appended, tool calls half-executed, task status never updated from `running`. This leaks resources and leaves inconsistent state.
- **Evidence:**
  ```python
  # agent.py:242-249 — run() has no try/finally for CancelledError
  async def run(self) -> None:
      self._messages = []
      self.task.status = TaskStatus.RUNNING
      # ... no cleanup on cancellation ...
  ```
  Test at `tests/test_agent_loop.py:73` confirms task status remains `"running"` after cancellation.
- **Fix:** Add `try/finally` in `run()` that catches `asyncio.CancelledError`, calls `self.fail("Agent cancelled")`, then re-raises.
- **Status:** [ ]

### C4 — `_tool_delegate` blocks parent loop with no cancellation propagation
- **File:** `src/dynamic_harness/core/capabilities.py:378`
- **Rationale:** `await child.run()` inside a tool call blocks the parent agent's loop. If the parent is cancelled while waiting, the child keeps running as a zombie with no reference held for cleanup. No `asyncio.TaskGroup` or structured concurrency.
- **Evidence:**
  ```python
  # capabilities.py:378
  await child.run()
  # Parent blocked here — if cancelled, child is orphaned
  ```
- **Fix:** Track child run as an `asyncio.Task` stored on the parent agent. On parent cancellation, cancel all child tasks. Use `asyncio.shield` only for cleanup.
- **Status:** [ ]

---

## HIGH

### H1 — Race condition in `Runtime.record_usage`
- **File:** `src/dynamic_harness/core/runtime.py:155-161`
- **Rationale:** Read-modify-write on a shared dict with no locking. If two coroutines concurrently update the same agent's usage counters, one update can silently clobber the other.
- **Evidence:**
  ```python
  # runtime.py:155-161
  def record_usage(self, agent_id: str, usage: dict) -> None:
      ag = self._usage.setdefault(agent_id, {...})
      for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
          ag[key] += usage.get(key, 0)  # RMW race
  ```
- **Fix:** Use `asyncio.Lock` per agent ID, or an `asyncio.Queue` with a single consumer that aggregates usage.
- **Status:** [ ]

### H2 — `Repository.clear()` does not clear disk data
- **File:** `src/dynamic_harness/memory/repository.py:85-86`
- **Rationale:** `clear()` only resets the in-memory `_commits` dict but never removes files from disk. `Runtime.reset()` calls `self.repository.clear()` expecting a full reset, but commits persist on disk and will be reloaded on next construction.
- **Evidence:**
  ```python
  # repository.py:85-86
  def clear(self) -> None:
      self._commits.clear()  # Disk files untouched!
  ```
  Contrast with `ArtifactStore.clear()` which does `shutil.rmtree`, and `TraceStore.clear()` which also cleans disk. `Runtime.reset()` (line 174-186) chains all three clears and expects a full reset.
- **Fix:** Add `shutil.rmtree(self.root); self.root.mkdir(parents=True, exist_ok=True)` to `Repository.clear()`.
- **Status:** [ ]

### H3 — `ArtifactStore._load_existing` silently swallows all exceptions
- **File:** `src/dynamic_harness/artifact/store.py:57-58`
- **Rationale:** `except Exception: pass` drops corrupted artifacts with zero visibility. A malformed JSON file, a permission error, or a Pydantic validation failure all vanish silently, making debugging impossible.
- **Evidence:**
  ```python
  # store.py:57-58
  except Exception:
      pass  # Silent data loss
  ```
- **Fix:** Log a warning with the file path and exception details. Skip only `json.JSONDecodeError` and Pydantic `ValidationError`.
- **Status:** [ ]

### H4 — `TraceStore.record_llm_request` prefix hash never updates
- **File:** `src/dynamic_harness/core/trace.py:41`
- **Rationale:** `setdefault` means after the first LLM request from an agent, the prefix hash is locked permanently. If the prefix changes (e.g., after `compress()` rewrites `_messages[0:2]`), deduplication silently compares against the stale hash and either incorrectly truncates or fails to truncate.
- **Evidence:**
  ```python
  # trace.py:41
  self._prefix_seen.setdefault(agent_id, prefix_hash)
  #                              ^^^^^^^^^^ only sets on first call
  ```
- **Fix:** Use `self._prefix_seen[agent_id] = prefix_hash` to always update.
- **Status:** [ ]

### H5 — `_tool_converse` accesses private Runtime internals
- **File:** `src/dynamic_harness/core/capabilities.py:534`
- **Rationale:** Directly accesses `agent._runtime._agents` — a private dict. Violates encapsulation and creates hidden coupling between capabilities module and Runtime's internal state.
- **Evidence:**
  ```python
  # capabilities.py:534
  target = agent._runtime._agents.get(agent_id)
  ```
- **Fix:** Use the existing public `Runtime.get_agent()` method (`runtime.py:146-147`) instead.
- **Status:** [ ]

### H6 — `_tool_compress` nested LLM call has no error recovery
- **File:** `src/dynamic_harness/core/capabilities.py:498-530`
- **Rationale:**
  1. Compression call uses `generate_with_tools` with `tools=[]` but no `tool_choice` is set — if the LLM hallucinates tool calls, it fails.
  2. If the compression LLM call raises, it propagates while agent messages are in an undefined state.
  3. No retry logic.
- **Evidence:**
  ```python
  # capabilities.py:498-530
  response = await agent.llm.generate_with_tools(
      messages=convo,
      tools=[],  # No tool_choice="none" guard
      ...
  )
  ```
- **Fix:** Set `tool_choice="none"`. Wrap in a retry loop. On total failure, return error without mutating `agent._messages`.
- **Status:** [ ]

### H7 — `Agent.run()` silently reports success with no LLM configured
- **File:** `src/dynamic_harness/core/agent.py:254-257`
- **Rationale:** When `self.llm` is `None`, the agent calls `self.report()` with a fabricated summary. The parent receives this as a successful completion with no indication it was a no-op.
- **Evidence:**
  ```python
  # agent.py:254-257
  if self.llm is None:
      payload = ReportPayload(
          task_id=self.task.id,
          summary=f"Agent executed: {self.task.description}",
      )
      await self.report(payload)
      return
  ```
- **Fix:** Call `self.fail("No LLM provider configured")` instead.
- **Status:** [ ]

### H8 — `_tool_read` and `_tool_write` have no path traversal protection
- **File:** `src/dynamic_harness/core/capabilities.py:305-311`
- **Rationale:** `Path(path).read_text()` accepts any path including `../../etc/passwd`. Combined with LLM having unrestricted control, this allows reading/writing arbitrary files on the host.
- **Evidence:**
  ```python
  # capabilities.py:305-311
  content = Path(path).read_text()   # No path validation
  Path(path).write_text(content)     # No path validation
  ```
- **Fix:** Resolve paths against a sandbox root directory and reject paths outside that root. Add a `_resolve_safe_path(base_root, requested_path)` utility.
- **Status:** [ ]

---

## MEDIUM

### M1 — `deliver_report` duplicates strip calls
- **File:** `src/dynamic_harness/core/runtime.py:84-85`
- **Rationale:** The second `.strip()` on line 85 is redundant — the first already stripped, and slicing `[:200]` cannot introduce whitespace.
- **Evidence:**
  ```python
  # runtime.py:84-85
  headline = lines[0].strip()[:200]
  headline = headline.strip()[:200]  # Redundant
  ```
- **Fix:** Remove the duplicate line 85.
- **Status:** [ ]

### M2 — `_tool_grep` swallows all file read errors silently
- **File:** `src/dynamic_harness/core/capabilities.py:461-462`
- **Rationale:** `except Exception: pass` catches PermissionError, UnicodeDecodeError, OSError — all silently discarded. Agent gets "No matches found" when files exist but couldn't be read, leading to incorrect conclusions.
- **Evidence:**
  ```python
  # capabilities.py:461-462
  except Exception:
      pass  # Files with errors silently excluded from results
  ```
- **Fix:** Collect and return a count of files that couldn't be read, or log warnings.
- **Status:** [ ]

### M3 — `_tool_glob` rebuilds gitignore filter on every call
- **File:** `src/dynamic_harness/core/capabilities.py:342`
- **Rationale:** Reads `.gitignore` and parses it fresh every time `glob` is called. For agents that call glob frequently, this is wasteful I/O and CPU.
- **Evidence:**
  ```python
  # capabilities.py:342
  gitignore_filter = _build_gitignore_filter(self._agent._runtime.workspace_root)
  # Called on every single glob invocation
  ```
- **Fix:** Cache the filter on the Runtime, re-read only if `.gitignore` mtime changes.
- **Status:** [ ]

### M4 — `Agent.delegate()` passes `**metadata: object` but Task expects `dict[str, Any]`
- **File:** `src/dynamic_harness/core/agent.py:455` and `src/dynamic_harness/core/task.py:27`
- **Rationale:** `Agent.delegate(**metadata: object)` accepts `object` values, but `Task.metadata: dict[str, Any]`. If a non-serializable object is passed, Pydantic accepts it but `model_dump_json()` fails later. The type annotation `object` also loses all type information.
- **Evidence:**
  ```python
  # agent.py:455
  async def delegate(self, description, role=None, system_prompt=None, **metadata: object):
      task = Task(description=description, role=role, system_prompt=system_prompt, metadata=metadata)
  ```
- **Fix:** Change signature to `**metadata: Any` and add Pydantic validation on `Task.metadata`.
- **Status:** [ ]

### M5 — `OpenAIProvider.generate_structured` fallback fragile with JSON arrays
- **File:** `src/dynamic_harness/llm/openai_provider.py:151-154`
- **Rationale:** If structured parsing fails, fallback calls `_extract_json()` which returns `object`. If the JSON is an array `[...]`, then `response_model(**data)` crashes at runtime since you can't unpack a list as kwargs.
- **Evidence:**
  ```python
  # openai_provider.py:151-154
  data = self._extract_json(text.content)  # Returns object (could be a list)
  return response_model(**data)             # Crashes if data is a list
  ```
- **Fix:** Check `isinstance(data, dict)` before unpacking. If it's a list or scalar, wrap it or raise a descriptive error.
- **Status:** [ ]

### M6 — `config.load_harness_config` does not handle invalid JSON
- **File:** `src/dynamic_harness/config.py:47-48`
- **Rationale:** `json.loads()` raises uncaught `json.JSONDecodeError` if the config file is malformed — propagates to caller with a cryptic traceback instead of a descriptive error.
- **Evidence:**
  ```python
  # config.py:47-48
  defaults = json.loads(cfg_path.read_text())  # No JSONDecodeError handler
  ```
- **Fix:** Catch `json.JSONDecodeError` and raise a descriptive `ValueError` with the file path.
- **Status:** [ ]

### M7 — `Runtime.reset()` clears event handlers
- **File:** `src/dynamic_harness/core/runtime.py:182-186`
- **Rationale:** `reset()` clears all handler lists. A user who calls `runtime.on_report(fn)` and then `runtime.reset()` loses their handler registration. This behavior is undocumented and surprising.
- **Evidence:**
  ```python
  # runtime.py:182-186
  self._report_handlers.clear()
  self._escalation_handlers.clear()
  self._failure_handlers.clear()
  self._budget_request_handlers.clear()
  ```
- **Fix:** Document this clearly, or add a `reset(clear_handlers: bool = False)` parameter.
- **Status:** [ ]

### M8 — `_tool_delegate` returns unstructured text
- **File:** `src/dynamic_harness/core/capabilities.py:389-402`
- **Rationale:** The return value is a free-text string the parent LLM must parse. No structured fields for child_id, status, summary, artifact_ids, confidence, or failure_reason. This is fragile and error-prone for the LLM.
- **Evidence:**
  ```python
  # capabilities.py:389-402
  return (
      f"Delegated to agent {child.agent_id}\n"
      f"Status: {child.task.status}\n"
      f"Summary: {report.summary}\n"
      # LLM must parse this unstructured text
  )
  ```
- **Fix:** Return a JSON string with structured fields: `child_id`, `status`, `summary`, `artifact_ids`, `confidence`, `failure_reason`.
- **Status:** [ ]

### M9 — No agent-level wall-clock timeout
- **File:** `src/dynamic_harness/core/agent.py:280-453`
- **Rationale:** The agent loop has iteration limits (max 500) and repeated-call detection, but no wall-clock timeout. A slow LLM or a varied-but-infinite loop could run indefinitely, consuming tokens and resources.
- **Evidence:** `_run_loop()` has `_safety_max_iterations` and `_repeated_batch_limit` but no `time.monotonic()` timeout check.
- **Fix:** Add a `safety_timeout_seconds` parameter to `Agent.__init__`, checked at the top of each iteration.
- **Status:** [ ]

### M10 — `Task.created_at` default factory issue on deserialization
- **File:** `src/dynamic_harness/core/task.py:26`
- **Rationale:** Pydantic `default_factory` creates the timestamp on model instantiation, but if a `Task` is deserialized from JSON (e.g., from `Repository`), the factory won't fire. This means tasks loaded from disk may have `None` timestamps.
- **Evidence:**
  ```python
  # task.py:26
  created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
  ```
- **Fix:** Add `validate_default=True` or handle missing timestamps in loaders.
- **Status:** [ ]

---

## LOW

### L1 — `ToolRegistry.execute` catches `Exception` too broadly (Python 3.8 concern)
- **File:** `src/dynamic_harness/core/capabilities.py:58`
- **Rationale:** On Python 3.8, `asyncio.CancelledError` is a subclass of `Exception`, so `except Exception` would swallow cancellation. On 3.10+ (the project's minimum), this is not an issue since `CancelledError` inherits from `BaseException`.
- **Evidence:** Project requires Python 3.10+, so this is a theoretical concern only.
- **Fix:** No change needed for current Python version. Note if backporting.
- **Status:** [ ]

### L2 — `Agent._messages` typed as `list | None` with repeated None checks
- **File:** `src/dynamic_harness/core/agent.py:237`
- **Rationale:** `_messages` starts as `None`, is set in `run()`, and then guarded by `assert self._messages is not None` in `_run_loop()`. The `assert` could be stripped with `python -O`. Every method that accesses `_messages` has to check for `None`.
- **Evidence:**
  ```python
  # agent.py:237
  _messages: list[dict[str, Any]] | None = None
  # Multiple methods check `if self._messages is not None`
  ```
- **Fix:** Initialize `_messages = []` in `__init__` and use a sentinel or boolean to track whether `run()` has been called.
- **Status:** [ ]

### L3 — Inline `type: ignore[abstract]` placement in tests
- **File:** `tests/backend/test_provider.py:101`
- **Rationale:** Inline type ignore comments may not be recognized by all type checkers. Stylistic issue.
- **Evidence:** `# type: ignore[abstract]` on the same line as the instantiation.
- **Fix:** Move to preceding line or ensure tooling accepts inline ignores.
- **Status:** [ ]

### L4 — No test coverage for `_tool_converse`, `_tool_compress`, `_tool_ask`, `_tool_escalate`, `_tool_fail`
- **File:** `tests/backend/test_capabilities.py`
- **Rationale:** These 5 tool implementations have zero tests beyond the registration check. `_tool_compress` in particular is a complex code path (nested LLM call, message mutation) with no coverage.
- **Evidence:** Grep shows no test functions for these tools beyond `test_default_tools_all_fifteen`.
- **Fix:** Add mock-LLM-based tests for each tool.
- **Status:** [ ]

### L5 — No test coverage for `_tool_bash` edge cases
- **File:** `tests/backend/test_capabilities.py`
- **Rationale:** The `bash` tool has no test coverage at all. Edge cases like timeout triggering, commands that only write to stderr, and commands producing no output are untested.
- **Evidence:** No test function for `_tool_bash` exists.
- **Fix:** Add parameterized tests for the bash tool.
- **Status:** [ ]

### L6 — `test_runner_reuse_across_multiple_runs` uses non-strict assertions
- **File:** `tests/backend/test_agent_loop.py:94-99`
- **Rationale:** `assert len(runner.last_reports) >= 2` passes if >=2 reports exist, even if 3, 4, or 5 were generated. A bug causing duplicate reports per run would not be caught.
- **Evidence:**
  ```python
  # test_agent_loop.py:94-99
  assert len(runner.last_reports) >= 2  # Should be == 2
  ```
- **Fix:** `assert len(runner.last_reports) == 2`.
- **Status:** [ ]

### L7 — `_tool_edit` replaces only first occurrence — ambiguous behavior
- **File:** `src/dynamic_harness/core/capabilities.py:362`
- **Rationale:** `str.replace(..., 1)` only replaces the first occurrence. The tool description says "Replace old_string with new_string in a file" — ambiguous whether it means first or all occurrences. If `old_string` appears in a docstring or comment before the intended target, the wrong match is replaced.
- **Evidence:**
  ```python
  # capabilities.py:362
  content = content.replace(old_string, new_string, 1)  # First occurrence only
  ```
- **Fix:** Add explicit documentation in the tool description, or add a `count` parameter.
- **Status:** [ ]

### L8 — `hierarchical_summary` uses `str.title()` which mangles underscores
- **File:** `src/dynamic_harness/artifact/summary.py:21`
- **Rationale:** `level_name.title()` turns `"detailed_technical"` into `"Detailed_Technical"` (not `"Detailed Technical"`). The test confirms this is expected behavior, but it looks like a formatting bug.
- **Evidence:**
  ```python
  # summary.py:21
  level_name.title()  # Produces "Detailed_Technical" not "Detailed Technical"
  ```
- **Fix:** Use `level_name.replace("_", " ").title()` for proper formatting.
- **Status:** [ ]

### L9 — No `__all__` exports in `__init__.py` files
- **File:** `src/dynamic_harness/core/__init__.py`, `artifact/__init__.py`, `llm/__init__.py`, `memory/__init__.py`
- **Rationale:** No curated public API surface — all internals are importable, and refactoring internal modules would break consumers. Makes it unclear which classes are public vs implementation details.
- **Evidence:** `__init__.py` files are empty or minimal.
- **Fix:** Add explicit `__all__` exports in each `__init__.py` to define the public API.
- **Status:** [ ]

### L10 — Missing `py.typed` marker per PEP 561
- **File:** (nonexistent — `src/dynamic_harness/py.typed`)
- **Rationale:** PEP 561 requires a `py.typed` file in the package root for type checkers to recognize the package as typed. All code uses type hints but downstream consumers don't benefit.
- **Evidence:** `src/dynamic_harness/py.typed` does not exist.
- **Fix:** Add an empty `src/dynamic_harness/py.typed` file.
- **Status:** [ ]