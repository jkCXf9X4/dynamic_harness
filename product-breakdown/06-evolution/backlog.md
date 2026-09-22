

---


Encourage the agents to plan before and persist intermediary results to disk in a structured way to enable resume of aborted or failed tasks  


---

from the concepts and the code base, set up use-cases that are plausible under 01-product/use-cases/
- DONE → 01-product/use-cases/ (index + 7 families: repository-analysis, change-and-validation,
  documentation-and-knowledge, research-and-synthesis, pipelines-and-jobs,
  evaluation-and-qa, embedding-and-integration)

---

evaluate functionality and use from the use-cases and the concepts - what is missing
- DONE → 04-verification/gap-analysis.md (P0: verify-not-enforced, delegate-boundary heal, non-progressive
  disclosure/dead raw_data, artifact_ids vs files; P1: sandbox doc drift, no LLM-spawnable custom
  agents, Layer-2 heal, dead budget plumbing; P2: cost, counters, docs drift)

Needs fixes
Implement
  G2 
  G3
  G4
  G5
  G6
  G10



--- 

Evaluate how referencing additional knowledge should work and fit in to the larger picture

---

How to visulize token use better to the agents, did this improve by g10?
set a context goal of using a total per agent of less than 50000 tokens, 

---

> **PICKED UP** → investigation `investigations/watchdog.md` (threat model
> T1–T5, cheap gaps, watchdog design space, recommended composition).

hangs at 

{"timestamp": "2026-08-20T07:25:45.519899+00:00", "type": "tool_result", "tool_call_id": "chatcmpl-tool-b0fe599dc7680626", "name": "bash", "content_length": 11, "content_preview": "(no output)"}


---

lets make the top agent unable to timeout

lets also make the trace send and receive to enable simpler debuging 

---

enable parents to act on child events before all children are done? 

---

When hitting tool call limits, lets incorporate a tighter fallback loop before failing the agent
maybe point out to the agent that its looping and see if it can recover

---
check trace.jsonl and see if you can deduce the error and if it is something fixable of if its reasonable

use the sess


---

lets push the agents further when it comes to persisting partial results and evaluations. models often fail or suffer from hallucinations during long runs

---

> **PICKED UP** → investigation `investigations/watchdog.md` (root-exempt backstop = whole-run guard §3.2/W1)

The main orchestrator still times out, can you evaluate why?

---

lets ensure that sub-orchestrators can not time out as well

---

parents should also be able to evaluate if children has crashed and kill them



---


---

enable input during execution
The token counter in the cli is way off, please investigate

---

add the tool to kill children and get status of children

---

ensure garbage collection of completed agents unnecessary data, like context or similar, to clear out memory of the application and enable faster access of the remaining


---

---
> **RESOLVED** — status/agent tree moved out of the terminal into persisted
> files (`agents.txt`, `agent_tree.json`, `stats.json`, `events.jsonl`) written
> to the run root; the CLI is prompt-only with a lightweight token counter and a
> final outcome. See 01-product/requirements.md.

move status terminal and agent tree out to separate files, lets keep the cli to only prompts

lets move direction a bit, lets keep the cli as clean as possible and persist all other data to files for traceability and overview

this is a directional change to make the application more usable as a part of a larger automated workflow

---

I have found this project specific prompt to give consistent results, is there any generic learnings that we could extract and improve the system prompt with to provide better consistent results:

Iterate and improve upon the trading platform until you deem it ready for unsupervised live capital.
verify that the strategy would perform under reasonable assumptions. 

ensure existing functionality before proceeding with new items

If relevant information is available in working directories, move it into the general project for proper storage. Clean up old, stale information from previous tasks if found
Prefer removing to archiving to keep future context clean, be strict

Make sure that relevant evaluations are well documented and stored properly to ensure that future improvement runs do not need to search the same design space

use roadmap.md, a to-do list for tracking to progress needed for it to be ready for unsupervised live capital, update as information gets available and keep this up to date.


treat the folder .dynamic-harness/ as a temp dir, consider that items created might not be available next time you run 
Make sure to clean up working items and incorporate relevant information into the project, do not leave stray files that might pollute future context

