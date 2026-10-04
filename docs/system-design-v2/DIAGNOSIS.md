# System-design pilots: diagnosis and reset

October 2026. Covers the five pilot questions generated in `tmp/foundational-e2e`
and the agent instructions that produced them.

## Summary

- **The drafts were the same length as good tutorials, but shaped like specifications.** Mean paragraphs of 75–80 words and up to 700 words of prose without a single list, table, or figure.
- **The instructions caused it.** The skill and style guide had grown to about 38,000 characters of dense prose, mostly prohibitions added one feedback round at a time. The style guide itself fails the new readability lint. The drafting model mirrored the density and caveat-heavy tone of what it was given.
- **Nothing measured the reader's experience.** The review skill explicitly ruled out readability thresholds, so every draft passed agent review.
- **Each question was an island.** Pattern tags named topics but taught nothing transferable, and handbook links were relative file paths with generic labels.
- **Introductions front-loaded assumptions.** Readers met retry ownership and workload numbers before learning what the system was for.

The reset rewrote the skills around a fixed chapter shape, added a design-move knowledge graph and a deterministic readability gate, and regenerated all five pilots.

## What the numbers show

Measured with `tools/lint_readability.py` (prose = paragraph text only).

| Chapter | Mean paragraph (words) | p90 | Longest prose run | Figures | Tables | Callouts | Lint errors |
|---|---|---|---|---|---|---|---|
| Notifications — old | 76 | 114 | 705 | 1 | 2 | 0 | 10 |
| Notifications — new | 28 | 44 | 127 | 4 | 5 | 13 | 0 |
| Log publishing — old | 75 | 107 | 419 | 1 | 0 | 0 | 8 |
| Log publishing — new | 37 | 56 | 152 | 4 | 5 | 11 | 0 |
| News feed — old | 80 | 119 | 581 | 1 | 2 | 0 | 13 |
| News feed — new | 35 | 63 | 100 | 4 | 4 | 11 | 0 |
| Market data feed — old | 38 | 60 | 240 | 3 | 0 | 0 | 0 |
| Market data feed — new | 30 | 52 | 177 | 4 | 9 | 13 | 0 |
| Risk-limit fan-out — old | 42 | 67 | 254 | 2 | 2 | 0 | 0 |
| Risk-limit fan-out — new | 35 | 66 | 155 | 4 | 6 | 11 | 0 |
| *Handbook Ch 23 (reference)* | *33* | *62* | *211* | *2* | *2* | *4* | — |

Total length barely changed: the old chapters ran 3,300–4,000 words, the new
ones 3,000–4,100. **The problem was never length. It was shape.**

The market-data and risk-limit drafts pass the shape lint because they were
already list-heavy. Their problem was different: they read as checklists and
formal contracts (symbols like `U`, `N`, `p`, `T_stale`, `A_stale` introduced
before any scenario), with Core / Deep dive / Stretch labels on every section.
The lint is necessary but not sufficient, which is why the review skill pairs it
with a fourteen-question reader checklist.

Words of framing before the first requirement (excluding quoted prompts and callouts):

| | Old | New |
|---|---|---|
| Notifications | 313 | 97 |
| Log publishing | 251 | 78 |
| News feed | 281 | 89 |

## Root causes

### 1. The instructions were walls of text, and the output copied them

The drafting skill (11 KB), style guide (14 KB), review skill (7 KB), content
`AGENTS.md`, and pattern guide together held about 38,000 characters, with over
120 negations. Each feedback round appended prohibitions — "do not invent",
"not a pronoun quota", "this is not a four-part template" — so the drafter
learned that every sentence must pre-empt an objection. The old style guide has
a 534-word prose run and a 151-word paragraph: it fails the lint it should have
inspired.

**Fix:** a 7 KB skill written as positive steps, with the detail moved into three
short references: a chapter skeleton with budgets, real before-and-after
rewrites, and a finance-lens table.

### 2. There was no picture of the target shape

The skill described qualities ("teach the reasoning", "derive, don't assert")
but never showed what a section looks like. The other model's working copy did
not contain the Hello Interview examples at all — its own review notes say so —
so it never saw the shape it was asked to match.

**Fix:** `chapter-skeleton.md` gives each section a budget and an example, and the
five new pilots are the reference implementations.

### 3. The reviewer could not fail a wall of text

The review skill told the agent not to use word-count or readability thresholds,
and agent review passed every draft. The human editor was the only shape gate.

