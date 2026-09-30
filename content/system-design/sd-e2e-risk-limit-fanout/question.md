# Risk-Limit Update Fan-Out

## Interview prompt

Design a service that distributes real-time risk-limit updates to multiple
trading strategy processes. Consumers can disconnect or become slow, but a
strategy must not silently continue forever with stale limits.

The full risk platform is too large for one 45-minute interview. **Core** work
should establish the authority, durable record, bounded delivery path, and
mandatory strategy-side action. Then agree on one or two **Deep dive** topics:
end-to-end freshness, slow-consumer isolation, or reconnect and replay.
Cross-region activation and emergency controls are **Stretch** material.

## **Core** — Start with one tightening

At 10:31:04, risk manager Maya cuts strategy S7's AAPL position limit from
10,000 to 5,000 shares and its maximum new-order size from 500 to 100 shares as
one change. S7 holds 4,900 shares and is still producing 400-share buy orders;
Gate7, the function called before every S7 order reaches the gateway, must see
both new fields together. Strategy S8 is healthy, but S7's receiver thread has
stalled. If the service calls Maya's change “delivered” while Gate7 keeps the
old table, S7 can add risk precisely when Maya intended to stop it.

Those values are illustrative, not hidden requirements. The interviewer still
has to choose the real scale, latency bound, and what Gate7 does when freshness
is lost.

### Foundations this answer assumes

Keep the interview focused by linking, rather than reteaching, four foundations:

- [Pre-trade risk-engine foundations](../../../release1/handbook-markdown/chapters/e3-pretrade-risk-engine/chapter.md)
  explain why Gate7 must be on the order path; a dashboard can observe stale
  state but cannot enforce it.
- [Idempotency and duplicate handling](../../../release1/handbook-markdown/chapters/e1-idempotency-and-duplicates/chapter.md)
  supply the stable operation identity used when Maya retries after a timeout.
- [Batching, overload, and backpressure](../../../release1/handbook-markdown/chapters/d4-parsing-batching-backpressure/chapter.md)
  supply the bounded-queue model. Here the producer is internal, so it may
  deliberately disconnect a consumer that cannot keep up.
- [Deterministic replay](../../../release1/handbook-markdown/chapters/e4-deterministic-replay/chapter.md)
  explains which inputs and versioned artifacts must survive if an incident is
  to be reproduced.

## **Core** — Settle the contract before choosing components

**Clarify the decisions that change correctness.** Ask who may author limits
and whether the ordering scope is a strategy, account, desk, risk group, or
instrument. Ask whether several fields or scopes must change atomically and
whether tightening, relaxation, and future activation have different rules.

Then ask for:

- peak update rate `U`, consumer count `N`, average recipient fraction `p`,
  encoded update size `S`, snapshot size, and reconnect burst;
- the timed endpoints and percentile for “real-time” delivery;
- maximum time `T_stale` without proof that the active version is current;
- the policy action `A_stale` in `SUSPECT`, `STALE`, and `RECOVERING`:
  block new risk, allow only risk reduction, cancel orders, or halt;
- durability and evidence requirements for acceptance and application; and
- whether per-consumer atomic application is enough or all consumers need a
  coordinated activation boundary.

Do not choose `T_stale` or `A_stale` on the candidate's own authority. Those are
risk-policy decisions. A design can keep them symbolic, but it cannot omit
their behavior.

**State the formal contract in observable terms.** A strong baseline is:

1. A validated command receives one stable operation ID and one increasing
   version within its ordering scope.
2. The author sees success only after the complete version is committed to the
   durable authority.
3. Gate7 reads either the complete old limit table or the complete new one,
   never a mixture.
4. Within `T_stale` after Gate7 can no longer prove its active version is
   current, Gate7 performs `A_stale`.
5. Every per-consumer queue and retry loop has a finite bound; S7 cannot delay
   S8 or global acceptance.
6. A receiver that observes a version gap installs a verified contiguous
   suffix or a current snapshot before it returns to `LIVE`.
7. Evidence distinguishes `ACCEPTED`, `SENT`, and `APPLIED` for a named
   consumer and version.

