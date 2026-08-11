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

bool StreamMerger::try_fill_source(std::size_t source_index) {
    if (has_buffered_record_[source_index]) {
        return true;
    }

    auto& source = sources_[source_index];
    if (source->is_exhausted()) {
        return true;
    }

    std::optional<Record> record = source->next();
    if (!record.has_value()) {
        return source->is_exhausted();
    }

    if (last_seen_ts_[source_index].has_value()
        && record->ts_ns < *last_seen_ts_[source_index]) {
        throw std::logic_error("source emitted a decreasing timestamp");
    }

    last_seen_ts_[source_index] = record->ts_ns;
    heap_.push(HeapItem{std::move(*record), source_index});
    has_buffered_record_[source_index] = true;
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
