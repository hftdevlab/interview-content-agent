<!--
chapter: b7-testing-concurrent-code
state: draft_created
contract: standards/chapter-contract.md
include_measurement_plan: false | include_quizzes: true | primary_artifact_mode: code
note: final chapter of Module B — carries the module review per contract 3.15
unresolved_markers: 0
-->

# The Bug That Passes Every Test

## Testing Concurrent and Lock-Free Code

**Prerequisites:** [b2] SPSC ring buffers · [b1] C++ memory-model foundations · [a4] Measurement and profiling
**Focus:** a passing concurrency test is weak evidence — the discipline is building tests that *can* fail, then knowing exactly what a pass establishes

---

## Fifty million iterations of nothing

A team ships a lock-free queue. It is backed by a serious-looking test: two threads, fifty million items pushed through, every one verified to arrive exactly once and in order. It runs in CI on every commit. It has never failed — not on a developer laptop, not on the build machines, not once in four months.

Then a production process on a newly provisioned host class starts dropping a message. Roughly once a week. Never reproducible on demand.

The test still passes. It passes on the new host class too.

The problem is not that the test is bad in any obvious way. It checks the right invariants and it runs a lot of iterations. The problem is what a passing run of it actually establishes, which is far less than the team believed — and running it longer would not have helped, because the interleaving it needs to produce is one this particular combination of compiler, architecture, and load will almost never generate.

## Where you will actually meet this

Every hand-rolled concurrent structure in a trading system needs this discipline: the queues from [b2] and [b4], any shared state touched by more than one thread, anything where someone chose atomics over a mutex.

The stakes are specific. A concurrency bug in a trading system does not usually crash — it drops a message, or processes one twice, or leaves a position figure slightly wrong. It surfaces as a reconciliation break weeks later, and by then the evidence is gone.

In interviews this comes up as a follow-up rather than a headline: you describe a lock-free queue, and the interviewer asks how you would know it is correct. The weak answer is "stress test it." The strong answer explains why that is weak evidence and what would strengthen it.

## The mental model

A concurrent program does not have one execution. It has an enormous space of possible **interleavings** — orderings of operations across threads, plus the reorderings the compiler and hardware are permitted to perform ([b1]).

Your test does not sample that space. It samples whatever the scheduler and the hardware happened to produce, which is a small, **biased** subset of it. Two biases in particular matter:

**The architecture excludes interleavings.** x86 will not reorder stores with other stores. So a bug that requires that reordering *cannot occur* on x86, no matter how long you run. It is not rare — it is impossible. The same binary logic on ARM produces it readily.

**The scheduler excludes interleavings.** With two threads pinned to two idle cores, preemption mid-operation is rare. Bugs that need a thread to be suspended between two specific instructions — like [b4]'s claim-then-write window — need preemption at exactly that point, and your test has arranged for preemption to be uncommon.

So: **a passing test tells you the executions it happened to produce were correct.** It says nothing about executions it did not produce, and the ones it did not produce are systematically the interesting ones.

That reframes the goal. You are not trying to run more iterations. You are trying to **run different ones** — to construct the conditions under which the bad interleavings become likely rather than impossible.

## Part 1 — Test the sequential logic first, without threads

Before any of the concurrency machinery, an observation that saves a great deal of trouble: **a large share of bugs in these structures are not concurrency bugs at all.**

Index arithmetic. Wraparound at the counter boundary. The full and empty conditions. Off-by-one at capacity. The [d3]-style question of what happens at a boundary. None of these need two threads to be wrong, and none of them need two threads to be found — but a stress test finds them only by luck, and reports them as mysterious concurrency failures when it does.

So test them deterministically, exhaustively, single-threaded:

```cpp
// code-b7-1 | RUNNABLE | C++20 | examples/, target: queue_tests
// No threads. Deterministic. Runs in milliseconds.

TEST(SpscRing, FillsExactlyToCapacity) {
    SpscRing<int, 4> q;
    for (int i = 0; i < 4; ++i) EXPECT_TRUE(q.try_push(i));
    EXPECT_FALSE(q.try_push(99));           // full: rejects, does not overwrite
}

TEST(SpscRing, EmptyAfterDraining) {
    SpscRing<int, 4> q;  int out;
    EXPECT_FALSE(q.try_pop(out));           // empty from the start
    q.try_push(1);
    EXPECT_TRUE(q.try_pop(out));  EXPECT_EQ(out, 1);
    EXPECT_FALSE(q.try_pop(out));           // empty again, not "one stale item"
}

TEST(SpscRing, SurvivesIndexWraparound) {
    SpscRing<int, 4> q;  int out;
    // Push and pop far more than capacity to cross the mask boundary repeatedly.
    for (int i = 0; i < 10'000; ++i) {
        EXPECT_TRUE(q.try_push(i));
        EXPECT_TRUE(q.try_pop(out));
        EXPECT_EQ(out, i);                  // never a stale value from a prior lap
    }
}
```

