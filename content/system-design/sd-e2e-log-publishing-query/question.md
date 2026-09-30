# Design a Log Publishing and Query System

Design patterns: Scale writes; High reliability; Time-series systems; Scale reads.

## Question and clarifications

Design a log publishing and query system. **Interpretation:** applications publish logs so engineers can search them centrally during operational investigations.

When checkout starts timing out, I want the on-call engineer to find recent errors across its hosts without signing into each machine. An empty result needs context: did checkout produce no errors, or have its logs stopped arriving? That gives us two connected jobs: collect the events and explain how current the searchable history is.

I'd first clarify whether these are operational logs or an audit trail, whether search means exact fields or arbitrary message text, and how quickly new records must appear. Here I'll assume structured application logs from hosts we operate, service/time/severity filters, and occasional substring searches. Counted drops during a prolonged outage are preferable to blocking the application indefinitely. Metrics, traces, alerting, and multi-region recovery would make this a larger interview; I'll focus on collection, searchable storage, and their capacity and recovery boundaries.

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
- Bound local disk use and query work, keeping application availability ahead of lossless logging during prolonged overload.

### What does this workload imply?

Before choosing storage, I'll turn the host estimate into the work we must do:

```text
2,000 hosts × 100 records/s = 200,000 records/s
200,000 × 500 bytes       = 100 MB/s
100 MB/s × 86,400 s       = 8.64 TB/day
7 days                   = 60.48 TB of raw records
5× burst                 = 1,000,000 records/s, 500 MB/s
```

All units are decimal. Compression could lower disk and network bytes, while indexes, recovery logs, and free space for maintenance raise provisioned storage. These estimates are not a server benchmark. They tell me that a per-event remote request creates substantial avoidable overhead, and that keeping a week of history deserves an explicit storage and query plan. A large disk alone does not answer whether inserts and incident searches can coexist.

## Core entities

The engineer starts with “show checkout errors,” then narrows to a host to see whether one machine is failing. I therefore need identifying attributes such as `service` and `host` on each **log record**, the immutable event containing a timestamp, severity, and message. Those attributes describe where the event came from; its **event ID** distinguishes this occurrence from another identical timeout. If delivery is retried, it is still the same occurrence. I'll generate the ID from a globally unique application-start identifier and a counter, and write it into the original event.

A second distinction comes from the engineer's empty search. A host may be healthy and quiet, or unreachable with unsent files. Its log records cannot tell us which. I need **collector health** separately: the last heartbeat, oldest pending record age, and cumulative drop counts for each expected host. A missing heartbeat means unknown status, not zero backlog.

I won't introduce metrics or series here: those would model a different product. Nor does every useful attribute deserve an index. Service and time select the common investigation; the storage discussion will decide which other filters justify write work.

## API and data schema

### From a local event to a searchable record

We control the applications and their hosts, so I can keep central delivery out of each application's request path. Sending synchronously from checkout is simple but makes a logging outage delay checkout. An in-memory asynchronous sender avoids that wait but loses pending events on restart. I'll instead have applications write structured records to rotating local files and run a collector on each host. This adds disk I/O and a rotation contract, but gives the collector something to retry while the application continues. Redaction happens before the local write so credentials never enter those files.

The collector reads complete records, groups them, and sends them to ingestion. This group is a **batch**: a transport unit, not a new logical event. At 100 records/s per host, a one-second flush carries roughly 100 records and turns 200,000 per-event requests/s into about 2,000 batch requests/s. I'll also flush at 256 KB so busy hosts do not build arbitrarily large requests; an oversized individual record is explicitly rejected and counted. A timer matters because quiet hosts might otherwise wait indefinitely to fill a batch. One second spends part of our five-second freshness budget in exchange for fewer requests and larger storage writes.

Ingestion validates and routes batches to searchable storage. Only after that storage commits can the collector forget the corresponding source bytes. To remember this after a restart, it saves a **collector checkpoint**: the file identity and offset up to which records have been acknowledged or deliberately discarded. An engineer follows the opposite path through a query handler, which reads committed records and attaches collector health. Publishing is continuous; searches are sporadic and can scan much more data than they return. That difference motivates separate ingestion and query work limits even when they share storage.

### The two main contracts

I need publication to tell the collector when ownership has moved, and search to specify a bounded investigation. The notation below shows the fields, not the wire encoding:

```text
POST /log-batches
  {host, records: [{event_id, event_time, service, severity, message}]}
  -> success after every valid record in this batch commits durably

GET /logs?service=checkout&from=...&to=...&severity=ERROR
          &contains=timeout&limit=100&cursor=...
  -> {records, next_cursor, collector_health}
```

