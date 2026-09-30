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
- Human-approved `editorial-memory.yaml` entries matching the question type.

## Review order

1. Verify prompt fidelity, sanitization, and all stated assumptions.
2. Check the reasoning chain and reader experience for the question type.
   System design should move from question/clarifications to prioritized
   functional/non-functional requirements, entities, useful interfaces,
   architecture, and selected deep dives, not a filled-out answer specification.
3. Verify technical claims, complexity, and failure behavior. Comparisons are
   optional, not a demand for two complete solutions. Prefer primary
   specifications for unstable or exact claims.
4. Check interview calibration and remove material that does not affect a
   decision, invariant, or realistic follow-up.
5. For system design, reject a technically correct specification that does not
   teach. Can the reader follow one request or event through a complete
   high-level architecture before dealing with its hardest details? The flow
   and component reasoning should precede the architecture diagram, not merely
   explain a finished design after showing it. Require at least one diagram
   and verify that its edges agree with the walkthrough. Entities should be
   motivated by user operations or useful distinctions, then accurately
   defined with their relationships. APIs and important fields should follow
   from that flow rather than arrive as an unexplained table. Deep dives should answer the question's distinctive challenges
   and connect to its non-functional requirements. A simple design may be
   sufficient; do not demand optional production machinery or a contrived
   failure. Do not require numerical sizing when it would not change a choice;
   do require workload reasoning where throughput is a defining challenge.
   Flag a tiny assumed workload that evades the prompt's core problem. Where
   serialization matters, check the reason for the chosen wire representation,
   not just whether a JSON-shaped example looks valid.
   Validate the selected `design_patterns` against the registry and check that
   their displayed labels and deep-dive explanations match. A familiar pattern
   is not automatically safe on a trading hot path; check domain limits.
6. Test two or three central decisions as a reader: why is the choice needed,
   what relevant alternative was considered, why does this choice fit, and
   what cost or changed assumption could change it? Cite missing reasoning as
   an important issue even when every conclusion is technically correct. A
   first-person voice is required for system-design walkthroughs, but simply
   adding "I would" to prescriptions is not a fix. Look for a reusable decision
   principle developed in the explanation, not merely a pattern label or link.
   Preserve good derivations instead of expanding every sentence into a lesson.
   Read only the first sentence of each explanatory paragraph. They should form
   a coherent argument; buried theses and uniform maximum density are important
   findings, not cosmetic suggestions. This sweep alone cannot establish
   teaching quality: a coherent series of conclusions can still omit reasoning.
   Repeated depth labels, up-front symbol inventories, mandatory bad/good/great
   comparisons, and editorial process language can obscure the explanation.
   Require changes when those patterns materially interrupt the teaching flow;
   do not replace them with a rigid word-count or readability-score threshold.
7. Enforce the page budget and the limit of three optional improvements and
   follow-ups each; for the new system-design outline also cap optional pitfalls
   at three. Do not fail a tutorial for omitting those sections, an evaluation
   rubric, or a failure matrix. Inspect the rendered preview rather than trusting only its page
   count: literal Markdown markers, cramped leading, tangled diagrams, or
   mostly empty portrait pages created by diagram breaks are important issues.
   If an inspection surface appears to crop running page furniture, corroborate
   it against the actual raster pixels and positioned PDF text before filing a
   defect; do not confuse a viewer crop with missing PDF content.
   In an automated read-only agent review, do not invoke browser, image,
   screenshot, or raster-rendering tools and do not create scratch files. The
   controller owns raster QA. Use pypdf/pdfplumber on the existing PDF,
   positioned text, generated SVGs, and the deterministic PDF-gate result;
   display-tool limitations are not content failures.
8. Reconcile code prose with headers, tests, diagrams, metadata, and links.
9. Record actionable findings in `review.yaml`. Set `agent_reviewed` true only
   after all agent-fixable issues are resolved.
10. Verify that relevant approved editorial-memory lessons were applied. Treat
   pending question-local candidates as proposals, not requirements.

Never set `human_reviewed`, `technical_accuracy_reviewed`, or
`interview_realism_reviewed`. Never change status to `approved` or `published`.
Never promote, reject, or rewrite editorial-memory records; those are explicit
human lifecycle decisions.

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
