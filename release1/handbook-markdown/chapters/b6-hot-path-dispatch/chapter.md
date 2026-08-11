<!--
chapter: b6-hot-path-dispatch
state: draft_created
contract: standards/chapter-contract.md
include_measurement_plan: true | include_quizzes: true | primary_artifact_mode: code
unresolved_markers: 0
-->

# The Cost of Asking Which Strategy

## Dispatch and Polymorphism on the Hot Path

**Prerequisites:** [a5] Cache locality and layout · [a4] Measurement and profiling
**Focus:** dispatch cost is dominated by lost inlining and branch predictability, not by the vtable indirection everyone blames

---

## Six types, one virtual call

A firm's strategy framework does the obvious thing. Strategies derive from a base class, register for the symbols they care about, and receive updates through a virtual method:

```cpp
class Strategy {
public:
    virtual void on_update(const BookUpdate&) = 0;
    virtual ~Strategy() = default;
};

// Hot path: for every book update, for every subscriber
for (Strategy* s : subscribers[symbol])
    s->on_update(update);
```

Six strategy types. Several hundred instances. This loop runs on every book update, which during a burst is tens of thousands of times a second.

In a design review someone proposes replacing the virtual calls with CRTP, "for performance." It is a substantial change — it touches how strategies are stored, registered, and built — and nobody in the room can say what it would save. The estimates offered range from "a few nanoseconds" to "it's the whole inner loop."

Both could be right. Which one it is depends on something nobody has measured, and on a cost model most of the room has slightly wrong.

## Where you will actually meet this

Any framework that dispatches to pluggable handlers on the critical path:

- **Strategy dispatch**, the case above.
- **Message-type dispatch** in a feed handler — a switch or a table mapping wire message types to handlers ([d1]).
- **Venue-specific behaviour** behind a common interface in the order gateway ([a2]).

It is also a reliable C++ interview topic at latency-sensitive firms, and it separates candidates in a specific way. The common answer — "virtual calls are slow because of the pointer indirection" — is not exactly wrong, but it names the smallest of the three costs. What the interviewer is listening for is whether you know which one actually dominates.

## The mental model

A virtual call does three things, and they are worth separating because they cost very different amounts.

1. **Load the vtable pointer** from the object, then **load the function pointer** from the vtable. Two dependent loads. If the object is in cache, these are cheap ([a5]).
2. **Call through the loaded pointer.** An indirect branch — the processor must predict the target before it knows it.
3. **Do so opaquely**, from the compiler's point of view. It does not know which function will run, so it cannot inline.

Almost everyone blames (1). It is usually the smallest of the three.

**(3) is normally the largest**, and the reason is that inlining is worth much more than the call overhead it removes. When a small function is inlined, the compiler can see across the boundary: it propagates constants into it, deletes branches it can prove are not taken, keeps values in registers instead of spilling them to the stack for the call, and merges the body into surrounding loop optimisations. A five-line `on_update` that is inlined might reduce to two instructions. The same function behind a virtual call is a genuine function call with a full argument setup and register save.

**(2) matters when the target is unpredictable.** Modern processors predict indirect branch targets, and they are good at it when there is a pattern. Call the same concrete type a thousand times in a row and the predictor is right every time, at which point the branch costs little. Alternate unpredictably between six types and it mispredicts often — and a misprediction costs the pipeline refill, which is far more than the two loads in (1).

This gives the practical shape of the problem. **The cost of a virtual call is not a constant.** It depends on whether the compiler could have inlined the callee, and on whether the call site sees a predictable sequence of types. Which is why "a virtual call costs N nanoseconds" is not a meaningful statement, and why the estimates in the design review varied so wildly.

## Part 1 — The cheap fix nobody proposes

Because prediction is a large part of the cost, there is an intervention that costs almost nothing and is routinely overlooked: **make the sequence of types predictable.**

```cpp
// code-b6-1 | ILLUSTRATIVE — same virtual calls, better prediction
// Before: subscribers in registration order — types interleaved arbitrarily.
for (Strategy* s : subscribers[symbol])
    s->on_update(update);

// After: group by concrete type once, at registration time.
for (auto& [type, group] : subscribers_by_type[symbol])
    for (Strategy* s : group)
        s->on_update(update);      // long runs of one target
```

Nothing about the design changed. Same base class, same virtual method, same objects. But the call site now sees long runs of one concrete type, the indirect branch predictor is right nearly always, and the instruction cache stays warm on one implementation instead of thrashing between six.

