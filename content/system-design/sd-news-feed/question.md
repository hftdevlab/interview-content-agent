# Design a News Feed System

> **Level:** Intermediate · 45 minutes
>
> **You will learn:** modelling data from sources that disagree · deduplicating by identity, then content · recording when it happened and when you knew · pushing to machines, letting humans pull
>
> **Related questions:** [Design a Log Publishing and Query System](../sd-log-publishing-query/question.md) · [Design a Low-Latency Market Data Feed and Normalization System](../sd-market-data-feed/question.md)
>
> **Handbook:** [Ch 21 — *Reading the Wire*](../../../release1/handbook-markdown/chapters/d1-market-data-and-protocols/chapter.md) · [Ch 29 — *Sending It Twice*](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) · [Ch 31 — *What Did It See, and Why Did It Do That?*](../../../release1/handbook-markdown/chapters/e4-deterministic-replay/chapter.md)

## The question

> Design the news feed system, supporting various feed format.

At a hedge fund, a news feed is machine-readable news: stories from wire services, company press releases, regulatory filings, and alternative sources, each arriving in its own format. The system turns all of them into one stream tagged with the firm's security IDs.

That stream has two very different audiences. Strategies react to headlines within milliseconds. Traders and researchers read, search, and backtest.

**The crux: turn many differently shaped, sometimes duplicated feeds into one trustworthy stream — without throwing away what makes each source useful, and honestly enough about time for backtests.**

> **Finance lens — this is not the social news feed.** The consumer-tech question with the same name is about fan-out: one post must reach millions of followers' timelines, and reads dominate. Here we have about ten sources and a few hundred consumers, so fan-out is small. The hard parts are heterogeneous formats, duplicates across vendors, latency for machine readers, licensing, and point-in-time correctness. In the interview, ask which version they mean, then say why the answers differ. That one question shows you know both worlds.

## Requirements

### Functional requirements

1. Ingest stories from multiple sources in their native formats: streaming vendor feeds and polled sources such as RSS feeds and regulatory filing indexes.
2. Deliver stories, tagged with the firm's security IDs, to subscribers in real time, filtered by security, topic, and source.
3. Search history by security, time, and keywords — including "what had we received by time T?" for backtests.

Out of scope: the language models that score stories (they are consumers), vendor contracts, and the trader UI.

### Non-functional requirements

Assume about 500,000 items a day across all sources, with peaks around 1,000 per second at scheduled release times such as the market open and the earnings window after the close. A story is 2–20 KB.

That is a small volume for one system. **This is a low-volume, high-correctness system.** Say so in the interview; it tells the interviewer you will not spend the hour on sharding.

1. **Latency.** A story reaches strategy subscribers within 5 ms (p99) of receipt; human terminals within a second.
2. **Completeness.** No received story is lost, and a source that goes silent is detected within a minute.
3. **Duplicates.** The same story arriving twice, or through two sources, is linked rather than delivered as two unrelated events.
4. **Point-in-time history.** We record when each version was received, and corrections never overwrite.
5. **Entitlements.** Each user, desk, or strategy receives only content the firm licenses for it.

## Core entities

- **Source** — one feed connection, plus the adapter that understands its format.
- **Raw item** — the exact bytes as received, with the source and a receive timestamp.
- **Story revision** — one version of one story, in the form consumers read. What fields it has is the hardest decision in this design; the first deep dive is about it.
- **Event cluster** — revisions from *different* sources that describe the same real-world event.
- **Subscription** — a consumer's filter, plus the entitlements that limit it.

Two relationships do most of the work. **One raw item becomes one or more revisions**, through exactly one adapter. **One story has many revisions**, and a correction is a new revision, never an edit.

## API

Adapters plug into the platform through one narrow interface:

```text
adapter.parse(raw_item)  ->  [StoryRevision]
    a pure function of the bytes: no clock reads, no network, no global state
```

