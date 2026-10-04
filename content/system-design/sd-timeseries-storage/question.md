# Design a Distributed Time-Series Storage System

> **Level:** Advanced · 60 minutes
>
> **You will learn:** columnar blocks with statistics · overwriting by versioned range · immutable files and compaction · lazy merge iterators · reading from a pinned snapshot
>
> **Related questions:** [Design a Log Publishing and Query System](../sd-log-publishing-query/question.md) · [Design a Low-Latency Market Data Feed and Normalization System](../sd-market-data-feed/question.md)
>
> **Handbook:** [Ch 5 — *Fetching a Kilobyte to Read a Price*](../../../release1/handbook-markdown/chapters/a5-cache-locality-and-layout/chapter.md) · [Ch 13 — *The Cost of Asking Which Strategy*](../../../release1/handbook-markdown/chapters/b6-hot-path-dispatch/chapter.md) · [Ch 18 — *Counting the Copies*](../../../release1/handbook-markdown/chapters/c6-mmap-and-zero-copy/chapter.md) · [Ch 31 — *What Did It See, and Why Did It Do That?*](../../../release1/handbook-markdown/chapters/e4-deterministic-replay/chapter.md)

## The question

> Design a distributed storage system that supports read and write operations for time-series data optimized for large batch queries. Each write should overwrite all previous data in the same range. The read interface should be based on iterators.

Research at a trading firm runs on history: years of trades, quotes, and derived features for thousands of instruments. One backtest reads a year of three columns for 500 instruments in a single pass. Meanwhile the history keeps changing: vendors correct past days, and researchers recompute whole datasets after fixing a bug.

This question goes below the boxes. Expect to discuss file layout, encodings, merge order, and when a file may be deleted.

**The crux: make huge scans fast while ranges keep being rewritten — when a fast scan wants data laid out once and left alone, and an overwrite wants to change it.**

> **Finance lens.** Metrics stores such as Prometheus or InfluxDB are the consumer-tech cousins: mostly appends, mostly recent data, small queries, and old data can simply be dropped. Here queries scan years, corrections are routine, and a backtest run last month must be reproducible exactly. So an overwrite must replace data for new readers without destroying what an earlier backtest saw ([Handbook Ch 31](../../../release1/handbook-markdown/chapters/e4-deterministic-replay/chapter.md), Part 3).

### Domain primer

Market data is corrected after the fact. An exchange cancels an erroneous trade, a vendor re-sends a day with fixed timestamps, a research team recomputes a feature for ten years. These arrive as **range writes**: "here is everything for AAPL trades from 10:00 to 11:00 on October 3." The new batch is the complete truth for that range, so anything stored there that is not in the batch must disappear.

| Stored before | In the write for AAPL, Oct 3, [10:00, 11:00) | Stored after |
|---|---|---|
| 10:15:02 trade 187.20 × 100 | 10:15:02 trade 187.20 × 100 | kept |
| 10:15:03 trade 817.20 × 100 — a bad print | — | removed |
| 10:40:11 trade 187.31 × 300 | 10:40:12 trade 187.31 × 300 | re-timed |
| 09:59:58 and 11:00:01 trades | outside the range | untouched |

The running scenario is this correction: the vendor's fix for AAPL on October 3, arriving on October 7, while backtests are reading October.

## Requirements

### Functional requirements

1. `write(series, range, rows)` replaces everything stored for that series in `[t0, t1)` with the given rows, removing stored rows the batch does not contain.
2. `read(series set, range, columns)` returns an iterator over rows in `(series, time)` order, pulling data only as the caller consumes it.
3. A read sees each write entirely or not at all, and can ask for the data as of an earlier version, to reproduce an old backtest.

Out of scope: SQL, joins, real-time streaming of today's ticks (the market data feed's job), and downsampling.

### Non-functional requirements

Assume tick data for 10,000 instruments: about 1 billion rows a day, each a timestamp and seven 8-byte values, so 64 bytes raw. Ten years is about 2.5 trillion rows: roughly 160 TB raw, or about 27 TB if it compresses six to one. A typical query reads 500 instruments for one year, three columns.

| Quantity | Value |
|---|---|
| Rows the query touches: 500 × 252 days × 100,000 rows | 12.6 billion |
| Read whole rows (8 columns × 8 B) | ~800 GB |
| Read only 3 of 8 columns | ~300 GB |
| ... compressed about 6× | ~50 GB |
| Time on 20 nodes reading 1 GB/s each | 40 s for 800 GB · 2.5 s for 50 GB |