Fast, deterministic, and they fail the same way every time. Every boundary condition you can express this way is one fewer thing the stress test has to find by chance.

## Part 2 — Making the stress test able to fail

Now the part that needs threads. The goal is to widen the set of interleavings you actually produce.

**Oversubscribe.** Run with more threads than cores. This is the single highest-value change, because it makes preemption mid-operation *routine* rather than rare — and preemption at an awkward point is exactly what [b3]'s guarantees are about and what [b4]'s claim-then-write bug needs. Two pinned threads on an idle machine is the configuration least likely to find anything.

**Inject delays at the dangerous points.** If you know where the window is, widen it. A test-only hook that pauses between claiming a slot and writing it turns a few-nanosecond window into a few microseconds, and a bug that needed a one-in-a-billion alignment now fires immediately.

```cpp
// code-b7-2 | ILLUSTRATIVE — test-only hook, compiled out of production builds
#ifdef CONCURRENCY_TEST_HOOKS
    #define TEST_YIELD_POINT(name) test_hooks::maybe_delay(name)
#else
    #define TEST_YIELD_POINT(name) ((void)0)
#endif

bool try_push(const T& value) {
    const size_t pos = claim_slot();
    TEST_YIELD_POINT("after_claim");     // widen the claim-to-write window
    slots_[pos & kMask] = value;
    publish(pos);
    return true;
}
```

**Check invariants, not absence of crashes.** "It did not crash" is nearly no information. Assert the properties the structure claims: every item arrives exactly once, per-producer order is preserved, the total count matches, no value appears that was never pushed. Writing a distinctive poison value into slots on free — so a premature read yields something obviously wrong rather than a plausible stale message — turns a silent corruption into a loud failure.

**Vary the shape of the load.** Bursts, then quiet. A fast producer with a slow consumer, so the queue runs full. The reverse, so it runs empty. Most designs have different code paths at the boundaries, and a steady-state test never visits them.

**Run on weakly ordered hardware.** This is evidence x86 cannot give you at any duration. An ARM host in CI will produce store-store reorderings that x86 forbids, which is precisely the class of bug [b1] warns about. If your production hardware is x86 only, this still matters: it catches ordering bugs that are currently latent and will surface the day a compiler upgrade reorders something the hardware would not have.

---

**Quiz 1**

Your two-thread stress test has pushed fifty million items through a lock-free queue on an x86 build machine, verifying order and completeness, with no failure in four months of CI runs.

State precisely what that establishes — and what it does not.

> **Answer**
>
> **What it establishes:** that *this* binary, built with *these* compiler flags, running on *this* architecture, under the interleavings that *this* machine's scheduler happened to produce, did not violate the checked invariants in those runs.
>
> That is genuinely worth something. It rules out gross logic errors, most index arithmetic bugs, and anything that fails on common interleavings.
>
> **What it does not establish:**
>
> - **Anything about other architectures.** If the code has a missing `release`, x86's store ordering hides it. The bug is not rare on x86 — it is unreachable. ARM will produce it.
> - **Anything about other builds.** Reordering is something the compiler is *permitted* to do, not obliged to. A flag change, an inlining decision, or a toolchain upgrade can start it.
> - **Anything about interleavings requiring preemption at a specific point.** Two pinned threads on an idle machine are preempted mid-operation rarely, so windows of a few instructions are essentially never hit.
> - **Anything at the boundaries the test never reached.** If the queue never ran full or empty during the test, those paths are untested regardless of iteration count.
>
> **And the trap:** running it for five hundred million iterations instead of fifty million changes none of the above. More samples from a biased distribution do not reach the parts of the space that distribution excludes. Duration is the wrong dial — **variety is the right one**: oversubscribe, inject delays, vary the load shape, and run on weakly ordered hardware.

---

## Part 3 — Tools, and their actual limits

**ThreadSanitizer** is the most useful tool here, and it is worth being precise about what it does. It instruments memory accesses and tracks the happens-before relation at runtime, reporting when two threads access the same location without synchronisation and at least one writes — that is, a **data race** in [b1]'s sense.

It is very good at that. It will catch the opening scenario from [b1]: a payload written without a release store and read after a relaxed load is a data race on the payload, and TSan will say so.

What it cannot do:

- **It only sees executed paths.** It is a runtime detector, not a proof. A race on a path your test never takes is invisible to it.
- **It does not verify that your orderings are strong enough for your invariants.** If every access is atomic, there is no data race to detect — but the code can still be wrong. [b1]'s store-buffering example, where both threads read zero, involves no data race at all. So a design whose bug is "I used `relaxed` where I needed `seq_cst` for multi-object ordering" can be TSan-clean and broken.
- **It changes timing substantially.** Instrumented code runs much slower, which alters which interleavings occur — sometimes exposing bugs, sometimes hiding them.

The honest summary: **TSan finds missing synchronisation, not insufficient ordering.** Both are real bug classes, and it addresses one of them. Run it, and do not treat a clean report as a correctness argument.

Two things worth pairing with it. **Run the stress test under TSan in CI**, accepting the slowdown, because the combination of many interleavings and race detection is stronger than either alone. And **treat any flaky concurrency test as a real bug** — never as something to retry until green. A test that fails once in fifty runs has found something, and rerunning it discards the only evidence you will get.

---

**Quiz 2**

Recall the [b4] MPSC bug: a producer claims a slot with `fetch_add`, is descheduled before writing it, and a second producer claims and completes the next slot — so the consumer sees an advanced index and reads a slot that was never written.

Your current test is two producers and one consumer, pinned, on an otherwise idle machine, checking that every pushed value arrives exactly once. It passes.

What three changes would make this test capable of catching that bug?

> **Answer**
>
> **1 — Oversubscribe and unpin.** The bug requires a producer to be descheduled *between* the claim and the write, a window of a few instructions. With two pinned producers on idle cores that essentially never happens. Run eight producers on two cores and preemption mid-operation becomes ordinary rather than exceptional. This alone may be enough.
>
> **2 — Inject a delay after the claim.** A test-only hook between claiming and writing turns a few-nanosecond window into microseconds. If the bug exists, it fires almost immediately rather than once in a billion operations. This is the change that converts a probabilistic test into a near-deterministic one, and it is only possible because you know where the window is — which is an argument for writing tests alongside the design rather than afterwards.
>
> **3 — Poison the slots, and check for the poison.** The bug's symptom is reading a slot that was never written — which currently contains a *plausible* stale value from an earlier lap, so "every pushed value arrives exactly once" may not even notice: the consumer receives a real value, just the wrong one, and the count still balances. Write a distinctive sentinel into each slot when it is freed, and assert the consumer never sees it. That turns a silent wrong-value bug into an immediate, obvious failure.
>
> **The trap is number 3**, and it is the important one. The first two changes make the bad interleaving *occur*; the third makes it **observable**. A test that produces the bug but cannot detect its symptom still passes — and "every value arrives exactly once" is exactly the kind of invariant that sounds complete and quietly is not.
>
> The general lesson: making a test able to fail has two halves. Reach the state, and detect it. Most effort goes into the first, and the second is where tests silently under-deliver.

---

## Common mistakes

**Running longer instead of differently.** Quiz 1. Duration does not reach interleavings the configuration excludes.

**Testing only on x86.** An entire class of ordering bug is unreachable there.

**Treating a clean TSan report as proof.** It finds data races on executed paths, not insufficient ordering among atomics.

**Testing only the steady state.** Full and empty are different code paths and are where the boundary bugs live.

**Checking for crashes instead of invariants.** Most concurrency bugs in these structures produce wrong values, not faults.

**Retrying a flaky test until it passes.** It found something. Rerunning destroys the evidence.

**Skipping the single-threaded tests.** Wraparound and capacity bugs are cheap to test deterministically and expensive to find by chance.

**Writing the test after the design.** The delay-injection hooks in Quiz 2 require knowing where the windows are, which is knowledge you have while designing and lose afterwards.

## Going deeper elsewhere

*Optional. Not required for an interview answer, and useful to know exists.*

Everything in this chapter is sampling — running executions and hoping to hit the bad ones. There is a different approach that does not sample: **model checking** tools systematically enumerate the interleavings and permitted reorderings of a small concurrent program, including those the hardware you own would never produce, and report whether any of them violates your assertions. For a structure with a handful of operations, that turns "we did not find a bug" into something much closer to "there is no bug, under this model."

The limitation is size — exhaustive exploration is only tractable for small programs and short executions — which happens to fit the primitives in this module rather well, since an SPSC or MPSC queue exercised for a few operations is exactly the right scale.

You are unlikely to be asked about this, and knowing it exists is a genuine plus, particularly if you are the person who owns a hand-rolled queue. **Sorin, Hill, and Wood, *A Primer on Memory Consistency and Cache Coherence*** covers the underlying models these tools check against; the research literature on stateless model checking for relaxed memory is where the tools themselves are described.

