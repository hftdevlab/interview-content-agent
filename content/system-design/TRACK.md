# The System Design Track

This track is the interview companion to the *Quant Systems Engineering Domain Bridge Handbook*. The handbook teaches mechanisms — ring buffers, sequence numbers, memory ordering, clocks. The track applies them to the open-ended design questions trading firms actually ask, and links to the handbook chapter where each mechanism is explained.

**Every chapter stands alone.** Open the question you are preparing for; you do not need to read the others first. Where a chapter uses an idea that another question develops in depth, it explains the idea in a sentence or two and links that question by title.

Each question teaches a few **design moves**: reusable decisions such as "accept durably, then work asynchronously" or "conflate to the latest value". A move is taught in full, with its cost, in one question, and recognised in the others. Over several questions, the moves add up to a toolkit for designs this track never covers.

## How each chapter works

Every chapter follows the same path, so you always know where you are:

1. **The question** — the prompt as asked, what the system is for, and the one hard thing about it. A short domain primer appears only when the system needs one.
2. **Requirements** — what it must do, and the numbers that make it hard.
3. **Core entities and API** — the nouns, and the few calls or messages that move them.
4. **High-level design** — built one requirement at a time, with a figure that grows at each step. Components added in a step are highlighted in blue.
5. **What is still broken** — the gaps in the working design, which set up the deep dives.
6. **Deep dives** — the two or three questions an interviewer will push on. Each starts from a concrete scenario, shows the answers candidates usually give first and what they cost, then the refinement — and says so when no option is perfect.
7. **Calibration and follow-ups** — what separates a passing answer from a strong one, and three questions to test yourself.

Three kinds of callout appear throughout: **Design move** (a reusable decision and its cost), **Finance lens** (where a trading firm's answer differs from a consumer-tech one), and **In the interview** (how to say it).

## The questions

| Question | Level | The hard thing | Moves it teaches in full |
|---|---|---|---|
| [Design a Notification System](sd-notification-system/question.md) | Foundation · 45 min | Keep urgent alerts fast during an alert storm, and never lose one | accept durably · idempotency key · bounded retry · priority lanes · a queue buys time |
| [Design a Distributed Task Scheduler](sd-task-scheduler/question.md) | Intermediate · 45 min | Urgent work first, nothing waits forever, and no task with two live owners | separate when from who · lease and fence · priority without starvation |
| [Design a Log Publishing and Query System](sd-log-publishing-query/question.md) | Intermediate · 45 min | Logging that costs the trading thread almost nothing, searchable across the fleet | hand off the hot path · batching · partitioned log · index for the query · decide what may be lost |
| [Design a News Feed System](sd-news-feed/question.md) | Intermediate · 45 min | Many formats and duplicates in, one trustworthy stream out — honest about time | normalize at the edge · dedup by identity, then content · record when you knew · push to machines |
| [Design a Live Price Dashboard](sd-live-price-dashboard/question.md) | Intermediate · 45 min | The latest price on every screen within 100 ms, when prices change faster than screens can show | conflate to the latest value · fan out in tiers · spend a latency budget |
| [Design a Low-Latency Market Data Feed and Normalization System](sd-market-data-feed/question.md) | Advanced · 60 min | The shortest possible live path that knows when it is wrong | split hot and reliable paths · sequence and recover · arbitrate feeds · publish trust state · capture for replay · isolate slow consumers |
| [Design a Risk-Limit Update Fan-Out Service](sd-risk-limit-fanout/question.md) | Advanced · 45 min | Prove every strategy uses current limits, and stop when you cannot | version authoritative state · acknowledge where enforced · freshness lease · fail safe · build aside, swap atomically |
| [Design a Distributed Time-Series Storage System](sd-timeseries-storage/question.md) | Advanced · 60 min | Fast scans over years of data that keeps being rewritten | columnar blocks · overwrite by versioned range · write immutably, compact later · lazy merge iterators · snapshot reads |

There is no required order. If you want one, the table runs from foundation to advanced: the early questions teach general distributed-systems moves, and the later ones apply them under trading-specific pressure.

## How the questions connect

The same idea often comes back in a different form, and noticing that is what lets you handle a question you have never seen:

| Idea | Taught in | Comes back in |
|---|---|---|
| A lease | Notification System: a claim that expires if its worker dies | Task Scheduler adds a fencing token for the worker that wakes up; Risk-Limit Fan-Out uses a lease as proof that limits are fresh |
| Versions | Risk-Limit Fan-Out: one version per change, to order updates and detect gaps | Time-Series Storage: versions decide which overlapping write a reader sees |
| Keep only the latest | Live Price Dashboard: conflate state for a screen | Market Data Feed: never conflate deltas for a strategy; mark it stale and recover |
| Append, do not overwrite | News Feed: a correction is a new revision | Time-Series Storage: an overwrite is a new version over a range, so old backtests stay reproducible |
| Idempotency key | Notification System: the caller names the operation once | Task Scheduler (job firings), Log Publishing (batch ranges), News Feed (vendor story IDs), Risk-Limit Fan-Out (operation IDs) |

The full move-by-question matrix, with the handbook chapter behind each move, is generated from chapter metadata into `generated/catalogs/system-design-track.md`, and a map of which questions share moves into `generated/diagrams/track/track-map.svg`.
