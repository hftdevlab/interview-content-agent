# Implement a Sequence-Counted Snapshot and Explain Its Memory Ordering

This is a coding-and-concepts exercise. The implementation is intentionally
small; most of the learning value is in proving which snapshots are legal
under the ISO C++ memory model.

## Concise interview answer

A sequence-counted snapshot lets readers copy several related fields without
taking the writer's lock:

1. an even sequence means the payload may be stable;
2. the writer changes the sequence to odd;
3. the writer updates all payload fields;
4. the writer publishes the next even sequence;
5. a reader accepts its copy only when the sequence was equal and even before
   and after the copy.

The algorithm is optimistic: readers may retry, and writers must be serialized.
In portable C++, the payload cannot simply be ordinary concurrently read/written
fields. Those accesses would be a data race and therefore undefined behavior.
The reference exercise uses atomic payload fields and sequentially consistent
ordering so the proof is clear before discussing weaker optimizations.

## Deep explanation

### The concrete coding problem

Several reader threads need a consistent quote:

```cpp
struct Quote {
    std::int64_t bid_ticks;
    std::int64_t ask_ticks;
    std::uint64_t exchange_ts_ns;
};
```

One or more producer threads may publish a new quote. Readers must never observe
a mixed generation such as:

```text
bid_ticks       from update 41
ask_ticks       from update 42
exchange_ts_ns  from update 41
```

A mutex around both read and write is the correctness baseline. The sequence
counter explores a different trade-off: serialize writers, but let readers
retry instead of taking the lock.

### Derive the odd/even protocol

Assume the stable version is `40`:

```text
sequence = 40   payload generation 40 is stable
sequence = 41   writer is modifying the payload
payload stores  generation 42 is written field by field
sequence = 42   generation 42 is stable
```

A reader performs:

```text
before = sequence
if before is odd: retry
copy every payload field
after = sequence
if before != after: retry
otherwise accept
```

If a writer's odd/even transition appears anywhere between the two sequence
observations, the reader rejects the copy.

### The most important C++ trap

This tempting layout is not a portable C++ sequence lock:

```cpp
std::atomic<std::uint64_t> sequence;
Quote payload;  // ordinary fields
```

If a reader copies `payload` while a writer changes it, at least one conflicting
access is non-atomic and there is no happens-before relationship. The ISO C++
rule says that execution has a data race and undefined behavior. A later
version check does not retroactively legalize the reads.

