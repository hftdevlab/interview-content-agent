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

Use an instructor-led interview tutorial, not an answer script or implementation
specification. The reader
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
3. **Core entities**: start with the operation or distinction that needs a
   concept, explain its relationships in ordinary language, then name and
   accurately define it. Distinguish a logical event from a delivery attempt
   because one event can have several delivery outcomes, not because the
   template needs another noun. Detailed storage fields come later.
4. **API and data schema**, where useful: sketch the few requests, wire events,
   queue records, or fields that support the main flows. Not every question
   needs HTTP endpoints or a database schema. Derive important operations and
   fields before giving the contract. Where wire format affects the workload,
   explain the serialization trade-off instead of silently choosing a format.
5. **High-level architecture**: first explain the data flow and derive its
   components, then summarize the design with at least one component/data-flow
   diagram. Follow a request from entry to response and explain what is stored
   along the way. A conceptual flow can precede the API section when that helps
   the reader understand who calls it. Finish the flow before every edge case.
6. **Deep dives**: select one to three challenges that follow from the non-functional
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

Use the instructor's first-person narration for all system-design tutorials.
The author guides the reader through a worked design, explains what deserves
attention, and teaches how to adapt the reasoning. An inclusive "we" belongs
here; a running candidate monologue answering an interviewer does not. Do not
turn the chapter into a script to memorize or a succession of interview tips.
This is not a pronoun quota; factual definitions, requirements, tables, and code
can remain direct. Do not invent the narrator's professional experience. A concrete example or a short
request trace often explains more than another requirements table. A named
character, failure story, numerical estimate, formal invariant, or
Core/Deep dive/Stretch label is a tool, not a mandatory writing template.
Calculate when the result determines a design decision, and introduce symbols
at that point rather than in an opening inventory. Keep technical precision at
the relevant decision boundary without repeating the same caveats everywhere.

#### Show the reasoning, not just the result

A useful paragraph lets the reader understand why a choice follows from the
problem. For central choices, expose the need, the relevant alternative, the
reason for selecting an approach, and its cost or reversal condition. Vary the
presentation naturally; do not stamp those four labels on every paragraph.
An accurate sequence of prescriptions is still not a tutorial, even if each
starts with "I would". Rhetorical questions need explanatory answers, not just
component names. Requirements should describe desired behavior, not smuggle in
the architecture that the next sections are supposed to derive.

For example, "Use a worker, retries, and a durable queue" states three results.
"I want to separate two moments here: saving a notification and asking an email
provider to send it. If we wait for the provider before replying, its slowness
also delays the inbox. Background delivery removes that wait, but now a restart
could erase unfinished sends. Storing pending work with the inbox item gives
the worker something durable to resume" teaches the causal
connection. The subsequent discussion can weigh database work rows against a
separate broker. This is an illustrative reasoning passage, not prose to copy
into every question.

Before the diagram, the reader should already understand where data originates,
why it is retained or transformed, and who consumes it. Different rates,
latencies, and failure boundaries then explain the separation into components.
The diagram consolidates that understanding; it should not introduce a finished
architecture that the reader must reverse-engineer from later sections.

Interfaces need the same treatment. JSON may be convenient for a readable
interview example or an easy-to-debug public API; a typed binary format such as
Protobuf can be worth evaluating for high-rate controlled producer/consumer
paths. Explain the relevant byte, parsing, interoperability, and schema costs.
Do not imply that binary always wins, invent a speedup, confuse serialization
with transport, or insert this comparison where representation is immaterial.
Use an authoritative reference such as the [Protobuf encoding guide](https://protobuf.dev/programming-guides/encoding/)
for codec details, while teaching the workload decision in the chapter itself.

For ingestion questions, throughput is often the problem, not an optional
extension. Make source counts, event rates/sizes, bursts, freshness, and retention
explicit enough to reason about records/second, bytes/second, and request work.
Then show how batching, buffering, partitioning, and storage address different
limits. A queue buys time; it does not fix a sustained capacity deficit. Keep
illustrative assumptions labeled and distinguish workload arithmetic from an
unmeasured hardware benchmark. Do not choose an artificially small workload
merely to avoid teaching the defining scaling challenge.

Conclude important derivations with their reusable decision principle in
ordinary prose. A pattern tag or prerequisite link is navigation, not a
substitute for explaining when a technique helps and what would change our
choice. Mechanism-level foundations can stay linked; problem-specific entity
definitions and the reasoning needed to choose a mechanism belong here.

Select reusable challenges from [the design-pattern guide](SYSTEM_DESIGN_PATTERNS.md).
Store stable IDs in `metadata.yaml.design_patterns`, display matching labels in
a short `Design patterns:` line near the question, and connect those patterns
to the relevant deep dives. Tags should help the reader recognize a transferable
decision, not merely advertise technologies or decorate the page. Trading-domain
applications belong where they illuminate a real difference, not as forced
changes to a general-purpose prompt.

#### The finance-engineering audience

Teach for hedge-fund, trading, and finance engineers, including when using a
general-purpose interview exercise. State which subsystem we are designing and
what it must protect before importing consumer-tech assumptions. Modest user
counts can coexist with bursty ingestion, stringent recovery needs, and tail
latency constraints. Availability, testability, and fault tolerance often
deserve more attention than hypothetical global scale, but derive that priority
from the stated workload; do not make it a universal industry claim.

Highlight a domain difference where it changes a decision. For example, a
research-content feed may need entitlement checks that a public social feed
does not; asynchronous notification delivery cannot itself enforce a risk
limit; dropping diagnostic logs under overload differs from losing an audit
record. Explain the consequence for this choice, not an unrelated finance
sidebar. Preserve the raw question and label domain variants as variants.
Use a concrete recovery or fault-injection test when it teaches the boundary.

Latency, throughput, low-level system behavior, and network costs can shape
the initial design, not just a final optimization list. That does not mean
adding kernel bypass to an email service or a dashboard. Define what must
remain available and when rejecting work is safer than using stale state.
CAP is a consistency/availability trade-off under network partition; it does
not rank latency, testability, fault tolerance, and scalability, nor does it
justify executing with unsafe risk state. Link to handbook mechanisms where
they become relevant instead of teaching the foundations again.

At least one diagram must orient the architecture; use an additional sequence
diagram only when it adds important ordering detail. Put diagrams at complete
reasoning boundaries, not between a heading and its explanation. The metadata
already supplies the printed caption; do not duplicate it in Markdown.

A foundational answer should stand alone before optional advanced branches.
Foundational means accessible reasoning and focused scope, not a toy workload.
An unusually complex flagship question can use more space for its defining
technical decisions. Standard questions have a ten-page ceiling and complex
ones fourteen, not mandatory page targets. Previous five-page examples are not
a length target; spend space on derivations and cut repetition first. Keep improvements optional and at
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
