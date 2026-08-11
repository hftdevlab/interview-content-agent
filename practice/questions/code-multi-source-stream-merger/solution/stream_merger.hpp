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
