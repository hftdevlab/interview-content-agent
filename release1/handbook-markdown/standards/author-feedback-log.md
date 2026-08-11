# Author feedback log

Every piece of author feedback, the rule it produced, and where that rule now lives.

Purpose: **calibration traceability.** When a chapter regresses, this file identifies which rule failed rather than re-deriving it from scratch. It is also the input to task C0-11 and to the Phase 1 validator specification.

Status values: `rule` (now normative) · `chapter-local` (applied once, did not generalise) · `open`.

---

## Round 1 — pilot `b2-spsc-ring-buffer`, draft r0

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 1.1 | Reader skill varies from C++ beginner to experienced HFT engineer refreshing | Content layering: every section tagged `core` / `deeper` / `optional`; a reader stopping at the end of `core` has a complete chapter | Plan §4.2, brief `content_layers` | rule |
| 1.2 | Solution code should omit type traits and cached variables | Simplest-correct-thing-first: the primary artifact is the simplest correct implementation; optimisations move to the `deeper` layer as explicit refinements | Plan §4.4, brief `code_artifact_expectations` | rule |
| 1.3 | Most important takeaway is memory ordering and index movement; spend most of the chapter there | `chapter_focus` field, one sentence, ~50% of word count; no other section over ~15% | Plan §4.1, brief `chapter_focus` | rule |
| 1.4 | Cached variable should be framed as a performance improvement on top of the basic solution | Covered by 1.1 + 1.2 | — | rule |
| 1.5 | Keep `alignas` and false sharing | Chapter-local retention decision; generalises only as "keep what is required for correctness or commonly asked" (see 1.6) | — | chapter-local |
| 1.6 | Product is interview prep, not academic polish — skip things like C++17 constants that won't be asked | Interview-relevance filter, stated verbatim in the draft prompt: *would this plausibly be asked or probed in an interview, or is it required for the code to be correct? If neither, cut it.* | Plan §4.3, brief `interview_relevance_filter` | rule |
| 1.7 | Measurement section should encourage experimentation and teach performance reasoning; only for chapters with complex performance implications | `include_measurement_plan`, default false; when true it is `optional` layer, framed as invitation plus reasoning pattern, never a protocol | Plan §4.5, brief `include_measurement_plan` | rule |
| 1.8 | Re-emphasise where SPSC is used in HFT market-data systems; link to related content | `industry_usage_anchor`: named production usage stated early and echoed in the summary; inline cross-links plus a `Related` line | Plan §4.6, brief `industry_usage_anchor` | rule |

## Round 2 — pilot `d3-sequence-and-gap-recovery`, draft r0

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 2.1 | Retransmission vs snapshot resync not clearly distinguished; beginners mix them up; needs costs and trade-offs | Where a chapter contains two mechanisms serving one goal, they get an explicit side-by-side comparison with costs, limits, and a selection rule — not just sequential description | Contract §3.4 | rule |
| 2.2 | Pseudocode focused on sequence-number conditions vs behaviour beats real code here, because the topic is tested as concept discussion | `primary_artifact_mode`: `code` / `pseudocode` / `none`, chosen by how the topic is *assessed*. Coding practice for pseudocode chapters is a separate product | Plan §4.10, brief `primary_artifact_mode` | rule |
| 2.3 | Complex topic; beginners may still be confused. Two quizzes — one basic, one deeper — with answers immediately after. Generalises to other advanced chapters | `include_quizzes`; exactly two, each stating what it tests, answer immediately following. `core` layer. Expected true for most applied/specialist chapters in Modules B–E | Plan §4.9, brief `include_quizzes` | rule |
| 2.4 | Opening should use a concrete real-world scene a newcomer can picture — named firm type, venue, instrument, time of day, specific failure | `opening_scenario`: concrete and imaginable, not an abstract problem statement. Real proper nouns for concreteness; any claim attached to them stays true of the category | Plan §4.8, brief `opening_scenario` | rule |

### Consequential adjustments from round 2

- **Length bands now cover prose only.** Worked traces and quizzes are structured assessment, not exposition; allow roughly +300 words for a quiz pair. (Plan §4.7)
- **`b2` owes a quiz pair.** Rule 2.3 applies retroactively. Candidates: deriving an ordering from the happens-before requirement, and the full/empty boundary. Tracked as C0-11.

