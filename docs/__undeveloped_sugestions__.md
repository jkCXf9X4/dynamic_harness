

---


Encourage the agents to plan before and persist intermediary results to disk in a structured way to enable resume of aborted or failed tasks  


---

from the concepts and the code base, set up use-cases that are plausible under docs/
- DONE → docs/use-cases/ (index + 7 families: repository-analysis, change-and-validation,
  documentation-and-knowledge, research-and-synthesis, pipelines-and-jobs,
  evaluation-and-qa, embedding-and-integration)

---

evaluate functionality and use from the use-cases and the concepts - what is missing
- DONE → docs/gap-analysis.md (P0: verify-not-enforced, delegate-boundary heal, non-progressive
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

use docs/roadmap/LIVE_CAPITAL_READINESS.md, a to-do list for tracking to progress needed for it to be ready for unsupervised live capital, update as information gets available and keep this up to date.


treat the folder .dynamic-harness/ as a temp dir, consider that items created might not be available next time you run 
Make sure to clean up working items and incorporate relevant information into the project, do not leave stray files that might pollute future context

Existing reports and artifacts may be available under .dynamic-harness/ that could be of use