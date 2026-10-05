#include "simple_vector.hpp"

#include <cstdlib>
#include <exception>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>

namespace {

[[noreturn]] void fail(const std::string& message) {
    std::cerr << "FAILED: " << message << '\n';
    std::exit(EXIT_FAILURE);
}

void expect(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename T>
void move_assign(SimpleVector<T>& destination, SimpleVector<T>&& source) {
    destination = std::move(source);
}

struct Probe {
    static int alive;
    static int moves;

    explicit Probe(int value_in) : value(value_in) { ++alive; }
    Probe(const Probe&) = delete;
    Probe& operator=(const Probe&) = delete;

    Probe(Probe&& other) noexcept : value(other.value) {
        other.value = -1;
        ++alive;
        ++moves;
    }

    Probe& operator=(Probe&&) = delete;
    ~Probe() { --alive; }

    int value;
};

int Probe::alive = 0;
int Probe::moves = 0;

struct CopyMoveProbe {
    static int copies;
    static int moves;

    explicit CopyMoveProbe(int value_in) : value(value_in) {}

    CopyMoveProbe(const CopyMoveProbe& other) : value(other.value) {
        ++copies;
    }

    CopyMoveProbe(CopyMoveProbe&& other) noexcept : value(other.value) {
        other.value = -1;
        ++moves;
    }

    CopyMoveProbe& operator=(const CopyMoveProbe&) = delete;
    CopyMoveProbe& operator=(CopyMoveProbe&&) = delete;

    int value;
};

int CopyMoveProbe::copies = 0;
int CopyMoveProbe::moves = 0;

struct ThrowingMove {
    static int alive;
    static int moves;
    static int throw_on_move;

    explicit ThrowingMove(int value_in) : value(value_in) { ++alive; }
    ThrowingMove(const ThrowingMove&) = delete;
    ThrowingMove& operator=(const ThrowingMove&) = delete;

    ThrowingMove(ThrowingMove&& other) {
        ++moves;
        if (throw_on_move != 0 && moves == throw_on_move) {
            throw std::runtime_error("scripted move failure");
        }
        value = other.value;
        other.value = -1;
        ++alive;
    }

    ThrowingMove& operator=(ThrowingMove&&) = delete;
    ~ThrowingMove() { --alive; }

    int value;
};

int ThrowingMove::alive = 0;
int ThrowingMove::moves = 0;
int ThrowingMove::throw_on_move = 0;

void test_growth_and_access() {
    SimpleVector<int> values;
    expect(values.empty(), "a default vector should be empty");
    expect(values.size() == 0, "a default vector should have size zero");

    std::size_t observed_capacity = values.capacity();
    std::size_t growth_events = 0;
    for (int value = 0; value < 1024; ++value) {
        values.push_back(value);
        if (values.capacity() != observed_capacity) {
            observed_capacity = values.capacity();
            ++growth_events;
        }
        expect(values.size() == static_cast<std::size_t>(value + 1),
               "push_back should increase size exactly once");
        expect(values.capacity() >= values.size(),
               "capacity must cover every live element");
    }
    expect(growth_events < 128,
           "automatic growth should be geometric rather than one slot at a time");

    for (std::size_t index = 0; index < values.size(); ++index) {
        expect(values[index] == static_cast<int>(index),
               "growth must preserve element order and values");
    }

    const std::size_t old_capacity = values.capacity();
    values.reserve(old_capacity + 50);
    expect(values.capacity() >= old_capacity + 50,
           "reserve should provide the requested capacity");
    values.reserve(1);
    expect(values.capacity() >= old_capacity + 50,
           "reserve should never shrink capacity");

    const SimpleVector<int>& read_only = values;
    expect(read_only.at(17) == 17, "const checked access returned the wrong value");

    bool threw = false;
    try {
        static_cast<void>(values.at(values.size()));
    } catch (const std::out_of_range&) {
        threw = true;
    }
    expect(threw, "at(size()) must throw out_of_range");
}

void test_lvalue_and_rvalue_overloads() {
    SimpleVector<CopyMoveProbe> values;
    values.reserve(4);

    CopyMoveProbe lvalue(11);
    CopyMoveProbe::copies = 0;
    CopyMoveProbe::moves = 0;
    values.push_back(lvalue);
    expect(CopyMoveProbe::copies == 1 && CopyMoveProbe::moves == 0,
           "the const-reference overload should copy an lvalue");

    CopyMoveProbe::copies = 0;
    CopyMoveProbe::moves = 0;
    values.push_back(CopyMoveProbe(22));
    expect(CopyMoveProbe::copies == 0 && CopyMoveProbe::moves == 1,
           "the rvalue-reference overload should move an rvalue");
    expect(values[0].value == 11 && values[1].value == 22,
           "push_back overloads stored the wrong values");
}

void test_move_only_elements() {
    SimpleVector<std::unique_ptr<int> > values;
    values.push_back(std::unique_ptr<int>(new int(11)));
    values.push_back(std::unique_ptr<int>(new int(22)));
    values.reserve(8);

    expect(values.size() == 2, "move-only elements should survive growth");
    expect(*values[0] == 11 && *values[1] == 22,
           "move-only values changed during growth");
}

void test_self_aliasing_during_growth() {
    SimpleVector<std::string> values;
    values.reserve(2);
    values.push_back(std::string("alpha"));
    values.push_back(std::string("beta"));
    values.push_back(values[0]);
    expect(values[2] == "alpha",
           "an lvalue element argument should survive growth before copying");

    values.push_back(std::string("padding"));
    values.push_back(std::move(values[1]));
    expect(values[4] == "beta",
           "an rvalue element argument should be rebound after growth");
}

void test_lifetime_and_clear() {
    expect(Probe::alive == 0, "probe test must start without live objects");
    Probe::moves = 0;
    {
        SimpleVector<Probe> values;
        values.push_back(Probe(3));
        values.push_back(Probe(5));
        values.reserve(16);

        expect(Probe::alive == 2, "only vector elements should remain alive");
        expect(Probe::moves >= 2, "elements should be move-constructed");
        expect(values[0].value == 3 && values[1].value == 5,
               "reallocation changed probe values");

        const std::size_t capacity = values.capacity();
        values.clear();
        expect(values.empty(), "clear should reset size");
        expect(values.capacity() == capacity, "clear should retain storage");
        expect(Probe::alive == 0, "clear should destroy every live element");

        values.push_back(Probe(8));
        expect(Probe::alive == 1, "cleared storage should be reusable");
    }
    expect(Probe::alive == 0, "the vector destructor should destroy its elements");
}

void test_vector_move_ownership() {
    SimpleVector<int> source;
    source.push_back(7);
    source.push_back(9);

    SimpleVector<int> moved(std::move(source));
    expect(source.empty() && source.capacity() == 0,
           "move construction should reset the source");
    expect(moved.size() == 2 && moved[0] == 7 && moved[1] == 9,
           "move construction should transfer the allocation");

    SimpleVector<int> destination;
    destination.push_back(100);
    destination = std::move(moved);
    expect(moved.empty() && moved.capacity() == 0,
           "move assignment should reset the source");
    expect(destination.size() == 2 && destination[1] == 9,
           "move assignment should replace the destination state");

    move_assign(destination, std::move(destination));
    expect(destination.size() == 2 && destination[0] == 7,
           "self move-assignment should preserve a valid vector");
}

void test_throwing_move_keeps_valid_state() {
    expect(ThrowingMove::alive == 0,
           "throwing-move test must start without live objects");
    {
        SimpleVector<ThrowingMove> values;
        values.push_back(ThrowingMove(1));
        values.push_back(ThrowingMove(2));
        const std::size_t old_capacity = values.capacity();

        ThrowingMove::moves = 0;
        ThrowingMove::throw_on_move = 2;
        bool threw = false;
        try {
            values.reserve(old_capacity + 4);
        } catch (const std::runtime_error&) {
            threw = true;
        }
        ThrowingMove::throw_on_move = 0;

        expect(threw, "the scripted reallocation move should throw");
        expect(values.size() == 2 && values.capacity() == old_capacity,
               "failed reserve must retain its committed shape");
        expect(ThrowingMove::alive == 2,
               "failed reserve leaked or destroyed a live element");
        expect(values.at(1).value == 2,
               "an element not yet moved should retain its value");
        values.clear();
    }
    expect(ThrowingMove::alive == 0,
           "throwing-move cleanup should leave no live objects");
}

void test_impossible_capacity_is_rejected() {
    SimpleVector<unsigned long long> values;
    bool threw = false;
    try {
        values.reserve(std::numeric_limits<std::size_t>::max());
    } catch (const std::length_error&) {
        threw = true;
    }
    expect(threw, "an impossible capacity should throw length_error");
    expect(values.empty(), "a rejected reserve should leave the vector empty");
}

}  // namespace

int main() {
    try {
        test_growth_and_access();
        test_lvalue_and_rvalue_overloads();
        test_move_only_elements();
        test_self_aliasing_during_growth();
        test_lifetime_and_clear();
        test_vector_move_ownership();
        test_throwing_move_keeps_valid_state();
        test_impossible_capacity_is_rejected();
    } catch (const std::exception& error) {
        fail(std::string("unexpected exception: ") + error.what());
    }
    std::cout << "all SimpleVector tests passed\n";
    return EXIT_SUCCESS;
}
