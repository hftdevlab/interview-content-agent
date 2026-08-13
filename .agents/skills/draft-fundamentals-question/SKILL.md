---
name: draft-fundamentals-question
description: "Draft or substantially revise a C++ systems, concurrency, operating-system, networking, or low-latency fundamentals question. Use when a content/fundamentals package needs a learning-first explanation, precise guarantees, an illustrative example, and an optional runnable experiment."
---

# Draft Fundamentals Question

Make technical learning the main product. Interview-answer advice is a short
communication layer over the explanation.

## Inputs

- The selected package's metadata, question, source, and expert notes.
- `content/STYLE_GUIDE.md`, schemas, taxonomy, and related questions.
- Relevant handbook or authoritative sources chosen with
  `$link-interview-foundations`.
- Human-approved entries in `editorial-memory.yaml` scoped to fundamentals or
  all questions. Apply them when relevant; current source and human notes win.

## Workflow

1. Start from the governing C++ language, OS, protocol, or hardware rule.
2. Separate portable guarantees from implementation-specific behavior.
3. Give a concise interview answer, then explain causality with a trace,
   litmus test, state transition, or focused code example.
4. Explain why tempting alternatives fail. For atomics, justify each memory
   order with the required happens-before relationship.
5. Add at most three strong-answer improvements and three follow-ups.
6. Add a runnable experiment only when it tests a material claim and state what
   a passing run does and does not prove.
7. When `workflow.yaml` shows a `contentctl` run, do not edit it; keep status
   `draft` and every review flag false because the controller owns lifecycle
   transitions and independent review. Otherwise return the package to
   `needs_human_review`; never set human review flags.

Avoid recreating foundational handbook chapters. Apply the foundation to this
question and link it.

## Outputs and edit boundary

Edit only the selected package's `question.md`, `metadata.yaml`, and
`review.yaml`. Preserve `source/` and `expert-notes.md`. Use
`$build-practice-question` for runnable files; never hand-edit generated output.

During a feedback-driven `contentctl` revision, do not edit
`editorial-memory.yaml` or `memory-candidates.yaml`. In the structured stage
result, propose at most three reusable lessons only when the newest human
feedback supports a general rule; return none for question-specific feedback.

## Validation

Run:

```bash
python -m tools.validate --id <id>
make pdf-preview
```

When an experiment is linked, also run `make practice-test` and
`make practice-sanitize` where it provides relevant coverage. Inspect the
rendered chapter, then run `make all` after a substantial revision.
During a `contentctl` run, keep the agent turn to targeted package and
question-specific experiment checks. The controller runs PDF and repository-wide
gates once before independent review.