There is a second benefit from [a5]: instances of the same type are now likely to be allocated and iterated together, so the object loads are more predictable too. <!-- CALLBACK: a5 -->

This does not recover the inlining — the compiler still cannot see the target. But it removes the misprediction cost, and it takes an afternoon rather than a refactor. **Try it before proposing anything structural**, because if it closes most of the gap, the structural change has to justify itself against a much smaller remaining benefit.

## Part 2 — The alternatives, honestly compared

Four mechanisms, each trading something different.

```cpp
// code-b6-2 | ILLUSTRATIVE — the same dispatch, four ways

// 1. Virtual — open set, runtime-extensible
struct Strategy { virtual void on_update(const BookUpdate&) = 0; };

// 2. CRTP — compile-time, fully inlinable
template <typename Derived>
struct StrategyBase {
    void on_update(const BookUpdate& u) {
        static_cast<Derived*>(this)->on_update_impl(u);   // resolved at compile time
    }
};

// 3. std::variant — closed set, no allocation, inlinable per alternative
using AnyStrategy = std::variant<MarketMaker, Arb, Taker /* ... */>;
for (auto& s : strategies)
    std::visit([&](auto& concrete) { concrete.on_update(update); }, s);

// 4. std::function — maximum flexibility, maximum cost
std::vector<std::function<void(const BookUpdate&)>> handlers;
```

| | Virtual | CRTP | `std::variant` | `std::function` |
|---|---|---|---|---|
| **Type set** | Open — plugins, runtime loading | Closed, and known at each call site | Closed, known at compile time | Open |
| **Inlining at the call site** | No | **Yes** | Yes, per alternative | No |
| **Branch behaviour** | Indirect, predictable if grouped | None — direct call | Jump table or branch chain | Indirect, plus a second indirection |
| **Heterogeneous container** | Yes, naturally | **No** — needs erasure, which reintroduces the problem | Yes | Yes |
| **May allocate** | No | No | No | **Yes** |
| **Compile time / code size** | Low | High — one instantiation per type | Moderate | Moderate |
| **Adding a type** | Add a class | Add a class, touch call sites | Add to the variant, recompile everything | Add a callable |

Two rows decide most real cases.

**CRTP's problem is the heterogeneous container.** CRTP is genuinely faster where the concrete type is known at the call site, because the call becomes direct and inlinable. But the opening scenario needs a *collection of different strategy types*, and CRTP alone cannot express that — the usual fix is to store them behind a virtual interface after all, at which point the dispatch is virtual again and you have gained nothing at the call site that matters. This is the trap in the design review: CRTP is faster in the microbenchmark someone will write, and the microbenchmark will not have the container.

**`std::variant` is the underrated option here.** A closed set of six strategy types is exactly what a variant expresses. Objects are stored by value with no allocation and good locality, `std::visit` can inline the body for each alternative, and the dispatch becomes a jump table rather than an indirect call through memory. The cost is compile time and a recompile whenever the set changes — acceptable when the set is a fixed part of your system, unacceptable for plugins.

**`std::function` should not be on the hot path.** It type-erases, which means an indirect call that cannot be inlined, plus a second indirection, plus a possible heap allocation for anything that does not fit its small-object buffer. It is a fine tool for configuration, callbacks, and cold paths, and a poor one for the inner loop.

**Devirtualisation** is worth knowing about and not worth relying on. The compiler may resolve a virtual call to a direct one when it can prove the type — a `final` class, an object whose construction it can see, or with link-time optimisation across the whole program. Marking classes and overrides `final` genuinely helps it. But whether it fires depends on inlining decisions, build configuration, and how the objects reach the call site, so it is a bonus rather than a plan.

---

**Quiz 1**

A microbenchmark compares a virtual call against a CRTP call in a tight loop over one concrete type. CRTP is roughly four times faster.

Which of the three costs does that gap mostly represent, and what would you expect if the same comparison used six interleaved types?

> **Answer**
>
> **Mostly the lost inlining.** In a tight loop over one type, the indirect branch is perfectly predicted after the first few iterations, and the object is in L1, so the vtable loads are nearly free. What remains is that the CRTP version's body got inlined into the loop — where the compiler could hoist, propagate constants, and keep values in registers — and the virtual version stayed a real function call.
>
> If the callee is small, the gap can be much larger than four times, because inlining does not merely remove the call: it may cause the body to disappear into surrounding optimisations.
>
> **With six interleaved types**, both numbers get worse and the gap changes character. CRTP over a heterogeneous set is not directly expressible, so the honest comparison is against a virtual call with an unpredictable target — where the misprediction cost is now real and the instruction cache is being shared between six implementations. The virtual side degrades more, so the ratio may widen.
>
> But the benchmark has now drifted from the real question. **The production loop has six types in a container, which is the case CRTP cannot express** without erasing back to a virtual interface. A microbenchmark over one type measures a configuration the system does not have — the [a4] lesson in a new costume ([a4]). <!-- CALLBACK: a4 -->
>
> The lesson: attribute the gap to the right cost before generalising from it. "CRTP is 4× faster" is a fact about inlining in a single-type loop, not a prediction about a heterogeneous dispatch loop.

