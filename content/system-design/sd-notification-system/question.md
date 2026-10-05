# Design a Notification System

> **Level:** Foundation · 45 minutes
>
> **You will learn:** accepting durably and working asynchronously · idempotency keys · bounded retries · priority lanes · burst arithmetic
>
> **Related questions:** [Design a Distributed Task Scheduler](../sd-task-scheduler/question.md) · [Design a Log Publishing and Query System](../sd-log-publishing-query/question.md)
>
> **Handbook:** [Ch 29 — *Sending It Twice*](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) · [Ch 24 — *When the Market Outruns You*](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md)

## The question

> Design a notification system.

Inside a trading firm, the notification system is the internal platform other services call when a person needs to know something. A desk breached its loss limit. The overnight reconciliation failed. A large order filled. The end-of-day P&L report is ready.

A service hands over a message and a recipient. The platform picks the channels — chat, email, SMS, pager — and delivers.

Most days it is quiet. Then a venue's feed drops at the open and fifty services alert at once.

**The crux: keep urgent alerts fast while bulk traffic surges, and never lose one.**

> **Finance lens.** The consumer-tech version of this question is about scale: push notifications to millions of app users, marketing campaigns. Here the audience is a few thousand employees, but bursts arrive *together with market events*, and a missed page is a risk incident, not a lost click. One more difference: this system informs people; it never controls trading. The risk engine blocks the order, and the notification tells a human it happened ([Handbook Ch 30 — *The Check You Cannot Skip*](../../../release1/handbook-markdown/chapters/e3-pretrade-risk-engine/chapter.md)).

## Requirements

### Functional requirements

1. Services can send a notification to a person or a group — a desk, a distribution list, or whoever is on call — by chat, email, SMS, or pager.
2. Users can set channel preferences and quiet hours. Critical alerts ignore quiet hours.
3. Senders and operators can see what happened to every notification: delivered, failed, or suppressed, and why.

Out of scope: deciding *when* to alert (that belongs to monitoring), template authoring, read receipts, and escalation (a follow-up).

### Non-functional requirements

We need a number before writing these. Assume about 400,000 notifications a day: roughly 5 per second on average. That is almost nothing.

Alerts never arrive evenly, though. When a venue's market-data feed drops at 09:30, every strategy and service watching it alerts in the same minute. Say 100,000 deliveries in 60 seconds: **about 1,700 per second, more than 300 times the average.** That burst shapes the whole design.

1. **At-least-once.** An accepted notification is never silently lost. A rare duplicate is acceptable: twice beats never.
2. **Critical in seconds.** Critical alerts reach the provider within 5 seconds of acceptance, even during a storm.
3. **Storms.** Absorb about 2,000 deliveries per second for several minutes.
4. **Traceable.** Every notification's fate is queryable for 30 days.

Out of scope: guaranteeing that a human reads it (providers own the last mile), ordering across channels, and multi-region failover.

These pull against each other. At-least-once means retries, and retries add load exactly when a storm leaves the least room. Keep that tension in mind; it drives the deep dives.

## Core entities

- **Notification** — what a service asked for: one message, one severity, one target (a person or a group), and the sender's idempotency key.
- **Delivery** — one notification to one person on one channel, with a status and an attempt count.
- **Recipient** — a person, with contact points (chat handle, email, phone, pager) and preferences.
- **Group** — a desk, a list, or an on-call rotation that resolves to recipients when we send.

The relationship that matters is **one notification, many deliveries**. A critical alert to an eight-person desk, sent by chat and SMS, is one notification and sixteen deliveries. Each delivery succeeds, fails, or retries on its own. If one trader's SMS fails, we retry that delivery, not the other fifteen.

## API

Sending is the main call:

```text
POST /notifications  ->  202 Accepted { notificationId }
{
  idempotencyKey,               // chosen by the sender, reused on every retry
  target: { userId | groupId },
  severity,                     // critical | normal
  title, body,
  dedupKey                      // optional, e.g. "feed-stale:XNAS"
}
```

The response is `202 Accepted` rather than `200 OK`. In our first version we will call providers inline, but once delivery moves off the request path, acceptance and delivery stop being the same event. Committing to `202` now saves changing the contract later.

```text
GET /notifications/{id}
    ->  { status, deliveries: [{ userId, channel, status, reason }] }
PUT /users/{userId}/preferences  { channels, quietHours }
```

Two fields earn their place later: `idempotencyKey` in the second deep dive and `dedupKey` in the third.