## Round 3 — pilot `c5-numa-placement`, draft r0

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 3.1 | The "testing:" line under each quiz creates a weird reading experience; fold into the answer or remove | No preamble before the question. Assessment metadata is authoring notes, not reader-facing. If the point needs stating it becomes the closing lesson of the answer | Contract §3.5 | rule |
| 3.2 | Instead of repeating "most systems don't need this", be clear which systems *do* and why it matters for trading. The product's strength is sharp quant-dev interview prep, not a knowledge textbook — introduce industry practice and use cases loudly | Industry anchor is content, not framing: state the conditions that make a technique apply rather than repeating a general caveat that it often does not. One scoping statement replaces three hedges | Contract §4 | rule |
| 3.3 | Once prerequisite chapters exist, link back to them explicitly to reinforce learning — *"remember in the thread affinity chapter we used X"* | Callbacks to prerequisites: name the tool or concept and where the reader met it. Requires the prerequisite to be written; applied as a revision pass, with `<!-- CALLBACK: [id] -->` markers left in drafts as targets | Contract §4 | deferred |

### Applied in round 3

- Quiz preambles removed from `d3` and `c5`.
- `c5` "Where you will actually meet this" rewritten around colocated hosts, consolidated multi-desk servers, capacity growth, and hardware refresh, with the tail-latency argument for why this industry cares and most others do not. Single-node scoping reduced to one line in *When not to use*, framed as diagnosis.
- `c5` summary now closes on the industry anchor rather than on non-applicability.

### Deferred work created by 3.3

Callback passes become possible as prerequisites land. Known targets so far:

| Chapter | Callback to | At |
|---|---|---|
| `c5` | `c4` thread affinity | pinning order in the first-touch fix; `numactl` / `lscpu` output |
| `c5` | `c1` virtual memory | page faults as the placement mechanism |
| `c5` | `a6` coherence | why remote access varies rather than merely being slower |
| `d3` | `d2` transports | why multicast makes loss the receiver's problem |
| `b2` | `b1` memory model | happens-before as the thing the orderings buy |
| `b2` | `a6` false sharing | the `alignas` justification |

## Round 4 — author decisions on open items

| # | Decision | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 4.1 | The relevance filter must not override operational content. It exists to prevent unnecessary detail that confuses readers, not to determine structure and bullets. Keep what the brief asked for | Filter governs **detail, never structure**. It does not decide which sections or bullets exist. Operational content is its own admissible category alongside interview-probable and correctness-required. A briefed item can only be removed by author decision | Contract §4, brief `interview_relevance_filter` | rule |
| 4.2 | Sequencing hazards: choose whichever approach makes output more deterministic — a new brief field | New `sequencing_hazards` field: declared order, failure if violated, detectability. Drafter must render each as an **ordered list with the failure named**, never leave it to inference | Contract §3.11, brief `sequencing_hazards`, validator V-11 | rule |
| 4.3 | Defer `f1` and `f2` to release 2 | Release 1 is 30 chapters, Modules A–E. Module F marked deferred | `curriculum.yaml` | done |
| 4.4 | Two-entry reference lists are acceptable | Reference count is not a quality signal. For `judgment`-heavy chapters a short list is the correct outcome, and padding it with weak sources is a defect. Evidence review checks type-appropriateness only | Plan §5 (already consistent) | confirmed |
| 4.5 | Venue-specific protocol detail may be included as an optional section or appendix, but simplified for learning — the goal is principles and interview prep, not implementing a real protocol | Permitted in `optional` layer or appendix, never core. Simplified for learning, with what is elided stated plainly. Every venue claim needs a resolved public source; simplified illustrations labelled as such | Contract §3.12, brief `venue_specific_content`, validator V-12 | rule |

### Applied in round 4

- Contract §4 scope paragraph; brief `interview_relevance_filter` scope note. The `c5` power/thermal bullet (C0-11 F-3) **stays** — it was briefed.
- `sequencing_hazards` added to the template and backfilled into the `b5` brief as `seq-b5-01`.
- `b5` transition-order paragraph rewritten as a three-step ordered list with the failure named and its timing-dependence called out.
- `f1` and `f2` set to `status: deferred`, `release: 2`. Module F annotated.
- Validators V-11 and V-12 added.

**Note on 4.2:** determinism was the deciding criterion, and it generalises. Where a rule could live either in a brief field or in the drafter's judgement, prefer the field — the same brief should produce the same chapter on every run. This is the first explicit statement of that principle and it should govern future schema decisions.

---

