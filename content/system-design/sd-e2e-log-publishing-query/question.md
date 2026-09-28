# Design a Log Publishing and Query System

## Interview prompt

Maya is on call for a checkout service running on ten application hosts. For an illustrative workload, the hosts together produce 1,000 log records per second, averaging 500 bytes each. At 10:02, customers begin seeing checkout failures; Maya wants to find recent error messages across all ten hosts in one place. Searching each machine separately delays diagnosis, and a missing result could mean either no errors or logs that have not arrived yet.

Design a log publishing and query system. **Interpretation:** these are application logs collected for operational search. Explain how a record reaches searchable storage, how Maya retrieves it, and what happens when delivery falls behind.

## What the interviewer is testing

**Core.** The question tests whether the candidate can turn “collect and search logs” into a small working design: choose a record format and access pattern, explain the acknowledgement boundary, estimate storage and search work, and make overload visible. Naming a distributed log or a search engine is less useful than explaining why it is needed.

## Requirements and assumptions

Use the following illustrative assumptions for this walkthrough, rather than treating the numbers as fixed requirements. One internal engineering team searches by service, time interval, severity, and optionally a message substring. Keep seven days of centrally received records; ordinary searches cover the last fifteen minutes. A few seconds of collection delay is acceptable, and logging should not stall checkout indefinitely. This is operational debugging, not a lossless audit trail: bounded local buffering and explicitly counted drops are acceptable during prolonged outages.

Before committing to that last choice, ask whether every log must survive host loss, whether arbitrary full-text search is essential, and how quickly new records must appear. Those answers could change the storage or delivery design. The baseline below uses the stated operational assumptions: centrally acknowledged records survive a process restart while the database disk remains intact; permanent disk loss is outside that guarantee. Cross-host timestamps provide an approximate display order, not a total order of events.

A full observability platform, including metrics, traces, alerting, and multi-region recovery, is too large for this interview. Sketch collection, storage, and search, then agree whether retries or search growth deserves the remaining depth.

## Good solution

### Core — Start with files, then centralize the search

Each application already writes structured records to a rotating local file: a new file replaces the active one before it becomes too large. At very small scale, Maya can search those files directly. That is sufficient for a few hosts, infrequent investigations, and no need for a shared history. The first limit in this scenario is the human effort of visiting ten hosts, not proof that one machine cannot handle the data.

Add a collector process on each host. It reads complete records from those files and sends small batches over an authenticated connection to a central ingestion process. The ingestion process checks record size and required fields, then inserts the batch into a relational database running on one server. A query handler in the same central service reads that database for Maya's browser. The database maintains the table and its indexes in files on disk; no separate message broker or indexing service is needed yet.

A record contains an event ID, application timestamp, service, host, severity, and message. The ingestion process adds a receipt timestamp. An event ID can be an application-start identifier plus a per-process counter, stored with the record before delivery; retries reuse it. Authenticate producers and authorize readers for the services they may access. Applications redact credentials before writing the local file, since central filtering would leave the original secret on the host.

Store records in a `logs` table with a unique event ID and an index on `(service, event_time, event_id)`. Here, an index is a database-maintained lookup structure that locates a service's time range without reading the entire table. Start with this one search index; add a severity-oriented index only if measurements show that filtering severity after the time lookup is expensive. Each extra index also consumes disk and write work.

### Core — Follow one record through publication

At 10:02:03, checkout writes event `checkout-start7:418`, an error saying that a payment request timed out. The collector sends it in a batch. The ingestion process commits the rows using the database's durable commit mode and only then acknowledges the batch. Durable commit means the database has persisted the recovery information needed to retain that transaction across a process restart under the stated storage assumptions.

The collector keeps its place in a small local checkpoint file identifying the source file and byte offset. It advances that checkpoint only after acknowledgement. It retains unread or unacknowledged source records within a configured disk budget, follows file rotation, and resumes from the checkpoint after restart. A publisher must not overwrite pending files silently: if its finite retention budget is exhausted, the operational policy permits dropping records, counts the loss, and reports a collection gap.

