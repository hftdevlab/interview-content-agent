<!--
chapter: b3-progress-guarantees
state: draft_created
contract: standards/chapter-contract.md
include_measurement_plan: false | include_quizzes: true | primary_artifact_mode: code
unresolved_markers: 0
-->

# When One Thread Stops, What Happens to the Rest

## Blocking, Lock-Free, and Wait-Free Progress Guarantees

**Prerequisites:** [b2] SPSC ring buffers · [b1] C++ memory-model foundations
**Focus:** progress guarantees describe what happens to *other* threads when one is descheduled — they are a statement about the worst case under preemption, not a claim about speed

---

## The thread that stopped at the wrong moment

A strategy thread takes a mutex to update shared position state. It is a short critical section — a few field updates, well under a microsecond.

Two seconds after an economic release, mid-burst, the operating system preempts it. Not because anything went wrong: its timeslice expired, or an interrupt arrived and the kernel took the opportunity to reschedule, or a higher-priority thread woke up. Perfectly normal behaviour.

The strategy thread is holding the mutex.

The feed handler needs that lock to record a fill. The order gateway needs it to check exposure. Neither can proceed. They are not slow — they are stopped, waiting on a thread that is not running, and will not run until the scheduler comes back to it. That could be a full timeslice, which is measured in milliseconds on a general-purpose kernel.

Nothing crashed. No function is slow. Every profiler will show a system that was idle. And for a few milliseconds, during a burst, the firm stopped trading.

The critical section was under a microsecond. That was never the number that mattered.

## Where you will actually meet this

This is why hot-path structures in trading systems avoid locks — and the reason is worth stating precisely, because the common version of it is wrong. It is not that locks are slow. An uncontended mutex acquire is cheap. It is that **a lock creates a dependency on the scheduler**, and the scheduler is not something you control.

You meet the consequence everywhere in the fast path: the ring buffer between feed handler and strategy ([b2]), the queue into the order gateway, per-thread statistics published without a lock. Each of those is lock-free not because someone benchmarked it faster but because none of them may stall when a thread is descheduled.

It is a standard interview topic, and it separates candidates sharply. The weak answer treats lock-free as a performance technique. The strong answer notices that the question is about worst-case progress, then observes — unprompted — that lock-free code is often *slower* than a mutex when nothing goes wrong.

## The mental model

The three guarantees answer one question at increasing strength: **if an arbitrary thread is suspended at an arbitrary point, what happens to everyone else?**

**Blocking.** A suspended thread can prevent others from making progress indefinitely. Any mutex-based design is blocking: suspend the lock holder and every waiter is stuck until it resumes. This is the opening scenario.

**Lock-free.** *Some* thread always makes progress, whatever happens to any individual thread. Suspend any thread you like and the system as a whole keeps moving. An individual thread might be delayed — possibly for a long time — but the system cannot stall.

**Wait-free.** *Every* thread completes its operation within a bounded number of its own steps, regardless of what other threads do. No retries, no dependence on anyone else's behaviour. This is the strongest guarantee and the hardest to achieve.

Three things follow that are worth stating flatly.

**None of these is a claim about speed.** They bound the worst case under preemption. They say nothing about throughput, and there is no implication that a stronger guarantee is faster.

**"Lock-free" is not "no mutex."** It is a property of the algorithm. You can write blocking code using only atomics — a spin lock is atomic, contains no mutex, and is blocking, because a thread suspended inside the critical section stalls everyone.

**Wait-free does not mean no waiting.** A wait-free `try_pop` on an empty queue returns immediately with nothing. The operation completed in bounded steps; there was simply nothing to return. What the consumer does next is [b5]'s question.

## Part 1 — Why blocking hurts here specifically

In most software, the opening scenario is a hiccup. Here it is the whole problem, for three reasons that compound.

**The stall is unbounded in principle and large in practice.** The waiting threads resume when the scheduler runs the lock holder again, and that interval is a property of the kernel, the load on the machine, and what else is runnable — none of which your code determines. A sub-microsecond critical section can produce a millisecond stall.

**It happens when the system is busiest.** Preemption is more likely when there is more to preempt for: more interrupts, more runnable threads, more work arriving. Which is precisely during a burst ([a3]). The failure mode is correlated with the moments that matter, exactly like every other tail problem in this book.

