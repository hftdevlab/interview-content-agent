#pragma once

#include "record_source.hpp"

#include <memory>
#include <optional>
#include <vector>

class StreamMerger {
public:
    explicit StreamMerger(
        std::vector<std::unique_ptr<RecordSource>> sources);

    std::optional<Record> next();
    bool is_exhausted() const;

private:
    std::vector<std::unique_ptr<RecordSource>> sources_;
};
