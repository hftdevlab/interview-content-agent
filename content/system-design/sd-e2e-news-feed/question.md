# Design a News Feed

## Question and clarifications

Design a news feed supporting different content formats. **Assumed interpretation:** a social following feed where people publish text, images, and video, then browse posts from authors they follow.

I want us to start with what determines which posts a reader sees. A recommendation feed must discover and score candidates; a following feed starts from relationships the reader chose. That distinction changes the selection problem before we choose any infrastructure. We will develop the following-feed interpretation, with public posts newest first. A new follow includes the author's retained history. Private audiences, deletion, recommendations, advertising, and detailed video encoding are outside this small baseline; adding them would require revisiting visibility or ordering.

Imagine Maya follows 200 people, including Leo, who has just posted a short video. She opens her feed to see the newest 20 updates. Those numbers are illustrative, not requirements supplied by the prompt. They help us ask two practical questions: how does Leo's post become available, and how can Maya see a useful page without downloading every video on it?

A whole social platform exceeds one interview. Publishing, following, and chronological reads give us one complete design to develop; its interesting limits are repeated selection work, uneven audiences, and recovery after interrupted publication. For the calculations, assume illustrative peak rates of 1,000 feed requests and 100 new posts per second, 200 followed authors per typical reader, and a mean audience of 500 per post, with some million-follower authors. These are workload assumptions, not facts supplied by the prompt. Keep the large audiences in view: an efficient design for Maya alone may still struggle when a popular author posts.

Design patterns: Scale reads; Fan-out write; Data transactions.

## Requirements

### Functional requirements

- Authenticated users can publish text and supported image or video attachments.
- Users can follow or unfollow authors and browse their currently followed authors' retained posts, newest first.
- Users can scroll through pages and load media separately from post descriptions.

### Non-functional requirements

- Show a useful first page promptly. Measure feed-response latency separately from video startup; a large media file should not delay all the text.
- Preserve acknowledged posts across application restarts and recover unfinished distribution. A short visibility delay is acceptable, but an unavailable feed must return a retryable error rather than look successfully empty. Reject publication if durable commit is unavailable.
- Make retry and recovery behavior testable: interrupt publication and distribution at their commit boundaries, then verify the result after restart.
- Keep read work bounded as history grows. Configure limits on follows, page size, text length, and upload size; choose production values from workload evidence.

For this walkthrough, use a first-page target of 300 ms at the 95th percentile and ordinary post visibility within a few seconds at the assumed peak. These are targets to test, not measured performance. I separate response latency from freshness because a fast response can still show an old feed. Both matter when we decide whether to precompute pages.

For finance engineers, this remains a human browsing system. Predictable response time, recoverable publication, and failure tests deserve attention; microsecond execution-path techniques do not follow from the audience. A **licensed research-feed variant** may have fewer readers but tighter access rules. We will return to that difference where it changes content delivery, while keeping the public social feed as our main design.

## Core entities

When Leo publishes and Maya reads, they are using two roles of the same account: a **user**. Notice that the operation changes, but the identity does not; separate author and reader accounts would add a distinction we do not need. Maya’s choice to see Leo’s updates must survive between visits, so we also need a **follow**: a directed relationship from a reader to an author. Reversing it has a different meaning; Leo need not follow Maya back.

Leo’s video and its caption should appear as one item, even when thousands of readers view it. That gives us a **post**, owned by one author and identified independently of any reader’s feed. But uploading a video may finish long before Leo presses Publish, or may fail halfway through. This is the distinction I want us to capture with a **media asset**: an uploaded file with an owner and a readiness state, separate from the published item. A post references ready assets; the files are not copied into each reader’s view.

Maya’s **feed page** is the newest slice of posts eligible through her current follows. We can derive it from posts and relationships instead of storing a separate feed immediately. That makes a new follow simple: Leo’s retained posts already exist and become eligible. The cost is repeating selection when Maya returns. We’ll use that cost to decide later whether a stored feed entry earns its place in the design.

## API and data schema

Let’s turn Leo’s publication into a contract. If the publish call carried the whole video, a network retry would repeat an expensive transfer and a slow upload would occupy the publication path. Separating upload from publication lets the phone finish the expensive operation once and retry the small one independently. The application first authorizes an upload, then accepts a post containing the ready asset’s ID. Text-only posts skip the upload. The extra step buys independent progress, but leaves us responsible for abandoned uploads.

A different retry problem remains: Leo may press Publish, lose the response, and try again. The server cannot infer whether identical text means a retry or a deliberate second post. A client-supplied request key expresses that intent: every attempt at the same publication reuses the key. To remember the outcome, we need a **publish-request record** connecting that author and key to a request fingerprint and post ID. The transaction deep dive explains how those records stay consistent.