**It is invisible to a profiler.** The waiting threads are not consuming CPU — they are asleep. There is no hot function, no expensive instruction, no code to blame. A sampling profiler will report a system doing very little ([a4]). <!-- CALLBACK: a4 -->

Two named consequences worth recognising in production:

**Priority inversion** — a low-priority thread holds a lock a high-priority thread needs, so the high-priority thread waits on the low-priority one, which may itself be starved by medium-priority threads. The priority scheme achieves the opposite of its intent.

**Convoying** — a thread is preempted holding a lock, so waiters pile up; when it resumes and releases, they all wake at once, contend, and the burst propagates. A single stall becomes a pattern that outlasts its cause.

## Part 2 — Classifying real code

The definitions are easy to memorise and slightly harder to apply. Three examples that cover most of what you will meet.

```cpp
// code-b3-1 | ILLUSTRATIVE — a spin lock. Atomics only, and BLOCKING.
class SpinLock {
    std::atomic<bool> locked_{false};
public:
    void lock() {
        while (locked_.exchange(true, std::memory_order_acquire)) {
            while (locked_.load(std::memory_order_relaxed)) cpu_pause();
        }
    }
    void unlock() { locked_.store(false, std::memory_order_release); }
};
```

Not a mutex in sight, and it is blocking. Preempt a thread between `lock()` and `unlock()` and every other thread spins forever — worse than a mutex, in fact, because the spinners are burning cores that the descheduled holder needs in order to finish and release ([b5]).

```cpp
// code-b3-2 | ILLUSTRATIVE — a CAS retry loop. LOCK-FREE, not wait-free.
void add_to_total(std::atomic<uint64_t>& total, uint64_t amount) {
    uint64_t current = total.load(std::memory_order_relaxed);
    while (!total.compare_exchange_weak(current, current + amount,
                                        std::memory_order_release,
                                        std::memory_order_relaxed)) {
        // current was updated with the actual value; retry
    }
}
```

Lock-free: a failed exchange means some *other* thread succeeded, so the system advanced. Suspend any thread anywhere and the others keep going — there is no state in which everyone is stuck.

Not wait-free: a single unlucky thread can be beaten to the exchange repeatedly, with no bound on how many times. In practice it succeeds quickly; in principle it need never succeed, and "in principle" is what the guarantee is about.

```cpp
// code-b3-3 | ILLUSTRATIVE — the SPSC push from b2. WAIT-FREE.
bool try_push(const T& value) {
    const size_t head = head_.load(std::memory_order_relaxed);
    const size_t tail = tail_.load(std::memory_order_acquire);
    if (head - tail == Capacity) return false;
    slots_[head & kMask] = value;
    head_.store(head + 1, std::memory_order_release);
    return true;
}
```

No loops, no retries, no compare-exchange. A fixed number of steps every time, whatever the consumer is doing — including being descheduled indefinitely. That is wait-free, and it is a large part of why the SPSC queue is the structure of choice for the hottest handoff in the system. The restriction to one producer is what buys it: with a single writer per index there is nothing to lose a race to. <!-- CALLBACK: b2 -->

---

**Quiz 1**

Classify each, and say what happens if the thread executing it is suspended at the worst possible moment:

1. `std::mutex` guarding a shared counter.
2. A `fetch_add` on an atomic counter.
3. A spin lock guarding a shared map.
4. `try_push` on the SPSC ring buffer.

> **Answer**
>
> **1 — Blocking.** Suspend the holder and every other thread waits until it is rescheduled. The opening scenario.
>
> **2 — Wait-free.** `fetch_add` is a single hardware read-modify-write with no retry loop. It completes in a bounded number of steps regardless of contention. Under heavy contention it is *slow* — the line ping-pongs between cores ([a6]) — but slow and unbounded are different properties, and this is the distinction the chapter turns on.
>
> **3 — Blocking**, despite containing no mutex and nothing but atomics. Suspend a thread inside the critical section and everyone else spins indefinitely. Using atomics does not make an algorithm lock-free.
>
> **4 — Wait-free.** No loop, no retry. Suspend the consumer forever and the producer still completes every call — it will start returning `false` once the queue fills, which is a defined outcome in bounded steps, not a stall.
>
> The trap is number 3. "Lock-free" describes what happens when a thread stops, not which library types appear in the code. If there is a window in which one suspended thread blocks all others, the algorithm is blocking however it is implemented.

