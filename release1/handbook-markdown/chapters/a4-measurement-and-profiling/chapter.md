<!--
chapter: a4-measurement-and-profiling
state: draft_created
contract: standards/chapter-contract.md
include_measurement_plan: false | include_quizzes: true | primary_artifact_mode: pseudocode
unresolved_markers: 0
-->

# The Regression the Profiler Cannot See

## Measurement, Benchmarking, and Performance Diagnosis

**Prerequisites:** [a3] Latency, tail latency, jitter, and throughput
**Focus:** a measurement answers a question — the skill is choosing the question and the smallest comparison that isolates it

---

## Nothing changed, and everything is slower

A release goes out on Tuesday. By Wednesday afternoon the p99.9 tick-to-trade is noticeably worse, and it is worse consistently — this is not noise, it reproduces every day, and it started with that release.

The team does the obvious thing. They run a sampling profiler against the process under production load and compare the flame graph with last week's.

The graphs are the same. No new hot function. No function that grew. Nothing at the top of the list that was not there before. The total time is distributed across the same code in roughly the same proportions.

The regression is real, reproducible, and invisible to the tool everyone reaches for first.

This is not a strange edge case. It is the *normal* situation when the problem is in the tail, and understanding why the profiler cannot see it — and what to do instead — is one of the more valuable things in this handbook.

## Where you will actually meet this

Performance diagnosis is routine work at any latency-sensitive firm. Systems drift, hardware changes, message rates grow, and someone has to find out why the number moved.

It is also a standard interview question, usually posed as a scenario much like the one above. What is being assessed is not which tools you can name. It is whether you reach for a **hypothesis** or for a **tool** — because a candidate who says "I'd run perf" has described a reflex, and a candidate who says "I'd first check whether the regression is in the median or only in the tail, because that changes what I'd look at" has described a method.

## The mental model

Here is the framing that makes the rest of the chapter follow.

**A measurement is an answer to a question.** Not a number you collect and then interpret — a question you formulate first, then design a measurement to resolve.

This sounds like a platitude until you notice how much performance work proceeds the other way: run the profiler, look at what is at the top, optimise it, hope. That process produces numbers you cannot interpret, because you never decided what would count as an answer.

The disciplined loop is:

1. **Form a hypothesis.** Something specific enough to be wrong. Not "the parser is slow" but "the regression is in the tail only, and it is caused by something that happens rarely."
2. **Design the smallest comparison that distinguishes it from the alternatives.** Two builds differing in one thing. One flag toggled. One stage timed.
3. **Say in advance what each outcome would mean.** If you cannot, the measurement will not settle anything.
4. **Run it, and be explicit about what it did and did not establish.**

Step 3 is the one people skip, and skipping it is why so many performance investigations produce a folder of benchmark results and no conclusion.

## Part 1 — Why the profiler cannot see it

A sampling profiler works by interrupting the program at intervals — say a thousand times a second — and recording the stack. Over a long run, the number of samples landing in a function is proportional to the **total time spent** there. That is exactly what you want for finding where the bulk of the work goes.

Now consider the shape of a tail problem, using [a3]'s framing. <!-- CALLBACK: a3 -->

Suppose one message in ten thousand takes 500µs instead of 5µs. That is a serious problem: at high message rates it happens many times a minute, and it lands during bursts when it hurts most.

What fraction of total execution time does it represent? If the other 9,999 messages take 5µs each, they account for about 50 milliseconds. The bad one accounts for 0.5 milliseconds — around **1% of the total**. The profiler will faithfully report that 1% of time is spent wherever that stall occurred, buried among a hundred other things at similar weight, indistinguishable from noise.

The profiler is not broken. It answered the question it was designed for: *where does the time go on average?* You asked a different question: *what happens during the rare bad case?* — and averages are the wrong instrument for rare events, structurally, not incidentally.

