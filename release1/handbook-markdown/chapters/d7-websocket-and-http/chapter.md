<!--
chapter: d7-websocket-and-http
state: draft_created
contract: standards/chapter-contract.md — APPENDIX, not in the numbered sequence
include_measurement_plan: false | include_quizzes: false | primary_artifact_mode: none
unresolved_markers: 0
-->

# The Control Plane

## Appendix: WebSocket, HTTP Polling, and Venue APIs

**Prerequisites:** [d1] Market data and protocols · [d2] Transports
**Status:** appendix — read after Module D if you work with venues that offer these interfaces

---

## Where most engineers start

An engineer arriving from web development looks at a crypto venue's API. There is a WebSocket endpoint that streams order-book updates as JSON, a REST endpoint for account state, and clear documentation with a working example in twelve lines.

They reasonably conclude this is how market data works.

It is how *this venue's* market data works. The difference between it and the multicast binary feed in [d1] is not a matter of taste or modernity, and understanding it explains a good deal about which strategies are viable on which venues — and why a firm's exchange connectivity and its crypto connectivity look like they were designed by different people, because in effect they were.

This appendix exists because many engineers meet these interfaces first and generalise from them in the wrong direction.

## What WebSocket actually is

A WebSocket connection is a **framed message stream over a single TCP connection**, established by an HTTP handshake that upgrades the connection. Once established, either side can send discrete messages without the request-response structure of HTTP.

It solves a real problem: browsers could not receive server-initiated messages without polling. As a general-purpose streaming transport it is sound, widely supported, and traverses the network infrastructure that HTTP traverses — which is a substantial practical advantage.

For market data it inherits three properties from what it is built on.

**It is per-client, so the venue's cost scales with subscribers.** Every connected client is a TCP connection with its own send buffer and its own serialisation of every update. This is exactly the fan-out problem from [d2]: the venue does work proportional to subscriber count, and clients are necessarily served in *some* order. A venue with a hundred thousand connected clients has a hard capacity limit and no way to serve them simultaneously — which is a fairness property no amount of engineering recovers.

**It inherits TCP's head-of-line blocking.** A lost segment stalls every message behind it until retransmission completes ([d2]). Your book is silently stale during that interval rather than known-untrusted, and there is no sequence gap to detect because TCP will deliver the missing bytes eventually and in order. Where a multicast feed hands you a detectable gap, this hands you an invisible delay.

**Encoding is usually text.** JSON is human-readable, self-describing, and costs a great deal more to parse than a fixed binary layout — allocation, string handling, and number conversion per message rather than a bounds-checked read into a struct ([d1]).

The number handling deserves particular attention. JSON numbers are conventionally parsed into a double, which reintroduces exactly the problem [d1] spent a section on: decimal prices that do not round-trip exactly. Careful venues send prices as **strings** for this reason, and a careful client parses those strings into a scaled integer rather than into a float. A client that parses `"178.42"` with a standard JSON library and gets a `double` has silently accepted an approximation of the price it will be held to.

## HTTP polling

The simpler pattern: ask periodically for the current state.

The property that decides everything is that **the polling interval bounds your staleness.** Poll every second and your view can be a second old. There is no mechanism by which polling delivers a change faster than the interval, so the interval is a floor on how out-of-date you are.

That makes it entirely appropriate for state that changes slowly and where seconds do not matter — account balances, position summaries, instrument lists, fee schedules, system status — and inappropriate for prices, in any market where prices move faster than you poll.

It also has a cost the client does not see: polling generates load proportional to `clients × frequency`, most of it returning unchanged data. Venues respond with rate limits, and a client that treats rate limits as an obstacle to work around rather than a signal that it is using the wrong interface will eventually be throttled at an inconvenient moment.

## Where these belong

The useful framing is the one from [a1]: **data plane versus control plane.**

The **data plane** carries the information the trading decision depends on and the orders that result. It is latency-sensitive, high-rate, and on the critical path. Where a venue offers a binary multicast feed, that is what belongs here.

The **control plane** is everything else: configuration, position and balance queries, instrument reference downloads, administrative actions, monitoring interfaces, session management. Rates are low, a millisecond is irrelevant, and the properties that matter are simplicity, debuggability, and not having to write a parser.

**HTTP and WebSocket are excellent control-plane interfaces.** They are well-understood, every language has libraries, they traverse firewalls, and they are easy to inspect when something is wrong. Using them for control-plane work is not a compromise; it is the right choice.

The mistake is putting them on the data plane when an alternative exists — and the corresponding mistake in the other direction is building a bespoke binary protocol for an admin interface that a REST endpoint would have served better.

## When the venue offers nothing else

Many crypto venues, and some brokers, provide only these interfaces. Then the question is not which to choose but what follows from the constraint.

**Your latency floor is set by the venue.** Per-client serialisation, TCP, and text parsing together put a floor under your reaction time that is orders of magnitude above a colocated binary feed. Strategies that depend on being first are not viable, and this is a fact about the venue rather than about your engineering. Recognising it early saves considerable wasted optimisation.

**Sequence handling still matters, and works differently.** Better venues include sequence numbers in their WebSocket messages, and everything in [d3] applies — with the difference that a gap usually means a *reconnect* rather than a lost packet, since TCP does not lose messages within a connection. The recovery path is typically to re-fetch a snapshot over REST and resume, which is [d3]'s snapshot resync with different plumbing.

