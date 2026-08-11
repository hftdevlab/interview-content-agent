<!--
front matter: preface
governed by: standards/chapter-contract.md section 0 (front matter exemption)
claim types: judgment throughout, except where noted. No firm-specific practices,
             compensation figures, or hiring processes asserted.
-->

# Before You Start: Where C++ Engineers Fit in Electronic Trading

You already know how to write C++. That is not what stands between you and an offer.

What stands between you is that this industry uses ordinary words in ways that assume context you may not have. A recruiter says "systematic mid-frequency"; an interviewer asks which asset class you have worked with; a job description says "quant developer" and means something different at the firm across the street. None of this is hard. It is just unshared vocabulary, and not having it costs candidates who could do the job.

This preface is the map. It is not an introduction to finance — there is no discussion of what makes a strategy profitable, and you do not need one. It covers only the distinctions that change **what you will be asked in an interview and what you will build if you are hired.**

One caveat, meant seriously: everything here is a generalisation, and the variance between firms is large. Treat these as priors to be updated by the specific firm in front of you, not as facts to recite. A candidate who states a confident taxonomy and gets corrected has done worse than one who asked.

---

## 1. Types of firm

The label on the door tells you a lot about the engineering.

**Market makers** continuously quote both sides of an instrument — a price to buy and a price to sell — and earn the difference. They are not predicting direction so much as being reliably present, managing inventory, and not getting picked off when the market moves. Because a stale quote is a losing quote, **speed is close to existential**, and the engineering organisation reflects it: small teams, deep C++, and a real chance that some of the path is in hardware. For a low-latency C++ engineer this is the most engineering-centric corner of the industry.

**Proprietary trading firms** trade the firm's own capital. No outside investors, no client money, no fee structure to explain. In practice many prop firms *are* market makers, and the terms overlap heavily. The distinguishing feature for you is organisational: with no external clients, these firms tend to be flatter, faster-moving, and more willing to rebuild infrastructure. The technology is the business rather than a cost centre supporting it.

**Hedge funds** manage external capital and are accountable to investors. This changes the engineering in ways that are easy to underestimate: reporting, attribution, risk frameworks, and operational rigour are first-class requirements, not overhead. Horizons are typically longer than a market maker's, so latency matters less and **research throughput matters more** — how quickly can a researcher test an idea against twenty years of data? Expect a mixed stack: Python and research tooling in front, C++ where performance or correctness demands it. Multi-strategy funds may contain a fast pod that looks exactly like a prop firm alongside pods that look nothing like one.

**Investment banks** are the sell side. They serve clients: making markets on clients' behalf, providing execution services, distributing research. Two consequences. First, the regulatory surface is much larger, so auditability, controls, and change management shape how you work. Second, the technology estate is older and broader — there are genuine low-latency C++ roles, particularly in FX and rates, alongside a great deal of platform and integration work. Cycles are slower. Some engineers find that steadying, others find it stifling; both reactions are reasonable and worth being honest with yourself about.

**What this changes for you:** who owns latency, how much of the stack you touch, and whether "the trading system" is a thing your team built or a thing your team integrates with.

## 2. Systematic and discretionary

A separate axis, and one candidates conflate with firm type.

**Systematic** firms make decisions by rule. A model produces a signal, and the system acts on it without a human in the loop. Here the software *is* the strategy — a bug does not delay a trade, it makes the wrong trade. Everything in this handbook is aimed at systematic trading.

**Discretionary** firms have humans deciding what to trade. Technology supports rather than decides: order and execution management, execution algorithms that work a large order into the market without moving it, risk and position systems, data and analytics. These are real C++ jobs and often interesting ones, but the objective changes. You are optimising **execution quality** — did we get a good price for this order — rather than tick-to-trade.

Many firms are both, in different groups.

## 3. How fast is fast

Within systematic trading, the time horizon determines what "performance" even means. This is the axis that most changes which chapters of this handbook you need.

**High-frequency trading** operates on horizons from sub-microsecond to a few milliseconds, with positions often held for seconds. At this end, the wire and the machine dominate: kernel bypass, careful memory placement, FPGAs on the receive path, and colocation — putting your server in the exchange's building because the speed of light in fibre is now a design parameter. Teams are small, C++ is deep, and interviews go to the hardware.

**Mid-frequency** covers roughly seconds to hours. Latency still matters — you do not want to be slow — but you are not competing for the first microsecond. Engineering effort shifts toward correct, scalable data infrastructure and reliable execution. Typical shape: C++ where it counts, Python around it.

**Lower-frequency systematic** trades on horizons of days to months. Latency is largely irrelevant. What matters is data integrity, backtesting fidelity, reproducibility, and correctness — a subtle lookahead bug in a research pipeline can invalidate years of work, and nobody will notice for a long time. C++ appears here for compute-heavy simulation and data processing rather than for latency.

**What this changes for you:** at the fast end you will be asked about cache lines and memory ordering. At the slow end you will be asked about data pipelines, reproducibility, and correctness under scale. Both are demanding. They are not the same interview, and preparing for the wrong one is the most common avoidable mistake.

## 4. What gets traded

You do not need to price a derivative to get hired as a systems engineer. You do need to know why the asset class changes the engineering, because it changes it a lot.

**Equities.** Shares in companies. In the US especially, trading is fragmented across many venues, so a complete picture means consuming and consolidating multiple feeds. Message rates are high and symbol counts are large. The order book is the central data structure. This is the most common starting point and most of the examples in this handbook are drawn from it.