---

## Part 3 — Choosing, and the cost of the stronger guarantee

The tradeoff is not what people expect.

| | Blocking (mutex) | Lock-free | Wait-free |
|---|---|---|---|
| **If a thread is suspended** | Everyone waits | System progresses | Every thread progresses |
| **Typical uncontended cost** | Low | Low | Low |
| **Under contention** | Waiters sleep, one proceeds | Retries burn CPU | Bounded, but coherence cost remains |
| **Worst-case bound** | None | None for an individual thread | Yes |
| **Difficulty to write** | Low | High | Very high |
| **Difficulty to modify safely** | Low | High | Very high |
| **Composes with other operations** | Yes, with care | Poorly | Poorly |

Two rows deserve emphasis because they are where the folklore is wrong.

**A mutex is frequently faster than a lock-free structure when nothing goes wrong.** Modern mutex implementations stay in user space when uncontended, so acquiring one is close to the cost of the atomic operation the lock-free version also performs. Under contention, waiters sleep instead of burning CPU on retries — which can leave *more* throughput available to the thread doing useful work. If you benchmark a lock-free container against a mutex-protected one on a quiet machine, the mutex often wins, and this surprises people who expected the opposite.

That result is not evidence against lock-free design. It is evidence that you were measuring the wrong thing. The guarantee is about the case where a thread stops, and a benchmark on an unloaded machine has arranged for that not to happen.

**Composability is the underrated cost.** Two thread-safe lock-free operations do not compose into a thread-safe compound operation. "Check the queue is non-empty, then pop" is not atomic just because both halves are. With a mutex you take the lock across both. Lock-free, you need a different algorithm — and this is where lock-free designs quietly acquire their real complexity as requirements grow.

---

**Quiz 2**

A team replaces a mutex-protected queue with a lock-free one. They benchmark both on a quiet development machine and find the lock-free version is **12% slower**. They conclude the change was a mistake and revert it.

What did the benchmark measure, and what should they have measured instead?

> **Answer**
>
> **The benchmark measured the case the guarantee does not apply to.**
>
> On a quiet machine with no oversubscription, threads are rarely preempted, so the mutex is essentially never contended while held. Under those conditions it is doing about the same atomic work as the lock-free version with less bookkeeping — so it being 12% faster is entirely plausible and not an error.
>
> But the reason to choose lock-free was never the median. It was the case where a thread *is* preempted mid-operation, which the benchmark specifically arranged not to happen: quiet machine, no competing load, threads outnumbered by cores.
>
> **What to measure:** the tail, under realistic load. Run with the machine loaded, with more runnable threads than cores, and during simulated bursts — then compare p99.9 and maximum rather than mean throughput ([a3]). That is where the mutex version shows stalls the lock-free version does not have, and where the 12% buys something. <!-- CALLBACK: a3 -->
>
> **And a real possibility worth taking seriously:** if the path genuinely never experiences preemption under contention — a cold path, a well-isolated pinned thread with a dedicated core — then the team's conclusion may be right, and reverting to the simpler code is the correct engineering call. The mistake is not the revert. It is that the benchmark could not have distinguished the two situations.
>
> The general lesson: a benchmark that never triggers the scenario a design defends against will always favour the simpler design. Decide what you are protecting against, then construct the measurement that exercises it.

---

## Common mistakes

**Believing lock-free means fast.** It means the system cannot stall when a thread stops. Frequently slower in the common case.

**Believing atomics make code lock-free.** A spin lock is atomic and blocking. Quiz 1.

**Believing wait-free means never waiting.** It means bounded steps. A wait-free `try_pop` returning `false` is still wait-free.

**Reaching for lock-free on a cold path.** All the cost, none of the benefit, plus a structure the next engineer will be afraid to modify.

**Benchmarking on an idle machine and drawing conclusions about progress guarantees.** Quiz 2.

**Assuming lock-free operations compose.** They do not, and this is where lock-free designs go wrong as they grow.

**Using a spin lock because it "avoids the kernel."** It avoids the kernel and inherits every problem in the opening scenario, plus it burns cores the holder needs to finish ([b5]).

## Going deeper elsewhere

*Optional. Not required for a typical interview answer, but it explains why real lock-free containers are far more complicated than textbook ones.*

