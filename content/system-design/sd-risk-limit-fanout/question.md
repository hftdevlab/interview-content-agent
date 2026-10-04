# Design a Risk-Limit Update Fan-Out Service

> **Level:** Advanced · 45 minutes
>
> **You will learn:** versioning authoritative state · acknowledging where it is enforced · freshness leases · failing safe · building aside and swapping atomically
>
> **Related questions:** [Design a Low-Latency Market Data Feed and Normalization System](../sd-market-data-feed/question.md) · [Design a Notification System](../sd-notification-system/question.md)
>
> **Handbook:** [Ch 30 — *The Check You Cannot Skip*](../../../release1/handbook-markdown/chapters/e3-pretrade-risk-engine/chapter.md) · [Ch 9 — *What the Other Thread Can See*](../../../release1/handbook-markdown/chapters/b1-cpp-memory-model/chapter.md) · [Ch 25 — *Whose Clock Was That?*](../../../release1/handbook-markdown/chapters/d5-clocks-and-timestamps/chapter.md)

## The question

> Design a service that distributes real-time risk-limit updates to multiple trading strategy processes. Consumers can disconnect or become slow, but a strategy must not silently continue forever with stale limits.

### Domain primer

A **risk limit** is a number a strategy must not exceed. A few typical ones, for a strategy we will call S7:

| Limit | S7's value | Checked |
|---|---|---|
| Maximum position in AAPL | 10,000 shares | before every order |
| Maximum size of one order | 500 shares | before every order |
| Maximum notional per order | $250,000 | before every order |
| Daily loss limit | $2 million | continuously |

Risk managers set limits, and automated controls tighten them when markets turn volatile or losses mount. The **pre-trade risk check** enforces them: a function on the order path, inside or beside each strategy process, that every order must pass before it reaches the exchange gateway. Handbook Ch 30 explains why that check must be synchronous and bounded.

So this service has one job: get the right numbers to every enforcement point, and prove they are still the right numbers.

Here is the scenario we will follow. **At 10:31:04, risk manager Maya cuts S7's AAPL position limit from 10,000 to 5,000 shares and its maximum order size from 500 to 100, as one change.** S7 holds 4,900 shares and is sending 400-share buy orders. If S7 keeps checking against the old limits for even a second, its next order takes it to 5,300 shares — past the limit Maya just set.

**The crux: a limit only protects you where it is enforced. The system must prove each strategy is using the current limits, and make a strategy stop adding risk the moment it cannot prove that.**

> **Finance lens.** In consumer tech this is configuration distribution or feature flags, often built on watches in ZooKeeper, etcd, or Consul. Eventual consistency is fine there: a stale flag shows an old button for a few seconds. A stale limit is unbounded financial risk. Staleness must be *bounded and detected*, and the safe failure is to stop adding risk, not to carry on. And because limits can go hours without changing, "no news" can never be taken to mean "still fresh".

## Requirements

### Functional requirements

1. Risk managers and automated controls change limits for a scope — a strategy, an account, or a symbol. Each change is validated, versioned, and recorded with who made it and why.
2. Every affected strategy applies the change, and the author sees, per strategy, the version actually in force.
3. A strategy that loses contact or falls behind detects it and stops opening new risk within a bounded time.
4. A starting strategy has its complete current limits before its first order.

Out of scope: computing positions and P&L (inputs to the check), approval workflows for limit changes, and the check itself.

### Non-functional requirements

Assume 1,000 strategy processes on 100 hosts, about 10 KB of limits per strategy, and changes that are rare — tens a day — except during volatility, when automated controls can push up to 50 updates per second per strategy.

At the worst case that is 1,000 × 50/s × 200 bytes ≈ **10 MB/s. This system is not bandwidth-bound. Every hard part is correctness and tail behaviour.** Saying so early stops the interview drifting into throughput.

1. **Propagation.** Healthy strategies apply a change within 100 ms (p99). The author sees confirmations within a second.
2. **Bounded staleness.** A strategy that cannot prove its limits are current blocks new risk within 2 seconds. The number is the risk owner's to choose; the mechanism is ours.
3. **Atomicity.** The check sees a complete version — never Maya's new position limit next to the old order size.
4. **Durability and audit.** An accepted change is never lost. Every change and every application is recorded.
5. **Isolation.** One slow strategy never delays another.
6. **Hot-path cost.** Reading limits inside the check costs nanoseconds: no locks, no system calls.