"Pure" is the important word. An adapter that depends only on the raw bytes can be re-run on yesterday's data and produce the same answer. That makes parsing bugs fixable after the fact, and new adapter versions testable.

Strategies subscribe to a stream; everyone else queries:

```text
Subscribe { securities[], topics[], sources[] }  ->  stream of StoryRevision
GET /stories?security=...&from=...&to=...&q=...&as_of=...
```

We leave `StoryRevision` deliberately vague for now. Deciding what goes in it is where this question is won or lost.

## High-level design

### 1) Ingest every source

1. A connector per source owns the session: a TCP or WebSocket stream for vendors, or polling with conditional requests for RSS and filing indexes.
2. The connector stamps the receive time and appends the raw bytes to a raw log, partitioned by source, before anything else happens.
3. The source's adapter parses the raw item into story revisions.
4. A normalizer maps the vendor's security identifiers to the firm's security IDs using reference data.

![Each source gets its own connector and adapter; raw bytes are appended with a receive time before parsing, and the normalizer maps vendor identifiers to firm security IDs.](../../../generated/diagrams/sd-news-feed/step1-ingest.svg)

Why separate connectors and adapters? They fail for different reasons. A connector fails when a session drops; an adapter fails when a vendor changes its format. Keeping them apart means a reconnect never touches parsing, and a format change never touches session handling.

Appending the raw bytes before parsing is the same "accept durably, then do the slow work" move a notification platform uses ([Design a Notification System](../sd-notification-system/question.md)), into a partitioned, append-only log. If an adapter has a bug, we fix it and re-parse from the log. Without the raw bytes, a parsing bug silently loses data forever.

Security mapping is the quietest source of bugs. Tickers get reused after delistings and change after corporate actions. Map using stable identifiers with effective dates, and treat an unmapped security as an alert, not a blank field. Handbook Ch 21 shows the same discipline for exchange protocols: get the representation right in the decoder, because every downstream comparison inherits it.

### 2) Deliver in real time

1. The normalizer hands every revision to a router.
2. The router matches it against subscription filters and entitlements, in memory.
3. Strategies receive matching revisions as a push stream over the firm's low-latency messaging bus.
4. Traders' terminals connect through a WebSocket gateway, and backfill from history when they connect.

![The router pushes matching, licensed revisions to strategies over a low-latency bus and to terminals through a WebSocket gateway; terminals backfill from the story store on connect.](../../../generated/diagrams/sd-news-feed/step2-deliver.svg)

Strategies and people want different things, so they get different paths. A strategy wants every matching revision, pushed, as fast as possible. A person wants a live view that is complete when they look at it — so the terminal subscribes for new items and *queries* for anything it missed while disconnected. WebSocket is the right tool for that internal, bidirectional view ([Handbook Ch 27 — *The Control Plane*](../../../release1/handbook-markdown/chapters/d7-websocket-and-http/chapter.md)).

> **Design move — Push to machines, let humans pull.** Push new items to latency-sensitive subscribers; serve human readers from a queryable store. *Cost:* two delivery paths with different freshness and failure behaviour.

Entitlements are checked at the router, where data leaves the system. Vendors license content per user, desk, or application, and algorithmic use is often licensed separately from human display. Filtering at ingest would mean one stream per licence combination. Filtering at delivery keeps one stream and one check per subscriber.

Notice what is *not* on this path: storage and indexing. The store writer reads the same revisions in parallel. A slow index can delay search, but it can never delay a headline.

### 3) Store and search history

1. A store writer appends every revision; nothing is ever updated in place.
2. It indexes each revision by security and received time, and by full text.
3. The query API answers searches, with `as_of` defaulting to now.

![History is append-only revisions plus a search index; the query API returns revisions received at or before as_of.](../../../generated/diagrams/sd-news-feed/step3-history.svg)

Half a million items a day is small enough to index every word: Elasticsearch or OpenSearch handles this volume comfortably. A log platform ingesting tens of billions of events a day cannot afford that and indexes only the fields people filter on ([Design a Log Publishing and Query System](../sd-log-publishing-query/question.md)). **The principle — index what the queries need — is the same; the volume changes the answer.** That kind of reasoning is what interviewers listen for.