Assume one logical writer owns each ordering scope and that strategies cannot
bypass Gate7. If either assumption is false, say so: the design needs
cross-scope coordination or an enforcement boundary at a gateway, broker, or
venue. A fan-out service alone cannot guarantee safe trading.

## What the interviewer is testing

- Can the candidate turn “fresh” into a bounded local safety action?
- Do they distinguish durable truth, byte delivery, and application at Gate7?
- Can they preserve transaction atomicity, ordering, retries, and recovery?
- Can they isolate a slow consumer with finite memory and a stated overflow
  action?
- Can they size steady delivery and reconnect bursts, then identify the scarce
  resource rather than naming fashionable infrastructure?

## **Core** — Execute the tempting design until it breaks

**The simplest plausible design has four physical pieces.** An HTTP API process
writes the latest limits into a database row and publishes a bundled message
to a broker process. On the strategy host, a receiver callback acknowledges the
broker message and places it on a local work queue. Gate7 runs on the order
thread and reads a mutable in-process limit table.

Walk Maya's change through that design:

1. The API stores both fields and publishes message `v42` for S7.
2. The broker invokes S7's callback. The callback puts `v42` on its local queue
   and acknowledges it, so the broker and dashboard report success.
3. The local worker stalls before it updates the table. Broker retry is now
   irrelevant because the message was acknowledged.
4. Gate7 reads `v41` and accepts the next 400-share order. If the worker instead
   mutates fields in place and stalls halfway, Gate7 can read the new position
   cap with the old order-size cap.
5. No further limit change is required, so silence can last indefinitely. The
   database is correct and the message was delivered, yet the enforcement
   point is wrong.

**The failure exposes two different missing proofs.** A complete version must
be published atomically to Gate7, and Gate7 needs continuing evidence that its
version is still the authority's current version. The age of the last *change*
cannot provide that evidence: limits may legitimately remain unchanged for
hours.

**Derived invariant.** Gate7 may use only one complete committed version.
Within `T_stale`, it must perform `A_stale` whenever it can no longer prove
that version is the authority's current version.

“Sent is not applied” and “freshness is not change frequency” now follow from a
concrete failure rather than from a broker choice.

## Good solution

### **Core** — Build the minimal correct path

Each name in the design maps to a physical process or memory structure:

- The authenticated `risk-api` sends Maya's validated command to one elected
  `scope-sequencer` process per shard. Its rising *fencing token* lets a
  replicated append-only log reject an old leader; quorum commit of the whole
  command is acceptance, independent of delivery.
- A `snapshot-builder` background process turns committed records into one
  checksum-protected, immutable limit-table file per current scope.
- `Dispatcher` processes tail the log through finite per-connection queues.
  They are replaceable because only the log and snapshots are authoritative.
- A strategy receiver thread builds an inactive table and atomically publishes
  an immutable view: table pointer, content `(version, hash)`, highest trusted
  authority epoch, and proof deadline. Gate7 loads that view and compares its
  own monotonic clock with the deadline before every order, so receiver stall
  cannot hide expiry.
- An `audit-projector` process records accepted, sent, applied, and state-change
  evidence in a queryable store that never authorizes an order.

For freshness, the receiver challenges the sequencer for a lease-bounded or
quorum-certified `HEAD(epoch, version, hash, session, nonce)`; the epoch is the
log's fencing term. A dispatcher can only relay it. A matching proof extends
the local deadline, and a newer certified epoch may advance unchanged content's
authority metadata. Failover needs no risk change, while S7 still cannot slow
S8.

### Version the command, not individual fields

**The committed unit is one complete transaction.** For Maya's change, the log
record needs only enough structure to make decisions mechanical:

```text
scope, operation_id, fencing_token
version, expected_base_version
complete_change_set, schema_version, content_hash
author, reason, accepted_at
```

The operation ID deduplicates retries, the expected base rejects stale edits,
and the token fences a former leader. Author and reason are audit facts.

**A transactional database with an outbox is a defensible alternative.** Its
transaction assigns the version and writes both current row and outbox; a
publisher drains later. The log makes ordering and replay explicit, but either
works with one acceptance point. Non-atomic “write, then publish” leaves a
crash gap.

