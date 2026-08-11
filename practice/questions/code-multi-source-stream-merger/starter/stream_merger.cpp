#include "stream_merger.hpp"

#include <utility>

StreamMerger::StreamMerger(
    std::vector<std::unique_ptr<RecordSource>> sources)
    : sources_(std::move(sources)) {}

std::optional<Record> StreamMerger::next() {
    // TODO(candidate): buffer one head per live source and emit only when safe.
    return std::nullopt;
}

bool StreamMerger::is_exhausted() const {
    // TODO(candidate): account for both source state and buffered records.
    return false;
}