## Core entities

- **Limit set** — the complete limits for one scope at one version.
- **Change** — an operation ID, author, reason, new values, and the version it produces.
- **Version** — a counter per scope, incremented by every committed change.
- **Consumer** — one running strategy process: the scopes it uses, the version it has applied, and when its proof of freshness expires.
- **Freshness proof** — a message from the authority saying "the current version of S7's limits is 42", sent in answer to a specific request from this consumer.

The relationship to watch is between two versions: **the authority's current version and each consumer's applied version.** The gap between them is exactly what this design must keep small, visible, and bounded in time.

## API

For risk managers:

```text
PUT /scopes/{scope}/limits
{ operationId, expectedVersion: 41, values: { ... }, reason }   ->  200 { version: 42 }

GET /scopes/{scope}/status   ->  { current: 42, consumers: [ { id, applied: 42, proofAgeMs } ] }
```

Two fields protect the author. `operationId` is an idempotency key: the author's tool picks it once, and a unique constraint makes a retry after a timeout a no-op instead of a second change ([Design a Notification System](../sd-notification-system/question.md) builds this move in full). `expectedVersion` stops two people from silently overwriting each other: if someone else committed version 42 first, Maya gets `409 Conflict` and re-reads before trying again.

Between the service and strategy hosts, a binary protocol over one TCP session per host:

```text
-> Hello    { consumer_ids[], scopes[], applied_versions[] }
<- Snapshot { scope, version, values }                  // complete set: on start or after a gap
<- Delta    { scope, version, base_version, values }    // base_version = version - 1
-> Applied  { consumer_id, scope, version }             // sent after the swap, not on receipt
-> Ping     { nonce }
<- Proof    { nonce, epoch, scope -> current version }   // created by the authority
```

## High-level design

### 1) Record a change durably

1. Maya's tool sends `PUT` with an operation ID and `expectedVersion: 41`.
2. The limit service validates the change — schema, sane bounds — and checks the expected version.
3. It assigns version 42 and commits the change to a replicated log, such as a Postgres primary with a synchronous replica or a Raft-based store.
4. Only after the commit does it reply `{ version: 42 }`.

![The limit service validates the change, checks the expected version, assigns version 42, commits it to a replicated log, and only then replies.](../../../generated/diagrams/sd-risk-limit-fanout/step1-record.svg)

**Acceptance means committed, not delivered.** Commit first, reply, then fan out in the background. It matters more here than anywhere: once Maya sees version 42, it must survive any crash.

One process — the current leader — assigns versions for a scope, so versions never collide and never go backwards. An exchange feed works the same way: the venue is the single writer of each channel's sequence numbers. Here, we are the venue.

> **Design move — Version authoritative state.** Give every change a monotonically increasing version per scope, so consumers can order updates and detect gaps. *Cost:* a single writer per scope, or a consensus step to assign versions.

### 2) Fan out to every strategy

The simplest design is a pub/sub topic that every strategy subscribes to. Our physical layout suggests a better shape: 1,000 strategies, but only 100 hosts.

1. Stateless distributors tail the committed log.
2. For each host that runs a strategy using the scope, a distributor puts `Delta(S7, v42, base v41)` on that host's bounded queue.
3. A risk agent on each host applies the delta to the strategy's limit table in shared memory.
4. The strategy's order thread reads its table from shared memory on every order.

