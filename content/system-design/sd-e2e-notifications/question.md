# Design a Notification System

Design patterns: Data transactions; Multi-step workflows.

## Question and clarifications

Design a notification system that lets an application tell a user about something that needs their attention. For example, Maya comments on a document owned by Leo. Leo should find the notification in the application and, if his preferences allow it, receive email and mobile push alerts.

I want to begin with what “notify” means to Leo. An inbox item remains available when he next opens the application; email and push try to draw his attention outside it. Those are different promises, even though they start with the same comment. We will interpret the open-ended prompt as **in-app, email, and mobile push**. Before choosing infrastructure, settle who chooses recipients, whether occasional duplicate alerts are acceptable, and whether delivery has a deadline. Each answer changes the work we own. One comment sent to a million watchers, for example, creates a recipient-discovery and fan-out problem that a comment sent to Leo does not.

For this walkthrough, we assume each request names one recipient, the calling application chooses that recipient, and messages are informational. Delivery within seconds is desirable, but it is not a hard deadline. The caller retries unacknowledged requests. The notification system takes responsibility once it accepts a request; reliably generating that first request from a saved comment is initially the caller's responsibility. These are illustrative assumptions, not requirements supplied by the original prompt.

A complete platform with bulk campaigns, scheduling, and multiple regions exceeds one interview. We will develop the single-recipient flow, then examine acceptance, external-send recovery, and bursts. Single-recipient requests simplify ownership; they do not imply low aggregate traffic. To keep capacity decisions concrete, use an illustrative busy workload of 1,000 notifications/s with roughly 1 KB of content each and both external channels enabled. Later we will test a threefold, one-minute burst against provider capacity.

## Requirements

### Functional requirements

- Applications can create a notification for a recipient.
- Users can browse their in-app inbox and mark notifications read.
- Users can configure email and push preferences; enabled channels receive delivery attempts.

### Non-functional requirements

- Accepted notifications must survive application-process restarts. Inbox availability and prompt acceptance must not depend on external provider response times.
- Retrying a create request should produce one inbox item. External delivery may repeat after an uncertain outcome; bounded retries are acceptable for these informational alerts.
- Slow or unavailable providers should not stall inbox access or consume unlimited worker capacity. Pending work and exhausted retries must remain visible to operators.
- Recovery must be testable: restarting a process at an acceptance or send boundary should leave explainable state. Seconds-level delivery is the normal-load goal; throughput and queue age determine whether bursts can meet it.

Before we carry this design into a trading firm, I want to separate informing a person from controlling financial activity. **Domain variant: operational alerts at a fund** might report that a reconciliation failed or a risk service rejected an order. The notification helps a person investigate; it does not perform the rejection or authorize further trading. That is why recoverability and visible failure matter here, while microsecond delivery does not. An asynchronous alert must never become a prerequisite for the risk engine to stop unsafe activity; the handbook’s [pre-trade risk chapter](../../../release1/handbook-markdown/chapters/e3-pretrade-risk-engine/chapter.md) develops that separate control boundary.

Cross-channel arrival order is unspecified. For the baseline, preferences and destinations are captured at acceptance, with one active push device per user. A stricter unsubscribe policy is a follow-up rather than a hidden guarantee.

## Core entities

When Leo opens his inbox, he expects one item for Maya’s comment even if email was retried three times. Notice the identity we need to preserve: the message stays the same while attempts to attract his attention multiply. A **notification** is that logical message addressed to one user; its read state belongs to the inbox, not to an email response.

Now suppose email succeeds but the push token is invalid. One “sent” flag on the notification cannot describe both outcomes. We can express that distinction with a **delivery** for each requested external channel: the saved work and outcome for one notification on one channel. Retrying email makes another attempt on its existing delivery. It must not create another inbox item or reset a successful push delivery. This separation costs extra records, but lets each channel progress independently.

Leo also needs to turn push off without changing yesterday’s inbox. **User settings** hold his enabled channels and verified destinations. Copying the relevant settings at acceptance gives each queued delivery a definite destination and policy. Reading settings only when sending would honor later changes, but would make the result depend on queue delay. For this design we keep the snapshot policy and revisit immediate opt-out as a follow-up. The reusable idea is to identify when a policy takes effect, rather than let a worker’s timing decide it accidentally.

Conceptually, the application supplies a message and recipient; settings determine the external work; the inbox retains the message while each external delivery reaches its own outcome. That distinction will drive both the interfaces and the storage boundary.

## API and data schema

