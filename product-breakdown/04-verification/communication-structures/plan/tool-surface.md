---
title: "Plan — Tool Surface"
category: investigation / plan
parent: "README.md"
---

# The tool surface — one vocabulary across all cells

Registered once in `core/tools/registration.py`; every tool is a thin wrapper over
`ToolContext` methods delegating to `runtime.comms` (the backend). No tool knows
which backend is live.

| Tool | Params | Read-only / cacheable? | Role |
|------|--------|------------------------|------|
| `channels` | *(none)* | Yes — repeated-call exempt | List known topics + your subscriptions (like `status`/`usage`) |
| `channel_info` | `topic: str` | Yes — exempt | Subscribers, last activity, creation authority |
| `post` | `topic, content, kind?, stage?` | No (mutates) | Publish to a topic; first post to a new topic triggers creation (gated by `ChannelPolicy.may_create`) |
| `channel_read` | `topic: str` | Yes — exempt | Delta read; backend-side watermark advanced on read. **Open-pull: works on any topic whether or not subscribed**. Named `channel_read` (not `read`) to avoid the filesystem collision |
| `subscribe` | `topic: str` | No (mutates routing) | Declare ongoing interest (adds to `channels` and, in push mode, the digest). Idempotent; creation/join gated by `ChannelPolicy` |
| `unsubscribe` | `topic: str` | No (mutates routing) | Stop tracking the topic (watermark/read history retained) |
| `message` | `agent_id, content, kind?` | No (mutates) | Fire-and-forget by-ID send (queued; unlike `converse` it does not wait). Backend scopes it |
| `converse` | `agent_id, message` | No (mutates) | Blocking by-ID request/response; routed through the backend when enabled |

## Subscription semantics — signal, not a gate

`subscribe`/`unsubscribe` are **routing-intent tools, not access-control tools** —
to make the push digest tractable and measure choice, not lock content away:

- **Pull stays open.** `channel_read(topic)` works on any topic the agent can
  name, subscribed or not (mirroring `read_artifact` reading any committed
  artifact). Requiring a subscription would add ceremony and skew cell 4's
  numbers toward tool friction rather than topology cost. `channel_read` alone
  sets the watermark.
- **Subscription is what the push path respects.** In digest mode only subscribed
  topics contribute to the per-turn delta; `unsubscribe` stops paying the
  push-multiplier. In pull mode it is a pure preference signal.
- **Idempotent and cheap.** Repeat `subscribe` = no-op success; no "already
  subscribed" failure. They are deliberately **not** repeated-call exempt — they
  mutate routing state, and a stuck spam-subscriber should still be caught.
- **Uniform signature, divergent effect:** cells 1/2 refuse ("no topic channels");
  cell 3 accepts as a no-op (everyone already subscribed); cell 4 makes it the
  load-bearing routing choice.

Back-compat: `converse` stays and routes through the backend when enabled (builds
a `CommsMessage`, asks the backend for the verdict, delivers the folded envelope
via `continue_with_input`, waits for the reply); default `off` keeps today's
behavior. `kind` is surfaced in tool output, never hidden. New tools join
`ORCHESTRATOR_ALLOWED_TOOLS` (`core/policies/permissions.py:34`); the three
read-only ones join the repeated-call exempt set, the five mutators join
`ResultCachePolicy.DEFAULT_NON_CACHEABLE`.
