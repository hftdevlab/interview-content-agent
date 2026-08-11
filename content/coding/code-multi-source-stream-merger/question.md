# Merge Multiple Temporarily Available Ordered Record Sources

## Interview prompt

Implement `StreamMerger` over several ordered `RecordSource` objects. A source
may temporarily return `std::nullopt` while still alive; only
`is_exhausted()` means EOF. `StreamMerger::next()` must not block or spin. It
returns the next globally safe record, or `std::nullopt` when no record is safe
yet.

## API contract

`Record` and `RecordSource` are given:

```cpp
struct Record {
    std::uint64_t ts_ns;
    std::uint32_t source_id;
    std::string payload;
};

class RecordSource {
public:
    virtual std::optional<Record> next() = 0;
    virtual bool is_exhausted() const = 0;
    virtual ~RecordSource() = default;
};
```

The candidate implements:

```cpp
class StreamMerger {
public:
    explicit StreamMerger(
        std::vector<std::unique_ptr<RecordSource>> sources);

    std::optional<Record> next();
    bool is_exhausted() const;
};
```

`next() == std::nullopt` has two meanings: temporary lack of a safe record when
`!is_exhausted()`, or permanent completion when `is_exhausted()`.

## Constraints

- Each source is non-decreasing by `ts_ns`; equal timestamps are valid.
- One merger thread owns and polls all sources.
- Each call makes at most one polling attempt per unbuffered source.
- Ties use `source_id`, then source index, for deterministic output.
- Decreasing input is a source-contract violation and should be detected.

## Examples

```text
source A: 1, 4, 7
source B: 2, 3, 9
output:   1, 2, 3, 4, 7, 9
```

The important boundary case is temporary silence:

```text
source A: nullopt, then 5
source B: 10

first merger.next(): nullopt
later output:         5, 10
```

Returning `10` on the first call is unsafe because A's unknown head may be
smaller.

## Clarifications a candidate should ask

- Does source `nullopt` mean EOF? No; check `is_exhausted()` separately.
- Must the merger block until every source has data? No; it returns immediately.
- Are equal timestamps allowed? Yes; use a deterministic tie-breaker.
- Are watermarks available? Not in the baseline API.

## Primary approach

The familiar part is a k-way merge: keep one head per source in a min-heap,
emit the minimum, then refill the source that produced it. The extra difficulty
is proving that the minimum is safe.

The key invariant is:

> Every source is either exhausted or represented by exactly one buffered head.

Only when the invariant holds may the heap minimum be emitted. If any live
source has no head, poll it once and return `nullopt` if it remains unknown.
Continue polling the other sources once so their progress is retained.

Required state follows directly:

- a min-heap of `(record, source_index)`;
- one buffered flag and last-seen timestamp per source;
- ownership of all sources.

Trace the hard case before coding: first buffer B's `10` but return `nullopt`;
on the next call buffer A's `5`, emit `5`, then later emit `10` after A is
refilled or exhausted.

## Reference solution

The given `Record` and `RecordSource` headers are not repeated. The candidate's
class design and implementation are:

### `stream_merger.hpp`

```cpp
#pragma once

#include "record_source.hpp"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <queue>
#include <vector>

class StreamMerger {
public:
    explicit StreamMerger(
        std::vector<std::unique_ptr<RecordSource>> sources);

    std::optional<Record> next();
    bool is_exhausted() const;

private:
    struct HeapItem {
        Record record;
        std::size_t source_index;
    };

    struct HeapCompare {
        bool operator()(const HeapItem& lhs, const HeapItem& rhs) const;
    };

    bool try_fill_source(std::size_t source_index);
    bool try_fill_all_sources();

    std::vector<std::unique_ptr<RecordSource>> sources_;
    std::vector<bool> has_buffered_record_;
    std::vector<std::optional<std::uint64_t>> last_seen_ts_;
    std::priority_queue<HeapItem, std::vector<HeapItem>, HeapCompare> heap_;
};
```

### `stream_merger.cpp`

