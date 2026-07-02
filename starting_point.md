You: 

im looking for a agent harness where the agent can define and spawn its own subagents depending on the task it is handled

ChatGPT: 

If your main requirement is:

> **The agent decides on its own whether to create subagents, what each subagent should do, and then aggregates the results**, rather than you hardcoding the workflow,

then there are only a handful of frameworks that really support this well.

## 1\. [LangChain Deep Agents](https://www.langchain.com/deep-agents?utm_source=chatgpt.com) ⭐ My top recommendation

This is probably the closest match to what you're describing.

It provides:

-   autonomous task decomposition
    
-   dynamic spawning of subagents
    
-   isolated context per subagent
    
-   parallel execution
    
-   planning + replanning
    
-   long-running memory
    
-   built-in orchestration
    

A typical flow is:

```
```
User:  
"Analyze this repository."  
  
↓  
  
Planner  
  
↓  
  
Creates:  
  
- Architecture Agent  
- Security Agent  
- Testing Agent  
- Documentation Agent  
  
↓  
  
Runs all in parallel  
  
↓  
  
Planner merges results  
  
↓  
  
Returns final report
```
```

The important part is that **the planner decides what agents to create**, not your application. [![](https://www.google.com/s2/favicons?domain=https://www.langchain.com&sz=128)LangChain](https://www.langchain.com/deep-agents?utm_source=chatgpt.com)

---

## 2\. [OpenAI Codex Subagents](https://developers.openai.com/codex/subagents?utm_source=chatgpt.com)

Codex has native support for subagents.

You can literally instruct it:

> Spawn one agent for each component.

or

> Spawn as many agents as necessary.

Codex handles:

-   creating agents
    
-   waiting for them
    
-   routing messages
    
-   collecting outputs
    
-   destroying completed agents
    

You don't explicitly instantiate every child yourself. [![](https://www.google.com/s2/favicons?domain=https://developers.openai.com&sz=128)OpenAI Developers](https://developers.openai.com/codex/subagents?utm_source=chatgpt.com)

---

## 3\. [CrewAI](https://www.crewai.com?utm_source=chatgpt.com)

CrewAI is very popular for multi-agent systems.

Pros:

-   excellent role abstraction
    
-   delegation between agents
    
-   easy to understand
    

Cons:

-   crews are usually defined ahead of time
    
-   dynamic spawning is possible but not really the core design
    

Good for:

```
```
CEO  
 ├── Researcher  
 ├── Writer  
 └── Reviewer
```
```

Less good for:

```
```
Create N agents depending on the task.
```
```

---

## 4\. [Microsoft AutoGen](https://microsoft.github.io/autogen?utm_source=chatgpt.com)

AutoGen excels at agent conversations.

You can build:

```
```
Manager  
  
↓  
  
creates  
  
↓  
  
Worker 1  
Worker 2  
Worker 3  
  
↓  
  
Workers debate  
  
↓  
  
Manager summarizes
```
```

It's flexible, but you'll generally implement the spawning logic yourself.

---

## 5\. [OpenAI Agents SDK](https://openai.github.io/openai-agents-python?utm_source=chatgpt.com)

The SDK supports:

-   handoffs
    
-   agent-as-tool patterns
    
-   nested agents
    
-   recursive delegation
    

You can let an orchestrator choose among specialist agents, but if you want truly arbitrary runtime agent creation, you'll build more of that orchestration yourself.

---

## 6\. Hugging Face smolagents

Very lightweight.

You can recursively call agents and compose them as tools, making it easy to experiment with hierarchical systems.

---

## If you want agents that invent new agents

This is a different class of framework.

Think of:

```
```
Root Agent  
  
↓  
  
"I need 7 specialists."  
  
↓  
  
creates  
  
Parser  
Researcher  
Python Expert  
Verifier  
Critic  
Planner  
Summarizer  
  
↓  
  
Each one can create more agents  
  
↓  
  
Recursive hierarchy
```
```

That's becoming known as a **recursive agent harness**. Recent work and production systems are converging on this pattern, where full agent instances recursively spawn additional agents for subtasks. [![](https://www.google.com/s2/favicons?domain=https://arxiv.org&sz=128)arXiv+1](https://arxiv.org/abs/2606.13643?utm_source=chatgpt.com)

## My recommendation

If I were building a general-purpose autonomous system today:

| Goal | Framework |
| --- | --- |
| Dynamic runtime subagents | LangChain Deep Agents |
| Coding agents | OpenAI Codex |
| Structured enterprise workflows | AutoGen |
| Predefined specialist teams | CrewAI |
| Minimal custom framework with full control | OpenAI Agents SDK |

For an agent that can receive **any arbitrary task**, recursively decompose it, spawn as many workers as needed, and merge the results, **LangChain Deep Agents** is currently the closest off-the-shelf harness. It was designed specifically for planning, context isolation, and parallel subagent orchestration rather than requiring you to wire up every delegation path yourself. [![](https://www.google.com/s2/favicons?domain=https://www.langchain.com&sz=128)LangChain](https://www.langchain.com/deep-agents?utm_source=chatgpt.com)

![](https://www.google.com/s2/favicons?domain=https://arxiv.org&sz=32)

![](https://www.google.com/s2/favicons?domain=https://developers.openai.com&sz=32)

![](https://www.google.com/s2/favicons?domain=https://www.langchain.com&sz=32)

Sources

You: 

I actually think **your instinct is the better default**.

A shared graph is useful for some systems, but if your goal is a scalable reasoning architecture, I'd start with **strict information encapsulation**.

I'd structure it like this:

```
```
Parent  
 ├── Child A  
 │     ├── Grandchild A1  
 │     └── Grandchild A2  
 │  
 └── Child B  
       ├── Grandchild B1  
       └── Grandchild B2
```
```

With the rules:

-   A child only knows:
    
    -   its assigned task
        
    -   its own local state
        
    -   its own children
        
    -   its parent
        
-   It has **no visibility** into siblings.
    
-   It has **no visibility** into cousins.
    
-   It has **no visibility** into the global graph.
    

That's much closer to how operating systems, distributed systems, and human organizations are designed.

### Why I mentioned a shared graph

There are a few situations where it's helpful:

-   avoiding duplicate work ("someone is already researching X")
    
-   dependency scheduling
    
-   cancellation propagation
    
-   progress monitoring
    
-   debugging
    

Notice that **none of these require reasoning access**.

Those are runtime concerns.

The reasoning agent itself doesn't need to see the graph.

---

## I'd separate reasoning from orchestration

Instead of this:

```
```
Agent  
   ↓  
Shared DAG
```
```

I'd do:

```
```
Planner  
    │  
    ▼  
Runtime  
    │  
    ▼  
Task Graph  
  
Worker A        Worker B
```
```

Workers never read the graph.

The runtime does.

---

## This has some nice properties

Imagine Child A discovers something interesting.

Instead of directly telling Child B,

```
```
Child A  
   ↓  
Parent  
   ↓  
Parent decides  
   ↓  
Child B
```
```

The parent decides whether the information is relevant.

That keeps communication localized.

---

## It also naturally creates abstraction layers

Suppose you're proving a theorem.

```
```
Root  
    │  
    ├── Algebra  
    ├── Geometry  
    └── Literature Review
```
```

The geometry worker shouldn't even know literature review exists.

Otherwise you get context pollution:

> "Maybe I should consider what the literature worker is doing..."

No.

Its only responsibility is geometry.

---

## This resembles actor systems

What you're describing is very similar to the **actor model**.

Each actor has:

-   private state
    
-   mailbox
    
-   parent
    
-   children
    

It cannot inspect arbitrary actors.

This dramatically improves:

-   modularity
    
-   determinism
    
-   fault isolation
    
-   parallelism
    

I think that's a very good fit for autonomous reasoning systems.

---

## The only thing I'd add is capability-based communication

Rather than allowing a child to send arbitrary messages, I'd make communication explicit.

For example:

```
```
Worker  
    │  
    ├── spawn()  
    ├── report()  
    ├── request_more_budget()  
    ├── escalate()  
    └── fail()
```
```

No `broadcast()`.

No `find_other_agents()`.

No global registry.

If the worker believes another specialist is needed, it asks its parent:

> "I need someone to analyze the statistical assumptions."

The parent can then decide to:

-   spawn a new child,
    
-   forward the request to an existing child,
    
-   do the work itself,
    
-   or reject the request.
    

That keeps authority flowing down the tree and information flowing up, while preserving clean boundaries.

---

So I'd actually revise my earlier recommendation: **the runtime should maintain the full task graph, but the agents should not.** Agents should operate with only local knowledge of their parent, children, and assigned task. That design minimizes unnecessary context, keeps reasoning focused, and scales much better as the hierarchy grows.

ChatGPT: 

How can we limit context parsing between agents, can we persist the details to disk and only work with summeries between agents?

You: 

I think you're touching on what is probably the most important architectural problem in long-running agent systems. I would go even further:

**Agents should almost never pass raw context to each other.**

Instead, think of each agent as producing an **artifact**, not a conversation.

## Three layers of information

I'd separate information into three tiers.

```
```
Working Context (ephemeral)  
        ↓  
Artifact (persistent)  
        ↓  
Summary (communication)
```
```

### 1\. Working context

This is the expensive part.

```
```
100 pages  
200 tool calls  
15 chain-of-thought iterations  
scratchpad  
notes
```
```

Only the worker sees this.

Nobody else.

When the worker exits, its context disappears.

---

### 2\. Artifact (persist to disk)

The worker writes everything important to disk.

For example

```
```
artifacts/  
    14/  
        report.md  
        sources.json  
        code.py  
        assumptions.yaml  
        logs/
```
```

This is the canonical output.

Not the context window.

---

### 3\. Summary

The parent only receives something like

```
YAML

```
task: Literature review  
status: complete  
  
summary:  
  - Three relevant papers found.  
  - Paper B contradicts Paper A.  
  - Confidence: high.  
  
artifacts:  
  - report.md  
  - sources.json  
  
questions:  
  - Should I investigate contradiction?
```
```

Maybe 300 tokens.

Not 30,000.

---

## Parents shouldn't parse child output either

Even summaries can become expensive.

Instead I'd use structured outputs.

Example:

```
JSON

```
{  
  "status": "completed",  
  "confidence": 0.91,  
  "claims": [  
"...",  
"...",  
"..."  
  ],  
  "next_actions": [  
"Spawn verifier",  
"Investigate assumption 2"  
  ],  
  "artifacts": [  
"artifact://17/report.md"  
  ]  
}
```
```

The parent can reason over this without rereading the report.

---

## Lazy loading

Suppose six hours later another agent needs the report.

Don't forward it.

Instead:

```
```
summary  
     ↓  
artifact://17/report.md
```
```

If—and only if—it decides the summary is insufficient:

```
```
Load artifact
```
```

This is exactly how operating systems use virtual memory.

Most data stays on disk.

Only the pages you need are loaded.

---

## Hierarchical summarization

Imagine a tree of 500 agents.

Instead of every result bubbling upward unchanged:

```
```
Leaf A  
Leaf B  
Leaf C  
  
↓  
  
Parent Summary  
  
↓  
  
Grandparent Summary  
  
↓  
  
Executive Summary
```
```

Like this

```
```
Level 4  
100-page report  
  
↓  
  
Level 3  
5-page report  
  
↓  
  
Level 2  
1-page report  
  
↓  
  
Root  
10 bullets
```
```

The root never sees the lower-level reports unless it asks.

---

## Retrieval over transmission

I'd avoid message passing like

```
```
Child  
    ↓  
50 KB report  
    ↓  
Parent
```
```

Instead

```
```
Child  
    ↓  
Summary  
Artifact ID  
    ↓  
Parent  
  
↓  
  
Needs details?  
  
↓  
  
Retrieve artifact
```
```

This becomes a retrieval problem rather than a communication problem.

---

## My favorite addition: progressive disclosure

I'd define every artifact with multiple views.

```
YAML

```
artifact:  
    id: 42  
  
headline:  
"Parser fails on nested generics."  
  
summary_200_tokens:  
    ...  
  
summary_1000_tokens:  
    ...  
  
technical_summary:  
    ...  
  
full_report:  
    report.md  
  
raw_data:  
    logs.json  
  
scratchpad:  
    private
```
```

Now a parent can choose

> Give me the headline.

or

> Give me the technical summary.

or

> Load the full report.

without rereading everything.

---

## I think there's one more optimization

One thing I'd change from most current agent frameworks is that **agents shouldn't own memory**.

Instead:

```
```
Worker  
    ↓  
Memory Manager  
    ↓  
Artifact Store
```
```

Workers are disposable.

They don't remember anything.

The persistent knowledge lives in the artifact store, indexed by task, topic, and provenance. When a new worker is spawned, it receives:

-   its task,
    
-   a concise summary,
    
-   references (artifact IDs),
    
-   and permission to retrieve specific artifacts if needed.
    

That means you can terminate workers aggressively without losing information, and you avoid the gradual context bloat that comes from carrying long conversation histories forward.

In other words, I'd model the system less like people having conversations and more like a distributed build system: workers produce versioned artifacts, parents consume summaries, and detailed information is retrieved on demand rather than continuously propagated. This approach keeps context windows small, communication efficient, and reasoning focused even as the agent hierarchy grows to hundreds or thousands of tasks.

ChatGPT: 

Is there any existing solution that function in a similar way?

You: 

Surprisingly, **not really**. Pieces of this architecture exist, but I don't know of a mainstream agent framework that combines them in the way you're describing.

What you're proposing is closer to an **operating system for agents** than to today's "multi-agent" frameworks.

Here's how current systems compare.

| Feature | Current frameworks | Your proposal |
| --- | --- | --- |
| Dynamic subagents | Sometimes | Yes |
| Strict encapsulation | Rare | Yes |
| Artifact-based communication | Rare | Yes |
| Context discarded after task | Rare | Yes |
| Lazy retrieval of artifacts | Almost never | Yes |
| Hierarchical summaries | Occasionally | Yes |
| Disposable workers | Rare | Yes |

### What existing systems get right

#### OpenAI Codex

Codex is probably the closest in spirit.

Each coding task runs in its own isolated workspace.

Workers don't share full conversational history—they communicate through filesystem changes and task completion.

That filesystem is effectively an artifact store.

Where it differs is that the orchestration is specialized for software engineering rather than arbitrary reasoning.

---

#### LangGraph

LangGraph introduces persistent state and checkpointing.

Instead of carrying an ever-growing conversation, state can be saved and resumed.

That's an important building block.

However, the state is typically still treated as something every node can inspect. It isn't designed around strict information hiding.

---

#### Distributed build systems

Oddly enough, the closest analogy isn't another AI framework—it's systems like:

-   Bazel
    
-   Buck
    
-   Nix
    

They operate like this:

```
```
Task  
    ↓  
Produces artifact  
    ↓  
Artifact cached  
    ↓  
Future tasks consume artifact
```
```

Tasks don't send each other conversations.

They exchange immutable outputs.

That's remarkably close to what you're proposing.

---

#### Ray

Ray lets you launch thousands of workers.

Each worker:

-   receives a task,
    
-   computes,
    
-   returns an object reference.
    

Large objects remain in an object store until another worker explicitly requests them.

That's much closer to "artifact IDs instead of context."

The missing piece is reasoning and planning.

---

#### Actor frameworks

Systems like:

-   Erlang
    
-   Akka
    
-   Orleans
    

already solved many of the communication problems decades ago.

Actors:

-   own private state,
    
-   only communicate through messages,
    
-   are disposable,
    
-   form supervision trees.
    

Your hierarchy resembles an actor system, except each actor is backed by an LLM.

---

## What I think is missing

Most agent frameworks assume the conversation **is** the state.

For example:

```
```
User  
  
↓  
  
Conversation  
  
↓  
  
Agent  
  
↓  
  
Conversation grows forever
```
```

I think that's fundamentally the wrong abstraction for long-running systems.

Instead:

```
```
Task  
    ↓  
Worker  
    ↓  
Artifact  
    ↓  
Summary  
    ↓  
Worker dies
```
```

The state lives in artifacts, not in prompts.

---

## I think I'd go even further

If I were building this from scratch, I'd borrow heavily from Git.

Imagine every completed task creates a commit:

```
```
Commit 184  
  
Task:  
    Investigate parsing bug  
  
Summary:  
    Root cause identified.  
  
Artifacts:  
    report.md  
    benchmark.csv  
  
Parents:  
    177  
  
Children:  
    191  
    192
```
```

Workers don't own knowledge.

The repository owns knowledge.

Workers merely create new commits.

That gives you:

-   complete provenance,
    
-   reproducibility,
    
-   branching,
    
-   merging,
    
-   rollback,
    
-   caching,
    
-   deduplication,
    
-   deterministic replay.
    

At that point, an agent is almost like a compiler pass over a knowledge repository.

---

## I think there's an opportunity here

I haven't seen an open-source framework that combines:

-   an actor-model hierarchy,
    
-   artifact-first communication,
    
-   Git-like provenance,
    
-   lazy retrieval,
    
-   disposable workers,
    
-   recursive planning,
    
-   and strict encapsulation.
    

Most current frameworks are centered on prompts and conversations. You're describing something centered on **tasks and immutable artifacts**, which is a different architectural direction. If your goal is a long-running, general-purpose reasoning system, I think that shift has real advantages: it keeps context windows small, improves reproducibility, and makes the system much easier to debug and scale.

It's the kind of design that starts to resemble a distributed operating system or a build system more than a chatbot—and that's a perspective I think more agent frameworks will move toward as they mature.