---

## Part 3 — Where the time actually goes

Before any of this matters, one question has to be answered: **how much of the loop is dispatch?**

If `on_update` does real work — walking book levels, computing a fair value, evaluating quoting logic — then the dispatch is a small fraction of the iteration and eliminating it entirely changes little. If `on_update` returns immediately for most updates because the strategy is not interested, then dispatch is nearly the whole cost, and the right fix may not be a faster call at all but **not making the call**: filter subscribers so uninterested strategies are never invoked.

That reframing is worth more than any mechanism in this chapter. A dispatch you avoid costs nothing, and it is very common for a subscriber list to contain strategies that will do nothing with this particular update.

---

**Quiz 2**

Your dispatch loop calls six strategy types in registration order, which interleaves them arbitrarily. Profiling shows the loop is a meaningful share of tick-to-trade.

Rank these by expected benefit per unit of engineering effort, and say what you would do first:

1. Convert everything to CRTP.
2. Group subscribers by concrete type.
3. Replace the base class with `std::variant` and `std::visit`.
4. Filter the subscriber list so uninterested strategies are never called.

> **Answer**
>
> **First: 4, then 2. Then consider 3. Almost never 1 as stated.**
>
> **4 — filter the list.** The cheapest call is the one that does not happen. If a meaningful share of invocations return immediately because the strategy does not care about this update, removing them removes the dispatch, the call, and the body together. Usually a small change to registration, and frequently the largest single win.
>
> **2 — group by type.** An afternoon's work, no design change, and it removes the misprediction component entirely by giving the predictor long runs of one target. Since the loop currently interleaves six types arbitrarily, misprediction is likely a real cost here.
>
> **3 — `std::variant`.** A genuine improvement — inlinable per alternative, no allocation, better locality — and a real change: the type set becomes closed, everything recompiles when it changes, and compile times grow. Worth doing if 4 and 2 leave a gap and the strategy set is genuinely fixed.
>
> **1 — CRTP.** As stated, it does not solve the problem. The loop iterates a heterogeneous collection, which CRTP cannot express; you would end up storing the strategies behind a virtual interface and dispatching virtually anyway. It is the change that sounds most like performance work and delivers least here.
>
> **What I would actually do first:** measure how much of the loop is dispatch versus strategy body ([a4]). If the body dominates, all four are close to irrelevant and the effort belongs elsewhere. The ranking above only matters once dispatch is established as a real share of the cost.
>
> The general lesson: the mechanism-swapping options are the visible ones, and the structural options — call less often, group better — usually pay more for less risk.

---

## Common mistakes

**Blaming the pointer indirection.** It is the smallest of the three costs. Lost inlining usually dominates.

**Assuming CRTP is universally faster.** It is faster where the type is known at the call site, and that is precisely what a heterogeneous container removes.

**Putting `std::function` on the hot path.** Indirect call, no inlining, possible allocation. Fine for configuration; wrong for the inner loop.

**Relying on devirtualisation.** It helps when it fires, and whether it fires depends on build configuration you may not control. Mark things `final`, and do not plan around it.

**Benchmarking one type and generalising to many.** Quiz 1.

**Restructuring before establishing that dispatch is a meaningful share.** If `on_update` does real work, this whole chapter is a rounding error ([a4]).

**Ignoring the option of dispatching less.** Filtering the subscriber list is usually cheaper and larger than any mechanism change.

## Going deeper elsewhere

*Optional. Not required for an interview answer, but it explains why the grouping fix in Part 1 works as well as it does.*

This chapter treats the indirect branch predictor as a black box that "does well with patterns." Real predictors are considerably more capable: they maintain histories of recent branch outcomes and can learn correlated patterns, not merely repeated targets, which is why an interleaved sequence with structure sometimes predicts better than expected while a genuinely random one does not.

