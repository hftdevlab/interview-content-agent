# Design a News Feed

## Question and clarifications

Design a news feed supporting different content formats. **Assumed interpretation:** a social following feed where people publish text, images, and video, then browse posts from authors they follow.

I first need to settle what “news feed” means. A recommendation feed needs candidate discovery and scoring; a following feed starts from relationships the user chose. I’ll take the latter interpretation and show public posts newest first, so we can focus on publishing and efficient selection rather than a ranking model. A new follow includes the author's retained history. Private audiences, deletion, recommendations, advertising, and detailed video encoding are outside this small baseline; adding them would require revisiting visibility or ordering.

Imagine Maya follows 200 people, including Leo, who has just posted a short video. She opens her feed to see the newest 20 updates. Those numbers are illustrative, not requirements supplied by the prompt. They help us ask two practical questions: how does Leo's post become available, and how can Maya see a useful page without downloading every video on it?

A whole social platform exceeds one interview. I’ll build publishing, following, and chronological reads, then use read scaling and reliable background distribution as the deep dives. To make that choice concrete, I’ll use illustrative peak rates of 1,000 feed requests and 100 new posts per second, 200 followed authors per typical reader, and a mean audience of 500 per post, with some million-follower authors. These assumptions describe a read-heavy service with uneven audiences; they are not facts supplied by the prompt. The large audiences matter even if most users look like Maya.

Design patterns: Scale reads; Fan-out write; Data transactions.

## Requirements

### Functional requirements

- Authenticated users can publish text and supported image or video attachments.
- Users can follow or unfollow authors and browse their currently followed authors' retained posts, newest first.
- Users can scroll through pages and load media separately from post descriptions.

### Non-functional requirements

- Show a useful first page promptly. Measure feed-response latency separately from video startup; a large media file should not delay all the text.
- Preserve acknowledged posts across application restarts. A short visibility delay is acceptable, but an unavailable feed must return a retryable error rather than look successfully empty.
- Keep read work bounded as history grows. Configure limits on follows, page size, text length, and upload size; choose production values from workload evidence.

For this walkthrough, I’ll aim for a first-page response within 300 ms at the 95th percentile and ordinary post visibility within a few seconds at the assumed peak. These are illustrative targets to test, not measured performance. They let us judge whether moving selection work away from reads is worth delaying visibility.

## Core entities

When Leo publishes and Maya reads, they are using two roles of the same account. I’ll call that account a **user**, rather than introduce separate author and reader identities. Maya’s choice to see Leo’s updates must survive between visits, so we also need a **follow**: a directed relationship from a reader to an author. Reversing it has a different meaning; Leo need not follow Maya back.

Leo’s video and its caption should appear as one item, even when thousands of readers view it. That gives us a **post**, owned by one author and identified independently of any reader’s feed. But uploading a video may finish long before Leo presses Publish, or may fail halfway through. I therefore need to distinguish the published item from a **media asset**, an uploaded file with an owner and a readiness state. A post references ready assets; the files are not copied into each reader’s view.

Maya’s **feed page** is the newest slice of posts eligible through her current follows. I can derive it from posts and relationships instead of storing a separate feed immediately. That makes a new follow simple: Leo’s retained posts already exist and become eligible. The cost is repeating selection when Maya returns. We’ll use that cost to decide later whether a stored feed entry earns its place in the design.

## API and data schema

I want Leo’s phone to upload a large file independently of the small publish request. If the publish call also carried the video, a network retry would repeat an expensive transfer and a slow upload would occupy the publication path. I’ll first authorize an upload, then publish using its asset ID once the file is ready. Text-only posts need only the second call.

A different retry problem remains: Leo may press Publish, lose the response, and try again. The server cannot infer whether identical text means a retry or a deliberate second post. I’ll have the client reuse a request key for attempts at the same publication. To remember the outcome, we need a **publish-request record** connecting that author and key to a request fingerprint and post ID. The transaction deep dive explains how those records stay consistent.

For following, the desired state is enough: “ensure I follow Leo” can be safely repeated. For scrolling, I need to identify where the previous page ended. With an offset such as “skip 20,” an insertion at the front can make the old twentieth item appear twice. I’ll instead order by an immutable server publication time plus a unique post ID to break ties, and put the last returned pair in a cursor. The next page selects strictly older pairs. This avoids insertion-induced repeats under stable membership and visibility, but does not create a frozen snapshot: follow changes and delayed visibility can change later pages. Refreshing starts again at the newest available posts.

The server derives the acting user from authentication. These interfaces now follow from the two journeys:

| Request | Purpose and result |
|---|---|
| `PUT /me/follows/{author_id}`; `DELETE /me/follows/{author_id}` | Ensure the follow exists or is absent. |
| `POST /uploads` with media type and size | Authorize a bounded upload; return an asset ID and upload destination. |
| `POST /posts` with text, asset IDs, and a request key | Publish ready media; return a stable post ID. |
| `GET /feed?limit=20&before=cursor` | Return descriptions, media references, and a next-page cursor. Omit the cursor for a refresh. |

