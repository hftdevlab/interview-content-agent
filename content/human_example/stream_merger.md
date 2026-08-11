Interview prompt

Implement \`StreamMerger\` over multiple \`RecordSource\` instances. Every source  
emits records in non-decreasing \`ts\_ns\` order, but a call to \`next()\` may return  
\`std::nullopt\` when the source is temporarily silent. Only \`is\_exhausted()\`  
means that the source has permanently ended.

\`StreamMerger::next()\` must be non-blocking. It returns the next record that is  
safe under global non-decreasing timestamp order, or \`std::nullopt\` when no  
record is currently safe.

\#\# API contract

\`\`\`cpp  
struct Record {  
    std::uint64\_t ts\_ns;  
    std::uint32\_t source\_id;  
    std::string payload;  
};

class RecordSource {  
public:  
    virtual std::optional\<Record\> next() \= 0;  
    virtual bool is\_exhausted() const \= 0;  
    virtual \~RecordSource() \= default;  
};

class StreamMerger {  
public:  
    explicit StreamMerger(  
        std::vector\<std::unique\_ptr\<RecordSource\>\> sources);

    std::optional\<Record\> next();  
    bool is\_exhausted() const;  
};  
\`\`\`

\`StreamMerger::next() \== std::nullopt\` means either “temporarily no globally  
safe record” or “fully exhausted.” Callers use \`is\_exhausted()\` to distinguish  
the two states.

\#\# Constraints

\- Each individual source is sorted by \`ts\_ns\`.  
\- Sources are polled; they do not provide readiness notifications.  
\- The merger must not spin or block inside \`next()\`.  
\- Timestamp order is non-decreasing. \`source\_id\` is used only as a deterministic  
  tie-breaker for currently buffered records.  
\- At most one head record per source is required.  
\- The baseline assumes source methods are called from one merger thread.

\#\# Examples

Two finite sources:

\`\`\`text  
source 1: 1, 4, 7  
source 2: 2, 3, 9  
output:   1, 2, 3, 4, 7, 9  
\`\`\`

A temporarily silent source:

\`\`\`text  
source 1: nullopt, then 5  
source 2: 10

first merger.next(): nullopt  
later output: 5, 10  
\`\`\`

Emitting \`10\` on the first call would be incorrect because source 1 can still  
produce the older timestamp \`5\`.

\#\# Clarifications a candidate should ask

\- Does \`nullopt\` mean temporary unavailability, end-of-stream, or both?  
It could mean both, the caller shouldn’t assume either case. Instead is\_exhausted() is the only method to tell whether a stream is finished or not.  
\- Is ordering by timestamp only, or by a total key such as  
  \`(timestamp, source\_id, sequence)\`?  
For this question, sort by timestamp is enough, but sort by a total key to make it stable is good to have.  
\- May a source produce duplicate timestamps?  
Assuming no.  
\- May \`next()\` block, and how does a caller distinguish pending from exhausted?  
next() must not block, a caller can only tell exhausted by calling the is\_exhausted() method  
\- Can the source provide a watermark or lower bound for future timestamps?  
No, that could be a follow up to solve though.  
\- Should the merger detect a source that violates its sorted-order contract?

\#\# Primary approach

The core task is: merge several individually sorted `RecordSource`s into one globally sorted stream by `ts_ns`.

The trick is that `RecordSource::next()` returning `nullopt` **does not mean end-of-stream**. It may just mean the source is temporarily silent. Only `is_exhausted()` means permanently done.Use one buffered “head” record per source, then a min-heap.

For strict timestamp ordering:

1. For each non-exhausted source, try to fetch one head record.  
2. If every active source has either:  
   * one buffered head record, or  
   * is exhausted,  
      then it is safe to emit the minimum timestamp record.  
3. If some source is alive but has no record available now, return `nullopt` instead of blocking.  
4. After emitting a record from source `i`, mark source `i` as needing refill next time.

Important tradeoff: without watermarks or a stronger API, you cannot both guarantee global ordering and keep emitting while another source is silent. A silent source might later produce an older timestamp.

\#\# Reference solution

**```` ``` ````**`stream_merger.hpp`

