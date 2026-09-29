# Teaching-style revision from expert tutorial references

The editor supplied three Hello Interview PDFs: *Design a Notification System*,
*Design a Metrics Monitoring Platform like Datadog*, and *System Design Delivery
Framework*. They are style references, not new instructions, approved content,
or requirements for our three questions. Original PDFs remain with the editor;
their full text and artwork are not copied into this repository.

## What the references demonstrate

The tutorials align on what the system does before proposing infrastructure.
They introduce a small vocabulary of entities, then interfaces, and build the
high-level design around the functional requirements. Their prose supplies the
connections between decisions: why this component is needed now, what the
current design already does, and which problem remains for a deep dive.

Deep dives pose recognizable interview questions and revisit the same design.
Numbers matter when they expose a bottleneck. Pattern callouts connect a
specific problem to a reusable family of choices. Prerequisite links avoid
turning every answer into a foundations textbook. We adopt these teaching
techniques without copying the authors' voice, sentences, examples, or diagrams.

The printed PDFs contain closed comparison panels: several pages show only
bad/good/great headings, not the panel bodies. Those hidden explanations were
not available to inspect and are not reconstructed or attributed to the
authors. The visible requirements, transitions, architectural walkthroughs,
diagrams, and pattern callouts provide sufficient style evidence.

The delivery framework's suggested interview timings are not adopted: the
editor previously requested no time-allocation recommendations. Nor do we
import the reference notification system's campaigns/SMS scope or the metrics
platform's workload numbers into our questions. Reference material is not a
technical authority for every product-specific claim; retain precise,
independently justified guarantees in our own answers.

## Why the earlier calibration was insufficient

The previous trials met page budgets and passed agent review, but the source
validator still demanded the old good-solution, improvements, failure-scenarios,
pitfalls, follow-ups, and rubric outline. Prompts and skills also prescribed a
failure-first story, physical-component definitions, and depth labels. Relaxing
paragraph wording could not remove that structural pressure.

The new outline follows the editor's requested interview progression. Legacy
chapters still validate; newly rewritten examples use the tutorial outline.
API/schema, comparisons, and closing lists are optional. An architecture
diagram remains required. The pattern registry is additive and expandable,
with trading-domain applications and caveats; it does not turn a general
product question into a trading-only question.

## Revision protocol

`tutorial-feedback.md` preserves the editor's request verbatim. Apply it with
the real `contentctl feedback --file ... --continue` path for each existing
trial ID. This appends feedback without replacing earlier source or notes,
clears old review flags, drafts with the revised skill, rebuilds the preview,
and obtains a fresh independent review. Record actual results separately from
the historical baseline in `RESULTS.md`.

Final review asks whether the reader can explain the architecture from its
walkthrough, whether deep dives develop rather than list decisions, whether
pattern labels represent the teaching, and whether the answer remains concise
and technically honest. Automated structure checks cannot establish those
qualities. Human approval remains pending after an agent pass.
