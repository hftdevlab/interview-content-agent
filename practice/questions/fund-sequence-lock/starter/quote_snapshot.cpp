#include "quote_snapshot.hpp"

void SequenceSnapshot::publish(const Quote& quote) {
    // TODO(candidate): serialize writers and publish an odd/even generation.
    static_cast<void>(quote);
}

Quote SequenceSnapshot::read() const noexcept {
    // TODO(candidate): retry until both sequence observations match and are even.
    return {};
}