If the caller loses the acceptance response, it cannot know the notification ID we generated. This tells us where the retry identity must originate: the caller supplies a stable request key before its first call and reuses it on retries. The recipient and content say what to create; the key says whether this is new work. For Leo, inbox retrieval and marking read are separate operations because browsing a page need not mean reading every item. These needs give us four interfaces:

| Operation | Relevant input and result |
|---|---|
| `POST /notifications` | Caller-scoped request key, recipient ID, text or content reference, requested external channels. Returns a stable notification ID after commit. |
| `GET /me/notifications?cursor=...&limit=...` | Returns a bounded page of inbox items and a next-page cursor. |
| `PUT /me/notifications/{id}/read` | Sets read state; repeating the request leaves it read. |
| `PUT /me/notification-settings` | Updates enabled channels and verified destinations. |

Authenticate producer requests and authorize which recipients they may target. The `/me` operations derive the user from authentication, and a read-state update must check ownership. A request key identifies one logical notification for one recipient; reusing it with different content or requested channels is rejected.

REST over HTTP fits these create, browse, and update operations because application callers need ordinary resource access and benefit from standard HTTP tooling. An RPC interface could also express the operations, but the workload gives us no reason to require a specialized service-call contract. We will use JSON on the wire, not just as interview notation. Human-readable fields help application teams diagnose rejected requests, and our illustrative workload carries roughly 1 KB of message content per notification. JSON repeats field names and requires text parsing; Protobuf uses numbered fields and typed binary values, which can reduce metadata bytes and parsing work, but does not compress the message text itself. Representative payload measurements are needed before claiming a speedup. Binary messages also need schema-aware tooling for inspection. The [Protobuf encoding guide](https://protobuf.dev/programming-guides/encoding/) explains these representation differences.

Compatibility needs a policy with either choice: JSON clients must tolerate added fields, while Protobuf requires disciplined field-number and type evolution, as its [schema-update guidance](https://protobuf.dev/programming-guides/proto3/#updating) describes. At our assumed content size and rate, straightforward integration is the stronger reason to retain JSON; measured bandwidth or parsing pressure on a controlled internal path could reverse that choice. Changing the codec cannot remove provider quotas or the cost of persisting delivery state.

The relationships now suggest a relational database, such as PostgreSQL: accepting one notification changes several related records, and the inbox needs indexed retrieval by recipient. Separate stores could scale these access paths independently, but would introduce a consistency problem before we have evidence that one store is insufficient. The compact schema is:

| Record | Fields needed for the flow |
|---|---|
| Notification | ID, caller ID, request key, recipient ID, content, creation time, read time. Unique `(caller_id, request_key)`. |
| Delivery | Notification ID, channel, destination snapshot, state, attempt count, next-attempt time. Unique `(notification_id, channel)`. |
| User settings | User ID, enabled channels, email address, push token. |

A push token is the destination supplied by the mobile platform. Delivery state starts as `pending` or `suppressed` by preferences and later becomes `accepted` by the provider or `failed`. Store enough of the original request to check whether a repeated key has the same meaning. Keep its identity for at least the supported caller retry window; removing it earlier would permit duplicate acceptance.

## High-level architecture

Let’s follow Maya’s comment and use the differences in waiting time to find the component boundaries. The calling application knows why Leo should be notified, so it submits the recipient, content, channels, and request key to the notification API. This boundary lets the notification service handle delivery without learning every application’s rules for choosing recipients. The API authenticates the caller, checks recipient authorization, and reads Leo’s settings.

We could call email and push immediately, then save the inbox item. But a slow provider would delay acceptance, and a crash after sending could leave an alert with no inbox record. The useful separation is between recording responsibility and performing the external effect. The API therefore saves the notification and its requested deliveries in one database transaction: enabled channels are pending, disabled ones suppressed. It replies with the notification ID only after commit. A background worker can finish the slower external work without holding the caller open. The cost is asynchronous delivery: acceptance means responsibility was recorded, not that an alert has arrived.

Leo’s screen can now fetch the inbox through the API, independently of that worker. An index on recipient, creation time, and ID follows directly from that lookup. The last time and ID form a cursor for the next bounded page; this avoids shifting offset positions as new messages arrive. Marking read updates only the owned notification’s read time. Settings updates affect later acceptance snapshots.

For the worker, those saved delivery rows are already a durable queue. A separate broker would provide dedicated dispatch capacity, but would also require reliable transfer from the database into the broker. Querying due work through an index on state and next-attempt time, in bounded batches, gives us a starting dispatcher without loading the whole backlog. This shares database resources with the inbox; measuring contention and pending age will tell us when that compromise stops working.

The worker loads saved content and destinations, makes provider calls with finite timeouts, and writes outcomes or retry times back to the delivery rows. Email and push can finish separately. Provider acceptance means the provider took responsibility for the request; it does not mean Leo saw it. Operators follow the notification ID through these states without logging private message text. Interrupted calls and competing workers need recovery rules, which I’ll develop next.

For in-app delivery, fetching stored items when the screen opens satisfies our current requirement. Keeping connections to every client would add connection management before we need live updates. If freshness while the screen is open becomes important, a post-commit signal can prompt a refresh, while fetching stored items on reconnect repairs missed signals. The handbook’s [WebSocket and polling chapter](../../../release1/handbook-markdown/chapters/d7-websocket-and-http/chapter.md) covers that transport choice. The diagram now summarizes the two paths: durable inbox access and asynchronous external work.

![The API stores inbox items and delivery work; the user reads the inbox while a worker sends pending email and push alerts.](../../../generated/diagrams/sd-e2e-notifications/context.svg)

## Deep dives

### What if acceptance succeeds but the caller never hears back?

Suppose the database commits Leo's notification, then the API process dies before replying. The caller cannot tell whether acceptance happened, so it retries the same key. A preliminary lookup seems sufficient until two retries arrive together: both can find no record and create an item. The database’s unique constraint must arbitrate creation. After a conflict, the API compares the saved request and returns the existing ID for a matching retry, without adding inbox or delivery rows. Thus the key describes logical work rather than a particular network call.

The **Data transactions** pattern connects the inbox item to its delivery work. Saving the inbox and then calling a provider directly leaves a crash window in which the item exists but no record says email is still due. Saving both the inbox and pending rows in one transaction removes that local gap: either both commit or neither does. If the commit outcome is unknown, the caller retains the request and retries its key. A database partition that prevents a durable commit therefore prevents new acceptance; replying successfully from process memory would violate our recovery promise. Provider outages, in contrast, need not stop acceptance while durable capacity remains. This is the availability distinction that matters here.

This boundary starts at the notification API. If the requirement expands to ensuring that every saved comment produces a request, the same reasoning applies one step earlier: save the comment and a pending request in one local transaction, then have a relay retry that request until the notification API acknowledges it. This pending-request table is an outbox. It closes the producer's gap without requiring the comment database and notification database to commit together.

I would test this boundary by stopping the API just after commit but before its response, then retrying concurrently. There should be one inbox item, the original settings snapshot, and one delivery per requested channel. Injecting failure before commit should leave none of those new records. These tests exercise the responsibility transfer that a happy-path send cannot establish.

### How do retries recover work without promising duplicate-free email?

The separate delivery entity now earns its place: retrying the whole notification after push fails could resend a successful email. The **Multi-step workflows** pattern records progress separately for each step, here using durable delivery rows. Immediate retries appear to improve freshness, but simultaneous failures would make workers hammer a recovering provider together. Increasing delay with random variation spreads that load, trading some freshness for a better chance of recovery. Invalid destinations fail permanently. An illustrative five-attempt budget bounds resource use for these informational alerts, at the cost of giving up on some that a later attempt might deliver. Exhausted work remains inspectable.

Consider a worker that sends Leo's email and crashes before saving the provider's success response. Its row is still pending, so recovery sends again. Marking it successful before the call would avoid that repeat but could instead lose the email if the worker died before sending. A local transaction cannot decide what happened at a remote provider.

Where supported, the worker sends the same notification-ID-and-channel key on every attempt within the provider's duplicate-suppression window. Otherwise, the chosen contract accepts duplicate risk after an ambiguous timeout. The handbook's [idempotency and retry chapter](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) explains why a timeout cannot establish whether an external effect happened.

The attempt budget itself must survive crashes, so the worker durably reserves an attempt before starting its call. Counting only completed calls would let repeated crashes bypass the limit. A crash can then consume an attempt without sending. For these best-effort alerts, reaching the budget produces an inspectable failure with a possibly uncertain external outcome. It never justifies labeling the message read or delivered. A fake provider that accepts a request and then times out lets us test precisely this ambiguity: recovery must preserve the inbox identity and expose the uncertain outcome, even when an external duplicate occurs. Injected clocks and provider responses also let tests advance retry delays without real sleeps.

### What changes when the worker falls behind?

Here I want us to count the work created by a request, rather than treating API throughput as delivery throughput. Our illustrative 1,000 notifications/s, 1 KB content, and two enabled channels mean about 1 MB/s of content entering the service and 2,000 delivery jobs/s before retries. These are workload assumptions, not measured database or provider capacities. Even one day at that rate creates 86.4 million inbox items, so retention and measured storage capacity matter; a single database is a starting layout, not an unlimited scaling claim.

If provider calls average 0.2 seconds, one serial sender completes about five jobs/s. Keeping pace requires roughly 400 concurrent calls across the two channels before allowing for retries and latency variation. Bounded concurrency overlaps those waits, with separate channel budgets so slow email cannot occupy every sender. This is waiting on provider I/O; it does not call for 400 dedicated CPU cores or trading-path networking techniques. More threads alone cannot overcome a provider quota: if email permits only 800 sends/s while 1,000 new emails/s arrive, its backlog grows by at least 200/s. We must obtain more capacity or reduce admitted demand.

A burst is different from a sustained deficit. Suppose email normally receives 1,000 jobs/s and can send 1,500/s, but receives 3,000/s for one minute. It accumulates about 90,000 jobs, then needs about 180 seconds to drain at the spare 500/s, ignoring retries. The queue preserves work, but some alerts miss our desired seconds-level freshness. That arithmetic tells us what decision remains: negotiate the burst freshness target or buy enough headroom to meet it. Buffering alone cannot deliver the seconds-level goal.

Batching reduces database round trips: claim up to a bounded number of ready rows, then dispatch within provider rate limits. Waiting to fill large batches would add avoidable delay during quiet periods; selecting up to a limit from already-due work avoids that wait. At the illustrative load, measure inbox query latency alongside enqueue, claim, and completion throughput; otherwise faster dispatch could hide a slower user inbox. If these compete beyond the database’s capacity, a broker fed by a reliable database relay can move dispatch pressure, while recipient-based partitioning can distribute inbox storage. Neither removes the underlying writes or a provider limit. Retention cleanup must also preserve request identities through the supported retry window and retain unresolved delivery content.

Multiple senders now need to agree who owns a row. A short atomic database operation can claim work by recording an owner token and expiry time, called a lease. Reserving the attempt in that same operation makes the retry budget apply across workers; claims beyond the budget become terminal failures. Holding database locks throughout a slow network call would tie up shared resources, so the call runs outside the transaction; only the current owner token can update the result. An expired lease allows recovery after a crash. It prevents routine double selection, but a paused sender could resume after expiry and still call the provider; the duplicate policy from the previous section remains necessary.

Oldest pending age by channel, provider errors, and exhausted retries tell us whether the system is meeting its purpose. Queue length alone hides whether users are waiting seconds or hours. When storage or acceptable queue age is exhausted, the API rejects new work before commit with a retryable response so the caller retains responsibility; caller backoff is needed to avoid a retry storm. Already accepted work remains queued or reaches a recorded outcome. A durable queue absorbs a burst; it cannot solve a permanent rate mismatch. These measurements determine which resource needs to grow. A load test should reproduce the burst, verify the drain time, and keep querying the inbox while email is stalled.

In the fund-operations variant, a common incident can alert many users at once even when the firm has few employees. Capacity follows incident fan-out, not headcount. These delivery records support operational investigation; finite retention, preference suppression, and exhausted retries make them unsuitable as the authoritative financial audit or replay record. Keep that record in the owning business system and include its event reference in the alert. Recovery can then explain what was sent without pretending that an email outcome proves what a risk engine did.

## Follow-ups and pitfalls

### What if Leo opts out while an email is waiting?

Rechecking current settings before each attempt can suppress newly disabled work. That buys a stronger opt-out policy at the cost of another read and a remaining race: a settings update cannot recall an email already accepted by a provider. This deliberately changes the baseline acceptance-time preference policy.

### What if one comment notifies thousands of watchers?

The create request would otherwise wait for all that expansion. Move recipient expansion into resumable work: store a job with a recipient-list reference and progress cursor, then create bounded batches of recipient notifications. We need an agreed membership snapshot and stable per-recipient request keys so restarting a batch is safe. This adds recipient expansion without making one large event monopolize the create request.

### What if a comment must arrive before its correction?

First distinguish display order from causal order: creation time and an ID tie-breaker give a stable display order, but concurrent acceptance need not preserve the application’s comment-before-correction relationship. Strict causal dispatch order needs producer ordering information and a per-recipient sequence and must stop later work from overtaking unresolved earlier work. Even ordered dispatch cannot promise the order in which external providers display messages.
