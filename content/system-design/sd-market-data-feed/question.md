# Design a Low-Latency Market Data Feed and Normalization System

> **Level:** Advanced · 60 minutes
>
> **You will learn:** splitting the hot path from the reliable path · sequence numbers and gap recovery · arbitrating redundant feeds · publishing trust state · capture for replay · isolating slow consumers
>
> **Related questions:** [Design a Log Publishing and Query System](../sd-log-publishing-query/question.md) · [Design a News Feed System](../sd-news-feed/question.md) · [Design a Risk-Limit Update Fan-Out Service](../sd-risk-limit-fanout/question.md)
>
> **Handbook:** [Ch 21 — *Reading the Wire*](../../../release1/handbook-markdown/chapters/d1-market-data-and-protocols/chapter.md) · [Ch 23 — *The Book That Is Silently Wrong*](../../../release1/handbook-markdown/chapters/d3-sequence-and-gap-recovery/chapter.md) · [Ch 26 — *Taking the Kernel Out of the Path*](../../../release1/handbook-markdown/chapters/d6-kernel-bypass/chapter.md) · [Ch 31 — *What Did It See, and Why Did It Do That?*](../../../release1/handbook-markdown/chapters/e4-deterministic-replay/chapter.md)

## The question

> Design a low-latency market data feed and normalization system. Discuss the live path, ordering, gap detection and recovery, replay, failure handling, capacity, observability, and how downstream trading components consume the normalized events.

Exchanges publish every change to their order books as a stream of small binary messages over UDP multicast. A feed handler on a server in the exchange's data centre receives them, decodes the venue's protocol, converts them into one event format, and hands them to strategies on the same machine — in microseconds.

**The crux: make the live path as short as the hardware allows, and make it know, and say, the moment its picture of the market is wrong.**

### Domain primer

Four facts about exchange feeds shape everything below. Handbook Chapters 21–23 teach them properly; here is the minimum.

| What the venue provides | What it means for us |
|---|---|
| **Incremental feed** — messages like "add order", "cancel order", "trade" | Our book is the sum of every delta. Miss one and the book is wrong without looking wrong. |
| **Channels** — instruments split across multicast groups, each with its own sequence numbers | Ordering and loss are per channel, not per instrument and not global. |
| **A and B lines** — identical packets sent over two separate network paths | Most single-path losses can be filled from the other copy. |
| **Recovery services** — retransmission of specific sequence numbers, and periodic full-book snapshots | Two different ways back to a correct book, with different costs. |

> **In the interview.** The prompt lists eight topics. Nobody covers eight topics deeply in an hour. Sketch the whole boundary in about fifteen minutes, then agree with the interviewer on two deep dives. Saying this out loud is part of the answer.

## Requirements

### Functional requirements

1. Receive feeds from several venues, decode them, and normalize every message into one event format.
2. Deliver normalized events to strategies on the same host; each strategy subscribes to the instruments it trades.
3. Detect loss, recover from it, and publish a trust state per instrument: live, recovering, or stale.
4. Capture every input so any session can be replayed and research datasets can be built.

Out of scope: order entry, strategy logic, the internals of the historical tick database, and redistribution to other sites.

### Non-functional requirements

Assume three venues and about 50 subscribed channels. A typical rate is 1 million messages per second across them; the open bursts to 5 million per second for a few seconds. A message averages 40 bytes.

| Quantity | Value | What it tells us |
|---|---|---|
| Peak bytes | 5 M/s × 40 B = 200 MB/s ≈ 1.6 Gb/s | A 10 or 25 Gb/s NIC carries it; bandwidth is not the problem |
| Per-message budget on one core | 1 s ÷ 5 M = **200 ns** | One core cannot decode, normalize, and publish everything; we must shard |

**The network is not the bottleneck. CPU time per message is.**

1. **Latency.** From NIC to strategy in single-digit microseconds at the 99th percentile, with low jitter. A good median with a bad tail is a bad feed ([Handbook Ch 3 — *The Worst Microsecond of the Day*](../../../release1/handbook-markdown/chapters/a3-latency-throughput/chapter.md)).
2. **Correctness.** Never publish a book known to be wrong. Detect every gap, and tell consumers which instruments are affected.
3. **Bursts.** Absorb the open without falling behind; if we do fall behind, it must be visible.
4. **Replay.** Replay any session through the same code and get the same output.
5. **Failure.** Survive the loss of one line, a process restart, and a host failure.