## Round 5 — front matter

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 5.1 | Add a preface, "Before you start, where C++ engineers fit in electronic trading" — tied to the target audience, covering only what affects interviews | Front matter registered as a category with its own rules; preface written for the reader's career situation, not a technical topic | Contract §0, `front-matter/preface.md` | done |
| 5.2 | Chapter 1 renamed and reframed as a bird's-eye anatomy: engineering problems at every stage, textbook CS mapped to production, anchors for later chapters | Chapter 1 rules: breadth over depth, every stage names its problem and points at the chapter covering it, forward-anchor density is a feature | Contract §0, `a1` | done |
| 5.3 | Preface and chapter 1 need not fit the framework built for teaching chapters | Front matter exempt from section order, focus weighting, quizzes, layering, interview mapping, when-not-to-use. **Still bound by** the claim taxonomy, the no-invented-numbers rule, and cross-reference resolution | Contract §0 | rule |
| 5.4 | Preface is in good shape | — | — | approved |
| 5.5 | Chapter 1: drop the strict bullet template per stage; use natural prose. Level, detail, and the CS curriculum table are right | **Structure by prose, not by labels.** A repeated bold-label scaffold makes the template the takeaway rather than the content. Where each item answers the same underlying questions, let the prose carry it. Applies to any recurring per-item structure, not only chapter 1 | Contract §0, general style | rule |

### Applied in round 5

- `preface.md` written: firm types, systematic vs discretionary, frequency tiers, asset classes, the three roles, and how interview emphasis varies. Generalisations flagged as such; no firm-specific practices, compensation, or hiring processes asserted.
- `a1` retitled *From Exchange Packet to Trade — Anatomy of an Electronic Trading System* and rewritten around twelve stages plus the curriculum mapping table.
- `a1` r1: per-stage `**The engineering problem** / **The CS concept**` labels removed, stages rewritten as flowing prose, chapter anchors kept as light parenthetical pointers. Verified mechanically — no labels remain, all anchors resolve.
- Prior `a1` draft archived at `chapter-v0-dataflow.md`.

## Round 6 — Module A

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 6.1 | The latency and profiling chapters need practical examples — not necessarily trading- or interview-specific, just enough to make the concept concrete. E.g. why dynamic vector reallocation is worse than reserving known capacity; why deterministic code beats wall-clock-dependent code. No need to go deep, later chapters enhance them | **Illustrative snippets are permitted in any artifact mode.** `primary_artifact_mode` governs the *primary* artifact, not whether code may appear. Concept chapters should carry short (<15 line), self-contained, deliberately shallow examples showing a mistake and its alternative, with a forward link instead of an explanation. Generic standard-library examples are fine and often land harder than domain-specific ones | Contract §3.14 | rule |
| 6.2 | The cache chapters are at the right level but should not hide deeper knowledge where it is useful. MESI is exactly how false sharing works; ignoring it leaves shallow understanding. Mention it, say explicitly it can be learned elsewhere, link a trustworthy source. Same for atomic and mutex implementation, virtual address translation, page tables | **Depth pointers.** Where a chapter stops short of a deeper mechanism, name it, say why it is out of scope, state honestly whether it is interview-relevant, and give a specific checkable source. Silent omission leaves a shallow model the reader cannot detect. Sources must be real and verifiable — an invented citation is worse than no pointer | Contract §3.13 | rule |

### Applied in round 6

- `a3`: new *What determinism looks like in code* subsection — amortised `push_back` versus `reserve`, periodic work on the hot path, and wall-clock branching. Property only; mechanisms forward-linked to [c2], [b2], [d5].
- `a4`: new *The two mistakes, concretely* subsection — a benchmark deleted by the optimiser with its fix, and closed-loop versus open-loop harness code for coordinated omission.
- `a5`: *Going deeper elsewhere* — virtual address translation, page tables and TLBs (→ [c1], [c5], OSTEP), and prefetcher specifics (→ vendor optimisation manual).
- `a6`: *Going deeper elsewhere* — MESI and the coherence protocol proper (→ Sorin, Hill & Wood; vendor architecture manual), and how atomics and mutexes are built from instructions (→ [b1], [b3], Herlihy & Shavit).
- Briefs updated with a `depth_pointers` field; references added to both cache chapters.

**Note on 6.2:** the depth-pointer rule has a claim-integrity dimension. It requires naming real sources, which makes it the one contract rule that could actively cause harm if a drafter invents a plausible-looking citation. Validator V-02 already checks that `normative` claims resolve; depth pointers should be checked the same way once a source pack exists.

