# Design a Low-Latency Market Data Feed and Normalization System

## Interview prompt

Design a colocated market-data platform that receives redundant UDP multicast
feeds, preserves venue ordering, recovers packet gaps, normalizes events, serves
latency-sensitive trading clients, and supplies reliable historical data to
researchers.

**Scope this explicitly before drawing.** The complete platform is larger than
one interview. Show the end-to-end boundary, then ask the interviewer which
parts to develop. A realistic discussion usually goes deep on one or two
components. This tutorial develops three because they contain the most reusable
engineering judgment:

1. isolating the trading hot path from capture and research pipelines;
2. applying low-latency techniques to ingestion and delivery;
3. preserving correctness through A/B arbitration and gap recovery.

Protocol evolution, replay, and artifact storage still appear where they change
the design, but they are not separate tutorials.

## Prerequisite refresh, not repeated theory

This chapter assumes the reader knows the underlying mechanisms. Review the
companion handbook only where needed:

- [Trading-system data flow](../../../release1/handbook-markdown/chapters/a1-system-data-flow/chapter.md)
  for the exchange-to-strategy context.
- [Busy spinning and hybrid waiting](../../../release1/handbook-markdown/chapters/b5-waiting-strategies/chapter.md)
  and [SPSC ring buffers](../../../release1/handbook-markdown/chapters/b2-spsc-ring-buffer/chapter.md)
  for thread handoff mechanics.
- [Market-data protocols](../../../release1/handbook-markdown/chapters/d1-market-data-and-protocols/chapter.md)
  and [sequence-gap recovery](../../../release1/handbook-markdown/chapters/d3-sequence-and-gap-recovery/chapter.md)
  for wire-level foundations.
- [Kernel bypass](../../../release1/handbook-markdown/chapters/d6-kernel-bypass/chapter.md)
  for DPDK, AF_XDP, and user-space networking concepts.
- [Deterministic replay](../../../release1/handbook-markdown/chapters/e4-deterministic-replay/chapter.md)
  for incident reconstruction and reproducible datasets.

The interview question is how to compose these techniques under a concrete
latency, loss, and operability contract.

## What the interviewer is testing

- Can the candidate narrow an oversized system while keeping the important
  boundaries visible?
- Can they protect the latency-critical path from storage, research, recovery,
  and slow-consumer work?
- Do they understand redundant lines, sequence authority, retransmission, and
  snapshot recovery well enough to state correctness invariants?
- Can they choose between standard sockets, busy polling, AF_XDP, DPDK, and
  different ring topologies from measurements rather than fashion?
- Do they preserve enough raw evidence and version information to reproduce
  what a strategy saw?

## Clarifying questions

- What exactly is timed: NIC arrival to normalized event, book update, or
  strategy read? What percentile and peak-rate target matter?
- Which venue protocols, channel counts, peak packet rates, and sequencing
  scopes must the first version support?
- Are A and B logically equivalent streams? Which retransmission and snapshot
  services does the venue provide?
- Must trading clients see only a contiguous feed, or may some consume marked
  stale data? What happens to a slow client?
- How complete and how fresh must research data be? Is raw-packet replay a hard
  audit requirement or an operational aid?
- Which deep dives should dominate this interview: path isolation, receive and
  delivery latency, or recovery?

## Core requirements and assumptions

### Trading path

- Receive and validate redundant multicast lines.
- Publish each logical event at most once and in venue sequence order.
- Decode versioned wire messages into a stable canonical representation.
- Deliver to colocated consumers without a slow consumer blocking ingestion.
- Expose explicit `LIVE`, `RECOVERING`, and `STALE` health state.

### Recovery and evidence

- Fill bounded gaps from the alternate line, retransmission, or a snapshot.
- Retain raw packets and the artifacts needed to decode and replay them.
- Detect incomplete capture rather than silently claiming a lossless archive.

### Research path

- Produce query-efficient historical data without coupling research load to
  live trading.
- Preserve exchange time, receive time, sequence provenance, and corrections.
- Support reproducible dataset versions rather than mutable "latest truth"
  alone.

Assume one primary writer owns each venue channel. Scaling is by assigning
channels to cores or processes, not by allowing several threads to mutate one
sequence state machine.