> **Finance lens.** In a consumer-tech streaming design, the default answer is a durable broker: write each event to Kafka, then let consumers read it. Durability per message is cheap next to a 50 ms budget. Here the budget is a few microseconds, so the live path has no durable write, no broker, and no network hop between the feed handler and the strategy. Durability still exists — on a parallel path. "Should we put Kafka here?" Yes, on the capture side. Never in front of the strategy.

## Core entities

- **Channel** — one multicast group from one venue, with its own sequence numbers, arriving twice (lines A and B).
- **Packet** — one UDP datagram: a header with the first sequence number and a message count, then the messages.
- **Venue message** — the exchange's native record: add, modify, delete, trade, status.
- **Normalized event** — our fixed-size record: instrument, event type, side, integer price, quantity, order ID, exchange time, receive time, channel, and sequence number.
- **Instrument state** — the book for one instrument, plus its trust state: `LIVE`, `RECOVERING`, or `STALE`.

The relationship to hold on to is **sequence numbers belong to channels**. One lost packet on channel 7 makes every instrument on channel 7 untrusted, and no instrument anywhere else.

## API

Here the interface is a memory layout, not an HTTP endpoint. Strategies read fixed-size normalized events from shared memory:

| Field | Bytes | Note |
|---|---|---|
| exchange time, receive time | 8 + 8 | the venue's timestamp; the NIC's hardware timestamp |
| order ID, channel sequence number | 8 + 8 | |
| price | 8 | an integer; the scale is per instrument |
| instrument, quantity | 4 + 4 | |
| channel, type, side, flags | 2 + 1 + 1 + 1 | type is add, modify, delete, trade, clear, or status; flags include `LAST_IN_PACKET` |
| padding | 11 | to exactly 64 bytes: one cache line |

A few choices in that layout are deliberate:

- **Fixed size, one cache line.** Rings of fixed-size slots need no allocation and no length parsing, and one event never straddles two cache lines.
- **Integer prices.** Doubles cannot represent most decimal prices exactly, and every equality check and tick-size check downstream inherits the error ([Handbook Ch 21](../../../release1/handbook-markdown/chapters/d1-market-data-and-protocols/chapter.md), Part 2).
- **Two timestamps.** Exchange time is when the venue says it happened; receive time is when we knew. Replay and latency measurement need both. [Design a News Feed System](../sd-news-feed/question.md) develops this move for backtests.
- **`LAST_IN_PACKET`.** One packet can carry several messages that only make sense together. Consumers should act on the book at packet boundaries, not mid-packet ([Handbook Ch 28 — *The Structure Everything Reads*](../../../release1/handbook-markdown/chapters/e2-order-book-construction/chapter.md), Part 4).

Control messages are ordinary calls: `subscribe(strategy, instruments)` returns the name of a shared-memory ring. Trust state travels in the data itself, as `STATUS` events, so a strategy cannot read prices without also seeing whether they are trusted.

## High-level design

### 1) Receive, decode, normalize, deliver

Start with one channel, one line, and two strategies.

1. A feed-handler thread, pinned to an isolated core, busy-polls the NIC receive queue for channel 7.
2. For each packet it checks the sequence number, decodes the venue messages, and normalizes each one.
3. It updates the instrument books, then writes each event into the shared-memory ring of every strategy subscribed to that instrument.

![One feed-handler thread owns channel 7 from the NIC queue to the strategy rings: sequence check, decode, normalize, update books, write events.](../../../generated/diagrams/sd-market-data-feed/step1-live-path.svg)

This is normalizing at the edge: one adapter per venue converts its format into the firm's model on entry, so nothing downstream parses venue formats. [Design a News Feed System](../sd-news-feed/question.md) builds the same move for heterogeneous text sources. Here the budget is a thousand times smaller: the adapter is a hand-written binary decoder, and the canonical model is a 64-byte struct.

The handoff to strategies is a hot-path handoff: the latency-critical thread writes a small record into a preallocated ring and never waits for a reader. [Design a Log Publishing and Query System](../sd-log-publishing-query/question.md) uses it for a logging side channel; here it is the product itself. One single-producer ring per strategy means the feed handler publishes with one release store and never waits on a reader ([Handbook Ch 10](../../../release1/handbook-markdown/chapters/b2-spsc-ring-buffer/chapter.md)).

Three rules keep the live path predictable:

- **One thread owns a channel end to end.** No shared mutable state, so no locks.
- **Nothing allocates.** Books and rings are preallocated and touched at startup ([Handbook Ch 16](../../../release1/handbook-markdown/chapters/c2-preallocation-and-pools/chapter.md)).
- **Nothing blocks.** The thread spins on its queue rather than sleeping, because waking a sleeping thread costs microseconds we do not have ([Handbook Ch 8 — *Waiting for the Market to Move*](../../../release1/handbook-markdown/chapters/b5-waiting-strategies/chapter.md)).

### 2) Detect loss with sequence numbers and two lines

Multicast over UDP has no retransmission: a dropped packet is simply gone. The venue's answer is to send everything twice.

1. The feed handler reads both line A and line B for channel 7.
2. For each sequence number, the first copy to arrive is used; the second is discarded.
3. Only if *both* lines miss a sequence number does the channel have a gap. Its instruments become `RECOVERING`, and a separate recovery thread starts working on it.

![Lines A and B each miss a different packet; arbitration takes the first copy of each sequence number and the stream is complete. Only a hole on both lines goes to the recovery thread.](../../../generated/diagrams/sd-market-data-feed/step2-ab-arbitration.svg)

Arbitration is deduplication by identity, at 200 ns per message: the identity is the sequence number, and the check is one integer comparison against `expected`.

> **Design move — Arbitrate redundant feeds.** Consume both copies of a feed and take the first arrival of each sequence number; one line fills the other's gaps. *Cost:* double the receive bandwidth and CPU.

> **Design move — Sequence, detect gaps, recover.** Number every message per stream. On a gap, mark the state untrusted, buffer what follows, and recover by retransmission or snapshot. *Cost:* recovery logic, buffers, and a period of publishing nothing for the affected instruments.

The first deep dive walks through recovery in detail.

### 3) Capture everything, off the live path

1. The colo switch mirrors every packet on both lines to a capture port.
2. A capture writer, on its own cores or its own host, records each raw packet with its NIC hardware timestamp into local files.
3. Files ship later to a central capture store.
4. Replay tools and research pipelines read the captures, using versioned decoders.

![The hot path and the reliable path read the same packets from the colo switch; nothing on the reliable path can slow the feed handlers.](../../../generated/diagrams/sd-market-data-feed/step3-two-paths.svg)

The two paths have different jobs and different clocks. The hot path is measured in microseconds and keeps nothing. The reliable path is measured in seconds to hours and keeps everything. Neither waits for the other.

> **Design move — Split the hot path from the reliable path.** Keep the latency path to the minimum work that is safe, and feed durable and slow work from the same input on a parallel path. *Cost:* two paths can disagree, so you need a way to reconcile them.

> **Design move — Capture inputs at the boundary for replay.** Record raw inputs with receive timestamps where they enter, so any decision can be replayed deterministically. *Cost:* storage, and a capture path that must never slow the live one.

This is where Kafka, columnar files, and object storage belong. A partitioned append-only log and batching — both built in [Design a Log Publishing and Query System](../sd-log-publishing-query/question.md) — come back on this side, where throughput matters and microseconds do not.

### 4) How strategies consume events

The prompt asks this explicitly, and there is no single answer. The choice is a trade between latency and isolation:

| Option | Latency | Isolation | Use when |
|---|---|---|---|
| Strategy code runs inside the feed-handler thread | lowest: no handoff at all | none: a slow strategy stalls the feed | one strategy, one team, one channel group |
| One SPSC ring per strategy, in shared memory | one cache-line handoff | a slow strategy only fills its own ring | the default |
| One shared broadcast ring with a cursor per reader | similar; one write serves every reader | a lagging reader must be detected and cut off | many readers of the same channels |
| Republish over multicast to other hosts | adds a network hop | complete | consumers that are not latency-critical |

### What is still broken

1. **Both lines miss the same packet**, at the open, when it matters most.
2. **The open itself:** 200 ns per message, and one strategy that cannot keep up.
3. **Proving it is right:** capture loss, replay, protocol changes, and what to watch.

## Deep dives

### 1) How do we recover from a gap without stalling the live feed?

At 09:30:00.150 a burst on channel 7 overflows a switch buffer upstream of both lines. Packets carrying sequence numbers 148,200 to 148,202 never arrive. Then 148,203 does.

The book for every instrument on channel 7 is now wrong, and nothing about it looks wrong. As Handbook Ch 23 puts it, a missed delta does not make the book stale; it desynchronises the accumulator.

The handler responds in a fixed order:

1. **Stop trusting.** Mark channel 7's instruments `RECOVERING` and publish a `STATUS` event for each. Strategies pull their quotes on those instruments.
2. **Keep receiving.** Buffer 148,203 onwards in a bounded per-channel buffer. The live thread never waits for recovery.
3. **Ask for the hole.** The recovery thread requests 148,200–148,202 from the venue's retransmission service, over its own session.
4. **Fill and drain.** When the missing messages arrive, apply them in order, then drain the buffer.
5. **Trust again.** Publish `STATUS: LIVE`.

If retransmission is refused, too slow, or the buffer fills first, switch to a snapshot: wait for the next full image of the channel stamped with sequence number S, rebuild the books from it, discard buffered messages up to S, and apply the rest.

![Trust state per channel: a gap moves LIVE to RECOVERING; a filled hole returns to LIVE; a refused or slow recovery, or a missed heartbeat followed by resumed data, goes through SNAPSHOT RESYNC.](../../../generated/diagrams/sd-market-data-feed/dd1-recovery-states.svg)

The two recovery mechanisms are easy to confuse. The difference that keeps them straight:

| | Retransmission | Snapshot resync |
|---|---|---|
| Book kept? | Yes — patch the hole | No — replace it |
| Wait bounded by | request round trip | snapshot publishing cycle |
| Large or late gaps | fails: limited history | works |
| Cold start | impossible | the only option |

Handbook Ch 23 has the full comparison, including why "retransmission first, snapshot on failure" is the usual policy — and why the venue's actual numbers can reverse it.

**Publishing nothing is better than publishing a book you know is wrong. The trust state is how the strategy finds out.**

> **Design move — Publish trust state as data.** Tell consumers explicitly when data is stale or untrusted; never let silence look like health. *Cost:* every consumer needs a defined behaviour for "untrusted".

Silence needs the same treatment. A quiet channel and a dead one look identical, so venues send heartbeats on idle channels. No heartbeat within the expected interval moves the channel to `STALE`. A news feed must notice a silent vendor for the same reason; here the timer is measured in milliseconds instead of minutes.

Containment matters as much as recovery. The gap is on channel 7, so only channel 7's instruments change state; every other channel keeps publishing. That is why sequence numbers are per channel, and why one thread per channel group is a correctness boundary as well as a performance one.

### 2) How do we fit the open into 200 ns per message?

Start from the budget. At 5 million messages per second, one core gets 200 ns per message for everything. So the work has to be small *and* spread across cores.

**Shard by channel.** Give each group of channels its own feed-handler thread on its own isolated core. Channels have independent sequence numbers, so no coordination is needed between threads. Put those cores, the NIC, and the rings on the same NUMA node, so no packet crosses the socket interconnect ([Handbook Ch 20 — *The Server Upgrade That Made Things Worse*](../../../release1/handbook-markdown/chapters/c5-numa-placement/chapter.md)).

**Pick the receive tier from the budget.** Each tier removes another layer between the wire and our code:

| Tier | What it removes | When it is worth it |
|---|---|---|
| Kernel sockets, one `recv` per packet | nothing | non-latency-critical consumers |
| Kernel sockets with busy polling, batched receive | interrupt and wake-up latency | moderate budgets, simple operations |
| Kernel bypass: vendor user-space stacks, DPDK, AF_XDP | system calls and kernel copies | single-digit-microsecond budgets |
| FPGA decoding on the NIC | software from the decode step | when the remaining software path is itself the bottleneck |

Handbook Ch 26 explains what each tier actually removes and what it costs to operate. Say in the interview which tier the budget forces, rather than reaching for the most exotic one.

**Batch only what is already waiting.** A log shipper waits up to 200 ms to fill a batch ([Design a Log Publishing and Query System](../sd-log-publishing-query/question.md)), which is fine for logs and fatal here. The safe version on a hot path is opportunistic: when several packets are already queued, take them all in one poll. Under load that amortises per-poll cost for free; when idle, it adds no delay.

**Now the slow consumer.** During the open, strategy C's ring fills because its own code is slow. The feed handler has three options:

| Option | What happens | Verdict |
|---|---|---|
| Wait for space | every other strategy stalls behind C | never |
| Drop C's events silently | C's book is wrong and it does not know | never |
| Mark C stale, stop writing, make it resync | only C pays; it knows it must recover | yes |

To resync, C reads a snapshot of the current books that the feed handler maintains in shared memory, then resumes from the ring at the snapshot's sequence number. A display-only consumer, such as a trader's screen, can accept conflation instead: deliver only the latest state per instrument, never every event. [Design a Live Price Dashboard](../sd-live-price-dashboard/question.md) builds that path.

