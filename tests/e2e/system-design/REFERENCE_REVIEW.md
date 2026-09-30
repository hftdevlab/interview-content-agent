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

## Follow-up: reasoning, not just section order

The next human review accepted the structure but rejected the prose as a stack
of conclusions. Re-reading the visible metrics tutorial makes the gap concrete:

- Its entities discussion starts with the need to examine different cuts of a
  measurement, connects identifying attributes to distinct histories, and only
  then formalizes the vocabulary. We need the equivalent motivation for each
  question's own entities, not to copy metrics/labels/series into a log system.
- Its data-flow discussion precedes its component architecture and interfaces.
  Continuous writes, investigative reads, and notification work have different
  demands; those differences give the later component boundaries a reason.
- Its interface section distinguishes readable JSON notation from a potential
  binary production encoding. The transferable lesson is to justify the
  representation with workload and operational needs, not to require Protobuf.
- It derives ingestion rate from source count and emission frequency. The
  workload drives batching and downstream capacity discussion rather than
  appearing as disconnected sizing arithmetic at the end.

Our previous first-person-free drafts often named components before those
reasons. The earlier "keep the passing answer small" trial instruction also
biased logging toward a workload that avoided write scaling. Latest feedback
takes precedence: keep the explanation accessible while retaining the defining
ingestion challenge. New workload numbers remain explicit illustrative choices,
not retroactively attributed to the raw prompt or copied from the reference.

The shared guidance now asks for a first-person candidate walkthrough and
decision-level reasoning. Review must examine central choices, not only verify
headings, factual conclusions, or narrative continuity. The editor's exact new
request is archived in `reasoning-feedback.md`; replay it through the same
feedback workflow and preserve the earlier notes and results as history.

For the revised ingestion discussion, primary references checked separately
from the style PDF include the [Protobuf overview](https://protobuf.dev/overview/)
and [wire encoding](https://protobuf.dev/programming-guides/encoding/), the
[OpenTelemetry log data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/),
and [Elastic's indexing guidance](https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/indexing-speed).
These help verify representation, event/observation timestamps, and bulk-write
trade-offs. They are not a mandate to adopt those products, nor evidence for a
particular server's throughput. Keep their use selective and link the source
at the point where a chapter needs it.
