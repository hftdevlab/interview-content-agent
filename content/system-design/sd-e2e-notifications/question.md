# Design a Notification System

Design patterns: Data transactions; Multi-step workflows.

## Question and clarifications

Design a notification system that lets an application tell a user about something that needs their attention. For example, Maya comments on a document owned by Leo. Leo should find the notification in the application and, if his preferences allow it, receive email and mobile push alerts.

The prompt leaves the channels and delivery expectations open. We explicitly interpret it as **in-app, email, and mobile push**. Ask who chooses recipients, whether occasional duplicate alerts are acceptable, and whether notifications must arrive immediately. Peak recipient volume matters more than the number of triggering events: one comment sent to a million watchers is a different problem from one sent to Leo.

For this walkthrough, assume each request names one recipient, the calling application chooses that recipient, and messages are informational. Delivery within seconds is desirable, but it is not a hard deadline. The caller retries unacknowledged requests. The notification system takes responsibility once it accepts a request; reliably generating that first request from a saved comment is initially the caller's responsibility. These are illustrative assumptions, not requirements supplied by the original prompt.

Bulk campaigns, scheduling, and multiple regions would make this too large for one interview. Establish the single-recipient flow first, then focus on recovering failed sends and handling bursts.

## Requirements

### Functional requirements

- Applications can create a notification for a recipient.
- Users can browse their in-app inbox and mark notifications read.
- Users can configure email and push preferences; enabled channels receive delivery attempts.

### Non-functional requirements

- Acceptance should wait for durable storage, without waiting for an external provider. Assume committed database data survives application-process restarts.
- Retrying a create request should produce one inbox item. External delivery may repeat after an uncertain outcome; bounded retries are acceptable for these informational alerts.
- Slow or unavailable providers should not stall inbox access or consume unlimited worker capacity. Pending work and exhausted retries must remain visible to operators.

Cross-channel arrival order is unspecified. For the small baseline, preferences and destinations are captured at acceptance, with one active push device per user. A stricter unsubscribe policy is a follow-up rather than a hidden guarantee.

## Core entities

A **notification** is the logical message addressed to one user. It remains in that user's inbox whether or not email succeeds. A **delivery** tracks the work for one external channel, so a notification can have an email delivery and a push delivery with different outcomes. Retrying email creates another attempt on the same delivery, not another notification.

**User settings** hold channel preferences and destinations. Keeping settings separate lets Leo change future alerts without rewriting his inbox. This distinction between the message, channel work, and user settings gives us the vocabulary to design the interfaces.

## API and data schema

The caller needs a stable identity for its request so that a lost response does not create a second message. An illustrative interface is:

| Operation | Relevant input and result |
|---|---|
| `POST /notifications` | Caller-scoped request key, recipient ID, text or content reference, requested external channels. Returns a stable notification ID after commit. |
| `GET /me/notifications?cursor=...&limit=...` | Returns a bounded page of inbox items and a next-page cursor. |
| `PUT /me/notifications/{id}/read` | Sets read state; repeating the request leaves it read. |
| `PUT /me/notification-settings` | Updates enabled channels and verified destinations. |

Authenticate producer requests and authorize which recipients they may target. The `/me` operations derive the user from authentication, and a read-state update must check ownership. A request key identifies one logical notification for one recipient; reusing it with different content or requested channels is rejected.

A relational database can hold all three entities:

| Record | Fields needed for the flow |
|---|---|
| Notification | ID, caller ID, request key, recipient ID, content, creation time, read time. Unique `(caller_id, request_key)`. |
| Delivery | Notification ID, channel, destination snapshot, state, attempt count, next-attempt time. Unique `(notification_id, channel)`. |
| User settings | User ID, enabled channels, email address, push token. |

A push token is the destination supplied by the mobile platform. Delivery state starts as `pending` or `suppressed` by preferences and later becomes `accepted` by the provider or `failed`. Store enough of the original request to check whether a repeated key has the same meaning. Keep its identity for at least the supported caller retry window; removing it earlier would permit duplicate acceptance.

## High-level architecture

Start with an API server, a database, and a background delivery worker. The worker reads unfinished delivery rows and calls external providers. Those rows form a durable work queue, so the baseline needs no separate message broker. This lets the API respond after saving work while email and push proceed independently.

![The API stores inbox items and delivery work; the user reads the inbox while a worker sends pending email and push alerts.](../../../generated/diagrams/sd-e2e-notifications/context.svg)

Follow Maya's comment through the design. The calling application submits Leo's notification with a stable request key. The API checks authorization and reads Leo's settings. In one database transaction, it saves the notification and a delivery row for each requested external channel. Enabled channels become pending; disabled channels are recorded as suppressed. After commit, it returns the notification ID. Maya's request no longer depends on how long an email provider takes to answer.

Leo can now open his inbox even if no external alert has arrived. The API queries notifications by recipient, newest first. An index on recipient, creation time, and ID supports this access; the last time and ID in a page form a cursor for fetching the next page. Marking an item read updates that item's read time. Updating settings changes the snapshot used by later create requests.