> **Design move — Isolate slow consumers.** Give each consumer a bounded buffer; on overflow, cut it off and make it resync instead of slowing everyone. *Cost:* the slow consumer pays with a resync, and you need a snapshot path.

**A slow consumer must never slow the producer. Cut it off loudly, and let it resync.** A queue buys time, not capacity ([Design a Notification System](../sd-notification-system/question.md)): size each ring for the longest stall you are willing to absorb, and treat anything longer as a resync, not as a bigger buffer.

### 3) How do capture, replay, and research stay off the trading path?

The rule for this part of the system is simple: research must never be able to slow trading. Three decisions make that true.

**Where capture happens.** Two options, with different failure behaviour:

| | Switch mirror or tap | Capture inside the feed handler |
|---|---|---|
| Can it slow trading? | No — it is a different device | Only if written badly; a full ring must drop |
| Sees what the handler missed? | Yes | No |
| Cost | capture hardware, a port per line | an SPSC ring and a writer thread |

The tap is the authoritative choice. If capture runs inside the handler instead, decide in advance what may be lost — the loss policy [Design a Log Publishing and Query System](../sd-log-publishing-query/question.md) sets for diagnostic logs — and apply it with care. The hot path still never blocks, but a capture gap is recorded explicitly, and research datasets covering it are flagged as incomplete.

**Deterministic replay.** Feed captured packets, with their original NIC timestamps, through the same feed-handler binary, driven by a replay clock instead of the wall clock. The normalized output must match the live run event for event. That makes replay a regression test for every decoder change and the first tool in any incident ([Handbook Ch 31](../../../release1/handbook-markdown/chapters/e4-deterministic-replay/chapter.md)).

**Protocol changes.** Venues publish new protocol versions with notice. Key decoder versions by venue, protocol version, and effective date. Every research dataset records which decoder version built it, so a number in a backtest can always be traced back to the bytes and the code that produced it. Releasing a new decoder follows the same process as a news adapter in [Design a News Feed System](../sd-news-feed/question.md): replay captured traffic, diff the output, run in shadow mode.

**What to watch.** Most of these metrics exist because a failure here is silent:

| Metric | Why it matters |
|---|---|
| Gaps per channel, recovery time | how often, and how long, books were untrusted |
| A/B arrival skew | a line degrading before it fails |
| Ring occupancy high-water mark, per consumer | which strategy is close to being cut off |
| NIC drop counters | loss before our code ever saw the packet |
| NIC-to-publish latency percentiles | our own contribution to latency, measured by hardware timestamps |
| Heartbeat age, stale instrument count | silence that looks like a quiet market |

**If it cannot be replayed, it cannot be debugged — and the capture path must never be able to slow the live one.**

## Interview calibration

**A passing answer**

- Receives multicast, decodes, normalizes, and delivers through a lock-free queue.
- Detects gaps with sequence numbers and mentions retransmission or snapshots.
- Separates storage from the live path.

**A strong answer also**

- Does the per-message budget arithmetic and shards by channel because of it.
- Arbitrates A and B lines, and contains gaps per channel.
- Publishes trust state in-band and explains why publishing nothing beats publishing a wrong book.
- Distinguishes retransmission from snapshot recovery and knows cold start is snapshot recovery.
- Cuts off slow consumers instead of letting them stall the producer.
- Makes replay deterministic and treats capture loss as a visible event.

## Follow-ups

**A strategy starts at 10:00, in the middle of the session. How does it get a correct book?**

> Cold start is snapshot recovery with an infinite gap. The strategy reads the feed handler's current book snapshot, stamped with a sequence number, then consumes events after that number from its ring. If the feed handler itself restarts, it does the same against the venue's snapshot channel. Handbook Ch 23 makes the point directly: build cold start and gap recovery as one code path.

**You run two feed-handler hosts hot-hot for failover. Do they publish identical data?**

> The same events in the same sequence, but with different timing and possibly different gaps. On failover, a consumer switches to the standby's stream and discards what it has already seen by `(channel, sequence)` — the arbitration move again. The standby must already be `LIVE`, with warm books, or failover becomes a cold start.

**The venue announces a new protocol version next month. What do you do?**

> Write a new decoder version keyed by effective date. Replay the venue's published sample or test-environment traffic through it, diff the normalized output against the old decoder where the formats overlap, and run it in shadow mode on the first live day. Research datasets record which decoder version built them.
