# Collaboration Setting — Lifecycle and State Transitions

Section 4 of the collaboration-setting spec. Index: [README.md](README.md).

```
FORMING                       founder spawns children with team.label
   │  founder: team_charter(objective, why, acceptance)
   ▼
ACTIVE                        members work in workspace; founder absent
   │
   ├── unresolved dispute escalated with resolve_as=dispute
   │      ▼
   │   ARBITRATING             founder arbitrates once (exception): converse →
   │   │   ok?  ──> ACTIVE     disconnect → revise membership
   │   │            └──> DISBANDED (structural conflict)
   │   └── founder may also: assign fresh worker, dissolve + re-delegate
   │
   └── founder reports / settles / is killed
            ▼
DISBANDED                     straggler members cancelled as today; their
                              commits/artifacts survive (existing semantics)
```
