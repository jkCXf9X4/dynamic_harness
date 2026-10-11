---
title: Watchdog — design space
summary: Cheap, robust run-watchdog options for the harness runtime
---

# Watchdog — design space

Cheap, robust run-watchdog options for the harness runtime.

| Doc | Question |
|---|---|
| [watchdog.md](watchdog.md) | A cheap, robust watchdog for the harness runtime |
| [watchdog_w3_utilization.md](watchdog_w3_utilization.md) | What the monitor-thread watchdog can actually do (W3 utilization) |

## Chain status

- **Question** — present, in `INFO-194` and `INFO-195`.
- **Plan** — pending; no plan doc.
- **Findings** — present, in `INFO-194` and `INFO-195` (findings only, no code change).
- **Results** — pending; no decision record names either leaf as `state:`. Next link: file an IMP under `INFO-196` (roadmap) referencing `INFO-194` + `INFO-195`.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-194** [Investigation — a cheap, robust watchdog for the harness runtime](watchdog.md) — Investigation (findings only, no code change): threat model, current defences, three cheap gaps, W1-W5 designs, and recommended composition for a cheap, robust run-watchdog.
- **INFO-195** [Investigation — W3 utilization: what the monitor-thread watchdog can actually do](watchdog_w3_utilization.md) — Investigation (follows INFO-194; no code change): the W3 monitor-thread design surface and the concrete ways to utilize it, as a staged escalation ladder.
<!-- pb:index:end -->
