# Information Theory, Transaction Costs, Bounded Rationality

Section 1 of the management-theory survey. Index: [README.md](README.md).

## 1.1 Information theory: noise in the channel
Claude Shannon's information theory (1948) defines communication as signal
passing through a channel subject to **noise**. Every retransmission stage adds
opportunity for noise, latency, and loss. In human organizations this is the
classic **telephone game**: the more hops a message takes, the more it is
distorted.

> Translation: a parent relaying child A's findings to child B is a
> retransmission stage. Each relay adds a parent LLM turn (cost + latency) and
> distorts the message (the parent summarizes from its own perspective). Direct
> A→B links minimize stages. The parent's one-time introduction is a *link
> setup*, not a retransmission.

## 1.2 Transaction cost economics: when direct links beat the hub
Coase (1937) and Williamson (1975) ask why firms exist, and when it is cheaper to
coordinate through a market than through a hierarchy. The answer is **transaction
cost** — the effort of finding partners, negotiating, and enforcing agreements.
Inside an organization the same logic applies to *communication*: when routing
every exchange through a central coordinator costs more than setting up a direct
relationship, teams route around the hub.

> Translation: each message relayed through the parent is a transaction with a
> token and context cost. A single `introduce` call is a one-time setup cost
> that amortizes over many direct exchanges. The runtime should *internalize*
> this: introducing costs ~1 turn, relaying costs O(n) turns.

## 1.3 Bounded rationality and the manager as bottleneck
Herbert Simon's **bounded rationality** (1957) — humans (agents) have limits on
attention, memory, and processing. Any actor that must process *everything* to
coordinate *everything* becomes the bottleneck and the limit on the whole
system's intelligence.

> Translation: option A failed precisely because the parent's bounded context
> cannot absorb N coordination streams. The parent must touch only *boundary
> events* (introductions, escalations, settlements), never every exchange.