## Round 7 — omission taxonomy and length gate

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 7.1 | ~3,000 words per chapter is about right. At 4,500+ excluding quizzes and references, decide whether to split | Bands become **targets, not gates**. The gate is 4,500 words of prose excluding quizzes and references, at which point the chapter is a split candidate and the decision goes to the author. Never shrink the focus section to fit | Contract §4 | rule |
| 7.2 | Atomic implementation was mentioned as an example for the *memory model* chapter. It does not belong in the caching chapter | **Depth pointers go in the chapter that owns the concept**, not wherever a reader first wonders about them. A pointer in the wrong chapter pads that chapter and pre-empts the one that should carry it | Contract §3.13 | rule |
| 7.3 | Two distinct categories of thing this book does not teach: (1) a simple fact or detail showing no skill — advanced syntax, a framework or tool name — knowing it impresses nobody, so omit entirely; (2) the principle or foundation under a concept — MESI, mutex implementation — not required for typical interview questions, but understanding at that depth is usually a plus, so mention it and encourage learning it elsewhere | The omission rule restated as an explicit **two-category taxonomy**, with the drafter required to classify. Category 1: cut silently, no pointer (this is the relevance filter). Category 2: name it, say what it sharpens, state that it is a plus rather than a prerequisite, give a checkable source | Contract §3.13 | rule |

### Applied in round 7

- Length rule rewritten: targets versus the 4,500-word split gate, with Module A's ~3,000–3,500 recorded as the observed norm.
- `a6`: the *How atomics and mutexes are actually built* pointer removed and reassigned to `b1`, recorded in `curriculum.yaml` as `owed_depth_pointer` so it is not lost. `a6`'s remaining pointer is MESI only, and its framing now states that the depth is a plus rather than a prerequisite.
- `a6` brief annotated to say the atomics pointer is deliberately absent, with the placement rule cited — so a future drafter does not "helpfully" restore it.

**Note on 7.3:** the taxonomy resolves a tension that existed since round 1. The relevance filter (rule 1.6) said cut anything not interview-probable or correctness-required, and the depth-pointer rule (6.2) said mention deep mechanisms that are explicitly *not* interview-probable. Both are right, and they apply to different things: the filter governs facts that carry no reasoning, the pointer governs mechanisms that carry the reasoning underneath a rule the chapter asserts. The distinguishing question is **whether understanding it would make the reader reason better about cases the chapter never covered.** If yes, it is category 2 however unlikely it is to be asked directly.

## Round 8 — Module B learning curve

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 8.1 | Module B is the core of the book and readers will feel a steep curve. It needs an entry chapter covering atomicity, the atomic instructions (compare-exchange and friends — no longer optional, they are used throughout later chapters), mutexes, and multithreading foundations, before the memory model | New chapter `b0-threads-atomics-locks`. **Rule: a module must not open on its hardest chapter.** Where a module's core topic assumes vocabulary, the vocabulary gets its own chapter rather than a paragraph of preamble | `b0`, contract §1.6 | rule |
| 8.2 | `b5` waiting strategies can come before the memory model | Module B resequenced: b0 → b5 → b1 → b2 → b3 → b4 → b6 → b7. `b5`'s prerequisites repointed to `b0`, and its SPSC references softened to forward links | `curriculum.yaml`, `b5` | done |
| 8.3 | The memory model chapter needs a summary table comparing each ordering, and the practical use cases for acquire/release, linkable from SPSC | Added: an orderings comparison table, and three named patterns (publish-data-then-flag, publish-data-then-index, reference counting) with the SPSC pair identified as the second pattern applied twice | `b1` | done |
| 8.4 | Evolve readers naturally from single-threaded, to mutex-based, to lock-free. Mention the default ordering when unspecified, and the motivation for ordering instead of locking | New *Why give up the mutex at all* section in `b1`, with a mutex-versus-lock-free table. Key point made explicit: **the mutex was already providing the visibility guarantee**, and dropping it transfers that obligation to you. `seq_cst` named as the default, with weakening framed as something the derivation licenses | `b1` | done |
| 8.5 | More context and foundation before the hardest topic improves the learning experience | **Curriculum sequencing is a learning-curve decision, not only a dependency-graph one.** A chapter may be moved earlier because it is easier and builds confidence, even where the dependency graph does not require it | Contract §1.6 | rule |

### Applied in round 8