> **In the interview.** It is fine to start with a smaller contract and add fields when you reach the problem they solve. Say that you are doing it. Interviewers reward a contract that evolves for a reason over one that arrives complete and unexplained.

## High-level design

We will satisfy one functional requirement at a time with the simplest thing that works. The non-functional requirements are tempting, but a working system on the board comes first.

### 1) Send a notification to a person or a group

Start with one critical alert to one person.

1. The risk service calls `POST /notifications`.
2. The Notification API authenticates the caller and looks up the recipient's contact points.
3. It writes a notification row and one `PENDING` delivery row per channel.
4. It calls each provider inline.
5. It marks each delivery `SENT` or `FAILED` and returns.

![One request writes the notification, calls the providers inline, and records the outcome.](../../../generated/diagrams/sd-notification-system/step1-direct-send.svg)

Postgres is enough. The rows are small, the normal write rate is tiny, and we will want transactions shortly. Contact points sync in from the firm's directory, so a send never waits on the directory service.

Groups add one lookup. Before writing deliveries, the API expands the group: a desk's members from the directory, the current on-call person from the rotation schedule.

We expand at send time, not when the alert rule was written. A page at 02:00 should reach whoever is on call at 02:00.

> **In the interview.** A common mistake is designing the last mile: persistent connections to phones, SMTP servers, carrier integrations. Our platform decides who gets what on which channel, and keeps the receipt. The providers deliver to the device. Saying this early keeps the interview on the problems you own.

### 2) Respect preferences and quiet hours

This needs no new components. Preferences live on the recipient row, and the API checks them just before sending:

- **Channel turned off** — skip it.
- **Quiet hours, normal severity** — hold the delivery until the quiet hours end.
- **Critical severity** — always send.

A skipped delivery is recorded as `SUPPRESSED` with a reason, never dropped silently. At 07:00 someone will ask why a trader missed the reconciliation alert. "Suppressed: quiet hours" answers that in one query.

Holding a delivery until morning needs something that wakes up later and sends it. We do not have that yet; the first deep dive builds it.

![Groups and preferences add lookups and a suppression reason; the provider call is still inline.](../../../generated/diagrams/sd-notification-system/step2-groups-preferences.svg)

### 3) Show what happened to every notification

The delivery rows already are the record. `GET /notifications/{id}` reads them, and an index on recipient and time serves "what did this person receive today?". After 30 days, rows move to cheap archive storage.

### What is still broken

The system works. It meets none of the non-functional requirements:

1. **The provider call sits inside the request.** A slow SMS provider makes every caller slow. If the API crashes after writing `PENDING` but before calling the provider, the notification is never sent, which breaks at-least-once.
2. **Retries can double-send.** If a caller times out and retries, we create a second notification. If we retry a provider call that actually succeeded, the trader is paged twice.
3. **A storm buries the page.** A hundred thousand "feed stale" alerts and one loss-limit page share one pipe. The page waits its turn.

Each becomes a deep dive.

## Deep dives

### 1) How do we never lose an accepted notification?

The fix is to separate two moments: *accepting* a notification and *delivering* it. Once we accept, we owe a delivery attempt, even if every process restarts.

**Bad: retry inside the request.** Keep the inline call and retry a few times on failure. The caller now waits through every retry, and a crash still loses whatever was in flight. More retries make the request slower without making it safer.

**Good: the database is the queue.** In one transaction, the API writes the notification and its `PENDING` deliveries, then returns `202`. A pool of dispatcher workers picks up due deliveries:

```sql
UPDATE deliveries SET claimed_until = now() + interval '30 seconds'
WHERE id IN (
  SELECT id FROM deliveries
  WHERE status = 'PENDING' AND next_attempt_at <= now()
    AND (claimed_until IS NULL OR claimed_until < now())
  ORDER BY next_attempt_at
  LIMIT 100
  FOR UPDATE SKIP LOCKED)
RETURNING id;
```

`SKIP LOCKED` lets many workers poll at once without blocking on each other's rows. The `claimed_until` column is a lease: if a worker dies mid-send, the lease expires and another worker picks the rows up. [Design a Distributed Task Scheduler](../sd-task-scheduler/question.md) shows what a lease alone cannot prevent — a paused worker waking up — and how a fencing token closes the gap.

The claim is a short transaction. The worker commits it, then calls the provider with no transaction open. **Never hold a database transaction across a network call to someone else's system;** one slow provider would pin rows and connections for everyone.

![The API commits notification and deliveries together and replies; workers claim due rows under a lease, send, and record the outcome.](../../../generated/diagrams/sd-notification-system/dd1-dispatcher.svg)