**Futures.** Standardised contracts to transact later, traded on a central exchange. Fewer instruments than equities, deeper books, and — importantly for engineers — one venue per contract, so no fragmentation. That combination of clean data and high liquidity makes futures a common home for latency-sensitive strategies.

**Options.** Contracts giving the right to buy or sell at a set price. The engineering problem here is *scale of instruments*: every underlying has many strikes and expiries, so one stock can correspond to thousands of tradeable contracts. Quote traffic dwarfs equities, and quotes must be updated as the underlying moves, which makes options market data among the highest-volume data problems in finance — and adds a real compute problem, since pricing is continuous.

**FX.** Currency. No central exchange; a decentralised network of electronic venues and bank price streams. That changes the shape of everything: there is no single authoritative book, you aggregate liquidity from sources you have credit relationships with, and some venues allow the price maker a brief window to reject a trade after you have accepted it. Engineers coming from equities find FX's assumptions genuinely different rather than merely varied.

**Fixed income.** Bonds and rates products. Historically dealer-driven and negotiated, and while electronic trading has grown substantially, much of it is request-for-quote rather than continuous order books — you ask several dealers for a price rather than lifting a resting offer. Instrument counts are enormous and many individual bonds trade rarely. The engineering leans toward pricing, quoting, and workflow rather than microsecond latency, though the rates and futures end can be very fast.

**What this changes for you:** message rates, whether an order book is even the right abstraction, how much compute sits alongside the data path, and how fragmented your view of the market is.

## 5. Which role you are interviewing for

Three titles that recruiters use loosely and firms mean specifically. The boundaries move, but the archetypes are recognisable.

**Quant researcher.** Finds the edge. Statistics, time-series analysis, machine learning, and a lot of careful work avoiding ways to fool yourself with historical data. Typically a PhD or equivalent in a quantitative field. Works mostly in Python or R against research infrastructure someone else built. **Interviews:** probability, statistics, modelling, and research judgement. Little systems content.

**Quant developer.** The bridge. Turns research into something that runs in production, and builds the tooling researchers depend on — backtesting engines, data pipelines, simulation, feature computation. Needs enough mathematics to talk to researchers and enough engineering to be trusted with production. **Interviews:** strong coding, system design, some probability and statistics, often a data-handling or backtesting design question. Broad rather than deep in any one direction.

**C++ developer / low-latency engineer / core systems engineer.** Builds the machine. Feed handlers, exchange connectivity, order gateways, the messaging fabric, the risk path. Cares about microseconds, determinism, and not falling over on the busiest day of the year. **Interviews:** deep C++, concurrency and the memory model, operating systems, networking, cache and memory behaviour, and system design under latency constraints. Usually little or no statistics.

**This handbook is written for the third role**, and for the systems half of the second.

Two adjacent roles worth knowing exist: **FPGA and hardware engineers**, who own the parts of the path that have left software entirely, and **trading infrastructure / production engineering**, which owns deployment, monitoring, network, and the health of live systems — a genuinely senior discipline in this industry rather than a support function.

## 6. What interviews actually emphasise

Given all of the above, the same job title produces materially different interviews.

**A high-frequency market maker or prop firm** will go deep on C++ and the machine. Expect the memory model, lock-free structures, cache behaviour, what the compiler is permitted to do, how you would measure something, and system design with a latency budget. Questions are often diagnostic — *here is a symptom, what do you check* — because that is the job. You may meet a coding round with unusually tight performance expectations. Little to no statistics.

**A multi-strategy hedge fund** casts wider. Systems design, data infrastructure, correctness at scale, and how you reason about tradeoffs. Latency questions appear but with less depth than at a market maker, unless you are interviewing for a fast pod. More emphasis on judgement and on how you work.

**An investment bank** typically runs a more conventional software interview — algorithms, design, language depth — plus product and workflow knowledge relevant to the desk, and awareness of controls and regulatory context. Domain knowledge is weighted more heavily than at prop firms, where they will teach you the domain if the engineering is there.

**A mid- or low-frequency systematic firm** will probe data engineering, pipeline design, reproducibility, and correctness. Expect questions about backtesting integrity and how you would know a result is real. Less hardware, more scepticism.

**The constant across all of them** is reasoning. Nobody senior is impressed by a memorised fact, and everyone is interested in how you got to an answer, what you would measure, and what you would do if you were wrong. This is why the chapters in this handbook derive their conclusions rather than stating them — the derivation is the transferable part, and it is what is actually being assessed.

---

## How to use this handbook

The chapters build in order and each names its prerequisites, so reading start to finish works. But if you are preparing for something specific:

- **HFT or market making** — everything, with Modules B and C the sharp end.
- **Mid-frequency systematic** — Modules A, B, and D, with Module C as background rather than target.
- **Quant developer, systems-leaning** — Module A in full, then D and E; treat B and C as depth you can reach for.
- **You have an interview next week** — Module A, then the chapters matching what the firm trades and how fast.

Every chapter ends with an *Interview mapping* section describing what separates a strong answer from a merely correct one. If you are short on time, those sections plus the summaries are a reasonable first pass — but the derivations are where the actual preparation is, because the follow-up question is always *why*.

One last thing. The distinctions in this preface are worth knowing and not worth performing. If an interviewer says something that does not match this map, they are right and this map is a generalisation. Ask.

**Next:** [chapter 1] From exchange packet to trade — the anatomy of an electronic trading system.
