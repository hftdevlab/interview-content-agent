# Design a Notification System

Design patterns: Data transactions; Multi-step workflows.

## Question and clarifications

Design a notification system that lets an application tell a user about something that needs their attention. For example, Maya comments on a document owned by Leo. Leo should find the notification in the application and, if his preferences allow it, receive email and mobile push alerts.

The prompt leaves the channels and delivery expectations open. I’ll interpret it as **in-app, email, and mobile push**, then clarify who chooses recipients, whether occasional duplicate alerts are acceptable, and whether notifications must arrive immediately. These answers decide whether I am designing recipient discovery, reliable message handling, or a deadline-sensitive alert service. Peak recipient volume matters more than the number of triggering events: one comment sent to a million watchers is a different problem from one sent to Leo.

For this walkthrough, I’ll assume each request names one recipient, the calling application chooses that recipient, and messages are informational. Delivery within seconds is desirable, but it is not a hard deadline. The caller retries unacknowledged requests. The notification system takes responsibility once it accepts a request; reliably generating that first request from a saved comment is initially the caller's responsibility. These are illustrative assumptions, not requirements supplied by the original prompt.

Bulk campaigns, scheduling, and multiple regions would make this too large for one interview. I’ll establish the single-recipient flow first, then focus on recovering failed sends and handling bursts. Single-recipient requests simplify ownership; they do not imply low aggregate traffic.

## Requirements

### Functional requirements

- Applications can create a notification for a recipient.
- Users can browse their in-app inbox and mark notifications read.
- Users can configure email and push preferences; enabled channels receive delivery attempts.

### Non-functional requirements

- Accepted notifications must survive application-process restarts. Inbox availability and prompt acceptance must not depend on external provider response times.
- Retrying a create request should produce one inbox item. External delivery may repeat after an uncertain outcome; bounded retries are acceptable for these informational alerts.
- Slow or unavailable providers should not stall inbox access or consume unlimited worker capacity. Pending work and exhausted retries must remain visible to operators.

Cross-channel arrival order is unspecified. For the baseline, preferences and destinations are captured at acceptance, with one active push device per user. A stricter unsubscribe policy is a follow-up rather than a hidden guarantee.

## Core entities

When Leo opens his inbox, he expects one item for Maya’s comment even if email was retried three times. I therefore need a durable identity for the message, separate from the work of sending it. A **notification** is that logical message addressed to one user; its read state belongs to the inbox, not to an email response.

Now suppose email succeeds but the push token is invalid. One “sent” flag on the notification cannot describe both outcomes. I’ll give each requested external channel a **delivery**: the saved work and outcome for one notification on one channel. Retrying email makes another attempt on its existing delivery. It must not create another inbox item or reset a successful push delivery. This separation costs extra records, but lets each channel progress independently.

Leo also needs to turn push off without changing yesterday’s inbox. **User settings** hold his enabled channels and verified destinations. At acceptance I’ll copy the relevant settings into the deliveries, so a queued job has a definite destination and policy. Reading settings only when sending would honor later changes, but would make the result depend on queue delay. I’ll keep the snapshot policy explicit and revisit immediate opt-out as a follow-up.

Conceptually, the application supplies a message and recipient; settings determine the external work; the inbox retains the message while each external delivery reaches its own outcome. That distinction will drive both the interfaces and the storage boundary.

## API and data schema

If the caller loses the acceptance response, it cannot know the notification ID we generated. I’ll therefore ask it to supply a stable request key before its first call and reuse that key on retries. The recipient and content say what to create; the key says whether this is new work. For Leo, inbox retrieval and marking read are separate operations because browsing a page need not mean reading every item. These needs give us four interfaces:

| Operation | Relevant input and result |
|---|---|
| `POST /notifications` | Caller-scoped request key, recipient ID, text or content reference, requested external channels. Returns a stable notification ID after commit. |
| `GET /me/notifications?cursor=...&limit=...` | Returns a bounded page of inbox items and a next-page cursor. |
| `PUT /me/notifications/{id}/read` | Sets read state; repeating the request leaves it read. |
| `PUT /me/notification-settings` | Updates enabled channels and verified destinations. |

Authenticate producer requests and authorize which recipients they may target. The `/me` operations derive the user from authentication, and a read-state update must check ownership. A request key identifies one logical notification for one recipient; reusing it with different content or requested channels is rejected.

