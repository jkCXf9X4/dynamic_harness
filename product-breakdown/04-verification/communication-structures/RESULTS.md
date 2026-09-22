# Communication comparison — real-LLM run

- When: `2026-09-18 12:25 UTC`
- Model: `deepseek/deepseek-v4-flash-0731`
- Base: `https://openrouter.ai/api/v1`
- Cells: 3 · Task modes: interdependent · Replicates: 1
- Runs: 3 · Total cost: $0.0000

## Per-cell summary (mean over tasks × replicates)

| cell | runs | pass | correct | tokens | prompt | turns | msgs | agents | depth | fail | esc | latency s |
|------|-----:|-----:|--------:|-------:|-------:|------:|-----:|-------:|------:|-----:|----:|----------:|
| off | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 900.0 |
| shared | 1 | 1 | 1 | 799955 | 781831 | 40 | 32 | 7 | 1 | 0 | 0 | 389.3 |
| topics_parent | 1 | 1 | 1 | 5219622 | 5126789 | 232 | 36 | 6 | 1 | 0 | 0 | 764.5 |

## Per-run detail

| cell | task | rep | status | correct | tokens | cost $ | turns | note |
|------|------|----:|--------|--------:|-------:|-------:|------:|------|
| off | collab_interdependent | 0 | timed_out | None | 0 | 0.0000 | 0 | hit 900s watchdog (possible converse deadlock) |
| shared | collab_interdependent | 0 | completed | True | 799955 | 0.0000 | 40 | collab (interdependent) matches all 4 parts |
| topics_parent | collab_interdependent | 0 | completed | True | 5219622 | 0.0000 | 232 | collab (interdependent) matches all 4 parts |
