# Design a News Feed

## Interview prompt

Maya follows 200 people, including Leo, who has just posted a short video. She opens her feed to read the newest 20 updates and expects Leo's post to appear without downloading every video on the page. If five of those posts contain 20 MB videos, fetching them all before showing any text turns a quick glance into a 100 MB transfer. These values are illustrative; they give us a concrete request to reason about.

Design a news feed supporting different content formats. **Assumed interpretation:** a social following feed with text, images, and video. Explain how Leo publishes a post and how Maya retrieves a page of posts from people she follows.

A complete social platform is too large for one interview. Keep the passing answer to publication, media storage, and chronological feed reads. Once that works, agree with the interviewer whether to explore read scaling or reliable background distribution. Recommendations, advertising, and detailed video encoding are separate topics.

## What the interviewer is testing

**Core**

- Clarifying a vague product request and choosing a small, coherent system boundary.
- Connecting a compact data model to the publish and feed-read paths.
- Separating media bandwidth from post-selection work and calculating which resource becomes scarce.
- Explaining pagination and retries through concrete stored state rather than service names.

## Clarifying questions

Does “various formats” mean text, images, and video, or imported news formats? Should the feed show followed authors chronologically or rank recommendations? Is a short visibility delay acceptable? Are posts public, and must new follows include historical posts?

Then ask about peak feed reads, publication rate, follows per reader, large author audiences, and response-time expectations. Those answers determine whether ordinary database queries are enough. The worked answer uses the explicit assumptions below; ranking or private audiences would require revisiting them.

## Requirements and assumptions

**Core**

Assume authenticated users publish public posts, and a feed shows the newest retained posts by authors the reader currently follows. New follows include those authors' retained history. Use pages of 20 posts for illustration, with configured limits on page size, follows, text length, and upload size. These limits bound request work; their production values need workload evidence.

A short delay before a new post appears is acceptable. A successful publish means the post record is durably committed and its media is ready to retrieve. An application restart must not lose an acknowledged post. Retry a failed core feed read explicitly rather than disguising an unavailable database as an empty feed. A failed media download can leave the text visible with a retry control.

Choose chronological order for the baseline. Each post receives an immutable server-side publication timestamp and unique ID; the pair gives a deterministic newest-first display order, including timestamp ties. This is display order, not a global causal clock. Scrolling is not a frozen snapshot: follow changes or delayed visibility can change what later requests encounter, and a refresh starts from the newest available posts.

## Good solution

### Core — Start with one application and one database

An application process handles the phone's HTTP requests. A database process stores follow rows `(reader_id, author_id)` and post rows containing a unique ID, author, publication timestamp, text, content type, and references to media files. An object-storage service stores those image and video files under stable keys. A key in a post identifies a file; the application returns a download reference instead of putting the entire file into the feed response.

For a small service, this is enough architecture. Leo publishes one post record. When Maya opens her feed, the application reads whom she follows, selects their newest posts, and returns descriptions and media references. The phone displays text and thumbnails first and fetches full media as needed. There is no need to create a separate feed for every user before knowing whether these reads are expensive.

The media split follows directly from Maya's request. Sending five 20 MB videos before displaying the page takes at least 10 seconds at an illustrative sustained 10 MB/s to her phone. A database index cannot reduce those bytes. Returning 20 descriptions of roughly 1 KB each instead makes the initial payload about 20 KB, excluding thumbnails and protocol overhead. This improves initial display; video startup and playback still have their own network costs.

### Core — Make the two user journeys complete

Leo first uploads his file to an application-authorized location in object storage. The application verifies that the upload belongs to him and is ready to serve, then commits the post in the database. Text-only posts skip the upload. For the baseline, accept supported ready-to-play media; producing additional video formats can be a later background step. An abandoned upload can be collected once it is old and unreferenced, but it must never appear as a published post.

The acknowledgement comes after the database commit. Suppose the commit succeeds but Leo's phone loses the response: retrying blindly could create a duplicate. Have the client reuse a request key, and record `(author_id, request_key)` with the resulting post ID in the same transaction. A database uniqueness constraint lets only one concurrent attempt create the post. Another attempt returns the same ID; using that key for different content is rejected. This guarantee lasts for the configured retry-record retention window, which the API must document. The handbook's [idempotency and duplicate handling](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) explains the timeout ambiguity; here it protects publication.

For Maya's read, begin with a database query over her followed authors, ordered by publication timestamp and ID, limited to one page. At modest traffic and small histories, this may already meet the latency target. Inspect its execution plan and measured latency before replacing it. A final `LIMIT 20` alone does not prove the database avoided reading and sorting many more rows.

Maya's next-page request carries the last returned publication key. Query strictly older keys instead of skipping a fixed row count. If Leo adds a new post between requests, an offset such as “skip 20” shifts and can repeat an item; the exclusive key boundary stays put. Newer posts appear on refresh. With unchanged membership and visibility, this avoids repeats from insertions above the boundary; it does not promise a complete snapshot across concurrent changes.

### Core — Bound the read when history grows

The first useful scaling question is how many rows the database examines to return Maya's 20 items. If each of her 200 followed authors has 100 retained posts, loading all of their histories means sorting 20,000 candidates for one small page. That may still be tolerable at low traffic, but the cost grows with history even when the returned page does not.

Add an index ordered by `(author_id, publication_time, post_id)`. This is a database-maintained ordered structure that supports seeking to an author's recent posts or to an older cursor position. Read up to one page of eligible posts per author using that index, then select the newest 20 overall. Batch these operations rather than making 200 sequential network round trips. The database may perform the merge, or the application can use a priority queue in request memory to take the newest head from the sorted author lists.

