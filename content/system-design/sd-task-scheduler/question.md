# Design a Distributed Task Scheduler

> **Level:** Intermediate · 45 minutes
>
> **You will learn:** separating *when* from *who* · leases and fencing tokens · priority without starvation · sizing shares from deadlines
>
> **Related questions:** [Design a Notification System](../sd-notification-system/question.md) · [Design a Risk-Limit Update Fan-Out Service](../sd-risk-limit-fanout/question.md)
>
> **Handbook:** [Ch 29 — *Sending It Twice*](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md) · [Ch 25 — *Whose Clock Was That?*](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md) · [Ch 11 — *When One Thread Stops, What Happens to the Rest*](../../../release1/handbook-markdown/chapters/b3-progress-guarantees/chapter.md)

## The question

> Design a distributed task scheduler: it should be able to schedule tasks asynchronously. Support priority based scheduling. Clients can query the status of scheduled tasks.

A trading firm runs a lot of work off the trading path that the trading day still depends on: the overnight risk and P&L runs, reference-data loads before the open, end-of-day reconciliation, and research backtests split into thousands of chunks. A task scheduler accepts that work from services and researchers and runs it on a shared fleet of workers.

Workers die mid-task. Deadlines cluster at the end of the day, exactly when the fleet is already full.

**The crux: decide when each task runs and who runs it, so urgent work goes first, nothing waits forever, and no task ever has two live owners.**

> **Finance lens.** In consumer tech this question is usually about scale: millions of jobs a second, or cron for a web fleet. A trading firm's volume is modest, but the market sets its deadlines. The overnight risk run must finish before the pre-open checks, and start-of-day positions must load before 09:30. Running one task twice can also corrupt the books: two copies of an end-of-day booking job post the same P&L twice. The second deep dive exists because of that.

## Requirements

### Functional requirements

1. Clients submit a task — to run now, at a given time, or on a recurring schedule — with a priority, and get an ID back immediately.
2. Workers run tasks, highest priority first, and failed tasks are retried.
3. Clients query a task's status and history: queued, running, succeeded or failed, how many attempts, and on which workers.

Out of scope: dependencies between tasks (a follow-up), the code inside a task, and packing tasks onto machines by CPU and memory — that is a cluster manager's job.

### Non-functional requirements

Assume about 2 million task runs a day. Most are research chunks; the spike is the end-of-day burst, when risk, P&L, and reconciliation tasks arrive together.

| Quantity | Value |
|---|---|
| Daily submissions | ~2 million (≈ 23/s on average) |
| End-of-day burst | 200,000 tasks between 18:00 and 18:05 (≈ 670/s) |
| Worker fleet | 2,000 slots; a typical task runs about a minute |
| Fleet throughput | 2,000 ÷ 60 s ≈ 33 tasks/s |
| Time to drain the burst | 200,000 ÷ 33/s ≈ 100 minutes |

Accepting 670 submissions a second is easy for one database. Running them is not. **The scheduler is never the bottleneck; the fleet is. For 100 minutes after 18:00, every scheduling decision is a decision about who waits.**

1. **Durable.** An accepted task is never lost; it runs at least once.
2. **On time.** A task becomes runnable within 1 second of its due time, and starts within another second if a slot is free.
3. **Priority without starvation.** Higher priority starts first, but every class of work keeps making progress.
4. **One owner at a time.** A dead worker's task restarts within a minute, and the dead worker can never commit results after that.
5. **Status.** Queries reflect the current state within a second; history is kept for 30 days.

Out of scope: exactly-once execution of arbitrary code — the second deep dive shows what we can promise instead — and multi-region failover.

## Core entities

- **Job** — a recurring definition: "run the London risk report at 06:00 every business day."
- **Task** — one unit of work to run once, with a priority, a due time, and a state. A client creates one directly, or a job creates one each time it fires.
- **Attempt** — one try of a task on one worker, with a lease and a fencing token.
- **Worker** — a process with a few slots that pulls tasks and runs them.

