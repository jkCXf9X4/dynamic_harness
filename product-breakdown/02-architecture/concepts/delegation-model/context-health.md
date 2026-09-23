# Context Health Monitoring

The agent loop includes a Context Observation before each turn:

```
[Context Observation]
Turn: 7
Messages in context: 21
Estimated prompt tokens this agent: 12000
Your task: Audit the auth module...
```

Decision rules:

| Condition | Action |
|-----------|--------|
| <5 turns, <15 messages | Healthy — continue or delegate |
| 5–15 turns, growing messages | Delegate sub-agents for remaining work |
| >15 turns or >50 messages | Call `compress()` immediately |
