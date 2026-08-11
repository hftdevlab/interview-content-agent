<!--
chapter: b0-threads-atomics-locks
state: draft_created
contract: standards/chapter-contract.md
include_measurement_plan: false | include_quizzes: true | primary_artifact_mode: code
role: Module B entry point. Bridges mutex-based C++ to the memory model (b1).
unresolved_markers: 0
-->

# The Counter That Lost Count

## Threads, Atomics, and Locks: The Tools of Concurrency

**Prerequisites:** [a1] Anatomy of an electronic trading system
**Focus:** atomicity is a property of an *operation*, not of a variable — and each tool makes a different scope of operation indivisible

---

## A few thousand messages short

A feed handler is falling behind on busy mornings, so it gets split across two threads. Each takes a share of the symbols, and both increment a shared counter of messages processed:

```cpp
uint64_t messages_processed = 0;   // shared by both threads

void handle(const Message& m) {
    parse_and_publish(m);
    ++messages_processed;          // one line, one operation. Surely.
}
```

At the end of the session the counter reads a few thousand short of the true total. Not wildly wrong — the number looks entirely plausible, which is why nobody notices for a week. It is just quietly, consistently low.

There is nothing to fix in that line. `++` is one token in the source and three operations on the machine: **read** the current value into a register, **add** one, **write** it back. Two threads can interleave between those steps. Both read 1,000. Both compute 1,001. Both write 1,001. Two messages were processed and the counter advanced by one.

This chapter is about the tools that stop that happening, and about what each of them actually guarantees. It is the foundation the rest of Module B stands on — and if you have written multi-threaded C++ with a mutex and never needed anything else, this is the chapter that gets you from there to the material that follows.

## Where you will actually meet this

Everywhere two threads touch the same data, which in a trading system is everywhere:

- **Counters and statistics** shared between working threads and a monitoring thread — the case above.
- **Position and exposure**, read and updated by the strategy, the risk engine, and reporting ([e3]).
- **Queue indices**, which are how one thread tells another that data is ready. Every chapter after this one depends on them ([b2]).

Interviews at latency-sensitive firms generally assume this material rather than testing it — the questions start where this chapter ends. That makes it worth being fluent rather than merely familiar: `compare_exchange` in particular shows up throughout the rest of the book, and stopping to work out its semantics mid-answer is the kind of hesitation that reads as unfamiliarity with the whole area.

## The mental model

Threads share memory. That is the entire source of the difficulty: two threads running on two cores, both able to read and write the same locations, with no coordination beyond what you write.

The problem is **not** that operations are slow or that threads run at unpredictable speeds. It is that operations you think of as single steps are not single steps at the level where interleaving happens. The unit of atomicity in your source code is not the unit of atomicity in the machine.

So the question to ask of any shared-data code is: **what exactly is the indivisible unit here, and is it big enough to preserve what I need to be true?**

Two ways an operation can be too small:

**Lost updates.** The read-modify-write case above. Both threads read the same value, both compute from it, one result is discarded.

**Torn reads and writes.** A wide value — say a 16-byte struct — may not be written in one step. Another thread can read it half-updated, seeing a combination that never existed: the new price with the old quantity. Not stale data; *impossible* data.

If you have a database background, atomicity here is the same idea as the A in ACID — an operation either fully happened or did not happen at all, with no observable middle. The scope is much smaller, but the guarantee is the same shape.

## Part 1 — The mutex: making a block indivisible

The tool you already know. A mutex gives you mutual exclusion: at most one thread at a time may hold it, so a block of code guarded by one is indivisible with respect to any other thread guarding with the same mutex.

```cpp
// code-b0-1 | RUNNABLE | C++20 | examples/, target: concurrency_basics
std::mutex m;
uint64_t   messages_processed = 0;

void handle(const Message& msg) {
    parse_and_publish(msg);
    std::lock_guard<std::mutex> lock(m);   // released at end of scope
    ++messages_processed;                  // now indivisible
}
```

The counter is fixed. But notice what the mutex actually gave you, because it is more than the counter needed: **an arbitrary block of code**, of any length, touching any number of variables, made indivisible as a unit.

That is the mutex's real strength, and it is why it never goes away. Consider an invariant spanning two variables:

```cpp
// A quote must always have a consistent price and size together.
{
    std::lock_guard<std::mutex> lock(quote_mutex);
    quote.price = new_price;
    quote.size  = new_size;          // no reader can see the pair half-updated
}
```

