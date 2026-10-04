---
name: draft-system-design
description: "Draft or substantially revise a system-design interview chapter for hedge-fund and trading engineers: a short problem statement, requirements, entities, API, a design built one requirement at a time with growing diagrams, and two or three deep dives that show the trade-offs between defensible answers. Each chapter stands alone, teaches named design moves, and links related questions by title and the companion handbook by chapter. Use for content/system-design packages before human review."
---

# Draft a System-Design Chapter

A chapter teaches **transferable design moves** through one interview question.
When the reader finishes, they can run this interview, explain why every box
exists, and reuse the moves on a question they have never seen.

It is not a specification, and it is not an answer to memorise.

## Inputs

- The package: `metadata.yaml`, `question.md` (if revising), `expert-notes.md`, `source/`, `feedback/`.
- `content/STYLE_GUIDE.md` (shared tone rules).
- [Chapter skeleton](references/chapter-skeleton.md) — required shape and word budgets.
- [Before and after](references/before-after.md) — what a wall of text looks like and how to fix it.
- [Finance lens](references/finance-lens.md) — where a trading firm changes the answer.
- `taxonomy/design-moves.yaml` and `content/system-design/TRACK.md` — the knowledge graph across questions.
- `$link-interview-foundations` for handbook links.
- Human-approved entries in `editorial-memory.yaml` scoped to system design or
  all questions. Apply them when relevant; current source and human notes win.

Human notes, feedback, and the original source win over everything here.
Flag contradictions instead of resolving them silently.

## Step 1 — Plan before prose

Write this plan into `review.yaml` `review_notes` before drafting. If any line is
hard to write, the chapter is not ready.

1. **Crux:** the one hard thing, in one sentence.
2. **Interpretation:** for an ambiguous prompt, the trading-firm reading and why.
3. **Moves:** 3–6 moves this chapter introduces, and the moves from other questions it reuses.
4. **Deep dives:** 2–3, each mapped to one non-functional requirement.
5. **Finance lens:** the one place a trading context changes a decision (or "none").

Record moves in `metadata.yaml` as `design_moves.introduces` / `design_moves.reuses`,
the track position as `track_order`, and handbook IDs as `handbook_chapters`.

## Step 2 — Write to the skeleton

Required `##` sections, in order (see the skeleton for budgets):

1. `## The question` — prompt verbatim, then at most ~120 words: what it is, who uses it, **the crux in bold**. Add a `### Domain primer` only when the purpose of the system depends on domain knowledge (a risk limit, an order book). Scope and assumptions belong in Requirements.
2. `## Requirements` — `### Functional requirements` (2–4, numbered) and `### Non-functional requirements` (3–5, numbered, with numbers). One "Out of scope" line each. A back-of-envelope table only when its result changes a decision.
3. `## Core entities` — one line per entity, then one short paragraph on the relationship that matters.
4. `## API` — the few calls or messages the flows need, as code blocks with one or two sentences each. Use a message contract instead of REST when that is the real interface.
5. `## High-level design` — one `###` step per functional requirement. Each step: a numbered flow, a figure that adds components, two or three short paragraphs on the choices. End with `### What is still broken`, a numbered list that sets up the deep dives.
6. `## Deep dives` — 2–3 `###` questions an interviewer would ask. Each: a concrete scenario, the naive option and where it breaks, the better option(s), a comparison table when two mechanisms compete, and **one bolded sentence** worth repeating in the interview.
7. `## Interview calibration` — what a passing answer covers and what a strong answer adds.
8. `## Follow-ups` — at most three; question in bold, answer in a blockquote.

There is no closing summary of moves. Moves live in their callouts and in metadata.

## Step 3 — The writing rules that matter

