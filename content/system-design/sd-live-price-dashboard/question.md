# Design a Live Price Dashboard

> **Level:** Intermediate · 45 minutes
>
> **You will learn:** conflating to the latest value · fanning out in tiers · spending a latency budget · WebSocket versus polling · making staleness visible
>
> **Related questions:** [Design a Low-Latency Market Data Feed and Normalization System](../sd-market-data-feed/question.md) · [Design a News Feed System](../sd-news-feed/question.md)
>
> **Handbook:** [Ch 24 — *When the Market Outruns You*](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md) · [Ch 27 — *The Control Plane*](../../../release1/handbook-markdown/chapters/d7-websocket-and-http/chapter.md) · [Ch 25 — *Whose Clock Was That?*](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md)

## The question

> Design a website that listens to trading hosts continuously publishing ticker prices, and shows the live prices to traders on a dashboard within 100 ms latency.

Trading hosts — the servers running pricing engines and strategies — publish prices continuously: the market prices they see and the firm's own fair values. Traders want those prices in a browser, as a grid of tickers that updates as the market moves.

At the open, some tickers change hundreds of times a second. A browser repaints about sixty times a second, and a trader reads far fewer changes than that.

**The crux: show every trader the latest price within 100 ms — when prices change faster than any screen can show, and without letting a slow browser reach back to the hosts that publish them.**

> **Finance lens.** The consumer version — a stock app or a sports-score page — tolerates a second or two and serves the same few values to millions. Here the audience is a few hundred traders, but they act on what they see, so a frozen price that looks live is worse than an empty cell. This dashboard is also the control plane, not the trading path: strategies get prices over the low-latency feed. Nothing on the dashboard path may ever slow the hosts that feed it ([Handbook Ch 27 — *The Control Plane*](../../../release1/handbook-markdown/chapters/d7-websocket-and-http/chapter.md)).

## Requirements

### Functional requirements

1. Trading hosts publish price updates for their tickers continuously.
2. A trader opens a dashboard with a watchlist and sees the current prices immediately.
3. Prices on the dashboard update live as they change.

Out of scope: charts and history (a follow-up), order entry from the dashboard, and the login system.

### Non-functional requirements

Assume the following workload. The last row is the one that shapes the design.

| Quantity | Value |
|---|---|
| Publishing hosts | 200 |
| Tickers | 20,000 |
| Updates in | 50,000/s normally; 500,000/s in the minutes after the open |
| Hottest ticker | about 800 updates/s at the open |
| Viewers | 500 traders, about 2,000 open tabs, 200 tickers each |
| Updates per tab at the open, if we send everything | 200 tickers × 25/s ≈ 5,000/s, most of it from a few dozen liquid names |

**A tab cannot use 5,000 updates a second. The screen redraws 60 times a second, and a trader reads a few changes a second per cell. Most updates can never be seen, so the design should not try to deliver them.**

1. **Latency.** p99 under 100 ms from a host publishing to the trader's screen changing, on the office network.
2. **Latest, not every.** The screen always converges to the latest price; intermediate updates may be skipped.
3. **Visible staleness.** A price that stops updating because its source or the connection failed is visibly marked within 1 second.
4. **Isolation.** A slow browser never slows other traders, and nothing on the dashboard path can slow a publishing host.
5. **Fast open.** A dashboard shows its whole watchlist within 1 second of opening.

Out of scope: delivering every event (fills, order states, and the trade tape need a different path), and traders on home connections — the third deep dive sets them a separate target.

## Core entities

- **Price update** — one change from one host: ticker, bid, ask, last, the host's sequence number, and its publish time.
- **Latest price** — the current state of one ticker: its most recent update, plus a status of `LIVE` or `STALE`.
- **Session** — one browser tab's connection.
- **Subscription** — the set of tickers a session watches.

The relationship that matters is **many updates, one latest price**. AAPL may update 800 times in the second after the open, and the trader's screen needs exactly one of those values each time it redraws: the newest. Everything in this design follows from treating a price as state to overwrite, not as events to deliver.

## API

Hosts publish a small binary message to the firm's internal messaging bus:

```cpp
struct PriceUpdate {          // topic: prices.<shard>, chosen by ticker
  uint32_t ticker_id;
  int64_t  bid, ask, last;    // scaled integers, never doubles
  uint32_t host_id;
  uint64_t host_seq;          // per-host sequence number
  uint64_t publish_ns;        // host's synchronised wall clock
};
```

Browsers talk to a gateway over one WebSocket, in JSON:

```text
→ { "op": "subscribe", "tickers": ["AAPL", "MSFT", ...] }
← { "op": "snapshot",  "prices": [{ "t": "AAPL", "bid": "187.20", "ask": "187.21", "age_ms": 12, "status": "LIVE" }, ...] }
← { "op": "update",    "seq": 1042, "prices": [ ...only tickers that changed... ] }
→ { "op": "ack",       "seq": 1042 }          // sent when the page's handler runs
← { "op": "heartbeat", "gw_ts": 1759831800123 }
```

Prices travel as strings, because a JSON number becomes a double in the browser and most decimal prices have no exact double ([Handbook Ch 27](../../../release1/handbook-markdown/chapters/d7-websocket-and-http/chapter.md)). The `update` message carries only changed tickers, and `ack` is the page's flow control — the first deep dive relies on both. `age_ms` and `heartbeat` serve the third.

## High-level design

We will build the simplest design that meets each functional requirement, then run the open through it.

### 1) Hosts publish prices

1. Each host publishes a `PriceUpdate` to the bus, on the topic for its ticker's shard.
2. The bus delivers it to the price service shard that owns that ticker. The host never waits for anyone.
3. The shard overwrites its latest-price entry for the ticker, ignoring any update with an older host sequence number.

![Two hundred hosts publish price updates onto the firm's bus, partitioned by ticker; each price-service shard keeps the latest price per ticker.](../../../generated/diagrams/sd-live-price-dashboard/step1-publish.svg)

The bus decouples hosts from viewers. A host does not know or care how many dashboards are open, so adding traders never touches a trading host.

We do not need a durable log such as Kafka here. A lost price is replaced by the next one within milliseconds, so durability buys nothing on this path and costs latency and storage. A low-latency bus — multicast, or a broker such as NATS — fits better.

**The bus must never push back on a host.** If a subscriber falls behind, the bus drops it; it does not slow the publisher.

### 2) Show current prices when a dashboard opens

1. The browser loads the page and opens a WebSocket to a gateway, through a load balancer.
2. It sends `subscribe` with its watchlist.
3. The gateway asks the price-service shards for the latest prices of those tickers.
4. It returns them in one `snapshot`, and the browser draws the grid.

![The browser opens a WebSocket to a gateway, subscribes to its watchlist, and receives one snapshot of the latest prices read from the price-service shards.](../../../generated/diagrams/sd-live-price-dashboard/step2-snapshot.svg)

Gateways hold the WebSocket connections and nothing else, so we can add them freely. A trader's tab sticks to one gateway for the life of its connection.

### 3) Update prices live

The simplest version relays each session's subscription upstream:

1. The gateway registers the session's tickers with the price-service shards.
2. Each shard pushes every change of a subscribed ticker to that session, through the gateway.
3. The browser updates the cell.

Why push rather than poll? Compare the options for 2,000 tabs:

| | Poll every 100 ms | Long polling | Server-Sent Events | WebSocket |
|---|---|---|---|---|
| Added delay | up to the interval | a round trip per batch | none | none |
| Server load | 20,000 requests/s, mostly unchanged data | a request per batch | one stream per tab | one stream per tab |
| Direction | client asks | client asks | server to client only | both ways |
| Fits | slow state: positions, status | rare updates | one-way feeds | live prices plus subscription changes |

Polling fails on the budget by itself: the interval bounds how stale a value can be, so polling every 100 ms can spend the whole budget before anything else happens ([Handbook Ch 27](../../../release1/handbook-markdown/chapters/d7-websocket-and-http/chapter.md)). A WebSocket also carries subscription changes upstream on the same connection, which Server-Sent Events cannot.

![Each session's subscription is relayed to the price-service shards, which push every change through the gateway to the browser.](../../../generated/diagrams/sd-live-price-dashboard/step3-push.svg)

A news feed can push headlines to machines and let human readers pull history at their own pace, the split [Design a News Feed System](../sd-news-feed/question.md) develops. Here even the human needs push, because a price is worth something only while it is current.

### What is still broken

Run 09:30 through this design:

1. **Every update goes everywhere.** A tab receives 5,000 updates a second. A slow tab queues them, and the queue shows old prices as if they were live.
2. **The price service sends to every tab.** 600 tabs watch AAPL, so each AAPL update becomes 600 sends — 480,000 a second for one ticker, from one shard.
3. **Nobody can see the budget, or the staleness.** When p99 reaches 140 ms, no one knows which hop spent it, and a frozen connection looks exactly like a quiet market.

## Deep dives

### 1) AAPL updates 800 times in one second. What do we send?

At 09:30:00, AAPL starts updating 800 times a second. One trader on desk 4 watches 200 tickers from a laptop that is also running three spreadsheets. In the high-level design, every update becomes a WebSocket message to that tab.

The tab's main thread cannot parse and draw 5,000 messages a second, but the browser keeps reading the socket anyway and queues the messages in the tab's memory. Suppose the tab can handle 1,500 a second:

| Time | Sent to the tab | Handled by the tab | Backlog | Screen shows prices from |
|---|---|---|---|---|
| 09:30:01 | 5,000 | 1,500 | 3,500 | 09:30:00.3 |
| 09:30:05 | 25,000 | 7,500 | 17,500 | 09:30:01.5 |
| 09:30:10 | 50,000 | 15,000 | 35,000 | 09:30:03 |

At 09:30:10 the screen shows prices from seven seconds ago, updating smoothly and looking perfectly live.

**Option A: forward every update, with a bigger queue.** Fast clients keep up and see every tick. A slow client falls behind without limit, and a queue of perishable values is worse than no queue: every item in it is older than the one behind it.

**Option B: throttle each ticker to a fixed rate.** Send AAPL at most every 100 ms. Load is bounded, but a naive throttle that drops updates inside the window can leave the screen on a stale value until the next change, and a fixed 100 ms window spends the whole latency budget at once.

Both options treat updates as messages to deliver. A strong candidate notices that the dashboard does not want messages. It wants the *current state* of 200 cells.

**Option C: conflate to the latest value.** For each session, the gateway keeps one slot per watched ticker and a set of dirty tickers:

1. An update for AAPL overwrites AAPL's slot and marks it dirty. Nothing is queued.
2. If nothing has gone to this session in the last 25 ms, the gateway flushes at once. Otherwise it flushes when the 25 ms window ends.
3. A flush sends one `update` message holding the current slot of every dirty ticker, then clears the set.
4. If two flushes are already unacknowledged, the gateway waits. The slots keep being overwritten, so when an ack arrives, the session gets the newest values, not a backlog.

![Updates overwrite one slot per ticker and mark it dirty; a flush at most every 25 ms sends only the dirty tickers' current values, so 800 updates in become at most 40 sends out.](../../../generated/diagrams/sd-live-price-dashboard/dd1-conflation.svg)

Why an application-level ack rather than TCP? A browser reads its WebSocket as fast as the network delivers, even while the page's main thread is too busy to handle the messages, so a slow tab never fills the socket and TCP never pushes back.

The flow control has to live in the protocol. The page acks each update when its handler runs, and the gateway allows two flushes in flight, so a fast tab's ack round trip never delays the next flush.

In one 25 ms window, AAPL might change 20 times, a dozen other liquid names a few times each, and most of the watchlist not at all. The flush carries one entry per changed ticker, each with its latest value. A fast tab receives up to 40 messages a second; a slow tab receives fewer, each one current.

Be precise about what this saves. Conflation caps messages at 40 a second and collapses the bursts on hot tickers — AAPL goes from 800 updates a second to at most 40. A ticker that changes once per window gains nothing, and does not need to.

Memory per session is fixed by the watchlist, not by the update rate: 200 slots of about 48 bytes. Across 2,000 tabs that is roughly 20 MB, whatever the market does.

| | A: forward every update | B: fixed-rate throttle | C: conflate to latest |
|---|---|---|---|
| Memory per session | grows without limit | bounded | bounded: one slot per ticker |
| Added delay when quiet | none | up to the window | none |
| Slow client | falls behind; old prices look live | keeps up | fewer updates, always current |
| Intermediate updates | all delivered | lost | lost |
| Right for | events that must all arrive | simple, slow dashboards | anything where only the current value matters |

Conflation is safe here only because every message is complete state: "AAPL bid is 187.20", not "AAPL bid moved up a cent". Dropping an older state loses nothing; dropping a delta corrupts everything after it. [Handbook Ch 24 — *When the Market Outruns You*](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md) puts the rule in one line: conflate state, never deltas.

The same rule says what must not go through this path. Fills, order acknowledgements, and the trade tape are events — each one matters — so they need a separate channel with sequence numbers and no conflation.

**For a value that only matters now, overwrite instead of queueing: memory stays bounded, and a slow reader sees fewer updates, never older ones.**

> **Design move — Conflate to the latest value.** When a consumer only needs the current value, keep one slot per key, overwrite it on every update, and send the slot when the consumer is ready; the intermediates are dropped. *Cost:* consumers never see every update, so this is wrong for anything that must process each event.

### 2) How does one update reach 600 tabs without being sent 600 times?

At 09:30:01, 600 tabs watch AAPL. In the high-level design, the shard that owns AAPL sends each of its 800 updates a second to each session: 480,000 sends a second for one ticker. Meanwhile 2,000 traders are opening dashboards, and every subscription lands on the same shards. Candidates usually reach for one of two fixes.

**Option A: replicate the price service.** Put several copies behind the gateways, each serving a subset of sessions. It is the right instinct — each copy fans out to fewer sessions — but every copy still processes all 500,000 updates a second and still sends once per session.

**Option B: let each gateway subscribe to everything.** A gateway receives every update once, keeps its own latest-price table, and fans out to its 50 tabs. The price service now sends to 40 gateways instead of 2,000 tabs, and a new tab's snapshot comes straight from the gateway's memory. The cost: at the open, every gateway processes 500,000 updates a second, mostly for tickers none of its tabs watch.

**Option C: fan out in tiers, by interest.** Keep Option B's single upstream subscription per gateway, but only for tickers its tabs watch. Each tier subscribes once to what its children need, conflates, and fans out:

1. A gateway subscribes upstream to a ticker when its first tab starts watching it, and unsubscribes when the last one stops.
2. The price-service shard conflates per gateway, with a 10 ms window: at most 100 AAPL updates a second to each of 40 gateways.
3. The gateway keeps the latest value for every ticker it carries, serves snapshots from that table, and conflates per session as in the first deep dive.

![Hosts publish to the bus; eight price shards each send a ticker once per gateway that wants it; forty gateways each serve fifty tabs from their own latest-price table.](../../../generated/diagrams/sd-live-price-dashboard/dd2-tiers.svg)

| | High-level design | A: replicated price service | B: gateways take everything | C: tiers by interest |
|---|---|---|---|---|
| Sends per AAPL update at the shard | 600 | 600, spread over copies | 40 | at most 40, conflated |
| Updates into each gateway | — | — | all 500,000/s | watched tickers only |
| Snapshot on open | from the shards | from a copy | from the gateway's table | from the gateway's table if carried |
| Upstream churn | every tab open and close | every tab open and close | none | a ticker's first or last watcher per gateway |
| Moving parts | fewest | copies to keep in sync | simple | subscription bookkeeping |

The arithmetic is the point. With tiers, the load on the price service grows with the number of gateways, not with the number of traders. AAPL goes from 480,000 sends a second to at most 4,000.

Option B is a reasonable answer if the firm has a cheap multicast bus to the gateways: then "subscribe to everything" costs the price service one send, and only the gateways pay. Say that, and name the input rate where filtering by interest starts to matter.

One placement trick helps more than it looks. Traders on one desk watch similar tickers, so route a desk's tabs to the same few gateways. Each gateway then carries fewer distinct tickers, and upstream subscriptions shrink.

A tab that stops acknowledging entirely — a laptop lid closed mid-session — costs only its slots. It still needs cutting loose. Isolating slow consumers — cutting off one that cannot keep up and making it resync, rather than letting it hold resources — is the move [Design a Low-Latency Market Data Feed and Normalization System](../sd-market-data-feed/question.md) develops for strategies. Here the trigger is simple: no ack for 5 seconds closes the session, and the browser reconnects to a fresh snapshot.

**Subscribe once per tier: upstream load should grow with the number of gateways, not the number of traders.**

> **Design move — Fan out in tiers.** Subscribe once per tier: each edge server holds one upstream subscription and serves many clients, so upstream load grows with edge servers, not with viewers. *Cost:* another hop of latency, and edge servers to operate.

### 3) Where do the 100 ms go, and how does a trader know a price is stale?

At 10:12, the head of desk 4 complains that AAPL sat at 187.20 for three seconds while the market moved, and nothing on screen said anything was wrong. The same week, monitoring reports a p99 of 140 ms, and nobody can say which hop spent it.

These are two failures with one root. We never decided where the 100 ms should go, and we cannot see where they actually go.

**First, budget it.** Split the target across the hops, then measure each one against its share:

| Hop | p99 budget |
|---|---|
| Host publishes to the bus | 1 ms |
| Bus to price-service shard | 2 ms |
| Shard conflation window, per gateway | ≤ 10 ms |
| Shard to gateway | 1 ms |
| Gateway conflation window, per session | ≤ 25 ms |
| Gateway to browser, office network | 5 ms |
| Browser: parse, wait for the next frame, paint | ≤ 25 ms |
| Headroom: retransmits, pauses, bursts | 31 ms |
| **Total** | **100 ms** |

**Most of the budget is spent on purpose — in the two conflation windows and the browser's frame — not on the wire.** That is the lever. Halving the gateway window buys 12 ms and doubles messages to fast tabs. The budget makes that trade visible instead of accidental.

There is no window that is right for everyone. A trader on a home VPN with an 80 ms round trip cannot get 100 ms from any design. Say so, and give that group a separate target — 250 ms, say — rather than shrinking everyone's windows to chase it.

**Second, measure it without trusting the browser's clock.**

- **Server hops.** Each tier adds its own timestamp to the message. With clocks synchronised by PTP to well under a millisecond, subtracting one server's stamp from another's is valid. NTP's error is about a millisecond — as large as the 1–2 ms hops — so with NTP, measure those hops as round trips instead.
- **The last hop.** A trader's laptop clock can be off by seconds, so use a round trip on one clock. The gateway stamps a heartbeat; the browser echoes it along with how long it held it, measured locally; the gateway subtracts the hold time and halves the rest.
- **Inside the browser.** The page reports its parse-to-paint time as a duration from `performance.now()`, which needs no shared clock at all.

The same rule decides how the screen shows age. The gateway computes `age_ms` from the host's publish time with its own synchronised clock. The browser adds the time since the message arrived, measured locally. It never compares its own wall clock with a server's ([Handbook Ch 25 — *Whose Clock Was That?*](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md)).

> **Design move — Spend a latency budget.** Split an end-to-end latency target into per-hop budgets, timestamp every hop, and spend the budget where it buys the most. *Cost:* measurement across machines needs clock discipline.

**Third, make staleness visible.** The 10:12 freeze was a TCP connection stalled on retransmission: the bytes would arrive eventually, in order, so nothing ever looked broken. Handbook Ch 27 calls this an invisible delay, as opposed to a gap you can detect. Silence must not look like a quiet market, at two levels:

- **The connection.** The gateway sends a heartbeat every 250 ms. If the browser hears nothing for 1 second, it greys the whole grid and shows "reconnecting".
- **The source.** Hosts heartbeat to the price service every 100 ms. If a host is silent for 500 ms, its tickers become `STALE`, and that status travels down the tiers like any price change. An illiquid ticker that has not moved is not stale while its host is alive.

This is publishing trust state as data: tell consumers explicitly when data is untrusted, and never let silence look like health. [Design a Low-Latency Market Data Feed and Normalization System](../sd-market-data-feed/question.md) builds the move for strategies; here the consumer is a human, so the state becomes grey cells and a visible age. The status is conflation-safe, because it is state too.

**Split the 100 ms into per-hop budgets, timestamp every hop, and show the trader how old each price is. A stale price must look stale.**

## Interview calibration

**A passing answer**

- Pushes updates over WebSockets instead of polling, with a snapshot when the dashboard opens.
- Puts a service between hosts and browsers that keeps the latest price per ticker.
- Scales the WebSocket tier horizontally.

**A strong answer also**

- Does the fan-out arithmetic, sees that a tab cannot render every update, and conflates to the latest value — and says which data must never be conflated.
- Adds flow control in the protocol, because a browser's WebSocket never pushes back on a slow page.
- Fans out in tiers with interest-based subscriptions, so upstream load grows with gateways, not tabs.
- Splits the 100 ms into a per-hop budget and spends most of it deliberately.
- Makes staleness visible at both the connection and the source.
- Measures the last hop without trusting the browser's clock.

## Follow-ups

**Traders want a one-minute chart next to each price. Can we build it from this stream?**

> Not from the conflated stream: it skips updates, so a bar's high and low would be wrong. Compute bars from the full stream — in the price service, or in a separate aggregator reading the bus — and store them in a time-series store, the kind [Design a Distributed Time-Series Storage System](../sd-timeseries-storage/question.md) builds. The *current* bar is state, though, so its live updates can ride the conflated path.

**Why not let browsers subscribe to the bus directly, through a WebSocket bridge?**

> Every tab becomes an upstream subscriber, so the fan-out problem returns. There is no per-session conflation for slow tabs, no single place to enforce which traders may see which prices, and a misbehaving browser now touches the system the hosts publish into. The gateway tier exists to absorb exactly that.

**How do you deploy a new gateway version during the trading day?**

> Drain one gateway at a time. Stop routing new sessions to it, then ask its tabs to reconnect in small batches with a random delay, so the remaining gateways are not hit by 50 reconnects in the same millisecond. Each reconnect gets a fresh snapshot, and the trader sees a sub-second "reconnecting" badge instead of a frozen grid.