## Operational behaviour

- **Run the concurrency suite under oversubscription in CI**, not on a quiet dedicated runner. The quiet runner is the configuration least likely to find anything.
- **Keep a weakly ordered target in the CI matrix** if you can, even when production is x86 only. It catches latent ordering bugs before a compiler upgrade activates them.
- **Never quarantine a flaky concurrency test.** Escalate it. The failure rate is a measurement of how close to the surface the bug is.
- **Record the environment on failure** — host, core count, load, build flags, architecture. A concurrency failure without its environment is very hard to reproduce and the environment is the main clue.
- **Keep the test hooks in the code**, compiled out by default. Removing them means the next person to investigate has to rediscover where the windows are.

## When not to build all this

- **When a mutex would have done.** The whole apparatus here is the ongoing cost of a lock-free structure, and it should be counted when the structure is chosen ([b3]). A mutex-protected queue on a cold path needs none of it.
- **When you can use an existing, well-tested implementation.** Hand-rolling is justified by a requirement, not by preference, and someone else's queue comes with someone else's test suite.
- **When the structure is not on the critical path.** Correct and simple beats fast and load-bearing everywhere it can ([a1]).

## Interview mapping

- **Say a passing stress test is weak evidence**, and explain the sampling argument. This is the whole chapter in one move.
- **Name the architecture point specifically** — that x86 makes certain bugs unreachable rather than rare. It is concrete and most candidates do not have it.
- **State what TSan does and does not establish.** Data races on executed paths; not ordering sufficiency.
- **Propose variety over duration**: oversubscription, delay injection, load shape, weak-memory hardware.
- **Mention testing the sequential logic separately.** It shows you know where the bugs actually are.
- **Say you would treat a flaky test as a real bug.** Simple, and it says a lot about how you work.

## Summary

A concurrency test samples a space of interleavings, and it samples it with a bias you did not choose. The architecture forbids some reorderings entirely, and an idle machine with pinned threads makes mid-operation preemption rare — so a passing run establishes that the executions your configuration happens to produce are correct, and nothing about the ones it structurally excludes.

Which means duration is the wrong dial. The productive moves are all about variety: oversubscribe so preemption is routine, inject delays where you know the windows are, vary the load so full and empty are actually visited, and run somewhere weakly ordered where the reorderings x86 forbids can occur. Before any of that, test the sequential logic — wraparound, capacity, boundaries — deterministically and without threads, because that is where a surprising share of the bugs are and none of them need an interleaving to find.

And making a test able to fail has two halves that get unequal attention: reaching the bad state, and being able to *see* it. An invariant like "every value arrives exactly once" can be satisfied by a queue handing out plausible wrong values. Poison the slots.

Tools help within their limits. ThreadSanitizer finds missing synchronisation on paths that execute, which is a real and common bug class, and it does not tell you whether your orderings are strong enough to preserve your invariants. A clean report is a useful signal and not a correctness argument.

The honest conclusion is uncomfortable and worth carrying: **you cannot test your way to confidence in a lock-free structure.** You get there by deriving the correctness argument ([b1]), keeping the structure small enough to hold in your head ([b2]), testing aggressively to catch the mistakes in that argument, and choosing a mutex whenever the requirement does not genuinely demand otherwise ([b3]).

---

# Module B in review

*You have now built the thread-to-thread machinery a trading system runs on. This section is a consolidation rather than new material — read it now, and again before an interview.*

## The arc

**[b0] Threads, atomics, and locks.** An increment is three operations, so shared counters lose updates. A mutex makes an arbitrary block indivisible; an atomic makes one location indivisible. The fact that decides between them, and that recurs everywhere afterwards: **atomicity does not compose.**

**[b5] Waiting strategies.** When a consumer finds nothing, blocking costs wake-up latency and spinning costs a whole core, permanently. The choice is a machine-level core budget decision, and spinning without a dedicated core is not a smaller improvement but a reversal.

**[b1] The memory model.** Dropping the mutex on the hot path removes a scheduler dependency and transfers an obligation the mutex was quietly discharging: **visibility**. Release publishes, acquire observes, and chaining them with program order gives happens-before. Derive the orderings from what must be visible; never pick them from a list.

**[b2] SPSC ring buffers.** Two release-acquire pairs pointing in opposite directions, monotonic counters, and the indices on separate cache lines. The single-writer property is what makes it cheap — no read-modify-write is needed, because there is no race to lose.