Is Postgres enough at storm peak? We write about 2,000 delivery rows per second and update each once or twice. That is well within what a single Postgres primary on ordinary server hardware typically sustains. Measure it, but nothing here suggests a problem.

**Also good: a dedicated queue.** Kafka or SQS between the API and the workers gives dispatch its own capacity, and Kafka can rewind to replay a morning's sends.

The catch is that writing the row and publishing the message are now two writes. A crash between them leaves a row with no message, or a message with no row. The standard fix is a transactional outbox: write the row and an outbox entry in one transaction, and let a relay publish the outbox.

| | Database as queue | Broker + outbox |
|---|---|---|
| Atomic acceptance | One transaction | Needs the outbox relay |
| Moving parts | API, Postgres, workers | Adds a broker and a relay |
| Throughput ceiling | Database write capacity | Broker partitions |
| Replaying old sends | Re-mark rows as pending | Rewind consumer offsets |
| Right when | Thousands per second, one firm | Many consumers, much higher rates |

**At this scale the database is the right queue. Say so out loud, and name the number that would make you switch.**

> **Design move — Accept durably, work asynchronously.** Commit the request, reply, and do slow external work in the background. *Cost:* the caller learns "accepted", not "done", so you need status tracking.

Now retries. A failed delivery is not retried immediately. The worker sets `next_attempt_at` using exponential backoff with random jitter — roughly 1 s, 2 s, 4 s, each ±50%. Jitter stops every worker from hitting a recovering provider at the same instant.

After a budget of, say, six attempts, the delivery becomes `FAILED`, and the platform raises an operational alert through a *different* provider. Retrying forever hides the failure. Giving up silently loses the alert. Neither is acceptable for a page about a loss limit.

> **Design move — Bounded retry with backoff.** Retry with exponential backoff and jitter, then park the work where a human can see it. *Cost:* some deliveries arrive late, and a few not at all — visibly.

The same dispatcher also solves the quiet-hours problem from the high-level design. A held delivery is just a row whose `next_attempt_at` is 07:00.

### 2) How do we retry without paging the trader twice?

At-least-once means duplicates are possible; our job is to make them rare. They come from two places.

**Duplicate requests.** The risk service sends a page. Our `202` is lost on the network. The service retries, and without protection we create a second notification.

The fix is the `idempotencyKey`. The sender chooses it once — for example `risk:desk7:loss-limit:2026-10-05` — and reuses it on every retry. A unique index on `(sender, idempotency_key)` makes the database the referee:

1. The first request inserts the notification.
2. A retry hits the unique constraint.
3. The API returns the original `notificationId` and creates nothing.

A check-then-insert in application code is not enough. Two concurrent retries can both check, both find nothing, and both insert. Only the constraint decides atomically — the "check, then act" trap from [Handbook Ch 29 — *Sending It Twice*](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md).

> **Design move — Idempotency key.** Let the caller name the operation once; a unique constraint turns retries into no-ops. *Cost:* you must keep keys for the whole retry window — 24 hours is plenty here.

**Duplicate sends.** The harder case happens inside our own worker. Trace it:

| Time | Worker A | Provider | Database |
|---|---|---|---|
| t0 | claims delivery 81, lease to t0+30 s | | `PENDING`, claimed |
| t1 | sends page | accepts, pages the trader | |
| t2 | crashes before writing `SENT` | | still `PENDING` |
| t0+30 s | | | lease expires |
| t0+31 s | *Worker B* claims 81, sends again | pages the trader **again** | |

No local transaction can fix this. The page happened in a system we do not control, and our database never heard about it.

Two mitigations, in order of preference:

- **Provider-side idempotency.** Some providers accept a client-supplied key and collapse repeats — PagerDuty's Events API, for example, groups events that share a `dedup_key`. Where one exists, send the delivery ID as that key on every attempt.
- **Accept the rare duplicate.** If the provider offers no such key, a second page after a crash is the price of at-least-once. Keep it rare with short leases and stable workers.

**Exactly-once delivery across a system you do not own does not exist. Exactly-once *effect* needs the other side's cooperation.** Interviewers listen for that distinction; Handbook Ch 29 calls it the difference between delivery and effect.

### 3) How does a critical page arrive within 5 seconds during a storm?

This is where the interview is won. Replay the storm.

At 09:30:02 a venue's feed drops. Within a minute, 300 strategy processes and a dozen services each send "feed stale" alerts: **100,000 deliveries**. At 09:30:20 the risk service pages the head of desk 7: the desk just breached its loss limit.

