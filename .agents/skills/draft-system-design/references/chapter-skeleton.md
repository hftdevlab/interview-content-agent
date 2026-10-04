# Chapter skeleton

The required shape of a system-design chapter, with a budget and a short example
for each part. Budgets are targets for a 45-minute question; a 60-minute flagship
may run about a third longer. The chapters in `content/system-design/` are the
reference implementations — read one before drafting. `sd-task-scheduler` and
`sd-timeseries-storage` show the "candidates' first answers, then the refinement"
pattern most fully.

Validation requires the `##` headings marked **required**, rejects references to other questions by number ("Q3"), and requires a `Design move — <label>` callout for every move the chapter introduces.

---

## Header block (required)

A short blockquote. It tells the reader what they will get and where to go next —
without assuming they have read anything else.

```markdown
> **Level:** Intermediate · 45 minutes
>
> **You will learn:** handing off the hot path · batching · partitioned logs · ...
>
> **Related questions:** [Design a Notification System](../sd-notification-system/question.md) · [Design a Low-Latency Market Data Feed and Normalization System](../sd-market-data-feed/question.md)
>
> **Handbook:** [Ch 10 — *The Handoff That Cannot Block*](../../../release1/handbook-markdown/chapters/b2-spsc-ring-buffer/chapter.md) · ...
```

Never "Question 2 of 5", "Q1", or "builds on": a chapter must work for a reader
who opens it first.

## `## The question` (required) — about 120 words, plus an optional primer

- The prompt verbatim, as a blockquote. Never edit it.
- Two to four short paragraphs: what the system is, who uses it, why it is hard.
- **The crux in one bold sentence.**
- One `> **Finance lens.**` callout when a trading firm changes the answer.
- `### Domain primer` only when the system's purpose depends on domain knowledge
  (a risk limit, an exchange feed). Keep it under ~200 words plus one small table,
  and end with the running scenario the chapter will reuse.

Do **not** put scope decisions, assumptions, retry semantics, or workload numbers
here. They belong in Requirements.

Example crux: **The crux: keep urgent alerts fast while bulk traffic surges, and never lose one.**

## `## Requirements` (required)

### `### Functional requirements` (required) — 2–4 numbered items
What users or callers can do. One "Out of scope:" line.

### `### Non-functional requirements` (required) — 3–5 numbered items
Each item is a property with a number. Before the list, state the workload as a
labelled assumption, and if the numbers drive the design, show a small table and
**say what the arithmetic teaches** in one bold sentence ("The network is not the
bottleneck. CPU time per message is."). One "Out of scope:" line.

## `## Core entities` (required) — a bullet list, then one paragraph

- **Name** — one-line definition.

Then one short paragraph on the relationship that matters, with a concrete example
("one critical alert to an eight-person desk is one notification and sixteen deliveries").

## `## API` — short pseudocode, then the parameters that matter

Show only what an interviewer will probe: the calls the flows need, the
parameters that change the design, and the metadata a caller gets back. The
programming language must never be the barrier to reading the design.

- Write calls as pseudocode or plain field lists:
  `read(series[], [t0, t1), columns[], as_of?)  ->  iterators`,
  `PriceUpdate { ticker, bid, ask, host_seq, publish_time }`. A REST call, a
  message contract, or short SQL is fine when that is the real interface.
- No class definitions, smart pointers, templates, `std::` containers,
  `virtual`, `alignas`, or memory-order arguments. Name the guarantee in words
  ("one store with release ordering") and link the handbook for the mechanism.
- When a memory layout *is* the design (a 64-byte event in shared memory),
  show it as a table of fields, sizes, and why — not as a struct.
- Keep each block under about 12 lines. After it, a short list of the two to
  four parameters that matter and the deep dive that uses each.

The lint warns on blocks over 15 lines and on language-specific constructs.

## `## High-level design` (required) — one `###` per functional requirement

Open with one sentence: we build the simplest design that works, one requirement at a time.

Each step:

1. A numbered flow (3–5 steps) a reader can follow with a finger.
2. A figure that adds components. New components use `role=new`; edge labels carry the step numbers.
3. Two or three short paragraphs explaining the choices: why this component exists,
   the alternative and why not, and the cost.
4. A `> **Design move — <label>.**` callout when the step introduces a move.

Close with `### What is still broken` — a numbered list, one line each, in the
order of the deep dives. When the question has a strong naive design (risk
limits), run the running scenario through it here and name the exact step where
it fails.

## `## Deep dives` (required) — 2–3 `###` questions

Title each as the question an interviewer would ask ("How does a critical page
arrive within 5 seconds during a storm?"). Each deep dive:

1. A concrete scenario with a time, names, and numbers (3–5 sentences).
2. The answers candidates usually give first, and exactly where each breaks or
   what it costs. Often there are two simple, defensible options pulling in
   opposite directions (one rigid schema vs. no schema; one queue vs. many).
3. The refinement, presented as an improvement a strong candidate reaches by
   noticing something specific — never as the obvious first idea. Use
   **Bad / Good / Great** labels only when there really are three; otherwise
   name the options.
4. A comparison table when two or more mechanisms serve one goal.
5. When no option is perfect, say so, name the requirement that decides, and
   what would change the decision.
6. **One bolded sentence** the reader should be able to say in the interview.
7. A short re-explanation plus a title link for any move another question
   teaches in full, and a handbook link where the mechanism lives.

Prefer a worked trace table (time, actor, state) over a sequence diagram.

## `## Interview calibration` — two short lists

**A passing answer** (3 bullets) and **A strong answer also** (4–6 bullets).
Write behaviours ("does the burst arithmetic"), not topics ("understands queues").
A passing answer usually picks one defensible simple option and knows its cost;
a strong answer reaches the refinement and argues the trade-off.

## `## Follow-ups` — at most 3, and the chapter ends here

```markdown
**Question in bold?**

> Answer in a blockquote: 3–5 sentences, ending with the move or principle it reuses.
```

There is no closing recap of design moves. They are taught in callouts and
recorded in `metadata.yaml`.

---

## Shape checks the lint enforces

`python -m tools.lint_readability <file>`:

- paragraph > 110 words → error; > 80 words or > 5 sentences → warning
- more than 320 words of uninterrupted prose → error; more than 220 → warning
- fewer than 2 figures → error

Typical pilot numbers: 1,200–1,600 paragraph words (3,300–4,500 words in total
including lists, tables, and code), mean paragraph 28–38 words, longest prose run
under 180 words, 4 figures, 4–9 tables, 10–13 callouts.
