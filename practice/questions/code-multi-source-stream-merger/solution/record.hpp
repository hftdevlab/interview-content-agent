#pragma once

#include <cstdint>
#include <string>

struct Record {
    std::uint64_t ts_ns;
    std::uint32_t source_id;
    std::string payload;

    bool operator==(const Record&) const = default;
};