The relationship that matters is **one task, many attempts, at most one of them live**. The overnight VaR job fires at 02:00 and creates task 4410. Its first attempt dies with its host at 02:40; the second, on another worker, finishes at 03:25. The client sees one task, succeeded, with two attempts.

## API

Clients submit and query:

```text
POST /tasks  ->  202 Accepted { taskId }
{
  idempotencyKey,          // chosen by the client, reused on every retry
  type, payload,           // what to run
  priority,                // 0 (critical) ... 3 (research)
  runAt,                   // optional; default now
  timeoutSeconds, maxAttempts
}

POST /jobs   { schedule: "0 6 * * MON-FRI", timezone: "Europe/London", calendar, taskTemplate }
GET  /tasks/{id}  ->  { state, priority, attempts: [{ worker, startedAt, endedAt, outcome }] }
```

Workers pull and report:

```text
POST /claim                { workerId, freeSlots }  ->  [{ taskId, attempt, leaseUntil, payload }]
POST /tasks/{id}/heartbeat { attempt }              ->  { leaseUntil }     // 409 if superseded
POST /tasks/{id}/complete  { attempt, outcome }
```

Two fields earn their place later: `runAt` in the first deep dive and `attempt` — which becomes the fencing token — in the second.

## High-level design

We will meet one functional requirement at a time with the simplest design that works, then see where it breaks.

### 1) Submit a task and get an ID

1. A client calls `POST /tasks`.
2. The scheduler API inserts a task row: state `QUEUED`, `due_at = runAt`, and the priority.
3. A unique index on `(client, idempotency_key)` turns a retried submit into a lookup of the existing task.
4. The API commits and replies `202` with the `taskId`.

![A client submits a task; the scheduler API writes it to Postgres under a unique idempotency key and replies 202 with the task ID. A job firer inserts tasks for recurring jobs the same way.](../../../generated/diagrams/sd-task-scheduler/step1-submit.svg)

This is accept-then-work: commit the request, reply, and do the slow part later, so a crash after the reply cannot lose the task. The idempotency key lets a client that timed out retry safely, because the database's unique constraint — not application code — decides whether the task already exists. [Design a Notification System](../sd-notification-system/question.md) develops both moves in full.

Postgres is enough here. 670 inserts a second at the burst is modest, and we want transactions shortly.

Recurring jobs need no new machinery. A small **job firer** wakes every minute and inserts the tasks due in the next hour, with `(job_id, fire_time)` as the idempotency key. If two firers run by mistake, the second insert finds the first and creates nothing.

### 2) Run tasks on workers

1. A worker with free slots calls `POST /claim`.
2. The API picks due `QUEUED` tasks, highest priority first, marks them `RUNNING` with a 30-second lease, and records an attempt.
3. The worker runs the task and renews the lease every 10 seconds.
4. It reports the outcome. A failure goes back to `QUEUED` with a later `due_at`, until `maxAttempts` is reached.
5. A reaper, every few seconds, returns `RUNNING` tasks whose lease has expired to `QUEUED`.

The claim is one statement — the same database-as-queue claim the notification system uses:

```sql
-- claim up to 4 due tasks, best priority first, skipping rows other workers hold
UPDATE tasks SET state = 'RUNNING', attempt = attempt + 1, lease_until = now() + interval '30 seconds'
WHERE id IN (SELECT id FROM tasks WHERE state = 'QUEUED' AND due_at <= now()
             ORDER BY priority, due_at LIMIT 4 FOR UPDATE SKIP LOCKED)
```

![Workers claim due tasks by priority under a 30-second lease, renew it while running, and report the outcome; failures return to the queue with a backoff delay.](../../../generated/diagrams/sd-task-scheduler/step2-run.svg)

Workers **pull** rather than being pushed work. Only a worker knows when it has a free slot, and a pushed task can land on a worker that died a second ago. The cost of pulling is empty polls when there is nothing to do; long-polling, where a claim waits up to 20 seconds for work, removes most of them.

