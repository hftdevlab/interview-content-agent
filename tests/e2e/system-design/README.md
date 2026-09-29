# Foundational system-design readability trials

These three deliberately incomplete prompts exercise real `contentctl` intake,
drafting, deterministic validation, independent review, and the human-review
handoff. They are live model evaluations, not deterministic unit tests. Do not
run them in ordinary CI or judge prose by exact wording.

The raw inputs preserve the editor's prompts. The trial brief asks for standard
foundational interview questions, with more advanced branches kept optional.
For this trial, news-feed formats mean text, images, and video; logging means
application-log collection and search. These are declared interpretations, not
additional requirements attributed to the original prompt. RSS/Atom aggregation
is a different reasonable interpretation of news feeds.

## Run a trial

Use an isolated worktree and the normal authenticated Codex configuration. From
the worktree root, run the following for each input, substituting its ID/title.
Set `PYTHON` to the interpreter containing the repository dependencies so the
controller's Make targets use the same environment. `--no-branch` keeps this
three-question evaluation on its existing isolated branch.

```bash
export PYTHON=/absolute/path/to/project/.venv/bin/python
"$PYTHON" -m tools.workflow submit --type design \
  --input tests/e2e/system-design/news-feed.md \
  --id sd-e2e-news-feed --title "Design a News Feed" --no-branch \
  --expert-note "This is a foundational system-design readability trial, not an advanced flagship question. Assume a social following feed with text, images, and video, and label this interpretation explicitly. Enrich missing requirements with clearly labeled illustrative assumptions. Keep the passing interview answer small; advanced extensions are optional."
"$PYTHON" -m tools.workflow status --id sd-e2e-news-feed

"$PYTHON" -m tools.workflow submit --type design \
  --input tests/e2e/system-design/notifications.md \
  --id sd-e2e-notifications --title "Design a Notification System" --no-branch \
  --expert-note "This is a foundational system-design readability trial, not an advanced flagship question. Assume in-app, email, and mobile push notifications, and label this interpretation explicitly. Enrich missing requirements with clearly labeled illustrative assumptions. Keep the passing interview answer small; advanced extensions are optional."

"$PYTHON" -m tools.workflow submit --type design \
  --input tests/e2e/system-design/log-publishing-query.md \
  --id sd-e2e-log-publishing-query \
  --title "Design a Log Publishing and Query System" --no-branch \
  --expert-note "This is a foundational system-design readability trial, not an advanced flagship question. Assume application logs collected for operational search, and label this interpretation explicitly. Enrich missing requirements with clearly labeled illustrative assumptions. Keep the passing interview answer small; advanced extensions are optional."
```

| Input | Stable ID | Title | Declared interpretation |
|---|---|---|---|
| `news-feed.md` | `sd-e2e-news-feed` | Design a News Feed | Social following feed; text, images, video |
| `notifications.md` | `sd-e2e-notifications` | Design a Notification System | In-app, email, and mobile push |
| `log-publishing-query.md` | `sd-e2e-log-publishing-query` | Design a Log Publishing and Query System | Application logs collected for operational search |

Run sequentially in a shared worktree: PDF previews are shared build outputs.
An existing ID must use `continue`, not `submit`; archive the original source and
review records. For a clean first-draft comparison, use a fresh worktree before
these examples were added, or new IDs and the normal duplicate-review process.
Never delete an existing workflow to make a trial look successful.

## Readability and correctness review

For each chapter, record concrete evidence for these checks:

- Can a reader restate the product and trace one user action through the small
  baseline without learning every later extension first?
- Does the explanation move from prioritized functional/non-functional
  requirements through entities and useful interfaces into a complete
  architecture, before selected deep dives develop the harder choices?
- Does each component have an explained purpose in the request flow, and is an
  initially sufficient simple design allowed to remain valid at small scale?
- Are unfamiliar terms explained at first use, with useful prerequisite links
  instead of long foundational detours?
- Is the core interview path coherent on its own, with advanced decisions
  optional and no more than three improvements and three follow-ups?
- Are the question's distinctive decisions actually taught: mixed media and
  feed assembly; delivery channels and retry ambiguity; ingestion, search
  visibility, and retention?
- Do the design-pattern tags describe challenges actually developed in the
  chapter, with useful links to foundations rather than another generic lesson?
- Do worked numbers lead to a decision, and do failure examples agree with the
  stated guarantees? Inspect diagrams and every new chapter's rendered pages.

`make ci` checks source integrity and PDF budgets, not teaching quality. Record
first-draft shortcomings, any generalized rule changes, revision counts, and
remaining human judgments in `RESULTS.md`. Do not label agent judgments as human
approval or claim that three samples establish statistical reliability.

## Apply the expert-style feedback

The subsequent [reference review](REFERENCE_REVIEW.md) explains why the first
calibration still read too much like a specification. The editor's new request
is preserved in [tutorial-feedback.md](tutorial-feedback.md). Replay it against
each existing trial, one at a time, with the current skills and tooling:

```bash
"$PYTHON" -m tools.workflow feedback --id sd-e2e-notifications \
  --file tests/e2e/system-design/tutorial-feedback.md --continue
```

Use the other two stable IDs for news feeds and logs. This adds a new feedback
record and obtains a fresh review; it does not approve the chapter. An
interrupted run resumes with `contentctl continue`, not another feedback
submission. Any proposed editorial memories remain pending human approval.