For these HTTP interfaces I’ll use JSON on the wire, not just as interview notation. Human-readable fields help application teams diagnose rejected requests, and the illustrative workload below carries roughly 1 KB of message content per notification. JSON repeats field names and requires text parsing; Protobuf uses numbered fields and typed binary values, which can reduce metadata bytes and parsing work, but does not compress the message text itself. I would measure representative payloads before claiming a speedup. Binary messages also need schema-aware tooling for inspection. The [Protobuf encoding guide](https://protobuf.dev/programming-guides/encoding/) explains these representation differences.

Compatibility needs a policy with either choice: JSON clients must tolerate added fields, while Protobuf requires disciplined field-number and type evolution, as its [schema-update guidance](https://protobuf.dev/programming-guides/proto3/#updating) describes. I’ll retain JSON for straightforward integration here and reconsider Protobuf on a controlled internal path if measured bandwidth or parsing cost becomes significant. Changing the codec cannot remove provider quotas or the cost of persisting delivery state.

I’ll start with a relational database because accepting one notification changes several related records, and the inbox needs indexed retrieval by recipient. Separate stores could scale these access paths independently, but would introduce a consistency problem before we have evidence that one store is insufficient. The compact schema is:

| Record | Fields needed for the flow |
|---|---|
| Notification | ID, caller ID, request key, recipient ID, content, creation time, read time. Unique `(caller_id, request_key)`. |
| Delivery | Notification ID, channel, destination snapshot, state, attempt count, next-attempt time. Unique `(notification_id, channel)`. |
| User settings | User ID, enabled channels, email address, push token. |

A push token is the destination supplied by the mobile platform. Delivery state starts as `pending` or `suppressed` by preferences and later becomes `accepted` by the provider or `failed`. Store enough of the original request to check whether a repeated key has the same meaning. Keep its identity for at least the supported caller retry window; removing it earlier would permit duplicate acceptance.

## High-level architecture

I’ll follow Maya’s comment to see where the work needs to separate. The calling application knows why Leo should be notified, so it submits the recipient, content, channels, and request key to the notification API. This boundary lets the notification service handle delivery without learning every application’s rules for choosing recipients. The API authenticates the caller, checks recipient authorization, and reads Leo’s settings.

We could call email and push immediately, then save the inbox item. But a slow provider would delay acceptance, and a crash after sending could leave an alert with no inbox record. I want the durable message available first. The API therefore saves the notification and its requested deliveries in one database transaction: enabled channels are pending, disabled ones suppressed. It replies with the notification ID only after commit. A background worker can finish the slower external work without holding the caller open. The cost is asynchronous delivery: acceptance means responsibility was recorded, not that an alert has arrived.

Leo’s screen can now fetch the inbox through the API, independently of that worker. I’ll index notifications by recipient, creation time, and ID because this is exactly the lookup the screen makes. The last time and ID form a cursor for the next bounded page; this avoids shifting offset positions as new messages arrive. Marking read updates only the owned notification’s read time. Settings updates affect later acceptance snapshots.

For the worker, those saved delivery rows are already a durable queue. A separate broker would provide dedicated dispatch capacity, but would also require reliable transfer from the database into the broker. I’ll initially query due work through an index on state and next-attempt time, using bounded batches so polling does not load the whole backlog. This shares database resources with the inbox; measuring contention and pending age will tell us when that compromise stops working.

The worker loads saved content and destinations, makes provider calls with finite timeouts, and writes outcomes or retry times back to the delivery rows. Email and push can finish separately. Provider acceptance means the provider took responsibility for the request; it does not mean Leo saw it. Operators follow the notification ID through these states without logging private message text. Interrupted calls and competing workers need recovery rules, which I’ll develop next.

For in-app delivery, fetching stored items when the screen opens satisfies our current requirement. Keeping connections to every client would add connection management before we need live updates. If freshness while the screen is open becomes important, I’d add a post-commit signal and still fetch stored items on reconnect. The handbook’s [WebSocket and polling chapter](../../../release1/handbook-markdown/chapters/d7-websocket-and-http/chapter.md) covers that transport choice. The diagram now summarizes the two paths: durable inbox access and asynchronous external work.

![The API stores inbox items and delivery work; the user reads the inbox while a worker sends pending email and push alerts.](../../../generated/diagrams/sd-e2e-notifications/context.svg)

## Deep dives

### What if acceptance succeeds but the caller never hears back?

Suppose the database commits Leo's notification, then the API process dies before replying. The caller cannot tell whether acceptance happened, so it retries the same key. I’ll let the database’s unique constraint arbitrate creation, then find the existing notification and return its ID without adding inbox or delivery rows. Simultaneous requests need the database constraint to arbitrate; checking for a key and then inserting without a constraint would race.

This is why I use the **Data transactions** pattern to connect the inbox item to its delivery work. Saving the inbox and then calling a provider directly leaves a crash window in which the item exists but no record says email is still due. Saving both the inbox and pending rows in one transaction removes that local gap: either both commit or neither does. If the transaction fails, there is no acceptance acknowledgment and the caller retains responsibility.

This boundary starts at the notification API. If the interviewer also requires a saved comment never to miss its first notification request, I’d extend the same idea to the producing application: save the comment and a pending request in one local transaction, then have a relay retry that request until the notification API acknowledges it. This pending-request table is an outbox. It closes the producer's gap without requiring the comment database and notification database to commit together.

### How do retries recover work without promising duplicate-free email?

I need recovery at the channel level: retrying the whole notification after push fails could resend a successful email. The **Multi-step workflows** pattern records progress separately for each step, here using durable delivery rows. For temporary provider errors I’ll schedule retries with increasing delay and random variation, rather than let many workers hammer a recovering provider together. Invalid destinations fail permanently. An illustrative five-attempt budget bounds resource use for these informational alerts, at the cost of giving up on some that a later attempt might deliver. Exhausted work remains inspectable.

Consider a worker that sends Leo's email and crashes before saving the provider's success response. Its row is still pending, so recovery sends again. Marking it successful before the call would avoid that repeat but could instead lose the email if the worker died before sending. A local transaction cannot decide what happened at a remote provider.

Where supported, I’ll send the same notification-ID-and-channel key on every attempt within the provider's duplicate-suppression window. Otherwise, the chosen contract accepts duplicate risk after an ambiguous timeout. The handbook's [idempotency and retry chapter](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) explains why a timeout cannot establish whether an external effect happened.

To make that budget survive crashes, I’ll durably reserve an attempt before starting its call. Counting only completed calls would let repeated crashes bypass the limit. A crash can then consume an attempt without sending. For these best-effort alerts, reaching the budget produces an inspectable failure with a possibly uncertain external outcome. It never justifies labeling the message read or delivered.

### What changes when the worker falls behind?

I’ll size external work rather than count only API requests. For an illustrative busy application, assume 1,000 single-recipient notifications per second, roughly 1 KB of content each, and both external channels enabled. That means about 1 MB/s of content entering the service and 2,000 delivery jobs/s before retries. These are workload assumptions, not measured database or provider capacities. Even one day at that rate creates 86.4 million inbox items, so retention and measured storage capacity matter; a single database is a starting layout, not an unlimited scaling claim.

If provider calls average 0.2 seconds, one serial sender completes about five jobs/s. Keeping pace requires roughly 400 concurrent calls across the two channels before allowing for retries and latency variation. I’ll use bounded concurrency to overlap those waits, with separate channel budgets so slow email cannot occupy every sender. More threads alone cannot overcome a provider quota: if email permits only 800 sends/s while 1,000 new emails/s arrive, its backlog grows by at least 200/s. We must obtain more capacity or reduce admitted demand.

A burst is different from a sustained deficit. Suppose email normally receives 1,000 jobs/s and can send 1,500/s, but receives 3,000/s for one minute. It accumulates about 90,000 jobs, then needs about 180 seconds to drain at the spare 500/s, ignoring retries. The queue preserves work, but some alerts miss our desired seconds-level freshness. This gives me a reason to negotiate the burst target or buy headroom, rather than claiming that durable buffering solves latency.

I’ll claim a bounded batch of ready rows per database round trip, then dispatch within provider rate limits. Waiting to fill large batches would add avoidable delay during quiet periods; selecting up to a limit from already-due work avoids that wait. At the illustrative load, I’d measure inbox query latency alongside enqueue, claim, and completion throughput. If these compete beyond the database’s capacity, a broker fed by a reliable database relay can move dispatch pressure, while recipient-based partitioning can distribute inbox storage. Neither removes the underlying writes or a provider limit. Retention cleanup must also preserve request identities through the supported retry window and retain unresolved delivery content.

Multiple senders now need to agree who owns a row. I’ll claim work in a short atomic database operation, recording an owner token and expiry time, called a lease. Holding database locks throughout a slow network call would tie up shared resources, so the call runs outside the transaction; only the current owner token can update the result. An expired lease allows recovery after a crash. It prevents routine double selection, but a paused sender could resume after expiry and still call the provider; the duplicate policy from the previous section remains necessary.

I’ll track oldest pending age by channel alongside provider errors and exhausted retries. Queue length alone hides whether users are waiting seconds or hours. When storage or acceptable queue age is exhausted, the API rejects new work before commit with a retryable response so the caller retains responsibility; caller backoff is needed to avoid a retry storm. Already accepted work remains queued or reaches a recorded outcome. A durable queue absorbs a burst; it cannot solve a permanent rate mismatch. These measurements determine when this database-and-worker design needs more capacity, and which resource actually needs to grow.

## Follow-ups and pitfalls

### What if Leo opts out while an email is waiting?

I’d recheck current settings before each attempt and suppress newly disabled work. That buys a stronger opt-out policy at the cost of another read and a remaining race: a settings update cannot recall an email already accepted by a provider. This deliberately changes the baseline acceptance-time preference policy.

### What if one comment notifies thousands of watchers?

I’d move recipient expansion out of the create request: store a job with a recipient-list reference and progress cursor, then create bounded batches of recipient notifications. I need an agreed membership snapshot and stable per-recipient request keys so restarting a batch is safe. This adds recipient expansion without making one large event monopolize the create request.

### What if a comment must arrive before its correction?

I’d first ask whether ordered inbox display suffices; creation time and an ID tie-breaker give a stable display order. Strict dispatch order instead needs a per-recipient sequence and must stop later work from overtaking unresolved earlier work. Even ordered dispatch cannot promise the order in which external providers display messages.
