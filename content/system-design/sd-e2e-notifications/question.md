# Design a Notification System

## Interview prompt

Design a notification system.

**Core — running scenario and scope.** Maya comments on a document owned by Leo. Leo should find one notification in the application; his preferences also enable email and mobile push. As an illustrative workload, the application creates 10 such notifications per second, and an email provider sometimes takes two seconds to respond. Waiting for that response would make Maya's comment feel slow, while losing the notification could leave Leo unaware that his input is needed.

Interpretation: support in-app, email, and mobile push notifications. For this example, each request names one recipient, messages are informational, and delivery within seconds is desirable rather than a hard deadline. These are illustrative assumptions, not fixed scale or reliability requirements. A full platform with bulk campaigns, scheduling, and multiple regions is too large for one interview; sketch the boundary, then agree whether to explore retries or bursts after establishing the small design.

## What the interviewer is testing

- Turning a broad prompt into a concrete user journey and a modest system boundary.
- Separating durable acceptance, provider acceptance, and a human actually seeing a message.
- Explaining how pending work survives a process crash without claiming duplicate-free external delivery.
- Locating the bottleneck with simple arithmetic before adding infrastructure.

## Clarifying questions

Ask which channels matter, who chooses recipients, whether occasional duplicates are acceptable, and whether the objective is immediate delivery or eventual visibility. Ask for peak recipient volume rather than just the number of triggering events: one comment sent to a million followers is a different problem.

For the running example, the calling application supplies the recipient and retries requests that have not been acknowledged. The notification system owns storage, preferences, and channel delivery after acceptance. Deriving recipients and reliably connecting a committed comment to its first notification request remain at the application boundary; an optional extension below closes that gap.

## Requirements and assumptions

**Core — the contract that drives the design.** An accepted request must leave a durable notification and a recorded disposition for each requested channel. A disposition means pending work, successful handoff, suppression by preferences, or an explicit failure; accepted work must not silently disappear. This assumes the database's committed data survives application-process restarts; recovery from destruction of the database is outside the small answer.

Use the same request identity when retrying. Leo sees one in-app item for that identity, but an external provider may receive a repeat after an ambiguous timeout. Email and push are best effort with bounded retries, not a promise that a person has read them. Cross-channel arrival order is unspecified. For simplicity, preferences are captured when the request is accepted; an unsubscribe policy requiring a later check would change the send path.

## Good solution

### Core — first try the direct path

Start with an application server process handling Maya's request and a relational database storing Leo's inbox. The process inserts an inbox row, then calls the email and push providers over network connections. Leo's app fetches his stored rows when he opens the notification screen and marks an item read through the same server. This is a reasonable direct design for a prototype where waiting and occasional missed external alerts are acceptable.

It does not meet our accepted-work contract. If the server crashes after inserting the inbox row but before sending email, nothing records that email is still due. Sending before inserting only moves the gap: Leo might receive email for a notification that was never saved. Even without a crash, two seconds waiting for email needlessly ties Maya's response time to another system.

Record the intent to send alongside the inbox item, then send later. A background worker is a loop in a separate process that reads due database rows and calls providers. The rows themselves form the durable work queue: a queue here is simply a table of unfinished delivery attempts, not an additional message-broker service. One server, one database, and one worker process are enough to explain the baseline.

### Core — keep the stored state small

Three kinds of rows support the ordinary journey:

| Stored rows | Fields that matter and why |
|---|---|
| Notification | Stable ID, caller request key, recipient, text or content reference, creation time, and read time. A unique constraint on caller identity plus request key prevents duplicate acceptance. |
| Delivery | Notification ID, channel, destination snapshot, state, attempt count, and next-attempt time. One row per notification and external channel prevents creating a second delivery job on a request retry. |
| User settings | Email address, push destination token, and enabled channels. A push token is the address supplied by the mobile platform for a device; assume one active device for this example. |

The request key identifies one logical notification for one recipient. A retry with the same key but different content is rejected, rather than silently changing an existing notification. Keep these identities for at least the supported retry window; deleting the identity while callers can still retry allows duplicates.

On a create request, the server authenticates the calling application and checks that it may notify Leo. In one database transaction, it inserts the notification and delivery rows, recording disabled channels as suppressed. It acknowledges with the stable notification ID only after commit. If the response is lost, retrying the same key returns the existing ID. A database uniqueness constraint arbitrates simultaneous requests; a separate check followed by an insert would race.

For the inbox, an index beginning with recipient and then creation time and ID supports a bounded page of Leo's newest notifications. A cursor containing the last time and ID retrieves the next page without loading the whole inbox. Reads and read-state updates are authorized as Leo, and setting a read time again does not create another item. Loading on screen-open is enough for this contract. If live updates become necessary, the handbook's [WebSocket and polling chapter](../../../release1/handbook-markdown/chapters/d7-websocket-and-http/chapter.md) explains the connection choices; live transport would supplement the saved inbox.

### Core — finish or record each external attempt

The worker selects due pending rows through an index on state and next-attempt time, then sends their stored content with a finite timeout. Provider acceptance marks a row accepted, not delivered or read. Invalid addresses or tokens fail permanently. Temporary errors schedule retries with increasing delay and random variation to avoid synchronized retries. After an illustrative five attempts, retain a failed row for investigation.

Leave work pending until its result is saved so a restarted worker can recover it. A crash after provider acceptance but before saving success can cause a duplicate send. Where supported, reuse a notification-ID-and-channel key within the provider's duplicate-suppression window. Otherwise accept duplicate risk: local uniqueness cannot suppress an external side effect. The handbook's [idempotency and retry chapter](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) explains this timeout ambiguity.