### What is still broken

1. **Sources disagree about what a story is.** Every adapter needs a target shape, and the sources do not agree on identity, securities, urgency, or topics.
2. **The same story arrives three times**, from two wires and a regulatory filing.
3. **Backtests can see the future** if a correction is applied to the original.

## Deep dives

### 1) How should we model stories from sources that disagree?

Take one earnings story and look at how four sources describe it:

| Field | Wire A (XML) | Wire B (JSON) | Press-release RSS | Filing index |
|---|---|---|---|---|
| Identity | story ID + revision number | new ID per version, no link between them | article URL | filing accession number |
| Securities | the vendor's own codes | tickers with exchange suffix | only in the body text | company identifier, not a ticker |
| Urgency | 1–5 scale | flash / alert / regular | none | none |
| Topics | ~800 vendor codes | ~40 categories | none | form type |
| Time | sent time, milliseconds | published time, seconds | publication date, sometimes hours late | filing acceptance time |

Every adapter must produce *something*. Candidates usually reach for one of two answers first, and both are defensible.

**Option A: one uniform schema.** Define fixed fields — headline, body, securities, urgency, topics, time — and make every adapter fill them. Anything without a home is dropped.

Consumers love it: one parser, and deduplication, search, and entitlements all work on the same fields. The trouble starts with the table above:

- Wire A's urgency 4 and Wire B's "alert" do not mean the same thing, so forcing them onto one scale invents precision.
- Mapping 800 topic codes onto 40 categories throws detail away; mapping 40 onto 800 makes detail up.
- Research later wants exactly the fields we dropped, and every new field changes a schema that every consumer depends on.

**Option B: keep each vendor's own schema.** Wrap each native record in a thin envelope — source, received time — and pass it on. Nothing is lost, and adding a vendor takes an adapter that barely parses.

Now every consumer writes a parser and a mapping per vendor, each slightly different. The features the platform itself needs — deduplication across sources, search by security, entitlements by topic — require normalized fields anyway. And when one vendor changes its format, every consumer breaks at once.

Option A pushes the cost onto the information; Option B pushes it onto every consumer. A strong candidate notices that the consumers are not all alike. Strategies need a few fields from every source, fast. Researchers need everything from one source, exactly.

**Option C: a small common core, vendor extensions, and the raw bytes.** The core holds only fields that most consumers filter or join on *and* that every source can fill honestly: identity, source, kind, headline, firm security IDs, source time, and received time. Everything else stays in a typed extension named after its vendor. The raw bytes sit alongside for anyone who needs the original.

![A story revision has three layers: a small shared core that strategies and the platform read, a typed vendor extension for specialists, and a reference to the raw bytes for reprocessing.](../../../generated/diagrams/sd-news-feed/dd1-record-shape.svg)

| | A: uniform schema | B: per-vendor schema | C: core + extensions + raw |
|---|---|---|---|
| Consumer effort | lowest | highest: one parser per vendor | low for core readers, explicit for specialists |
| Information lost | a lot, silently | none | none, but most of it is not normalized |
| Adding a vendor | schema change for everyone | an adapter only | adapter plus a new extension type |
| Cross-source dedup, search, entitlements | easy | needs normalization anyway | easy on the core |
| Vendor changes its format | adapter fix | every consumer breaks | adapter fix; extension readers may need updates |
| Ongoing cost | schema churn | duplicated parsing everywhere | governing the core |

Option C is not free, and saying where it hurts is part of a strong answer:

- **Choosing the core is a judgement call.** Use a two-part test: most consumers filter or join on the field, *and* every source can fill it without guessing — or marks the guess as inferred. Urgency fails the second test.
- **Even core fields are not equally honest.** The wires' securities are mapped through reference data; the press releases' are extracted from body text, which is a guess. Wire B's revisions share no ID, so linking them is inferred too — the next deep dive does it by content. Tag each core field with its provenance — supplied, mapped, or inferred — so a strategy can refuse inferred securities.
- **Same name, different meaning.** Wire A's sent time, Wire B's published time, and a filing's acceptance time are all "source time", with different meanings and precision. Store the kind and precision with the value.
- **Some fields have no honest mapping.** For urgency we can leave it out of the core, map it onto a coarse shared scale with an explicit "unknown" while keeping the original in the extension, or learn a mapping from historical data. Each option loses something; pick the one the strategies can live with, and write the choice down.
- **"Not provided" must be explicit.** A filing has no urgency. A core field filled with a made-up default is worse than an empty one.
- **Someone must own the core.** Adding a core field is a versioned change with a reviewer. Without that, the extensions become a dumping ground and the core stops meaning anything.

There is no perfect model here. If the only consumers were two strategies that need a headline, a security, and a time, Option A would be simpler and correct. If the only consumer were a research team rebuilding signals from one vendor's metadata, Option B would be. Option C wins *because this firm has both kinds of consumer*.

**Pick the core from what consumers filter and join on and every source can fill honestly; keep everything else, unmapped, next to it.**

> **Design move — Normalize at the edge, keep the raw.** One adapter per source fills a small shared core at entry; vendor-specific fields stay in typed extensions, and the original bytes are kept. *Cost:* choosing and governing the core is a judgement call, and some fields have no honest mapping.

Formats will keep changing, so the model must change safely. Core changes are additive only: new optional fields, never renamed or repurposed ones. Because adapters are pure and the raw bytes are kept, releasing a new adapter version is mechanical:

1. Re-run a week of captured raw items through the new version.
2. Diff its output against the current version's.
3. Run it in shadow mode for a day — parsing live traffic, publishing nothing.
4. Promote it, keeping the old version ready to switch back.

### 2) The same story arrives three times. What do we deliver?

At 16:05 a company publishes its earnings. The press release reaches us through Wire A at 16:05:12.004 and Wire B at 16:05:12.019. The regulatory filing appears at 16:05:40. At 16:07, Wire A sends a correction to the earnings-per-share figure, and its connector reconnects and resends its last ten stories.

There are two different kinds of duplicate here, and they need different tools:

| Kind | Example | Identity | Action |
|---|---|---|---|
| Same source, same revision | resend after reconnect | `(source, source_story_id, revision)` | drop and count |
| Same source, new revision | the 16:07 correction | same `source_story_id`, higher revision | store and deliver as a correction |
| Same source, new version, no shared ID | Wire B's correction, sent under a fresh ID | none — compare content within the source | link as a revision, marked inferred |
| Different sources, same event | Wire B and the filing | none shared — compare content | deliver, tagged with `cluster_id` |

The first two rows use an idempotency key the vendor chose for us: an identity that stays the same on every resend. A unique constraint on it turns resends into no-ops. [Design a Notification System](../sd-notification-system/question.md) builds the same move for callers that retry.

The last two rows have no shared ID, so we compare content. Normalize the headline (case, punctuation, numbers), take word shingles, and compute a similarity fingerprint such as MinHash. A match with the same securities inside a 10-minute window joins the existing event cluster. This only works because the core gives every source the same headline and security fields.

