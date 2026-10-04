# Companion handbook map

Chapter numbers and display titles as printed in the handbook (`release1/handbook-markdown/INDEX.md`;
`curriculum.yaml` is authoritative). Link with the chapter number and display title, and point at a
part when it helps. "Track" lists the system-design questions that already link the chapter.

Link format: `[Handbook Ch 23 — *The Book That Is Silently Wrong*](../../../release1/handbook-markdown/chapters/d3-sequence-and-gap-recovery/chapter.md)`


## Module A — System context, domain model, and performance reasoning

| Ch | Display title | Concept | ID | Parts worth pointing at | Track |
|---|---|---|---|---|---|
| 1 | *From Exchange Packet to Trade* | Anatomy of an Electronic Trading System | `a1-system-data-flow` | — | — |
| 2 | *The Order You Cannot See* | Order lifecycle and state machines | `a2-order-lifecycle` | P1: The states, and why the pending ones exist; P2: Transitions, as conditions and behaviour | — |
| 3 | *The Worst Microsecond of the Day* | Latency, tail latency, jitter, and throughput | `a3-latency-throughput` | P1: Why the tail is the product; P2: Latency and throughput are different questions | Q4 |
| 4 | *The Regression the Profiler Cannot See* | Measurement, benchmarking, and performance diagnosis | `a4-measurement-and-profiling` | P1: Why the profiler cannot see it; P2: What to do instead; P3: What microbenchmarks actually measure | — |
| 5 | *Fetching a Kilobyte to Read a Price* | CPU cache locality and data-oriented layout | `a5-cache-locality-and-layout` | P1: Counting lines; P2: When struct-of-arrays is the wrong answer; Going deeper elsewhere | — |
| 6 | *Four Threads, One Core's Worth of Work* | Cache coherence and false sharing | `a6-coherence-and-false-sharing` | P1: Why nothing will tell you; P2: Fixing it, and not overdoing it; Going deeper elsewhere | — |

## Module B — C++ concurrency and communication

| Ch | Display title | Concept | ID | Parts worth pointing at | Track |
|---|---|---|---|---|---|
| 7 | *The Counter That Lost Count* | Threads, atomics, and locks: the tools of concurrency | `b0-threads-atomics-locks` | P1: The mutex: making a block indivisible; P2: Atomics: making one location indivisible; P3: Choosing between them | — |
| 8 | *Waiting for the Market to Move* | Busy spinning, blocking, and hybrid waiting | `b5-waiting-strategies` | P1: What blocking actually costs; P2: What spinning actually costs, and when it inverts; P3: Hybrid waiting | Q4 |
| 9 | *What the Other Thread Can See* | C++ memory-model foundations | `b1-cpp-memory-model` | P1: Deriving the fix; P2: The ordering menu, and what each one buys; Going deeper elsewhere | Q5 |
| 10 | *The Handoff That Cannot Block* | SPSC ring buffers | `b2-spsc-ring-buffer` | P1: Correct index movement; P2: The memory ordering, derived; Going deeper — caching the peer's index | Q2, Q4 |
| 11 | *When One Thread Stops, What Happens to the Rest* | Blocking, lock-free, and wait-free progress guarantees | `b3-progress-guarantees` | P1: Why blocking hurts here specifically; P2: Classifying real code; P3: Choosing, and the cost of the stronger guarantee; Going deeper elsewhere | — |
| 12 | *When Everyone Wants the Same Cache Line* | MPSC queues and contention | `b4-mpsc-and-contention` | P1: Why `fetch_add` alone is broken; P2: The contention, and the alternative | Q2 |
| 13 | *The Cost of Asking Which Strategy* | Dispatch and polymorphism on the hot path | `b6-hot-path-dispatch` | P1: The cheap fix nobody proposes; P2: The alternatives, honestly compared; P3: Where the time actually goes; Going deeper elsewhere | — |
| 14 | *The Bug That Passes Every Test* | Testing concurrent and lock-free code | `b7-testing-concurrent-code` | P1: Test the sequential logic first, without threads; P2: Making the stress test able to fail; P3: Tools, and their actual limits; Going deeper elsewhere | Q5 |

## Module C — Memory and machine topology

