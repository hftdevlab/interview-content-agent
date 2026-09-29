# Design a Log Publishing and Query System

Design patterns: High reliability; Time-series systems; Scale reads.

## Question and clarifications

Design a log publishing and query system. **Interpretation:** applications publish logs so engineers can search them centrally during operational investigations.

For example, checkout runs on ten hosts. When payment requests begin timing out, an on-call engineer should be able to search recent errors across those hosts without signing into each machine. The system must also help the engineer distinguish “no errors found” from “logs have not arrived.”

Before drawing components, clarify three choices: must every log survive host loss, what kinds of message search are needed, and how soon must a new record appear? For this walkthrough, assume one internal engineering team, structured application logs, and occasional substring searches. A few seconds of collection delay is acceptable. During a prolonged outage, counted drops are preferable to blocking checkout indefinitely. This is operational debugging rather than a lossless audit trail.

All workload numbers below are illustrative: 1,000 records per second across the hosts, averaging 500 bytes each, seven days of retention, and searches usually covering fifteen minutes. A complete observability platform with metrics, traces, alerting, and multi-region recovery exceeds one interview. Focus on collection and search, then explore retry safety and the limits of a single database.

## Requirements

### Functional requirements

- Applications publish structured logs from multiple hosts into a shared history.
- Engineers search by service and time interval, with severity and optional message-substring filters, and page through bounded results.
- Engineers can see collection delays, disconnected hosts, and reported drops alongside search results.

### Non-functional requirements

- Keep normal collection delay within a few seconds and bound query work so incident searches do not starve ingestion.
- Preserve centrally acknowledged records across process restarts while the database disk remains intact. Permanent disk loss requires an optional stronger design.
- Bound local buffering and central retention; make overload losses visible while keeping the application available.

These priorities suggest separating application logging from central delivery. They do not yet justify a distributed search cluster: first build a working publication and query path, then measure its limits.

## Core entities

A **log record** is one immutable application event, identified independently of how often it is sent. It belongs to a service and a host and carries a timestamp, severity, and message. A **batch** groups records for transport; retrying the batch must not create new logical events.

A **collector checkpoint** records how far a host's files have been successfully delivered. It is local recovery state, not a property of the log itself. Separately, **collector health** reports pending-record age, drops, and the last heartbeat for each expected host. That distinction lets a query return matching records while also explaining which hosts may be missing from the result.

## API and data schema

Two interfaces are enough to discuss the main flow:

```text
POST /log-batches
  {records: [{event_id, event_time, service, host, severity, message}]}
  -> success only after the valid batch commits durably

GET /logs?service=checkout&from=...&to=...&severity=ERROR
          &contains=timeout&limit=100&cursor=...
  -> {records, next_cursor, collector_health}
```

Use a half-open time interval `[from, to)` and enforce server-side limits on the interval, batch bytes, record size, and result count. Authenticate producers and authorize readers for the services they access. Applications redact credentials before writing local files; filtering only at ingestion would leave secrets on the host.

The `logs` table stores the fields in the publication request plus `received_at`, assigned on first central insertion. Make `event_id` unique. One way to generate it is a globally unique application-start identifier plus a per-process counter, written into the original record so retries reuse it. An existing event is immutable; retrying it does not update its receipt time.

Start with a search index on `(service, event_time, event_id)`. It matches the common request: locate one service's time interval, then filter its records by severity and message. Add a severity-oriented index only if that filtering proves expensive. Each additional index costs storage and write work. The schema now gives us enough information to follow an actual record through the design.

## High-level architecture

Each application writes structured records to rotating local files. A collector on the same host sends complete records in small batches to a central service. That service handles ingestion and queries against one relational database. Local files provide temporary buffering, while the database provides shared searchable history. The diagram shows the publication path and the separate query path; responses return along the corresponding request paths.

![Host files feed collectors and ingestion into one database; the engineer queries that database through a query handler, which also receives collector health.](../../../generated/diagrams/sd-e2e-log-publishing-query/context.svg)

### Publish a record

At 10:02:03, checkout writes event `checkout-start7:418`, an error saying that a payment request timed out. The collector reads it from the host file and sends a batch. Ingestion validates the records, inserts them in a transaction, and acknowledges only after durable commit. Here, durable commit means the database has persisted the recovery information needed to retain the transaction across a process restart under our storage assumptions.

After acknowledgement, the collector saves the source file identity and byte offset in its checkpoint. It can then release the acknowledged portion of its retained files. Before acknowledgement, delivery still depends on the host's copy. We will examine the crash windows shortly; for now, this establishes where responsibility moves from local buffering to central storage.

### Search the shared history

The engineer searches checkout errors from 09:48 to 10:03, requesting at most 100 results. The query handler uses the service/time index, applies the remaining filters, and returns records ordered by `(event_time, event_id)`, including the timeout at 10:02:03. A continuation token binds the original filters to the last returned pair, so the next request can seek beyond that pair instead of skipping an increasing number of rows.

The query reads the same database that ingestion writes. Committed rows are therefore eligible for a new query without waiting for a separate indexing service. Collection and batching account for the principal freshness delay in this design. Collectors send periodic health reports, which the service tracks against the expected host inventory. The query response includes that status so the browser can show a stale or disconnected host even when there are no matching records. A query timeout is an error, not an empty successful result.