**Fix:** `tools/lint_readability.py` (tested, in `make readability` and CI) fails
paragraphs over 110 words, prose runs over 320 words, and chapters with fewer than
two figures. The review skill adds a fourteen-question reader checklist run on the
rendered PDF.

### 4. A good rule was applied to every paragraph

"For central choices, show the need, the alternative, the choice, and its cost"
became four ideas per paragraph, everywhere. Combined with "structure by prose,
not labels" (a handbook rule about per-item label scaffolds), the drafter avoided
lists and tables and packed each comparison into one long paragraph.

**Fix:** comparisons become tables; steps become numbered lists; each paragraph
carries one idea. The four-part reasoning moves to a deep dive's option blocks,
where it belongs.

### 5. No knowledge progression across questions

`design_patterns` tags such as "Scale reads" labelled topics without teaching a
reusable decision, and nothing connected one question to the next. Handbook
links were `../../../release1/...chapter.md` paths labelled "the handbook's
pre-trade risk chapter" — meaningless in print.

**Fix:** a registry of 26 design moves (`taxonomy/design-moves.yaml`), each
introduced by exactly one question and reused by later ones with a callback.
Metadata records `track_order`, `design_moves`, and `handbook_chapters`, and the
validator enforces the graph: moves exist, introduction precedes reuse, the recap
names every move, and every linked handbook chapter is declared and real. Links
now read "Handbook Ch 23 — *The Book That Is Silently Wrong*". `TRACK.md` and a
generated map show the whole graph.

### 6. Tooling made diagrams and pages worse

The Mermaid-subset renderer supported no edge labels, grouping, or emphasis,
which is why diagrams came out as flat node lists. The ReportLab guide builder
put every diagram on its own landscape page, leaving half-empty portrait pages
behind it.

**Fix:** Graphviz sources with the handbook palette and `role=` shorthands
(`new` highlights what a step adds); compact figures now stay inline in the
legacy builder; and `tools/build_sd_preview.py` renders the track the way the
handbook is rendered (Markdown → HTML → Chromium PDF).

### 7. Generic prompts got generic answers with finance sidebars

The social news feed and an app-notification system were answered as
consumer-tech questions, with "Domain variant" paragraphs appended for finance.

**Fix:** choose the trading-firm reading when the prompt allows it, say so in one
line, and contrast it with the consumer-tech version in a single callout at the
decision it changes.

## What changed

| Area | Files |
|---|---|
| Skills | `.agents/skills/draft-system-design/` (skill + 3 references), `review-question`, `link-interview-foundations` (+ regenerated handbook map) |
| Guidance | `content/STYLE_GUIDE.md`, `content/AGENTS.md`, `PROJECT_PLAN.md` note, `README.md` |
| Knowledge graph | `taxonomy/design-moves.yaml`, `content/system-design/TRACK.md`, `tools/build_track_map.py` |
| Tooling | `tools/lint_readability.py`, `tools/build_sd_preview.py`, Graphviz support in `tools/render_diagrams.py`, `tools/validate.py` (skeleton, graph, handbook checks), `tools/build_pdfs.py` (Graphviz SVG, inline figures), `tools/ingest.py` scaffold, `tools/deduplicate.py` |
| Schema and tests | `schemas/system-design.schema.json`; `tests/test_readability.py`, `tests/test_track.py`, updated `tests/test_validation.py` — 45 tests pass |
| Pilots | five packages under `content/system-design/`, rendered in `generated/pdf-preview/system-design-track-preview.pdf` |

The old pilots are untouched in `tmp/foundational-e2e` for comparison. Previous
versions of every replaced skill and guide are saved in `tmp/pre-v2-backup/`.

## Decisions for the editor

1. **News feed interpretation.** The new chapter reads "various feed format" as vendor news ingestion and names the social feed as the consumer-tech version. If you want the social feed, the chapter needs a rewrite around fan-out on write versus read.
2. **Notification framing.** Reframed as a trading firm's internal alerting platform (risk breaches, alert storms at the open). Confirm this matches the interviews you have seen.
3. **PDF pipeline.** The ReportLab builder still works, but `make sd-preview` is what the track should look like. Adopting it for the system-design guide would add pandoc and Playwright as build dependencies.
4. **Graphviz.** Diagrams now need `dot` to re-render (`brew install graphviz`). Committed SVGs validate without it; the stale check runs only when the local Graphviz version matches the one that rendered the SVG.
