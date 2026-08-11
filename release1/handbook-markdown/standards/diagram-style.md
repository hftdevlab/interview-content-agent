# Diagram authoring standard

Diagrams are **committed SVG files**, not generated at build time and not described in prose placeholders.

```
chapters/<chapter-id>/figures/fig-<chapter>-<n>.svg
```

Referenced from the chapter with standard markdown, so they render in GitHub, in the HTML build, and in the PDF build without a toolchain:

```markdown
![Alt text describing what the figure shows](figures/fig-c1-1.svg)
*Figure c1-1 — Caption stating the takeaway.*
```

## Why SVG files rather than a diagramming DSL

Mermaid and similar tools are convenient for flowcharts and cannot express the diagrams this book needs — memory layouts, address-space maps, hardware topology. Those require precise spatial arrangement, which is the entire content of the figure. Hand-authored SVG gives that control, has no build dependency, and diffs readably.

## Required properties

**Self-contained.** No external fonts, no external stylesheets, no embedded raster images. A reader who opens the file alone sees the finished figure.

**Legible on white.** The book is printed and rendered light. Explicit colours, no reliance on inherited CSS.

**Readable at print width.** `viewBox` width 640–760, height as needed. Text no smaller than 11px in that coordinate space. Assume the figure may be printed at about 15cm wide.

**Text is text.** Never convert labels to paths — they must be selectable, searchable, and accessible.

**Alt text is required** and describes what the figure shows, not that it is a figure.

## Palette

Fixed, so figures look like one book:

| Token | Value | Use |
|---|---|---|
| ink | `#1f2328` | Text, primary strokes |
| muted | `#6b7280` | Secondary text, annotations |
| rule | `#9aa4b2` | Boxes, dividers |
| fill | `#f3f4f6` | Neutral box fill |
| accent | `#1a6fb5` | The subject of the figure — the thing the reader should look at |
| accentFill | `#dbeafe` | Fill for accented boxes |
| warn | `#b5501a` | Cost, failure, the wrong path |
| warnFill | `#fde8d7` | Fill for warning boxes |
| ok | `#2f7a4f` | The good path, when a figure contrasts two |

Colour carries emphasis, never sole meaning: anything shown in colour is also distinguished by label, shape, or position, so the figure survives greyscale printing and colour-blind readers.

Type: `font-family="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"`. Labels 13px, annotations 11–12px, titles 14px semibold.

## Content rules

Each figure carries the three fields from the brief's `diagram_expectations`:

- **purpose** — what it makes visible that prose cannot;
- **critical distinction** — the thing the reader must not confuse;
- **forbidden implication** — what the figure must not lead the reader to believe.

These live in an SVG comment at the top of the file, so the constraint travels with the artifact and survives editing.

**One idea per figure.** A diagram showing three things shows none of them. Split it.

**Label the thing, not the category.** "`head_` — written only by the producer" beats "Producer index".

**Show the cost.** Where the figure exists to explain a cost, mark where it is paid — a fault, a crossing, a copy — rather than only drawing the structure.

## When a chapter needs one

Spatial or structural content: memory layout, address spaces, hardware topology, wire formats, state machines. If the prose is describing an arrangement in space, the figure is doing work prose cannot.

Sequential or causal content usually does not need one — a worked trace table is better than a flowchart, and quizzes beat both.


## Generation and verification

Figures are **generated from `build/figures_*.py`** using the shared helpers in `build/figlib.py`, not hand-edited as XML. Editing the `.svg` directly is a mistake: the next regeneration overwrites it, and the header of every generated file says so.

`figlib` emits **inline presentation attributes rather than CSS classes**, so figures survive markdown renderers that strip `<style>` blocks. Use `wrap()` and `footer()` for any text longer than a few words — the library measures and breaks lines rather than trusting the author's eye.

**`build/lint_figures.py` must pass before a figure is considered done.** It checks:

- no text overflows the `viewBox` horizontally, accounting for `text-anchor`;
- no text sits below the bottom edge;
- no text is smaller than 10.5px in figure coordinates.

This exists because overflow is invisible in the source and invisible in most previews — the SVG is valid, the file parses, and the text is simply cut off at the edge in the rendered output. The first pass of figures for this book had **37 such defects** and every one of them looked fine until the PDF was rasterised and read.

## Verifying the real output

`build/make_book.py <MODULE>` produces HTML and PDF. Figures are **inlined** into the HTML rather than linked, which is why the output is self-contained and why relative-path resolution never arises.

Markdown previews do not resolve `figures/*.svg` relative links — so a chapter that looks broken in a preview may be entirely correct. **Judge figures from the PDF, never from a markdown preview.** Rasterise a page and look at it:

```
python3 build/make_book.py C
pdftoppm -r 55 -png -f 3 -l 3 build/out/module-C.pdf page
```
