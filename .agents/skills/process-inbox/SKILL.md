---
name: process-inbox
description: "Pick up interview questions the editor dropped into inbox/<type>/*.md, turn each into a question package on its own branch, draft it, review it independently, and prepare it for human review. Use when asked to process, check, or work through the inbox."
---

# Process the Inbox

The editor adds questions as Markdown files, one per file, under
`inbox/system-design/`, `inbox/coding/`, or `inbox/fundamentals/`. The folder
decides the type. A file is either the bare prompt, or the template in
`templates/system-design/inbox-question.md`: optional front matter (`title`,
`id`, `confidentiality`), a `## Prompt` section, and a `## Notes` section that
becomes `expert-notes.md`. Notes are the editor's direction; they outrank your
defaults.

## Workflow

1. Read `AGENTS.md`, `content/AGENTS.md`, and `inbox/README.md`.
2. Run `contentctl inbox --list`. If it is empty, say so and stop.
3. Start from a clean `main` worktree. Each question gets its own
   `question/<id>` branch, so take **one file per pass**.
4. Choose the path:
   - **From a terminal, with Codex installed:** `contentctl inbox --open-pr`
     runs intake, the drafting agent, deterministic gates, the independent
     review agent, and opens a draft PR. Use this when you are not the drafter.
   - **When you are the drafting agent in this session:** run
     `contentctl inbox --offline`. It archives the file, screens duplicates,
     writes the normalized package, creates the branch, and moves the inbox
     file to `inbox/processed/`. Then continue below.
5. If `workflow.yaml` shows `needs_clarification` (a likely duplicate or an
   unreadable prompt), stop and report the exact question to the editor. Do not
   guess.
6. Draft with the type's skill — `$draft-system-design` for system design —
   and `$link-interview-foundations`. Follow the editor's notes in
   `expert-notes.md`.
7. Review with `$review-question` as a separate pass that does not edit files
   (a fresh session or sub-agent where possible). Fix every agent-fixable
   finding, then review again.
8. Run the gates: `make validate readability diagrams track-map sd-preview`
   for system design (add `make practice-test` for coding). Read the rendered
   chapter in `generated/pdf-preview/`, not the Markdown.
9. Set status `needs_human_review` with only `agent_reviewed` true, then
   `contentctl open-pr --id <id>`.
10. Report the package ID, branch, PR, the reading of any ambiguous prompt,
    and what still needs human judgement.

## Never

Never approve or publish. Never edit another question package, the editor's
inbox file, or `expert-notes.md` beyond what intake wrote. Never process more
than one file on one branch unless the editor asks for `--all --no-branch`.
