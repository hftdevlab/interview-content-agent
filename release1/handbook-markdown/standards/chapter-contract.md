# Chapter contract

Normative. Derived from the approved exemplars, not from theory.

**Exemplars:** `b2-spsc-ring-buffer` (code mode, one experiment) · `d3-sequence-and-gap-recovery` (pseudocode mode, quizzes, two-mechanism comparison)

Where this document and an exemplar disagree, **the exemplar wins** and this document is corrected. Rules trace to `author-feedback-log.md`.

---

## 0. Scope — what this contract does not govern

**Front matter is exempt.** The preface and chapter 1 are orientation pieces, not teaching chapters, and forcing them into this structure would damage both.

| | Preface | Chapter 1 | Teaching chapters |
|---|---|---|---|
| Section order (§2) | no | no | yes |
| `chapter_focus` at ~50% | no | no | yes |
| Quizzes | no | no | per brief |
| Interview mapping section | no | no | yes |
| When not to use | no | no | yes |
| Layering (core/deeper/optional) | no | no | yes |
| Claim taxonomy (§4) | **yes** | **yes** | yes |
| No invented numbers | **yes** | **yes** | yes |
| Cross-links resolve to `curriculum.yaml` | **yes** | **yes** | yes |
| Callback markers | n/a | n/a | yes |

What still binds both: **never invent a figure**, every claim typed, and every cross-reference must resolve.

**Preface rules.** Written for the reader's *career situation*, not for a technical topic. It orients someone deciding what to prepare for and why. Industry generalisations are stated as generalisations with the variance acknowledged — the failure mode is a confident taxonomy the reader repeats in an interview and is corrected on. No specific firm's practices, compensation figures, or hiring processes are asserted.

**Chapter 1 rules.** A bird's-eye anatomy, not a lesson. Its job is to give every later chapter a place to attach: each stage of the path names the engineering problem it creates, maps that problem to the CS concept the reader already knows, and points at the chapter that covers it. Breadth over depth throughout — where it would be natural to explain a mechanism, it names it and moves on. Density of forward anchors is a feature.

**Both are written with more author involvement than the pipeline provides**, and are revised whenever the curriculum changes, since both index the whole book.

---

## 1. The three questions before drafting

1. **What is the one thing the reader must leave with?** → `chapter_focus`, ~50% of the word count.
2. **How is this topic actually assessed?** → `primary_artifact_mode`.
3. **Can a reader follow every paragraph and still not be able to apply it?** → `include_quizzes`.

Get these wrong and no amount of revision fixes the chapter.

## 1.5 Titles

Every chapter carries **two** titles:

- **H1 — a descriptive title** naming the trading problem, concretely, in the reader's language. "The Book That Is Silently Wrong", not "Gap Recovery Concepts". It should make sense to someone who does not yet know the concept name.
- **H2 — the concept name**, exactly as a reader would search for it or an interviewer would say it. "Sequence Numbers, Gap Detection, and Recovery".

The purpose is that the contents page reads as a list of trading problems rather than a CS syllabus, so a reader links the engineering topic to the system instantly — while the concept name stays discoverable and unambiguous.

The descriptive title is usually drawn from the opening scenario. Avoid mystery for its own sake: it should be recognisable in hindsight, not a riddle.

## 1.6 Sequencing is a learning-curve decision

Reading order comes from the curriculum's `order` field, not from chapter IDs, which are stable opaque handles. Two rules govern it.

**A module must not open on its hardest chapter.** Where a module's core topic assumes vocabulary the reader does not have, that vocabulary earns its own chapter rather than a paragraph of preamble. Module B originally opened on the memory model — the most demanding topic in the book — while assuming atomics syntax it never taught.

**A chapter may be moved earlier because it is easier**, even where the dependency graph does not require it. Confidence compounds, and a reader who has already succeeded at two chapters in a module approaches the third differently. `b5` sits before `b1` for exactly this reason.

A consequence for drafting: when a chapter is repositioned, its assumed knowledge changes. References to material now downstream become forward links and must read as such, and the brief's `reader_starting_point` must be updated to say what the reader has *not* yet seen.

## 2. Section order

Required sections, in this order. Conditional sections are marked and appear in this position when present.

