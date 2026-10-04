# Design a Log Publishing and Query System

> **Level:** Intermediate · 45 minutes
>
> **You will learn:** handing off the hot path · batching · partitioned logs · indexing for the query · deciding what may be lost
>
> **Related questions:** [Design a Notification System](../sd-notification-system/question.md) · [Design a Low-Latency Market Data Feed and Normalization System](../sd-market-data-feed/question.md)
>
> **Handbook:** [Ch 10 — *The Handoff That Cannot Block*](../../../release1/handbook-markdown/chapters/b2-spsc-ring-buffer/chapter.md) · [Ch 24 — *When the Market Outruns You*](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md) · [Ch 25 — *Whose Clock Was That?*](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md)

## The question

> Design a log publishing and query system.

At a trading firm, the publishers are C++ trading processes — strategies, risk checks, gateways, feed handlers — on a hundred or so hosts. The readers are engineers in the middle of an incident: "show me everything that happened to order 8812 between 09:30:00 and 09:30:05, on every host it touched."

**The crux: logging must cost the trading thread almost nothing and never block it, while one order's story stays findable across the fleet within seconds.**

> **Finance lens.** The consumer-tech version of this question is a log platform like an ELK stack or Datadog: the hard part is ingest scale and full-text search, and the cost of one log call is invisible next to a 50 ms web request. In a trading process, a log call on the order path that takes a few microseconds is a measurable cost on every order, and a log call that *blocks* during the open is an outage. Here, the producer is half the problem.

## Requirements

### Functional requirements

1. Trading processes publish log events with negligible impact on their latency.
2. Engineers query by time range plus labels (host, service, process, severity) and fields (order ID, symbol), with free-text matching inside the result.
3. Engineers can live-tail a service: new events appear within about 5 seconds.

Out of scope: metrics and tracing, alerting on log patterns, and the regulatory audit trail (we will see why it needs a separate path).

### Non-functional requirements

Assume 100 trading hosts, each averaging 10,000 events per second and bursting to 5× that at the open. A binary event is about 100 bytes.

| | Average | Peak (the open) |
|---|---|---|
| Events per host | 10,000/s | 50,000/s |
| Fleet events | 1 M/s | 5 M/s |
| Fleet bytes (binary) | 100 MB/s | 500 MB/s |
| One trading day (8 h) | ≈ 30 billion events, ≈ 3 TB raw, ≈ 600 GB compressed | |

Per host, 5 MB/s at peak is easy to move. **The hard parts are the producer cost and finding a needle in 30 billion events a day**, not bandwidth.

1. **Producer cost.** A log call on a hot thread takes tens of nanoseconds: no formatting, no allocation, no lock, no system call. It never blocks.
2. **Freshness.** Events are searchable within 5 seconds in normal operation.
3. **Query latency.** A query for one order over a few minutes returns within a few seconds.
4. **Retention.** 30 days searchable; older data in cheap storage.
5. **Overload.** Under a burst the system may drop diagnostic events, but it must never slow trading, and every drop must be counted.

## Core entities

- **Log event** — timestamp, host, process, thread, per-thread sequence number, severity, a format ID, and the raw argument values.
- **Format registry** — maps each format ID to its format string and argument types, so binary events can be decoded later.
- **Stream** — the ordered sequence of events from one thread or process on one host.
- **Chunk** — a compressed block of one stream's events covering a short time range: the unit of storage and of reading.
- **Chunk index** — for each chunk: its labels, time range, and a compact summary of which order IDs and symbols it contains.

The idea to notice is the **format ID**. The hot thread does not produce text. It records "format 417 with arguments 8812, 101.25, 300", and formatting into "order 8812 acked px=101.25 qty=300" happens later — on another thread, or only when someone reads it.

## API

Three interfaces serve three callers. Inside the trading process, the log call looks like any formatted log line:

```text
log_info("order {} acked px={} qty={}", order_id, px, qty)
    at startup:    the format string is registered once, under a format_id
    on each call:  the thread writes { timestamp, format_id, order_id, px, qty } into its own ring
```

Between a host and the platform, batches carry their own identity:

```text
PushBatch { host, stream, first_seq, last_seq, compressed_events }  ->  Ack { last_seq }
```

For engineers, a query and a live tail:

```text
GET /logs?from=09:30:00&to=09:30:05&service=gateway&order_id=8812&level>=WARN&q="reject"
GET /logs/tail?service=strategy-7
```

