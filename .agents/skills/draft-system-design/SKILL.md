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
- Human-approved entries in `editorial-memory.yaml` scoped to system design or
  all questions. Apply them when relevant; current source and human notes win.

Human notes and original source are authoritative. Flag contradictions rather
than resolving them silently.

## Workflow

1. Settle the system boundary, core requirements, scale, and failure contract.
2. Open the answer with one concrete running scenario: named actors,
   illustrative values, and a visible consequence. Reuse it through the major
   decisions; do not introduce architecture vocabulary first.
3. Execute the simplest plausible design and show the exact step where the
   scenario violates correctness, boundedness, or latency. Derive the central
   invariant from that failure rather than announcing it as a premise.
4. Define each uncommon term in plain language on first use and attach every
   abstract component to a process, thread, file, queue, connection, or memory
   structure before it appears in a diagram.
5. State prominently when the full platform is too large for one interview;
   sketch it, then offer a few likely deep dives for agreement.
6. Explain what is tested and develop the candidate's reasoning toward a
   minimal correct design.
7. Use symbolic requirements but concrete exposition. Add illustrative
   arithmetic and state what it reveals about the scarce resource. Present
   defensible forks before adjudicating them from the contract.
8. Mark material inline as **Core**, **Deep dive**, or **Stretch**. Lead each
   paragraph with its thesis, then mechanism, then sufficiency; vary density
   with traces and plain-language restatements.
9. Deepen the decisions that control correctness or performance. Keep adjacent
   subsystems concise.
10. Express at most three great improvements and three realistic follow-ups.
   Do not repeat the good solution.
11. Add Mermaid only when labeled edges, ownership, ordering, or failure states
   teach more than prose. Place it after the complete reasoning unit it depicts;
   do not strand half a section before a forced landscape page. Give it a
   caption, alt text, and metadata entry.
12. When `workflow.yaml` shows a `contentctl` run, do not edit it; keep status
   `draft` and every review flag false because the controller owns lifecycle
   transitions and independent review. Otherwise set status to
   `needs_human_review`, set only `agent_reviewed` true, and leave all human
   review flags false.

A typical chapter must fit ten rendered pages. A genuinely complex flagship
question may use up to fourteen when the extra pages contain interview-relevant
decisions rather than prerequisite tutorials.

## Outputs and edit boundary

Edit only `question.md`, `metadata.yaml`, `review.yaml`, and `diagrams/*.mmd`
inside the selected package. Preserve `source/` and `expert-notes.md`. Do not
edit rendered SVGs, catalogs, PDFs, or other generated artifacts by hand.

During a feedback-driven `contentctl` revision, do not edit
`editorial-memory.yaml` or `memory-candidates.yaml`. In the structured stage
result, propose at most three reusable lessons only when the newest human
feedback supports a general rule; return none for question-specific feedback.

## Validation

Run:

```bash
python -m tools.validate --id <id>
make diagrams
make pdf-preview
```

Inspect the rendered chapter for page count, diagram legibility, and density.
Finish with `make all` after a substantial revision. During a `contentctl` run,
run targeted package checks only; the controller renders PDFs and runs
repository-wide gates once before independent review.
