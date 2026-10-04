# Move-aware vector practice

Implement the candidate-owned `SimpleVector<T>` API in
`starter/simple_vector.hpp`. The starter is buildable but deliberately has no
storage or lifetime implementation. The separate reference header uses
C++11-era `::operator new`, placement new, explicit destructor calls, and
`::operator delete` to maintain one live prefix. It provides the basic exception
guarantee if moving an element during growth throws.

The behavioral suite covers normal growth, checked access, the lvalue/rvalue
`push_back` distinction, move-only values, self-aliasing across growth,
destruction and reuse, vector move ownership, partial-construction cleanup, and
impossible capacities. The reference header and tests also compile as C++11,
although the repository target remains C++20 as required by the practice area.

From the repository root:

```bash
cmake -S practice -B build/practice
cmake --build build/practice --target simple_vector_starter
cmake --build build/practice --target simple_vector_solution
cmake --build build/practice --target simple_vector_test
ctest --test-dir build/practice -R simple_vector_test --output-on-failure
ctest --test-dir build/practice -R simple_vector_starter_rejected --output-on-failure
```

`simple_vector_starter_rejected` is intentionally marked `WILL_FAIL`. It passes
at the CTest level only while the untouched starter fails the behavioral suite;
if candidate-facing files leak a working solution, the gate fails.
