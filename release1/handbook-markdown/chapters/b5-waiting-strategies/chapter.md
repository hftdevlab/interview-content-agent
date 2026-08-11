<!--
chapter: b5-waiting-strategies
state: draft_created
run: C0-11 cold test — drafted from brief.yaml + standards/chapter-contract.md + prompts/draft.md
include_measurement_plan: true | include_quizzes: true | primary_artifact_mode: pseudocode
unresolved_markers: 0
-->

# Waiting for the Market to Move

## Busy Spinning, Blocking, and Hybrid Waiting

**Prerequisites:** [b0] Threads, atomics, and locks · [a4] Measurement and profiling
**Focus:** the choice between spinning and blocking is a whole-machine core budget decision, not a local optimisation

---

## Nothing to do, and everything depends on it

A strategy thread at a market-making firm waits for updates from the feed handler. They share a queue: the handler pushes normalised messages, the strategy pops them and decides whether to requote. (How that queue is built is [b2]'s subject — here it is simply a box the strategy takes messages out of.)

On a quiet Tuesday afternoon in an illiquid name, the queue is empty most of the time. The strategy might wait several milliseconds between messages. Two seconds after the CPI print, it will not wait at all — the queue is never empty and the thread never catches up.

The engineer has to write one line of code that covers both: **what does the thread do when `try_pop` returns false?**

Two answers are obvious. Sleep, and let the operating system wake you when there is work. Or check again, immediately, forever.

They differ by orders of magnitude in how fast the thread reacts to the first message after a quiet period — and they differ just as dramatically in how much of the machine they consume doing nothing. Pick the wrong one and you either add latency to every quiet-period wake, or you burn a core the rest of the system needed.

## Where you will actually meet this

This is the consumer side of every hot-path queue in a trading system, which means you will write it more often than almost anything else in this handbook:

- **Strategy polling the feed handler.** The scenario above. The first message after a lull is often the one that matters — it is the market moving.
- **Order gateway polling the strategy.** Same shape, and here the wake-up latency is directly in tick-to-trade.
- **Kernel-bypass receive loops.** These are busy-poll *by construction* ([d6]). A user-space stack has no kernel to wake it, so the loop that reads the NIC ring is a spin loop by definition, and the core it occupies is not negotiable.

It is also a reliable interview question at latency-sensitive firms, because it separates candidates cleanly. The weak answer is "spin, because it's faster." The strong answer starts by asking how many cores are available.

## The mental model

A thread with nothing to do has exactly two options, and they trade the same two currencies in opposite directions.

**Blocking** parks the thread. It tells the operating system "wake me when this condition changes," and the scheduler takes the core away and gives it to someone else. When work arrives, the producer signals, the kernel marks the thread runnable, the scheduler eventually places it on a core, and it resumes. Every step of that costs time.

**Spinning** keeps the thread running. It checks the queue, finds it empty, and checks again. The core is never given up, so when work arrives the thread notices on its very next iteration — no kernel, no scheduler, no context switch. It sees the message roughly as fast as the coherence protocol can deliver the producer's write to it.

So the trade:

> **Blocking costs latency and saves cores. Spinning costs a core and saves latency.**

The critical word is *core*, singular and literal. A spinning thread does not use "some CPU." It uses one core, completely, permanently, at 100%, whether messages arrive every microsecond or once an hour. That is what you are buying with, and it is why this is not a local decision. You cannot make it by looking at the consumer loop. You have to know how many cores the machine has and what else needs them — which makes it a **budget** question about the whole system.

## Part 1 — What blocking actually costs

The reason blocking is slow is not that the kernel is inefficient. It is that waking a thread is a distributed operation across the machine.

The producer signals. The kernel marks the waiter runnable. The scheduler must then decide where to run it — and if the target core is busy, the waiter waits longer still. The thread's data has meanwhile left cache: after even a short sleep, the caches on the core it lands on are cold for its working set, so its first pass through the hot loop is slower than its steady-state pass ([a5]). <!-- CALLBACK: a5 -->

That last part is easy to miss. The wake-up cost is not just the scheduler latency; it is the scheduler latency *plus* a cold-cache first iteration, on the specific message you most wanted to handle quickly — the first one after a quiet period, which in market data is disproportionately likely to be the market moving.

A second-order effect matters for the tail: the wake-up cost is not constant. It depends on what the scheduler is doing, whether the target core is idle, and how deep a power state the core has entered. So blocking does not add a fixed latency; it adds a *variable* one. That is a tail-latency problem, and tail is the product ([a3]). <!-- CALLBACK: a3 -->

**How large is the gap?** Large enough that it dominates the handoff, which is the entire reason this chapter exists. This handbook does not have representative hardware to measure it on and will not print a figure it cannot stand behind — the numbers depend on kernel version, scheduler configuration, power management, and core topology, and a wrong figure is worse than none. Measure it on your target machine; the *Optional* section shows how. In an interview, "spinning avoids the scheduler entirely, so it's faster by roughly the cost of a wake-up, which I'd measure on the target" is a stronger answer than a memorised number.

## Part 2 — What spinning actually costs, and when it inverts

Spinning looks free when you have a spare core. It is not free, and two things make it worse than it looks.

**A naive spin loop is hostile to its own hardware.** A tight loop hammering a shared variable generates coherence traffic and saturates the core's execution resources. If the core has a sibling hyperthread, the spinner is competing with it for those resources — and that sibling might be a thread doing real work. A `pause` hint (the platform's spin-wait instruction) tells the CPU this is a spin loop, which reduces the resource pressure on the sibling and lowers the cost of exiting the loop. **A spin loop without one is a bug**, not a missing optimisation.

