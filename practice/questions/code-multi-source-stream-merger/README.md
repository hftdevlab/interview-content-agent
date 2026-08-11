# Multi-source stream merger practice

Implement a non-blocking k-way merger whose sources may be temporarily silent.
The starter exposes the required API and builds, but deliberately does not
implement the ordering behavior. The reference solution validates per-source
ordering and passes the public tests.

From the repository root:

```bash
cmake -S practice -B build/practice
cmake --build build/practice
ctest --test-dir build/practice --output-on-failure
```

Question-specific targets:

```bash
cmake --build build/practice --target stream_merger_starter
cmake --build build/practice --target stream_merger_solution
cmake --build build/practice --target stream_merger_test
ctest --test-dir build/practice -R stream_merger_test --output-on-failure
ctest --test-dir build/practice -R stream_merger_starter_rejected --output-on-failure
```

The contract deliberately distinguishes temporary unavailability from
exhaustion. A strict merger must return `std::nullopt` whenever a live source
has neither a buffered head nor a watermark.

The `stream_merger_starter_rejected` test is intentionally marked
`WILL_FAIL`. It passes at the CTest level only while the unchanged starter
fails the behavioral suite; if the starter accidentally contains the complete
answer, the gate fails.