I’ll use JSON for these small request and response bodies and transfer media as files. Named fields make client debugging and operational inspection straightforward. A typed binary representation such as Protobuf could reduce field-name overhead and parsing work, but the actual gain depends on the payload and implementation; media bytes would be unchanged. JSON still needs a compatibility policy: clients should tolerate added optional fields, while existing field meanings and types stay stable. Protobuf offers an explicit schema and field identifiers, at the cost of code generation and tooling to inspect binary payloads. Here I’d start with JSON because readable metadata and independently evolving clients matter more than an unmeasured codec saving. If metadata bandwidth or parsing becomes material, I’d benchmark both on real feed pages before changing the contract.

These are the storage fields needed to support the operations, not a complete production schema:

| Record | Important fields and keys |
|---|---|
| Follow | `(reader_id, author_id)`, unique as a pair |
| Post | `post_id`, `author_id`, immutable server publication time, text, asset IDs |
| Media asset | `asset_id`, owner, immutable storage key, media type, readiness |
| Publish request | `(author_id, request_key)`, request fingerprint, resulting `post_id`; unique by author and key |

The ordering pair defines display order, not a global causal clock. I’ll keep it unchanged when retrying a publication so retries cannot move a post around the feed.

## High-level architecture

### Follow the bytes from publication to reading

I’ll separate the flow into small searchable records and large files. Suppose Maya’s page contains five 20 MB videos: fetching them all before displaying anything would transfer 100 MB, taking ten seconds at an illustrative sustained 10 MB/s. Twenty descriptions at roughly 1 KB each need about 20 KB, excluding thumbnails and protocol overhead. Shrinking the metadata cannot eliminate the video transfer; letting Maya read text before choosing which video to play can eliminate the wait.

That distinction gives object storage a specific job: hold immutable media files that phones can upload and download directly. An application service still needs to authorize those transfers and enforce publication rules. I’ll store follows, posts, asset state, and retry records in a relational database because feed selection needs indexed relationships and publication needs an atomic update of related records. Storing everything as files would simplify bulk byte storage but make those operations harder. This is a logical starting architecture, not a claim that one database machine will meet the assumed peak; the next section examines its read work.

Leo first asks the application for an upload destination and sends his video to object storage. On publication, the application verifies that the asset belongs to Leo and that the completed object is ready before committing a post referring to it. I’ll initially accept supported ready-to-play media; producing additional renditions would introduce a separate processing step. Text-only posts skip this file path. The application commits the post and publish-request record together, then returns the post ID. Readers can now discover it without waiting for any copying to followers.

The file upload and database commit are separate operations. I prefer allowing an abandoned upload to exist temporarily over exposing a post with an unfinished video. Cleanup can reclaim old, unreferenced assets, but it must first claim them in database state that publication also checks, so attachment and cleanup cannot both win. A committed reference protects its file from that cleanup. This costs some temporary storage while keeping partial uploads out of the feed.

Maya’s follow request creates the relationship row. When she opens the feed, the application reads her current follows, selects their newest eligible posts below the cursor if present, and returns at most the requested page size. Leo’s retained history is eligible as soon as the follow commits; an unfollow removes him from subsequent selections. I’ll start reads against the authoritative database so replica lag does not silently weaken that behavior.

The phone displays descriptions and thumbnails, then retrieves full media from the authorized object locations as needed. A failed video download leaves its description visible with a retry control. At the assumed 1,000 feed requests per second, 20 KB of descriptions per response is about 20 MB/s of metadata payload. Media demand depends on actual playback, so I would size and measure that path separately. The application is responsible for selection, not relaying every video byte.

We now have a complete path for publishing, following, and browsing. The diagram summarizes those roles and dependencies:

![The phone requests publication and feed pages from the application, which uses the database and checks media readiness; the phone uploads and downloads media directly through object storage.](../../../generated/diagrams/sd-e2e-news-feed/context.svg)

A page limit bounds response size, but a query returning 20 rows might still scan a long history. That is the unresolved cost I’ll address first, before adding more infrastructure.

## Deep dives

### How can reads stay small as history grows?

I first want selection cost to stop growing with old history: the **Scale reads** challenge. If each of Maya's 200 followed authors has 100 retained posts, loading all their histories produces 20,000 candidates for a page of 20. The output is small, but the selection work grows with retained history.

I could load all those posts and sort them, but most cannot possibly enter this page. An index on `(author_id, publication_time, post_id)` lets me seek directly to each author’s newest eligible posts below the cursor. I’ll retrieve at most one page per author and batch the lookups so 200 follows do not mean 200 sequential network waits. This adds index storage and maintenance on publication, in exchange for skipping older history. The database can merge the lists; if storage is later partitioned by author, the application can merge the returned sorted lists with a priority queue.

Why is one page per author enough? Any post below an author's newest 20 eligible posts already has 20 newer candidates ahead of it, so it cannot enter the overall first 20. For F followed authors and page size K, we retrieve at most F × K candidate entries, independent of retained history. Maya's example falls from 20,000 candidates to at most 4,000. This bounds candidate retrieval, not all physical database work; index seeks and storage access still cost time.

