# Tool definitions and help — real signatures + docstrings for `harness_tools`

## The question

How do we give the `harness_tools` RPC stub **real definitions** — the actual
function signatures and descriptions, not a hand-copied shadow — that (a) can be
**injected into / read as the prompt-side tool reference** the model writes code
against, and (b) make **Python's native help features usable in the sandbox**
(`help()`, `pydoc`, `inspect.signature`) so the code itself can collect tool
information on demand?

## Current state (facts)

- The stub is a hand-written module constant (`core/tools/code.py::_STUB_SOURCE`):
  24 bridge functions + 3 terminal markers, written to a tempdir at each `invoke`.
- The stub functions carry **no docstrings** (only the module docstring). Inside
  the sandbox, `help(harness_tools.read)` prints the bare signature and nothing
  else — no description, no parameter docs.
- The model writing `invoke` code sees only tool **names** in the invoke
  description (`read, grep, write, delegate, ask, converse, plan, checkpoint,
  usage, status, ...`). It never sees the stub text, signatures, or docs at
  generation time — it guesses, or burns a probe turn.
- Hand-maintenance drift: every new tool / signature change needs a manual stub
  edit, and nothing verifies parity. (Today's signatures happen to match; the
  risk is forward, and any tool added later silently misses the stub.)
- The real definitions already live in the runtime — `ToolDef(name,
  description, input_schema)` plus the actual tool function (`*args`): one source
  of truth, currently unused by the stub.
- `_STUB_SOURCE` mirrors `token_limit`/`token_offset` on `read` etc., but the
  parent strips those knobs from bridge calls (the code gets full payloads
  in-process) — the stub advertises parameters that do nothing.

**Verified mechanism** (spike): a stub generated as source and loaded with
`exec` keeps real signatures — `inspect.signature(fn)` reads the code object —
and real docstrings — `help()` / `pydoc.render_doc(fn)` render
"definition + signature + Args" natively. Defaults copied from the real
function (e.g. `strategy="automatic"`, `recursive=False`) forward to the bridge
exactly, preserving call parity.

## Design options

| Option | Mechanism | Verdict |
|---|---|---|
| **A. Checked-in readable module** | A real `harness_tools.py` (full docstrings + minimal `_call` wrappers), **generated once from the registry and checked in**, never generated per invoke. A parity test re-derives it and fails on drift. The agent gets the overview by **reading the file** (or `help()` inside a snippet). | **Recommended** |
| B. Generate per invoke | `build_stub_source(registry, role)` renders each bridge tool at invoke time. | Fallback — no per-invoke cost problem actually exists; rendering is cheap, but a tempdir write + a live generator is strictly more machinery than a copy of a checked-in file. |
| C. Keep the constant, add docstrings | Parallel hand-maintained mapping constant → docstrings. | Rejected — two sources of truth, same drift, help() only as complete as the mapping. |
| D. Runtime help RPC only | Stub stays bare; a custom `help(name)` call fetches the ToolDef over the wire. | Rejected — native `help()`/`pydoc`/`inspect` not usable (the requested *Python help features*), signatures still hand-maintained. |

## Recommended design (A): a readable module, generated once, checked in

The stub stays a thin-wrapper module — its functions already *are* minimal
wrappers (`return _call(name, **{...})`); what changes is that it becomes:

1. **A real file with real docstrings**, so the agent can `read` it for the
   initial overview instead of guessing:

   ```python
   def read(path):
       """Read a file from disk by path

       Args:
           path (str): Absolute or relative file path
       """
       return _call("read", path=path)
   ```

   - Docstring from `ToolDef.description` + per-property `input_schema`
     descriptions (types included).
   - Signature equal to the real fn (minus `ctx`, minus underscore-prefixed
     internals like `_tool_call_id`), defaults copied → call parity by
     construction. Generic `token_limit`/`token_offset` knobs absent — the
     bridge neutralizes them anyway.
   - Terminal tools (`report`/`escalate`/`fail`) keep their names but return
     the `# TERMINAL:` marker (they stay blocked on the wire).
   - Module `__doc__` renders a `name — one-line description` catalog, so
     `help(harness_tools)` (no args) prints the whole surface, and a zero-arg
     `docs()` returns it as a printable string.