**[b3] Progress guarantees.** Blocking, lock-free, and wait-free describe what happens to *other* threads when one is suspended. They are not speed claims, and a mutex often wins a benchmark on a quiet machine — because such a benchmark arranged for the scenario the guarantee defends against never to occur.

**[b4] MPSC and contention.** Adding a producer destroys the single-writer property. Claims and writes come apart, so readiness has to live in the slot rather than in the shared index. The remaining cost grows with producer count, and the alternative — private queues per producer — removes it while destroying any global order across producers.

**[b6] Hot-path dispatch.** A virtual call costs loads, an indirect branch, and lost inlining, in ascending order of importance. Group by type and filter the subscriber list before redesigning anything.

**[b7] Testing.** A passing test samples a biased subset of the interleaving space. Vary the conditions, not the duration.

## The recurring ideas

Five things this module says repeatedly in different costumes. If you carry nothing else forward, carry these.

**1. Atomicity does not compose.** Two atomic operations are not an atomic operation ([b0]). Two lock-free operations are not a lock-free compound operation ([b3]). A claim and a write are two things ([b4]). Every time you want a compound guarantee, you need a mechanism that provides it directly.

**2. Single-writer is the property that buys everything.** It makes [b2] wait-free and cheap; losing it in [b4] costs correctness machinery and contention that scales with producers. When designing a handoff, the first question is whether you can arrange for exactly one writer.

**3. Guarantees are about the worst case; benchmarks measure the average.** The mutex that wins on a quiet machine ([b3]), the median that hides the tail ([a3]), the stress test that never preempts ([b7]) — all the same error. Decide what you are protecting against, then construct the measurement that exercises it.

**4. Derive, then choose.** Orderings come from a visibility requirement ([b1]). Structures come from an ordering requirement ([b4]). Dispatch mechanisms come from whether the type set is open ([b6]). Reaching for the strongest or fastest-sounding option without a derivation is how you get code nobody can safely change.

**5. The cheapest fix is usually structural.** Do not share the data ([b0]). Give each producer its own queue ([b4]). Do not make the call ([b6]). Use a mutex ([b3]). The mechanism-swapping options are the visible ones and rarely the best ones.

## Choosing a handoff

| Situation | Use |
|---|---|
| One producer, one consumer, hot path | SPSC ring buffer ([b2]) |
| Several producers, order across them matters | MPSC with per-slot readiness ([b4]) |
| Several producers, order across them does not matter | One SPSC queue per producer ([b4]) |
| Shared counter, nothing depends on it | Relaxed atomic, or per-thread and summed ([b0]) |
| Invariant across several variables | Mutex, or redesign so it is one variable ([b0]) |
| Cold path, anything | Mutex and a standard container ([b3]) |

## Check yourself

If you can answer these without looking, the module has landed.

1. Why does `count = count + 1` lose updates when `count` is `std::atomic<int>`?
2. What does a mutex guarantee besides mutual exclusion — and who provides it when you remove the mutex?
3. Derive the four orderings in `try_push` and `try_pop`, and say what breaks if each is weakened.
4. Why does an SPSC queue need no compare-exchange?
5. Why is `alignas(64)` on the indices not optional, and why would the same treatment be wrong on an order table?
6. Is a spin lock lock-free? Why not?
7. Why can't you make an MPSC queue by changing the producer's store to `fetch_add`?
8. When is one shared queue *required* rather than merely convenient?
9. What does spinning cost, and what precondition makes it worth paying?
10. Your stress test has passed fifty million iterations. What have you established?

## What comes next

Module B assumed the machine underneath was uniform and cooperative. It is neither.

**Module C** takes that assumption apart: memory does not appear when you ask for it ([c1], [c2], [c3]), threads run where the scheduler decides unless you say otherwise ([c4]), and on a multi-socket host memory has a physical home that determines what your accesses cost ([c5]). Several problems this module treated as fixed costs turn out to be placement decisions.

**Related:** [b0] threads, atomics, and locks · [b1] memory model · [b2] SPSC ring buffers · [b3] progress guarantees · [b4] MPSC and contention · [b5] waiting strategies · [b6] hot-path dispatch · [a1] system anatomy · [a4] measurement · [d3] gap recovery · [e4] deterministic replay

## References

- Williams, A. (2019). *C++ concurrency in action* (2nd ed.). Manning. [testing concurrent code, and the design practices that make it testable]
- Herlihy, M., & Shavit, N. (2020). *The art of multiprocessor programming* (2nd ed.). Morgan Kaufmann. [correctness conditions and what they require of a test]
- Sorin, D. J., Hill, M. D., & Wood, D. A. (2011). *A primer on memory consistency and cache coherence*. Morgan & Claypool. [the memory models that model checkers verify against]