- `b0` written: lost updates and torn reads; mutex and condition variable; atomic load/store, `fetch_add`, `exchange`, and `compare_exchange` with its expected-value semantics; the compare-exchange loop as a pattern; `is_lock_free`; the `seq_cst` default. Closes on why the module gives up the mutex anyway.
- **"Atomicity does not compose"** established in `b0` as the fact that decides mutex-versus-atomic, and reused in `b3` (lock-free operations do not compose) and `b4` (claim and write are separate).
- `b1` prerequisites now `b0` + `a6`; opening motivation section added; orderings table and practical patterns added; `seq_cst` default called out. Now ~4,200 words total, still inside the split gate on prose.
- `curriculum.yaml`: **IDs declared stable opaque handles**, with reading order in an explicit `order` field, so the module can be resequenced without rewriting cross-references. Documented at the top of the file.

**Note on 8.1:** this is the first structural gap found by reading the module as a sequence rather than chapter by chapter. Each of `b1`–`b4` passed review individually; the defect was in what the *first* of them assumed. Worth adding to the review lanes — a whole-module read against the reader's actual starting point, distinct from per-chapter review.

## Round 9 — Module B completion

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 9.1 | Finish the remaining Module B chapters | `b6` and `b7` drafted | `b6`, `b7` | done |
| 9.2 | The module is large and difficult — worth a review and summary at the end of the last chapter | **Module review.** The final chapter of a large or difficult module closes with a consolidation section: the arc (one paragraph per chapter), the recurring ideas with cross-citations, a decision table, ~10 self-check questions, and what the next module takes apart. Trigger is difficulty and interdependence, not length | Contract §3.15, `b7` | rule |

### Applied in round 9

- `b6` written. Central correction: the three costs of a virtual call ranked — loads (smallest), branch misprediction, lost inlining (largest) — against the common belief that the pointer indirection dominates. Cheap structural fixes (group by type, filter the subscriber list) placed ahead of mechanism changes, and CRTP's heterogeneous-container problem made explicit, since it is the option most likely to be proposed and least likely to help.
- `b7` written, closing with **Module B in review**.
- Contract §3.15 added.

**Note on the module review:** the *recurring ideas* section turned out to be the part that could not have been written chapter by chapter. Four of the five — atomicity does not compose; single-writer buys everything; guarantees are worst-case while benchmarks measure the average; the cheapest fix is structural — appear in three or more chapters each, and no individual chapter is the right place to say so. This is the third finding this project has produced that was only visible when reading a module as a sequence (after the `a5`/`a6` contradiction and the `b1` entry-point gap), which is now a strong argument for adding a whole-module review lane in Phase 1.

## Round 10 — Module C

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 10.1 | Proceed to Module C | Six chapters drafted or completed; module resequenced so NUMA closes it | `c1`–`c6`, `curriculum.yaml` | done |

### Applied in round 10

- `c1`, `c2`, `c3`, `c6`, `c4` written; `c5` (the original pilot) retained and extended with the module review.
- **Module C resequenced** to `c1 → c2 → c3 → c6 → c4 → c5`. Rationale under contract §1.6: the memory chain (`c1`–`c3`, `c6`) is self-contained and easier; thread placement (`c4`) follows; and `c5` closes the module because NUMA is where memory placement and thread placement meet, making it the synthesis rather than just the hardest chapter.
- Module review appended to `c5` per contract §3.15.
- Contract §4 clarified: **a module review is excluded from the 4,500-word split gate**, since it consolidates the module rather than the chapter and would otherwise penalise whichever chapter hosts it. `c5` is 3,402 words of chapter plus 1,139 of review.

**Note on the recurring ideas:** the strongest one to emerge was *placement is decided earlier than you think, and by the wrong actor* — the NUMA node fixed by first write rather than `malloc`, the page created by first touch rather than allocation, the core chosen at thread start. In every case the decision is made before the code that cares about it runs, which is why every remedy in the module is "do something deliberately and early" rather than "optimise the hot path." That framing is not visible from any single chapter.

A second finding, worth watching: **every fix in Module C is configuration with a hardware dependency**, not code. That is a different maintenance category from anything in Modules A or B, and it is why so many of these chapters end with "assert it at startup and refuse to run if wrong." Module D will likely have the same property for network and clock configuration.