```cpp
#include "stream_merger.hpp"

#include <stdexcept>
#include <utility>

bool StreamMerger::HeapCompare::operator()(
    const HeapItem& lhs,
    const HeapItem& rhs) const {
    if (lhs.record.ts_ns != rhs.record.ts_ns) {
        return lhs.record.ts_ns > rhs.record.ts_ns;
    }
    if (lhs.record.source_id != rhs.record.source_id) {
        return lhs.record.source_id > rhs.record.source_id;
    }
    return lhs.source_index > rhs.source_index;
}

StreamMerger::StreamMerger(
    std::vector<std::unique_ptr<RecordSource>> sources)
    : sources_(std::move(sources)),
      has_buffered_record_(sources_.size(), false),
      last_seen_ts_(sources_.size(), std::nullopt) {}

bool StreamMerger::try_fill_source(std::size_t i) {
    if (has_buffered_record_[i]) {
        return true;
    }

    auto& source = sources_[i];
    if (source->is_exhausted()) {
        return true;
    }

    std::optional<Record> record = source->next();
    if (!record.has_value()) {
        return source->is_exhausted();
    }

    if (last_seen_ts_[i] && record->ts_ns < *last_seen_ts_[i]) {
        throw std::logic_error("source emitted a decreasing timestamp");
    }

    last_seen_ts_[i] = record->ts_ns;
    heap_.push(HeapItem{std::move(*record), i});
    has_buffered_record_[i] = true;
    return true;
}

bool StreamMerger::try_fill_all_sources() {
    bool all_ready_or_done = true;
    for (std::size_t i = 0; i < sources_.size(); ++i) {
        if (!try_fill_source(i)) {
            all_ready_or_done = false;
        }
    }
    return all_ready_or_done;
}

std::optional<Record> StreamMerger::next() {
    if (!try_fill_all_sources() || heap_.empty()) {
        return std::nullopt;
    }

    HeapItem item = heap_.top();
    heap_.pop();
    has_buffered_record_[item.source_index] = false;
    return std::move(item.record);
}

bool StreamMerger::is_exhausted() const {
    if (!heap_.empty()) {
        return false;
    }
    for (const auto& source : sources_) {
        if (!source->is_exhausted()) {
            return false;
        }
    }
    return true;
}
```

`priority_queue::top()` returns `const&`, so this clear baseline copies the
small `HeapItem` before moving out its `Record`. An indexed heap can remove that
copy if profiling shows it matters.

## Complexity analysis

For `N` sources, a call scans up to `N` source states and performs at most one
heap pop plus new pushes: `O(N + N log N)` in the worst refill pass and
`O(N + log N)` when only one source needs refilling. Memory is `O(N)`.

## Alternative approaches

- For a small fixed number of sources, store one head per source and linearly
  scan for the minimum; the safety invariant is unchanged.
- With readiness notifications, poll only signaled sources, but an unknown live
  source still blocks strict ordering without a watermark or timeout policy.

## Common mistakes

- Treating source `nullopt` as EOF.
- Emitting the smallest available head while another live head is unknown.
- Buffering multiple records from one source.
- Spinning on a silent source or stopping the poll loop too early.
- Reversing the `priority_queue` comparator.
- Claiming `O(log N)` while scanning all sources.

## Optional improvements

- Add source watermarks so a candidate record can be released when every
  unknown source promises not to produce an earlier timestamp.
- Separate strict, deadline-based, and best-effort emission policies from source
  polling.
- Replace copied heap records with handles into per-source head storage only if
  record-copy cost is material.

## Follow-up questions

- **Why can one silent source stop the merger?** Its unseen head has no lower
  bound and may precede the heap minimum.
- **How do you guarantee progress?** Add a watermark, deadline, source-removal
  rule, or explicitly weaker ordering contract.
- **What tests matter most?** The `A: nullopt then 5, B: 10` case, empty and
  exhausted inputs, equal timestamps, decreasing input, and deterministic ties.

## Related C++ knowledge

Ownership with `unique_ptr`, `optional` versus EOF, comparator direction,
move/copy behavior of `priority_queue::top()`, and exception policy for a
violated source contract.

## Related design patterns

This is k-way merge over source Adapters. Production variants may use Strategy
for emission policy and a reactor for readiness, but the invariant matters more
than the pattern names.

## Practice repository

[`practice/questions/code-multi-source-stream-merger`](../../../practice/questions/code-multi-source-stream-merger/README.md)
