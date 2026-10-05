# Expert notes

No question-specific expert notes yet.

Editorial direction carried from the system-design track reset (2026-10-03):

- Interpret the prompt the way a trading-firm interviewer usually means it: the
  producers are latency-critical C++ processes, so the in-process logger is half
  of the design, and the query side must find one order's story across hosts.
- Keep diagnostic logs and the authoritative order record on separate paths with
  opposite overload rules.