**And then the failure mode that actually hurts.** Everything above assumes the spinning thread has a core to itself. Remove that assumption and spinning does not degrade gracefully — it inverts.

If there are more runnable threads than cores, the scheduler time-slices them. A spinning thread now occupies its slice doing nothing useful, and — worse — it may be spinning on a condition that only another *descheduled* thread can satisfy. It burns a full quantum waiting for a thread that cannot run because the spinner is holding the core. Latency does not get slightly worse. It gets catastrophically worse, and it gets worse specifically under load, which is when you least want it.

This is why "spinning is faster" is the wrong shape of belief. Spinning is faster **on a dedicated core**, and it is much slower without one. The precondition is doing all the work.

---

**Quiz 1**

A host has 8 physical cores. An engineer, having read that spinning reduces latency, converts 12 worker threads from condition variables to busy-wait loops. There is no pinning; the scheduler places threads freely.

What happens to latency, and why is the direction of the change surprising?

> **Answer**
>
> **It gets much worse, not slightly worse.**
>
> Twelve runnable threads on eight cores means the scheduler must time-slice. Every one of those threads is now permanently runnable — a spinning thread never sleeps, so it never voluntarily yields its core. The scheduler is forced to preempt threads that have real work in order to run threads that are doing nothing.
>
> Worse, a spinner waiting for data from another thread may be occupying the very core that other thread needs to produce it. The spinner burns its entire quantum waiting for a producer that cannot run. Under the old condition-variable design, an idle thread cost nothing and the producer ran immediately.
>
> The lesson: spinning is not a property of the loop, it is a property of the loop **plus a dedicated core**. Without the second half, the change is not a smaller improvement — it is a reversal. And it shows up worst under load, which is when the system is least able to absorb it.

---

## Part 3 — Hybrid waiting

Most real systems are neither uniformly busy nor uniformly quiet, which suggests the obvious compromise: **spin for a bounded period, then block.**

If the message arrives within the spin budget — the common case during active trading — you got spin latency. If it does not, you block and give the core back, so a quiet afternoon does not cost a permanently pinned core.

```
wait_for_message():

    deadline = now() + spin_budget

    while now() < deadline:
        if queue.try_pop(msg):
            return msg                  // fast path, no kernel involved
        cpu_pause()                     // spin-wait hint

    // Spin budget exhausted. Give the core back.
    register_as_waiter()                // publish intent to block

    if queue.try_pop(msg):              // re-check AFTER registering
        deregister_as_waiter()
        return msg                      // work arrived during the transition

    block_until_signalled()             // now safe to sleep
    return queue.try_pop(msg)
```

**The re-check after registering is not optional**, and the order of the three steps is load-bearing:

1. **Register as a waiter** — publish the intent to block, before checking anything.
2. **Re-check the queue** — work may have arrived during the spin-to-block transition.
3. **Sleep** — only now, having found the queue genuinely empty *while registered*.

Check before registering and there is a window in which the producer can push and signal with no waiter registered. The consumer then sleeps on a queue that already holds data, and stays asleep until the *next* message — which on a quiet channel could be a very long time. Note what is and is not broken: the queue is entirely correct throughout. Only the waiter is stuck, which is why this bug survives a passing queue test suite.

