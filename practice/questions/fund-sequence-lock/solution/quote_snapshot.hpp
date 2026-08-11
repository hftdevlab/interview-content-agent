#pragma once

#include <atomic>
#include <cstdint>
#include <mutex>

struct Quote {
    std::int64_t bid_ticks;
    std::int64_t ask_ticks;
    std::uint64_t exchange_ts_ns;

    bool operator==(const Quote&) const = default;
};

class SequenceSnapshot {
public:
    SequenceSnapshot() noexcept = default;

    void publish(const Quote& quote);
    Quote read() const noexcept;

private:
    std::mutex writer_mutex_;

    alignas(64) std::atomic<std::uint64_t> sequence_{0};
    std::atomic<std::int64_t> bid_ticks_{0};
    std::atomic<std::int64_t> ask_ticks_{0};
    std::atomic<std::uint64_t> exchange_ts_ns_{0};
};

