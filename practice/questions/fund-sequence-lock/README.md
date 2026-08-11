# Sequence-counted snapshot practice

Implement a consistent multi-field quote snapshot with serialized writers and
optimistic readers.

The learning order is deliberate:

1. make every shared payload field atomic;
2. use sequentially consistent operations to establish a simple proof;
3. test that concurrent readers never observe a torn field relationship;
4. only then consider weaker ordering or an alternative design.

Build and test from the repository root:

```bash
cmake -S practice -B build/practice
cmake --build build/practice --target sequence_snapshot_starter
cmake --build build/practice --target sequence_snapshot_solution
cmake --build build/practice --target sequence_snapshot_test
ctest --test-dir build/practice -R sequence_snapshot_test --output-on-failure
ctest --test-dir build/practice -R sequence_snapshot_starter_rejected --output-on-failure
```

The starter target compiles but does not implement the protocol. The reference
target is portable C++20; it does not copy Linux-kernel seqlock code or rely on
ordinary concurrently accessed payload fields.

The `sequence_snapshot_starter_rejected` test is intentionally marked
`WILL_FAIL`. It guards against accidentally shipping the solution in the
starter package.