It is also timing-dependent, so it will not show up reliably in testing. You will not find this one by running the code; you find it by getting the order right on purpose.

### Choosing the spin budget

The budget is not a tuning constant to be picked by feel. It follows from a distribution you can measure: **how long are the gaps between your messages?**

Spinning pays when the message arrives before the budget expires. So the question is what fraction of your inter-arrival gaps fall under a candidate budget. If 90% of gaps are shorter than some duration, a budget around there captures most of the benefit; extending it further buys the remaining 10% at the cost of burning the core through every long gap.

The shape of the distribution matters more than its average. Market-data inter-arrival times are heavily bimodal — dense bursts separated by long quiet periods — and an average sits in the empty middle, describing neither mode. Budget from the distribution, not the mean.

Which means the spin budget is a property of the *channel*. A busy index feed and a sleepy single-name feed should not share one.

---

**Quiz 2**

A hybrid waiter is configured with some spin budget. A message arrives a fraction of a microsecond *after* the budget expires and the thread has just committed to blocking.

What latency does that message experience, and what does that tell you about how the budget should be tuned?

> **Answer**
>
> **It gets the full blocking cost — spin latency plus wake-up latency, and nothing saved.** The thread paid to spin for the entire budget and then paid the wake-up anyway. This is the worst case in the design, and it is strictly worse than pure blocking would have been for that message.
>
> That does not make hybrid waiting a bad design. It means the budget must be chosen so this case is **rare**, which is a statement about the inter-arrival distribution, not about the code. If most gaps are far shorter than the budget, the worst case happens seldom and the average is excellent. If your gaps cluster right around the budget, you have picked the worst possible value: you pay the spin almost every time and frequently pay the wake-up too.
>
> The general lesson: a hybrid strategy tuned against the mean can land exactly in the danger zone. Tune against the shape — pick a budget that sits well clear of the bulk of the distribution, on the side where the spin usually succeeds.

---

## Comparing the three

| | Blocking | Spinning | Hybrid |
|---|---|---|---|
| **Wake-up latency** | Scheduler cost, variable | Next loop iteration | Spin latency if within budget; worse than blocking if not |
| **CPU when idle** | None | One full core, permanently | One core for the budget, then none |
| **Needs a dedicated core?** | No | **Yes — hard requirement** | Preferably, but degrades gracefully |
| **Behaviour when oversubscribed** | Fine | Catastrophic | Poor but recoverable |
| **Cache state on wake** | Cold | Warm | Warm inside budget, cold after |
| **Main tuning input** | None | None | Inter-arrival distribution |
| **Fits** | Cold paths, control planes | Dedicated hot path with a core to spare | Bursty traffic, constrained core budget |

The asymmetry to keep in mind: **blocking's cost is paid per wake, spinning's cost is paid continuously.** That is why the decision cannot be made from the consumer loop alone. A per-wake cost is local; a continuous cost is a claim on a shared resource, and it has to be reconciled against every other thread on the machine.

## Common mistakes

**Spinning without a dedicated core.** The single most damaging error in the chapter. Quiz 1.

**Spinning without a pause hint.** Punishes the sibling hyperthread and the core's own execution resources for no gain.

**Reaching for `sched_yield` in the spin loop.** It looks like a considerate compromise and is usually the worst of both: you keep the thread runnable, so you have not released the core in any useful sense, but you have added a syscall to every iteration and handed the scheduler an opportunity to place you badly.

**Blocking on the hot path by default.** The mirror error. If a dedicated core is available and the path is latency-critical, blocking is leaving the main benefit unclaimed.

**Tuning the spin budget from the mean.** Quiz 2. Bimodal distributions make the mean actively misleading.

**Getting the hybrid transition order wrong.** Register, re-check, sleep. Any other order can lose a wakeup.

**Treating it as one global setting.** Different channels have different arrival distributions and deserve different strategies.

## Operational behaviour

- **A spinning thread reads as 100% CPU forever.** Monitoring must know this is intended, or someone will "fix" it during an incident. Document which threads are expected to be pegged, and alarm on the ones that are *not* pegged when they should be.
- **CPU utilisation stops being a load signal.** On a spinning system, utilisation says nothing about how busy you are. Queue occupancy and message rate are the real load indicators ([b2]). <!-- CALLBACK: b2 -->
- **The core budget needs an owner.** How many cores are dedicated to spinners is a machine-level constraint. It has to be documented, and it has to be re-checked whenever a thread is added or the host changes.
- **Power and thermal behaviour differ.** A host with several permanently spinning cores runs hotter and draws more power than one that blocks, which can affect boost behaviour for every other core on the package.