| # | Section | Layer | Condition |
|---|---|---|---|
| 1 | Opening scenario | core | always |
| 2 | Where you will actually meet this | core | always |
| 3 | The mental model | core | always |
| 4 | Focus part 1 | core | always |
| — | *Quiz 1* | core | `include_quizzes` |
| 5 | Focus part 2 (and 3) | core | always |
| 6 | The artifact — code or pseudocode | core | unless mode is `none` |
| — | *Quiz 2* | core | `include_quizzes` |
| 7 | A worked trace | core | state evolves over time |
| 8 | Going deeper — *named refinement* | deeper | a meaningful refinement exists |
| 9 | Common mistakes | core | always |
| 10 | Operational behaviour | core | chapter has failure modes |
| 11 | When not to use this | core | always |
| 12 | Optional — if you want to see it for yourself | optional | `include_measurement_plan` |
| 13 | Interview mapping | core | always |
| 14 | Summary | core | always |
| 15 | Related | core | always |
| 16 | References | core | always |

Header block above section 1: prerequisites by chapter ID, and the focus in one line.

## 3. Section rules

### 3.1 Opening scenario
Concrete and imaginable. Named firm type, named venue, named instrument, time of day, specific failure. End on the question the chapter answers. No terminology before the scene is set.

Real proper nouns make it concrete; keep any attached claim true of the category, so the chapter never asserts unverified venue-specific behaviour.

### 3.2 Focus sections
Roughly half the chapter. Derive, do not assert — the reasoning is the content, and "what breaks if you weaken this" is usually the better framing than "here is the rule."

### 3.3 The artifact
- `code` — simplest correct implementation. Optimisations live in *Going deeper*. If the reader cannot hold it in their head, it is too big.
- `pseudocode` — explicit condition → behaviour mapping. This is the form the reader reproduces out loud.
- Illustrative or deliberately broken code carries a visible banner. Readers copy anything that looks like code.

### 3.4 Two mechanisms serving one goal
Where a chapter contains two mechanisms for the same goal (retransmission vs snapshot; lock vs lock-free; blocking vs spinning), they get an **explicit side-by-side comparison** — costs, limits, failure modes, and a selection rule — not sequential description. Beginners conflate them otherwise. Prefer a table. Find and state the structural asymmetry that keeps them straight.

### 3.5 Quizzes
Exactly two. Basic tests whether the mechanism landed; deeper tests an edge case or a step people get wrong.

**No "testing:" preamble before the question.** Metadata about what a quiz assesses reads as authoring notes leaking into the page and breaks the flow into the question. If the point needs stating, it belongs in the closing line of the answer as a lesson, phrased for the reader.

Question, then answer immediately after in a blockquote. The answer walks the steps, then explains **the trap** — what a wrong answer would have looked like and why — rather than only stating the result.

### 3.6 Going deeper
Opens with a skip instruction: *"A refinement on the above. Skip on a first read."* Built visibly on top of the core version, never folded into it.

### 3.7 Measurement
Only when `include_measurement_plan`.

**No formulaic opener.** The section must signal that it is skippable, and it must do so differently in every chapter — a repeated stock sentence ("Skippable. Here because...") turns a considerate aside into boilerplate the reader learns to skip without reading. Say what makes *this* experiment worth ten minutes. Same rule as §1.5's prose-over-labels principle: if a sentence appears verbatim in three chapters, it has stopped being writing.

 One instructive experiment, plus the transferable reasoning pattern: identify the suspected cost, construct the smallest comparison that isolates it, state what it does and does not establish. Never a protocol. Opens by telling the reader it is skippable.

### 3.8 When not to use this
The section readers value most and models write worst. Specific situations, each with a reason. Include the case where the technique is unnecessary, not only where it is harmful.

### 3.9 Interview mapping
What distinguishes a strong answer, not a topic list. Prefer "say X unprompted" over "understand X". Name the omissions that reveal inexperience.

### 3.10 Summary
Reconstructs the argument in compressed form. Ends by returning to the industry anchor from section 2.

### 3.11 Sequencing hazards
Where the brief declares `sequencing_hazards`, each one is written out **as an ordered list of steps, in order, with the failure named**. This is not left to inference: a step order that is load-bearing must be stated as a step order, not implied by prose or by the shape of an example.

Each hazard gets: the required order, what breaks if it is violated, and — where the failure is timing-dependent — a note that it will not reliably show up in testing.

### 3.12 Venue-specific detail
Venue-specific protocol material is permitted in an **optional-layer section or appendix**, never in the core path.