There is a second problem. Many tail causes do not live in your code at all. A page fault, a scheduling delay, an interrupt, a cache miss cascade, a cross-socket memory access — these show up as ordinary instructions taking longer than usual. The profiler attributes the time to whatever instruction was executing, which tells you where the cost *landed* and nothing about where it came from.

**So: sampling profilers are excellent for throughput problems and structurally poor for tail problems.** If the median regressed, profile. If only the tail regressed, you need something that observes every event rather than a sample of them.

## Part 2 — What to do instead

The tool for tail problems is **timestamping the path**: record a timestamp at each stage boundary for every message, and store the deltas. Every event is captured, so a one-in-ten-thousand stall is one clearly visible sample rather than a fraction of a percent of an aggregate.

```
// Per-message stage timestamps, hot path
on message arrival:
    t[0] = now()

after parse:
    t[1] = now()
after book update:
    t[2] = now()
after strategy decision:
    t[3] = now()
after risk check:
    t[4] = now()
after gateway send:
    t[5] = now()

// The recording step is the one that must not cost anything
for stage in 0..4:
    histogram[stage].record(t[stage+1] - t[stage])   // no allocation, no I/O

// Capture the whole trace only for outliers — rare, so the cost is amortised
if (t[5] - t[0]) > outlier_threshold:
    push_to_ring_buffer(t[])      // off-path thread writes it out
```

Three things matter about that sketch.

**Histograms, not averages.** You are looking for the tail, so you must keep the distribution. Recording a running mean per stage throws away the only information you came for ([a3]).

**The recording must be cheap and bounded.** No allocation, no locks, no I/O on the path. A histogram with fixed buckets is an array index and an increment. If your instrumentation can itself stall, you have added a tail source while hunting one.

**Capture outlier traces, not all traces.** Full detail on every message is too expensive. Full detail on the 0.01% that exceed a threshold costs almost nothing and gives you the cases you actually want — pushed to an off-path thread, since writing them out is emphatically not critical-path work ([a1], [b2]).

Once this is running, the diagnosis usually collapses quickly. Per-stage histograms tell you *which stage* the tail lives in, which turns an open-ended investigation into a bounded one. That single fact — knowing the regression is in book update rather than parsing — is often worth more than everything a profiler told you.

---

**Quiz 1**

You profile the process and find that 40% of total CPU time is in `parse_message`. A colleague proposes optimising it.

What do you need to know before agreeing, and under what circumstances would that 40% be the wrong thing to work on?

> **Answer**
>
> **Three things, and the 40% alone answers none of them.**
>
> **Is it on the critical path?** If parsing happens on a research replay thread or in an off-path capture pipeline, its CPU consumption is irrelevant to tick-to-trade. Large CPU share and zero latency impact coexist comfortably ([a1]).
>
> **Which problem are you solving?** 40% of *total time* is a throughput statement. If the complaint is a tail regression, this number is close to unrelated — the tail is made of rare events that contribute little to totals, which is precisely why the profiler ranked something else first.
>
> **Is it reducible?** Parsing might be 40% because it is genuinely the largest necessary piece of work. A stage being big is not evidence that it is wasteful, and "the biggest thing in the profile" is not a synonym for "the best thing to optimise."
>
> **When the 40% would be right:** the complaint is throughput — the system cannot keep up during bursts and messages are queueing — and parsing is on the path. Then it is exactly the right target, and the profiler did its job.
>
> The general lesson: a profiler tells you where time goes on average. Whether that is the thing you should care about depends on a question the profiler cannot answer for you.

---

## Part 3 — What microbenchmarks actually measure

Microbenchmarks are useful and routinely lie. Four ways, worth knowing by name.

**The optimiser deletes your work.** If a benchmark computes a value nobody uses, the compiler is entitled to remove the computation entirely, and you have timed an empty loop. Every benchmark framework provides some mechanism to prevent this; if you have hand-rolled a timing loop, you have almost certainly not thought about it.

**Cache state is unrealistic.** A loop hammering the same small array runs entirely in L1. The production version of that code runs once per message, on data that was evicted long ago, with the caches full of somebody else's working set. The benchmark measures a machine state that never occurs in production ([a5]).