## When not to use spinning

- **More runnable threads than cores.** Non-negotiable. Count before you spin.
<!-- CALLBACK: c4 -->
- **Shared or virtualised hosts.** If you cannot guarantee a dedicated physical core, you do not have the precondition — and on a virtualised host, your "core" can be descheduled by a hypervisor you cannot see.
- **Cold paths and control planes.** Config reloads, admin interfaces, logging drains. Milliseconds are fine; a core is not.
- **When the queue is rarely empty.** If the consumer is always behind, it never waits, and the waiting strategy is irrelevant. Fix the consumer instead.
- **When the core is worth more elsewhere.** A core given to a spinner is a core denied to another strategy. That is a business decision as much as a technical one.

## Optional — if you want to see it for yourself

*This chapter gives you no latency figures on purpose, and the follow-up question in an interview is always how you would know.*

The measurement that actually informs the design is not the spin-versus-block latency gap — it is **your inter-arrival distribution**. Capture the timestamps at which messages arrive on a real channel for a real session, take the gaps, and plot them. That single histogram tells you whether spinning is viable, what the spin budget should be, and whether a hybrid is worth the complexity, in a way no borrowed figure can.

If you also want the latency gap itself, the comparison is straightforward: a ping-pong between two pinned threads, once with the consumer spinning and once with it blocking, reporting percentiles rather than means. Run the blocking case with genuinely idle gaps so you are measuring a real wake and not a thread that never actually slept — that is the most common way this benchmark quietly measures nothing.

Two habits, both transferable:

- **Distribution, not mean.** The whole argument in this chapter is about shape. A mean would have hidden it.
- **State the environment.** Kernel version, scheduler and power-management settings, pinning, whether the two threads shared a physical core. A wake-up latency figure without those is not a result.

The reasoning pattern an interviewer is probing: identify the suspected cost, build the smallest comparison that isolates it, and be explicit about what it does and does not establish. Here it establishes a gap on one machine under one configuration. It does not establish a portable number, and you should say so.

## Interview mapping

- **Ask how many cores are available**, before proposing anything. This is the single highest-signal move in the whole answer, and most candidates skip straight to "spin."
- **Frame it as a budget decision**, unprompted — a claim on a shared machine resource, not a property of one loop.
- **Explain the oversubscription inversion.** Knowing spinning gets *worse*, not just less good, shows you have run this rather than read it.
- **Describe hybrid waiting and derive the budget** from the arrival distribution, not from a constant.
- **Get the transition order right** if asked to sketch the hybrid: register, re-check, sleep, and be able to say what the re-check prevents.
- **Decline to quote a wake-up latency.** "It depends on kernel and power configuration; I'd measure it on the target" is correct and better received than a number you cannot defend.
- **Mention the monitoring consequence.** That 100% CPU becomes normal and utilisation stops being a load signal is a detail only people who have operated these systems tend to raise.

## Summary

When a consumer finds its queue empty it can give the core back or keep it, and that choice buys latency with cores in one direction or cores with latency in the other. Blocking pays a variable wake-up cost per message and a cold cache on the first iteration — on the first message after a lull, which in market data is disproportionately the one that matters. Spinning removes that cost entirely and pays instead with one core, continuously, forever.

The precondition is the whole answer. Spinning on a dedicated core is faster; spinning without one is catastrophically slower, because a permanently runnable thread starves the producer it is waiting for. Hybrid waiting bounds the exposure, at the price of a transition that must be sequenced correctly and a budget that must come from the measured shape of your arrivals rather than their average.

Which is why the first question is not "should I spin?" but "how many cores does this machine have, and what else needs them?" — a question about the whole system, asked from inside a five-line loop.

**Related:** [b0] threads, atomics, and locks · [b2] SPSC ring buffers · [b3] progress guarantees · [c4] thread affinity · [a3] latency and tail latency · [a4] measurement and profiling · [a5] cache locality · [d6] kernel bypass · [d4] backpressure and overload

## References

- Platform documentation for the spin-wait hint instruction and its intended use. *(Stage 1 source pack to pin the exact vendor references.)*
- Linux scheduler and futex documentation for wake-up path behaviour. *(Stage 1.)*
- Herlihy, M., & Shavit, N. (2020). *The art of multiprocessor programming* (2nd ed.). Morgan Kaufmann. [spinning, backoff, and contention management]