| Ch | Display title | Concept | ID | Parts worth pointing at | Track |
|---|---|---|---|---|---|
| 15 | *The Latency Spike at 09:30* | Virtual memory, page faults, huge pages, and TLBs | `c1-virtual-memory` | P1: Getting the faults out of the way; P2: Translation has its own cache; Going deeper elsewhere | — |
| 16 | *Never Ask the Allocator During Market Hours* | Preallocation and object pools | `c2-preallocation-and-pools` | P1: A pool with a bounded worst case; P2: Empty is a policy question; P3: Return discipline | Q2, Q4 |
| 17 | *Free Everything at Once* | Arenas, slabs, and custom allocators | `c3-arenas-and-allocators` | P1: What the arena forbids; P2: Slabs, and plumbing it in; Going deeper elsewhere | — |
| 18 | *Counting the Copies* | mmap, shared memory, and zero-copy claims | `c6-mmap-and-zero-copy` | P1: Counting copies in a real path; P2: What mmap changes about failure; P3: Shared memory between processes | Q2 |
| 19 | *Where Your Thread Actually Runs* | Thread affinity and scheduler interaction | `c4-thread-affinity` | P1: Doing the pinning, and the topology trap; P2: The isolation half; Going deeper elsewhere | Q2 |
| 20 | *The Server Upgrade That Made Things Worse* | NUMA-aware placement | `c5-numa-placement` | P1: Where your memory actually is; P2: Is NUMA actually your problem?; Going deeper — automatic balancing and sub-socket nodes | Q4 |

## Module D — Networks, protocols, and time

| Ch | Display title | Concept | ID | Parts worth pointing at | Track |
|---|---|---|---|---|---|
| 21 | *Reading the Wire* | Market data and exchange protocols | `d1-market-data-and-protocols` | P1: Framing: what is actually in the packet; P2: Numbers on the wire; P3: What kind of feed is it? | Q3, Q4 |
| 22 | *Why the Exchange Does Not Reply to You* | TCP, UDP, and multicast in trading systems | `d2-tcp-udp-multicast` | P1: Why market data is multicast, and unreliable on purpose; P2: Why order entry is a session; P3: The settings that actually matter | Q4 |
| 23 | *The Book That Is Silently Wrong* | Sequence numbers, gap detection, and recovery | `d3-sequence-and-gap-recovery` | P1: What a gap actually means; P2: Two ways to recover, and they are not the same; P3: Recovering without stalling the live feed; Going deeper — redundant feeds | Q4, Q5 |
| 24 | *When the Market Outruns You* | Hot-path networking, batching, and overload | `d4-parsing-batching-backpressure` | P1: Knowing where you lost it; P2: Batching, and its price; P3: Choosing what to lose | Q1, Q2 |
| 25 | *Whose Clock Was That?* | Clock synchronisation, timestamp semantics, and time domains | `d5-clocks-and-timestamps` | P1: Which subtractions are legal; P2: Synchronisation, and what it buys; P3: Ordering, which is a separate problem | Q2, Q3, Q5 |
| 26 | *Taking the Kernel Out of the Path* | Kernel bypass and user-space networking | `d6-kernel-bypass` | P1: What it costs; P2: What to try first | Q3, Q4 |
| 27 | *The Control Plane* | WebSocket, HTTP polling, and venue APIs (appendix) | `d7-websocket-and-http` | — | Q3 |

## Module E — Orders, books, risk, and correctness

| Ch | Display title | Concept | ID | Parts worth pointing at | Track |
|---|---|---|---|---|---|
| 28 | *The Structure Everything Reads* | Order-book representation and construction | `e2-order-book-construction` | P1: Four representations; P2: The full version: a ladder of intrusive lists; P3: Maintain the top, do not recompute it; P4: Publish whole packets, not whole messages | Q4 |
| 29 | *Sending It Twice* | Idempotency, duplicate handling, and retry semantics | `e1-idempotency-and-duplicates` | P1: The client order ID; P2: Not everything needs this equally; P3: Duplicates arriving at you | Q1, Q3 |
| 30 | *The Check You Cannot Skip* | Pre-trade risk-engine foundations | `e3-pretrade-risk-engine` | P1: What is actually checked; P2: When exposure is counted; P3: Two layers, and a switch that always works | Q1, Q5 |
| 31 | *What Did It See, and Why Did It Do That?* | Deterministic replay and incident reconstruction | `e4-deterministic-replay` | P1: Designing for it; P2: What replay cannot do; P3: Two times, and why research needs both; P4: When the replay diverges | Q2, Q3, Q4, Q5 |

## Not in release 1

Backtesting methodology (`f1`) and columnar storage (`f2`) are deferred to handbook release 2. Until then,
link a related track question or an authoritative external source, and never invent a chapter number.
