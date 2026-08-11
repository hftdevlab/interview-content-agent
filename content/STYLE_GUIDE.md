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

Start with only the requirements needed to define the system boundary. When the
prompt describes a platform too large for one interview, say so prominently,
sketch the context, and agree with the interviewer on a few deep dives. Do not
present a minute-by-minute allocation: the interviewer controls where the
conversation goes.

Build a minimal correct design before scaling it. Deep dives should emerge from
an access pattern, failure mode, latency budget, or consistency requirement.
Use diagrams after the reader understands the decision they represent. A
typical system-design chapter should render in at most ten pages; an unusually
complex question may use up to fourteen.

For a flagship complex question, the upper budget is available for genuine
interview depth; do not compress away the decisions that make the question
valuable. Show the complete context, make the likely deep dives explicit, and
develop those paths while keeping adjacent components concise.

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
- Define uncommon terms once; link to a primary tutorial/specification instead
  of re-teaching a large prerequisite.
- Prefer the companion handbook for foundations it already covers. Use a
  primary specification or authoritative project documentation for protocol,
  kernel, library, and platform details; never pad a chapter with a second
  generic explanation of the same technique.
- Avoid long inventories without a decision or narrative.
- Keep code and diagrams close to the reasoning they support.