A lost acknowledgement must not create a second logical event. The database's unique constraint makes a repeated insert of the same event ID a no-op; commit the batch atomically and acknowledge it again. Treat retries as resends of immutable records. This is the application of the handbook's [stable identities and retry handling](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md), rather than a claim that the network delivers exactly once.

The key invariant is small: **an acknowledgement means the central database owns a durable copy; before acknowledgement, delivery still depends on the host's retained file.** A crash before a local write or loss of that host can still lose unacknowledged logs. The design does not promise otherwise.

### Core — Make Maya's query bounded and interpretable

Maya requests checkout errors from 09:47 through 10:02, with at most 100 results. The query handler enforces a maximum time span and result size, uses the service/time index to find candidates, and applies severity and optional substring filters. It returns rows ordered by `(event_time, event_id)`. A continuation token contains the last pair and the original filters so the next request can seek beyond it instead of skipping an ever-growing number of rows.

This browsing view is not a frozen snapshot. A late-arriving record can sort before the continuation point; Maya refreshes the interval to include it. Both event and receipt times are retained so she can distinguish an old event arriving now from a new event. A host clock error can still misplace a record in an event-time search, so receipt-time browsing is a useful diagnostic fallback. The handbook's [timestamp domains](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md) explain why sorting host clocks cannot establish causality.

Because the query reads the same database, committed records are immediately eligible for a new query; collection and batching account for most freshness delay in this baseline. Collectors report their oldest pending record age, dropped-record count, and periodic health updates. The browser shows stale or disconnected collectors alongside results. “No matching records” must not imply “all hosts are current,” and a query timeout is an error, not an empty successful result.

Delete records older than seven days by receipt time in bounded background batches. Receipt time makes the retention rule independent of a host's clock. Limit query concurrency and execution time so an expensive search cannot consume all resources needed for ingestion.

The following trace shows why the checkpoint follows the database commit. The local source file remains the collector's retry buffer; the acknowledgement transfers responsibility to the database.

![Collector reads a host file, ingestion commits records before acknowledgement, then the collector checkpoints; Maya queries the committed rows.](../../../generated/diagrams/sd-e2e-log-publishing-query/context.svg)

### Core — Check that one server is a reasonable starting point

At 1,000 records per second and 500 bytes per record, raw payload arrives at 0.5 MB/s: about 43.2 GB/day or 302.4 GB over seven days, using decimal units. This excludes indexes, database recovery files, and free space for maintenance. It is a sizing floor, not a disk recommendation or a throughput benchmark.

A fifteen-minute window contains 900,000 records across all services, about 450 MB before overhead. The service index can reduce that candidate set, but searching every message for a substring still requires examining the selected messages. During an incident, many simultaneous broad searches can make read I/O or CPU the bottleneck even when append traffic is modest.

Keep one database while measured ingestion, retention cleanup, and concurrent representative searches fit with headroom. A larger disk may solve retention capacity; it will not automatically solve substring-search CPU. This collector, ingestion process, table, and bounded query path is a complete passing answer. It should precede any discussion of distributed storage.

## Failure scenarios

### Deep dive — Trace the boundary instead of promising no loss

| Failure | Consequence and response |
|---|---|
| Database commit succeeds but acknowledgement is lost | Collector resends the same IDs; the unique constraint prevents duplicate rows. It then checkpoints after the new acknowledgement. |
| Collector crashes after acknowledgement but before checkpoint | Restart rereads some records. The same duplicate handling makes this harmless. |
| Central service is unavailable | Collectors retry with increasing delays and random variation; retained files buffer the interruption until their byte budget fills. Drops beyond that budget are counted. |
| A record is malformed or too large | Reject it explicitly, without an ambiguous partial batch commit. The collector isolates the offending record, reports a rejected-record count, and retries valid records; it must not retry an unchanging invalid batch forever. |
| Database disk is lost | A single-server durable commit does not cover this failure. Recovery requires a backup with an accepted loss interval, or a stronger replicated design agreed separately. |

### Deep dive — A queue buys time, not sustained capacity

