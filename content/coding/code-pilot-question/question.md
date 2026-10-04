# Implement a Move-Aware Vector

## Interview prompt

Implement a small `SimpleVector<T>`. The repository compiles it as C++20, but
the required solution should use only C++11-era language facilities. Focus on
constructors, destruction, ownership, and object reallocation. Do not use
`std::vector` or `std::allocator` as the backing store. You may assume `T` is
move-constructible and destructible; it need not be copyable or default
constructible.

This is a focused vector subset, not a request to reproduce every
`std::vector` feature.

## API contract

The candidate owns the complete class declaration and implementation. It must
provide:

- default construction, destruction, move construction, and move assignment;
- deleted copy construction and copy assignment;
- `size()`, `capacity()`, `empty()`, unchecked `operator[]`, and checked `at()`;
- `push_back(const T&)`, `push_back(T&&)`, `reserve(new_capacity)`, and
  `clear()`.

The lvalue overload copies and is usable when `T` is copy-constructible. The
rvalue overload moves and supports move-only values. `reserve()` never shrinks.
`at()` throws `std::out_of_range` for an invalid index, and an impossible
capacity throws `std::length_error`. Successful reallocation invalidates
references and pointers to elements. Automatic growth is geometric, so repeated
`push_back` is amortized `O(1)`; the exact factor is not part of the contract.
The container is single-threaded and supports types with fundamental alignment;
over-aligned allocation is outside the C++11-era baseline.

Allocation and element-construction exceptions propagate. If moving an element
during reallocation throws, the vector must remain valid, destructible, and
leak-free, but an earlier element may be moved from. This is the basic exception
guarantee; do not silently assume moving `T` is `noexcept`.

## What this tests

- separating allocated storage from the lifetimes of objects within it;
- applying RAII and move ownership without double destruction;
- understanding lvalue/rvalue overloads and explicit object construction;
- cleaning up a partially constructed replacement block after an exception.

## Clarifications a candidate should ask

- **Must the vector be copyable?** No. Container copying is outside the
  baseline, though `push_back(const T&)` naturally requires a copyable `T`.
- **Must it match the whole standard-library API?** No. Implement only the
  operations above.
- **What guarantee is required if an element move throws?** The basic
  guarantee: all original objects remain alive and the vector remains usable.
- **Should allocation use an array new-expression?** No. Obtain uninitialized bytes with
  `::operator new`, then start each element lifetime with placement new.

## Primary approach

Three values describe the state: `data_` points to storage for `capacity_`
objects, and exactly the prefix `[data_, data_ + size_)` contains live `T`
objects. The rest is storage, not a collection of default-constructed objects.
The invariant is: `0 <= size_ <= capacity_`; every element before `size_` is
alive exactly once, no later slot is alive, and this vector uniquely owns
`data_`.

This is why an ordinary `new T[capacity]` expression is the wrong primitive: it
both allocates and constructs `capacity` objects, requires default construction,
and makes capacity indistinguishable from size. Calling `::operator new(bytes)`
only allocates suitably aligned raw storage. Placement new constructs one `T` in
a chosen slot; an explicit destructor call ends that object's lifetime; and
`::operator delete` finally releases the storage. These operations must be
paired separately.

Trace the failure boundary before coding. With two live elements, `reserve(4)`
allocates replacement storage and moves the first element, then the second move
throws. Destroy the one new object and release the replacement bytes. Both old
objects are still alive, although the first may be moved from. Commit to the new
block only after every move succeeds.

The two `push_back` overloads differ only at final construction: a `const T&`
is copied, while a named `T&&` is still an lvalue expression and must be cast
with `std::move`. The implementation records an argument's index when it aliases
an existing element, then rebinds it after growth so it never uses a dangling
reference.

## Reference solution

The entire candidate-owned implementation fits in one C++11-compatible header:

```cpp
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

    T& operator[] (size_type index) noexcept { return data_[index]; }
    const T& operator[] (size_type index) const noexcept { return data_[index]; }

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
```

## Complexity analysis

Accessors, indexing, and vector move operations are `O(1)`. `clear()` destroys
`N` live elements. `reserve(C)` allocates `C * sizeof(T)` bytes and moves and
destroys `N` elements, so it is `O(N)` time with `O(C)` replacement storage.
Geometric growth makes `push_back` amortized `O(1)` and worst-case `O(N)` when
it reallocates. The self-alias scan is `O(N)` only when growth already costs
`O(N)`, so it does not change those bounds.

## Common mistakes

- Using `new T[capacity_]`, which constructs unused slots and requires a default
  constructor.
- Assigning into raw storage instead of starting a lifetime with placement new.
- Updating `data_` before every replacement element has been constructed.
- Destroying `size_` replacement slots after only a prefix was constructed.
- Forgetting that a named `T&&` is an lvalue and therefore needs `std::move`.
- Releasing storage without explicitly destroying its live objects first.

## Optional improvements

- Add `emplace_back(Args&&... args)`. For an lvalue argument, deduction makes
  `Args` a reference type and reference collapsing leaves an lvalue reference;
  for an rvalue, `Args` is a value type and the parameter remains an rvalue
  reference. `std::forward<Args>(args)...` uses that deduction to cast only the
  original rvalues, whereas `std::move(args)...` would cast every named argument
  and could unexpectedly move from caller-owned lvalues. Placement new then
  invokes the matching `T` constructor. Reallocation and self-aliasing still
  need the same lifetime discipline.
- When `T` is copyable but its move may throw, copy during growth in the style of
  `std::move_if_noexcept` to preserve the strong exception guarantee.
- Support over-aligned types: C++17 aligned allocation handles this directly;
  a C++11-only design needs a platform or allocator policy that guarantees the
  requested alignment.

## Follow-up questions

- How would you implement vector copy construction and copy assignment without
  exposing a half-copied destination after an exception?
- Why does `emplace_back` take forwarding references rather than only `T&&`, and
  what exactly does `std::forward` preserve?
- For a latency-sensitive hot path, when would you reserve or fix capacity so
  growth cannot occur during steady state, and what should happen on exhaustion?

## Evaluation criteria

A strong solution first states the live-prefix invariant and explains why
allocation and construction are separate. Give the most weight to paired
lifetimes, unique ownership, and cleanup of a partially constructed block. Then
look for correct lvalue/rvalue overload behavior, a safe commit point, checked
capacity arithmetic, and accurate complexity. A happy-path move loop that leaks,
double-destroys, or uses `new T[]` has not met the core contract; extra API polish
does not compensate for a broken lifetime invariant.

## Related foundation

[Preallocation and object pools](../../../release1/handbook-markdown/chapters/c2-preallocation-and-pools/chapter.md)
explains why a production low-latency path often removes dynamic growth from
steady state and requires an explicit exhaustion policy. This exercise stays
focused on correctly implementing growth when it is permitted.

## Practice repository

[Runnable C++20 practice package](../../../practice/questions/code-pilot-question/README.md)