## Candidate reasoning: establish boundaries before components

The hard tension is not simply "make parsing fast." Trading wants bounded work,
current data, and predictable tail latency. Research wants complete history,
rich metadata, recomputation, and throughput-efficient storage. Recovery may
need network requests and seconds of buffered state. Combining those concerns
in one queue or process lets a slow disk, schema migration, or research query
become a trading outage.

Start with four invariants:

1. A logical sequence is published at most once.
2. A strict stream never advances past an unresolved gap.
3. No research, persistence, recovery, or client operation can wait on the RX
   loop.
4. Every published event can be tied to raw input, session and sequence,
   decoder version, configuration generation, and channel-health epoch.

These invariants naturally produce separate execution planes joined only by
bounded, observable handoffs.

## Good solution

### End-to-end architecture

![The trading hot path is isolated from recovery, durable capture, and research processing.](../../../generated/diagrams/sd-market-data-feed/architecture.svg)

The latency-critical plane owns NIC queues, channel state, decoding, and live
publication. The recovery plane may supply missing packets but must re-enter
through the same sequence gate. A capture plane drains a bounded handoff into
append-only local segments and immutable artifact storage. Research processing
reads those durable objects, never live RX memory.

Keep the hot-path event envelope compact but sufficient:

```
venue, channel, session, logical_sequence
exchange_timestamp, hardware_receive_timestamp
message_type, wire_schema_version, canonical_schema_version
health_epoch, source_line, payload_or_packet_reference
```

The `health_epoch` changes on restart, recovery, failover, or resync. Consumers
can therefore distinguish an ordinary sequence from one produced after a state
transition.

### Deep dive 1: isolate the trading and research pipelines

#### Define the latency boundary

The hot path performs only work needed before a trading consumer can act:

1. poll a designated RX queue and obtain packet metadata;
2. validate bounds, session, channel, and packet sequence/count;
3. arbitrate A/B copies and pass data through the contiguous sequence gate;
4. decode the required fields into a compact canonical event or update a local
   book;
5. publish to bounded client transport and update cheap per-core counters.

No disk call, compression, object-store RPC, database write, schema-registry
lookup, heap allocation, formatted log, or research transformation belongs in
that loop. Configuration and decoder tables are prepared off-path and swapped
at controlled boundaries.

"Asynchronous" alone is not isolation. Each handoff needs a fixed owner, finite
capacity, and a full-queue policy. The RX thread should write a descriptor or
compact event into preallocated memory and continue. Downstream workers own
compression, checksums, storage retries, indexing, and telemetry export.

#### Capture once, derive many times

Persist the closest practical representation to the wire. A raw log segment
contains an immutable header plus packet records:

```
segment: venue/channel/session, capture host, clock source,
         start/end sequence, start/end receive time, format version
packet:  line, sequence range, hardware/software timestamps,
         captured length, original bytes, integrity checksum
```

Write large sequential segments on a dedicated capture core or host, seal them
with counts and a checksum, then upload them to replicated object storage. A
manifest records gaps, duplicate-line coverage, decoder build, schema package,
configuration generation, and clock-health intervals. The manifest must say
"incomplete" when capture lost data; storage success is not proof of feed
completeness.

There are two defensible capture topologies:

- A bounded tap from the receiver is simple and preserves the exact bytes the
  trading process observed. If its ring fills, trading continues and capture
  completeness is marked broken.
- A separate packet-capture queue, process, or network tap gives persistence
  independent resources and may be engineered as lossless. It must still be
  reconciled by session and sequence because it may observe a different A/B
  arrival order from the trading receiver.

Do not make live publication wait for durable storage unless the business
contract explicitly prefers a trading halt to an audit gap. That choice should
be stated, not hidden in a supposedly reliable queue.

#### Build research data after durability

An offline decoder reads sealed raw segments and produces versioned normalized
datasets, commonly columnar files partitioned by trading date, venue, and feed.
Avoid extremely fine partitions such as one file per symbol; they create small
file and metadata costs. Compaction, richer validation, book reconstruction,
and cross-venue enrichment can use large batches because they no longer affect
packet-to-trade latency.