## Round 11 — diagrams and chapter fixes

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 11.1 | All content is text; no diagram generation. Address translation, custom allocators, and NUMA placement all deserve at least one diagram of shape and memory layout | **Diagrams are committed SVG files** under `chapters/<id>/figures/`, referenced with markdown image syntax, authored to a fixed palette and type scale. Not build-time generated, not prose placeholders. A chapter earns one when its content is spatial or structural | Contract §3.16, `standards/diagram-style.md`, validator V-13 | rule |
| 11.2 | The optional in-depth section repeats the same "Skippable. Here because..." sentence every time | **No formulaic opener.** The section must signal skippability differently in each chapter. A sentence appearing verbatim in three chapters has stopped being writing | Contract §3.7, validator V-14 | rule |
| 11.3 | `c2` jumps into code straight after explaining the purpose; it should describe the free-list algorithm first | New *The free list, before any code* subsection: the two arrays, the stack discipline, and why it is a stack rather than a linked list. Code follows | `c2` | done |
| 11.4 | `c6` should open with process vs thread — address spaces, stack and heap layout, stack pointer — with a diagram. Standard OS material, but so relevant it is worth the review | New *First: what a process actually is* section with `fig-c6-1`. Three consequences drawn out: thread sharing is free and unprotected, process sharing is partial and needs offsets rather than pointers, and process isolation is also a failure boundary | `c6` | done |

### Applied in round 11

- `standards/diagram-style.md` written: SVG-file approach with rationale, fixed palette, type scale, and the rule that colour never carries sole meaning.
- **Six figures authored and validated:** `fig-c1-1` (allocation vs residency), `fig-c1-2` (translation and TLB reach), `fig-c2-1` (the free list), `fig-c3-1` (three allocator layouts), `fig-c5-1` (NUMA topology with NIC placement), `fig-c6-1` (process vs thread address space).
- Nine formulaic optional-section openers rewritten, each specific to its chapter.
- Validators V-13 and V-14 added.

**Note on 11.1:** the placeholder blockquotes were an invisible defect. Every chapter carrying one *read* as complete — the placeholder describes the figure well enough that prose review glides over it — which is why four of them survived eleven rounds of review without being raised. Four remain outstanding (`fig-a2-1`, `fig-b2-1`, `fig-d3-1`, `fig-d3-2`) and are now tracked as a publication blocker rather than a note.

**Note on 11.2:** this is rule 5.5 recurring in a new form. There the template was a bold-label scaffold inside a chapter; here it is a stock sentence across chapters. Both come from the same drafting instinct — reaching for a reliable structure and letting it substitute for the writing — and both were only visible when reading several chapters together.

## Round 12 — figure completion and build verification

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 12.1 | Finish all Module C figures and back-populate Modules A and B. No structural change needed to B — embed figures naturally. SPSC and MPSC queue movement, memory-model synchronisation, and a high-level dataflow architecture diagram in particular | 17 figures now generated from `build/figures_*.py` via shared helpers, embedded at the point in the prose where the reader needs them | all modules | done |
| 12.2 | Images do not render in the browser | Diagnosed: the SVGs are valid and render correctly; markdown **previews do not resolve relative `figures/*.svg` paths**. Fixed properly with a build that **inlines** figures into self-contained HTML/PDF | `build/make_book.py` | done |
| 12.3 | Verify the final effect in the PDF version | **Figures are judged from rendered PDF output, never from a markdown preview.** Build, rasterise, read | Contract §3.16, `diagram-style.md` | rule |

### Applied in round 12

- `build/figlib.py`: shared generator emitting **inline presentation attributes rather than CSS classes**, so figures survive sanitisers that strip `<style>`. Includes `wrap()` and `footer()` for measured line breaking.
- **17 figures**: `a1-1` dataflow architecture, `a2-1` order state machine, `a3-1` latency distribution, `a5-1` AoS vs hot/cold split, `a6-1` false sharing, `b1-1` happens-before edges, `b2-1` SPSC ring movement, `b4-1` MPSC claim vs write, `c1-1`/`c1-2`, `c2-1`, `c3-1`, `c4-1` topology and SMT siblings, `c5-1`, `c6-1`, `d3-1`, `d3-2`.
- All four remaining placeholder blockquotes replaced. **Zero placeholders and zero broken image links remain.**
- `build/make_book.py`: markdown → self-contained HTML → PDF, with print CSS.
- `build/lint_figures.py` + validator V-15.

**Note on 12.3 — the finding that justifies the rule.** The first figure pass had **37 text-overflow defects**: text running past the viewBox edge, clipped in the rendered output. Every SVG was valid, parsed cleanly, and looked correct in source. They were invisible until a PDF page was rasterised and read. Worse, the linter's *own* regex mis-parsed `text-anchor` on the first attempt and produced false positives, which had to be corrected before its output could be trusted.

