---
name: review-question
description: "Review a system-design, coding, or C++ fundamentals question for technical correctness, interview realism, reader experience, knowledge-graph links, source fidelity, diagrams, and runnable-code consistency. Use before requesting human approval or after expert feedback changes a package."
---

# Review Question

Review against the source, the expert notes, and the **rendered** reader
experience — not just the schema. Every earlier pilot passed schema checks and
agent review while reading as a wall of text; this skill exists to catch that.

## Inputs

- The full package, including `source/`, `expert-notes.md`, and `feedback/`.
- `content/STYLE_GUIDE.md`, the type schema, taxonomy, related questions, and any linked practice package.
- For system design: `.agents/skills/draft-system-design/references/chapter-skeleton.md`,
  `taxonomy/design-moves.yaml`, and the rendered preview from `make sd-preview`.
- Human-approved `editorial-memory.yaml` entries matching the question type.

## Review order — all question types

1. **Fidelity.** Prompt verbatim, sanitised, and every assumption labelled once.
2. **Correctness.** Technical claims, complexity, failure behaviour. Prefer primary specifications for exact claims. Flag any number presented as fact that is really an assumption.
3. **Calibration.** Depth matches the interview length. Cut material that changes no decision and prepares for no realistic follow-up.
4. **Consistency.** Prose agrees with code, tests, diagrams, metadata, and links.
5. **Editorial memory.** Verify that relevant approved editorial-memory lessons were applied. Treat pending question-local candidates as proposals, not requirements.
6. **Record findings** in `review.yaml`. Set `agent_reviewed` true only after every agent-fixable issue is fixed.

## System design — the reader-experience gate

Run the deterministic checks first. Any error is a blocking finding:

```bash
python -m tools.validate --id <id>                        # skeleton, links, knowledge graph
python -m tools.lint_readability content/system-design/<id>/question.md
```

Then read the rendered PDF and answer each question with yes or no. A "no" is a
finding with a location and a concrete fix.

| # | Check | Typical fix |
|---|---|---|
| 1 | Is the question section about 120 words, ending in a bold crux, with no scope or workload detail? | Move assumptions into Requirements |
| 2 | If the system needs domain knowledge, is there a short primer with a running scenario? | Add `### Domain primer` |
| 3 | Do the non-functional requirements carry numbers, and does the arithmetic say what it teaches? | Add the one bold "what this tells us" sentence |
| 4 | Is the high-level design built one requirement at a time, each with a numbered flow and a growing figure? | Split into `###` steps; highlight new components |
| 5 | Does "What is still broken" set up exactly the deep dives that follow? | Align the list with the deep-dive titles |
| 6 | Does each deep dive start from a concrete scenario and show where the naive option breaks? | Add the scenario and the failing step |
| 7 | Where the best design is non-obvious, does the chapter show the answers candidates give first, what each costs, and only then the refinement — and say plainly when no option is perfect? | Add the simple options and a trade-off table |
| 8 | Is each simple option given its strongest form before it is rejected? | Concede what a tuned version handles; argue the refinement on what it cannot do |
| 9 | Has every failure scenario been replayed against the fix, with the residual risk stated? | Add the "what still gets through" column |
| 10 | Is there a comparison table wherever two mechanisms serve one goal? | Convert the comparing paragraph into a table |
| 11 | Does each deep dive have one bolded sentence worth repeating in the interview? | Add or sharpen it |
| 12 | Read only the first sentence of each paragraph. Do they form an argument? | Move buried theses to the front |
| 13 | Does the chapter stand alone? Each introduced move has a `Design move` callout; each reused move is re-explained in a sentence and links its question by title — never "Q3" or "as we saw earlier". | Add the explanation and title link |
| 14 | Recompute every number. Are scenarios feasible under the chapter's own workload, and do times, versions, and counts agree across sections? | Fix the scenario, not just the sum |
| 15 | Are handbook links labelled by chapter number and title, at the point of use, and applied rather than re-taught? | Relabel and apply |
| 16 | Is the finance lens placed at a decision it changes, and accurate? | Move or cut it |
| 17 | Do figures read at print size, with edge labels that match the numbered flows? | Re-layout top-down; shorten labels |
| 18 | Are caveats stated once, not repeated in every section? | Delete the repeats |

Do not demand an evaluator rubric, a failure matrix, a closing summary of
design moves, or more than three follow-ups. Do not accept an architecture that arrives complete in one diagram
with no derivation. Do not accept new design moves invented in prose: propose
them for `taxonomy/design-moves.yaml` instead.

## Coding and fundamentals

- Coding: the invariant comes before the data structure; every member, header, and lifecycle state the candidate must write is present; a boundary case is traced before the final code; at most three improvements and three follow-ups.
- Fundamentals: the governing language, OS, network, or hardware rule comes first; portable C++ is separated from platform behaviour; experiments are runnable.

## Never

Never set `human_reviewed`, `technical_accuracy_reviewed`, or
`interview_realism_reviewed`. Never change status to `approved` or `published`.
Never promote, reject, or rewrite editorial-memory records; those are explicit
human lifecycle decisions.

## Outputs and edit boundary

Prefer a findings report. When asked to fix issues, edit only the package's
`question.md`, `metadata.yaml`, `review.yaml`, and `diagrams/*`, plus its linked
practice package when required. Preserve `source/`, `expert-notes.md`, and
`feedback/` verbatim. Do not edit generated output by hand.

## Validation

```bash
python -m tools.validate --id <id>
python -m tools.lint_readability content/system-design/<id>/question.md   # system design
make practice-test                                                         # coding / fundamentals
make sd-preview                                                            # system design: read the PDF
make all
```

Report which items still need human judgment: interview realism, difficulty,
and any interpretation of an ambiguous prompt.