**A batch query's cost is the bytes it reads, and the layout decides the bytes: about 800 GB by row, about 50 GB by compressed column.**

1. **Scan throughput.** Scans run at about 1 GB/s of compressed data per node, and a query uses every node.
2. **Atomic overwrite.** A range write is all-or-nothing for readers, and a ten-year recompute never blocks them.
3. **Snapshot reads.** An iterator sees one consistent version for its whole life, even if it runs for ten minutes while writes land.
4. **Durable.** An acknowledged write survives the loss of any node.
5. **Write cost.** About 1 billion rows loaded nightly, plus a few thousand corrections a day, most of them a single instrument-day.

Out of scope: sub-millisecond point lookups, and making today's data readable within seconds — minutes is fine.

## Core entities

- **Series** — one stream of rows keyed by time, such as `(trades, AAPL)`, with a fixed set of columns.
- **Partition** — one series over one time bucket, such as AAPL trades for October 2026. The unit of placement and of rewriting.
- **Segment** — an immutable file of rows for one partition, stored column by column and tagged with the version that wrote it.
- **Range record** — "series S, `[t0, t1)`, replaced at version v". Every write creates one.
- **Version** — a number the catalog assigns to each committed change, in commit order.
- **Catalog** — the small, strongly consistent store that says which segments and range records make up each version.

The relationship that matters, once the design is complete, is **one write = one range record + one segment, at the same version**. A read of October 3 takes every segment that covers it, drops rows hidden by a newer range record, and merges the rest by time. No file is ever edited.

## API

Two calls carry the design. In pseudocode:

```text
write(series, [t0, t1), rows, idempotency_key)  ->  version
    replaces everything stored for the series in [t0, t1); every row lies inside the range
write_batch([(series, [t0, t1), rows), ...], idempotency_key)  ->  version
    many range writes committed as one version, such as a vendor's correction file

read(series[], [t0, t1), columns[], as_of?, splits?)  ->  iterators
    iterator.next()   ->  the next batch of rows, column by column; empty at the end
    iterator.version  ->  the version this iterator reads
```

The parameters an interviewer will probe:

- **`columns`** — the query names the columns it needs, which decides how many bytes it reads (deep dive 1).
- **`[t0, t1)` on writes** — the range being replaced, not just the rows sent; it is how a write deletes (deep dive 2).
- **`version` and `as_of`** — a backtest stores the version it read and can read it again later (deep dives 2 and 3).
- **`splits`** — independent iterators over disjoint partitions, so many readers can scan in parallel.

`next()` returns a batch, not a row; the first deep dive explains why. Writes stream their rows, because a recompute can be terabytes.

## High-level design

We will build the simplest design that meets each requirement, then run October 7 through it.

### 1) Write a range

Partition each series by a time bucket chosen so a partition is tens of megabytes compressed: a month for tick data (about 2 million rows per instrument, roughly 22 MB), a year or more for minute bars. Each partition lives on three storage nodes, chosen by hashing the partition key and recorded in the catalog.

That is partitioning by time and storing what the queries filter on — the same principle a log store uses, which [Design a Log Publishing and Query System](../sd-log-publishing-query/question.md) develops. Here the filter is always series and time, so the partition key is exactly that.

The simplest overwrite rewrites every partition the range touches:

1. The client calls `write(AAPL.trades, [Oct 3 10:00, 11:00), rows)`.
2. A coordinator finds the partitions the range touches: AAPL trades, October.
3. For each, it builds a replacement file: old rows outside the range, plus the new rows, in time order.
4. It writes the new files to three storage nodes.
5. It commits one catalog transaction pointing the partitions at the new files, as version 812, and replies.

![The coordinator splices old rows outside the range with the new rows, writes a replacement file to three storage nodes, and commits one catalog transaction that switches the partition to the new file at version 812.](../../../generated/diagrams/sd-timeseries-storage/step1-write.svg)

Files are never edited, only replaced. That makes replication simple: a replica is a copy of a file, verified by checksum, and two replicas can never disagree. The idempotency key makes a retried write a no-op instead of a second version — the move [Design a Notification System](../sd-notification-system/question.md) builds for retrying callers.

### 2) Read through an iterator

