# Design a News Feed

## Question and clarifications

Design a news feed supporting different content formats. **Assumed interpretation:** a social following feed where people publish text, images, and video, then browse posts from authors they follow.

The first clarification is what “news feed” means: followed authors or recommended news, chronological order or ranking? For this walkthrough, choose public posts from followed authors, newest first. A new follow includes the author's retained history. Private audiences, deletion, recommendations, advertising, and detailed video encoding are outside this small baseline; adding them would require revisiting visibility or ordering.

Imagine Maya follows 200 people, including Leo, who has just posted a short video. She opens her feed to see the newest 20 updates. Those numbers are illustrative, not requirements supplied by the prompt. They help us ask two practical questions: how does Leo's post become available, and how can Maya see a useful page without downloading every video on it?

A whole social platform exceeds one interview. Start with publishing, following, and chronological reads. Once that works, explore read scaling and, if needed, reliable background distribution. Ask about peak reads, publication rate, audience sizes, and latency expectations before choosing that extra machinery.

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

These are illustrative service assumptions. We do not yet have evidence that the workload needs precomputed feeds or a particular numerical latency target.

## Core entities

A **user** can be both an author and a reader. A **follow** connects a reader to an author; the reader's current follows determine which authors are eligible for the feed. A **post** belongs to one author and carries text plus zero or more **media assets**. The assets are stored files, while the post holds references to them.

The **feed page** is initially a query result, not another durable copy of every post. This distinction keeps publication simple: Leo stores one post, and Maya's request selects it if she follows him. If repeated selection becomes expensive, we can later introduce stored feed entries without changing what a post means.

## API and data schema

A compact interface is enough to connect these entities to the two user journeys. The server derives the acting user from authentication.

| Request | Purpose and result |
|---|---|
| `PUT /me/follows/{author_id}`; `DELETE /me/follows/{author_id}` | Ensure the follow exists or is absent; repeating the same operation is harmless. |
| `POST /uploads` with media type and size | Authorize a bounded upload and return an asset ID and upload destination. |
| `POST /posts` with text, asset IDs, and a request key | Publish ready media and return a stable post ID. |
| `GET /feed?limit=20&before=cursor` | Return descriptions, media references, and a next-page cursor. Omit the cursor for a refresh. |

The database stores the following records. These are the fields needed for the discussion, not a complete production schema.

| Record | Important fields and keys |
|---|---|
| Follow | `(reader_id, author_id)`, unique as a pair |
| Post | `post_id`, `author_id`, immutable server publication time, text, asset IDs |
| Media asset | `asset_id`, owner, immutable storage key, media type, readiness |
| Publish request | `(author_id, request_key)`, request fingerprint, resulting `post_id`; unique by author and key |

Order posts by `(publication_time, post_id)` descending so timestamp ties have a deterministic answer. A cursor encodes the last returned pair, and later pages ask for strictly older pairs. This is display order, not a global causal clock. Scrolling is also not a frozen snapshot: follow changes or delayed visibility can affect later pages; refreshing starts again from the newest available posts.

## High-level architecture

Start with one application, one database, and object storage. The application handles publication and feed selection, the database owns follows and searchable post records, and object storage holds the large media files. The arrows below show request dependencies: the client uses the application for post metadata and accesses authorized media locations separately.

![The phone requests publication and feed pages from the application, which uses the database and checks media readiness; the phone uploads and downloads media directly through object storage.](../../../generated/diagrams/sd-e2e-news-feed/context.svg)

### Publish a post

Leo first asks the application for an upload destination, then sends his video directly to object storage. The application verifies ownership and readiness before accepting the asset in `POST /posts`. For this baseline, accept supported ready-to-play media; generating more renditions can come later. Text-only posts skip the upload.

The application commits the post and its publish-request record together, then acknowledges the post ID. The file remains independently stored under its immutable key. A failed upload cannot become a visible post; a completed upload abandoned before publication can be collected later once it is old and unreferenced. Cleanup must coordinate with publication so it cannot remove an asset being attached to a committed post. We will examine the lost-response case in the transaction deep dive.

### Follow an author and read the feed

Maya follows Leo by creating a follow row. Opening her feed asks the application to read her current follows and select their newest posts from the database, using the ordering key and page limit above. Because the baseline queries posts directly, Leo's retained history is eligible immediately after the follow commits. Unfollowing removes that author from subsequent feed selections.

The application returns descriptions and media references. Maya's phone displays text and thumbnails first, then fetches full media as needed. If five posts each contain a 20 MB video, sending them all before displaying the page requires a 100 MB transfer: at an illustrative sustained 10 MB/s, that alone takes ten seconds. Twenty descriptions of roughly 1 KB each need about 20 KB, excluding thumbnails and protocol overhead. This is why media belongs on a separate path. If a download fails, its description can stay visible with a retry control.

For scrolling, the application queries below the cursor's exclusive key boundary. If Leo publishes between page requests, the new post does not shift that boundary. By comparison, an offset such as “skip 20” can now repeat the old twentieth item. Under unchanged follow membership and visibility, key pagination avoids those insertion-induced repeats; newer posts appear on refresh.

