---
name: draft-system-design
description: "Draft or substantially revise a normalized system-design interview question with an invariant-led good solution, focused deep dives, diagrams, trade-offs, and realistic follow-ups. Use for content/system-design packages that need an interview-ready answer before human review."
---

# Draft System Design Question

Write for a real interview conversation, not for schema completion.

## Inputs

- The package's `metadata.yaml`, `question.md`, `expert-notes.md`, and `source/`.
- `content/STYLE_GUIDE.md`, relevant taxonomy, and related questions.
- Relevant foundations selected with `$link-interview-foundations`.

Human notes and original source are authoritative. Flag contradictions rather
than resolving them silently.

## Workflow

1. Settle the system boundary, core requirements, scale, and failure contract.
2. State prominently when the full platform is too large for one interview;
   sketch it, then offer a few likely deep dives for agreement.
3. Explain what is tested and develop the candidate's reasoning toward a
   minimal correct design.
4. Deepen the decisions that control correctness or performance. Keep adjacent
   subsystems concise.
5. Express at most three great improvements and three realistic follow-ups.
   Do not repeat the good solution.
6. Add Mermaid only where a diagram clarifies architecture, ownership, or an
   event sequence. Give it a caption, alt text, and metadata entry.
7. Set status to `needs_human_review`; set only `agent_reviewed` true and leave
   all human review flags false.

A typical chapter must fit ten rendered pages. A genuinely complex flagship
question may use up to fourteen when the extra pages contain interview-relevant
decisions rather than prerequisite tutorials.

## Outputs and edit boundary

Edit only `question.md`, `metadata.yaml`, `review.yaml`, and `diagrams/*.mmd`
inside the selected package. Preserve `source/` and `expert-notes.md`. Do not
edit rendered SVGs, catalogs, PDFs, or other generated artifacts by hand.

## Validation

Run:

```bash
python -m tools.validate --id <id>
make diagrams
make pdf-preview
```

Inspect the rendered chapter for page count, diagram legibility, and density.
Finish with `make all` after a substantial revision.
