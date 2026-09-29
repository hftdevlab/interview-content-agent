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

Use an interview walkthrough, not an implementation specification. The reader
should see how the requirements lead to one working design, then learn how to
handle the design's most interesting limits. The current presentation replaces
the historical good/great/rubric checklist in `PROJECT_PLAN.md`:

1. **Question and clarifications**: describe the product and resolve the few
   ambiguities that change the answer. State the chosen interpretation and
   assumptions. For an oversized platform, agree on a small interview scope.
2. **Requirements**, with separate **Functional requirements** and
   **Non-functional requirements**: prioritize what users can do and the
   qualities that make this design challenging. A handful of meaningful
   requirements is more useful than an exhaustive production contract.
3. **Core entities**: introduce the domain nouns and their relationships before
   their detailed representation. Distinguish a logical event from a delivery
   attempt, for example, when that distinction matters to later reasoning.
4. **API and data schema**, where useful: sketch the few requests, wire events,
   queue records, or fields that support the main flows. Not every question
   needs HTTP endpoints or a database schema. Omit irrelevant interface work.
5. **High-level architecture**: include at least one component/data-flow
   diagram and explain the design by walking through the functional
   requirements. Follow a request from entry to response and explain what is
   stored along the way. Finish the main flow before diving into every edge case.
6. **Deep dives**: select the challenges that follow from the non-functional
   requirements. Frame them as useful engineering questions and evolve the
   same design. A local bad/good/great comparison is optional; two complete
   competing solutions are normally unnecessary.
7. **Follow-ups and pitfalls**, optionally: include only the few realistic
   extensions or mistakes not already taught. At most three of each.

The high-level architecture should make the system understandable before the
deep dives make it robust or scalable. It may defer a clearly named limitation;
it must not claim a guarantee that the unfinished design does not provide.
Explain unfamiliar components by what they do in this flow. Do not repeatedly
define every box as a process or turn every paragraph into a contract clause.

Use natural transitions and connected prose. A concrete example or a short
request trace often explains more than another requirements table. A named
character, failure story, numerical estimate, formal invariant, or
Core/Deep dive/Stretch label is a tool, not a mandatory writing template.
Calculate when the result determines a design decision, and introduce symbols
at that point rather than in an opening inventory. Keep technical precision at
the relevant decision boundary without repeating the same caveats everywhere.

Select reusable challenges from [the design-pattern guide](SYSTEM_DESIGN_PATTERNS.md).
Store stable IDs in `metadata.yaml.design_patterns`, display matching labels in
a short `Design patterns:` line near the question, and connect those patterns
to the relevant deep dives. Tags should help the reader recognize a transferable
decision, not merely advertise technologies or decorate the page. Trading-domain
applications belong where they illuminate a real difference, not as forced
changes to a general-purpose prompt.

At least one diagram must orient the architecture; use an additional sequence
diagram only when it adds important ordering detail. Put diagrams at complete
reasoning boundaries, not between a heading and its explanation. The metadata
already supplies the printed caption; do not duplicate it in Markdown.

A foundational answer should stand alone before optional advanced branches.
An unusually complex flagship question can use more space for its defining
technical decisions. Standard questions have a ten-page ceiling and complex
ones fourteen, not mandatory page targets. Keep improvements optional and at
most three. Do not append a compulsory failure matrix or evaluator rubric.
Preserve useful handbook links instead of re-teaching prerequisites. Do not
prescribe a minute-by-minute schedule or expose editorial workflow in the prose.

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

- Typical readers have strong CS and coding foundations but may lack trading
  systems experience, or have finance experience but need sharper interview
  explanations. Do not re-teach standard topics such as STL basics or TCP versus
  UDP. Explain HFT-specific decisions such as kernel bypass or cache-local
  allocation when they materially affect the answer, and link to dedicated
  chapters as the catalog grows.
- Use natural engineering language and short transitions that explain why the
  next section exists.
- Prefer a worked example, state trace, or formula over generic adjectives.
- Prefer one running example over a sequence of unrelated miniature examples.
- Define uncommon terms once; link to a primary tutorial/specification instead
  of re-teaching a large prerequisite.
- Prefer the companion handbook for foundations it already covers. Use a
  primary specification or authoritative project documentation for protocol,
  kernel, library, and platform details; never pad a chapter with a second
  generic explanation of the same technique.
- Avoid long inventories without a decision or narrative.
- Keep code and diagrams close to the reasoning they support.
