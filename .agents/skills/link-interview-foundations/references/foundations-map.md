# Companion handbook topic map

Use stable chapter IDs and paths from
`release1/handbook-markdown/INDEX.md`. This map routes common interview concepts;
the catalog and `curriculum.yaml` remain authoritative.

## System context and performance

| Interview concept | Handbook chapter |
|---|---|
| End-to-end trading data flow and hot-path boundaries | `a1-system-data-flow` |
| Latency, tail latency, jitter, and throughput | `a3-latency-throughput` |
| Benchmarking and profiling | `a4-measurement-and-profiling` |
| Cache locality and data-oriented layout | `a5-cache-locality-and-layout` |
| Cache coherence and false sharing | `a6-coherence-and-false-sharing` |

## Concurrency and communication

| Interview concept | Handbook chapter |
|---|---|
| Threads, atomics, mutexes, and compare-exchange | `b0-threads-atomics-locks` |
| Busy polling, blocking, and hybrid waits | `b5-waiting-strategies` |
| Acquire/release and the C++ memory model | `b1-cpp-memory-model` |
| SPSC ring-buffer delivery | `b2-spsc-ring-buffer` |
| Lock-free and wait-free progress | `b3-progress-guarantees` |
| MPSC queues and contention | `b4-mpsc-and-contention` |
| Hot-path dispatch | `b6-hot-path-dispatch` |
| Testing concurrent code | `b7-testing-concurrent-code` |

## Memory and topology

| Interview concept | Handbook chapter |
|---|---|
| Page faults, huge pages, and TLBs | `c1-virtual-memory` |
| Preallocation and object pools | `c2-preallocation-and-pools` |
| Arenas and custom allocators | `c3-arenas-and-allocators` |
| mmap, shared memory, and zero-copy claims | `c6-mmap-and-zero-copy` |
| Thread affinity and scheduler interaction | `c4-thread-affinity` |
| NUMA-aware placement | `c5-numa-placement` |

## Networking, market data, and time

| Interview concept | Handbook chapter |
|---|---|
| Market-data and exchange protocol structure | `d1-market-data-and-protocols` |
| TCP, UDP, and multicast | `d2-tcp-udp-multicast` |
| Sequence numbers, gaps, retransmission, and recovery | `d3-sequence-and-gap-recovery` |
| Parsing, batching, overload, and backpressure | `d4-parsing-batching-backpressure` |
| Clock synchronization and timestamp domains | `d5-clocks-and-timestamps` |
| Kernel bypass and user-space networking | `d6-kernel-bypass` |
| WebSocket, polling, and venue control APIs | `d7-websocket-and-http` |

## Trading correctness

| Interview concept | Handbook chapter |
|---|---|
| Order lifecycle and state machines | `a2-order-lifecycle` |
| Order-book construction | `e2-order-book-construction` |
| Idempotency, duplicate handling, and retries | `e1-idempotency-and-duplicates` |
| Pre-trade risk | `e3-pretrade-risk-engine` |
| Deterministic replay and incident reconstruction | `e4-deterministic-replay` |

The handbook defers backtesting methodology and columnar storage to a later
release. For those topics, use a relevant repository chapter when available or
an authoritative external source.