`#include <memory>`  
`#include <optional>`  
`#include <queue>`  
`#include <vector>`

`#include "record.hpp"`  
`#include "record_source.hpp"`

`class StreamMerger {`  
`public:`  
    `explicit StreamMerger(std::vector<std::unique_ptr<RecordSource>> sources);`

    `std::optional<Record> next();`

`private:`  
    `struct HeapItem {`  
        `Record record;`  
        `std::size_t source_index;`  
    `};`

    `struct HeapCompare {`  
        `bool operator()(const HeapItem& a, const HeapItem& b) const {`  
            `if (a.record.ts_ns != b.record.ts_ns) {`  
                `return a.record.ts_ns > b.record.ts_ns;  // min-heap by timestamp`  
            `}`

            `// Tie-breaker only for deterministic output.`  
            `return a.record.source_id > b.record.source_id;`  
        `}`  
    `};`

    `bool try_fill_source(std::size_t i);`  
    `bool try_fill_all_sources();`

    `std::vector<std::unique_ptr<RecordSource>> sources_;`

    `// true means this source currently has exactly one record in heap_.`  
    `std::vector<bool> has_buffered_record_;`

    `std::priority_queue<`  
        `HeapItem,`  
        `std::vector<HeapItem>,`  
        `HeapCompare`  
    `> heap_;`  
`};`  
```` ``` ````

```` ```stream_merger.cpp ````  
`#include "stream_merger.hpp"`

`#include <utility>`

`StreamMerger::StreamMerger(std::vector<std::unique_ptr<RecordSource>> sources)`  
    `: sources_(std::move(sources)),`  
      `has_buffered_record_(sources_.size(), false) {}`

`bool StreamMerger::try_fill_source(std::size_t i) {`  
    `// Already have this source's current head record in the heap.`  
    `if (has_buffered_record_[i]) {`  
        `return true;`  
    `}`

    `// Permanently finished. It no longer constrains global ordering.`  
    `if (sources_[i]->is_exhausted()) {`  
        `return true;`  
    `}`

    `// Try exactly once. Do not spin/block here.`  
    `std::optional<Record> rec = sources_[i]->next();`

    `if (rec.has_value()) {`  
        `heap_.push(HeapItem{std::move(*rec), i});`  
        `has_buffered_record_[i] = true;`  
        `return true;`  
    `}`

    `// next() returned nullopt. This may mean temporary silence.`  
    `// Check whether it also became permanently exhausted.`  
    `if (sources_[i]->is_exhausted()) {`  
        `return true;`  
    `}`

    `// Alive but currently has no record. We cannot safely emit anything,`  
    `// because this source may later produce a smaller timestamp.`  
    `return false;`  
`}`

`bool StreamMerger::try_fill_all_sources() {`  
    `bool all_ready_or_done = true;`

    `for (std::size_t i = 0; i < sources_.size(); ++i) {`  
        `if (!try_fill_source(i)) {`  
            `all_ready_or_done = false;`  
        `}`  
    `}`

    `return all_ready_or_done;`  
`}`

`std::optional<Record> StreamMerger::next() {`  
    `// Try to make sure every active source has a known head record.`  
    `if (!try_fill_all_sources()) {`  
        `// Not EOF necessarily. It means no globally safe record is available now.`  
        `return std::nullopt;`  
    `}`

    `// If all sources are exhausted and heap is empty, we are truly done.`  
    `if (heap_.empty()) {`  
        `return std::nullopt;`  
    `}`

    `HeapItem item = heap_.top();`  
    `heap_.pop();`

    `has_buffered_record_[item.source_index] = false;`

    `return std::move(item.record);`  
