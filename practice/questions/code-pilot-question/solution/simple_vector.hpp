#pragma once

#include <cstddef>
#include <limits>
#include <new>
#include <stdexcept>
#include <utility>

template <typename T>
class SimpleVector {
public:
    typedef std::size_t size_type;

    SimpleVector() noexcept : data_(nullptr), size_(0), capacity_(0) {}

    ~SimpleVector() {
        release_storage();
    }

    SimpleVector(const SimpleVector&) = delete;
    SimpleVector& operator=(const SimpleVector&) = delete;

    SimpleVector(SimpleVector&& other) noexcept
        : data_(other.data_),
          size_(other.size_),
          capacity_(other.capacity_) {
        other.data_ = nullptr;
        other.size_ = 0;
        other.capacity_ = 0;
    }

    SimpleVector& operator=(SimpleVector&& other) noexcept {
        if (this != &other) {
            release_storage();
            data_ = other.data_;
            size_ = other.size_;
            capacity_ = other.capacity_;
            other.data_ = nullptr;
            other.size_ = 0;
            other.capacity_ = 0;
        }
        return *this;
    }

    size_type size() const noexcept { return size_; }
    size_type capacity() const noexcept { return capacity_; }
    bool empty() const noexcept { return size_ == 0; }

    T& operator[](size_type index) noexcept { return data_[index]; }
    const T& operator[](size_type index) const noexcept { return data_[index]; }

    T& at(size_type index) {
        if (index >= size_) {
            throw std::out_of_range("SimpleVector index out of range");
        }
        return data_[index];
    }

    const T& at(size_type index) const {
        if (index >= size_) {
            throw std::out_of_range("SimpleVector index out of range");
        }
        return data_[index];
    }

    void push_back(const T& value) {
        if (size_ == capacity_) {
            const size_type source_index = index_of(&value);
            reserve(next_capacity());
            const T& source =
                source_index < size_ ? data_[source_index] : value;
            ::new (static_cast<void*>(data_ + size_)) T(source);
        } else {
            ::new (static_cast<void*>(data_ + size_)) T(value);
        }
        ++size_;
    }

    void push_back(T&& value) {
        if (size_ == capacity_) {
            const size_type source_index = index_of(&value);
            reserve(next_capacity());
            T& source = source_index < size_ ? data_[source_index] : value;
            ::new (static_cast<void*>(data_ + size_)) T(std::move(source));
        } else {
            ::new (static_cast<void*>(data_ + size_)) T(std::move(value));
        }
        ++size_;
    }

    void reserve(size_type requested) {
        if (requested <= capacity_) {
            return;
        }
        if (requested > max_capacity()) {
            throw std::length_error("SimpleVector capacity is too large");
        }

        T* replacement = static_cast<T*>(
            ::operator new(requested * sizeof(T)));
        size_type constructed = 0;
        try {
            for (; constructed < size_; ++constructed) {
                ::new (static_cast<void*>(replacement + constructed))
                    T(std::move(data_[constructed]));
            }
        } catch (...) {
            destroy_prefix(replacement, constructed);
            ::operator delete(replacement);
            throw;
        }

        destroy_prefix(data_, size_);
        ::operator delete(data_);
        data_ = replacement;
        capacity_ = requested;
    }

    void clear() noexcept {
        destroy_prefix(data_, size_);
        size_ = 0;
    }

private:
    static void destroy_prefix(T* data, size_type count) noexcept {
        while (count != 0) {
            --count;
            (data + count)->~T();
        }
    }

    static size_type max_capacity() noexcept {
        return std::numeric_limits<size_type>::max() / sizeof(T);
    }

    size_type next_capacity() const {
        const size_type maximum = max_capacity();
        if (size_ == maximum) {
            throw std::length_error("SimpleVector capacity is too large");
        }
        if (capacity_ == 0) {
            return 1;
        }
        return capacity_ > maximum / 2 ? maximum : capacity_ * 2;
    }

    size_type index_of(const T* address) const noexcept {
        for (size_type index = 0; index < size_; ++index) {
            if (data_ + index == address) {
                return index;
            }
        }
        return size_;
    }

    void release_storage() noexcept {
        clear();
        ::operator delete(data_);
        data_ = nullptr;
        capacity_ = 0;
    }

    T* data_;
    size_type size_;
    size_type capacity_;
};