Preserve at least three time domains: exchange event time, local receive time,
and transformation time. Keep source session/sequence and raw-segment identity
with every derived row. Corrections are appended as a new dataset version or
validity interval; overwriting old rows destroys the ability to reproduce what
a researcher or strategy knew at an earlier point.

A dataset release is a manifest over immutable inputs and artifacts:

```
raw segment IDs + schema/decoder versions + transform build/config
-> normalized file IDs + validation report + completeness interval
```

Research jobs consume a named release, not whichever files happen to be
present. This makes historical results repeatable and allows a corrected
decoder to publish a new release without mutating the old one.

#### Backpressure and failure isolation

Every crossing has an explicit degradation policy:

- A trading client that falls behind is disconnected, switched to recovery, or
  detects overwrite; the producer never waits.
- A capture writer that falls behind raises a completeness incident and may
  fail over to a reserved capture path; it does not borrow the RX core.
- Research backlog changes data freshness, not live trading health. Autoscaling
  and storage retries happen entirely after sealed raw objects exist.

Separate process address spaces and CPU sets are useful because a logical queue
boundary does not prevent allocator contention, page faults, CPU throttling, or
an out-of-memory kill from crossing the boundary. At minimum, reserve cores and
memory for the live plane and cap the queues and caches used by the other
planes.

### Deep dive 2: engineer the ingestion and delivery path

#### Choose an ingress tier from the budget

Start with a measured baseline rather than declaring DPDK mandatory:

- Standard UDP sockets can be strong enough with NIC receive queues, RSS or
  hardware flow steering, IRQ affinity, large but bounded socket buffers,
  batched reads, and pinned receiver threads.
- NAPI socket busy polling removes some wake-up delay by spending a dedicated
  core polling for work. It improves latency only when queue, IRQ, and thread
  placement are coherent; it also consumes power and CPU continuously.
- AF_XDP redirects selected NIC queues into user-space UMEM rings and can reduce
  copies while retaining Linux control-plane integration.
- DPDK poll-mode drivers let the application poll NIC descriptors directly and
  manage packet memory. They can reduce kernel-path variability but add device
  ownership, huge-page, deployment, observability, and failover work.

Escalate only when stage timestamps show the kernel receive path is material to
the unmet percentile target. Kernel bypass cannot fix a slow decoder, remote
NUMA access, a shared consumer queue, or an overloaded strategy.

#### Make ownership and topology obvious

Assign one receiver thread to one or more RX queues whose channels fit its
peak-rate budget. Pin the thread, its packet pool, and client-ring memory to the
NIC's NUMA node. Pre-fault memory, preallocate packet and event objects, use
fixed-capacity gap buffers, and keep frequently written counters away from
read-mostly configuration and other cores' counters.

A run-to-completion loop—receive, arbitrate, decode, publish on one core—avoids
handoffs and is the default when parsing is bounded. Split stages only when
measurement shows variable decode/book work can starve RX draining. The new
queue then buys isolation at the cost of a cache transfer, another capacity
limit, and additional ordering state.

Do not perform general virtual dispatch or a schema lookup for each field.
Select the decoder once per session/template and call generated or table-driven
code with bounds checks. Batch enough packets to amortize descriptor and API
cost, but cap both batch size and loop time so one busy channel cannot delay
another.

#### Bound burst work and expose overload

The poll loop needs a fairness rule as well as a fast steady state. Drain at
most a configured packet burst or cycle budget from one RX queue before checking
the next owned queue, recovery input, and control generation. A permanently
busy channel must not starve heartbeats or a quieter channel. Record how often
the loop hits its budget; that counter reveals saturation before average CPU
utilization does.

When offered load exceeds sustainable decode and publish capacity, correctness
comes before graceful-looking latency. Surface NIC and socket/PMD drop counters,
let missing sequence numbers trigger recovery, and mark the channel stale if
the bounded window is exceeded. It is acceptable to shed sampling, detailed
telemetry, or a best-effort consumer. It is not acceptable to skip an
incremental book update and continue presenting the book as current.

Treat host configuration as part of the deployed data plane. Verify RX queue
steering, IRQ or poller affinity, SMT-sibling usage, CPU frequency policy,
memory locking, page prefaulting, and NUMA allocation on the target host. These
are benchmark inputs, not universal incantations. Record them with the binary
and compare latency histograms after firmware, kernel, BIOS, or hardware
changes.