The relevant rule is in the C++ draft's
[data-race section](https://www.eel.is/c%2B%2Bdraft/intro.races). Linux kernel
sequence counters use kernel primitives and a kernel memory model; their
[seqlock documentation](https://docs.kernel.org/locking/seqlock.html) is useful
for the algorithm and operational constraints, but its code should not be
copied mechanically into portable user-space C++.

### Why the reference starts with `memory_order_seq_cst`

The reference makes the sequence and every payload field atomic, and uses
`memory_order_seq_cst` for all shared accesses. Sequentially consistent atomic
operations participate in one total order.

The writer's operations appear in that order as:

```text
store odd sequence
store bid
store ask
store timestamp
store even sequence
```

The reader's operations appear as:

```text
load sequence before
load bid
load ask
load timestamp
load sequence after
```

If `before == after` and the value is even, no writer's odd/even pair can be
between those observations in the total order. Because the payload stores are
inside that pair, the reader cannot have accepted a mix spanning a completed
writer generation.

This is deliberately stronger than a highly tuned implementation. It gives the
candidate a small, defensible proof. The standard's
[atomic ordering section](https://www.eel.is/c%2B%2Bdraft/atomics) defines
relaxed, acquire, release, and sequentially consistent behavior.

### What acquire and release would need to accomplish

When weakening the ordering, there are two different “bookends”:

- **Writer opening:** readers must not observe new payload stores as though they
  happened before the odd marker.
- **Writer closing:** payload stores must become visible before the final even
  marker is published.
- **Reader opening:** payload loads must occur after the first acceptable even
  observation.
- **Reader closing:** the final sequence observation must not move ahead of the
  payload loads it validates.

A final release store read by an acquire load can publish preceding payload
stores, but that is only one of the required edges. Two acquire counter loads
and a release final store are not a substitute for proving both bookends.
Relaxed payload atomics avoid undefined behavior, but relaxed ordering alone
does not prove a consistent multi-field snapshot.

For production optimization, use a reviewed sequence-counter abstraction with
the exact fences required for the target compilers and architectures, or choose
a design whose correctness is easier to express. Do not weaken each operation
independently because it “looks safe on x86.”

### Progress and lifecycle properties

- Readers are lock-free in the informal sense that they do not acquire the
  writer mutex, but they are not guaranteed bounded completion.
- A continuously active or preempted writer can cause reader retry storms.
- The sequence counter does not serialize multiple writers; the reference uses
  a writer mutex.
- A 64-bit counter can wrap. Equality after a complete wrap is theoretically an
  ABA problem if a reader can span that many writes.
- Pointer payloads need independent lifetime protection. A retry cannot rescue a
  reader that already dereferenced freed memory.

## Good answer framework

1. State the requirement: every field must come from one published generation.
2. Offer a mutex as the correct baseline, then derive the odd/even retry
   protocol.
3. State writer serialization and possible reader starvation.
4. Catch the plain-payload data race before choosing memory orders.
5. Implement the strong portable version; weaken ordering only after proof and
   measurement.

## Great answer improvements

- **Make the proof executable.** Document that writers are serialized, every
  shared field is atomic, and accepted reads saw one equal even generation.
  Stress-test relationships such as `ask == bid + 1` so torn snapshots fail.
- **Measure before weakening ordering.** Record retries, reader tail latency,
  writer rate, generated assembly, and cache-line traffic. Sequential
  consistency may not be the dominant cost.
- **Choose a design that fits the payload.** Small integer snapshots can use
  atomic fields; a supported `atomic<Snapshot>` may be simpler; larger state may
  favor immutable snapshot publication or a mutex with bounded progress.

## Example

### `quote_snapshot.hpp`

```cpp
#pragma once

#include <atomic>
#include <cstdint>
#include <mutex>

struct Quote {
    std::int64_t bid_ticks;
    std::int64_t ask_ticks;
    std::uint64_t exchange_ts_ns;

    bool operator==(const Quote&) const = default;
};

class SequenceSnapshot {
public:
    SequenceSnapshot() noexcept = default;

    void publish(const Quote& quote);
    Quote read() const noexcept;

private:
    // Serializes writers. Readers never acquire this mutex.
    std::mutex writer_mutex_;

    alignas(64) std::atomic<std::uint64_t> sequence_{0};
    std::atomic<std::int64_t> bid_ticks_{0};
    std::atomic<std::int64_t> ask_ticks_{0};
    std::atomic<std::uint64_t> exchange_ts_ns_{0};
};
```

### `quote_snapshot.cpp`

```cpp
#include "quote_snapshot.hpp"

#include <cstdint>
#include <mutex>

void SequenceSnapshot::publish(const Quote& quote) {
    const std::lock_guard<std::mutex> lock(writer_mutex_);

    const std::uint64_t stable =
        sequence_.load(std::memory_order_seq_cst);

    // stable is even because writers are serialized and every publish closes.
    sequence_.store(stable + 1, std::memory_order_seq_cst);

    bid_ticks_.store(quote.bid_ticks, std::memory_order_seq_cst);
    ask_ticks_.store(quote.ask_ticks, std::memory_order_seq_cst);
    exchange_ts_ns_.store(
        quote.exchange_ts_ns, std::memory_order_seq_cst);

    sequence_.store(stable + 2, std::memory_order_seq_cst);
}

Quote SequenceSnapshot::read() const noexcept {
    for (;;) {
        const std::uint64_t before =
            sequence_.load(std::memory_order_seq_cst);
        if ((before & 1U) != 0U) {
            continue;
        }

        const Quote copy{
            bid_ticks_.load(std::memory_order_seq_cst),
            ask_ticks_.load(std::memory_order_seq_cst),
            exchange_ts_ns_.load(std::memory_order_seq_cst),
        };

        const std::uint64_t after =
            sequence_.load(std::memory_order_seq_cst);
        if (before == after) {
            return copy;
        }
    }
}
```

The runnable package uses this implementation and checks the field invariants
with concurrent writers/readers.

## Common misconception

### “The final sequence check makes ordinary payload reads safe”

False in ISO C++. The ordinary read/write race is already undefined behavior.
Validation can reject a logically inconsistent atomic snapshot; it cannot undo
a language-level data race.

### “Acquire makes the whole snapshot consistent”

Acquire describes ordering relative to an operation it synchronizes with. It
does not turn several independent payload locations into one atomic snapshot,
and it does not automatically prove the closing side of a retry protocol.

### “Lock-free readers and multiple writers need no other coordination”

False. Readers can retry indefinitely, and two writers can interleave their
odd/even transitions. Use single-writer ownership or a writer lock, and choose
another design if bounded reader completion matters.

## Interview trap

An interviewer may show:

```cpp
std::atomic<std::uint64_t> sequence;
Quote payload;
```

and ask which memory order belongs on `sequence`. The first answer should be:
“Before choosing the order, the concurrent non-atomic payload accesses are a
data race in portable C++.”

Other common traps:

- a writer blocks or is preempted for a long time while the counter is odd;
- a payload contains a pointer the writer can free;
- the counter wraps while a reader is stalled;
- a reader checks only that the two sequence values match, but not that they are even;
- a benchmark measures throughput but not retries or tail latency;
- `volatile` is used as a threading primitive.

## Follow-up questions

### Why not use `memory_order_relaxed`, and can acquire/release replace `seq_cst`?

The accesses remain atomic, so there is no data race, but relaxed operations do
not provide the ordering needed to prove that payload accesses remain between
the version observations. Acquire/release may work with a carefully reviewed
set of operations and fences, but both writer and reader bookends matter.

### What are the progress and multi-writer limits?

Readers may retry indefinitely under sustained writes or a preempted odd
writer. The counter also does not serialize writers. Use a writer lock, and use
a fallback or different design when bounded reader completion is required.

### Why are pointers dangerous, and how would you test the implementation?

Retry protects consistency, not lifetime; a reader can dereference an object
freed before it notices the new sequence. Test atomic payloads by publishing
fields with fixed relationships from concurrent writers while many readers
verify them, then run stress and sanitizer builds.

## Related concepts

- ISO C++ happens-before, synchronization, and data-race rules;
- acquire, release, relaxed, and sequentially consistent atomics;
- optimistic concurrency control and version validation;
- writer serialization;
- cache coherence and false sharing;
- immutable snapshots, safe reclamation, and mutex alternatives.

## Runnable experiment

See the complete starter, reference implementation, and concurrent tests:

[`practice/questions/fund-sequence-lock`](../../../practice/questions/fund-sequence-lock/README.md)

The exercise intentionally begins with sequential consistency. A later advanced
variant can compare a reviewed weaker-order implementation, a mutex, and
immutable snapshot publication while recording retries and latency percentiles.