With the sorted lists in memory, an application merge takes roughly O(F + K log F) work after retrieval and O(FK) memory if all candidates are fetched. I’ll retrieve keys first and fetch descriptions only for the selected posts, trading an extra fetch step for avoiding thousands of unused descriptions. I’d keep this design while indexed reads meet the latency target: it makes new follows inexpensive and has no background feed state to repair. The reusable idea is to reduce each sorted source to candidates that can still win before merging across sources.

### When should publication do more work to make reads cheaper?

Even bounded reads can repeat a lot of work. At R feed requests per second, the candidate budget is roughly R × F × K. Illustrative values R = 1,000, F = 200, and K = 20 yield four million entries per second. At 64 bytes per entry, that is about 256 MB/s of logical index data before descriptions and database overhead. It is not measured disk traffic; caching, CPU, and lookups determine the actual bottleneck.

If those repeated lookups miss our latency target, I can buy cheaper reads by doing work when a post arrives: the **Fan-out write** pattern. Unlike a shared cache of posts, this avoids recomputing which posts belong in each reader’s page. I now need a **feed entry**, a stored reference associating a reader with an eligible post and its ordering key: `(reader_id, post_id, publication_time)`. A background worker inserts these references into followers’ ordered lists. Maya can then read a short list and fetch the descriptions. Keeping only references avoids multiplying text and media storage by audience size.

This trades read work for write amplification and visibility delay. If W posts arrive per second and their mean audience is A, fan-out needs about W × A inserts per second. W = 100 and A = 500 mean 50,000 inserts per second, while one million-follower author creates a million-write burst. Those rates make precomputation worth testing for ordinary authors, but they do not establish that any particular database can sustain it. I’d compare measured read savings against insert throughput, storage growth, and worker lag before selecting the cutoff.

A million-write burst from one popular author can delay everybody else’s visibility. Instead of distributing that post to every follower, I’ll keep such authors on the read path and merge their recent posts with precomputed entries for ordinary authors. We pay a few extra indexed reads to avoid the largest write bursts. I’ll deduplicate by post ID and retain the same ordering key. Changing an author’s strategy needs a coverage transition: retain read-time selection until backfill is complete, otherwise the optimization can create holes in the feed.

Precomputation also makes membership harder. Deleting the follow row no longer removes copied entries, so I’ll filter them against current follows and scan further when stale entries occupy candidate slots. For a new follow, I’ll merge that author’s history at read time until backfill catches up. A bounded recent feed list needs the same fallback when scrolling beyond its retained window. This is why I would not introduce precomputed feeds solely because reads outnumber writes: the saved selection work must justify maintaining and repairing a second view of the data.

### What happens when publication or fan-out is retried?

Returning to Leo’s lost response, blindly retrying could create a second post, while refusing to retry could hide a successful publication from him. I need a durable answer to “what happened to this request?” The **Data transactions** pattern lets me commit the post and its request-key mapping together; saving the mapping afterward would leave a crash window with a post but no remembered outcome. A uniqueness constraint on `(author_id, request_key)` allows only one concurrent attempt to create the post. Retrying the same content returns the committed ID; reusing the key for different content is rejected using the stored fingerprint. Document the retry-record retention window, since this guarantee ends when that record expires. The handbook's [idempotency and duplicate handling](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) explains why a timeout leaves the outcome ambiguous.

Fan-out creates another gap: if I commit the post and then enqueue distribution, a crash between those steps leaves a visible post that never reaches stored feeds. I’ll therefore commit a pending-work row with the post. This outbox records unfinished distribution in the same database transaction. It adds worker and cleanup load to the database, but avoids needing an atomic commit across the database and a separate broker. The worker scans followers in stable ID order, inserts feed entries under a unique `(reader_id, post_id)` key, and saves its position after each follower batch. A crash after insertion but before progress recording causes harmless repeated inserts. Mark work complete only after the intended batches finish; use the history fallback above for follows created during distribution.

I’ll batch follower inserts to amortize database round trips, while limiting each batch so one large audience does not monopolize a worker. Pending work absorbs bursts; it does not create insert capacity. At 50,000 average inserts per second, a worker fleet sustaining less than that falls further behind even without a celebrity post. I’ll watch the age of the oldest pending work against the freshness target and throttle new publications before the pending-work storage budget is exhausted. Already acknowledged work must remain recoverable. The handbook's [overload and backpressure](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md) explains why a queue cannot fix sustained overload. Here the product can reject new writes before acceptance, which gives us a useful control when capacity is exhausted.

## Follow-ups and pitfalls

- **What if the feed is ranked?** Add scoring after candidate selection, then decide whether scrolling follows a saved ordered list or allows reshuffling. A chronological cursor alone cannot preserve ranked pages.
- **What if video startup is slow?** Cache immutable files near readers through a content-delivery network. Generate additional playable renditions asynchronously and record their readiness. Keep processing outside feed reads and measure playback separately from metadata latency.
- **How would you test the baseline?** Lose a publish acknowledgement and retry concurrently; verify one post ID. Insert a newer post between pages and check for repeats under stable membership. Reject an unfinished upload, and measure rows examined as history grows. These are database and service integration checks; a standalone toy program would not establish those guarantees.
