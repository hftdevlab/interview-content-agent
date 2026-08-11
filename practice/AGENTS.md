# Practice-area instructions

- Compile as portable C++20 unless a question explicitly teaches a documented
  platform-specific mechanism.
- Keep `starter/` and `solution/` independent. Candidate-facing files must not
  include, copy, import, or reveal the reference implementation.
- Give starters a complete API contract and buildable scaffolding. Use an
  explicit unimplemented behavior when the behavioral suite is expected to
  reject the untouched starter.
- Test reference behavior, boundary cases, failure/lifecycle states, and the
  material complexity or concurrency invariant. Avoid tests coupled only to one
  implementation detail.
- Register every runnable package in `practice/CMakeLists.txt`; its metadata and
  content link must agree with the question package.
- Use deterministic tests. Bound concurrency tests with timeouts and avoid
  sleep-based correctness assumptions where synchronization can express the
  condition.
- Keep warnings enabled and treat compiler diagnostics as design feedback.
- Run `make practice-test` after C++ or CMake changes. Run
  `make practice-sanitize` for ownership, bounds, lifetime, or concurrency
  changes where UBSan adds useful coverage.
- Preserve any human-written test or solution notes unless the human editor
  explicitly replaces them.