![Distributors tail the log and send deltas through a bounded queue per host; each host's risk agent applies them to limit tables in shared memory that strategies read on every order.](../../../generated/diagrams/sd-risk-limit-fanout/step2-fanout.svg)

Machines that must react get changes pushed; people who only need status pull it — the split [Design a News Feed System](../sd-news-feed/question.md) draws between strategies and terminals. One connection per host instead of per strategy cuts connections tenfold and lets the agent serve every strategy on the host from one copy of the stream.

The distributors hold no truth; the log does. Any distributor can serve any host, and a crashed distributor costs a reconnect, not data.

Two mechanisms from market data drop straight in, both built in full in [Design a Low-Latency Market Data Feed and Normalization System](../sd-market-data-feed/question.md). The per-host queue is bounded, so one stalled agent is cut off and resyncs instead of slowing the distributor. And `base_version` is a sequence number: if an agent at version 40 receives a delta based on 41, it has a gap and asks for a snapshot.

### 3) Start up with a snapshot

1. A starting strategy's agent sends `Hello` with the versions it already has — none, on a cold start.
2. The distributor sends a `Snapshot` of the current limit set for each scope, then any later deltas.
3. The strategy may not send an order until every scope it uses has a snapshot applied and a fresh proof (the second deep dive explains proofs).

Cold start is snapshot recovery with an infinite gap, so one code path handles both.

### What is still broken: run Maya's change through it

At 10:31:04 Maya's change commits as version 42. The distributor sends the delta to host 1. The host agent receives it, the queue reports "delivered", and Maya's screen shows success. Now three things can go wrong:

1. **Half-applied.** The agent writes the new position limit, then is descheduled before writing the new order size. For a few milliseconds S7's check sees 5,000 shares with a 500-share order size — a combination Maya never approved.
2. **Delivered, not in force.** The agent's thread stalls after reading the delta and before touching the table. S7's next 400-share buy passes the old check, and S7 reaches 5,300 shares. Every dashboard says the change was delivered.
3. **Silence.** The distributor loses its connection to the limit service just before version 43 commits. It sends nothing to host 1, and nothing is exactly what host 1 expects on a quiet day. S7 trades on version 42 indefinitely.

Each failure is a missing proof. The check needs a complete version; "delivered" must mean "in force"; and silence must expire. Those are the deep dives.

## Deep dives

### 1) How does "applied" come to mean "in force at the check"?

**First, never edit the table the check is reading.** The agent builds the new version off to the side and publishes it in one step:

1. Copy version 41 into an inactive slot and apply *all* of the delta's fields there.
2. Validate the complete table.
3. Publish it with a single atomic store of the active-slot index.

```cpp
struct LimitTable { uint64_t version; Limits limits; };
LimitTable slots[2];                    // in shared memory, one pair per strategy
std::atomic<uint32_t> active;           // an index, not a pointer: valid across processes

// Host agent (writer)
uint32_t next = 1 - active.load(std::memory_order_relaxed);
slots[next] = slots[1 - next];          // start from the current version
apply(slots[next], delta);              // every field, off to the side
validate(slots[next]);
active.store(next, std::memory_order_release);   // one store publishes everything

// Order thread (reader), once per order
const LimitTable& t = slots[active.load(std::memory_order_acquire)];
check(order, t);                        // every field from the same version
```

The release store and the acquire load pair up: an order thread that sees the new index also sees every field written before it. That is the publish-data-then-flag pattern from [Handbook Ch 9 — *What the Other Thread Can See*](../../../release1/handbook-markdown/chapters/b1-cpp-memory-model/chapter.md). The check reads one complete version per order: 41 or 42, never a mixture.

The writer must not reuse the old slot while a check might still be reading it. A check takes nanoseconds and updates arrive at most every 20 ms, so in practice that window is tiny — but "in practice" is not a proof. Have the order thread publish the version it last read, and let the agent wait until it has moved on before overwriting that slot.

A sequence lock is a reasonable alternative for small tables: readers copy the table and retry if a writer was active. The companion fundamentals question on sequence locks works through that protocol.

> **Design move — Build aside, swap atomically.** Build the new version off to the side and publish it with one store, so readers see old or new, never a mix. *Cost:* two copies in memory, and a rule for when the old copy can be reused.

![The host agent builds v42 in the inactive slot, publishes it with one release store of the active index, and only then sends Applied; orders before the swap see v41, orders after see v42.](../../../generated/diagrams/sd-risk-limit-fanout/dd1-atomic-swap.svg)

**Second, acknowledge only after the swap.** The agent sends `Applied(S7, v42)` only once the new index is published. Now the three words a dashboard might use mean three different things:

| Status | Proves | Who can claim it |
|---|---|---|
| Sent | the distributor queued it | distributor |
| Received | the bytes reached the host | host agent, on receipt |
| **Applied** | the next order is checked against v42 | host agent, after the swap |

Maya's status view shows applied versions only: "S7: v42 at 10:31:04.031 · S9: v41 — 3 s behind". A strategy still on 41 is visible, and someone can act on it.

The same acknowledgements feed the audit trail. The limit service appends every `Applied` and every trust-state change to an audit log, off the order path. Together with the change log, that answers the question a regulator or an incident review will ask: "which limits was S7 checking at 10:31:05?"

It is capture at the boundary — record inputs where they enter, so any decision can be replayed — applied to control data. The audit store only records; it never authorizes an order.

> **Design move — Acknowledge where it is enforced.** Sent is not applied: confirm a change only when the enforcing component reports the version it is using. *Cost:* an extra feedback path from every consumer.

**Sent is not applied. Only the enforcement point can confirm a change.**

### 2) How does a strategy know its limits are still current?

The third failure is the subtle one. Limits can stay the same for hours, so a strategy cannot learn anything from the absence of updates. A silent link and a quiet day look identical.

**Freshness is not change frequency.** The strategy needs positive, recent proof that its version is still the current one — and it must stop adding risk when that proof runs out. That is a lease.

1. Every 250 ms, the host agent sends `Ping(nonce)`, with a new random nonce each time.
2. The distributor forwards it to the limit service, the authority.
3. The authority answers `Proof(nonce, epoch, S7: v42)`, and the distributor relays it.
4. If the nonce matches the agent's latest ping and v42 equals the version applied for S7, the agent sets `fresh_until = now + 1 s` in shared memory next to the limit table.
5. The order thread compares its own clock with `fresh_until` on every order.

![Pings travel from the host agent through the distributor to the authority; only the authority's proof for the latest nonce renews fresh_until, which the order thread checks on every order.](../../../generated/diagrams/sd-risk-limit-fanout/dd2-freshness.svg)

**Who is allowed to vouch?** Only the authority. If the distributor could answer pings itself, a distributor cut off from the limit service would keep telling hosts "you're current at 42" while version 43 sat unsent. Because the proof is created by the authority and carries the agent's latest nonce, the distributor can only relay it — it cannot invent one, and it cannot replay yesterday's.

Run the third failure again with the lease in place:

| Time | What happens | S7 |
|---|---|---|
| 10:40:00.000 | last proof for v42 arrives; `fresh_until = 10:40:01.000` | LIVE |
| 10:40:00.100 | distributor loses the limit service | LIVE |
| 10:40:00.250 – 00.750 | pings go unanswered | LIVE, then SUSPECT |
| 10:40:01.000 | `now > fresh_until` | **STALE: blocks new risk** |

Nobody had to notice the outage. S7 stopped adding risk on its own, within a second.

The budget is simple. If the lease lasts L and the slowest acceptable proof round trip is R, staleness is detected within L + R of the last good proof. Keep L + R within the 2-second policy. Both `now` and `fresh_until` come from the same host's monotonic clock, so no cross-host clock synchronisation is needed. In Handbook Ch 25's terms, it is a same-clock comparison — the kind that is always legal.

The `epoch` in each proof identifies the leader that produced it. After a leader failover, agents accept proofs only from the newest epoch, so a deposed leader that has not yet noticed cannot keep vouching.

> **Design move — Freshness lease.** A consumer may use state only while it holds a recent proof that its version is current; silence expires the proof. *Cost:* heartbeat traffic, and a clock check on every order.

**What does STALE actually do?** That is a policy decision, and it belongs to the risk owner, not to the candidate. The system's job is to make every state explicit and enforce whatever the policy says. A typical policy:

| State | Condition | New risk | Cancels and risk-reducing orders |
|---|---|---|---|
| LIVE | fresh proof, current version | allowed within limits | allowed |
| SUSPECT | two pings unanswered | allowed; alert raised | allowed |
| STALE | lease expired | **blocked** | allowed |
| RECOVERING | gap or reconnect, until snapshot plus fresh proof | **blocked** | allowed |

The right-hand column never changes. Risk-reducing actions must stay available precisely when the machinery is failing ([Handbook Ch 30](../../../release1/handbook-markdown/chapters/e3-pretrade-risk-engine/chapter.md), Part 3).

> **Design move — Fail safe, not open.** When safety cannot be proven, restrict: block new risk and keep risk-reducing actions available. *Cost:* false alarms stop trading, so the policy needs an owner.

The states are trust state published as data, the same idea a feed handler uses to tell strategies a book is stale ([Design a Low-Latency Market Data Feed and Normalization System](../sd-market-data-feed/question.md)). The policy is enforced inside the check, where it cannot be skipped.

### 3) What happens when a strategy falls behind or reconnects?

During a volatility spike, automated controls push 50 updates a second. Host 9's agent is slow — its machine is overloaded — and its queue at the distributor fills.

The distributor does not wait for host 9, and it does not drop deltas silently. It disconnects host 9. That is all it has to do. Watch what follows:

1. Host 9 stops receiving proofs, because its session is gone.
2. Within a second its leases expire, and its strategies go STALE on their own.
3. The agent reconnects and sends `Hello` with its applied versions.
4. The distributor sends the missing deltas, or a snapshot if the gap is too large or too old.
5. The agent swaps in the new tables, sends `Applied`, receives a fresh proof, and its strategies return to LIVE.

**Isolation and the lease compose: you can cut off a slow consumer without asking it anything, because it will stop itself.** Without the lease, disconnecting host 9 would leave its strategies trading on old limits with nobody aware of it. With the lease, the disconnection is safe by construction.

The same path covers the other failures:

| Failure | What happens | Back to LIVE when |
|---|---|---|
| Distributor crashes | agents reconnect to another distributor | first fresh proof |
| Agent restarts | cold start: snapshot | snapshot applied, fresh proof |
| Limit-service leader fails | proofs pause; leases expire if failover takes longer than the lease | new leader answers with a newer epoch |
| Network partition between host and service | leases expire | partition heals; gap filled |

Notice that every row ends in the same place, through the same code: reconnect, fill the gap or take a snapshot, swap, prove freshness. There is one recovery path, not one per failure.

**Should tightenings get special treatment?** A cut like Maya's is urgent. A loosening can wait. This design already favours tightening in the one place that matters: a strategy unsure of its limits stops adding risk, which is the conservative direction. For the truly urgent case — stop everything now — the firm's independent kill switch, not this service, is the last line of defence (Handbook Ch 30, Part 3).

## Interview calibration

**A passing answer**

- Stores limits durably with versions and pushes changes to strategies.
- Handles reconnects with a snapshot and mentions heartbeats.
- Says that a stale strategy should stop.

**A strong answer also**

- Runs a concrete scenario through the naive design until it breaks, and names the missing proofs.
- Applies changes atomically with build-aside-and-swap, and acknowledges only after the swap.
- Explains why freshness cannot come from change frequency, and builds a lease the order thread checks.
- Makes the authority, not the distributor, the source of freshness proofs.
- Leaves the stale policy to the risk owner while making every state explicit, and keeps cancels always available.
- Notices that bounded queues plus leases make disconnecting a slow consumer safe.

## Follow-ups

**Must every strategy switch to the new limits at the same instant?**

> Usually not: per-strategy atomicity is what the check needs. If a change spans strategies that hedge each other, add an activation version or time: distribute first, activate when every affected consumer reports it has the data. That costs a second phase and makes the slowest consumer set the pace — so reserve it for changes that genuinely need it.

**Why not just use etcd or ZooKeeper watches?**

> They are a fine foundation for the authority: versioned, replicated storage with change notifications, where etcd's revisions can serve as our versions. But a watch notification is "sent", not "applied", and a client's session being alive is not a per-order freshness guarantee at the check. You still need the atomic swap, acknowledgement after the swap, and a lease the order thread enforces.

**How would you test this?**

> Inject the failures on purpose. Pause a host agent with `SIGSTOP`, cut the distributor off from the limit service, kill the leader, and assert that every affected strategy is STALE within the policy bound plus a small margin. Stress the swap under ThreadSanitizer and assert that no check ever sees fields from two versions. Replay the change log to rebuild state and compare it with what the agents applied. [Handbook Ch 14 — *The Bug That Passes Every Test*](../../../release1/handbook-markdown/chapters/b7-testing-concurrent-code/chapter.md) explains why concurrency bugs need this kind of deliberate testing.
