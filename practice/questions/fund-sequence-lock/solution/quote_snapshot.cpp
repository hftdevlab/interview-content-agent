#include "quote_snapshot.hpp"

#include <cstdint>
#include <mutex>

void SequenceSnapshot::publish(const Quote& quote) {
    const std::lock_guard<std::mutex> lock(writer_mutex_);

    const std::uint64_t stable =
        sequence_.load(std::memory_order_seq_cst);
    sequence_.store(stable + 1, std::memory_order_seq_cst);

    bid_ticks_.store(quote.bid_ticks, std::memory_order_seq_cst);
    ask_ticks_.store(quote.ask_ticks, std::memory_order_seq_cst);
    exchange_ts_ns_.store(
        quote.exchange_ts_ns, std::memory_order_seq_cst);

    sequence_.store(stable + 2, std::memory_order_seq_cst);
}

Quote SequenceSnapshot::read() const noexcept {
    for (;;) {
        const std::uint64_t before =
            sequence_.load(std::memory_order_seq_cst);
        if ((before & 1U) != 0U) {
            continue;
        }

        const Quote copy{
            bid_ticks_.load(std::memory_order_seq_cst),
            ask_ticks_.load(std::memory_order_seq_cst),
            exchange_ts_ns_.load(std::memory_order_seq_cst),
        };

        const std::uint64_t after =
            sequence_.load(std::memory_order_seq_cst);
        if (before == after) {
            return copy;
        }
    }
}

