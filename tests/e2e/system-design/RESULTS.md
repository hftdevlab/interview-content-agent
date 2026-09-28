# Foundational system-design readability evaluation

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

## Final results

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