Failed tasks are retried with exponential backoff and jitter — about 1 minute, 2, 4, each randomised — so a broken dependency is not hammered by every retry at once. After the last attempt the task is `FAILED` and its owner is alerted. The backoff is just a later `due_at`.

### 3) Query status

The task and attempt rows are the record. `GET /tasks/{id}` reads them, and an index on `(client, created_at)` serves "what did I submit today?". After 30 days, finished tasks move to archive storage. Clients that would rather not poll can register a callback, which the scheduler fires when a task finishes.

### What is still broken

The design works on a quiet afternoon. Run the end-of-day burst through it:

1. **One query answers two questions.** "Is it due?" and "who goes next?" share one table and one `ORDER BY`, so the only policy it can express is priority, then age.
2. **A paused worker can wake up and commit.** After its lease expires and another worker takes over, the first can still write its results. One task, two owners.
3. **Strict priority starves.** For about two hours after 18:00, research never runs, and anyone who labels their work critical jumps the queue.

## Deep dives

### 1) How do we find what is due without wading through what is not?

At 17:59 the tasks table holds about a million `QUEUED` rows. 600,000 are research chunks, due now, at priority 3. The other 400,000 are due later: retries backing off, tonight's batch runs, and tomorrow's 06:00 pre-open loads. At 18:00 the burst begins, and 2,000 workers poll once a second.

**Option A: keep one table and tune it.** With four priority levels, a partial index on `(priority, due_at)` over `QUEUED` rows, probed once per priority with `priority = p AND due_at <= now()`, finds due work without touching a single future row. Add long-polling and batched claims, and this handles a few million tasks a day. It is a good answer, and you should say so.

It has one real limit: **the policy is whatever an index can sort** — priority, then age. The third deep dive needs shares per class and quotas per team, and no `ORDER BY` expresses those.

**Option B: move dispatch to a message broker.** RabbitMQ supports priority queues, and a broker hands out messages far faster than a polled table. The trouble is everything else:

- SQS caps a message's delay at 15 minutes, and Kafka has neither delay nor priority.
- None of the three lets you reprioritise or cancel a message already queued.
- Status still needs a database, so every state change becomes a write to two systems.

A strong candidate notices that the two questions have different shapes. "Is it due?" concerns a large set, mostly in the future, ordered by time. "Who goes next?" concerns only work that is already due, and its answer is a policy, not a sort order. Each deserves its own owner.

**Option C: a timer for *when*, a dispatcher for *who*.**

1. A task with a future due time is written as `SCHEDULED`, under an index on `due_at` that covers only `SCHEDULED` rows. A task due now is written as `READY` directly.
2. A promoter — one leader with a standby — queries that index every 100 ms and flips everything due to `READY`, in batches.
3. A dispatcher, also a leader with a standby, keeps the `READY` set in memory, one queue per class and team.
4. Workers long-poll the dispatcher. It chooses tasks by policy, commits them `RUNNING` with new attempt numbers in one batched transaction, then hands them out.

![The timer side holds future tasks indexed by due time; a promoter moves due tasks to READY every 100 ms; a dispatcher holds READY work in memory by class and team and hands it to long-polling workers, committing claims in batches.](../../../generated/diagrams/sd-task-scheduler/dd1-when-who.svg)

The database stays the record. The dispatcher learns of new `READY` rows — promoted, submitted, or returned by the reaper — from a notification sent after each commit (Postgres `LISTEN/NOTIFY`, say), with a one-second re-scan as a safety net. Its batched claim is conditional, `... WHERE id IN (...) AND state = 'READY'`, so a dispatcher that has lost leadership to its standby claims nothing.

If the dispatcher dies, its standby rebuilds the queues from the `READY` rows; if the promoter dies, its standby promotes anything overdue at once. Compare due times against one clock — the database's — not each machine's own ([Handbook Ch 25 — *Whose Clock Was That?*](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md)).