A background task deletes records older than seven days by receipt time in bounded batches. Query concurrency and execution-time limits reserve capacity for ingestion. We now have collection, shared search, and freshness visibility in one design. The remaining questions are whether retries preserve its delivery boundary and how much storage and search work one server can support.

## Deep dives

### What happens when the acknowledgement disappears?

Suppose the database commits the timeout record, but the collector never receives the response. Advancing the checkpoint would risk loss if the commit had actually failed; resending with a new ID would risk duplicate search results if it succeeded. Instead, retain the source and resend the same immutable records. Ingestion treats an insert with an already stored event ID as a no-op and acknowledges the transaction again. The database's unique constraint enforces this even if duplicate attempts overlap.

The same mechanism handles a collector crash after acknowledgement but before its checkpoint is saved: restart rereads a few records, and insertion deduplicates them. Persist the checkpoint atomically so a crash leaves a valid old or new position, and track file identity across rotation so a reused filename cannot skip pending data. The logging and rotation policy must retain unacknowledged files within the configured budget.

This is the **High reliability** pattern applied to a specific boundary: an acknowledgement means central storage owns a durable copy. The handbook's [stable identities and retry handling](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) explains the underlying mechanism. The guarantee still starts after local recording, and loss of the host can destroy logs that have not reached central storage. Deduplication here lasts while the row is retained; if retries may outlive seven-day retention, retain deduplication identities longer or define a bounded retry age before promising the same protection.

Malformed records need a different response from temporary failure. Validate the whole batch before committing and reject invalid batches with the offending record identified. The collector counts and skips explicitly rejected records, retries valid ones, and checkpoints only past records that have either been acknowledged or deliberately discarded under this policy. Retrying an unchanged invalid batch forever would block all later logs from that host.

If permanent database disk loss enters the requirements, add replication with an explicit acknowledgement policy. Waiting for another machine's durable copy changes write latency and availability when that machine cannot be reached. Backups address a different problem, including accidental deletion that replication would also copy.

### Can one database retain and search this workload?

At 1,000 records/s and 500 bytes/record, raw payload arrives at 0.5 MB/s: 43.2 GB/day or 302.4 GB over seven days, in decimal units. Indexes, database recovery files, and maintenance headroom add to that total. This is a storage floor, not evidence that a particular server meets the throughput requirement.

The **Time-series systems** pattern connects the time range, retention rule, and meaning of a timestamp. Retaining by receipt time prevents a bad host clock from immediately expiring a newly received record. Support the cleanup job with a receipt-time index so each bounded deletion does not scan the entire history. Event time remains useful for incident search, but a late record can sort before an existing pagination cursor. This browsing view is not a frozen snapshot: refresh the interval to include late arrivals. Receipt-time browsing is a useful diagnostic fallback when host clocks are suspect. The handbook's [timestamp domains](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md) explains why ordering host timestamps does not establish causality.

Now consider search cost. Fifteen minutes contains 900,000 records across all services, roughly 450 MB of raw payload. A service filter may narrow that considerably, but substring matching still examines the selected messages. A 100-row response limit alone does not bound this work: finding no matches can require scanning the whole candidate set. This is why time-span limits, execution budgets, and query concurrency controls belong in the baseline.

The **Scale reads** decision is to keep this indexed database while ingestion, retention cleanup, and representative concurrent searches fit with headroom. A larger disk solves retention capacity, but not necessarily substring-search CPU. If message scans dominate, evolve this design with a separate search index maintained from committed records. An index mapping terms to record IDs can accelerate token searches; it does not automatically implement arbitrary substring matching. Agree on those semantics before choosing the index. The indexer needs a durable checkpoint and retry-safe updates by event ID, and the UI must now expose indexing lag because database commit no longer implies search visibility.

### How long can collection fall behind?

During an incident, more logs arrive just as more engineers search them. Suppose input rises to 5,000 records/s while the database sustains 3,000 records/s under that query load. Pending files grow by 2,000 records/s, about 1 MB/s of raw payload. A 60-second burst adds about 60 MB. When input returns to 1,000 records/s, the 2,000 records/s of spare capacity takes roughly 60 seconds to drain it, assuming capacity stays unchanged.

Use this calculation to size each host's buffer against its own traffic share; an aggregate budget cannot protect the busiest host. Bound outgoing batches by bytes and a short flush timer, so large messages do not exhaust memory and quiet hosts do not wait indefinitely. During central outages, retry with increasing delays and random variation to avoid synchronized reconnects. The handbook's [batching and overload discussion](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md) provides the queueing foundation. Slowing collector sends protects ingestion, but checkout can keep producing logs, so the backlog moves into local files.

When the local disk budget fills, the logging path drops new records and counts losses. Collector health reports these losses and pending-record age; a missing heartbeat means status is unknown. Finite buffers buy recovery time. Lossless auditing would require revisiting blocking, admission, storage capacity, and failure domains.

If host files cannot cover database interruptions, a reachable central broker can durably accept batches and take ownership before workers write the database. Workers advance their positions only after database commit. Bound broker retention, provision catch-up capacity, and expose worker lag: buffering cannot fix a sustained database throughput deficit.

## Follow-ups

- **A month of history?** Estimate storage, then weigh compressed archives for rare scans against indexing costs for frequent searches.
- **Verify recovery?** Crash ingestion before commit and between commit and acknowledgement; restart the collector before and after checkpoint persistence. Verify one row per retried event within the deduplication horizon, no acknowledgement before commit, and visible buffer-overflow losses.