1. The client calls `read(...)` and immediately gets iterators back. Nothing has been fetched.
2. Each iterator asks the catalog which partitions and files cover its part of the request, and records the current version.
3. On the first `next()`, it reads the first file's blocks from a storage node, filters rows to the range, and returns them.
4. While the caller works, it prefetches the next few partitions in parallel from other nodes.

![Iterators get the file list and version from the catalog once, then stream blocks from storage nodes, prefetching ahead, while the caller pulls batches at its own pace.](../../../generated/diagrams/sd-timeseries-storage/step2-read.svg)

An iterator fits batch queries for three reasons. The result — 50 GB even after compression — never has to fit in memory. The caller sets the pace, so a slow consumer slows the scan instead of filling a buffer. And a caller that stops early stops the work.

Order holds within an iterator, not across them. A query that asks for 20 `splits` gets 20 iterators over disjoint partitions, so 20 threads or machines can consume at once.

### 3) Read a consistent version

The catalog commit is the only mutable step, so a write becomes visible all at once. An iterator that recorded version 811 keeps reading 811's files even after 812 commits. `as_of = 790` simply asks the catalog for version 790's file list, as long as those files still exist.

### What is still broken

1. **Every scan reads every column.** Row files make the three-column query read 800 GB.
2. **Small corrections rewrite whole partitions.** Fixing one instrument-day rewrites its month, and 5,000 corrections rewrite 5,000 months.
3. **Old files have no safe time to die.** A ten-minute scan may still be reading a replaced file, and nothing records that.

## Deep dives

### 1) How do we read 50 GB instead of 800 GB?

A researcher runs the typical query: 500 instruments, all of 2025, columns `time`, `price`, and `size`. Each stored row is 64 bytes, and the query wants 24 of them. Within those 24, timestamps climb in small steps and prices barely move from one trade to the next. Row storage ignores both facts.

**Option A: a relational table with an index on `(series, time)`.** This is the answer most candidates give first. The index finds the first row of each series in microseconds. Then the database reads every matching row in full — all 800 GB of it, plus index pages. Finding rows was never the expensive part; reading them is.

**Option B: sorted row files, as in the high-level design.** No index overhead, and sequential reads. Still 800 GB, and general-purpose compression does poorly on rows that interleave timestamps, prices, and sizes.

The strong move is to start from the arithmetic: the query's cost is bytes, so change what a byte holds.

**Option C: columnar segments with block statistics.**

1. **Store each column separately.** Within a segment, each column is its own sequence of blocks of tens of thousands of rows. The query reads three columns and never touches the other five.
2. **Encode each column for its shape**, then apply a fast general compressor such as LZ4 or Zstandard on top. Neighbouring values in one column are similar, which is what compression needs.
3. **Record statistics per block** — first and last time, minimum and maximum of each column — in a footer at the end of the file. A reader fetches the footer first, then only the byte ranges of blocks it needs.
4. **Sort by `(series, time)`**, the order the queries ask for, so a time range is a contiguous run of blocks.

| Column | Shape | Encoding |
|---|---|---|
| `time` (ns) | increasing, irregular gaps | delta, then variable-length integers; delta-of-delta for regular series such as bars |
| `price` (scaled integer) | moves a few ticks either way | delta, zigzag for the sign, then bit-packing |
| `size` | small integers, frequent repeats | bit-packing or run-length |
| exchange, conditions | a handful of distinct values | dictionary |

![A segment stores each column as a run of compressed blocks; the footer holds offsets and min/max statistics per block, so a reader fetches the footer, then only the blocks and columns it needs.](../../../generated/diagrams/sd-timeseries-storage/dd1-segment.svg)

This is struct-of-arrays at file scale. [Handbook Ch 5 — *Fetching a Kilobyte to Read a Price*](../../../release1/handbook-markdown/chapters/a5-cache-locality-and-layout/chapter.md) counts cache lines for a scan that reads one field per record: array-of-structs uses 12.5% of every line it loads, struct-of-arrays uses all of it. The same arithmetic, applied to disk blocks, takes the query from 800 GB to 50 GB. Parquet, ClickHouse, and kdb+ all store data this way.

The iterator has to keep up. A virtual `next()` per row, called 12.6 billion times, makes the call itself a visible share of the scan. [Handbook Ch 13 — *The Cost of Asking Which Strategy*](../../../release1/handbook-markdown/chapters/b6-hot-path-dispatch/chapter.md) explains why that cost depends on inlining and prediction, and that the cheapest call is the one that does not happen.