`first_seq` and `last_seq` matter more than they look. They let the collector recognise a batch it has already stored when an agent retries. That is an idempotency key — an identity that stays the same on every retry, so a unique constraint turns the retry into a no-op — named here by a sequence range. [Design a Notification System](../sd-notification-system/question.md) builds the same move for callers that retry.

## High-level design

### 1) Publish without hurting the trading thread

The naive version writes formatted text through a shared logger. Formatting a price can cost hundreds of nanoseconds, a `write` system call a microsecond or more, and a full disk buffer can stall for milliseconds. All of that would land on the order path.

Instead, split the work:

1. The hot thread reads the CPU timestamp counter, then copies the format ID and raw arguments into **its own** preallocated single-producer, single-consumer ring.
2. A logger thread, pinned to a housekeeping core, drains every thread's ring.
3. It appends binary records to a local file, one per process.

![Each hot thread copies a small binary record into its own ring; a logger thread on a housekeeping core drains the rings and appends to a local file.](../../../generated/diagrams/sd-log-publishing-query/step1-in-process.svg)

Why one ring per thread rather than one shared queue? With a shared multi-producer queue, every hot thread contends on the same cache line to claim a slot — exactly the contention Handbook Ch 12 examines. A single-producer ring needs one release store to publish an entry, and the producer never waits for anyone ([Handbook Ch 10 — *The Handoff That Cannot Block*](../../../release1/handbook-markdown/chapters/b2-spsc-ring-buffer/chapter.md)).

The ring's memory is allocated and touched at startup, so the first busy minute does not take page faults ([Handbook Ch 16 — *Never Ask the Allocator During Market Hours*](../../../release1/handbook-markdown/chapters/c2-preallocation-and-pools/chapter.md)). The logger thread is pinned away from the isolated trading cores so its file I/O never competes with them ([Handbook Ch 19 — *Where Your Thread Actually Runs*](../../../release1/handbook-markdown/chapters/c4-thread-affinity/chapter.md)).

> **Design move — Hand off the hot path.** The latency-critical thread writes a small fixed-size record into a preallocated SPSC ring; another thread does the slow work. *Cost:* the ring can fill, and you must decide in advance what happens then.

Writing to a local file first means accepting durably before doing the slow work — the move [Design a Notification System](../sd-notification-system/question.md) develops for a service, applied here at host scale. Once an event is in the file, a network or collector outage cannot lose it, and the trading process never waits for anything off the host.

### 2) Ship logs off the host

1. A shipping agent on each host tails the local files.
2. It closes a batch at 1 MB or 200 ms, whichever comes first, compresses it, and sends `PushBatch` to a collector.
3. The collector appends the batch to Kafka, partitioned by host and stream.
4. The collector acknowledges `last_seq`, and the agent advances its checkpoint.

![Agents tail local files, batch by size or time, and push to collectors over the management network; collectors append to Kafka and acknowledge the last sequence number.](../../../generated/diagrams/sd-log-publishing-query/step2-shipping.svg)

Batching is what makes the fleet manageable. Without it, the open would mean 5 million network sends per second. With 200 ms batches, each host sends about 5 requests per second at peak: **500 requests per second for the whole fleet**, each carrying about 1 MB.

> **Design move — Batch to amortize fixed costs.** Pay per-request overhead once per batch, and close a batch on size *or* time. *Cost:* each event waits up to the time bound — here 200 ms, well inside the 5-second freshness target.

Kafka gives us the partitioned log we want between collection and indexing. Each partition is an append-only sequence; indexers read at their own pace; a slow indexer falls behind without slowing the collectors. Order is guaranteed within a partition, which is all we need, because each stream's order is already defined by its sequence numbers.

> **Design move — Partitioned append-only log.** Append records to a log split by key; consumers read at their own pace, and order holds within a partition. *Cost:* there is no global order across partitions, and a hot key makes a hot partition.

Two details matter at a trading firm. The agent sends over the **management network**, never the NIC that carries orders or market data. And when a collector is down, the agent retries with exponential backoff and jitter, so a fleet of agents does not hammer a recovering collector in lockstep, while the local file absorbs the gap.

### 3) Make it searchable

1. Indexer consumers read Kafka and group each stream's events into chunks: up to 4 MB compressed or 1 minute, whichever comes first.
2. They write each chunk to storage — SSD for recent days, object storage for older ones.
3. They write one small index entry per chunk: labels, time range, severity counts, and a Bloom filter of the order IDs and symbols inside.
4. The query service uses the chunk index to find candidate chunks, fetches only those in parallel, decodes, filters, and merges by time.