![A new revision is first checked against its source's own identity, then against content from other sources; matches are linked and delivered, never delayed or deleted.](../../../generated/diagrams/sd-news-feed/dd1-dedup.svg)

Two policy choices matter more than the algorithm:

- **Never delay delivery for deduplication.** The first copy goes out immediately. Later copies go out tagged, and each strategy decides what to do with them.
- **Link, never delete.** Fuzzy matching will occasionally merge two different stories. Keeping both, linked, makes that mistake recoverable. And for some strategies, a second source confirming the first is itself a signal.

> **Design move — Deduplicate by identity, then by content.** Collapse repeats with the source's own ID first, then with a content fingerprint across sources. *Cost:* fuzzy matching can merge two different stories, so keep the evidence.

**Dedup by identity first, by content second — and link, don't delete.** Handbook Ch 29 covers the identity half in depth: why "check, then act" fails, and how a receiver keeps duplicates from becoming double effects.

### 3) What had we received by 16:05:30?

A researcher backtests a strategy that trades on earnings headlines. Here is the history of that one story:

| Revision | Source time (vendor's claim) | Received time (our clock) | EPS |
|---|---|---|---|
| r1 | 16:05:11.9 | 16:05:12.004 | 1.42 |
| r2 — correction | 16:06:58 | 16:07:00.120 | 1.24 |

If the store had updated r1 in place, a backtest replaying 16:05:30 would see EPS = 1.24, a number the live strategy could not have known until 16:07. The backtest looks better than reality, the strategy goes live, and it loses money for reasons nobody can see. This is lookahead bias, and the storage design either prevents it or causes it.

The rule for an as-of query is:

> **Return, for each story, the latest revision whose *received* time is at or before T.**

Not source time. A vendor can stamp a story 16:05:00 and deliver it at 16:05:40; querying by source time would show it to the backtest 40 seconds early. Received time is the only time we can vouch for, and it should come from a well-synchronised clock at the connector ([Handbook Ch 25 — *Whose Clock Was That?*](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md)).

The same rule applies to reference data. If a ticker was remapped at 16:30, a backtest at 16:05 must use the mapping that was in force at 16:05.

> **Design move — Record when it happened and when you knew.** Store event time and arrival time on every record, and append corrections instead of overwriting. *Cost:* more storage, and a query API that defaults to as-of.

Make `as_of` the default, not an option. Handbook Ch 31 puts it bluntly: the convenient call is the one people make under a deadline, so the safe query must also be the short one ([Ch 31, Part 3](../../../release1/handbook-markdown/chapters/e4-deterministic-replay/chapter.md)).

**Backtests must ask "what had we received by T?", never "what is true about T?"**

## Interview calibration

**A passing answer**

- Builds per-source ingestion and picks either a uniform schema or per-vendor schemas — and can say what that choice costs.
- Pushes new stories to subscribers and stores history with search.
- Handles obvious duplicates by source ID.

**A strong answer also**

- Asks which "news feed" is meant, and explains why the trading version is low-volume and correctness-heavy.
- Compares uniform and per-vendor schemas, reaches a small core with vendor extensions, and states the test for what belongs in the core.
- Names fields that have no honest mapping, and treats the choice as a judgement tied to who the consumers are.
- Keeps raw bytes and makes adapters pure, so parsing bugs are recoverable and adapter releases are testable.
- Separates same-source and cross-source duplicates, delivers first and links later.
- Explains lookahead bias and insists on received-time, as-of queries — for reference data too.

## Follow-ups

**One strategy needs headlines in under 50 microseconds. Does this design work?**

> No, and it should not try to. That strategy subscribes directly to the vendor's low-latency machine-readable feed and parses it in-process — normalization moved inside the strategy. The platform still captures the same feed for history and for everyone else. Different consumers, different paths.

**A vendor retracts a story ten minutes after publishing it. What happens?**

> The retraction is a new revision of kind `RETRACTION`. It is pushed immediately, because a strategy that acted on the original must know. History keeps both revisions, so an as-of query before the retraction still returns the original — which is what the strategy saw at the time.

**One source stops sending at 14:00. How would anyone notice?**

> A dead feed and a quiet news day look identical from the inside. Use the protocol's heartbeats where it has them; otherwise learn each source's normal arrival rate by time of day and alert when silence runs past it. Then publish source health to subscribers, not only to operations: a strategy that trades on news must know when its news is stale. The handbook's Module D review calls this "silence is ambiguous, and it resolves in the expensive direction" ([Ch 26 — *Taking the Kernel Out of the Path*](../../../release1/handbook-markdown/chapters/d6-kernel-bypass/chapter.md)).