A batch comes from one authenticated host; ingestion attaches that host to each stored record. I bind producer identity to its permitted host/services and authorize readers for their services. The interval is half-open, `[from, to)`, so adjacent searches need not overlap at the boundary. Server-side batch-byte, record-size, time-span, and result-count limits keep the contract bounded.

For representation, readable JSON lines are useful on the host: an operator can inspect a retained file without a schema-specific decoder. Carrying that same JSON over the network would simplify the collector, but repeats field names and requires parsing text and converting numeric fields at ingestion. Protobuf uses numbered fields and binary numeric representations; it can reduce that overhead, although the message text still occupies bytes. Its payload requires decoding tools to inspect. The [Protobuf encoding guide](https://protobuf.dev/programming-guides/encoding/) explains those wire properties.

I'll choose Protobuf batches for the controlled collector-to-ingestion path, where aggregate traffic makes bytes and parsing worth attention, and JSON for the low-volume browser response. The price is a collector conversion step, generated schema tooling, and coordinated compatibility rules. With Protobuf, I'll add fields compatibly and reserve removed field numbers; changing field meanings still needs application-level migration. JSON also needs agreed field meanings and tolerant readers. The [schema evolution guidance](https://protobuf.dev/programming-guides/proto3/#updating) explains the binary compatibility rules. I'd compare compressed bytes and CPU on representative messages before claiming a saving: long free-text messages may dominate either encoding. If conversion and schema maintenance outweigh measured savings, batched JSON remains a reasonable choice. A codec does not increase database insert capacity.

The stored row adds `received_at`, assigned on first insertion, to the event fields. I need both times: the engineer asks when checkout observed the timeout, while retention needs a clock the storage system controls. A retry leaves the row and its receipt time unchanged. I'll index `(service, event_time, event_id)` to locate a service's interval, then apply severity and substring filters. A severity index is a possible measured improvement, but every extra index makes our continuous writes more expensive.

## High-level architecture

### Where should the batches go?

One relational database could serve a smaller workload: immutable rows, unique event IDs for retries, and a search index. With 60 TB raw retention and concurrent writes and searches, I won't assume one machine suffices. I'll distribute this model across **storage shards**, each owning some hosts and their indexes. Committed rows remain directly searchable without an asynchronous search copy.

I'll hash host identity rather than service: a popular service then spreads across shards while each host batch stays together. The cost is multi-shard service queries. A directory maps fixed host buckets to owners, including for retries. Adding machines must move bucket data and ownership together; simply rehashing could send a retry to a second shard. Online migration details are outside this walkthrough.

Ingestion workers validate and route batches independently. Each shard transaction commits rows and event-ID uniqueness checks, persisting recovery information before acknowledgement returns through ingestion to the collector. Local files retain unacknowledged data, avoiding another durable tier for now. This makes outage buffering depend on host disks; the burst calculation below tests that choice.

### Following the investigation

Checkout writes timeout `checkout-start7:418` at 10:02:03. Its collector batches it; the shard commits, then the collector checkpoints. For checkout errors from 09:48 to 10:03, the query handler asks each shard for ordered candidates using its service/time index. It merges by `(event_time, event_id)` and returns the first 100, including our timeout, with health for checkout's expected hosts.

I'll bind the next-page token to the filters and last returned pair. Shards seek beyond that pair, avoiding growing offset scans. This live view isn't a frozen snapshot: refresh the interval to find late arrivals preceding the cursor. Shard failures or timeouts produce explicit incomplete/error responses, never a successful empty result.

Collectors send heartbeats even without logs. The handler compares them with the host inventory: fresh health describes collection status, not proof that every event was captured. Shards also expire rows by receipt time. We now have collection, searchable history, and freshness visibility; the diagram summarizes these paths.

![Applications write local files; collectors send batches through ingestion to host-owned storage shards. The query handler merges shard results for the engineer and receives collector health separately.](../../../generated/diagrams/sd-e2e-log-publishing-query/context.svg)

## Deep dives

### How much burst capacity and buffering do we need?

Batching reduces request and transaction overhead, but storage must still process every event and maintain its indexes. To choose a shard count, I'd measure sustainable throughput with representative records, concurrent searches, and retention cleanup running. Divide the required capacity by that measured rate and leave headroom for uneven host traffic. Separately check each shard's retained bytes and disk bandwidth; the largest constraint wins. Hashing helps distribute hosts but does not fix a single exceptionally noisy host, so admission limits must also apply per host.

Suppose, purely for sizing, the provisioned shards together sustain 600,000 records/s under that mixed load. Normal input is 200,000/s, while a one-minute incident produces 1,000,000/s. The pending work grows at 400,000 records/s, or 200 MB/s, adding **12 GB** over the minute. Once traffic returns to normal, 400,000 records/s of spare capacity drains that backlog in about **30 seconds**. That gives the engineer a concrete expectation: the five-second normal freshness target will be missed during this burst, and the UI must show the lag.

Across evenly loaded hosts, the burst backlog is about 6 MB per host. A ten-minute central outage is different: even at normal traffic, each host accumulates about 30 MB. I'll size each local budget from its own peak rate and the outage duration we intend to cover, including file and safety overhead, rather than dividing a fleet-wide budget blindly. Rotation must retain pending files within that budget. Slowing sends protects ingestion but does not slow checkout's log generation; when the budget fills, the logging path drops new records and counts losses. Retry delays with jitter prevent all collectors reconnecting together. The handbook's [batching and overload discussion](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md) develops the underlying queueing reasoning.

This is the **Scale writes** pattern: batches amortize fixed work, partitions distribute sustained work, and buffers absorb a temporary rate mismatch. None substitutes for the others. If host buffers cannot cover the required interruptions, I'd add a reachable durable broker before storage. Its acknowledgement would transfer ownership earlier, and workers would advance broker positions only after storage commit. That adds retention and consumer-lag management; it still cannot fix a sustained downstream capacity deficit.

### What happens when the acknowledgement disappears?

Suppose the shard commits our timeout but the response is lost. The collector cannot distinguish this from a failed commit. If I checkpoint now, I might lose the event; if I resend with a fresh ID, I might show it twice. I'll retain the source and resend the same immutable event ID. Stable host routing brings it back to the owning shard, whose unique constraint makes an existing ID a no-op. The retry can then be acknowledged without changing the event or `received_at`.

This also handles a collector crash after acknowledgement but before checkpoint persistence. Restart may resend a few records, which is safe. I'll persist checkpoints atomically and track file identity through rotation, so a reused filename cannot skip an older pending file. This is the **High reliability** pattern at a precise boundary: central acknowledgement transfers responsibility for a durable copy. The handbook's [stable identities and retry handling](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) covers the mechanism. Protection against duplicates lasts while the row is retained; retries older than that need a defined expiry or a longer-lived identity registry.

Malformed input cannot improve with another identical retry. I'll validate a complete batch before writing, identify rejected records, and let the collector count and discard those records while retrying valid ones. The checkpoint advances only across acknowledged or explicitly discarded records. This prevents one malformed line blocking all later logs.

The remaining durability limit is intentional: a host failure can destroy events not yet transferred, and a permanent shard-disk loss can destroy acknowledged history. If the requirement changes, I'd require acknowledgement after another machine's durable copy, accepting extra latency and reduced write availability during some failures. Backups solve a separate recovery need, including accidental deletion replicated to both copies. Operational logging's acceptable loss policy must be agreed before choosing this boundary.

### How do we keep search and retention affordable?

A fifteen-minute interval contains 180 million fleet-wide records, about 90 GB raw. Even a service producing 1% of traffic contributes roughly 900 MB. Asking for only 100 results does not bound substring-search work: finding no match can require reading every candidate message. I'll cap search intervals, per-query scanned work, and concurrent searches so an incident does not let readers consume all write capacity. The handler must report budget exhaustion rather than return a false “no errors” answer.

This is the **Scale reads** trade-off in our design. Sharding distributes ingestion, but broad service queries fan out, and substring scans remain expensive. I'll keep the indexed row store while bounded investigations meet the target. If message scans dominate, I'd add a search index fed durably from committed records. A term index accelerates token searches, not arbitrary substring semantics; I'd settle whether token matching suffices before paying for substring-oriented indexing. The new path needs replayable changes and idempotent indexing by event ID, and the UI must expose indexing lag. Faster reads cost write amplification, storage, and another freshness boundary.

Retention is the **Time-series systems** decision. Expiring by event time would let a bad host clock delete a newly delivered log immediately, so I'll expire by receipt time and keep event time for investigation. The handbook's [timestamp domains](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md) explains why host timestamps also cannot establish causal order. Receipt-time browsing is a useful fallback when clocks are suspect.

At steady state we expire about as many rows as we insert. I'll index receipt time and use bounded cleanup batches, including their write and maintenance cost in the capacity measurement above. If row deletion becomes the bottleneck, receipt-time partitions let us retire whole time ranges. That improvement also changes uniqueness enforcement: if a database only enforces unique IDs within a time partition, a retry must not enter a different partition as a new row. I'd retain a cross-partition deduplication registry for the agreed retry horizon before making that change. A cheaper expiry path is useful only if it preserves the delivery semantics we've already promised.

## Follow-ups

- **A month of history?** Recalculate retained bytes, then weigh compressed archives for rare scans against the cost of keeping all history indexed.
- **Verify recovery?** Crash ingestion around commit and acknowledgement, and restart collectors around checkpoint persistence. Check one visible row per retried event within the deduplication horizon, visible overflow losses, and lag recovery while queries and expiry run.
