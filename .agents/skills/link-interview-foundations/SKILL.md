---
name: link-interview-foundations
description: "Link an interview question to the companion handbook (by chapter number and title), to earlier questions in the system-design track, or to authoritative external sources. Use when a draft relies on C++ concurrency, memory, networking, market-data, low-latency, replay, or trading-system foundations that should be applied rather than retaught."
---

# Link Interview Foundations

The handbook teaches mechanisms. Interview questions apply them. A good link
lets the chapter stay short *and* tells the reader exactly where the deeper
explanation lives.

## Inputs

- The selected question and the concepts it relies on.
- [Handbook map](references/foundations-map.md): chapter numbers, display titles, IDs, and the sections worth pointing at.
- `taxonomy/design-moves.yaml` and `content/system-design/TRACK.md` for links between questions.

## Choosing the target

1. **An earlier question in the track** when the reader needs to recall a *design move* ("the idempotency key from Q1"). Link the question and name the move by its taxonomy label.
2. **The handbook** when the reader needs the *mechanism* underneath (memory ordering, gap recovery, clock domains).
3. **A primary source** (standard, specification, official documentation, a named paper) when the handbook does not cover it or an exact claim needs support.
4. Wikipedia only for orientation on a stable general term — never as authority.

## Link format

Handbook links name the chapter the way a reader of the printed book knows it:

```markdown
[Handbook Ch 23 — *The Book That Is Silently Wrong*](../../../release1/handbook-markdown/chapters/d3-sequence-and-gap-recovery/chapter.md)
```

Point at a part when it helps: "Handbook Ch 31, Part 3". After the first full
link in a chapter, "Handbook Ch 23" is enough.

Question links use the short track name:

```markdown
[Q4 Market Data Feed](../sd-market-data-feed/question.md)
```

## Placement rules

- Link at the point of use, in the same paragraph that applies the idea. Never in a closing bibliography.
- One sentence of application per link: say what the reader will find and how it bears on *this* design.
- The header block lists the three or four handbook chapters that matter most; the body links the rest.
- Record handbook IDs in `metadata.yaml` `handbook_chapters`; the validator checks them against `curriculum.yaml`.

## Outputs and edit boundary

Edit only the selected package's `question.md` and `metadata.yaml`
(`handbook_chapters`, `prerequisites`, `related_questions`). Preserve sources,
expert notes, review decisions, and status. Do not edit the handbook or generated guides.

## Validation

```bash
python -m tools.validate --id <id>     # local links, handbook IDs, knowledge graph
make sd-preview                        # links render as labelled references
```