`}`  
```` ``` ````

\`priority\_queue::top()\` returns \`const&\`, so this simple version copies the  
\`HeapItem\` out of the heap and then moves its \`Record\` into the returned  
\`optional\`. Avoid a \`const\_cast\`; a more advanced implementation can select a  
heap container that permits moving elements if the copy is material.

The complete reference implementation and tests are in the linked practice  
package.

\#\# Complexity analysis

For \`N\` sources:

\- polling scan: \`O(N)\` per merger call;  
\- heap push and pop: \`O(log N)\`;  
\- buffered memory: \`O(N)\`.

With readiness notifications, the repeated scan can be reduced, but the  
one-known-head correctness rule remains.

\#\# Alternative approaches

A linear scan of buffered heads avoids a heap and costs \`O(N)\` to choose each  
record. It may be simpler and faster for a very small fixed source count.

An event-driven design can maintain a ready-source set instead of polling every  
source. This changes scheduling and latency behavior but does not resolve an  
unknown head from a silent source.

\#\# Common mistakes

\- Treating \`nullopt\` as end-of-stream without checking \`is\_exhausted()\`.  
\- Emitting the smallest available record while another active source has no head.  
\- Fetching several records from one source while ignoring other source heads.  
\- Using a max-heap comparator by accident.  
\- Forgetting a deterministic policy for equal timestamps.  
\- Spinning until a pending source produces data, violating the non-blocking API.  
\- Moving from \`priority\_queue::top()\` through \`const\_cast\`.  
\- Claiming \`O(log N)\` per call while still scanning all sources.

\#\# Optional improvements

\- Track each source's last observed timestamp and reject a decreasing record.  
\- Add a source watermark: “no future record is earlier than \`W\`.” A candidate  
  may be emitted when it is no greater than every unbuffered source's watermark.  
\- Use a readiness callback, file-descriptor event loop, or poll set to avoid  
  scanning inactive sources.  
\- Define a stale-source timeout and choose explicitly between strict ordering  
  and best-effort liveness.  
\- Add a full total-order key with a per-source sequence when duplicate  
  timestamps and source IDs are not enough.

Tracking only the last emitted timestamp is a weak lower bound. It usually  
allows additional equal-timestamp records through, but it does not solve the  
general silent-source problem.

\#\# Follow-up questions

\#\#\# Why can a pending source block a larger buffered timestamp?

It may later emit a smaller timestamp. Without a head or watermark, the merger  
has no safe lower bound for that source.

\#\#\# What happens if one source stays pending forever?

Strict ordering may return \`nullopt\` forever. The API needs a watermark,  
timeout, source-removal policy, or documented best-effort mode to improve  
liveness.

\#\#\# Why buffer only one record per source?

Because the earliest unseen record is the only record from that sorted source  
that can compete for the next global position. Prefetching may improve  
throughput but is not required for correctness.

\#\#\# Does \`last\_emitted\_ts\` make a pending source non-blocking?

Only for a candidate no greater than that lower bound. After a source emitted  
\`100\`, a buffered \`100\` can be safe under timestamp-only ordering, but \`120\`  
cannot be emitted because the pending source may next produce \`105\`.

\#\#\# How would you test the merger?

Cover one source, multiple finite sources, duplicates, empty inputs, temporary  
silence, pending-then-older data, exhaustion, a source-order violation, and a  
large source count. The critical test proves that a buffered \`10\` is not emitted  
before a temporarily silent source later yields \`5\`.

\#\# Related C++ knowledge

\- \`std::priority\_queue\` comparator direction and \`top()\` returning \`const&\`.  
\- \`std::optional\` as a value that needs a separate lifecycle state.  
\- \`std::unique\_ptr\` ownership of polymorphic sources.  
\- Move construction into \`std::optional\<Record\>\`.  
\- Exception behavior when validating a broken source contract.

\#\# Practice repository

See  
\[\`practice/questions/code-multi-source-stream-merger\`\](../../../practice/questions/code-multi-source-stream-merger/README.md)  
for the starter, reference solution, build target, and public tests.