Returning 4,096 rows per call, column by column, makes the call rare — the batching move from [Design a Log Publishing and Query System](../sd-log-publishing-query/question.md) — and lets the caller's loop run over plain arrays.

| | A: row table + index | B: sorted row files | C: columnar + statistics |
|---|---|---|---|
| Bytes read for the query | ~800 GB plus index | ~800 GB | ~50 GB |
| Find one series' time range | index lookup | file per partition | footer statistics |
| Compression | poor | moderate | high |
| Append one row | cheap | rewrite the file | rebuild blocks |
| Read one whole row | one page | one block | one block per column |
| Right for | transactional point access | simple archives | batch scans |

Columnar layout makes small writes and single-row reads worse. That is an acceptable price only because this system's writes arrive as whole batches and its reads are scans. Say that condition out loud.

**A batch query's cost is the bytes it reads. Store each column on its own, compressed, with statistics that let a scan skip what it does not need.**

> **Design move — Columnar blocks with statistics.** Store each column in large compressed blocks with min/max statistics, so batch scans read only the columns and blocks they need. *Cost:* single-row lookups and small writes get more expensive.

### 2) The vendor sends 5,000 corrections for October 3. Do we rewrite October 5,000 times?

At 07:10 on October 7, the vendor's correction file for October 3 arrives: 5,000 instruments, loaded as one batch. Most entries replace a whole instrument-day — about 100,000 rows, roughly 1 MB compressed. AAPL's replaces 10:00–11:00. At 07:40 a second file re-sends 300 of them; for AAPL, it removes 10:15–10:20. Meanwhile, a research team starts recomputing a feature dataset across ten years.

In the high-level design, each 1 MB correction rewrites a 22 MB month:

| Write | New data | Rewritten under copy-on-write |
|---|---|---|
| 07:10 — 5,000 instrument-days | 5 GB | 110 GB |
| 07:40 — 300 re-sent | 0.3 GB | 6.6 GB |

Worse, two writes to the same partition at once both splice from the same old file, so the second to commit must start over or erase the first.

Candidates usually reach for one of two answers.

**Option A: copy-on-write with smaller partitions.** Partition by instrument-day, and a day-sized correction rewrites only itself. But ten years of 10,000 instruments becomes 25 million files of about 1 MB. Every file costs an open, a footer read, and a catalog entry, and scans now spend their time on overhead. Corrections smaller than a day still rewrite the day.

**Option B: merge on read.** Never rewrite. Each write adds its own segment plus a note of the range it replaces, and reads combine the pieces. Writes cost exactly their own size and never conflict. But every correction adds a piece that every later scan must merge, so read cost grows without bound.

A strong candidate notices that Option B is right about writes and Option A is right about reads, and that they need not happen at the same time.

**Option C: versioned range records, merged on read, compacted later.**

1. **Every write is a range record plus a segment, at one version.** The 07:10 file commits as one batch, so all 5,000 range records get version 812, and each new segment's rows are tagged 812. The 07:40 file commits as 815; AAPL's entry there is a range record with no rows.
2. **The visibility rule.** At snapshot version V, a row tagged r at time t is visible if r ≤ V and no range record for its series covering t has a version greater than r and no greater than V.
3. **Deletes come free.** The 10:15:03 bad print is tagged 700. Range record 812 covers 10:15:03, and 812 > 700, so the row is hidden. It was never deleted; it just stopped being visible.
4. **Compaction rewrites later.** A nightly job rewrites every partition that has overlays into one segment containing only the visible rows. A partition that crosses a threshold during the day — more than four overlays, or overlays above 10% of its bytes — is compacted at once.

![Three versions cover October 3 for AAPL: the base at 700, a correction at 812 for 10:00 to 11:00, and an empty write at 815 that removes 10:15 to 10:20. The visible result takes each interval from the newest version that covers it.](../../../generated/diagrams/sd-timeseries-storage/dd2-range-overlay.svg)

Compaction does not avoid the rewrite. It moves it. At 02:00 the next night, the compactor rewrites AAPL's October once, folding in the 07:10 correction, the 07:40 re-send, and anything else since the last compaction. It runs off the write path, at a time we choose, and never conflicts with writers.

