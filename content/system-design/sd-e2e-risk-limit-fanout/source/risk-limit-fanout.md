# Risk-limit update fan-out

Design a service that distributes real-time risk-limit updates to multiple
trading strategy processes. Consumers can disconnect or become slow, but a
strategy must not silently continue forever with stale limits.

The prompt is intentionally incomplete. Treat clarification, bounded delivery,
recovery, and the boundary between the low-latency delivery path and durable
audit/replay as the important interview areas.