2. **Generated once, never per invoke.** A small sync script renders the file
   from the live registry; it is **checked in** (like the product-breakdown's
   generated registers). Invoke-time work shrinks to copying the checked-in text
   into the tempdir (or pointing `HARNESS_TOOLS` straight at the bundled file) —
   no rendering, no generator in the hot path.

3. **Readable by the agent.** The file's directory is added to
   `_read_only_roots` (the same mechanism the reference/skills library uses), so
   the normal `read` tool reaches it from any workspace. The invoke description
   advertises the path: "run `help(harness_tools)` or read `<path>` for the full
   tool reference." Codeact agents (no direct `read`) get the same overview with
   a one-line probe: `help(harness_tools)` — printed into context, stdout-capped.

4. **Role gating stays server-side, so one static file is safe.** The bridge
   enforces policy at `ToolRegistry.execute()` (a disallowed tool returns an
   error). Showing the full catalog as *documentation* cannot bypass that — the
   current always-full stub already works this way. Per-role stub generation was
   a nicety, not a requirement.

### The overview economics (why this replaces a prompt index)

Zero fixed prompt cost: nothing about `harness_tools` docs is injected up front.
The model pulls the file (or `help()`) when it needs it; a `read <path>` at task
start is a normal cached read, so the docs stay in context for the rest of the
task via the ResultStore. This is the artifact progressive-disclosure pattern
applied to the tool docs — and it beats a compact index (P2 below) because the
*total* context cost is the same or lower, and it is on demand.

| Injection | Model sees | Cost | Use |
|---|---|---|---|
| P1 full generated stub text | the whole `.py` in the system prompt (Hermes-style) | ~1.5–3 K tokens/turn prefix | not needed — the file is readable |
| P2 compact index | one line per bridge tool | ~400–600 tok fixed | redundant once the file is readable |
| **P3 the readable file** | `read <path>` / `help(harness_tools)` on demand | zero fixed; docs enter context only when asked | **recommended** |
| P4 gated | `invoke.tool_index_in_prompt: none\|compact\|full` | config knob | keep as an escape hatch |

## Why a dispatcher at all? — and the agent-authored-surface goal

The stub's wrappers are `_call(name, **kwargs)` proxies because the real tool
functions are `async` and need a live `ToolContext` (agent, runtime loop, result
store, repo lock, comms routing) — state that exists only in the parent process.
The subprocess boundary (trust parity with `bash`: process-group kill, crash/OOM/
busy-loop isolation) is why execution is parent-side and calls come back over the
socket. "Use the actual function" inside the sandbox therefore means *in-process
execution*, which deletes that boundary — a posture change gated behind the C1
hardening path, not a v1 refactor.

Two consequences, one for now and one for later:

1. **The named functions ARE the surface — and customization is plain Python.**
   No generic `call(name, **kwargs)` entry: a string dispatcher would split the
   surface into two styles (`read(path)` vs `call("read", path=…)`) and break
   first-class function semantics — you cannot `functools.partial(read, …)`,
   decorate it, `inspect.signature(read)`, or pass it to a higher-order helper on
   a string. Customization wants function objects, not an indirection. New tools
   are handled by regeneration, not by a fallback route: add a tool → re-run the
   sync script → the checked-in module gains the named wrapper (parity test
   enforces). The agent authors against real callables with real signatures,
   docstrings, and defaults:

   ```python
   def batch_read(paths):                  # the agent's own method
       return [read(p) for p in paths]
   ```

   `_call(name, **kwargs)` remains only as the *private transport* inside the
   stub (the name travels over the socket server-side; dispatch is a registry
   dict lookup + role filter, never an `if/elif` switcher) — it is the
   implementation, not the model-facing contract.

2. **In-process mode (`invoke.execution: subprocess | inprocess`, default
   subprocess)** is the literal endpoint of "use the actual function": the
   snippet runs as an async task on the runtime's loop, `harness_tools.<name>`
   binds the real function object with a live `ctx`, and the agent gets genuine
   composition (`inspect.signature`, `functools.wraps`, decorators, `partial`).
   Gated: a busy snippet blocks the whole loop, timeout needs cooperative
   interruption instead of a process-group kill, and there is no crash isolation —
   the C1-sandbox companion, not a v1 default.

The authoring goal itself ("the agent writes its own calls and methods") is two
things: in-snippet composition (possible today — the snippet is Python) and
**persisted self-authored methods** (the proposal §3 procedural-skill pipeline:
a validated routine persists as a skill). Neither the wrappers nor the dispatcher
gate it; `call` + real docs + result-paging already give the full authoring
surface.