Use a hardware RX timestamp when the NIC and clock contract support it, then a
cheap monotonic CPU timestamp around arbitration, decode, and publication.
Export or aggregate samples off-path. The point is to locate queueing and
variance without turning every event into a logging operation.

#### Deliver without consumer interference

![Bounded ring delivery gives each consumer an explicit cursor and recovery policy.](../../../generated/diagrams/sd-market-data-feed/delivery-rings.svg)

For a small number of colocated strategies, one SPSC shared-memory ring per
consumer is the clearest interview baseline. The publisher copies a compact
canonical event into each ring, writes the payload before a release publication
of its sequence, and never waits for a consumer. The consumer acquire-loads the
published sequence before reading the slot. Keep producer and consumer cursors
on separate cache lines and include stream sequence, health epoch, event length,
and schema version in each slot.

Per-consumer rings make lag and disconnect policy independent but multiply
publisher writes. When fan-out is large, a shared append-only ring can publish
one copy with a cursor per consumer. The producer still must not read or wait on
all consumer cursors. A lagging consumer detects that its expected sequence has
been overwritten and resynchronizes from replay or a snapshot. This topology
trades copies for more complex lifetime and overwrite semantics.

Avoid a reference-counted packet object whose last reader returns memory to the
RX pool: every consumer then writes the same cache line and a stopped consumer
can retain scarce buffers. Either copy the small normalized event, use a
producer-owned overwrite ring, or transfer descriptors into a separately sized
pool with an explicit reclamation scheme.

Busy-spin only the dedicated consumers whose latency budget justifies a core.
Hybrid wait or block research, monitoring, and recovery consumers. Queue depth,
oldest unread age, overwrite/disconnect count, and consumer generation must be
observable without synchronous logging from the producer.

### Deep dive 3: arbitration and gap recovery

#### A/B line arbitration

Consume A and B hot-hot. They carry logically equivalent data over independent
paths, so a missing A packet may already be available on B. Active/idle failover
throws away that latency and recovery advantage.

Maintain per channel/session:

```
expected_sequence
bounded out-of-order packets keyed by logical sequence
per-line last sequence, last receive time, and loss/duplicate counters
state: LIVE | RECOVERING | STALE
recovery range, deadline, and health epoch
```

For each valid packet:

- sequence below `expected_sequence`: count and discard the duplicate;
- sequence equal to `expected_sequence`: accept it, advance, and drain any
  contiguous buffered packets;
- sequence above `expected_sequence`: buffer it within a fixed window and open
  or extend the missing range.

Accepting the first valid copy minimizes latency. Do not compare every duplicate
payload on the RX core. Sample or compare asynchronously. If A and B claim the
same logical sequence with different bytes, preserve both, quarantine the
channel, and stop advertising it as healthy.

Do not assume one datagram equals one sequence. Some protocols number messages
and carry a first sequence plus a message count in each packet. The
protocol-specific framing adapter should emit a validated logical range; the
common sequence gate advances over its messages. A truncated packet is invalid
rather than a partially useful range unless the venue specification says
otherwise.

Session changes are also ordering boundaries. Fence the old session, clear its
bounded reorder state, install the new session's starting rule, and publish a
new health epoch. Comparing sequence numbers across daily resets or reconnects
without the session identity can turn a valid restart into a duplicate storm or
a false gap.

#### Recovery state machine

![Sequence gap detection and recovery without pausing the live feed.](../../../generated/diagrams/sd-market-data-feed/gap-recovery.svg)

The live receiver continues draining both multicast lines while another
component repairs the missing range:

1. First consume a valid alternate-line copy already in the bounded buffer.
2. Otherwise request exactly the still-missing range from the venue's
   retransmission service, coalescing overlapping requests.
3. Send replay packets through the same session, sequence, and decoder checks
   as live packets; one sequence gate merges replay and buffered live traffic.
4. Publish only the newly contiguous prefix. Duplicates from overlapping live
   and recovery traffic cannot publish twice.
5. If the gap exceeds the time/window limit, retransmission is unavailable, or
   recovery data fails validation, mark the channel `STALE` and snapshot-resync.

