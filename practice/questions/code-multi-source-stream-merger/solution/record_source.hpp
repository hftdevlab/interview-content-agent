#pragma once

#include "record.hpp"

#include <optional>

class RecordSource {
public:
    virtual std::optional<Record> next() = 0;
    virtual bool is_exhausted() const = 0;
    virtual ~RecordSource() = default;
};