**Branch predictors are unrealistically well-trained.** A loop running the same branch a million times teaches the predictor perfectly. In production that branch is taken once per message with different data, and the misprediction cost the benchmark never saw is now the dominant term.

**The access pattern is wrong.** Benchmarking a book update on a book with three price levels tells you almost nothing about a book with three hundred, because the answer is dominated by memory behaviour that only appears at realistic sizes.

None of this makes microbenchmarks useless. It means a microbenchmark answers a narrow question — *which of these two implementations is faster under these specific conditions* — and the burden is on you to argue that those conditions resemble production. Where the two disagree, **production is right**.

### The two mistakes, concretely

The first one is worth seeing in code, because it is easy to make and produces confident nonsense.

```cpp
// code-a4-1 | ILLUSTRATIVE — this benchmark measures an empty loop
auto start = clock::now();
for (int i = 0; i < 1'000'000; ++i) {
    double result = expensive_calculation(input[i]);   // result is never used
}
auto elapsed = clock::now() - start;                   // suspiciously fast
```

`result` is never read, `expensive_calculation` has no side effects, so the compiler is entitled to delete the call — and at higher optimisation levels it will. You have timed an empty loop and concluded your function is free.

```cpp
// The fix: make the result observable so it cannot be removed.
double sink = 0;
for (int i = 0; i < 1'000'000; ++i)
    sink += expensive_calculation(input[i]);
consume(sink);                    // or a benchmark framework's DoNotOptimize
```

The tell is a result that seems too good. A function that "takes 0.2ns" is not fast; it is absent. Any benchmark framework provides a mechanism for this — if you have hand-rolled a timing loop, assume you have this bug until you have checked the disassembly or the numbers against a known cost.

The second mistake is structural rather than syntactic, and it is [a3]'s coordinated omission arriving in your own harness: <!-- CALLBACK: a3 -->

```cpp
// code-a4-2 | ILLUSTRATIVE — closed loop: throttled by the thing it measures
for (auto& msg : messages) {
    auto t0 = clock::now();
    send(msg);
    await_response();                    // stalls here during a stall
    record(clock::now() - t0);           // one bad sample per stall
}
```

```cpp
// Open loop: send on a schedule, measure from when the message SHOULD have gone.
auto next_send = clock::now();
for (auto& msg : messages) {
    next_send += send_interval;
    busy_wait_until(next_send);
    send(msg);
    record(clock::now() - next_send);    // includes time spent behind schedule
}
```

The second version records every message that was delayed, not just the one that happened to be in flight. On a healthy system the two agree closely. On a system with a tail problem — the only case you care about — they disagree by a large factor, always in the direction that flatters the system.

---

**Quiz 2**

A microbenchmark says a function takes 8ns. Instrumented in production on the same hardware, the same function takes around 60ns at the median.

Nothing is wrong with either measurement. Where did the other 50 nanoseconds come from?

> **Answer**
>
> **Machine state.** The benchmark ran the function in a tight loop; production runs it once per message, and everything the loop had warmed up is cold.
>
> - **Caches.** The benchmark's data was resident in L1 after the first iteration. In production the data was last touched thousands of messages ago and has been evicted by everything since — so the production call takes cache misses the benchmark never paid for ([a5]).
> - **Branch predictors.** A million identical iterations train the predictor perfectly. One call with fresh data mispredicts.
> - **Instruction cache and TLB.** The benchmark's code and page mappings stay hot. In production the function competes with the rest of a large working set.
> - **Everything else on the machine.** Other threads, interrupts, the memory system serving other cores.
>
> Neither number is wrong. They answer different questions. The benchmark answers *how fast is this function when everything it needs is already in the right place*; production answers *how fast is it in the situation it will actually run in*. The gap between them is not error — **it is a measurement of how much this function depends on machine state**, which is itself a useful finding, and often the thing worth optimising.
>
> The trap is treating the 8ns as the true value and the 60ns as overhead to be explained away. It is the other way round.