This completes the small service. Its open question is cost: a query that returns only 20 rows may still examine and sort a large history. Inspect its execution plan and latency before assuming the page limit also limits database work.

## Deep dives

### How can reads stay small as history grows?

This is the **Scale reads** challenge. If each of Maya's 200 followed authors has 100 retained posts, loading all their histories produces 20,000 candidates for a page of 20. The output is small, but the selection work grows with retained history.

Add an index on `(author_id, publication_time, post_id)`. For each followed author, seek to the cursor boundary and retrieve at most one page of eligible posts in descending order. Batch these queries rather than making 200 sequential network round trips. The database can merge the results, or the application can use a priority queue to select the newest heads from the sorted author lists.

Why is one page per author enough? Any post below an author's newest 20 eligible posts already has 20 newer candidates ahead of it, so it cannot enter the overall first 20. For F followed authors and page size K, we retrieve at most F × K candidate entries, independent of retained history. Maya's example falls from 20,000 candidates to at most 4,000. This bounds candidate retrieval, not all physical database work; index seeks and storage access still cost time.

With the sorted lists in memory, an application merge takes roughly O(F + K log F) work after retrieval and O(FK) memory if all candidates are fetched. Retrieve keys first and fetch full descriptions for the selected posts when practical. Keep this design while indexed reads meet the measured workload: it is simple and makes new follows inexpensive.

### When should publication do more work to make reads cheaper?

Even bounded reads can repeat a lot of work. At R feed requests per second, the candidate budget is roughly R × F × K. Illustrative values R = 1,000, F = 200, and K = 20 yield four million entries per second. At 64 bytes per entry, that is about 256 MB/s of logical index data before descriptions and database overhead. It is not measured disk traffic; caching, CPU, and lookups determine the actual bottleneck.

The **Fan-out write** pattern moves that repeated selection work to publication. Add ordered feed-entry rows containing `(reader_id, post_id, publication_time)`. A background worker copies a new post's ID into its followers' lists. Maya then reads a short list and fetches the corresponding descriptions. The post and media remain stored once; only references are copied.

This trades read work for write amplification and visibility delay. If W posts arrive per second and their mean audience is A, fan-out needs about W × A inserts per second. W = 100 and A = 500 mean 50,000 inserts per second, while one million-follower author creates a million-write burst. Compare these costs and measured latency before changing the baseline.

For exceptionally popular authors, retain selection on read and merge their recent posts with ordinary authors' precomputed entries. Deduplicate by post ID and use the same ordering key. This hybrid limits large bursts, but adds work at read time and needs a transition plan when an author changes strategy. Backfill entries or retain a read-time fallback until coverage is complete.

Membership also needs care. Filter entries against current follows before returning a page, scanning further if stale entries occupy candidate slots. New follows need historical backfill or a temporary read-time merge to keep the promised history behavior. A bounded retained feed list similarly needs an older-history fallback. These costs are part of choosing precomputation, not optional details after it ships.

### What happens when publication or fan-out is retried?

Return to Leo's publish request. The database may commit even if his phone never receives the response. The **Data transactions** pattern lets the post and its request-key mapping succeed together. A uniqueness constraint on `(author_id, request_key)` allows only one concurrent attempt to create the post. Retrying the same content returns the committed ID; reusing the key for different content is rejected using the stored fingerprint. Document the retry-record retention window, since this guarantee ends when that record expires. The handbook's [idempotency and duplicate handling](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) explains why a timeout leaves the outcome ambiguous.

If fan-out is added, also commit a pending-work row with the post. This outbox is durable evidence that distribution remains to be done. The worker inserts feed entries under a unique `(reader_id, post_id)` key and saves its position after each follower batch. A crash after insertion but before progress recording causes harmless repeated inserts. Mark work complete only after the intended batches finish; use the history fallback above for follows created during distribution.

This makes distribution recoverable, not instantaneous. Watch the age of the oldest pending work to see whether freshness is deteriorating. Set a storage budget and throttle new publications before accepting more work than can be retained; do not silently discard acknowledged work. The handbook's [overload and backpressure](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md) explains why a queue cannot fix sustained overload. Here the product can reject new writes before acceptance, which gives us a useful control when capacity is exhausted.

## Follow-ups and pitfalls

- **What if the feed is ranked?** Add scoring after candidate selection, then decide whether scrolling follows a saved ordered list or allows reshuffling. A chronological cursor alone cannot preserve ranked pages.
- **What if video startup is slow?** Cache immutable files near readers through a content-delivery network. Generate additional playable renditions asynchronously and record their readiness. Keep processing outside feed reads and measure playback separately from metadata latency.
- **How would you test the baseline?** Lose a publish acknowledgement and retry concurrently; verify one post ID. Insert a newer post between pages and check for repeats under stable membership. Reject an unfinished upload, and measure rows examined as history grows. These are database and service integration checks; a standalone toy program would not establish those guarantees.