No collection of atomic variables gives you this. You could make `price` and `size` each atomic and a reader could still see the new price with the old size — each write was indivisible, and the *pair* was not. **Atomicity does not compose**, and that single fact determines most of the choices in this chapter.

A mutex also brings a companion tool for waiting. When a thread needs to wait for a condition rather than for exclusive access, a **condition variable** lets it release the mutex and sleep until another thread signals:

```cpp
std::condition_variable cv;

// Consumer
std::unique_lock<std::mutex> lock(m);
cv.wait(lock, [&]{ return !queue.empty(); });   // sleeps, releasing the lock
auto item = queue.pop();
```

That is the standard blocking handoff, and it is correct. What it costs — and when a trading system cannot afford it — is [b5]'s subject. What happens if the thread holding the mutex is descheduled at the wrong moment is [b3]'s.

## Part 2 — Atomics: making one location indivisible

`std::atomic<T>` makes operations on a single location indivisible. No mutex, no blocking, and for the types that matter it usually compiles to one instruction.

```cpp
std::atomic<uint64_t> messages_processed{0};

messages_processed.fetch_add(1);       // indivisible read-modify-write
```

Three families of operation, and the distinction between them is the thing to hold onto.

**Load and store** — read or write the whole value indivisibly. Prevents torn reads and writes. Does *not* prevent lost updates, because a load and a separate store are two operations.

```cpp
uint64_t v = counter.load();
counter.store(v + 1);                  // STILL loses updates — two operations
```

**Read-modify-write** — read, compute, and write as one indivisible operation. This is what fixes lost updates.

```cpp
counter.fetch_add(1);        // returns the value BEFORE the addition
counter.fetch_sub(1);
flags.fetch_or(kReady);
uint64_t old = value.exchange(42);     // unconditional swap, returns the old
```

**Compare-exchange** — the general one, and the one worth being fluent in.

```cpp
bool ok = value.compare_exchange_weak(expected, desired);
```

It compares `value` against `expected`. If they match, it writes `desired` and returns true. If they do not match, it writes the *actual current value* back into `expected` and returns false.

That last part is the whole trick. On failure you are handed the value you did not know about, ready to try again:

```cpp
// code-b0-2 | RUNNABLE | C++20 | examples/, target: concurrency_basics
// Update a high-water mark: only raise it, never lower it.
// There is no fetch_max, so compare-exchange is how you build one.
void record_peak(std::atomic<uint64_t>& peak, uint64_t observed) {
    uint64_t current = peak.load();
    while (observed > current) {
        if (peak.compare_exchange_weak(current, observed))
            return;                     // we set it
        // failed: `current` now holds what another thread put there.
        // The loop condition re-tests against that new value.
    }
}
```

Read that loop again with the failure semantics in mind. You never reload `peak` manually — the failed exchange did it for you, and re-testing `observed > current` handles the case where another thread already set a higher peak, in which case you correctly stop.

**Weak versus strong.** `compare_exchange_weak` may fail spuriously — returning false even when the values matched — because on some architectures the underlying instruction can be interrupted. It is cheaper, and inside a retry loop a spurious failure costs one extra iteration. Use `weak` in a loop, `strong` when you are not looping and a spurious failure would be wrong.

**Not every type is cheap.** `std::atomic<T>` compiles to hardware instructions only for types the hardware supports — typically up to the machine word size, sometimes double that. For anything larger, the standard library falls back to a hidden lock, so `std::atomic<BigStruct>` compiles fine and is not lock-free at all. `is_lock_free()` tells you which you got, and it is worth checking rather than assuming.

**And there is an ordering parameter you have not seen yet.** Every operation above takes an optional memory-order argument, and when you omit it you get `std::memory_order_seq_cst` — the strongest and most expensive option. That default is correct: code written without thinking about ordering will not be wrong because of ordering. It is also not free, and understanding when you can weaken it is [b1], the next chapter. For now, omitting it is the right choice.

---

**Quiz 1**

Which of these are safe, and which need something stronger?

```cpp
// 1
std::atomic<int> count{0};
count = count + 1;

// 2
std::atomic<uint64_t> total{0};
total.fetch_add(size);

// 3
struct Quote { std::atomic<double> price; std::atomic<uint32_t> size; };
q.price.store(new_price);
q.size.store(new_size);

// 4
std::atomic<bool> ready{false};
if (!ready.load()) { ready.store(true); do_once(); }
```