Knowing the specifics rarely changes a design and is not usually asked, but it does explain otherwise confusing measurements — including why grouping helps more on some workloads than others, and why a dispatch loop can get faster after an unrelated change that shortened the branch history. The authority is your CPU vendor's optimisation manual for the specific part, which documents the predictor structures its microarchitecture uses. These details differ substantially between vendors and generations, so do not carry conclusions across hardware.

## Operational behaviour

- **Record why the dispatch mechanism is what it is.** A `std::variant` where a base class would read more naturally will be "simplified" by someone eventually. One comment prevents it.
- **Watch subscriber counts.** Dispatch cost scales with how many handlers each update reaches, and that number grows quietly as strategies are added. A per-update subscriber count is a cheap metric that predicts this getting worse.
- **Treat `final` as free.** Marking classes and overrides `final` where they are not extended costs nothing and occasionally lets the compiler devirtualise.

## When not to touch dispatch

- **When the handler body dominates.** Measure first ([a4]).
- **When the type set is genuinely open** — plugins, runtime-loaded strategies, anything configured rather than compiled. Virtual is the right tool and the alternatives do not apply.
- **When it is not on the critical path.** Dispatch in a research pipeline or a configuration loader is not interesting ([a1]).
- **When the win is smaller than the maintenance cost.** CRTP and variant both make the code harder to change; that is a real ongoing cost against a one-time gain.

## Optional — if you want to see it for yourself

*The cost model above becomes intuitive only after you have watched the three costs move independently.*

The instructive experiment isolates the three costs rather than comparing mechanisms. Take one dispatch loop and vary a single thing at a time:

- **Same call, types interleaved versus grouped.** Isolates branch prediction. Nothing else differs.
- **Same call, tiny body versus substantial body.** Isolates the inlining component — the gap between virtual and direct should shrink dramatically as the body grows, because the call overhead becomes a smaller share.
- **Same call, objects contiguous versus scattered.** Isolates the object loads ([a5]).

Three comparisons tell you which of the three costs your loop actually pays, which is the thing you need before choosing a fix. A single virtual-versus-CRTP number tells you almost nothing, because it conflates all three.

Two habits worth keeping:

- **Vary one thing.** The point is attribution, not a headline number.
- **Use a realistic type mix and body.** A loop over one type with an empty body measures a configuration that does not exist.

## Interview mapping

- **Name the three costs and rank them.** Loads, branch prediction, lost inlining — with inlining usually largest. This is the answer that distinguishes you, because the common answer stops at the first.
- **Say the cost is not a constant.** It depends on predictability and inlinability, which is why "a virtual call costs N nanoseconds" is not a well-formed claim.
- **Propose grouping by type** before proposing a redesign. It signals you optimise cheaply first.
- **Raise the heterogeneous-container problem with CRTP.** Candidates who recommend CRTP without it have read about the technique rather than applied it.
- **Mention dispatching less often** as an option. Structural beats mechanical, and few candidates offer it.
- **Ask what fraction of the loop is dispatch** before proposing anything at all.

## Summary

A virtual call costs three things: two dependent loads, an indirect branch, and the inlining the compiler could not do. The last is usually the largest and the first is usually the smallest, which is the reverse of how it is normally described — and it means the cost is not a fixed number but a function of how predictable the call site is and how much the compiler could have done with the body.

That cost model points at cheaper fixes than a redesign. Grouping subscribers by concrete type removes the misprediction without changing anything structural. Filtering the subscriber list removes the call entirely, which is cheaper still. Both should be exhausted before a mechanism change is considered.

When a mechanism change is warranted, the choice follows from whether the type set is open or closed. Open sets need virtual dispatch and the alternatives do not apply. Closed sets have a real option in `std::variant`, which stores by value, inlines per alternative, and pays in compile time. CRTP is the answer people reach for and frequently the wrong one here, because it cannot express the heterogeneous container that made dispatch a question in the first place. And `std::function` belongs on cold paths.

Underneath all of it is the [a4] discipline: establish what fraction of the loop is dispatch before optimising the loop's dispatch.

**Related:** [a4] measurement and profiling · [a5] cache locality and layout · [a1] system anatomy · [a3] latency and tail latency · [d1] market data and protocols · [a2] order lifecycle

## References

- ISO/IEC. (2020). *ISO/IEC 14882:2020 — Programming languages — C++*. International Organization for Standardization. [virtual functions, `std::variant`, `std::function`]
- Indirect branch prediction structures are documented per microarchitecture in the relevant CPU vendor optimisation manual — the correct source for any specific behaviour, and the reason this chapter describes prediction qualitatively. *(Stage 1 source pack to pin editions.)*
