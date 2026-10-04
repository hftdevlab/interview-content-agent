#pragma once

#include <cstddef>
#include <exception>
#include <stdexcept>
#include <utility>

template <typename T>
class SimpleVector {
public:
    typedef std::size_t size_type;

    SimpleVector() noexcept = default;
    ~SimpleVector() = default;

    SimpleVector(const SimpleVector&) = delete;
    SimpleVector& operator=(const SimpleVector&) = delete;
    SimpleVector(SimpleVector&&) noexcept = default;
    SimpleVector& operator=(SimpleVector&&) noexcept = default;

    size_type size() const noexcept { return 0; }
    size_type capacity() const noexcept { return 0; }
    bool empty() const noexcept { return true; }

    T& operator[](size_type) noexcept { std::terminate(); }
    const T& operator[](size_type) const noexcept { std::terminate(); }

    T& at(size_type) {
        throw std::logic_error("TODO(candidate): implement checked access");
    }

    const T& at(size_type) const {
        throw std::logic_error("TODO(candidate): implement checked access");
    }

    void push_back(const T&) {
        throw std::logic_error("TODO(candidate): copy-construct one element");
    }

    void push_back(T&&) {
        throw std::logic_error("TODO(candidate): move-construct one element");
    }

    void reserve(size_type) {
        throw std::logic_error("TODO(candidate): reallocate the live prefix");
    }

    void clear() noexcept {
        // TODO(candidate): destroy every live element without releasing capacity.
    }
};