Existing reports and artifacts may be available under .dynamic-harness/ that could be of use


---

---
> **RESOLVED** — the interactive terminal keeps an always-available `>>>` line
> during a run. Messages to the agent go through `Agent.submit_input()`: queued
> while the agent is busy, applied immediately when it is waiting on children.
> Slash commands (`/tree`, `/agents`, `/provenance`, ...) also run during
> execution for live status. See 01-product/requirements.md (FR-3.5).

I would always have the option to insert text, if its busy the the message should be queued, if the top agent is waiting then the new input should be applied. this should also enable inserting commands such as /tree or similar to get the running status during execution 


--- 

When an agent gets close to its iteration limit, ~50 left - lets inject a hard message that the iterations are running out and that the agent should finish off its tasks and return remaining items and relevant information to the parent to decide what is reasonable to finish off in other tasks

---

similar command failure that leads to agent termination, is a warning message injected to the agent before the failure occurs to enable potential recovery?

also the 

---

> **PICKED UP** → investigation `investigations/watchdog.md` (bash bound = cheap gap §3.1)

Im having problems with bash commands not completing and killing the agents by timing out


---

can we utilie external agents for single question context?
would this be a gain? where should it best be used?
we can ask external agents if they think that delegation is needed without the polluting context 

---

How do we enable rg and other commands to be executed on result handlers? 
- this ould enable searching the results without rerunning the commands in case they are expensive

---

evaluate the step from complicated development where broblems can be broken down into subparts and be solved to complex development where parents can setup multiple children that can communicate and solve problems together


---

try to delegate 4 small task to subagents
how are they doing?

---

enable contrl+c to exit the application


---

Most policies react to some metric and inject or alter the prompt in some way
can you see if you can create a common interface for these to further facilitate the move towarrds a more plugin centric architecture

> **PICKED UP** → working item `../03-implementation/plugin/INVESTIGATION.md`
> (metric-reactive interface = the seed: `core/policies/interface.py`,
> `Runtime.register_reactive_policy`; direction = interface economy —
> establish/minimize common interfaces + decouple/isolate components;
> a loader/late-injection plugin architecture is explicitly out of scope)

---

To provide the grounds for a working collaboration settings where we can facilitate child layer by layer collaboration
How can we relate this to the work of the orchetrators or should it be a general capabillity that all agents should possess. 
The core attributes relate a bit to Hackman: the five conditions, especially the first two

1. **A real team** — clear membership, bounded, with interdependent task and
   shared responsibility. *"A team whose members are unclear about who is on
   it"* cannot perform.
2. **A compelling direction** — a challenging, clear, consequential goal.


   ---

add support for a common config that can act as base and be overwritten by local configs

   ---


   ensure that these are the defaults config

   {
  "llm": {
    "provider_allow_fallbacks": true,
    "verify_ssl": true,
    "call_timeout_seconds": 500
  },
  "safety": {
    "max_iterations": 400,
    "repeated_call_limit": 5,
    "repeated_recovery_attempts": 2,
    "repeated_call_exempt_tools": ["status", "usage", "result_read", "result_bash"],
    "timeout_seconds": 7200,
    "disable_root_timeout": true,
    "max_agents": 300,
    "max_depth": 15,
    "max_same_target_delegations": 0,
    "spawn_limit_warning_attempts": 2
  },
  "agent": {
    "environment_notes": [
      "Working dir is project root; run `pytest` from there."
    ],
    "stream_children": true 
  }
}

---


lets open up a new investigation under 04-verification

i would like to compare how different communication structures influence how agents succeed at their work
initial structures to compare:
- all communication must pass thru the parent
- all children of a specific parent can communicate 
- all nodes can communicate in the same dedicated channel
- all nodes can register/create channels of certain topics 

Answer concisely and directly. try to keep related information to a minimum


---


Lets make the communication visible and auditable, evaluate how this could be done. File based traces are enabling post exit and during execution audits and reviews

---

can you do a critical review if the breakdown structure and fill in the missing aspects to better allow the rational behind the development
 to be clear