| | Copy-on-write | Merge on read | Merge on read + compaction |
|---|---|---|---|
| Bytes written per 1 MB correction | 22 MB, immediately | 1 MB | 1 MB now; 22 MB later, shared by every correction since the last compaction |
| Read cost | one segment per partition | grows with every correction | bounded: at most about four overlays |
| Space | old files until readers finish | every overlay kept | overlays until compacted |
| Concurrent writes to one partition | conflict and retry | never conflict | never conflict |
| Right when | rare, large writes | writes dominate | batch reads with routine corrections |

Storage researchers call this the RUM trade-off: you can minimise two of read cost, update cost, and memory overhead, not all three. **This system is built for reads, so it pays the write cost — but in the background, once per batch of corrections.**

Option C has sharp edges, and naming them is part of a strong answer:

- **Compacted rows carry the snapshot's version.** Suppose compaction reads snapshot V, a correction commits as V+1 while it runs, and compaction then commits as V+2. The correction's range record must still hide the compacted rows, which works only if they are tagged V, never V+2.
- **The swap must be exact.** The catalog commit replaces precisely the input segments with the output, and drops the range records the output has already applied, so later reads stop sweeping them. Range records are clipped at partition boundaries when written, so dropping one here cannot expose rows in another partition. A segment committed during compaction is not an input, so it survives untouched.
- **Big writes commit at the end.** The ten-year recompute uploads segments for hours, then commits once — one catalog transaction, or for very large writes one entry pointing at a manifest file that lists the segments. Readers see the old dataset until that instant. If the job dies, its uploaded segments were never referenced and are swept away later.

Versions are also what make old backtests reproducible. A version is a knowledge time — what the store knew after that commit — and "as of version 790" is the point-in-time query [Design a News Feed System](../sd-news-feed/question.md) builds for news, applied to whole datasets. Handbook Ch 31 draws the same picture: a correction is a new point higher on the knowledge axis, not an edit of the old one.

**Make an overwrite a new version that hides a range, not an edit. Let compaction pay the rewrite later, in the background, once.**

> **Design move — Overwrite by versioned range.** Implement overwrite as a new version that covers a key range; reads take the newest version for each point; old versions are removed once no reader needs them. *Cost:* reads must resolve overlaps, and old versions occupy space until compaction.

> **Design move — Write immutably, compact later.** Never edit stored files in place: each write adds new immutable files, and a background process merges them so reads stay cheap. *Cost:* reads consult several files until compaction catches up, and compaction spends I/O rewriting data that did not change.

### 3) An iterator reads October for ten minutes while compaction replaces its files. What does it see?

At 09:00 a backtest opens an iterator over AAPL trades for October. The catalog is at version 820. The partition holds two segments — the base (700) and the 10:00–11:00 correction for October 3 (812) — plus a range record with no rows that removed 10:15–10:20 (815).

At 09:04, an operator compacts October early — ahead of the nightly run — because a week of backtests is about to scan it. Compaction merges the two segments into one, applying both range records, and wants to delete the inputs. At 09:06, a new correction for October 20 commits as version 830.

Two problems: merging the overlapping segments efficiently, and keeping the iterator's files alive.

**The merge.** The iterator opens one cursor per segment, each already sorted by `(series, time)`:

1. A min-heap on `(series, time)` holds the head row of each cursor. With k segments, choosing the next row costs O(log k).
2. The iterator keeps the series' range records at version 820, sorted by start time, and sweeps through them as time advances. A row is dropped if the newest record covering its time is newer than the row.
3. Surviving rows go into the output batch, column by column.
4. A cursor reads its next block only when the heap needs it, so memory is k blocks, whatever the range.

| Next row | From | Newest range covering it | Emitted? |
|---|---|---|---|
| 09:59:58 | 700 | none | yes |
| 10:00:01 | 700 | 812 | no: hidden by 812 |
| 10:00:01 | 812 | 812 | yes: same version |
| 10:15:02 | 812 | 815 | no: removed by 815 |
| 10:40:12 | 812 | 812 | yes |
| 11:00:01 | 700 | none | yes |

![One cursor per segment feeds a min-heap ordered by series and time; a range filter drops rows hidden by newer records; a batch builder fills 4,096-row column batches. The iterator holds pinned version 820 while compaction publishes 821 beside it.](../../../generated/diagrams/sd-timeseries-storage/dd3-merge.svg)

