# Expert notes

- The source discussion emphasized that `next() == std::nullopt` is temporary
  unavailability, not necessarily end-of-stream.
- The strict baseline should block emission when any live source has no known
  head. Watermarks belong in improvements, not in the baseline contract.
- Human review is still required before this fixture becomes an approved
  template.

