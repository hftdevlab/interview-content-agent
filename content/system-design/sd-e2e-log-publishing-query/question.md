# Design a Log Publishing and Query System

Design patterns: Scale writes; High reliability; Time-series systems; Scale reads.

## Question and clarifications

Design a log publishing and query system. **Interpretation:** applications publish logs so engineers can search them centrally during operational investigations.

Let's follow an engineer investigating timeouts in an internal pricing service. I want us to start with the task: find recent errors across its hosts without signing into each machine. An empty result needs context: did pricing produce no errors, or have its logs stopped arriving? That gives us two connected jobs: collect the events and explain how current the searchable history is.

Three ambiguities change the design: operational logs versus an audit trail, exact-field versus arbitrary text search, and acceptable delay before a record appears. For this walkthrough, we use structured application logs from hosts we operate, service/time/severity filters, and occasional substring searches. Counted drops during a prolonged outage are preferable to blocking the application indefinitely. A complete observability platform exceeds one interview. We will develop collection and searchable storage, then examine burst capacity, recovery, and query cost; metrics, traces, alerting, and multi-region recovery stay outside that scope.

For an **illustrative workload**, assume 2,000 hosts averaging 100 records/s each, 500 bytes per record before transport compression, seven days of retention, and fleet-wide bursts of five times normal traffic for a minute. Engineers usually search fifteen-minute intervals. These are sizing assumptions, not facts supplied by the prompt. They keep high-throughput ingestion central to the design while leaving the product scope small.

## Requirements

### Functional requirements

- Collect application logs from the managed fleet into a shared searchable history.
- Search by service and time, optionally severity and message substring, with bounded pages of results.
- Show collection delays, disconnected hosts, and reported losses alongside results.

### Non-functional requirements

- Make records searchable within about five seconds during normal operation; expose increased delay during bursts and recovery.
- Sustain the illustrative average workload while engineers query and old data expires.
- Preserve centrally acknowledged records across process restarts while the owning storage disk remains intact. Host or central disk loss needs a stronger durability policy if the interviewer requires it.
- Bound local disk use and query work, keeping application availability ahead of lossless diagnostic logging during prolonged overload.
- Make recovery and overload behavior testable: a retry must not duplicate retained events, and a failed search must not look like a successful empty result.

I put recovery and honest visibility ahead of dashboard response speed here: an incident is exactly when delayed or misleading logs are most costly. A few hundred engineers can still investigate a fleet producing enormous write traffic. Our latency objective is seconds to searchable diagnostics, not microseconds to execute an order. In a finance system, this boundary matters: missing diagnostics may impair an investigation, but cannot authorize an order or establish authoritative risk state.

### What does this workload imply?

Let's turn the host estimate into rates before choosing storage. The useful distinction is between the number of requests we can batch away and the volume of records that must still be stored:

```text
2,000 hosts × 100 records/s = 200,000 records/s
200,000 × 500 bytes       = 100 MB/s
100 MB/s × 86,400 s       = 8.64 TB/day
7 days                   = 60.48 TB of raw records
5× burst                 = 1,000,000 records/s, 500 MB/s
```

All units are decimal. Compression could lower disk and network bytes, while indexes, recovery logs, and free space for maintenance raise provisioned storage. These estimates are not a server benchmark. Per-event remote requests would create substantial avoidable overhead, while a week of history demands an explicit storage and query plan. A large disk alone does not answer whether inserts and incident searches can coexist.

## Core entities

The engineer starts with “show pricing errors,” then narrows to a host to see whether one machine is failing. That operation motivates identifying attributes such as `service` and `host` on each **log record**, the immutable event containing a timestamp, severity, and message. Those attributes describe where the event came from; its **event ID** distinguishes this occurrence from another identical timeout. If delivery is retried, it is still the same occurrence. A globally unique application-start identifier plus a counter gives each occurrence an ID that survives delivery retries because it is written into the original event. Message text cannot serve as identity: two real timeouts may have identical text.

A second distinction comes from the engineer's empty search. A host may be healthy and quiet, or unreachable with unsent files. Its log records cannot tell us which. This motivates **collector health**, recorded separately: the last heartbeat, oldest pending record age, and cumulative drop counts for each expected host. A missing heartbeat means unknown status, not zero backlog.

Notice that these concepts come from two reader needs: identifying an occurrence and judging whether the available history is current. We do not need a metrics model to answer either. Likewise, an attribute need not become an index; service and time select our common investigation, while each additional index must earn its write cost.