---

## Common mistakes

**Reaching for a tool before forming a hypothesis.** The most consequential one, because it determines everything after it.

**Using a sampling profiler on a tail problem.** Structurally the wrong instrument.

**Measuring without deciding in advance what each outcome would mean.** Produces results that cannot settle anything.

**Instrumenting everything.** Broad instrumentation perturbs the system, costs more than it returns, and buries the signal. Target the hypothesis.

**Trusting a microbenchmark that was never argued to resemble production.**

**Skipping warm-up, or warming up too much.** Both are wrong for different reasons: cold measurements include one-time costs that will not recur, and heavily warmed ones describe a state production never reaches.

**Changing two things and measuring once.** Then you know something changed and not what.

**Reporting a number without its environment.** CPU, pinning, compiler and flags, load, what else was running. Without those it is not reproducible, so it is not a result.

## Operational behaviour

- **Instrumentation must be always-on.** Measurement infrastructure enabled only during incidents is untrustworthy during incidents — you have no baseline to compare against, and the act of enabling it changes the system.
- **Give it an overhead budget.** Decide what fraction of the path you are willing to spend on knowing what the path is doing, and hold the instrumentation to it.
- **Keep baselines.** A regression is only visible against history. Per-stage histograms from last month are what turn "it feels slower" into a bounded question.
- **Record the environment with the data.** Kernel version, hardware, configuration. Six months later this is the difference between an explanation and a mystery.

## When not to measure

- **Before establishing that the code is on the critical path.** Measure the right path first ([a1]).
- **When the answer is already determined by structure.** If a design allocates on the hot path, you do not need a benchmark to know it will have a tail. Fix it and measure afterward if you want the magnitude.
- **When you have no hypothesis.** Collecting data in the hope that something turns up is how investigations consume a week.
- **When the effect is smaller than your measurement noise.** Establish the noise floor first, or you will spend days chasing variance.

## Interview mapping

- **Start with a hypothesis, not a tool.** The single strongest move. "First I'd check whether the regression is in the median or only the tail, because that changes what I'd reach for."
- **Explain why the profiler missed it.** The arithmetic — a rare event contributes almost nothing to total time — is the part that shows you understand rather than recall.
- **Propose per-stage timestamping** with histograms and outlier capture, and note it must be allocation-free.
- **Identify what a described microbenchmark measures.** Interviewers like presenting one and asking what is wrong with it.
- **Say what your measurement does not establish.** Volunteering the limits of your own evidence reads as senior, because it is.
- **Ask what changed.** The regression started with a release. That is a bisection problem before it is a performance problem, and candidates who go straight to profiling often miss the cheapest path to the answer.

## Summary

A sampling profiler answers one question well: where does time go on average? Tail problems are made of rare events that contribute almost nothing to averages, so the instrument and the question are mismatched — and the graphs look identical while the p99.9 doubles.

What works instead is capturing every event: timestamps at stage boundaries, recorded into fixed-bucket histograms with no allocation, and full traces captured only for outliers. That localises the problem to a stage, which turns an open investigation into a bounded one.

Underneath the tooling is the discipline that transfers everywhere. Form a hypothesis specific enough to be wrong. Build the smallest comparison that separates it from the alternatives. Decide in advance what each outcome would mean. State what the result does and does not establish — including that a microbenchmark and a production measurement can both be right while disagreeing by a factor of eight, because they are answering different questions about different machine states.

Every later chapter that says "measure it on your hardware" is pointing here.

**Related:** [a1] system anatomy · [a3] latency and tail latency · [a5] cache locality · [b2] SPSC ring buffers · [b5] waiting strategies · [c4] thread affinity · [c5] NUMA placement · [d5] clocks and timestamps

## References

*(Practitioner framing per the claim taxonomy in `PROJECT_PLAN_V3.md` §5. A Stage 1 source pack should pin references for sampling-profiler methodology and for hardware performance-counter documentation on the target platform.)*