**Reconnection is the dominant failure mode.** Connections drop, and every drop is a gap of unknown size. A client needs automatic reconnection, a snapshot refresh on reconnect, and reconciliation of anything it believed about its orders ([a2], [e1]) — because a disconnect tells you nothing about what the venue did while you were away.

**Parsing is worth attention here**, unusually. On a binary feed, parsing is a small share of the cost. With JSON at high message rates it can be the dominant cost in the client, so a parser that avoids allocation and handles numbers as strings is worth more here than most micro-optimisations elsewhere.

## Where trading firms actually use WebSocket

Everything above is about why these interfaces do not belong on the data plane. The other half is more useful, and it is skipped surprisingly often: **firms use WebSocket heavily, internally, and it is the right tool there.**

The property that makes it right is the one HTTP lacks. A WebSocket connection is **bidirectional and persistent**: the server can push without being asked, and the client can send on the same connection, at any time, with no new handshake. That is exactly the shape of a human sitting in front of a screen.

**Live dashboards.** A trader watching positions, P&L, working orders, and risk utilisation needs the numbers to change as the market does. Polling every second means a display that is up to a second stale and a server answering thousands of requests that mostly return what it returned last time. A WebSocket push means the server sends an update when something changes, and the screen is as current as the network allows.

Note what has happened to the requirements. The display is off the critical path entirely ([a1]) — a human cannot perceive a millisecond, so none of the latency arguments in this appendix apply. What matters instead is that the connection is cheap to maintain, that it recovers automatically, and that a developer can debug it with browser tools. WebSocket is good at all three.

**Bidirectional control.** The same connection carries commands back. A trader clicks *pause strategy*, *cancel all*, *widen quotes*, or *reduce size*, and the command travels over the connection already open for the price feed. Building that with HTTP means a separate request path, separate authentication handling, and a polling loop to discover whether the command took effect. With a persistent bidirectional connection the command goes out and the resulting state change arrives back as a normal update on the same stream.

That said, a **kill switch should not depend on it.** Anything that reduces risk needs a path that works when the primary one is broken — the [c2] principle that risk-reducing operations must not queue behind the machinery that might be failing. A convenient WebSocket control channel is fine for routine actions and a poor sole mechanism for stopping everything.

**Internal monitoring consoles.** Feed health, gap counts, queue depths, drop counters, latency percentiles — everything Module D said to export ([d4], [d6]) has to reach a screen, and this is how. The traffic is small, the audience is small, and the tooling is excellent.

**Vendor and broker APIs.** Many providers offer WebSocket as the only streaming interface. There the choice is not yours, and the earlier sections apply: parse prices from strings, handle reconnection as the dominant failure mode, and accept the latency floor.

**Request-for-quote workflows.** In markets that work by asking dealers for a price rather than by continuous order books — much of fixed income and parts of FX ([preface]) — the interaction is genuinely conversational: a request goes out, quotes come back from several dealers, one is accepted, and a confirmation follows. A persistent bidirectional session fits that shape far better than either polling or a one-way feed.

The unifying observation: **WebSocket is a good fit wherever the interaction is a conversation between a system and a person, or between two systems that genuinely take turns.** It is a poor fit where one party is broadcasting to many at high rate and every microsecond counts. Those are different problems, and it is only confusing because the same word — "streaming" — gets used for both.

## Interview mapping

- **Place these on the control plane** and justify it: per-client fan-out, TCP head-of-line blocking, text parsing cost.
- **Explain why per-client connections limit fan-out and fairness.** It is [d2]'s argument applied to a different protocol, and connecting them shows the reasoning transfers.
- **Note that prices should be strings, not JSON numbers**, and say why. A precise, specific point that lands well.
- **Say what changes when a venue offers only this** — a latency floor set by the venue, reconnection as the dominant failure mode, snapshot-on-reconnect as the recovery path.
- **Do not disparage them.** They are the right tool for the control plane, and an interviewer is listening for judgement rather than a preference.

## Summary

WebSocket is a framed message stream over one TCP connection, so it carries TCP's ordering guarantee, TCP's head-of-line blocking, and a per-client cost that makes the venue's work grow with subscriber count and its delivery necessarily unequal. HTTP polling bounds your staleness at the polling interval by construction. Both usually carry text, which costs parsing time and — unless prices are sent as strings and parsed into scaled integers — quietly reintroduces floating-point approximation into numbers that must be exact.

Those properties make both excellent for the control plane, where a millisecond does not matter and simplicity and debuggability do, and poor for the data plane wherever a binary multicast feed is available.

Where a venue offers nothing else, the constraint is real and worth accepting early: the latency floor is theirs, not yours; reconnection rather than packet loss is the failure mode you design for; and the recovery path is [d3]'s snapshot resync wearing different clothes.

**Related:** [d1] market data and protocols · [d2] transports · [d3] gap recovery · [a1] system anatomy · [a2] order lifecycle · [e1] idempotency

## References

- The WebSocket protocol is specified in IETF RFC 6455; it is the authority for framing and the handshake. *(Stage 1 source pack to confirm current status.)*
- Individual venue API documentation is the authority for that venue's message formats, sequence-number semantics, rate limits, and reconnection behaviour, all of which differ substantially.