Suppose an incident raises input to an illustrative 5,000 records/s, while measurements show the central database can sustain 3,000 records/s under the concurrent query load. The pending files grow by 2,000 records/s, or roughly 1 MB/s of raw payload. A 60-second burst adds about 60 MB. After input returns to 1,000 records/s, 2,000 records/s of spare capacity takes about 60 seconds to drain that backlog, assuming capacity stays unchanged.

Size each host's buffer against its own traffic share and record sizes; the aggregate calculation alone cannot protect the busiest host. Bound batches by both bytes and a short flush timer, so large messages cannot exhaust memory and quiet hosts do not wait indefinitely to send. The handbook's [batching and overload discussion](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md) supplies the queueing foundation. Here the central service can slow collector sends, but checkout may keep producing logs, moving the backlog into local files.

Under sustained excess load, choose a policy rather than growing the queue forever. For this walkthrough, preserve checkout availability, drop new logs once the configured local budget is exhausted, and expose the gap through health reporting. If Maya instead needs a lossless audit trail, this policy is unacceptable: the interview must revisit producer blocking, durable storage capacity, and the failures that retention must survive.

## Great solution improvements

**Stretch — Choose only when a measured limit or stronger requirement warrants it.**

- **Speed up message search.** If scans dominate, add a search index mapping message terms to record IDs, maintained by a separate indexing process reading committed records. Token search is not the same as arbitrary substring search; settle the required matching semantics first. Keep a durable indexing checkpoint, use event IDs for retry safety, and show indexing lag because commit no longer implies search visibility.
- **Buffer centrally for longer outages.** If local files cannot cover ingestion interruptions, a broker process can append incoming batches to durable disk files before workers write the query database. Acknowledgement now transfers ownership to the broker; workers advance their read positions only after database commit. Set finite retention and ensure workers can catch up. This isolates bursts but does not fix a sustained storage throughput deficit.
- **Protect against disk loss.** If that failure enters the contract, replicate database writes to another machine under an explicit acknowledgement policy. State the cost in write latency and availability when a replica cannot be reached. Backups remain useful for accidental deletion; replication alone reproduces deletions too.

## Common pitfalls

- Acknowledging a batch while it exists only in central memory, then calling it durable.
- Generating fresh event IDs on retry or discarding source files before acknowledgement.
- Treating an unbounded queue as a capacity plan, or silently returning empty results when collection or querying fails.
- Starting with a distributed search cluster without explaining the query pattern or why the single-database design is insufficient.

## Follow-up questions

### How would Maya search a month of messages quickly?

**Deep dive.** First distinguish rare archival searches from frequent interactive searches. Extend the storage estimate, measure bytes scanned per query, and decide whether compressed archived files with slower scans suffice or a term index is worth its write and storage costs. Do not promise indexed substring search merely because token search is fast.

### What changes if losing any checkout log is unacceptable?

**Deep dive.** Define which failure domains must be survived and when the guarantee starts. Durable local recording, replication before central acknowledgement, and blocking or rejecting work when safe capacity is exhausted may all become relevant. No finite buffer guarantees lossless delivery through an arbitrarily long outage while producers continue without restriction.

### How would you check the retry design?

**Deep dive.** Kill ingestion immediately before commit and immediately after commit but before acknowledgement. Restart the collector before and after its checkpoint write. Verify one stored row per event ID for successfully retried records, no acknowledgement for an uncommitted batch, and visible gaps when the configured buffer budget is exceeded.

## Evaluation rubric

**Core.** A passing answer describes one record and one query end to end, gives a compact schema and useful index, acknowledges after durable commit, handles duplicate retries, and bounds storage and query work. It names the permitted loss boundary and explains when one database is sufficient.

A strong answer uses arithmetic to identify scan cost or burst backlog, distinguishes collection health from empty results, and explains the checkpoint/commit crash windows. It proposes an improvement because a specific limit demands it.

An incomplete answer is a list of technologies with no delivery contract, a lossless claim backed by finite queues, or a search path with no time bounds. Optional distributed components are not required for a passing foundational answer.