Snapshot recovery needs a sequence boundary. Build a candidate book from the
snapshot, note its `last_processed_sequence`, discard buffered increments at or
below that boundary, and apply the contiguous suffix. Validate book invariants
and atomically publish the new book generation before returning to `LIVE`.

The client contract is explicit. A strict trading feed pauses publication at
the gap but continues receiving. A separate best-effort feed may expose
post-gap events only when each carries a visible stale flag and recovery epoch.
Never apply post-gap deltas to a book still labeled healthy.

### Protocol and schema evolution: mention, then make it safe

Treat the wire protocol and canonical model as two versioned contracts. A
decoder registry is keyed by venue, feed/session, message template, and wire
schema version. Generated decoders validate packet bounds and required fields;
unknown messages are counted and retained raw rather than guessed.

The canonical schema should stabilize common downstream semantics without
erasing venue-specific information. Carry a canonical version and an extension
or raw reference for fields that cannot be represented safely. Avoid changing
an in-process shared-memory layout underneath running consumers; publish a new
version or ring generation and migrate consumers explicitly.

Before activation, replay golden and recent raw segments through the new
decoder, shadow-decode live traffic, compare canonical outputs and book state,
then switch at a recorded session/sequence boundary. Keep the old decoder and
schema artifacts addressable so historical replay uses the interpretation that
was actually deployed.

### Deterministic replay and artifacts: preserve decisions, not only bytes

Raw packets are necessary but not sufficient. Reproducing the emitted stream
also needs the decoder binary or build identity, wire and canonical schemas,
instrument/reference data, configuration generation, clock-health record, and
any arbitration decision that depended on A/B arrival order.

Replay should use a virtual clock and the same ordered state machine as live
processing while replacing NIC, timers, and recovery clients with recorded
inputs. It should produce stable event hashes, state snapshots, and a report of
gaps or non-deterministic differences. This supports incident reconstruction,
decoder regression tests, and reproducible research releases without putting a
general replay framework on the live path.

## Trade-offs and sizing

- **Latency versus evidence:** publishing before durable capture reduces
  latency but allows an audit gap on capture failure. Independent capture
  resources reduce the risk without coupling disk latency to trading.
- **Copies versus coordination:** per-consumer SPSC rings copy more bytes but
  isolate readers; a shared fan-out ring reduces copies but requires explicit
  overwrite and reclamation semantics.
- **Run-to-completion versus stages:** one core avoids handoffs; staged parsing
  protects RX draining from variable work but adds queue latency and ordering
  boundaries.
- **Kernel integration versus bypass:** sockets are easier to operate; AF_XDP
  or DPDK may improve tail latency only when the receive stack is the measured
  bottleneck.

Size every buffer from a burst or outage budget. If peak input is `P` packets/s,
average captured bytes are `B`, and recovery may take `T` seconds, a raw recovery
window needs at least `P * B * T` bytes plus indexes and safety margin. A client
ring sized for `R` events/s and a tolerated scheduling pause of `S` seconds
needs more than `R * S` slots or an explicit overwrite/disconnect policy.

For research, track durable ingest rate versus peak raw byte rate and retained
backlog, not only average transformation throughput. Storage manifests should
make complete sequence/time intervals queryable so missing data is discovered
before a backtest.

Instrument hardware receive, post-arbitration, post-decode/book, publish, and
consumer-read timestamps. Report p50, p99, and p99.9 under peak load, injected
loss, and a slow consumer. Per-stage histograms reveal whether the next useful
change is networking, parsing, placement, or delivery.

## Great solution improvements

- **Prove plane isolation under failure.** Reserve CPU and memory, bound every
  handoff, inject capture stalls and research backlog, and demonstrate that live
  latency and sequence health remain within contract while completeness alarms
  fire accurately.
- **Treat latency configuration as a deployable artifact.** Record NIC
  firmware, queue steering, IRQ/NAPI settings, CPU/NUMA placement, power state,
  binary build, and benchmark results; canary and roll back the complete
  configuration rather than only the application binary.
- **Make evidence reproducible end to end.** Seal raw logs and manifests,
  version decoder/configuration artifacts, replay A/B and recovery decisions,
  and publish immutable research dataset releases with validation results.

## Failure scenarios

