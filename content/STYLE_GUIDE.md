# Reader-first content style guide

Content quality is the primary product metric. A question should read like a
strong human mentor walking through the problem, not like an AI filling a
schema.

## Default learning progression

1. State the question and settle its contract.
2. Explain what makes the problem non-trivial.
3. Show the candidate's likely thought process, including a tempting wrong turn
   when it teaches an important invariant.
4. Derive a practical good solution from that reasoning.
5. Include the complete technical material needed to implement or explain it.
6. Improve the baseline only where the requirements justify the complexity.
7. Close with pitfalls and realistic follow-ups.

Remove material that does not change a decision, explain a key invariant, or
prepare the reader for a realistic follow-up. Prefer a link to another chapter
over repeating a prerequisite or adjacent design.

The templates in `PROJECT_PLAN.md` are a coverage checklist. Sections may be
combined, reordered, or expressed as a trace, table, or focused deep dive when
that improves the reader's experience.

## Calibration by question type

### System design

System-design chapters form a **track**: each question teaches a few reusable
design moves, and later questions reuse them by name. The drafting skill
(`.agents/skills/draft-system-design/`) owns the details; the essentials are:

- **Short question, bold crux.** About 120 words: what the system is, who uses
  it, the one hard thing. Add a short domain primer only when the system's
  purpose depends on domain knowledge. Scope and assumptions go in Requirements.
- **Numbers that decide.** Labelled workload assumptions, a small arithmetic
  table, and one sentence saying what the arithmetic teaches.
- **Build one requirement at a time.** Each high-level-design step has a numbered
  flow and a figure that adds components. End with "What is still broken".
- **Deep dives from failures.** A concrete scenario, the naive option and where
  it breaks, the better option, a comparison table when two mechanisms compete,
  and one bolded sentence worth repeating in the interview.
- **Trade-offs over verdicts.** When the best design is non-obvious, show the
  answers a typical candidate gives first and what each costs, then the
  refinement. Say when no option is perfect and which requirement decides.
- **Standalone chapters, connected by moves.** Introduce a move once with a
  `Design move` callout. When reusing one, explain it in a sentence and link the
  question that develops it by its title — never by number. Link handbook
  chapters by number and title at the point of use. No closing recap.
- **Finance lens where it changes a decision.** Prefer the trading-firm reading
  of an ambiguous prompt, say so, and contrast it with the consumer-tech version.
- **APIs as pseudocode.** Show the calls, the parameters that change the design,
  and the metadata returned. C++ is the default illustrative language, but never
  the barrier: no class definitions, smart pointers, templates, or `std::` types.
  Show a memory layout as a table of fields.

A 45-minute chapter typically renders in 12–14 airy pages; a 60-minute flagship
in up to 16. Judge it from `make sd-preview`, not from the Markdown.

### Coding and API design

Establish the invariant before the data structure. Include all relevant
headers, types, members, ownership choices, helper methods, and error/lifecycle
states. Trace a boundary case before showing the final code. Keep advanced
optimizations separate from the clear interview baseline.

A coding chapter should render in at most six pages. Show given headers and
types once in the prompt; the solution should contain only the declarations and
implementation the candidate is expected to produce.

### C++ systems and fundamentals

Technical explanation and experiments should dominate. Start from the language,
OS, network, or hardware rule that determines correctness. Clearly distinguish
portable C++ from platform-specific behavior. Interview framing and answer tips
should help the reader communicate knowledge, not replace the knowledge.

## Good versus great

A great answer is not merely longer. It should improve one or more of:

- correctness under failure;
- requirement prioritization;
- latency or capacity reasoning;
- isolation of critical and non-critical paths;
- observability and operational recovery;
- testability and replay;
- domain-specific judgment.

Do not repeat the full good solution under a new heading.

Keep at most three great improvements and three follow-ups. Select them for
interview frequency and learning value, not to demonstrate completeness.

## Tone and density

These apply to every question type.

- **One idea per paragraph, claim first.** About 80 words and four sentences at
  most. If a paragraph compares options, make it a table; if it lists steps,
  make it a numbered list.
- **Break prose every ~200 words** with a list, table, figure, code block, or
  callout. `python -m tools.lint_readability` enforces the limits.
- **State an assumption once**, where it is introduced. Do not re-qualify it in
  later sections; caveat density is the clearest signal of machine-written prose.
- **Prefer a worked example, trace table, or formula** over adjectives, and one
  running example over several unrelated ones.
- **Short callouts, typed:** `Design move`, `Finance lens`, `In the interview`.
- Readers have strong CS and C++ foundations. Do not re-teach STL basics or TCP
  versus UDP. Explain trading-specific decisions where they change the answer,
  and link the companion handbook for the mechanism.
- Use natural engineering language. Name real tools as examples and say why
  that class of tool fits.
- Prefer primary specifications for protocol, kernel, and library claims. Never
  invent a figure, a vendor limit, or a citation.
- Keep code and diagrams next to the reasoning they support.