## API and data schema

### From a local event to a searchable record

Source ownership gives us a useful option: because we control both applications and hosts, central delivery can run independently of the application's request path. Sending synchronously from pricing is simple but makes a logging outage delay pricing. An in-memory asynchronous sender avoids that wait but loses pending events on restart. Rotating local files and a collector on each host retain pending data across collector restarts without making the application wait for a remote service. This adds disk I/O and a rotation contract, but gives the collector something to retry while the application continues. Redaction happens before the local write so credentials never enter those files.

Local writes still incur filesystem stalls; moving network delivery is not a guarantee of bounded application latency. **Trading hot-path variant:** hand diagnostic events to a bounded in-process queue and let a background writer own file I/O. Queue overflow must be counted, and process failure can lose queued events. That is acceptable only under our diagnostic-loss policy, not for the authoritative record of an execution.

The collector reads complete records, groups them, and sends them to ingestion. This group is a **batch**: a transport unit, not a new logical event. At 100 records/s per host, a one-second flush carries roughly 100 records and turns 200,000 per-event requests/s into about 2,000 batch requests/s. A 256 KB byte threshold also forces a flush so busy hosts do not build arbitrarily large requests; an oversized individual record is explicitly rejected and counted. A timer matters because quiet hosts might otherwise wait indefinitely to fill a batch. One second spends part of our five-second freshness budget in exchange for fewer requests and larger storage writes.

Ingestion validates and routes batches to searchable storage. Only after that storage commits can the collector forget the corresponding source bytes. To remember this after a restart, it saves a **collector checkpoint**: the file identity and offset up to which records have been acknowledged or deliberately discarded. An engineer follows the opposite path through a query handler, which reads committed records and attaches collector health. Publishing is continuous; searches are sporadic and can scan much more data than they return. That difference motivates separate ingestion and query work limits even when they share storage.

### The two main contracts

The interface now follows from the flow: publication tells the collector when ownership has moved, while search describes a bounded investigation. A batch POST and a query GET fit these operations over a persistent HTTP connection; Protobuf below is a payload choice, not a requirement to change transport. The notation below shows the fields, not the wire encoding:

```text
POST /log-batches
  {host, records: [{event_id, event_time, service, severity, message}]}
  -> success after the whole validated batch commits durably
  -> invalid batch: rejected record positions; no new writes

GET /logs?service=pricing&from=...&to=...&severity=ERROR
          &contains=timeout&limit=100&cursor=...
  -> {records, next_cursor, collector_health}
```

A batch comes from one authenticated host; ingestion attaches that host to each stored record. Producer identity is bound to its permitted host/services, and readers are authorized for their services. The interval is half-open, `[from, to)`, so adjacent searches need not overlap at the boundary. Server-side batch-byte, record-size, time-span, and result-count limits keep the contract bounded.