That is the same class of defect as the figure placeholders in round 11 and the repeated openers in 11.2: **failures that leave the artifact looking complete.** The pattern across this project is now unmistakable — the defects that survive review are the ones where nothing appears wrong. Every one has been caught by building the real output and looking at it, or by a mechanical check. None was caught by reading.

## Round 13 — Module D

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 13.1 | Proceed to Module D; add figures wherever they help illustration and learning | Six chapters drafted plus the existing `d3` pilot; five new figures; module review on `d6`; `d7` reclassified as an appendix | `d1`–`d7` | done |

### Applied in round 13

- `d1`, `d2`, `d4`, `d5`, `d6`, `d7` written. Module order `d1 → d2 → d3 → d4 → d5 → d6`, with `d7` moved **out of the numbered sequence into an appendix** — it is a low-priority topic and putting it last in sequence would have made it look like the module's conclusion rather than a reference for people on venues that offer nothing else.
- Five figures: `d1-1` channels and packet framing, `d2-1` multicast versus unicast fan-out, `d4-1` the three drop points, `d5-1` timestamp capture points by clock, `d6-1` kernel path versus bypass.
- Module review on `d6`.
- **Directory `d3-sequence-gap-recovery` renamed to `d3-sequence-and-gap-recovery`** to match its curriculum ID. The mismatch had been silently skipping the chapter in the build. `make_book.py` now reports a missing directory as an error rather than skipping quietly.

**Note on figure review.** The lint catches viewBox overflow and nothing else. `fig-d6-1` passed it cleanly while a column of annotations ran *underneath* an adjacent panel — a collision the checker cannot see, caught only by rasterising the page. Overlap detection is possible but needs real text metrics rather than an estimate; for now the rule stands that **figures are reviewed in rendered output**, and the lint is a floor rather than a substitute.

**Note on the module's own theme.** The recurring idea that emerged strongest was *silence is ambiguous, and it resolves in the expensive direction* — a quiet market and a dead feed look identical, a failed multicast join looks like nothing happening, an empty queue looks like a slow market. It appears in `d2`, `d4`, `d6`, and back in `c6`'s dead-producer quiz. Every instance has the same remedy: the system must be told it is healthy rather than inferring it from the absence of bad news.

## Round 14 — Module D content

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 14.1 | `d4` should focus more on network techniques for low-latency: disabling Nagle on the hot path, head-of-line blocking in TCP, a brief introduction to `epoll` | `d4` widened into the practical socket chapter. **Responsibility split with `d2`: `d2` explains why the pathologies exist, `d4` is the toolkit for doing something about them.** Duplicated Nagle material removed from `d2` and cross-referenced instead | `d4`, `d2` | done |
| 14.2 | The appendix should cover how trading firms actually use WebSocket — live price dashboards, bidirectional connections | New *Where trading firms actually use WebSocket* section: dashboards, bidirectional operator control, monitoring consoles, vendor APIs, RFQ workflows | `d7` | done |

### Applied in round 14

- `d4` retitled *Hot-path networking, batching, and overload*, with a new **rest of the toolkit** subsection under the "go faster" option: `TCP_NODELAY`, head-of-line blocking, buffer sizing, batched receive, and readiness notification. New figure `fig-d4-2` contrasting a UDP gap with a TCP stall.
- `epoll` framed by **when not to use it**: with one almost-always-ready socket it adds a syscall to learn what `recv` would have told you. It earns its place with many mostly-idle sockets — the gateway and the control plane, not the feed handler.
- `d7`: WebSocket's persistent bidirectional connection reframed as the reason it *succeeds* internally, with the note that a kill switch must not depend on it ([c2]'s principle that risk-reducing operations must not queue behind the machinery that may be failing).
- `d2` de-duplicated; `d4` now 3,295 prose words, inside the gate.

**Note on 14.1 — the finding worth keeping.** Writing head-of-line blocking as a *detectability* problem rather than a delay inverts the usual framing and is, I think, the sharpest point in Module D: **the reliable protocol produces the failure that is harder to handle.** A UDP gap announces itself and [d3] turns it into bounded, visible untrust; a TCP stall is invisible from inside the application — no gap, no error, no counter — and is indistinguishable from a quiet market. That is the module's *silence is ambiguous* theme appearing once more, and it now appears in `d2`, `d4`, `d6`, and `c6`.

## Round 15 — Module E, release 1 complete

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 15.1 | Proceed to Module E | Four chapters, four figures, module review plus a release-1 closing section on `e4`. Whole-book build added | `e1`–`e4`, `build/make_all.py` | done |

### Applied in round 15