Do not collapse order-dependent tightening, relaxation, or multi-field changes.
Only a checksum-verified full snapshot that explicitly supersedes omitted
versions may replace them.

### Publish at the enforcement point

**Application completes only when Gate7 can read `v42`.** The receiver:

1. validates channel, scope, schema, hash, and a non-regressing certified epoch;
2. accepts only an identical duplicate; otherwise the expected base must match;
3. applies both fields to an inactive table and validates it;
4. after matching `HEAD`, atomically publishes the table, identity, epoch, and
   local proof deadline; and
5. sends `APPLIED(S7, v42, hash)` only after publication.

A gap, conflicting duplicate, unknown schema, or bad hash leaves the last
complete table visible and moves the receiver to `RECOVERING`. `SENT` proves
only byte delivery; the post-swap `APPLIED` acknowledgement proves visibility
at the order check.

![Committed versions and authority-originated head proofs reach a bounded receiver before Gate7 can use them.](../../../generated/diagrams/sd-e2e-risk-limit-fanout/context.svg)

## **Deep dive** — Make freshness end to end

**A dispatcher must not be allowed to certify its own stale view.** Suppose its
link to the authority fails just before `v43` commits. Without the authority's
expiring `HEAD` proof, the dispatcher could keep saying “S7 is current at
`v42`” forever.

Use one ordered strategy socket for updates, challenges, and relayed proofs. A
dispatcher forwards the receiver's nonce to the authority and relays a `HEAD`
proof only after sending every record through its `head_version`. The receiver
renews the deadline only when the quorum certificate and signature validate;
the session and sole outstanding nonce match; the response meets the local
challenge budget; and `(head_version, head_hash)` matches Gate7's active
content. It consumes the nonce after one use. Replay cannot renew the deadline,
a dispatcher cannot stockpile future responses, and proof for `v42` cannot make
active `v41` fresh.

**Leader failover changes authority, not necessarily content.** If Gate7 holds
`(v42, H42)` from epoch 7 and a new leader wins epoch 8 without a risk update,
a quorum-certified `HEAD(epoch=8, v42, H42, nonce)` advances the view's trusted
epoch and deadline without republishing the table. Gate7 pins epoch 8 and
rejects later epoch-7 proofs, while the old leader cannot answer fresh nonces
after losing quorum or its lease. If the certified head version or hash
differs, the receiver must install that content before renewal. This term-only
transition preserves fencing while keeping freshness independent of change
frequency.

**The timeout budget composes across the path.** If `T_proof` is the maximum
locally measured challenge-to-proof time and Gate7 may retain the last valid
confirmation for `T_gate`, configure:

```text
T_proof + T_gate <= T_stale
```

Both durations use local monotonic clocks, so normal operation needs no
wall-clock synchronization. Each accepted proof publishes
`proof_deadline = now_monotonic + T_gate`; Gate7 compares its own monotonic
clock with that stored deadline before every order. If authority proof stops,
the dispatcher falls behind, the queue fills, or the receiver thread stalls,
nothing extends the deadline and Gate7 performs `A_stale` within the contract.

The receiver owns connection progress such as `CONNECTING` and `RECOVERING`,
but it does not own expiry. Gate7 derives `LIVE`, `SUSPECT`, or `STALE` from the
loaded view and current time; the exact action remains the risk owner's policy.

