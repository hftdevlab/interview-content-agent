# Quant Systems Engineering Domain Bridge Handbook
## Release 1 — source markdown

Chapters are stored one per directory so the relative figure links inside each
chapter resolve when the markdown is rendered in place.

**Read in this order.** Chapter IDs are stable handles and deliberately do not
encode reading order — Module B and Module C were both resequenced during
writing. `curriculum.yaml` is authoritative.

| # | Chapter | Path |
|---|---|---|
| — | Preface: Before You Start — Where C++ Engineers Fit in Electronic Trading | `front-matter/preface.md` |
| | **Module A — System context, domain model, and performance reasoning** | |
| 1 | From Exchange Packet to Trade — Anatomy of an Electronic Trading System | `chapters/a1-system-data-flow/chapter.md` |
| 2 | **The Order You Cannot See** — Order lifecycle and state machines | `chapters/a2-order-lifecycle/chapter.md` |
| 3 | **The Worst Microsecond of the Day** — Latency, tail latency, jitter, and throughput | `chapters/a3-latency-throughput/chapter.md` |
| 4 | **The Regression the Profiler Cannot See** — Measurement, benchmarking, and performance diagnosis | `chapters/a4-measurement-and-profiling/chapter.md` |
| 5 | **Fetching a Kilobyte to Read a Price** — CPU cache locality and data-oriented layout | `chapters/a5-cache-locality-and-layout/chapter.md` |
| 6 | **Four Threads, One Core's Worth of Work** — Cache coherence and false sharing | `chapters/a6-coherence-and-false-sharing/chapter.md` |
| | **Module B — C++ concurrency and communication** | |
| 7 | **The Counter That Lost Count** — Threads, atomics, and locks: the tools of concurrency | `chapters/b0-threads-atomics-locks/chapter.md` |
| 8 | **Waiting for the Market to Move** — Busy spinning, blocking, and hybrid waiting | `chapters/b5-waiting-strategies/chapter.md` |
| 9 | **What the Other Thread Can See** — C++ memory-model foundations | `chapters/b1-cpp-memory-model/chapter.md` |
| 10 | **The Handoff That Cannot Block** — SPSC ring buffers | `chapters/b2-spsc-ring-buffer/chapter.md` |
| 11 | **When One Thread Stops, What Happens to the Rest** — Blocking, lock-free, and wait-free progress guarantees | `chapters/b3-progress-guarantees/chapter.md` |
| 12 | **When Everyone Wants the Same Cache Line** — MPSC queues and contention | `chapters/b4-mpsc-and-contention/chapter.md` |
| 13 | **The Cost of Asking Which Strategy** — Dispatch and polymorphism on the hot path | `chapters/b6-hot-path-dispatch/chapter.md` |
| 14 | **The Bug That Passes Every Test** — Testing concurrent and lock-free code | `chapters/b7-testing-concurrent-code/chapter.md` |
| | **Module C — Memory and machine topology** | |
| 15 | **The Latency Spike at 09:30** — Virtual memory, page faults, huge pages, and TLBs | `chapters/c1-virtual-memory/chapter.md` |
| 16 | **Never Ask the Allocator During Market Hours** — Preallocation and object pools | `chapters/c2-preallocation-and-pools/chapter.md` |
| 17 | **Free Everything at Once** — Arenas, slabs, and custom allocators | `chapters/c3-arenas-and-allocators/chapter.md` |
| 18 | **Counting the Copies** — mmap, shared memory, and zero-copy claims | `chapters/c6-mmap-and-zero-copy/chapter.md` |
| 19 | **Where Your Thread Actually Runs** — Thread affinity and scheduler interaction | `chapters/c4-thread-affinity/chapter.md` |
| 20 | **The Server Upgrade That Made Things Worse** — NUMA-aware placement | `chapters/c5-numa-placement/chapter.md` |
| | **Module D — Networks, protocols, and time** | |
| 21 | **Reading the Wire** — Market data and exchange protocols | `chapters/d1-market-data-and-protocols/chapter.md` |
| 22 | **Why the Exchange Does Not Reply to You** — TCP, UDP, and multicast in trading systems | `chapters/d2-tcp-udp-multicast/chapter.md` |
| 23 | **The Book That Is Silently Wrong** — Sequence numbers, gap detection, and recovery | `chapters/d3-sequence-and-gap-recovery/chapter.md` |
| 24 | **When the Market Outruns You** — Hot-path networking, batching, and overload | `chapters/d4-parsing-batching-backpressure/chapter.md` |
| 25 | **Whose Clock Was That?** — Clock synchronisation, timestamp semantics, and time domains | `chapters/d5-clocks-and-timestamps/chapter.md` |
| 26 | **Taking the Kernel Out of the Path** — Kernel bypass and user-space networking | `chapters/d6-kernel-bypass/chapter.md` |
| 27 | **The Control Plane** — WebSocket, HTTP polling, and venue APIs *(appendix)* | `chapters/d7-websocket-and-http/chapter.md` |
| | **Module E — Orders, books, risk, and correctness** | |
| 28 | **The Structure Everything Reads** — Order-book representation and construction | `chapters/e2-order-book-construction/chapter.md` |
| 29 | **Sending It Twice** — Idempotency, duplicate handling, and retry semantics | `chapters/e1-idempotency-and-duplicates/chapter.md` |
| 30 | **The Check You Cannot Skip** — Pre-trade risk-engine foundations | `chapters/e3-pretrade-risk-engine/chapter.md` |
| 31 | **What Did It See, and Why Did It Do That?** — Deterministic replay and incident reconstruction | `chapters/e4-deterministic-replay/chapter.md` |

## What is here

| Path | Contents |
|---|---|
| `chapters/<id>/chapter.md` | the chapter source |
| `chapters/<id>/brief.yaml` | the authoring brief the chapter was written from |
| `chapters/<id>/figures/` | figures, referenced relatively from the chapter |
| `front-matter/preface.md` | the preface |
| `curriculum.yaml` | authoritative chapter list, reading order, prerequisites, status |
| `standards/` | chapter contract, diagram style, validator spec, feedback log |

31 chapters and the preface. Deferred to release 2: f1-backtesting-methodology, f2-columnar-storage.

## Rendering

Figure links are relative, so most markdown viewers resolve them **provided the
folder structure is preserved**. Previewing a single `chapter.md` on its own will
not show figures — that is a path-resolution limit of the viewer, not a broken
file. Figures are hand-authored SVG and open correctly on their own.

To produce HTML or PDF with figures inlined, use `build/make_book.py` from the
full project tree; it inlines each SVG so the output is self-contained.

## A note on the figures

Figures are generated from `build/figures_*.py`, not hand-edited as XML — the
header of each file says so. Editing the `.svg` directly will be overwritten by
the next regeneration.