- **Feed and recovery:** one line freezes, both lines lose the same range,
  packets reorder beyond the buffer, retransmission is partial, or snapshot and
  increment boundaries disagree.
- **Latency plane:** one channel monopolizes a batch, a decoder becomes
  variable-time, NUMA placement changes, a client stops, or an RX core is
  preempted.
- **Capture and research:** the journal ring fills, a segment is truncated,
  object storage is unavailable, a transform publishes partial output, or a
  correction mutates an older dataset.
- **Evolution and operations:** a venue changes template version, PTP loses
  lock, two producers claim a channel, or a deployment mixes incompatible ring
  layouts.

Each case ends in a defined action: continue on the alternate line, recover
within bounds, mark stale and resync, fence a producer, disconnect a lagging
consumer, or mark an archive interval incomplete. "Log and continue" is not a
recovery policy.

## Common pitfalls

- Trying to design the entire market-data estate instead of agreeing on the
  deep dives.
- Calling A/B redundancy active/idle failover or ordering by arrival timestamp.
- Putting storage, compression, RPC, allocation, or formatted logging in the RX
  loop.
- Saying "kernel bypass" or "lock-free" without queue ownership, topology,
  capacity, and measurement points.
- Calling an unbounded queue isolation; it merely delays coupled failure.
- Letting a slow consumer own packet lifetime or backpressure the publisher.
- Keeping normalized rows but not raw bytes and versioned decode artifacts.

## Follow-up questions

### A gap appears while both lines continue at peak rate. Walk the state changes.

The strong answer keeps draining both lines, publishes only the contiguous
prefix, uses alternate-line packets before requesting the exact missing range,
merges all arrivals through one sequence gate, and snapshot-resyncs when the
bounded recovery contract expires. Clients see an explicit recovery epoch.

### The capture writer is ten seconds behind. What happens to trading and research?

Trading never waits. A bounded capture ring either absorbs the agreed burst or
declares an incomplete interval and activates a reserved capture/failover path.
Research freshness degrades, manifests prevent incomplete data from appearing
complete, and operators scale or repair the offline plane independently.

### Would you choose sockets, AF_XDP, or DPDK, and how would clients receive data?

Choose from an end-to-end percentile budget and stage measurements. Explain NIC
queue/core/NUMA ownership, busy-poll cost, packet-pool lifetime, per-consumer
SPSC versus shared fan-out rings, full/overwrite behavior, and the operational
cost of bypass. The product name alone earns no credit.

## Evaluation rubric

- **Insufficient:** generic receive-parse-publish diagram with no sequence,
  backpressure, or failure semantics.
- **Pass:** correct hot-hot arbitration, contiguous recovery, bounded client
  delivery, and a visibly separate research path.
- **Strong:** precise hot-path work and ownership, defensible ingress/ring
  choices, durable raw evidence, schema rollout, and explicit overload policy.
- **Exceptional:** scopes the interview deliberately and connects isolation,
  latency, recovery, and reproducibility decisions to measurable contracts and
  failure tests.

## Similar questions

- `code-multi-source-stream-merger` - unseen input constrains safe ordering.
- `fund-sequence-lock` - publishing a consistent snapshot to readers.
- Design a raw-packet journal, deterministic replay, and dataset-release
  service.

## Tags

`multicast`, `feed-arbitration`, `sequence-numbers`, `gap-recovery`,
`retransmission`, `snapshot-resync`, `kernel-bypass`, `busy-polling`,
`lock-free-ring`, `schema-evolution`, `normalization`, `raw-capture`,
`research-pipeline`, `artifact-storage`, `deterministic-replay`, `numa`

### Further primary references

[Linux NAPI and busy polling](https://docs.kernel.org/networking/napi.html),
[Linux AF_XDP](https://docs.kernel.org/networking/af_xdp.html),
[DPDK poll-mode drivers](https://doc.dpdk.org/guides/prog_guide/ethdev/ethdev.html),
[FIX Simple Binary Encoding](https://www.fixtrading.org/standards/sbe-online/),
[CME MDP 3.0 recovery](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457325847/MDP%2B3.0%2B-%2BRecovery%2BServices%2Bfor%2BUDP),
and the [Nasdaq MoldUDP64 protocol](https://nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/moldudp64.pdf).
