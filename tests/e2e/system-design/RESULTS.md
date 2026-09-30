# Foundational system-design readability evaluation

This record preserves the first calibration and its limitations. Subsequent
human feedback rejected its specification-like presentation despite the agent
passes below. The [expert-style revision](REFERENCE_REVIEW.md) supersedes that
presentation guidance; its results are recorded separately after fresh runs.
The next review accepted the outline but found that the prose still stacked
conclusions without enough reasoning. Earlier agent passes and short page
counts below are historical results, not evidence that the editor accepted
their teaching quality. The reasoning-focused revision is recorded last.

## Setup and scope

The editor requested three simpler questions after accepting the advanced
risk-limit example: a mixed-format news feed, notifications, and application-log
publishing/query. Each raw one-line prompt is retained in this directory and
archived unchanged in the generated question package. The interpretation and
foundational calibration are recorded separately in its expert notes.

The live trials use the real `contentctl` generation, PDF gate, and independent
read-only review. They use the existing local Codex configuration (gpt-6-astra,
medium reasoning), without selecting a special model for these examples. No
human approval or publication command is part of the trial. Automated reviewer
judgments are evidence for editor review, not a substitute for it.

The starting point includes PR #4's accepted tutorial rules. Although PRs #3
and #4 were both merged on GitHub, #4 was merged into the old base branch after
PR #3 reached main. This branch integrates that accepted merge into main's history
before applying the new calibration.

## First news-feed trial

The initial draft was technically useful and passed independent agent review.
It developed media separation, indexed chronological reads, cursor pagination,
and optional fan-out. After an automatic diagram correction it occupied six
pages and approximately 2,610 words. Its first sequence diagram exceeded the
PDF landscape frame; the controller retried, and the agent consolidated steps
already covered by the prose.

The main readability review still found unnecessary friction:

- Nearly every explanatory paragraph repeated a bold depth label and thesis.
  Navigation became a visible writing template rather than a few useful signs.
- A symbolic requirements table introduced page size, follows, rates, latency,
  freshness, retention, and retry-window notation before explaining the design.
- Reader-facing prose exposed editorial process language such as
  "Interpretation authorized by the expert notes" and described why a runnable
  package was not attached. Those details belong in review records.

This is a useful counterexample to treating either an agent pass or the page
budget as proof of readability.

## Generalized changes

The drafting prompt, style guide, and draft/review skills now calibrate the
passing core to the question. A foundational answer must remain understandable
without its advanced branches. Simple designs may remain valid at small scale;
the tutorial should demonstrate the workload or failure that justifies a change.
Requirements begin in plain language, symbols appear with the calculation that
uses them, and depth labels mark sections rather than every paragraph. None of
these rules removes the deeper contract reasoning required by advanced prompts.

The workflow regression suite also runs all three raw fixtures through intake
and a simulated review lifecycle. It verifies source/notes preservation and
that a fresh failed review clears an earlier agent pass. This deterministic
test checks the lifecycle, not the teaching quality of model-generated text.

The revised news-feed run exposed two controller problems. Source validation
checked an old SVG before rebuilding the changed Mermaid, wasting an agent
revision on a build artifact. The controller now renders valid diagrams from
the selected package first; malformed sources still fail validation. Also,
`continue` after an exhausted review loop restarted the general drafting prompt
instead of passing the saved findings. It now resumes from those findings and
requires another independent review. Regression tests cover stale SVG refresh,
invalid-source rejection, and review-failure recovery.

## First-calibration results

Live runs completed on 2026-09-28. All three workflows reached
`needs_human_review`, with only `agent_reviewed` true, no unresolved duplicate
candidates, and no clarification blockers. The controller preserved the raw
inputs and notes. The question packages contain the draft/review attempt counts
and individual results in `workflow.yaml` and `agent-review.yaml`.

| Question | Approx. words | Pages | Draft/review calls | Readability evidence |
|---|---:|---:|---:|---|
| [News feed](../../../content/system-design/sd-e2e-news-feed/question.md) | 2,354 | 6 | 5 / 3 | Two ordinary user journeys precede indexed retrieval and optional fan-out; notation appears with the calculation. |
| [Notifications](../../../content/system-design/sd-e2e-notifications/question.md) | 2,204 | 5 | 2 / 2 | Inbox and pending delivery rows form the core; provider acceptance, retry ambiguity, and the concurrency calculation are explained through one scenario. |
| [Log publishing/query](../../../content/system-design/sd-e2e-log-publishing-query/question.md) | 2,395 | 5 | 1 / 1 | A host record and an operator query motivate collection, commit/checkpoint ownership, bounded search, and visible data gaps. |