![A fresh challenge cannot reach the authority after dispatcher isolation, so Gate7's stored proof deadline expires and its order thread performs the stale action.](../../../generated/diagrams/sd-e2e-risk-limit-fanout/recovery-sequence.svg)

## **Deep dive** — Bound fan-out and recover explicitly

**A slow strategy owns a bounded inconvenience, not shared backpressure.** Give
each socket a finite byte/event queue or give each consumer an independent
cursor into a finite shared ring. The per-socket queue is the clearer baseline
for the illustrative scale. A shared ring reduces copies at larger fan-out but
still needs a rule that evicts a lagging cursor; the slowest cursor must never
retain the ring forever.

When S7 reaches its queue or send-deadline limit, the dispatcher marks it
lagging, stops ordinary deltas and freshness confirmations, and disconnects it
or requests a snapshot. It retains the consumer identity and last applied
version, not an unbounded personal history. S8 continues from the committed
log.

**Recovery chooses the cheaper trustworthy starting point.** On reconnect S7
sends its identity, scopes, schemas, last applied `(version, hash)`, and highest
trusted authority epoch. The dispatcher sends a retained suffix when that
content identity belongs to the authoritative history and the gap is small;
otherwise it sends the latest immutable snapshot plus versions committed during
transfer.
[Sequence and gap recovery](../../../release1/handbook-markdown/chapters/d3-sequence-and-gap-recovery/chapter.md)
provides the underlying suffix-versus-snapshot reasoning.

S7 remains `RECOVERING` until it has atomically installed the snapshot, applied
the contiguous suffix, and validated a current `HEAD` proof matching the
installed version and hash. Snapshot content identity is separate from its
creator's epoch, so a current certified epoch may validate unchanged content
created under an older leader. Cache one encoding per scope/version, admit
reconnects gradually, add jitter, and reserve capacity for current updates and
proofs so a site restart does not become a second outage.

## **Deep dive** — Size the bottleneck, not just the network

**Steady payload egress is approximately:**

```text
U * p * N * S bytes/second
```

For illustration, `U = 50` updates/s, `p = 1`, `N = 1,000` strategies, and
`S = 200` bytes produce about 10 MB/s before framing, proofs, and
acknowledgements. That is not a demanding aggregate bandwidth number on a
modern server. Correct ordering and tail behavior are the harder part.

**Queue memory makes the lag budget visible.** If each strategy receives 10
KB/s and `T_queue = 2 s`, its illustrative payload allowance is about 20 KB,
or 20 MB over 1,000 strategies before burst margin and allocator overhead.
The two seconds are an outage budget ending in disconnect, not permission to
queue forever.

**Reconnects can dominate the quiet steady state.** A 2 MB snapshot sent to 200
strategies after a site restart creates 400 MB of transfer plus repeated hash,
parse, and publication work. Cached encoding and admission control therefore
matter more than optimizing the 200-byte live messages. In this example the
scarce resources are reconnect concurrency, per-session tail latency, and
bounded memory—not raw live-update bandwidth.

Measure author-to-commit, commit-to-dispatch, socket-to-parse, and
parse-to-pointer-swap separately at the required percentile. Also expose active
and proved version, queue occupancy, watchdog margin, disconnect reason,
recovery duration, log/snapshot lag, dedup hits, conflicts, and hash or fencing
failures.

## **Deep dive** — Preserve one authority through failure and audit

**High availability needs a fenced writer, not two independent truths.** A
consensus group elects one scope-sequencer, certifies its authority epoch, and
checks that epoch on every append. Dispatchers may be active-active because
they only replay committed records. Without quorum or a valid lease, commands
are not acknowledged and new `HEAD` proofs stop; with a new certified leader,
term-only proofs keep unchanged content fresh while older epochs stay fenced.

**Accepted history and delivery evidence answer different questions.** The
authoritative log records Maya's command, authorization result, version, old
and new hashes, schema, writer token, and required validator artifacts. A
separate append-only evidence stream records dispatcher attempts, connection
epochs, `APPLIED` acknowledgements, and freshness-state transitions.
`SENT` is not `APPLIED`, and a missing acknowledgement means unknown rather
than definitely failed.

Replay begins at a known snapshot and applies committed versions in order,
checking the hash after each table. That can reproduce what Gate7 was able to
install. Reproducing exact network timing additionally requires recorded
connection, timer, and failure inputs; the configuration log alone cannot make
that claim.

No standalone runnable experiment is warranted. A toy in-process queue would
not test the material claims—durable failover, isolated network stalls, or the
mandatory gate. The meaningful tests are protocol integration tests and fault
injection against those process boundaries.

## Failure scenarios

**Core — check the contract against concrete faults.**

| Failure | Expected outcome |
|---|---|
| Maya retries after a response timeout | The operation ID returns the original committed version; no second change is created. |
| Sequencer dies before commit | No success is returned; a retry is safe. |
| Sequencer dies after commit but before reply | The retry discovers the committed operation and version. |
| Leader changes; old sequencer resumes | A certified newer epoch can renew unchanged content, while the log and receivers reject the old epoch. |
| Dispatcher loses the authority link | Its `HEAD` proof expires, confirmations stop, and Gate7 reaches `A_stale` within the composed bound. |
| S7 stops reading | Its finite queue reaches policy; S8 and acceptance continue. |
| S7 observes a gap or corrupt update | It keeps the last complete table, enters `RECOVERING`, and requests a suffix or snapshot. |
| Many strategies reconnect together | Admission control and cached snapshots bound recovery while reserved capacity protects current traffic. |

## Great solution improvements

1. **Stretch — add an independent emergency brake.** A broker/venue halt or
   cancel mechanism can reduce risk when the ordinary control plane is down;
   it must not become an unsequenced routine writer.
2. **Stretch — stage coordinated activation only when required.** Distribute a
   verified immutable table in `PREPARED` state, then activate it with a
   versioned boundary and an explicit policy for missing participants.
3. **Deep dive — continuously prove the failure contract.** Inject stalled
   readers, authority isolation, leader failover, corrupt deltas, snapshot
   loss, and reconnect storms; assert Gate7's action and the bounded impact on
   S8.

## Common pitfalls

- Treating database success, broker acknowledgement, TCP delivery, or a
  callback as proof that Gate7 installed the limit.
- Measuring freshness from the last change instead of an authority-originated,
  expiring proof of the current head.
- Letting an isolated dispatcher manufacture confirmations for its stale view.
- Mutating a live table field by field or skipping a version gap.
- Calling an unbounded queue “isolation,” or letting the slowest cursor retain
  a shared ring.
- Blocking global acceptance on every consumer acknowledgement.
- Replaying from the beginning after every reconnect and causing a recovery
  storm.
- Choosing a stale timeout or cancel policy without the risk owner's decision.

## Follow-up questions

### **Core** — S7's queue is full when Maya tightens the limit. What happens?

The tightening keeps its committed version and reaches S8. S7 gets no unbounded
backlog: its dispatcher stops confirmations and disconnects or resnapshots it,
so Gate7 performs `A_stale` within the bound. S7 installs a verified current
snapshot before returning `LIVE`.

### **Deep dive** — A region partitions during leader change. How do you avoid two truths?

The quorum and fencing token allow only one scope-sequencer to append. The
minority cannot acknowledge commands or originate new `HEAD` proofs. The
availability cost is deliberate; an independent risk-reducing brake may still
operate, but both regions cannot accept ordinary writes.

### **Stretch** — Ten thousand strategies must activate one version “together.” What changes?

Clarify permitted skew and the action for a strategy that cannot prepare.
Broadcast is not simultaneous atomic visibility. A defensible extension stages
the immutable table, records readiness, and sends one versioned activation for
a clock boundary or barrier, accepting added coordination and reduced
availability.

## Evaluation rubric

| Level | Evidence in the conversation |
|---|---|
| Insufficient | Names a broker and database but has no mandatory stale action, applied acknowledgement, gap recovery, or finite slow-consumer policy. |
| Pass | Derives one durable version authority, atomic local publication, end-to-end bounded freshness, per-consumer isolation, and snapshot recovery. |
| Strong | Explains authority-originated proofs, retries and fencing, sizes steady and reconnect load, and separates accepted history from application evidence. |
| Exceptional | Challenges the enforcement boundary, reasons about tightening versus relaxation, handles split brain and coordinated activation, and ties fault injection to each invariant. |

Give most weight to safety and failure reasoning, then to recovery and bounded
fan-out, and finally to product choices. A named broker, database, or transport
earns no credit without its ownership, ordering, and failure semantics.

## Related question

[`sd-market-data-feed`](../sd-market-data-feed/question.md) exercises a larger
low-latency fan-out system with independent cursors, gap recovery, and raw
replay. This question narrows those mechanisms around an enforceable
risk-limit freshness contract.
