# References and Term Mapping

Section 8 + appendix of the management-theory survey. Index:
[README.md](README.md).

## Verified online (fetched for this report)
- Netflix — *Culture Memo*, "People over Process: Context not control; Highly
  aligned, loosely coupled; Farming for dissent; Disagree and commit."
  <https://jobs.netflix.com/culture>
- Hackman interview (Diane Coutu), "Why Teams Don't Work," *HBR*, May 2009.
  <https://hbr.org/2009/05/why-teams-dont-work>
- Hamel, "First, Let's Fire All the Managers," *HBR*, Dec 2011.
  <https://hbr.org/2011/12/first-lets-fire-all-the-managers>

## Sourced by name (canonical primary or well-known secondary)
- Shannon, C. E. (1948), "A Mathematical Theory of Communication," *Bell System
  Technical Journal*.
- Coase, R. (1937), "The Nature of the Firm." / Williamson, O. E. (1975),
  *Markets and Hierarchies*.
- Simon, H. (1957), *Administrative Behavior* (bounded rationality).
- Conway, M. (1968), "How Do Committees Invent?" *Datamation*.
- Hackman, J. R. (2002), *Leading Teams*.
- McChrystal, S. (2015), *Team of Teams*.
- Wegner, D. M. (1985; transactive memory), and the TMS line of team research.
- Duhigg, C. (2016), "What Google Learned From Its Quest to Build the Perfect
  Team," *NYT Magazine* (Project Aristotle).
- Edmondson, A. (2018), *The Fearless Organization*.
- Greenleaf, R. (1970), "The Servant as Leader."
- Burt, R. (1992), *Structural Holes*.
- Granovetter, M. (1973), "The Strength of Weak Ties," *American Journal of
  Sociology*.
- Deci, E. & Ryan, R. (self-determination theory); Amabile & Kramer, "The Power
  of Small Wins," *HBR*, May 2011.
- Ancona, D. & Caldwell, D. (1992), "Bridging the Boundary," *Administrative
  Science Quarterly*.

## Appendix: mapping theory terms to agent-runtime vocabulary
- Leader / manager → parent agent (enabler role)
- Team membership → sibling set under a common parent, formalized by `introduce`
- Context (the "why") → `intro_note` in `introduce`; roles; delegation description
- Norms (Hackman) → guardrail policy objects (delivery caps, advisory semantics, yield rules)
- Boundary-spanning signals → `[child settled]` events, artifact summaries, statuses
- Shared consciousness → sibling-ID injection + scoped summary visibility
- Knowledge broker / directory → parent's children map; `introduce` = lookup + route
- Ritual / standup → settlement cadence; "persist before you speak" rule
- Psychological safety → cheap, non-punitive `ask` / `escalate` / decline paths
- Farming for dissent → deliberate contrarian/verifier introductions
- Micromanagement (anti-pattern) → option A relaying — rejected
- Unbounded peer-messaging (anti-pattern) → unconstrained option B — no real team boundary
