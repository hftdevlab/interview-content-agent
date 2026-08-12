---
name: build-practice-question
description: "Create, complete, or repair a runnable C++20 practice package for a coding question or suitable fundamentals experiment. Use when starter code, a reference solution, behavioral tests, CMake registration, metadata linkage, or sanitizer verification is required."
---

# Build Practice Question

Keep candidate and reference implementations physically separate and make the
tests enforce the interview contract.

## Inputs

- A reviewed coding or fundamentals package with a settled API or experiment.
- The relevant explanation, edge cases, complexity claims, and expert notes.
- Existing practice files, if any.

## Workflow

1. Read `practice/AGENTS.md` and the selected content package.
2. If no package exists, run:

   ```bash
   python -m tools.create_practice_question --id <id>
   ```

3. Replace the generic scaffold with the question-specific C++20 API,
   candidate implementation stub, reference solution, and behavioral tests.
4. Keep starter headers complete but free of reference algorithms or leaked
   constants. Preserve human-written solution and test notes.
5. Cover normal, boundary, invalid/lifecycle, ordering, and concurrency behavior
   when each is material. Keep concurrent tests deterministic and bounded.
6. Confirm root CMake registration, practice metadata, and the content link all
   name the same targets and path.

## Outputs and edit boundary

Edit only `practice/questions/<id>/`, `practice/CMakeLists.txt`, and the selected
content package's practice link and metadata. Do not alter other exercises,
source archives, expert notes, or generated guides.

## Validation

Run:

```bash
python -m tools.validate --id <id>
make practice-test
```

Run `make practice-sanitize` for ownership, bounds, lifetime, atomics, or
concurrency changes. Confirm the solution passes and the untouched starter is
rejected by the starter-negative gate. Finish substantial changes with
`make all`. During a `contentctl` run, do not edit `workflow.yaml`, lifecycle
status, or review flags. Run only the selected exercise's targets; the
controller runs the complete practice and repository gates once.