It must be **simplified for learning**. The goal is to make the principles concrete, not to enable an implementation: a reader should finish it understanding what a real specification looks like and why it is shaped that way. Anyone implementing against a venue reads the venue's own specification, and the appendix says so.

Every venue-specific claim needs a resolved public source. A simplified illustration is labelled as simplified.

### 3.13 What this book does not teach — and which kind it is

Two different things get left out, for opposite reasons, and they must be handled differently. Deciding which category something falls into is the drafter's job.

**Category 1 — facts and details that demonstrate no skill. Omit entirely.**

A piece of syntax, a library name, a framework, a tool, a standard-library constant, a version-specific feature. Knowing it demonstrates nothing to an interviewer because there is no reasoning behind it — you either happen to have read it or you have not. Including it costs words and adds nothing.

This is the interview-relevance filter (§4) doing its job. No mention, no pointer, no apology. Just cut it.

*Examples:* an advanced C++23 syntax feature; the name of a profiling tool; `std::hardware_destructive_interference_size` and its toolchain support; historical rationale for a design.

**Category 2 — principles and foundations underneath a concept. Mention, and point elsewhere.**

The mechanism that explains *why* the chapter's rule is true. Not required to answer a typical interview question — which is why the chapter does not teach it — but understanding at that depth is a genuine plus in an interview, and a reader who has it reasons better about cases the chapter never covered.

Omitting these silently leaves the reader with a shallow model **they cannot detect is shallow**, and no way to find the missing piece. So name it, and hand them the door.

*Examples:* the MESI protocol under false sharing; how atomics and mutexes are built from instructions; virtual address translation and page-table walks; scheduler internals; TCP congestion control.

**The form for category 2** is a short *Going deeper elsewhere* section, `optional` layer, which:

- names the mechanism precisely enough to search for;
- says in one or two sentences what understanding it would sharpen;
- states honestly that it is not usually required in interviews, and that knowing it is a plus rather than a prerequisite;
- gives a specific, checkable source — a named book, a vendor manual, a standard reference — not "search online".

**Sources must be real and verifiable.** A fabricated or half-remembered citation is worse than no pointer, because the reader will chase it. This is the one rule in this contract whose failure mode actively harms the reader rather than merely producing a weaker chapter.

**Place the pointer in the chapter that owns the concept**, not wherever it is first mentioned in passing. Atomics and mutex implementation belong with the memory model, not with false sharing, even though false sharing is where a reader first wonders about them. A pointer in the wrong chapter both pads that chapter and pre-empts the one that should carry it.

### 3.14 Illustrative examples in concept chapters

A chapter whose `primary_artifact_mode` is `none` may still carry **short illustrative snippets**. The mode governs the *primary* artifact — whether the chapter is built around code the reader studies — not whether code may appear at all.

Concept chapters in particular benefit from small, self-contained examples that make an abstract property concrete: a few lines showing the mistake and a few showing the alternative. These should be

- **short** — under about fifteen lines, and readable without context;
- **generic where useful** — they need not be trading-specific, and a familiar standard-library example often lands harder;
- **shallow on purpose** — the mechanism belongs to a later chapter, and the snippet's job is to make the property visible, with a forward link rather than an explanation.

### 3.15 Module review

The final chapter of a **large or difficult module** closes with a *Module in review* section. Module B is the reference implementation.

It is consolidation, not new material, and it exists because a reader who has finished eight demanding chapters has the pieces and not necessarily the shape. It is written to be read twice: once on finishing the module, and once before an interview.

Contents, in this order:

- **The arc** — one short paragraph per chapter, stating the single thing that chapter established, in reading order.
- **The recurring ideas** — three to five points the module made repeatedly in different guises, each citing the chapters where it appeared. This is the highest-value part: it is what a reader cannot assemble from the chapters individually.
- **A decision table** mapping situations to choices, so the module is usable as a reference afterwards.
- **Check yourself** — around ten questions answerable from the module. No answers given; they are pointers back to sections.
- **What comes next** — what the following module assumes, and which of this module's fixed assumptions it takes apart.

Not every module needs one. The trigger is difficulty and interdependence rather than length: a module whose chapters only make full sense together earns a review, and a module of loosely related chapters does not.

### 3.16 Diagrams

Diagrams are **committed SVG files** under `chapters/<id>/figures/`, referenced with standard markdown image syntax, authored to `standards/diagram-style.md`. They are not prose placeholders describing a figure that does not exist, and not generated at build time.