Assume our providers together accept about 500 sends per second; contracts and rate limits set that ceiling. Now do the arithmetic for one first-in, first-out queue:

| Quantity | Value |
|---|---|
| Arrival rate during the storm | 100,000 ÷ 60 s ≈ 1,700/s |
| Arrived by 09:30:20 | ≈ 33,000 |
| Sent by 09:30:20 | 20 s × 500/s = 10,000 |
| Queued ahead of the page | ≈ 23,000 |
| Page waits | 23,000 ÷ 500/s ≈ **46 s** |

The page misses its 5-second target by an order of magnitude. Adding a bigger queue changes nothing: the backlog is a capacity problem, and a buffer only decides who waits.

> **Design move — A queue buys time, not capacity.** Size buffers with burst arithmetic: drain time = backlog ÷ spare capacity. *Cost:* a sustained deficit still grows without bound; only more capacity or less admitted work fixes it ([Handbook Ch 24 — *When the Market Outruns You*](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md), Part 3).

Two changes fix the page, and they work best together.

**Fix 1: priority lanes.** Give critical and normal traffic separate queues, separate worker pools, and separate provider budgets.

| Lane | Traffic | Workers | Provider budget | Target |
|---|---|---|---|---|
| Critical | pages, limit breaches | dedicated pool | 100/s reserved | under 5 s |
| Normal | info alerts, reports | shared pool | the rest, plus unused critical budget | minutes |

In the database-as-queue design, a lane is just a `lane` column, a partial index per lane, and worker pools that poll only their lane. The page now waits behind other critical alerts, which during this storm means behind nothing.

Reserved capacity sits idle on quiet days. That is the cost, and it is worth paying.

Protect the critical lane from its own senders. Each service gets a quota of critical notifications per minute. A runaway service that marks everything critical is downgraded to the normal lane; it cannot starve the risk desk.

> **Design move — Priority lanes.** Give each traffic class its own queue and workers, so bulk work never sits in front of urgent work. *Cost:* reserved capacity is idle when its class is quiet.

**Fix 2: collapse the storm.** Three hundred messages saying "feed stale: XNAS" help nobody. The on-call engineer needs one: "312 sources report XNAS feed stale since 09:30:02."

This is what `dedupKey` is for. In the accept transaction, the API groups deliveries by `(recipient, dedupKey)` in a short window:

1. The first delivery for a new key goes out immediately.
2. Repeats inside the window increment a counter instead of creating deliveries.
3. When the window closes, one summary goes out if anything was folded in.

Sending the first one immediately keeps latency for the alert that matters. Suppose 200 engineers subscribe to 5 storm keys. The 100,000 deliveries become about 1,000 first alerts and 1,000 summaries, which drain in about 4 seconds at 500 per second.

**Lanes protect urgent work from bulk work; collapsing shrinks the bulk.** You want both.

![The final design: critical and normal lanes with separate workers and provider budgets, plus storm windows that fold repeats into one summary.](../../../generated/diagrams/sd-notification-system/dd3-priority-lanes.svg)

## Interview calibration

**A passing answer**

- Moves delivery off the request path with a durable record and background workers.
- Retries failed deliveries with backoff and gives up visibly.
- Handles groups and preferences.

**A strong answer also**

- Says "at-least-once" out loud, adds an idempotency key, and explains why provider-side duplicates cannot be fully prevented.
- Separates traffic classes and *does the burst arithmetic* to show why a queue alone fails.
- Collapses storms, and notes that a notification informs; the risk control lives elsewhere.
- Picks the database as the queue at this scale, and names the number that would change that.

## Follow-ups

**How would you add escalation — page the next person if nobody acknowledges within 5 minutes?**

> Write an escalation row with `due_at = sent_at + 5 min` in the same transaction as the page. The dispatcher already polls by due time, so an escalation is just another due item. `POST /notifications/{id}/ack` marks the row done. The timer survives restarts because it is a row, not a sleep in memory — the accept-durably move again.

**A trader turns off SMS while fifty SMS deliveries to them are queued. Do those still go out?**

> Check preferences at send time, not at acceptance, and the opt-out applies to everything not yet sent. The cost is one more read per delivery. Anything already handed to a provider cannot be recalled.

**Why not use Kafka from day one?**

> Nothing in the requirements needs it. At about 2,000 per second, Postgres gives atomic acceptance in one transaction. Kafka adds a broker, an outbox relay, and partition planning. Switch when dispatch load competes with status queries, or when several independent consumers need the same stream — an audit store and an analytics pipeline, for example.