The per-row heap is the slow path, and most of the data never needs it. From 11:00 on October 3 to the end of the month, only the base segment overlaps and no range record applies. There the iterator decodes whole blocks in bulk, straight into the output batches, with no per-row heap work. After compaction, almost every block takes this fast path.

> **Design move — Merge sorted sources lazily.** Read several sorted sources through a lazy k-way merge that resolves overlaps by version and pulls only what the caller consumes. *Cost:* per-row merge overhead unless rows are processed in batches.

**The snapshot.** The iterator pinned version 820 when it opened: a fixed list of segments and range records. Everything that happens next creates *new* versions and leaves 820 alone:

- At 09:04, compaction commits 821: one new segment replaces the two inputs, with identical visible data. The iterator keeps reading the two inputs.
- At 09:06, the October 20 correction commits 830. The iterator does not see it, because it reads version 820 from start to finish.

So when can the two input segments be deleted? Only when no pinned snapshot references them and they are older than the as-of retention window. Each iterator registers its pinned version with a lease that it renews every minute, so a client that crashes stops pinning within a minute instead of holding files forever. Databases call this multi-version concurrency control; here the versions are whole files.

| | Lock the partition while reading | Copy the data for each reader | Pin a snapshot |
|---|---|---|---|
| Writers during a 10-minute scan | blocked | proceed | proceed |
| Extra storage | none | a full copy per reader | replaced files, until the slowest reader finishes |
| Reader sees | one state | one state | one state |
| Right when | never, for long scans | tiny datasets | immutable files |

Immutability pays off once more at the lowest level. Storage nodes can read segments through `mmap` safely: the replay tool in [Handbook Ch 18 — *Counting the Copies*](../../../release1/handbook-markdown/chapters/c6-mmap-and-zero-copy/chapter.md) crashed mapping a file another process was still writing, and a sealed segment never changes under its reader. Caches of decoded blocks never need invalidating either, for the same reason.

**Merge lazily, resolve overlaps by version, and pin each long read to one version. Then writes and compaction proceed without ever stopping a reader.**

> **Design move — Read from a pinned snapshot.** Pin a long read to one immutable version of the data, so it sees a consistent state while writes continue. *Cost:* old files stay alive until the slowest reader finishes.

## Interview calibration

**A passing answer**

- Partitions by series and time, stores immutable files, and streams results through an iterator.
- Chooses columnar storage for batch scans.
- Implements overwrite by rewriting the affected partitions and switching to them atomically.

**A strong answer also**

- Does the bytes-read arithmetic and lets it choose the layout: columns, encodings, block statistics, batch-at-a-time iterators.
- Turns overwrite into a versioned range record, shows how deletes fall out of it, and argues the read-versus-write trade-off with compaction.
- Notices that compacted rows must carry the version of the snapshot compaction read, not a new one, or rows that a concurrent correction replaced come back.
- Builds a lazy k-way merge with version filtering and a fast path for blocks with no overlap.
- Pins long reads to a snapshot, explains when an old file may be deleted, and offers as-of reads at a stated storage cost.

## Follow-ups

**A backtest from last March must be reproduced exactly. What do you keep?**

> Keep catalog versions, and the segments they reference, for a retention window — say 90 days — and let a team tag the version a published backtest used so it is kept for good. The backtest stored its iterator's version with its results, so it replays with `as_of`. Corrections are small, so retention is cheap for them; a ten-year recompute doubles the dataset's storage for as long as both versions are kept. Name that cost, and let the owners choose.

**Researchers want all 500 instruments in one time-ordered stream, not one series after another.**

> The same merge works with the key `(time, series)` across series: 500 cursors, so about nine comparisons per row, in batches. If this access pattern dominates, store a second copy partitioned by day and sorted by `(time, series)`. That is the classic trade: storage for a layout that matches the query.

**Why not use Parquet files on object storage with a table format like Apache Iceberg or Delta Lake?**

> Often you should: they provide much of this design — immutable columnar files, a catalog of snapshots with time travel, atomic overwrite of the rows matching a filter, and compaction. What can remain yours is making a narrow range overwrite cheap — depending on the format and its settings, an overwrite may rewrite every file the range touches — plus the iterator interface and tuning partitions for these scans. In the interview, name the off-the-shelf option, then show you understand the mechanism underneath it.
