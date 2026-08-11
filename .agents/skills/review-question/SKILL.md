---
name: review-question
description: "Review a system-design, coding, or C++ fundamentals question for technical correctness, interview realism, reasoning flow, concision, source fidelity, links, diagrams, and runnable-code consistency. Use before requesting human approval or after expert feedback changes a package."
---

# Review Question

Review against the source, expert notes, and rendered reader experience—not
just against the schema.

## Inputs

- The full selected package, including preserved sources and expert notes.
- `content/STYLE_GUIDE.md`, the type schema, taxonomy, related questions, and
  linked practice package.
- The rendered preview for page and diagram inspection.

## Review order

1. Verify prompt fidelity, sanitization, and all stated assumptions.
2. Check the reasoning chain: contract, tested skills, human thought process,
   primary solution, meaningful improvements, then pitfalls and follow-ups.
3. Verify technical claims, complexity, failure behavior, and good-versus-great
   distinctions. Prefer primary specifications for unstable or exact claims.
4. Check interview calibration and remove material that does not affect a
   decision, invariant, or realistic follow-up.
5. Enforce the page budget and the limit of three improvements and three
   follow-ups.
6. Reconcile code prose with headers, tests, diagrams, metadata, and links.
7. Record actionable findings in `review.yaml`. Set `agent_reviewed` true only
   after all agent-fixable issues are resolved.

Never set `human_reviewed`, `technical_accuracy_reviewed`, or
`interview_realism_reviewed`. Never change status to `approved` or `published`.

## Outputs and edit boundary

Prefer a findings report. When asked to fix issues, edit only the selected
package's `question.md`, `metadata.yaml`, `review.yaml`, and Mermaid sources,
plus its linked practice package when required. Preserve source files and
expert notes verbatim. Do not edit generated output by hand.

## Validation

Run the applicable checks:

```bash
python -m tools.validate --id <id>
make practice-test
make pdf-preview
make all
```

Inspect the relevant PDF pages after any content or diagram change and report
which items still require human judgment.
