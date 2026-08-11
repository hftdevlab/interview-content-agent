#include "stream_merger.hpp"

#include <cstdlib>
#include <exception>
#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace {

class ScriptedSource final : public RecordSource {
public:
    explicit ScriptedSource(std::vector<std::optional<Record>> steps)
        : steps_(std::move(steps)) {}

    std::optional<Record> next() override {
        if (is_exhausted()) {
            return std::nullopt;
        }
        return std::move(steps_[cursor_++]);
    }

    bool is_exhausted() const override {
        return cursor_ == steps_.size();
    }

private:
    std::vector<std::optional<Record>> steps_;
    std::size_t cursor_{0};
};

std::unique_ptr<RecordSource> source(
    std::vector<std::optional<Record>> steps) {
    return std::make_unique<ScriptedSource>(std::move(steps));
}

Record record(
    std::uint64_t timestamp,
    std::uint32_t source_id,
    std::string payload = {}) {
    return Record{timestamp, source_id, std::move(payload)};
}

[[noreturn]] void fail(const std::string& message) {
    std::cerr << "FAILED: " << message << '\n';
    std::exit(1);
}

void expect(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void test_empty_merger() {
    StreamMerger merger({});
    expect(!merger.next().has_value(), "empty merger should return nullopt");
    expect(merger.is_exhausted(), "empty merger should be exhausted");
}

void test_merges_finite_sources() {
    std::vector<std::unique_ptr<RecordSource>> sources;
    sources.push_back(source({record(1, 1), record(4, 1), record(7, 1)}));
    sources.push_back(source({record(2, 2), record(3, 2), record(9, 2)}));
    StreamMerger merger(std::move(sources));

    const std::vector<std::uint64_t> expected{1, 2, 3, 4, 7, 9};
    for (const auto timestamp : expected) {
        const auto next = merger.next();
        expect(next.has_value(), "finite merge unexpectedly returned nullopt");
        expect(next->ts_ns == timestamp, "finite merge produced wrong order");
    }
    expect(!merger.next().has_value(), "exhausted merge should return nullopt");
    expect(merger.is_exhausted(), "finite merge should become exhausted");
}

void test_pending_source_blocks_unsafe_record() {
    std::vector<std::unique_ptr<RecordSource>> sources;
    sources.push_back(source({std::nullopt, record(5, 1)}));
    sources.push_back(source({record(10, 2)}));
    StreamMerger merger(std::move(sources));

    expect(
        !merger.next().has_value(),
        "pending source must block an unsafe buffered timestamp");
    const auto first = merger.next();
    expect(first.has_value() && first->ts_ns == 5, "recovered older record must lead");
    const auto second = merger.next();
    expect(second.has_value() && second->ts_ns == 10, "buffered record should follow");
}

void test_equal_timestamps_are_deterministic() {
    std::vector<std::unique_ptr<RecordSource>> sources;
    sources.push_back(source({record(8, 2)}));
    sources.push_back(source({record(8, 1)}));
    StreamMerger merger(std::move(sources));

    const auto first = merger.next();
    const auto second = merger.next();
    expect(first.has_value() && first->source_id == 1, "source id should break ties");
    expect(second.has_value() && second->source_id == 2, "second tie is incorrect");
}

void test_source_order_violation_is_detected() {
    std::vector<std::unique_ptr<RecordSource>> sources;
    sources.push_back(source({record(10, 1), record(9, 1)}));
    StreamMerger merger(std::move(sources));
    expect(merger.next().has_value(), "first ordered record should be emitted");

    bool threw = false;
    try {
        static_cast<void>(merger.next());
    } catch (const std::logic_error&) {
        threw = true;
    }
    expect(threw, "decreasing source timestamp must be rejected");
}

}  // namespace

int main() {
    try {
        test_empty_merger();
        test_merges_finite_sources();
        test_pending_source_blocks_unsafe_record();
        test_equal_timestamps_are_deterministic();
        test_source_order_violation_is_detected();
    } catch (const std::exception& error) {
        fail(std::string("unexpected exception: ") + error.what());
    }
    std::cout << "all stream merger tests passed\n";
    return 0;
}

