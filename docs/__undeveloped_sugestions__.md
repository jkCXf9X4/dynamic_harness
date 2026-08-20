

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