Every lock-free structure in this book has a fixed-size preallocated buffer, and that is not a coincidence — it sidesteps the hardest problem in the field. **Safe memory reclamation** is the question of how a lock-free structure can free a node when another thread might still be about to read it. There is no lock to tell you nobody is looking.

The standard solutions — **hazard pointers**, **epoch-based reclamation**, and **RCU** — each let threads announce what they might be accessing so memory is freed only when it is provably unreachable. This is the bulk of the complexity in production lock-free containers, and it is why a lock-free linked list is a genuinely hard piece of engineering while a lock-free ring buffer over preallocated slots is not.

You will rarely be asked to implement one, and preallocation ([c2]) means trading systems often avoid needing them at all. But knowing the problem exists explains a great deal about why lock-free code in the wild looks the way it does. **Herlihy and Shavit, *The Art of Multiprocessor Programming*** (2nd ed.) covers all three approaches alongside the algorithms that need them.

## Operational behaviour

- **Unexplained latency spikes with an idle-looking profiler** are the signature of a preempted lock holder. Worth having near the top of the list, because nothing points at it directly.
- **Track how long threads spend waiting**, not just how long operations take. A lock that is never contended and a lock that is contended for 3ms once an hour look identical in an average.
- **Document the guarantee next to the structure.** "This queue is wait-free for the producer" is information the next engineer needs before adding a retry loop that quietly downgrades it.
- **Watch for thread count exceeding core count.** Every guarantee in this chapter is about preemption, and oversubscription is what makes preemption routine ([c4]).

## When a mutex is the right answer

- **The path is not on the critical path.** Config reload, session setup, admin interfaces ([a1]).
- **The critical section is complex or has several invariants.** Lock-free correctness arguments do not compose, and a subtly wrong lock-free structure is far more dangerous than a correct locked one.
- **The threads involved are pinned to dedicated cores and not oversubscribed**, so preemption while holding the lock is genuinely rare. Quiz 2's caveat.
- **You cannot state what the lock-free version protects against.** If you cannot name the scenario, you are paying the complexity for nothing.

## Interview mapping

- **Define the guarantees in terms of a suspended thread**, not in terms of locks or atomics. This is the definition that generalises and the one that shows understanding.
- **Say lock-free is not a speed claim**, unprompted. The single highest-signal statement here.
- **Classify a spin lock as blocking** if given one. It is the standard trap.
- **Explain why a CAS loop is lock-free but not wait-free**, and note that the distinction is about the bound, not about observed behaviour.
- **Point out that the SPSC queue is wait-free** and that the single-writer property is what buys it. It ties [b2] to this chapter and shows you understand why the restriction is valuable.
- **Argue for a mutex** where one is appropriate. Candidates who treat lock-free as always-better reveal they have read about it rather than maintained it.

## Summary

Progress guarantees answer one question: if a thread is suspended at the worst possible moment, what happens to everyone else? Blocking means everyone waits. Lock-free means the system keeps moving even if an individual thread does not. Wait-free means every thread finishes in a bounded number of its own steps.

None of that is a claim about speed, and a mutex will frequently beat a lock-free structure in a benchmark on a quiet machine — because such a benchmark has carefully arranged for the scenario the guarantee defends against never to occur. What lock-free buys is the removal of a dependency on the scheduler, and the scheduler is the thing that stalls a sub-microsecond critical section for a millisecond during a burst.

The property is of the algorithm, not the library types: a spin lock built entirely from atomics is blocking. And the guarantee is not free — lock-free code is harder to write, much harder to change safely, and does not compose, which is why the right question is not "can this be lock-free" but "what am I protecting against, and does this path need it?"

For the hottest handoff in the system, the answer is yes, and [b2]'s single-writer restriction is what makes the strongest guarantee available cheaply. [b4] is what happens when you give that restriction up.

**Related:** [b1] memory model · [b2] SPSC ring buffers · [b4] MPSC and contention · [b5] waiting strategies · [b7] testing concurrent code · [a3] latency and tail latency · [a4] measurement · [a6] coherence · [c4] thread affinity · [c2] preallocation

## References

- Herlihy, M., & Shavit, N. (2020). *The art of multiprocessor programming* (2nd ed.). Morgan Kaufmann. [progress conditions, and the reclamation problem]
- Williams, A. (2019). *C++ concurrency in action* (2nd ed.). Manning. [lock-free design in C++, with the practical caveats]