For following, the desired state is enough: “ensure I follow Leo” can be safely repeated. Scrolling needs a different kind of memory: where the previous page ended. Imagine a new post arrives after Maya reads her first page. An offset such as “skip 20” now counts from a different starting point and can repeat the old twentieth item. A cursor anchored to the last item avoids that shift. We order by an immutable server publication time plus a unique post ID to break ties, and put the last returned pair in the cursor. The next page selects strictly older pairs. This avoids insertion-induced repeats under stable membership and visibility, but does not create a frozen snapshot: follow changes and delayed visibility can change later pages. Refreshing starts again at the newest available posts.

HTTP resource operations fit these mobile-client journeys: create an upload or post, set a relationship, and retrieve a page. An internal RPC interface could express the same operations, but our workload does not yet give us a reason to add another protocol. The server derives the acting user from authentication. The compact contract is:

| Request | Purpose and result |
|---|---|
| `PUT /me/follows/{author_id}`; `DELETE /me/follows/{author_id}` | Ensure the follow exists or is absent. |
| `POST /uploads` with media type and size | Authorize a bounded upload; return an asset ID and upload destination. |
| `POST /posts` with text, asset IDs, and a request key | Publish ready media; return a stable post ID. |
| `GET /feed?limit=20&before=cursor` | Return descriptions, media references, and a next-page cursor. Omit the cursor for a refresh. |

For this design, JSON carries the small request and response bodies; media travels as files. Named fields make client debugging and operational inspection straightforward. A typed binary representation such as Protobuf could reduce field-name overhead and parsing work, but the actual gain depends on the payload and implementation; media bytes would be unchanged. JSON still needs a compatibility policy: clients should tolerate added optional fields, while existing field meanings and types stay stable. Protobuf offers an explicit schema and field identifiers, at the cost of code generation and tooling to inspect binary payloads. Readable metadata and independently evolving clients justify JSON here; we have no measured codec bottleneck. The useful comparison is bytes and parsing time for actual feed pages, including compression and client cost, rather than the label “binary.” If that measurement becomes material at our request rate, a typed binary contract earns another look.

These are the storage fields needed to support the operations, not a complete production schema:

| Record | Important fields and keys |
|---|---|
| Follow | `(reader_id, author_id)`, unique as a pair |
| Post | `post_id`, `author_id`, immutable server publication time, text, asset IDs |
| Media asset | `asset_id`, owner, immutable storage key, media type, readiness |
| Publish request | `(author_id, request_key)`, request fingerprint, resulting `post_id`; unique by author and key |

The ordering pair defines display order, not a global causal clock. Keeping it unchanged on a publication retry prevents retries from moving a post around the feed.

## High-level architecture

### Follow the bytes from publication to reading

I find it useful to follow the bytes before naming services. Suppose Maya’s page contains five 20 MB videos: fetching them all before displaying anything would transfer 100 MB, taking ten seconds at an illustrative sustained 10 MB/s. Twenty descriptions at roughly 1 KB each need about 20 KB, excluding thumbnails and protocol overhead. Shrinking the metadata cannot eliminate the video transfer; letting Maya read text before choosing which video to play can eliminate the wait.

That distinction gives object storage a specific job: hold immutable media files that phones can upload and download directly. An application service still needs to authorize those transfers and enforce publication rules. Follows, posts, asset state, and retry records belong in a relational database, such as PostgreSQL, because selection needs indexed relationships and publication needs an atomic update of related records. Storing everything as files would simplify bulk byte storage but make those operations harder. This is a logical starting architecture, not a claim that one database machine will meet the assumed peak; the next section examines its read work.

Leo first asks the application for an upload destination and sends his video to object storage. On publication, the application verifies that the asset belongs to Leo and that the completed object is ready before committing a post referring to it. Our baseline accepts supported ready-to-play media; producing additional renditions would introduce a separate processing step. Text-only posts skip this file path. The application commits the post and publish-request record together, then returns the post ID. Readers can now discover it without waiting for any copying to followers.

The file upload and database commit are separate operations. Allowing an abandoned upload to exist temporarily keeps incomplete media out of published posts without requiring a transaction across object storage and the database. Cleanup can reclaim old, unreferenced assets, but it must first claim them in database state that publication also checks, so attachment and cleanup cannot both win. A committed reference protects its file from that cleanup. This costs some temporary storage while keeping partial uploads out of the feed.