![Indexers turn Kafka partitions into compressed time-bounded chunks plus a small chunk index; the query service finds candidate chunks first, then fetches only those.](../../../generated/diagrams/sd-log-publishing-query/step3-query.svg)

The design choice here is *what not to index*. We do not build an index of every word in every message. We index the handful of things engineers filter on, and scan inside the chunks that survive. Grafana Loki is built on this idea; Elasticsearch takes the opposite approach and indexes every token. The deep dive compares them.

> **Design move — Store by time, index what people filter on.** Partition storage by time, index only the fields queries filter on, and move old data to cheaper tiers. *Cost:* a query on an unindexed field becomes a scan.

Live tail is a shortcut through the same pipeline: the query service subscribes to the relevant Kafka partitions and decodes events as they arrive, skipping chunk storage entirely.

### What is still broken

1. **The open.** What happens when the ring, the disk, the network, or the indexers fall behind?
2. **Finding one order.** Does pruning by labels and Bloom filters really get a fleet-wide search down to seconds?
3. **Ordering across hosts.** The merged view sorts by timestamp — but whose clock produced it?

## Deep dives

### 1) What happens when logs arrive faster than we can move them?

At 09:30:00 the busiest strategy host jumps from 10,000 to 120,000 events per second. At the same moment its logger thread stalls for 40 ms while the operating system flushes dirty pages, and one collector is restarting.

Walk the pipeline from the hot thread outward. Each layer has a buffer, a job, and a rule for when that buffer is full:

| Layer | Buffer | Absorbs | When full |
|---|---|---|---|
| Hot thread → logger thread | SPSC ring, 65,536 slots × 128 B = 8 MB per thread | logger stalls up to ~0.5 s at 120 k/s | **drop the event and count it — never block** |
| Logger → agent | local disk, hours of logs | collector or network outages | alert; delete oldest diagnostic files first |
| Collectors → indexers | Kafka retention, 24 h | indexer lag, re-indexing after a bug | add indexers; search freshness degrades, visibly |

The 40 ms stall needs 120,000 × 0.04 ≈ 4,800 slots, a small fraction of the ring. The ring would overflow only if the logger thread stalled for over half a second at full burst. A buffer buys time, not capacity: size each one from the stall it must survive, and accept that a longer stall still overflows it. [Design a Notification System](../sd-notification-system/question.md) works through the same arithmetic for an alert storm.

When the ring *is* full, the hot thread has two options: wait or drop. Waiting means a log call can stall an order, which is never acceptable. So the hot thread drops the event and increments a per-thread drop counter.

The logger thread later writes a synthetic event — "thread 3 dropped 1,204 events between 09:30:00.412 and 09:30:00.988" — so the gap shows up in every query that covers it. Handbook Ch 24 calls this choosing what to lose: decide before the overload, not during it.

**A log call must never block the trading thread. Decide in advance what you may drop, and make every drop visible.**

That rule is only safe because these are *diagnostic* logs. Some records must never be dropped: orders sent, acknowledgements, fills, risk decisions. Those are the firm's authoritative record, used for audit, reconciliation, and replay ([Handbook Ch 31 — *What Did It See, and Why Did It Do That?*](../../../release1/handbook-markdown/chapters/e4-deterministic-replay/chapter.md)). They go through a separate capture path with the opposite rule: if it cannot record, it alerts and the desk's policy decides whether to stop trading.

> **Design move — Decide what may be lost.** Under overload, drop or sample what is diagnostic and never drop what is authoritative; give each its own path. *Cost:* two paths to build and operate.

It is priority lanes in another form: different classes of traffic get different paths and different overload rules, so the cheap class can never starve the critical one. [Design a Low-Latency Market Data Feed and Normalization System](../sd-market-data-feed/question.md) builds the authoritative capture path for market data.

### 2) How do we find one order's story across the fleet in seconds?

At 09:31:07 a client asks why order 8812 was rejected. The engineer searches for `order_id = 8812` from 09:30 to 09:32 across the strategy, risk, and gateway services.

Three storage designs could serve this:

| | Full inverted index (Elasticsearch, OpenSearch) | Label index + chunk scan (Loki) | Columnar store (ClickHouse) |
|---|---|---|---|
| Index | every token in every event | labels per stream | sort key, plus optional skip indexes |
| Ingest cost | high: index work per event | low | medium |
| Storage overhead | large | small | small, compresses well |
| Fast at | arbitrary text search | label + time queries | aggregations, typed columns |
| Weak at | cost at billions of events per day | high-cardinality fields like order IDs | free text |