> **Answer**
>
> **1 — Broken.** `count = count + 1` is an atomic *load*, an ordinary addition, and an atomic *store*: three operations, not one. Both threads can load the same value and both store the same result. The variable being atomic prevented torn reads and did nothing about the lost update. This is the single most common misunderstanding of `std::atomic`, and it compiles without a warning. Use `fetch_add(1)` or `++count`, which the standard defines as an atomic read-modify-write.
>
> **2 — Safe.** `fetch_add` is one indivisible read-modify-write. This is exactly the fix for the opening scenario.
>
> **3 — Broken for its purpose.** Each store is indivisible, and the *pair* is not. A reader between the two stores sees the new price with the old size — a quote that was never true. Atomicity does not compose. Either put both under a mutex, or pack them into one atomically-writable value, or publish them through a mechanism that makes the pair visible together (which is what [b2]'s queue does).
>
> **4 — Broken.** Two threads can both load `false`, both store `true`, and both call `do_once`. Load-then-store is two operations with a gap. The fix is one operation that does both: `if (!ready.exchange(true)) do_once();` — exchange returns the previous value, so exactly one thread sees `false`.
>
> The pattern in 1, 3, and 4 is the same: **the indivisible unit was smaller than the thing that needed to be indivisible.** That is the question to ask every time.

---

## Part 3 — Choosing between them

The comparison, on the terms that decide real code:

| | Mutex | Atomic |
|---|---|---|
| **Scope made indivisible** | An arbitrary block of code | One memory location |
| **Invariants across several variables** | Yes | No |
| **Uncontended cost** | Low — usually stays in user space | Low — usually one instruction |
| **Contended cost** | Waiters sleep; the OS gets involved | Retries or coherence traffic ([a6]) |
| **If the holder is descheduled** | Everyone waits ([b3]) | Nothing to hold, so nothing stalls |
| **Composes** | Yes — take the lock across both operations | **No** |
| **Difficulty to get right** | Low | Rises steeply with complexity |

The decision rule that follows:

> **Use an atomic when the indivisible unit really is one location. Use a mutex when it is anything larger. Use neither when the data does not need to be shared.**

That third clause is the one worth taking seriously. The best solution to most of this chapter's problems is per-thread state with no sharing at all — each thread keeps its own counter and a monitoring thread sums them, at which point there is nothing to make atomic. Sharing is the cost; the tools here are what you pay when you cannot avoid it.

Which leaves an obvious question. If a mutex is easier and composes better, why does the rest of this module spend so long on atomics? Because a mutex creates a dependency on the operating system's scheduler, and on the critical path of a trading system that dependency is unacceptable — for reasons that are [b3]'s subject and [b5]'s. When you drop the mutex, you take on an obligation the mutex was quietly discharging on your behalf, and that obligation is what [b1] is about.

---

**Quiz 2**

Complete this compare-exchange loop, which should double the value only if it is currently below a cap:

```cpp
void double_if_below(std::atomic<uint64_t>& value, uint64_t cap) {
    uint64_t current = value.load();
    while (current < cap) {
        // ??? — apply value = current * 2, retrying on interference
    }
}
```

What goes in the loop, and what happens on failure?

> **Answer**
>
> ```cpp
> void double_if_below(std::atomic<uint64_t>& value, uint64_t cap) {
>     uint64_t current = value.load();
>     while (current < cap) {
>         if (value.compare_exchange_weak(current, current * 2))
>             return;                     // succeeded
>         // failed: `current` now holds the actual value another thread wrote.
>         // The loop condition re-tests it against the cap.
>     }
> }
> ```
>
> **On failure, `compare_exchange_weak` overwrites `current` with what it actually found.** So the loop needs no manual reload — writing `current = value.load();` inside the loop is redundant at best, and at worst introduces a window where the value changes between the reload and the next attempt.
>
> Two things this structure gets right that hand-written versions often miss. The recomputation of `current * 2` happens against the *new* `current`, so the update is always derived from a value that was genuinely present. And the `while (current < cap)` re-test means that if another thread pushed the value to or past the cap while we were trying, we exit rather than doubling something we should not have.
>
> The trap is treating failure as an error to retry blindly. It is not an error — it is a fresh reading, and the loop's job is to reconsider the whole decision with it, not just to attempt the same write again.

---

## Common mistakes

**`x = x + 1` on an atomic.** Three operations. Quiz 1.

**Assuming a struct of atomics is thread-safe.** Each field is indivisible and the object is not.

**Assuming `std::atomic<T>` is lock-free for any `T`.** Large types fall back to a hidden lock. Check `is_lock_free()`.

**Reloading the atomic inside a compare-exchange loop.** The failed exchange already did it, correctly. Quiz 2.

**Using `compare_exchange_strong` inside a retry loop.** You are paying to avoid spurious failures that the loop handles anyway.

**Reaching for atomics to avoid "slow" mutexes.** An uncontended mutex is cheap; the reason to avoid it on the hot path is scheduler dependency, not speed ([b3]).

**Sharing data that did not need to be shared.** Per-thread state summed on demand removes the problem instead of solving it.

**Using `volatile` for any of this.** It is not a threading tool. It does not make operations atomic and does not synchronise anything ([b1]).

## Operational behaviour

- **Lost-update bugs produce plausible numbers, not crashes.** Nothing alarms; the count is simply low. They are found by reconciliation against an independent source, which is a reason to have one.
- **Make shared counters atomic even where precision is not critical.** A torn read of a wide type is not a stale value, it is a value that never existed — and someone will eventually make a decision based on it.
- **Contended atomics are a scaling problem, not an error.** If per-thread throughput falls as threads are added, the coherence cost of a shared location is a prime suspect ([a6]).
- **Prefer per-thread counters aggregated on read.** Cheaper, contention-free, and the aggregation happens off the hot path.

## When not to reach for either

- **When the data can be thread-local.** The best answer to a sharing problem is not to share.
- **When one thread owns the data and publishes it.** That is a queue, and Module B's remaining chapters are about doing it well ([b2]).
- **When the path is cold and a mutex is clearer.** Config reload, session setup, admin interfaces. Clarity wins on paths where microseconds do not ([a1]).
- **When you cannot state the invariant.** If you cannot say what must be indivisible, you cannot choose the tool — and picking one is guessing.

## Interview mapping

- **Explain why `++` loses updates** in terms of read-modify-write. Table stakes, and worth being crisp about.
- **Distinguish the operation families.** Load/store prevent tearing; read-modify-write prevents lost updates. Candidates who say "atomic means thread-safe" have not made this distinction.
- **Write a compare-exchange loop from memory**, including that failure writes back the observed value. This comes up constantly in later material and hesitating here is costly.
- **Say that atomicity does not compose.** It is the reason mutexes survive, and it is the cleanest justification for choosing one.
- **Mention that the default ordering is `seq_cst`** and that it is not free. It shows you know the parameter exists before anyone asks about [b1].
- **Suggest not sharing at all** where the problem allows it. Frequently the best answer, and rarely the first one offered.

## Summary

`++` on a shared counter is a read, a modify, and a write, and threads interleave between them — so the bug in the opening scenario is not in the line of code but in the gap between what looks like one operation and what actually is one.

Fixing it means choosing an indivisible unit large enough to preserve what must be true. A mutex makes an arbitrary block indivisible, which is why it is the only tool that can maintain an invariant spanning several variables. An atomic makes one location indivisible: load and store prevent tearing, read-modify-write operations prevent lost updates, and compare-exchange generalises the rest by handing back the value it found so you can reconsider and retry.

Atomicity does not compose. Two atomic operations are not an atomic operation, and no arrangement of atomic variables reproduces what a mutex gives you across a block. That single fact decides most of the choices here — and it is why the rest of this module, which removes the mutex from the hot path, has to work so hard to get back the guarantees it gave away.

The first thing it gave away is visibility: with no mutex, what is one thread guaranteed to see of another's writes? That is [b1], and everything from here rests on it.

**Related:** [b1] memory model · [b2] SPSC ring buffers · [b3] progress guarantees · [b5] waiting strategies · [a6] coherence and false sharing · [a1] system anatomy · [e3] pre-trade risk

## References

- ISO/IEC. (2020). *ISO/IEC 14882:2020 — Programming languages — C++*. International Organization for Standardization. [`<atomic>` and `<mutex>`]
- Williams, A. (2019). *C++ concurrency in action* (2nd ed.). Manning. [threads, locks, and atomic operations, with worked examples]
