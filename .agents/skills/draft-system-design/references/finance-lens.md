# Finance lens

Where a trading firm's answer differs from the consumer-tech answer to the same
question. Use at most one or two `> **Finance lens.**` callouts per chapter, at the
decision they change. Never append a generic finance section.

## Reading an ambiguous prompt

Many prompts have a consumer-tech reading and a trading-firm reading. Choose the
trading-firm reading when the prompt allows it, say so in one sentence, and
teach the reader to ask. Examples from the pilot track:

| Prompt | Consumer-tech reading | Trading-firm reading |
|---|---|---|
| Notification system | push and marketing to millions of app users | internal alerts: risk breaches, recon failures, fills, reports |
| Log publishing and query | ELK / Datadog: ingest scale, full-text search | the producer is a latency-critical C++ process; find one order across hosts |
| News feed, various formats | social timeline: fan-out to followers | vendor news ingestion: formats, dedup, latency, point-in-time history |
| Config / limit distribution | feature flags with eventual consistency | risk limits: bounded staleness, fail safe |

## Differences that change decisions

| Topic | Consumer-tech default | Trading-firm difference | Decision it changes |
|---|---|---|---|
| Scale | huge user counts | modest counts, bursts correlated with market events (the open, an exchange outage) | design for the burst; do the burst arithmetic |
| Latency | milliseconds, median | microseconds on the hot path, tail and jitter matter | no broker, no allocation, no syscalls on the live path |
| Durability | durable write per request | durability on a parallel path; live path keeps nothing | split hot and reliable paths |
| Availability | stay up, serve stale | unproven state must stop new risk | fail safe; explicit trust state |
| Silence | no news is good news | a dead feed looks like a quiet market | heartbeats, leases, staleness timers |
| Data loss | drop and retry | diagnostic data may drop; the order record never | explicit loss policy, two paths |
| Time | one clock is fine | several clocks; PTP-level skew matters; event vs knowledge time | carry both timestamps; as-of queries |
| Correctness | eventual consistency | a book or limit known to be wrong must not be published | sequence numbers, gap recovery, atomic swap |
| Control vs information | notifications and dashboards drive action | monitoring is not control; the check on the order path is | never put a control behind an async notification |
| Licensing | content is owned | vendor data is licensed per user and per use | enforce entitlements at delivery |

## Things not to do

- Do not add kernel bypass, FPGA, or lock-free structures to a system whose
  budget is milliseconds (a notification platform, a dashboard).
- Do not claim "availability matters more than consistency" as a slogan. State
  what must stay available (cancels, the kill switch) and what must stop (new
  risk on unproven state).
- Do not use CAP to rank latency, testability, and scale; it concerns
  consistency versus availability during a partition.
- Do not invent firm-specific practices, vendor limits, or latency figures.
  Label workload numbers as assumptions; describe hardware tiers qualitatively
  and link the handbook for numbers.