## Context contract: only the returned ToolResult enters context

Today "only what the code PRINTS enters context" — an unconstrained channel (the
model can dump any payload, and the stdout caps exist to bound the damage).
Replace it with an **outcome contract**: every tool call is a segment
`result = tool_call(args)` returning a `ToolResult`, and only the **final
returned** `ToolResult` enters the agent's context.

- **Bridge calls return objects, not strings.** The stub's `_call` yields a
  `ToolResult` (`content`, `result_id`, `summary`) — a lightweight class mirrored
  in the stub module; the parent rehydrates it server-side. Code:
  `r = read(path); "TODO" in r.content` — intermediate payloads stay in-process,
  full-sized, in the model's hands; it chooses what to carry forward.
- **Real return semantics.** The snippet runs wrapped as a function
  (`def _main(): <user code>`), so the final statement can be
  `return result` — no printed marker, no stdout parsing. The wrapper serializes
  the returned `ToolResult` over the socket; the parent deserializes it.
- **Terminal intent = a returned terminal `ToolResult`.**
  `return harness_tools.report(summary, …, technical_summary=…)` replaces the
  `print(harness_tools.report(…))` marker hack — same `ctx.report` terminal path,
  cleaner contract. `escalate`/`fail` likewise; printed markers stay recognized as
  a back-compat fallback.
- **Context insertion = progressive disclosure.** The parent renders the returned
  `ToolResult` like an `ArtifactView` (headline/summary/technical/full) and caches
  the body behind a `# result:` handle — reusing the harness's existing shapes
  (`ToolResult`, `ArtifactView`, `ReportPayload`). No new schema.
- **Prints are debug, not context.** Demoted to trace, surfaced to the model only
  on the error path (or `invoke.include_stdout`); the stdout caps now bound debug
  noise rather than the result channel. Context pollution from an `invoke` turn is
  impossible by construction: the model must compose a result, not spill one.

Cost: the model loses ad-hoc print communication (it accumulates findings in
variables and returns a composed result — the discipline the contract enforces);
top-level `return` means the invoke description must state the function contract;
an uncaught exception produces the failure result as today (trace instead of a
returned `ToolResult`).

## Self & scoped capability tokens for delegation (follow-up, not v1)

What a "self object passed to tools and delegated agents" can mean, evaluated:

- **To tools: already exists.** `ToolContext` is the narrow capability façade
  every tool receives — the "self", bound server-side. In the sandbox, adding an
  OO `self.read(...)` layer is a rendering of the named-function surface, not a
  new capability — rejected (same reason `call` was).