| | A: one tuned table | B: broker queues | C: timer + dispatcher |
|---|---|---|---|
| Future-dated tasks | rows with a due time | limited or none | timer index |
| Dispatch policy | what an index can sort: priority, then age | per-queue priority | any: shares, quotas, aging |
| Cancel or reprioritise a waiting task | update the row | not in SQS, Kafka, or RabbitMQ | update the row and the queue |
| Status queries | same table | a second store | same table |
| Moving parts | fewest | broker + database | promoter, dispatcher, database |
| Right when | strict priority, a few million tasks a day | due-now, fire-and-forget work | richer policies or larger fleets |

There is no universal winner. If every task were due at once and nobody queried status, a broker would be simplest. If strict priority were enough, Option A would be. Option C earns its two extra processes only because the policy this firm needs is richer than a sort order.

**"Is it due?" and "who goes next?" are different questions. Keep a time index for the first, and let a dispatcher answer the second over due work only.**

> **Design move — Separate when from who.** Keep a durable index of work by due time, and move work into ready queues only when it is due; workers pull only from ready queues. *Cost:* two structures to keep consistent, and a promoter process to run.

Job systems such as Sidekiq use the same split: a time-sorted set of scheduled jobs, and plain queues of jobs ready to run.

### 2) A worker stalls for 40 seconds. Who owns the task now?

Task 9137 posts desk 7's end-of-day P&L adjustments to the ledger. Trace what happens when its worker stalls for 40 seconds — a stop-the-world garbage collection in the task's runtime, or a host swapping under memory pressure:

| Time | Worker W17 | Scheduler | Worker W22 |
|---|---|---|---|
| 18:04:10 | claims 9137 (attempt 1), lease to 18:04:40 | | |
| 18:04:20 | renews to 18:04:50, then stalls | | |
| 18:04:50 | stalled | lease expires; 9137 is `READY` | |
| 18:04:51 | | | claims 9137 (attempt 2), starts |
| 18:05:00 | resumes, posts its adjustments | | |
| 18:05:20 | | | posts its adjustments |

The ledger now holds desk 7's adjustments twice. W17 did nothing wrong by its own reckoning: it was paused, not dead, and it finished the work it was given.

Candidates usually reach for one of these first:

- **A longer lease.** Five minutes instead of thirty seconds means fewer false expiries. But a crashed worker's task now waits five minutes to restart, and a six-minute pause breaks it anyway. It moves the threshold without closing the hole.
- **Check the lease before writing.** W17 can check, see a valid lease, and stall again between the check and the write. This is the "check, then act" trap from [Handbook Ch 29 — *Sending It Twice*](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md).
- **Stop the old worker.** Some clusters power off a node before reassigning its work. That is reliable, but slow, heavy, and needs control over the hardware.

You cannot stop a paused process from waking up. What you can control is whether anything it writes counts.

**Step 1: a fencing token.** Every claim increments the task's `attempt`; that number is the token. The worker sends it with every heartbeat and completion, and the scheduler checks it on every state change:

```sql
UPDATE tasks SET state = 'SUCCEEDED'
WHERE id = 9137 AND attempt = 1;     -- 0 rows: attempt 2 owns it now
```

W17's report changes nothing, and it learns it has been superseded.

**Step 2: the ledger.** Here is the subtle part. A ledger that rejects tokens lower than the highest it has seen would *accept* W17's write at 18:05:00, because attempt 2 has not written anything yet. **A fencing token stops an old writer that arrives after a newer one, not one that arrives first.**

Keying the effect by task helps: treat "the adjustments for task 9137" as one unit that a higher token replaces, and W22's write at 18:05:20 replaces W17's. But for twenty seconds the risk run could read W17's adjustments. And if attempt 2 fails and never writes, they stay for good, under a task marked `FAILED`.

**Step 3: one commit point.** Workers never write to the ledger directly. Each attempt stages its adjustments under `(task, attempt)`, where no reader looks. The scheduler's fenced update that marks the task `SUCCEEDED` is the only commit, and only the winning attempt's staged adjustments are posted — in the same transaction if the ledger shares the database, otherwise by a publisher that posts exactly the committed attempt.