Leo now has a durable inbox, Maya does not wait for email, and each external channel has inspectable work or an outcome. This design suffices while the database and bounded worker capacity handle measured peaks with acceptable queue age; no broker, global ordering, or database partitioning is needed.

![Commit separates acceptance from sending; worker restarts can repeat a provider call without losing saved intent.](../../../generated/diagrams/sd-e2e-notifications/context.svg)

### Deep dive — when the worker falls behind

Return to Maya and Leo's workload. At an illustrative 10 notifications per second with both external channels enabled, the worker receives 20 delivery jobs per second. If calls average 0.2 seconds, a serial worker completes only about 5 jobs per second. Its pending work grows by about 15 rows per second even though the create API looks healthy. The bottleneck is time waiting for provider responses, not the inbox lookup.

A bounded set of worker threads or asynchronous network requests can overlap those waits. At 20 jobs per second and 0.2 seconds per call, about four requests are in flight on average merely to keep pace; provision measured headroom for variation and retries. Extra concurrency does not overcome a provider quota. If email permits only 5 sends per second while 10 new emails arrive per second, the email backlog still grows by at least 5 per second.

Once multiple senders can select rows, claim each row in a short atomic database operation. Store an owner token and an expiry time, called a lease, so another sender may reclaim work after a crash. Send outside the transaction, and accept outcome updates only from the current owner token. A lease prevents routine double selection, but a paused sender can still resume after expiry and call the provider; provider-side duplicate suppression or the stated duplicate tolerance remains necessary.

Give email and push separate concurrency budgets so a slow email provider does not occupy every sender. Track oldest pending age per channel, provider errors, and permanent failures. Limit admission before committing new work when storage or acceptable queue age is exhausted; return a retryable rejection so the caller retains responsibility. A durable queue absorbs a burst, but cannot absorb a permanent rate mismatch. Choose limits from the delivery objective and actual provider capacity, not from an arbitrary queue length.

## Great solution improvements

**Stretch — choose only if the interviewer changes the scope.**

1. **Close the comment-to-notification gap.** If losing the first request is unacceptable, the application writes a pending notification request in the same transaction as Maya's comment. A relay process retries those saved rows until the notification server acknowledges the stable request key. This table is commonly called an outbox; it extends the guarantee to the producing application.
2. **Handle large recipient lists incrementally.** If Maya's comment must alert many watchers, save a job row with a recipient-list reference and a progress cursor. A worker creates bounded batches of recipient notifications with stable per-recipient keys. Restarting a batch is safe, and one large event cannot monopolize the create request.
3. **Add immediate in-app updates only when required.** A server process holding persistent connections can signal Leo's connected app after commit. Reconnecting clients still fetch saved inbox rows, so a dropped live signal does not become a lost notification.

## Failure scenarios

**Core — check the boundaries.** These traces test the design without requiring a runnable experiment.

| Failure | Expected behavior |
|---|---|
| Server dies before transaction commit | No acceptance is promised; caller retries the same key. |
| Commit succeeds but acknowledgment is lost | Retry returns the saved ID without new jobs or another inbox item. |
| Worker dies before sending | Pending work survives and is tried after restart. |
| Provider accepts but its response is lost | Outcome is uncertain; retry may duplicate unless the provider suppresses the stable key. |
| Push destination is invalid | Record failure for push; email and the inbox remain independent. |
| Provider stays unavailable | Attempts are delayed and bounded; failed rows remain inspectable, and backlog limits constrain new acceptance. |

## Common pitfalls

- Saying “delivered” when only the database or provider has acknowledged. Specify whose acknowledgment is being measured.
- Saving the inbox and enqueueing in a separate system without explaining the crash between those writes. The baseline uses one transaction in one database.
- Retrying with a new identity, marking success before sending, or assuming a lease makes a provider call happen exactly once.
- Adding senders without checking provider limits, or accepting unlimited work while promising delivery within seconds.

## Follow-up questions

**Deep dive — realistic changes to the contract.**

### What if Leo opts out while an email is waiting?

Recheck current settings before the attempt and mark newly disabled work suppressed. Agree what happens to a call already in flight: a settings update cannot recall an email already accepted by the provider. Strict cancellation would need a more precise boundary than the baseline acceptance-time preference snapshot.

### What if Maya's comment must precede her later correction?

First ask whether ordered inbox display suffices; creation time plus an ID tie-breaker provides a stable display order. Strict dispatch order needs a per-recipient sequence and prevents later work from overtaking unresolved earlier work. Even ordered dispatch cannot promise the order in which external providers display messages.

### How would you investigate “Leo never received it”?

Trace the stable ID from acceptance through preference suppression, attempts, and provider responses. Distinguish a missing inbox row from a pending email, an invalid token, and provider acceptance without evidence of display. Log identifiers and outcomes without unnecessarily copying private message content.

## Evaluation rubric

**Core — a passing answer** explains the single-recipient journey, a paginated authorized inbox, transactional creation of pending delivery work, and a worker that records outcomes and retries temporary failures. It states when that design is sufficient and recognizes that a timeout can hide a successful external send.

**A strong answer** derives concurrency from provider latency, notices provider quotas and retry load, preserves stable identities across restarts, and uses queue age to make delivery delay visible. It keeps the foundational answer understandable before discussing multiple workers.

**A weak answer** lists infrastructure without tracing Maya's request, promises exactly-once email from a local queue, or has no explanation for a crash between storing a notification and sending it. Advanced extensions do not compensate for a missing acceptance boundary.