Order ID is the awkward field. It is high-cardinality — millions of distinct values a day — so putting it in a label index explodes that index, and a full inverted index pays to index every token of every event to answer it.

The middle path is a **Bloom filter per chunk**: a few kilobytes that answer "might this chunk contain order 8812?" with no false negatives and a tunable false-positive rate. Watch how much each stage discards:

![A fleet-wide two-minute window holds about 600 million events; the label filter keeps about 300 chunks; per-chunk Bloom filters keep about 10; only those are decoded.](../../../generated/diagrams/sd-log-publishing-query/dd2-pruning.svg)

At a 1% false-positive rate, about 3 of the 300 candidate chunks are read for nothing — a cheap price. The query fetches roughly 40 MB instead of 60 GB, and decoding 40 MB across a few workers takes well under a second.

**Index the few fields people filter on; scan everything else inside a narrow window.**

Free text then runs only over the decoded survivors. A search for the word "reject" across all 30 days with no labels is still a scan, and the query service should say so up front rather than time out silently.

### 3) Whose timestamp do we sort by?

The merged view for order 8812 shows the gateway's "order sent" 3 µs *before* the strategy's "decided to send". That is impossible, and it happens because each event was stamped by a different host's clock.

Three kinds of order exist here, and they have different strengths:

| Order | Source | Trust it for |
|---|---|---|
| Within one thread | per-thread sequence number | exact order, always |
| Across hosts, by time | each host's clock, synchronised by PTP | order only when events are further apart than the clock error |
| Across hosts, by cause | IDs carried in the events (order ID, client order ID) | "this happened because of that" |

Even well-run PTP leaves clocks differing by a fraction of a microsecond to a few microseconds; NTP-synchronised hosts can be milliseconds apart. In a consumer-tech log tool nobody notices. When you are reconstructing a microsecond sequence of an order's life, it decides whether the story makes sense.

So the query service merges by timestamp but shows each host's current clock-error estimate, and it never reorders events within a stream. For cause and effect, follow the IDs. Handbook Ch 25 explains which timestamp subtractions are legal across clocks, and why ordering is a separate problem from synchronisation ([Ch 25 — *Whose Clock Was That?*](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md)).

One implementation detail pays off: store the raw CPU timestamp-counter value in each event, along with the logger thread's periodic calibration pairs of (counter, wall clock). Converting to wall-clock time then happens at read time and can be redone if the calibration was wrong.

## Interview calibration

**A passing answer**

- Ships logs asynchronously through agents, a queue, and an indexed store.
- Batches transfers and partitions storage by time.
- Mentions retention tiers and basic overload handling.

**A strong answer also**

- Treats the producer as the hard part: per-thread rings, binary records with deferred formatting, a pinned logger thread.
- States the never-block rule and makes drops countable.
- Separates diagnostic logs from the authoritative order record, with opposite overload rules.
- Explains why order IDs fit a per-chunk Bloom filter better than a label index, with the pruning arithmetic.
- Knows that cross-host timestamps are only as good as clock sync, and orders by cause using IDs.

## Follow-ups

**The trading process crashes. Which logs are lost?**

> Events already in the local file survive. Events still in the in-memory rings are lost. If that matters, put the rings in a shared-memory file and run the logger as a separate process: the rings outlive the crashed producer and the logger drains them. Shared memory survives a process crash, not a host crash ([Handbook Ch 18 — *Counting the Copies*](../../../release1/handbook-markdown/chapters/c6-mmap-and-zero-copy/chapter.md)).

**Why not use an off-the-shelf asynchronous logger?**

> Measure it first. General-purpose asynchronous loggers are built for convenience; many still format the message on the calling thread or share one queue across threads behind a lock. Benchmark the p99 of the log call under a burst on your hardware. A per-thread binary ring is a design whose worst case you can reason about. The NanoLog paper (Yang, Park, and Ousterhout, USENIX ATC 2018) describes this deferred-formatting approach in depth.

**Compliance asks for seven years of order history. Do we keep these logs for seven years?**

> No. Order history belongs to the authoritative record path, written to immutable storage with its own retention. Diagnostic logs keep 30 days. Different retention, different loss rules, and different readers are exactly why the two paths are separate.