Meanwhile, the worker selects due pending rows using an index on state and next-attempt time. It loads the saved content and destination, sends with a finite timeout, and records the result. If email is accepted and push has an invalid destination, only push fails. Provider acceptance means the provider took responsibility for the request; it does not establish that Leo saw or read it. Operators can trace the notification ID through suppression, pending attempts, and final outcomes without copying private message text into logs.

Loading the inbox on screen-open meets the chosen requirement. If immediate in-app updates become necessary, add a signal after commit to connected clients; reconnecting clients still fetch stored items. The handbook's [WebSocket and polling chapter](../../../release1/handbook-markdown/chapters/d7-websocket-and-http/chapter.md) supplies the transport background for that extension.

This completes the ordinary user journey. The remaining questions are how the saved work survives interrupted processing and whether the worker can keep up.

## Deep dives

### What if acceptance succeeds but the caller never hears back?

Suppose the database commits Leo's notification, then the API process dies before replying. The caller cannot tell whether acceptance happened, so it retries the same key. The unique constraint lets the API find the existing notification and return its ID without adding inbox or delivery rows. Simultaneous requests need the database constraint to arbitrate; checking for a key and then inserting without a constraint would race.

The **Data transactions** pattern connects the inbox item to its delivery work. Saving the inbox and then calling a provider directly leaves a crash window in which the item exists but no record says email is still due. Saving both the inbox and pending rows in one transaction removes that local gap: either both commit or neither does. If the transaction fails, there is no acceptance acknowledgment and the caller retains responsibility.

This boundary starts at the notification API. If the interviewer also requires a saved comment never to miss its first notification request, extend the same idea to the producing application. Save the comment and a pending request in one local transaction, then have a relay retry that request until the notification API acknowledges it. This pending-request table is an outbox. It closes the producer's gap without requiring the comment database and notification database to commit together.

### How do retries recover work without promising duplicate-free email?

The **Multi-step workflows** pattern appears because email and push finish at different times and can each fail. Their durable delivery rows let the worker resume unfinished steps after restart. A temporary provider error schedules another attempt with increasing delay and random variation, while invalid addresses or tokens fail permanently. After an illustrative five attempts, keep a failed row for investigation instead of silently dropping it.

Consider a worker that sends Leo's email and crashes before saving the provider's success response. Its row is still pending, so recovery sends again. Marking it successful before the call would avoid that repeat but could instead lose the email if the worker died before sending. A local transaction cannot decide what happened at a remote provider.

Where supported, send the same notification-ID-and-channel key on every attempt within the provider's duplicate-suppression window. Otherwise, the chosen contract accepts duplicate risk after an ambiguous timeout. The handbook's [idempotency and retry chapter](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) explains why a timeout cannot establish whether an external effect happened.

Even the attempt count deserves a boundary: durably reserve an attempt before starting its call so repeated crashes do not bypass the retry budget. A crash can then consume an attempt without sending. For these best-effort alerts, reaching the budget produces an inspectable failure with a possibly uncertain external outcome. It never justifies labeling the message read or delivered.

### What changes when the worker falls behind?

Use an illustrative load of 10 notifications per second with both external channels enabled: that produces 20 delivery jobs per second before retries. If provider calls average 0.2 seconds, one serial worker finishes only about 5 jobs per second. Pending work grows by about 15 rows per second even though the create API looks healthy.

A bounded set of concurrent sends overlaps network waits. At that average latency, roughly four in-flight requests merely keep pace with new work; measured variation and retries require headroom. Concurrency does not overcome a provider quota. If email allows 5 sends per second while 10 new emails arrive per second, its backlog still grows by at least 5 per second. Give email and push separate concurrency and rate budgets so slow email does not occupy every sender.

Multiple senders now need to agree who owns a row. Claim work in a short atomic database operation, recording an owner token and expiry time, called a lease. Make the network call outside the transaction, and accept the result update only from the current owner token. An expired lease allows recovery after a crash. It prevents routine double selection, but a paused sender could resume after expiry and still call the provider; the duplicate policy from the previous section remains necessary.

Track oldest pending age by channel alongside provider errors and exhausted retries. When storage or acceptable queue age is exhausted, reject new work before commit with a retryable response so the caller retains responsibility. Already accepted work remains queued or reaches a recorded outcome. A durable queue absorbs a burst; it cannot solve a permanent rate mismatch. These measurements determine when this small database-and-worker design needs more capacity, rather than adding infrastructure on speculation.

## Follow-ups and pitfalls

### What if Leo opts out while an email is waiting?

Recheck current settings before each attempt and suppress newly disabled work. Agree on the treatment of calls already in flight: a settings update cannot recall an email already accepted by a provider. This deliberately changes the baseline acceptance-time preference policy.

### What if one comment notifies thousands of watchers?

Store a job with a recipient-list reference and progress cursor, then create bounded batches of recipient notifications. Define the membership snapshot and use stable per-recipient request keys so restarting a batch is safe. This adds recipient expansion without making one large event monopolize the create request.

### What if a comment must arrive before its correction?

First ask whether ordered inbox display suffices; creation time and an ID tie-breaker give a stable display order. Strict dispatch order instead needs a per-recipient sequence and must stop later work from overtaking unresolved earlier work. Even ordered dispatch cannot promise the order in which external providers display messages.