Maya’s follow request creates the relationship row. When she opens the feed, the application reads her current follows, selects their newest eligible posts below the cursor if present, and returns at most the requested page size. Leo’s retained history is eligible as soon as the follow commits; an unfollow removes him from subsequent selections. Reading the authoritative database preserves that behavior. A read replica would spread load, but its lag could make a completed follow appear ineffective; using one would require an explicit weaker freshness contract or routing recent relationship changes back to the authority.

The phone displays descriptions and thumbnails, then retrieves full media from the authorized object locations as needed. A failed video download leaves its description visible with a retry control. At the assumed 1,000 feed requests per second, 20 KB of descriptions per response is about 20 MB/s of metadata payload. Media demand depends on actual playback, so that path needs separate sizing and measurement. The application is responsible for selection, not relaying every video byte.

We now have a complete path for publishing, following, and browsing. The diagram summarizes those roles and dependencies:

![The phone requests publication and feed pages from the application, which uses the database and checks media readiness; the phone uploads and downloads media directly through object storage.](../../../generated/diagrams/sd-e2e-news-feed/context.svg)

A page limit bounds response size, but a query returning 20 rows might still scan a long history. I want us to distinguish those two costs before adding more infrastructure: small output does not imply a cheap query.

## Deep dives

### How can reads stay small as history grows?

The first **Scale reads** question is whether selection cost must grow with old history. If each of Maya's 200 followed authors has 100 retained posts, loading all their histories produces 20,000 candidates for a page of 20. The output is small, but the selection work grows with retained history.

Loading all those posts and sorting them is a useful reference algorithm, but most cannot possibly enter this page. An index on `(author_id, publication_time, post_id)` lets us seek directly to each author’s newest eligible posts below the cursor. Retrieve at most one page per author and batch the lookups: 200 follows should not require 200 sequential network waits. This adds index storage and maintenance on publication, in exchange for skipping older history. The database can merge the lists; if storage is later partitioned by author, the application can merge the returned sorted lists with a priority queue.

Here is the argument that makes the reduction safe. Any post below an author's newest 20 eligible posts already has 20 newer candidates ahead of it, so it cannot enter the overall first 20. For F followed authors and page size K, we retrieve at most F × K candidate entries, independent of retained history. Maya's example falls from 20,000 candidates to at most 4,000. This bounds candidate retrieval, not all physical database work; index seeks and storage access still cost time.

With the sorted lists in memory, an application merge takes roughly O(F + K log F) work after retrieval and O(FK) memory if all candidates are fetched. Retrieving keys first and fetching descriptions only for the selected posts trades an extra fetch step for avoiding thousands of unused descriptions. While indexed reads meet the latency target, this design has an important advantage: new follows are inexpensive and there is no background feed state to repair. The reusable idea is to reduce each sorted source to candidates that can still win before merging across sources.

### When should publication do more work to make reads cheaper?

Even bounded reads can repeat a lot of work. At R feed requests per second, the candidate budget is roughly R × F × K. Illustrative values R = 1,000, F = 200, and K = 20 yield four million entries per second. At 64 bytes per entry, that is about 256 MB/s of logical index data before descriptions and database overhead. It is not measured disk traffic; caching, CPU, and lookups determine the actual bottleneck.

Now we can see why moving work to publication might help. If those repeated lookups miss our latency target, doing the selection once when a post arrives can make later reads cheaper: the **Fan-out write** pattern. Unlike a shared cache of posts, this avoids recomputing which posts belong in each reader’s page. That optimization introduces a new entity for a specific reason. A **feed entry** stores the association between a reader and a post, together with its ordering key: `(reader_id, post_id, publication_time)`. A background worker inserts these references into followers’ ordered lists. Maya can then read a short list and fetch the descriptions. Keeping only references avoids multiplying text and media storage by audience size.

This trades read work for write amplification and visibility delay. If W posts arrive per second and their mean audience is A, fan-out needs about W × A inserts per second. W = 100 and A = 500 mean 50,000 inserts per second, while one million-follower author creates a million-write burst. Those rates make precomputation worth testing for ordinary authors, but they do not establish that any particular database can sustain it. The cutoff depends on measured read savings, insert throughput, storage growth, and worker lag. Audience size alone misses an important variable: an author whose followers rarely open the app creates many entries that nobody reads.

A million-write burst from one popular author can delay everybody else’s visibility. Keep such authors on the read path and merge their recent posts with precomputed entries for ordinary authors. We pay a few extra indexed reads to avoid the largest write bursts. Both sources use the same ordering key, with duplicate post IDs removed before returning the page. Changing an author’s strategy needs a coverage transition: retain read-time selection until backfill is complete, otherwise the optimization can create holes in the feed.