For representation, readable JSON lines are useful on the host: an operator can inspect a retained file without a schema-specific decoder. Carrying that same JSON over the network would simplify the collector, but repeats field names and requires parsing text and converting numeric fields at ingestion. Protobuf uses numbered fields and binary numeric representations; it can reduce that overhead, although the message text still occupies bytes. Its payload requires decoding tools to inspect. The [Protobuf encoding guide](https://protobuf.dev/programming-guides/encoding/) explains those wire properties.

We will use Protobuf batches between collectors and ingestion, where aggregate traffic makes bytes and parsing worth attention, and JSON for the low-volume browser response. The price is a collector conversion step, generated schema tooling, and coordinated compatibility rules. With Protobuf, adding fields compatibly and reserving removed field numbers protects decoding; changing field meanings still needs application-level migration. JSON also needs agreed field meanings and tolerant readers. The [schema evolution guidance](https://protobuf.dev/programming-guides/proto3/#updating) explains the binary compatibility rules. We should compare compressed bytes and CPU on representative messages before claiming a saving: long free-text messages may dominate either encoding. If conversion and schema maintenance outweigh measured savings, batched JSON remains a reasonable choice. A codec does not increase database insert capacity.

The stored row adds `received_at`, assigned on first insertion, to the event fields. The two times answer different questions: the engineer asks when pricing observed the timeout, while retention needs a clock the storage system controls. A retry leaves the row and its receipt time unchanged. An index on `(service, event_time, event_id)` lets us locate a service's interval, then apply severity and substring filters. A severity index is a possible measured improvement, but every extra index makes our continuous writes more expensive.

## High-level architecture

### Where should the batches go?

One relational database could serve a smaller workload: immutable rows, unique event IDs for retries, and a search index. At 60 TB raw retention, a single machine concentrates storage, insert work, and incident searches. Distributing the row-store model across **storage shards**, each owning some hosts and their indexes, lets us add capacity without changing the query contract. A relational engine such as PostgreSQL is a concrete implementation candidate, subject to the mixed-load measurements below; no engine name establishes its capacity. Committed rows remain directly searchable without an asynchronous search copy.

Consider the partition key. Grouping by service makes service searches local, but concentrates a popular service's writes. Hashing host identity distributes a popular service across shards while keeping each host batch together. The cost is multi-shard service queries. A directory maps fixed host buckets to owners, including for retries. Adding machines must move bucket data and ownership together; simply rehashing could send a retry to a second shard. Online migration details are outside this walkthrough.

Ingestion workers validate and route batches independently. Each shard transaction commits rows and event-ID uniqueness checks, persisting recovery information before acknowledgement returns through ingestion to the collector. Local files retain unacknowledged data, avoiding another durable tier for now. This makes outage buffering depend on host disks; the burst calculation below tests that choice.

### Following the investigation

Pricing writes timeout `pricing-start7:418` at 10:02:03. Its collector batches it; the shard commits, then the collector checkpoints. For pricing errors from 09:48 to 10:03, the query handler asks each shard for ordered candidates using its service/time index. It merges by `(event_time, event_id)` and returns the first 100, including our timeout, with health for pricing's expected hosts.

Binding the next-page token to the filters and last returned pair keeps pagination attached to the same investigation. Shards seek beyond that pair, avoiding growing offset scans. This live view isn't a frozen snapshot: refresh the interval to find late arrivals preceding the cursor. Shard failures or timeouts produce explicit incomplete/error responses, never a successful empty result.

Collectors send heartbeats even without logs. The handler compares them with the host inventory: fresh health describes collection status, not proof that every event was captured. Shards also expire rows by receipt time. We now have collection, searchable history, and freshness visibility; the diagram summarizes these paths.

![Applications write local files; collectors send batches through ingestion to host-owned storage shards. The query handler merges shard results for the engineer and receives collector health separately.](../../../generated/diagrams/sd-e2e-log-publishing-query/context.svg)

## Deep dives

### How much burst capacity and buffering do we need?

Batching reduces request and transaction overhead, but storage must still process every event and maintain its indexes. The missing quantity for a shard count is measured sustainable throughput with representative records, concurrent searches, and retention cleanup running. Divide the required aggregate rate by that measured per-shard rate and leave headroom for uneven host traffic. Separately check each shard's retained bytes and disk bandwidth; the largest constraint wins. Hashing helps distribute hosts but does not fix a single exceptionally noisy host, so admission limits must also apply per host.

Suppose, purely for sizing, the provisioned shards together sustain 600,000 records/s under that mixed load. Normal input is 200,000/s, while a one-minute incident produces 1,000,000/s. The pending work grows at 400,000 records/s, or 200 MB/s, adding **12 GB** over the minute. Once traffic returns to normal, 400,000 records/s of spare capacity drains that backlog in about **30 seconds**. That gives the engineer a concrete expectation: the five-second normal freshness target will be missed during this burst, and the UI must show the lag.

Across evenly loaded hosts, the burst backlog is about 6 MB per host. A ten-minute central outage is different: even at normal traffic, each host accumulates about 30 MB. We size each local budget from its own peak rate and the outage duration we intend to cover, including file and safety overhead, rather than dividing a fleet-wide budget blindly. Rotation must retain pending files within that budget. Slowing sends protects ingestion but does not slow pricing's log generation; when the budget fills, the local writer drops new records and counts losses. The writer and collector must share this budget; otherwise a collector limit cannot stop an application filling the filesystem. Persisted drop counters travel on the health path, though a failed host can leave losses unknown. Retry delays with jitter prevent all collectors reconnecting together. The handbook's [batching and overload discussion](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md) develops the underlying queueing reasoning.

This is the **Scale writes** pattern: batches amortize fixed work, partitions distribute sustained work, and buffers absorb a temporary rate mismatch. None substitutes for the others. If host buffers cannot cover the required interruptions, a reachable durable broker before storage can take responsibility for the backlog. It helps when storage is unavailable but the broker is reachable; it cannot rescue a host isolated from both. Its acknowledgement would transfer ownership earlier, and workers would advance broker positions only after storage commit. That adds retention and consumer-lag management; it still cannot fix a sustained downstream capacity deficit.

### What happens when the acknowledgement disappears?

Suppose the shard commits our timeout but the response is lost. The collector cannot distinguish this from a failed commit. Checkpointing now risks losing an uncommitted event; resending with a fresh ID risks showing a committed event twice. The uncertainty disappears only on the storage side, so the collector retains the source and resends the same immutable event ID. Stable host routing brings it back to the owning shard, whose unique constraint makes an existing ID a no-op. The retry can then be acknowledged without changing the event or `received_at`.

This also handles a collector crash after acknowledgement but before checkpoint persistence. Restart may resend a few records, which is safe. Persisting checkpoints atomically and tracking file identity through rotation prevents a reused filename from skipping an older pending file. This is the **High reliability** pattern at a precise boundary: central acknowledgement transfers responsibility for a durable copy. The handbook's [stable identities and retry handling](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) covers the mechanism. Protection against duplicates lasts while the row is retained; retries older than that need a defined expiry or a longer-lived identity registry.

Malformed input cannot improve with another identical retry. Validation rejects the complete batch before new writes and identifies bad record positions. The collector counts and discards those records, then resubmits the valid subset with unchanged IDs. The checkpoint advances only across acknowledged or explicitly discarded records. This prevents one malformed line blocking all later logs.

The remaining durability limit is intentional: a host failure can destroy events not yet transferred, and a permanent shard-disk loss can destroy acknowledged history. If surviving a storage-machine loss is required, acknowledgement must wait for an independently durable replica, accepting extra latency and reduced write availability when that copy cannot be reached. Backups solve a separate recovery need, including accidental deletion replicated to both copies.

I want to make the domain boundary explicit here. **Audit/replay variant:** a record needed to reconstruct executions cannot use our drop-on-overflow policy or single-disk acknowledgement. Its owning workflow needs durable capture before reporting success, recovery ordering, and retention agreed for that purpose; when it cannot capture safely, it must reject or halt the dependent work. Keeping the log search page available cannot justify accepting unsafe financial state. This is a changed contract, not a configuration switch that makes diagnostic logs authoritative.

### How do we keep search and retention affordable?

A fifteen-minute interval contains 180 million fleet-wide records, about 90 GB raw. Even a service producing 1% of traffic contributes roughly 900 MB. Asking for only 100 results does not bound substring-search work: finding no match can require reading every candidate message. Bounding search intervals, per-query scanned work, and concurrent searches prevents an incident from letting readers consume all write capacity. The handler must report budget exhaustion rather than return a false “no errors” answer.

This is the **Scale reads** trade-off in our design. Sharding distributes ingestion, but broad service queries fan out, and substring scans remain expensive. The indexed row store remains sufficient while bounded investigations meet the target. If message scans dominate, a search index fed durably from committed records can reduce candidate reads. A term index accelerates token searches, not arbitrary substring semantics; we need to settle whether token matching suffices before paying for substring-oriented indexing. The new path needs replayable changes and idempotent indexing by event ID, and the UI must expose indexing lag. Faster reads cost write amplification, storage, and another freshness boundary.

Retention is the **Time-series systems** decision. Expiring by event time would let a bad host clock delete a newly delivered log immediately, so we expire by receipt time and keep event time for investigation. The handbook's [timestamp domains](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md) explains why host timestamps also cannot establish causal order. Receipt-time browsing is a useful fallback when clocks are suspect.

At steady state we expire about as many rows as we insert. An index on receipt time supports bounded cleanup batches. Their write and maintenance cost belongs in the capacity measurement above. If row deletion becomes the bottleneck, receipt-time partitions let us retire whole time ranges. That improvement also changes uniqueness enforcement: if a database only enforces unique IDs within a time partition, a retry must not enter a different partition as a new row. We would need a cross-partition deduplication registry for the agreed retry horizon before making that change. A cheaper expiry path is useful only if it preserves the delivery semantics we've already promised.

## Follow-ups

- **A month of history?** Recalculate retained bytes, then weigh compressed archives for rare scans against the cost of keeping all history indexed.
- **Verify recovery?** Crash ingestion around commit and acknowledgement, and restart collectors around checkpoint persistence. Check one visible row per retried event within the deduplication horizon. Then saturate buffers, disconnect a host, and time out a query shard: reported drops, unknown health, and incomplete search must remain distinguishable. Measure lag recovery while queries and expiry run, not just ingestion in isolation.
