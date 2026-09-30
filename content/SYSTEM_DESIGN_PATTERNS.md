# System-design challenge patterns

Patterns organize recurring decisions across the question bank. They are not
technology prescriptions, question types, or claims that a design is error-free.
The authoritative, expandable registry is `taxonomy/design-patterns.yaml`.

## Apply a pattern

Select only the challenges that the tutorial actually develops. Put their IDs
in `metadata.yaml.design_patterns` and their matching labels in a concise
`Design patterns:` line in the chapter. At the relevant deep dive, name the
pattern and explain its application in ordinary prose: what becomes expensive
or unsafe, the mechanism chosen, and its important trade-off. Do not repeat the
whole registry, add tags for passing mentions, or append a generic pattern essay.

For example, a news feed teaches **Scale Reads** when repeated timeline queries
motivate indexed retrieval or precomputed feeds. **Fan-out Write** names the
more specific choice to maintain those reader views at publication time. The
labels overlap deliberately: one identifies the challenge, the other a common
response whose freshness and recovery costs still need explanation.

## Transfer to trading systems carefully

The registry includes read/write scaling, real-time updates, multi-step
workflows, transactions, low latency, reliability/correctness, networking,
write fan-out, and time-series systems. Each entry records a trading application
and a caveat. Read these when choosing a tag rather than importing a web-system
technique unchanged:

- A stale cached social post is not equivalent to a stale risk limit. Establish
  the allowed staleness and authority before using the same read-scaling idea.
- A queue can absorb an alert burst, but queueing an order does not remove its
  latency deadline or make overload disappear. Admission, expiry, and recovery
  remain part of the design.
- Timestamped logs, metric samples, and market events have different query and
  ordering needs. A time-series tag does not automatically imply a specialized
  database, nor does an event timestamp establish a total order.

These are navigation and transfer hints, not another foundations textbook. Use
the companion handbook for mechanism-level teaching and related questions for
worked interview practice. Keep a general-purpose question general-purpose;
mention the trading difference only when it helps the reader apply the lesson.

## Extend the registry

Add a stable slug, readable label, challenge, trading application, and caveat
when a genuinely new recurring challenge is needed. Check overlap with existing
patterns first. Preserve existing IDs so catalog links and future similarity
features remain stable. Validation rejects unknown or repeated metadata IDs;
the catalog exposes questions grouped by pattern. Pattern overlap is useful
retrieval context, not evidence that two questions are duplicates.
