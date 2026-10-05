# Expert notes

No question-specific expert notes yet.

Editorial direction (2026-10-04, from the track owner's request):

- Prompt supplied directly by the track owner. Interpreted as an internal batch
  and compute scheduler at a trading firm (end-of-day risk and P&L, pre-open
  loads, research backtests), not a consumer-tech cron service.
- The chapter must not repeat the notification system's lessons. It reuses
  accept-then-work, idempotency keys, retries, and priority lanes in a sentence
  each, and spends its depth on timers versus ready queues, fencing, and
  starvation.
- Human editor to confirm the interpretation and the workload numbers.