1. **One idea per paragraph.** Lead with the claim. Four sentences, about 80 words, at most.
2. **Break prose every ~200 words** with a list, table, figure, code block, or callout.
3. **Build, then break, then fix.** Show the simplest design that works, run a concrete scenario through it until it fails, then improve it. The reader should feel the need before seeing the fix.
4. **Show how candidates actually get there.** When the best design is not obvious, present the answers a typical candidate reaches first — usually two simple, defensible options — with what each costs, before the refinement. Never present the expert answer as if it were the natural first idea.
5. **Say when no answer is perfect.** Name the trade-off, the requirement that decides it, and what would change the decision. A well-argued judgement is the strong answer; a pretend-perfect design is not.
6. **Numbers once, where they decide.** Labelled assumptions ("assume 2,000/s during a storm"), then what the arithmetic teaches ("FIFO drains in 200 s, so the page misses its 5 s target").
7. **State an assumption once.** Do not re-caveat it in later sections.
8. **Name real tools as examples** (Postgres, Kafka, Aeron, ClickHouse) and say why that class of tool fits. Never as a shopping list.
9. **Voice:** an instructor building the design with the reader — "we" while designing, "you" for interview advice, "I" for a judgement call. No narration about the chapter itself.
10. **Callouts are short and typed:** `> **Design move — <label>.**`, `> **Finance lens.**`, `> **In the interview.**`. Two to five per chapter.
11. **Give the simple option its strongest form before rejecting it.** If a tuned version of the first answer works at this scale, say so and argue for the refinement on what it still cannot do. A refinement justified by a weak strawman is the first thing an expert interviewer attacks.
12. **Trace every failure through the fix.** For concurrency and failure arguments, replay the scenario step by step against the proposed fix and ask what still gets through — a fencing token does not stop a stale write that lands *first*. Put the residual risk in the comparison table.
13. **Make the numbers agree.** Every scenario must be feasible under the chapter's own workload: deadlines against capacity, versions against commit order, times across sections. Recompute after every edit.

## Step 4 — Stand alone, but connect

Readers open whichever question they are preparing for. Every chapter must make
sense on its own.

- **Introduce** a move in full with a `Design move` callout: the rule and its cost. The validator checks that every move in `design_moves.introduces` has one.
- **Reuse** a move by explaining it in a sentence or two right here, then linking the question that develops it, **by title**: "a caller-chosen idempotency key, which [Design a Notification System](../sd-notification-system/question.md) builds in full". Never write "Q1" or "as we saw earlier"; the validator rejects question numbers.
- **Header block:** level and time, what the reader will learn, related questions by title (optional), and the most relevant handbook chapters. No "question N of M", no "builds on".
- **Link the handbook** where the mechanism lives, by number and title:
  `[Handbook Ch 23 — *The Book That Is Silently Wrong*](../../../release1/handbook-markdown/chapters/d3-sequence-and-gap-recovery/chapter.md)`.
  Apply the concept here; do not re-teach it.
- Record moves in metadata only from `taxonomy/design-moves.yaml`. Propose new moves in `review.yaml` rather than inventing them in prose.

## Step 5 — Diagrams

- 3–5 figures, Graphviz sources in `diagrams/*.dot`. Use `role=new` for components added in this step, `role=warn` for failure paths, `role=store` for data stores, `role=ext` for systems we do not own.
- High-level design figures grow step by step; the new parts are highlighted.
- Number edge labels to match the numbered flow next to the figure.
- Deep-dive figures show ordering or state (a sequence, a state machine), not another box list.
- Each figure gets a caption and alt text in `metadata.yaml`. Put the figure after the paragraph that sets it up.

## Length

3,000–4,500 prose words (the lint counts paragraphs only). Cut repetition and
caveats before cutting a step of reasoning.

## Outputs and edit boundary

Edit only `question.md`, `metadata.yaml`, `review.yaml`, and `diagrams/*` in the
selected package. Preserve `source/`, `expert-notes.md`, and `feedback/`. Do not
edit generated files by hand.

Lifecycle: when `workflow.yaml` shows a `contentctl` run, do not edit it; keep
status `draft` and every review flag false, because the controller owns lifecycle
transitions and independent review. Otherwise set status `needs_human_review`
with only `agent_reviewed` true.

During a feedback-driven `contentctl` revision, do not edit
`editorial-memory.yaml` or `memory-candidates.yaml`. In the structured stage
result, propose at most three reusable lessons only when the newest human
feedback supports a general rule; return none for question-specific feedback.

## Validation

```bash
python -m tools.validate --id <id>
python -m tools.lint_readability content/system-design/<id>/question.md
make diagrams
make sd-preview          # read the rendered PDF, not the Markdown
```

The lint must report zero errors. Treat warnings as edits to make unless the
paragraph is a deliberate exception you can justify in `review.yaml`.

During a `contentctl` run, run the targeted package checks above only; the
controller renders previews and runs repository-wide gates once before
independent review.
