---
name: draft-coding-question
description: "Draft or substantially revise a C++ coding or API-design interview question, including the candidate's reasoning, complete required implementation, complexity, pitfalls, and focused follow-ups. Use for content/coding packages that need an interview-ready chapter before human review."
---

# Draft Coding Question

Derive the implementation from the contract and invariant. Keep the finished
chapter concise enough to rehearse.

## Inputs

- The package's metadata, current question, source, and expert notes.
- `content/STYLE_GUIDE.md`, applicable schema and taxonomy files.
- Existing practice API or tests when the package is already runnable.

## Workflow

1. Clarify inputs, outputs, ownership, invalid input, lifecycle, and material
   constraints.
2. Identify the central invariant and trace a boundary case before presenting
   code.
3. Develop one clear primary solution from the reasoning.
4. Include every header, declaration, member, helper, and implementation step
   the candidate must supply. Do not repeat code already given in the prompt.
5. State time and space complexity in terms of the actual operations.
6. Keep at most three improvements and three realistic follow-ups. Omit weak
   alternatives that do not teach a meaningful trade-off.
7. Reconcile the prose with any runnable API and tests.
8. Return the package to `needs_human_review`; never set human review flags.

The rendered chapter must fit six pages.

## Outputs and edit boundary

Edit only the selected package's `question.md`, `metadata.yaml`, and
`review.yaml`. Preserve `source/` and `expert-notes.md`. Use
`$build-practice-question` for files under `practice/`; do not hand-edit
`generated/` or `dist/`.

## Validation

Run:

```bash
python -m tools.validate --id <id>
make pdf-preview
```

If practice is linked, also run `make practice-test`. Inspect the rendered
chapter for duplicate code and page count, then run `make all` after a major
revision.