A chapter earns a diagram when its content is **spatial or structural** — memory layout, address spaces, hardware topology, wire formats, state machines. If the prose is describing an arrangement in space, a figure does work the prose cannot, and the prose can then stop trying.

Sequential or causal content usually does not need one: a worked trace table beats a flowchart, and a quiz beats both.

Every figure carries `purpose`, `critical distinction`, and `forbidden implication` in an SVG comment, so the constraint travels with the artifact rather than living only in the brief.

**Backlog rule:** a placeholder blockquote describing a figure is acceptable in a draft and is a blocker for publication. Track outstanding ones — they are invisible defects, since the chapter reads as complete without them.

**Figures are generated, linted, and judged from the PDF.** They come from `build/figures_*.py`, must pass `build/lint_figures.py`, and are reviewed in rendered output rather than in a markdown preview — previews do not resolve relative image paths, and text overflow is invisible in the source. See `standards/diagram-style.md`.

## 4. Global rules

**Interview-relevance filter.** Would this plausibly be asked or probed in an interview, **or** is it required for correctness? If neither, cut it. Cut by default: named standard-library constants, toolchain support status, standardese, historical rationale, language-lawyer edge cases.

**Scope of the filter — detail only, never structure.** The filter removes elaboration that would confuse a reader. It does **not** decide which sections exist or which bullets appear. Anything the brief asked for stays, and operational content in particular is never pruned on relevance grounds: what an on-call engineer needs to know is a legitimate category in its own right, alongside interview-probable and correctness-required. If a section feels thin against the filter, that is a signal to write it more sharply, not to delete it. Removing a briefed item requires an author decision, not a drafter's judgement.

**Layering.** Every section tagged `core` / `deeper` / `optional`. A reader stopping at the end of `core` has a complete, coherent chapter.

**Claim types.** `normative` must cite. `empirical` needs a reproducible in-repo experiment or an explicit unverified label. `judgment` needs no citation but must read as judgment. Never invent a number.

**Cross-links.** Inline at the point of relevance, plus a `Related` line. Only to IDs in `curriculum.yaml`.

**Callbacks to prerequisite chapters.** Where a chapter reuses a tool, command, or concept the reader already met, name it and where they met it: *"the `numactl --hardware` output you read in [c4] — the node column is the one that matters here."* This reviews prior material at the moment it becomes useful, which is when it sticks, and it makes the handbook read as one course rather than thirty essays.

Requires the prerequisite to be **written**, not merely planned, since the callback must describe what that chapter actually said. Deferred until prerequisites exist; applied as a revision pass. Candidate callback sites are marked `<!-- CALLBACK: [id] -->` in draft chapters so the pass has targets rather than a re-read.

**Industry anchor.** Say loudly and specifically where the technique is used in this industry and why it matters *here* rather than generally. The product's value is sharp interview preparation, not a knowledge textbook, so the trading context is content and not framing. Where a technique's applicability is narrow, state the conditions that make it apply — do not repeat a general caveat about it often being unnecessary. One clear scoping statement, placed where the reader can act on it, replaces three hedges.

**Length (prose only).** Target bands: foundation 1200–2000 · applied 1400–2600 · specialist 1800–3000. Quizzes, worked traces, code blocks, and references are excluded from the count.

These are **targets, not gates.** Chapters that exceed them because the extra material earns its place — illustrative examples, a two-mechanism comparison, a depth pointer — are fine, and Module A settled at roughly 3,000–3,500 words in practice.

**The gate is 4,500 words** of prose, excluding quizzes, references, and any module review (§3.15) the chapter carries — a review is consolidation of the whole module, not chapter content, and counting it would penalise the chapter that hosts it. At that point the chapter is a split candidate, and the decision goes to the author: split it, or justify the length. Do not shrink the focus section to fit.

## 5. Return without review if

- word count is evenly distributed across sections — the focus was not enforced;
- the primary artifact contains an optimisation the chapter did not motivate;
- a quiz answer states the result without explaining the trap;
- a quiz carries a "testing:" preamble before the question;
- an empirical claim carries a number with no in-repo experiment;
- a normative claim is asserted without a resolved reference (a placeholder is not resolved);
- the opening is an abstract problem statement;
- `core` sections depend on material introduced in `deeper` or `optional`;
- no `<!-- CALLBACK: [id] -->` markers were emitted despite the chapter having prerequisites it visibly reuses.

**This list is the enforcement surface.** A rule stated only in the prose above tends not to get checked — a rule that matters belongs here as well.