The news-feed total includes the baseline draft, a diagram-size correction,
the readability rewrite, an unnecessary stale-SVG correction before the
controller fix, and a focused pagination correction. The final review passed.
Notifications passed the content criteria on its first review; one automatic
revision condensed a sparse pre-diagram continuation and moved a detached
caption into metadata. Log publishing/query passed on its first draft and
review, using the revised guidance from the start.

The main agent also read all three complete chapters and inspected their
rendered pages. The final review bundle's chapter ranges are logs 4-8,
notifications 9-13, and news feed 14-19. The accepted advanced examples follow.
All new chapters have one diagram, three improvements, and three follow-ups.
They preserve complete reasoning within the ten-page standard-question limit;
the shorter length is an observed result, not a new mandatory page target.

No manuscript was manually rewritten outside the live workflow to produce
these results. The durable reusable changes are in the system-design drafting
and review skills, `content/STYLE_GUIDE.md`, and the controller prompts. The
caption rule also records a renderer-specific fact: metadata already supplies
the printed caption. These are versioned generation rules, not automatically
approved editorial-memory candidates.

Verification commands for this evaluation:

```bash
make ci PYTHON=/absolute/path/to/project/.venv/bin/python
```

This includes `make all`, repository validation, Python tooling tests, C++
practice tests, catalogs/Markdown builds, and release/review PDF gates. The
updated skills were also checked with the skill validator. PDFs, SVGs, catalogs,
and practice binaries are rebuilt outputs and are not checked in by hand.

## Human review still needed

Please assess whether the core explanations feel natural at interview pace,
whether the distinction between required reasoning and optional extensions is
clear, and whether the assumed news-feed interpretation matches the intended
question. Review approval remains a separate human-only operation; none of the
new content is approved or included in the approved-only release PDFs.

Three distinct topics test transfer beyond one worked example, but do not
establish statistical reliability across models or repeated fresh generations.
Human readability feedback remains the final product-quality judgment.

## Expert-style tutorial revision

The editor subsequently supplied the Hello Interview notification, metrics,
and delivery-framework PDFs and requested a different teaching structure.
The [reference review](REFERENCE_REVIEW.md) records what was visible in those
exports and what we adopted. The feedback is preserved verbatim and replayed
through the real feedback workflow for each existing question, not substituted
with manual manuscript edits outside the workflow.

The shared skills, style guide, workflow prompts, and intake scaffold now use
question/clarifications, functional/non-functional requirements, core entities,
useful interfaces, an architecture walkthrough, and selected deep dives.
Comparison sections, evaluator rubrics, and closing lists are no longer
compulsory. The validator accepts the new outline and existing legacy chapters,
while still checking requirements and the architecture diagram. Deduplication
recognizes the new question heading and excludes the pattern navigation line
from prompt similarity.

The ten-pattern registry includes trading applications and explicit caveats.
Selected pattern IDs are validated, their readable labels appear in tutorials,
and catalogs group questions under stable pattern anchors. This supports
discovery without treating shared pattern tags as proof of duplication.

| Question | Words | Pages | Additional draft/review calls | Patterns developed |
|---|---:|---:|---:|---|
| News feed | 2,144 | 5 | 1 / 1 | Scale reads; Fan-out write; Data transactions |
| Notifications | 2,037 | 5 | 1 / 1 | Data transactions; Multi-step workflows |
| Log publishing/query | 2,100 | 5 | 2 / 2 | High reliability; Time-series systems; Scale reads |

The notification chapter now explains its entities and interfaces before
tracing inbox creation and external delivery. The news-feed chapter connects
publishing and reading before conditional read scaling and fan-out. The log
chapter completes collection and search before analyzing acknowledgement,
retention/search cost, and backlog. Each uses one evolving design and retains
its useful handbook references. There are no mandatory good/great solutions or
evaluator rubrics. Logs has two closing follow-ups; the other chapters have
three. The scope and accepted technical guarantees are preserved.