- Module ordered `e2 → e1 → e3 → e4`: the book chapter follows directly from Module D's data stream and is the most concrete, and replay closes both the module and the release as the synthesis chapter.
- Figures: `e2-1` three book representations, `e1-1` the two indistinguishable failures and the retry that resolves them, `e3-1` exposure ordering around the send, `e4-1` the capture boundary.
- `build/make_all.py` builds every module plus `handbook-release-1.pdf` — **183 pages**, preface through release close.

**Note on the module's own theme.** The strongest recurring idea was *risk-reducing operations must always be available*, and it turned out to be structural rather than a convention: creating exposure is a state change and removing it is a state assertion, which is **why** cancels are naturally idempotent and new orders are not. That single observation explains the reserved cancel pool ([c2]), the retry asymmetry ([e1]), and the kill-switch independence requirement ([e3]) as one principle rather than three practices. It was not visible from any single chapter.

**Note on the release close.** `e4` ends with a section walking one packet through the entire book — transport choice, framing, sequence check, queue handoff, book update, preallocated memory, pinned thread, risk check, identity-carrying order, capture. It exists because the reader has just finished thirty-one chapters and the thing they most need is the map from [a1] filled in. Worth reviewing specifically: if the arc does not land there, it does not land anywhere.

## Round 16 — Module E content

| # | Feedback | Rule produced | Lives in | Status |
|---|---|---|---|---|
| 16.1 | `e2` should explicitly introduce L1/L2/L3 order books and their messages, with the price-indexed array plus linked list as the full version, explaining add, cancel and update — with code | New *What kind of book are you building?* section (L1/L2/L3, aggregation runs one way, queue position is what L3 buys) and a new Part 2 building the order-by-order book: ladder of intrusive doubly-linked FIFO lists plus an order-id index, with code for add, cancel, modify, execute, and queue-position query | `e2` | done |
| 16.2 | `e4` should cover bitemporal timestamps — event time and transaction time — in a research system: how they are used for backtesting and replay, and how engineers design for researchers | New Part 3: event versus knowledge time, the lookahead failure, append-only correction storage, and the interface rule that the point-in-time query must be the default | `e4` | done |

### Applied in round 16

- Three figures: `e2-2` L1/L2/L3 side by side, `e2-3` the L3 structure (ladder, intrusive list, id index), `e4-2` the bitemporal plane.
- `e2` is now 3,653 prose words and `e4` 3,217 — both inside the 4,500 gate, both at the top of the observed range.
- The **modify rule** — reduce at the same price keeps queue priority, increase or reprice loses it — written up with its fairness reasoning, and flagged as something to confirm per venue.
- The **bitemporal interface rule** stated as a design decision rather than a convention: make the point-in-time query the short name, because the convenient call is the one made under deadline.

**Note on 16.1.** Adding L1/L2/L3 fixed a gap that had been invisible: the chapter discussed "the book" for 2,600 words without ever saying what detail level of data it was built from, and `d1`'s order-based versus level-based distinction was left hanging with no chapter that resolved it. The new section closes that loop.

**Note on 16.2 — why this belongs in an engineering book.** The bitemporal section's argument is that whether a researcher's question is *answerable at all* was decided years earlier by an engineer choosing whether corrections would be appended or applied in place. Overwriting is unrecoverable: the information is gone. That makes it one of the few decisions in this handbook with no remediation path, and it is normally treated as a database detail rather than as a system-design obligation.

**Figure defect worth recording:** `fig-e4-2` shipped its first draft with the shading **inverted** — the impossible region marked as knowable. The lint passed, since the geometry was valid; only reading the rendered page caught it. That is the third distinct class of figure defect the checker cannot see, after text-under-panel overlap and label collision. **The rule holds: figures are judged from the rendered page, and the lint is a floor.**

---

## Open items for the author

*All items from rounds 1–3 resolved in round 4. Remaining:*

1. **C0-11 re-run on an independent model family** (A6). Blocked on a second provider. Until then the cold-test result stands as provisional — it shows the contract is consistent with rules the drafter already knew, not that it transmits them.
2. **`b2` owes a quiz pair** under rule 2.3. Candidates: deriving an ordering from the happens-before requirement, and the full/empty boundary.
3. **Callback pass** cannot begin until Module A and B prerequisites are drafted. Marker convention is live; `b5` carries four markers.
4. **Which chapters get venue-specific appendices**, now that 4.5 permits them. `d1` and `d3` are the obvious candidates and both need a Stage 1 source pack first.
