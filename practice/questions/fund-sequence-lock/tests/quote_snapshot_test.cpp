#include "quote_snapshot.hpp"

#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

namespace {

[[noreturn]] void fail(const std::string& message) {
    std::cerr << "FAILED: " << message << '\n';
    std::exit(1);
}

void expect(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

bool is_consistent(const Quote& quote) {
    return quote.ask_ticks == quote.bid_ticks + 1
        && quote.exchange_ts_ns
            == static_cast<std::uint64_t>(quote.bid_ticks) * 10U;
}

void test_single_thread_publication() {
    SequenceSnapshot snapshot;
    const Quote expected{101, 102, 1010};
    snapshot.publish(expected);
    expect(snapshot.read() == expected, "single-thread snapshot is incorrect");
}

void test_concurrent_readers_observe_complete_generations() {
    SequenceSnapshot snapshot;
    snapshot.publish(Quote{0, 1, 0});

    constexpr std::int64_t update_count = 50000;
    constexpr std::size_t reader_count = 4;
    std::atomic<bool> start{false};
    std::atomic<bool> done{false};
    std::atomic<bool> inconsistent{false};

    std::vector<std::thread> readers;
    readers.reserve(reader_count);
    for (std::size_t i = 0; i < reader_count; ++i) {
        readers.emplace_back([&] {
            while (!start.load(std::memory_order_acquire)) {
                std::this_thread::yield();
            }
            while (!done.load(std::memory_order_acquire)) {
                if (!is_consistent(snapshot.read())) {
                    inconsistent.store(true, std::memory_order_release);
                    return;
                }
            }
            if (!is_consistent(snapshot.read())) {
                inconsistent.store(true, std::memory_order_release);
            }
        });
    }

    std::thread writer([&] {
        while (!start.load(std::memory_order_acquire)) {
            std::this_thread::yield();
        }
        for (std::int64_t value = 1; value <= update_count; ++value) {
            snapshot.publish(Quote{
                value,
                value + 1,
                static_cast<std::uint64_t>(value) * 10U,
            });
        }
        done.store(true, std::memory_order_release);
    });

    start.store(true, std::memory_order_release);
    writer.join();
    for (auto& reader : readers) {
        reader.join();
    }

    expect(!inconsistent.load(), "a reader observed a torn generation");
    expect(
        snapshot.read()
            == Quote{update_count, update_count + 1,
                     static_cast<std::uint64_t>(update_count) * 10U},
        "final snapshot is incorrect");
}

void test_multiple_writers_are_serialized() {
    SequenceSnapshot snapshot;
    snapshot.publish(Quote{0, 1, 0});

    constexpr std::int64_t writes_per_thread = 10000;
    std::atomic<bool> inconsistent{false};
    std::atomic<bool> done{false};

    std::thread reader([&] {
        while (!done.load(std::memory_order_acquire)) {
            if (!is_consistent(snapshot.read())) {
                inconsistent.store(true, std::memory_order_release);
                return;
            }
        }
    });

    std::thread first([&] {
        for (std::int64_t value = 1; value <= writes_per_thread; ++value) {
            snapshot.publish(Quote{
                value,
                value + 1,
                static_cast<std::uint64_t>(value) * 10U,
            });
        }
    });
    std::thread second([&] {
        for (std::int64_t value = 100001;
             value < 100001 + writes_per_thread;
             ++value) {
            snapshot.publish(Quote{
                value,
                value + 1,
                static_cast<std::uint64_t>(value) * 10U,
            });
        }
    });

    first.join();
    second.join();
    done.store(true, std::memory_order_release);
    reader.join();

    expect(!inconsistent.load(), "serialized writers produced a torn snapshot");
    expect(is_consistent(snapshot.read()), "final multi-writer snapshot is invalid");
}

}  // namespace

int main() {
    try {
        test_single_thread_publication();
        test_concurrent_readers_observe_complete_generations();
        test_multiple_writers_are_serialized();
    } catch (const std::exception& error) {
        fail(std::string("unexpected exception: ") + error.what());
    }
    std::cout << "all sequence snapshot tests passed\n";
    return 0;
}