Precomputation also makes membership harder. Deleting a follow row no longer removes copied entries. Current follows must therefore filter those entries, with further scanning when stale entries occupy candidate slots. For a new follow, merge that author’s history at read time until backfill catches up. A bounded recent feed list needs the same fallback when scrolling beyond its retained window. If stale-entry scanning exceeds the read budget, return to indexed selection rather than declaring the feed exhausted. The stored list is an acceleration of the relationship query, not a replacement for its meaning.

In the **licensed research-feed variant**, following a publisher expresses interest; it does not establish permission to read its research. An entitlement is a separate grant from reader to licensed content. Check current authorization when returning descriptions and when serving media, even if a stored feed entry still exists. If revocation must stop new deliveries immediately, a previously issued long-lived object URL is insufficient: use an authorization-enforcing delivery path and fail closed when the required authority cannot be reached. Test that revocation blocks fresh retrieval through both a server-cached page and a saved media URL; it cannot retract bytes already downloaded. This costs an extra availability dependency, but an available feed cannot justify disclosing restricted content.

### What happens when publication or fan-out is retried?

Let’s return to Leo’s lost response and distinguish publication from delivery. Retrying publication blindly could create a second post, while refusing to retry could hide a successful publication. A durable request outcome removes that ambiguity. The **Data transactions** pattern commits the post and its request-key mapping together; saving the mapping afterward would leave a crash window with a post but no remembered outcome. A uniqueness constraint on `(author_id, request_key)` allows only one concurrent attempt to create the post. Retrying the same content returns the committed ID; reusing the key for different content is rejected using the stored fingerprint. Document the retry-record retention window, since this guarantee ends when that record expires. The handbook's [idempotency and duplicate handling](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) explains why a timeout leaves the outcome ambiguous.

Fan-out creates another gap: committing the post and then enqueueing distribution leaves a crash window in which a visible post never reaches stored feeds. The transaction now also needs a pending-work row. This outbox records unfinished distribution in the same database transaction. It adds worker and cleanup load to the database, but avoids needing an atomic commit across the database and a separate broker. The worker scans followers in stable ID order, inserts feed entries under a unique `(reader_id, post_id)` key, and saves its position after each follower batch. A crash after insertion but before progress recording causes harmless repeated inserts. Mark work complete only after the intended batches finish; use the history fallback above for follows created during distribution.

Batching follower inserts amortizes database round trips; bounding each batch prevents a large audience from monopolizing a worker. Pending work absorbs bursts; it does not create insert capacity. During an interval sustaining the illustrated 50,000 inserts per second, a worker fleet below that rate falls further behind even without a celebrity post. Recovery afterward requires spare capacity above the continuing arrival rate. The age of the oldest pending work reveals whether distribution meets the freshness target. Throttle new publications before the pending-work storage budget is exhausted. Already acknowledged work must remain recoverable. The handbook's [overload and backpressure](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md) explains why a queue cannot fix sustained overload. Here we own the publication API and can reject new writes before acceptance. That control does not transfer to an external market-data source that keeps transmitting; source ownership determines which overload policies are possible.

I use these commit boundaries to derive failure tests: lose the publish response and retry concurrently, then verify one post ID; kill a worker after inserting a batch but before recording progress, then verify that restart finishes distribution without duplicates. Run these against the database and worker implementation. For selection, compare indexed results with the simple full-history sort, including equal timestamps, unfollows, and inserts between pages under the stated cursor semantics. Measure query work as history grows and backlog recovery after a burst. These checks turn the design’s claims into observable behavior without pretending that a standalone merge exercise validates distributed recovery.

The lag and latency metrics above provide operational visibility. They are not an authoritative audit or replay record. If a finance application must reconstruct which research version was available to a decision-maker, it needs retained versions and delivery or access evidence under a separate contract. Rebuilding today’s feed from today’s follows cannot answer that historical question. Likewise, an asynchronous feed is suitable for browsing information, not for enforcing a current risk limit.

## Follow-ups and pitfalls

- **What if the feed is ranked?** Add scoring after candidate selection, then decide whether scrolling follows a saved ordered list or allows reshuffling. A chronological cursor alone cannot preserve ranked pages.
- **What if video startup is slow?** Cache immutable files near readers through a content-delivery network. Generate additional playable renditions asynchronously and record their readiness. Keep processing outside feed reads and measure playback separately from metadata latency.
- **What does chronological browsing leave out?** Late visibility can place a newly discoverable post above an existing cursor, so refresh may reveal items that scrolling missed. A stable historical snapshot or a lossless consumption interface needs a stronger contract than this browsing API.