An external ledger dedupes posts by task ID, so a publisher that crashes after posting and retries cannot post twice.

![W17's completion is rejected by the scheduler and its staged adjustments are never posted; W22's completion commits, and only attempt 2's staged adjustments reach the ledger.](../../../generated/diagrams/sd-task-scheduler/dd2-fencing.svg)

| Mechanism | What the ledger must do | What still gets through |
|---|---|---|
| Longer lease | nothing | any longer pause; recovery is slower |
| Check the lease, then write | nothing | a stall between check and write |
| Fencing token at the ledger | compare tokens | a stale write that lands first |
| Token plus effect keyed by task | replace a unit by task | a stale write, visible until replaced — forever if attempt 2 never writes |
| Stage per attempt, commit through the scheduler | accept posts only from the commit, deduped by task ID | nothing |

This extends the receiver-side defence from Handbook Ch 29 — apply each operation once, keyed by an identity it carries — so that only one identity is ever applied. Some targets cannot stage anything: an email, or a third-party API with no idempotency key. For those, the commit writes an outbox row and a sender delivers it, accepting a rare duplicate if the sender crashes mid-send — the compromise a notification system makes with pagers.

Leases also need the right clock. The scheduler measures leases with its own clock; a worker times its renewals with its monotonic clock, which never steps, and stops starting new side effects a few seconds before its lease ends. That narrows the window. Only the fenced commit closes it.

**You cannot stop a paused worker from waking up. You can make sure nothing it writes counts.**

> **Design move — Lease the work, fence the stale owner.** Claim work with a time-bounded lease that carries a fencing token; an expired lease lets others reclaim the work, and the token stops the old owner from committing. *Cost:* work can run twice after an expiry, so its effects must be idempotent or fenced.

### 3) The end-of-day burst fills the fleet. When does research run?

From 18:00, the burst's 200,000 priority-1 tasks keep all 2,000 slots busy for about 100 minutes. Behind them wait:

- **Priority 2:** data-quality checks, about 600 slot-hours of work, that must finish by 19:30, when the overnight risk run starts and reads their output.
- **Priority 3:** 600,000 research chunks for a model the team needs by 08:00.

At 18:30, a team submits 30,000 tasks marked priority 0, because to them it is urgent.

**Option A: strict priority.** Always run the highest priority waiting. It is simple, and priority 0 is never delayed. But the 18:30 team jumps ahead of the firm's risk runs simply by choosing a label, priority 1 finishes around 19:55, and priority 2 cannot start until then — it misses 19:30 before it begins.

**Option B: round-robin across classes.** Every class gets an equal turn. Nothing starves, but tomorrow's pre-open load now waits behind research.

The strong move is to notice that "priority" mixes two questions. One is *order*: who goes first right now. The other is *entitlement*: how much of the fleet each class gets over an evening. Strict priority answers the first and ignores the second.

[Handbook Ch 11 — *When One Thread Stops, What Happens to the Rest*](../../../release1/handbook-markdown/chapters/b3-progress-guarantees/chapter.md) draws the same line for threads. A lock-free structure guarantees that *some* thread progresses; only a wait-free one bounds *every* thread's wait. Strict priority is the scheduler's lock-free: the fleet is always busy, but one task can wait forever.

Two refinements give every task a bound:

- **Aging.** A task's effective priority improves as it waits — say one class per 30 minutes — so work that has waited long enough overtakes newer urgent work. It bounds starvation for old work, but it cannot help work that arrived *with* the burst: the priority-2 checks and the priority-1 burst age together, so priority 1 stays ahead.
- **Weighted shares.** Priority 0 stays strict, within a per-team quota of, say, 100 slots. Below it, classes share the fleet by weight: 60% priority 1, 25% priority 2, 15% priority 3. When a slot frees, it goes to the class furthest below its share, then to the team furthest below its share within that class, then to that team's oldest task. A class with no waiting work lends its share to the others.

Preemption is rarely needed for priority 0. With 2,000 one-minute tasks, a slot frees every 30 milliseconds on average. Preemption matters only when tasks run for hours.

Shares are not free, and the cost is easy to compute. With 60% of the fleet, priority 1 gets 1,200 slots, about 20 tasks a second, and the burst can take up to 2.8 hours to drain instead of 100 minutes. **Shares slow the top class by exactly the capacity they hand to the others.**

| Policy | Pre-open priority 0 | Research during the burst | Work mislabelled as critical | What it costs |
|---|---|---|---|---|
| Strict priority | first | starves for about two hours | jumps the queue | priority 2 misses its deadline |
| Round-robin | waits its turn | runs | does not matter | urgent work is slow |
| Strict + aging | first | only work older than the burst moves up | jumps until quotas exist | priority 2 still misses: it ages with the burst |
| Priority 0 strict + weighted shares + team quotas | first, within quota | 15% of the fleet | capped by quota | priority 1 drains in 2.8 h, not 100 min |
| Reserved pools per class | first | its own pool | capped | idle slots when a class is quiet |

The right policy depends on deadlines, and the arithmetic decides it. If only priority 1 had a deadline and research had until morning, strict priority plus aging would be enough: the fleet clears everything by about 01:15.

Here, priority 2 has its own deadline, and its volume sets its share. 600 slot-hours in the 90 minutes to 19:30 needs 600 ÷ 1.5 = 400 slots, a fifth of the fleet. The 25% weight covers that with a margin; anything below 20% misses.

Priority lanes — a separate queue and workers per class — protect urgent work by reserving capacity, the move [Design a Notification System](../sd-notification-system/question.md) uses for pages. With four classes and dozens of teams, reserved pools would leave much of the fleet idle; weighted shares are the version that lends unused capacity.

**Priority decides who goes first; shares decide that everyone goes eventually. Size the shares from deadlines, not from who shouts loudest.**

> **Design move — Priority without starvation.** Serve higher priority first, but guarantee lower priorities a share of capacity or raise their effective priority as they wait. *Cost:* urgent work occasionally waits behind old low-priority work.

## Interview calibration

**A passing answer**

- Accepts tasks durably, returns an ID, and lets workers pull due tasks in priority order.
- Retries with backoff and reports status from the same records.
- Recovers a dead worker's task with a lease or timeout.

**A strong answer also**

- Does the fleet arithmetic and says the hard part is ordering a backlog, not scheduling throughput.
- Separates the timer from dispatch, says when one tuned table is enough, and explains what the split buys.
- Shows why a lease alone allows two owners, adds a fencing token, and makes the scheduler's fenced update the single commit point for the task's effects.
- Explains starvation under strict priority, and sizes shares or aging from actual deadlines.
- Says when a broker would be the better tool.

## Follow-ups

**How would you add dependencies — reconciliation runs only after every P&L task succeeds?**

> Keep a count of unfinished parents on each task. A task becomes `READY` only when it is due *and* that count is zero; a parent's success decrements its children's counts in the same transaction that marks it done. "Ready" now means due and unblocked — the same separation of when from who, with one more condition. A failed parent leaves its children visibly `BLOCKED` instead of running them on partial data.

**"Every business day at 06:00 London time." What goes wrong?**

> Daylight saving: 06:00 in London is 05:00 UTC in summer and 06:00 UTC in winter, so store the rule with its time zone and compute each firing, never a fixed UTC time. Holidays: use the exchange calendar, not the day of the week. Missed firings while the scheduler was down: decide per job whether to catch up (a report) or skip (a pre-open load that is now pointless). The `(job_id, fire_time)` idempotency key makes a catch-up safe to run twice.

**The scheduler's database fails over. What happens to running tasks?**

> Workers keep running, but cannot renew leases or report until the new primary is up. If the failover takes longer than a lease, every running task would look abandoned and restart at once. So the new primary extends every live lease by the outage length before expiring anything. Synchronous replication keeps every accepted task; the cost is a little latency on each submit, which 670 a second can easily afford.