Taking 20 from each author is sufficient: a post below an author's newest 20 eligible posts already has 20 newer candidates ahead of it, so it cannot enter the overall first 20. More generally, for F followed authors and page size K, this simple strategy retrieves at most F × K candidates. Maya's illustrative request examines at most 4,000 instead of 20,000, and that bound no longer grows with retained history. An application merge takes roughly O(F + K log F) work after retrieval; storing all fetched candidates uses O(FK) memory. The configured follow and page limits keep this bounded.

This remains a valid small design as long as indexed reads meet the measured workload. The application owns selection, the database owns searchable records, and file storage owns media bytes.

### Deep dive — Decide whether to pay on reads or writes

Read-time selection becomes expensive when many readers repeatedly ask about the same authors. Let R be feed reads per second. The candidate-read budget is approximately R × F × K. At illustrative values R = 1,000, F = 200, and K = 20, that is 4 million candidate entries per second. At 64 bytes per entry, it represents about 256 MB/s of logical index data before descriptions and database overhead. This is not measured disk traffic: cache hits matter, and database CPU, lookups, or concurrent requests may become the bottleneck first.

The alternative is to store an ordered list of post IDs for each reader in database rows. A background worker process copies a newly published post's ID into followers' lists. This copying is called fan-out. Maya can then read a short list directly, but every publication creates extra writes and may take time to reach all followers.

Compare the costs before choosing. If W authors publish per second and A is their mean audience, fan-out needs approximately W × A insertions per second. With W = 100 and A = 500, that is 50,000 writes per second. A single author with a million followers creates a million-write burst, regardless of the average. Keep selection on read while it meets the target; precompute lists when repeated read work justifies the writes and the allowed freshness delay permits asynchronous distribution.

The diagram shows the read-time baseline, without optional fan-out. Media is ready before publication succeeds, while reading the feed does not wait for full media downloads.

![Ready media precedes publication; feed descriptions and media downloads use separate requests.](../../../generated/diagrams/sd-e2e-news-feed/context.svg)

## Great solution improvements

**Deep dive — Optional extensions to a working baseline**

1. **Make background distribution recoverable.** If fan-out is chosen, commit the post and a pending-work row together. That row is an outbox: durable work for a worker process to consume. The worker inserts `(reader_id, post_id)` under a uniqueness constraint and saves progress after each follower batch. A crash between insertion and progress recording repeats harmless inserts. Current-follow filtering removes stale list entries; a new follow needs history backfill or a temporary read-time merge to preserve the baseline history behavior.
2. **Keep large audiences from dominating the work queue.** Merge exceptionally popular authors' posts on read while using precomputed lists for ordinary authors; deduplicate by post ID. Monitor oldest pending work and impose a storage budget. Throttle new publication before accepting more work than can be retained, rather than discarding acknowledged work. The handbook's [overload and backpressure](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md) explains why queuing alone cannot fix sustained overload. This application, unlike an exchange feed, can reject new writes before acceptance.
3. **Stretch — Improve media startup separately.** A content-delivery network uses proxy processes to cache files near readers. Immutable file keys allow safe byte reuse. If more video formats are needed, a worker process can consume uploaded-file jobs from a durable queue and record when each playable rendition is ready. Keep this processing outside the feed read, and measure video startup separately from metadata latency.

## Failure scenarios

**Core**

| Failure | Visible behavior and recovery |
|---|---|
| Leo uploads but publication fails | No visible post; retry publication or later collect the unreferenced file. |
| The publish response is lost after commit | A retry with the same key returns the committed post ID within the supported retry window. |
| Maya's database read fails | Return a retryable error, not a successful empty feed. |
| Leo's video download fails | Keep the description visible and let the phone retry the media request. |

For optional fan-out, a worker crash raises visibility delay. Durable progress and unique inserts allow it to resume without duplicate list entries. This is a reason to monitor pending-work age as well as request latency.

## Common pitfalls

- Sending full videos with the feed response, or treating a fast metadata response as proof of fast playback.
- Assuming a final page limit bounds database work without checking the access plan.
- Choosing fan-out automatically without comparing read demand, publication rate, and audience size.
- Calling a key cursor a consistent snapshot, or treating timestamp order as causal order.
- Adding private posts or deletion while continuing to serve unchecked cached references; those requirements need explicit visibility and media-access rules.

## Follow-up questions

### How would a million-follower author change the design?

**Deep dive:** Compare the write burst with repeated read demand. Explain a read-time merge for this author and how post IDs prevent duplicates while moving between strategies. Include history backfill or a fallback during the transition; a follower-count threshold alone is not a design.

### What changes if the feed must be ranked?

**Stretch:** A scoring process can select and order candidates, but it introduces feature reads and a latency budget. Decide whether scrolling uses a saved ordered list of IDs or allows reshuffling. The chronological cursor alone does not preserve ranked pages.

### How would you test the small baseline?

**Core:** Lose the acknowledgement after a publish commit, retry concurrently, and verify that one post ID exists. Insert a newer post between page requests and check for repeats under unchanged follow membership. Fail an upload and verify that it cannot become a visible post. Measure database rows examined as retained history grows. These require integration tests against the selected database and services; a standalone toy experiment would not establish those guarantees, so none is attached.

## Evaluation rubric

- **Core — Passing:** States the social-feed assumptions, explains both user journeys with a compact data model, separates media from descriptions, and gives an indexed read, key cursor, and retry-safe publication path. Says when the simple design is sufficient.
- **Deep dive — Strong:** Calculates read amplification and fan-out cost, identifies the scarce resource, and explains the freshness and recovery consequences of precomputation.
- **Stretch — Excellent:** Selects one justified extension and names the additional contract it requires, without making the baseline depend on advanced machinery.
- **Below the bar:** Lists service names without a request trace, invents compulsory scale or ranking, or cannot explain what remains stored after a failed publish response.