All three passed their fresh independent workflow reviews. The log chapter's
first review found a two-line final-page spill; the automatic focused revision
shortened the ending and its second review passed. A separate read-only reader
check of each completed chapter found no important prose or technical issues.
Final preview chapter ranges are logs 4-8, notifications 9-13, and news feed
14-18. Existing advanced chapters follow and were not rewritten in this batch.

All three remain `needs_human_review`. Raw prompts are unchanged, previous
expert notes remain intact with the new feedback appended, and no approval or
publication command was run. Each workflow proposed two reusable editorial
memories; all six remain pending. The versioned generation-rule changes are
already active under this explicit editorial request, independently of the
human-only memory-approval lifecycle.

The full verification command remains `make ci`, including `make all`, source
validation, 67 Python tests, four C++ practice checks, Markdown lint, and both
release and review PDF gates. Skill validation and visual inspection of the
rebuilt chapters complete the review. These checks support another human
readability evaluation; they do not declare the content human-approved.

## Reasoning-focused first-person revision

The editor next accepted the outline but rejected the conclusion-stacking
prose. `reasoning-feedback.md` preserves that request verbatim. The metrics
reference was re-read, including its entity relationships, pre-architecture
data flow, representation discussion, and workload derivation. We borrowed
these teaching techniques, not its product requirements or prose.

Two independent audits found the same gap: the drafts often named final
entities and components before explaining their need. The tooling still urged
a small baseline, and the scaffold put a diagram before its explanation. That
encouraged an artificially modest logging workload and pushed the important
ingestion choices into optional extensions.

The shared drafting/review skills, style guide, content instructions, workflow
prompts, and intake scaffold now require first-person decision reasoning and
motivated concepts. Data flow comes before the architecture diagram. Relevant
serialization and storage choices follow from the workload. First-person
prefixes, headings, or a short page count do not establish teaching quality.
Review examines central decisions: why they are needed, the relevant
alternative, the trade-off, and what would change the choice. Fresh trial briefs
preserve the defining challenge; historical expert notes remain append-only.

All three revisions again used the real feedback workflow and fresh independent
reviews. No manuscript was manually substituted after generation.

| Question | Words | Pages | Additional draft/review calls | Concrete reasoning gained |
|---|---:|---:|---:|---|
| Log publishing/query | 2,829 | 6 | 2 / 2 | Collection follows from application isolation and restart needs; batching reduces request work; host partitioning trades write distribution for query fan-out; burst arithmetic predicts recovery delay; JSON/Protobuf is a workload and operational choice. |
| Notifications | 2,887 | 6 | 1 / 1 | Independent channel outcomes motivate delivery records; asynchronous sending creates durable pending responsibility; concurrency, quotas, and burst recovery are distinct capacity problems. |
| News feed | 3,123 | 6 | 1 / 1 | Media lifecycle and byte volume motivate separate upload/delivery; cursors and top-K selection follow from concrete problems; measured read savings must justify fan-out's writes, lag, and repair work. |

Logging now uses a clearly labeled illustrative fleet workload rather than the
earlier ten-host assumption. It remains operational log search, not the metrics
monitoring product in the reference. The log review first found a nearly empty
portrait page before the diagram; one focused automatic revision resolved it
without removing the ingestion and representation reasoning. Notifications and
news feeds passed their first reviews in this round.

A separate read-only reader check found no important issues in the three
rewrites and identified the concrete causal explanations summarized above.
It noted minor optional prose polish, not new technical or teaching blockers.
This is evidence for the next human review, not a claim that the editor's
quality bar has been met. The earlier review passes demonstrably did not
establish that.

Final preview ranges are logs 4-9, notifications 10-15, and news feed 16-21.
Existing advanced chapters were not rewritten in this batch. All three revised
questions remain `needs_human_review`; eight new memory proposals remain
pending alongside the earlier six. No approval or publication command was run.
The explicit editorial request is implemented in versioned shared guidance,
independently of memory approval.

Verification uses `make ci`, including `make all`, 68 Python tests, four C++
practice checks, source validation, Markdown lint, and release/review PDF gates.
Both changed skills also pass their validator. The new deterministic tests
protect delivery of system-design guidance to drafting, revision, and review,
plus scaffold ordering; they do not score prose by pronoun counts or phrases.
Visual inspection of every rewritten page is complete; no clipping, overlapping
text, unreadable diagrams, or nearly empty pre-diagram portrait pages remain.