- **To delegated agents: genuinely new, in one form only — an opaque, scoped
  capability token, never the live agent.** Passing the live self would break
  actor encapsulation (children know only parent + children + task), fresh-context
  economics (delegation's point is a clean slate; state is artifact-driven), and
  runtime-owns-graph (`Runtime.delegate` force-sets `parent_id`; caller-supplied
  identity is untrusted). A token grants **actions, never state** — no message
  buffer, no live context, no task-graph reach cross the boundary.

The split that makes it work **in `invoke` code**: flat functions stay the data
capabilities (`read`, `grep`, `webfetch`, …); **lifecycle + communication become
methods on an agent handle**, because that is where identity actually matters.

```python
from harness_tools import agent, read, grep   # capabilities stay flat functions

self = agent()                                 # the invoking agent's handle

# -- parent delegation: mint an explicit, auditable grant; delegate carries it --
probe = self.grant(
    ask=True, questions=3,                     # child may ask the parent, count-capped
    progress=True,                             # ...push progress notes
    read=["artifacts:ab12"],                   # ...read scoped artifacts only
)
child_id = self.delegate(
    description="Audit the widget lifecycle in src/widgets/",
    intent="Find correctness risks, do not fix",
    end_state="A findings list with confidence per finding",
    constraints=["Do not modify files"],
    authority="Adapt the plan within the intent",
    grants={"probe": probe},                   # capability by value in the brief
)
```

Why an explicit `grant()` mint + `delegate(grants=...)` instead of inline
`grants=` flags: the brief is the mission-command description
(intent/end-state/constraints/authority); the grant is a **boundary decision**
(the same boundary `ChannelPolicy` owns for topics). Minting is auditable,
tokens are reusable across delegates, and re-instantiating a delegate with the
same grant stays one line. In code-as-action the extra call is free (it is code,
not a tool-call turn).

```python
# -- child communication: the child NEVER addresses the parent by id.
#    The runtime binds the granted token as `self.parent` at delegate time —
#    id is ambient; the token is the explicit, enforceable edge. --
from harness_tools import agent
self = agent()
self.parent.report_progress("Phase 1 done: 3 risky flows in widgets/")
sig = self.parent.read_artifact("ab12", level="technical")   # only if read granted
if answer := self.parent.ask("Widen the grep to tests/?", timeout=80):
    ...

# -- transitive narrowing: the child passes a NARROWER token down. --
sub = self.parent.narrow(ask=False, progress=True)           # grandchild reaches
self.delegate(description="...", grants={"line": sub})        # the parent only via me

# -- terminal intent composes with the outcome contract. --
return self.report(summary="...", technical_summary="...")
```

Notes on the sketch:

- **Enforcement table (server-side).** The runtime keeps
  `token_id → (issuer, holder, actions, scope, counts/expiry)`; every token-routed
  call checks holder == caller, action granted, scope/count respected; `narrow()`
  is a subset check against the holder's own grant. Same shape as the comms
  audit trail (`comms.jsonl` verdicts).
- **Comms-topology interplay.** When `communication.topology` is active,
  token-routed child→parent messages still pass the backend `route_message`
  verdict — grants decide *whether*, topology decides *how* (direct edge vs
  relay through the parent). The parent is a legal hierarchy edge in every
  topology, so child→parent token traffic is topology-safe by construction. The
  token is the capability-by-reference answer to the topologies' capability-
  by-config.
- **The `ask` naming collision.** The tool-level `ask` asks the *operator*; the
  token `self.parent.ask(...)` asks the *parent* (count-capped). Both can live
  side by side; the docstrings must say which.
- **Invariants preserved.** No state crosses (fresh contexts stay fresh), the
  runtime still owns the graph, the actor rule holds (the token IS the explicit
  parent edge), and the v1 sandbox surface stays a module of flat functions.

This is its own design space (a delegation/capability follow-up, not the stub
work) — sketched here so the shape is on record, deliberately out of v1.

## Drift verification (the load-bearing piece)

Because the file is checked in, drift is prevented the same way the generated
registers are: a **parity test** re-derives the module from the live registry
and fails unless the checked-in file matches (signature param-sets, defaults,
docstring bodies vs `ToolDef.description`). The update path is: add/change a
tool → run the sync script → the file, the catalog, and `help()` all follow;
forget the sync → CI fails fast instead of the agent silently learning a stale
API.

## Open questions / next steps

- Where the bundled file lives (`src/dynamic_harness/core/tools/_harness_tools.py`
  as package data vs a `docs/`-adjacent location) and whether invoke copies it or
  points `PYTHONPATH` at its directory.
- Landing order: write the sync script + checked-in file + parity test, add the
  read-only root, add the generic `call(name, **kwargs)` entry, switch bridge
  calls to return `ToolResult` objects with function-wrap `return` semantics
  (terminal intent via returned terminal results), then drop the `_STUB_SOURCE`
  string constant and demote prints to trace.
- Later: `invoke.execution: inprocess` mode with real function binding + live
  `ctx` (gated behind the C1 hardening decision); procedural-skill persistence
  (proposal §3) as the home for agent-authored methods; capability tokens for
  parent→child back-channels (`self.grant` / `self.parent.*` / `narrow()`, per
  the section above) as a delegation follow-up.
- Keep `docs()`/`help()` output within the existing stdout cap (already bounded).

## Related

- [proposal.md](proposal.md) §2 — the `harness_tools` RPC stub spec this sharpens
- `core/tools/code.py` — `_STUB_SOURCE` (becomes the checked-in file), `_serve_harness_tools`, `invoke`
- `core/tools/filesystem.py` — `_read_only_roots` / `SandboxPolicy` (readability wiring)
- `core/tools/registry.py` — `ToolDef` / `openai_schemas()` (the JSON alternative)
- [benefits-and-costs.md](benefits-and-costs.md) — Hermes' generated
  `hermes_tools.py` (same generate-from-registry pattern, docstrings included)
- [context-management-improvement.md](context-management-improvement.md) — the
  progressive-disclosure principles this mirrors
