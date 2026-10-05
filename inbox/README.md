# Inbox

Drop one interview question per Markdown file into the folder for its type:

```text
inbox/system-design/<anything>.md
inbox/coding/<anything>.md
inbox/fundamentals/<anything>.md
```

The simplest file is just the question, exactly as it was asked. To add a
title, a stable ID, or direction for the author, copy
`templates/system-design/inbox-question.md`: an optional front-matter block, a
`## Prompt` section, and a `## Notes` section that goes to `expert-notes.md`.

Then run one of:

```bash
contentctl inbox --list              # show what is waiting
contentctl inbox --open-pr           # next file: intake, Codex draft, independent review, draft PR
contentctl inbox --offline           # next file: intake and question branch only
contentctl inbox --all --no-branch   # every file on the current branch
```

Each question gets its own `question/<id>` branch, so the default processes one
file per run. Submitted files move to `inbox/processed/`, and the original file
is archived in the package's `source/`.

Everything in this folder except this README and the type folders is ignored
by Git: drafts stay local until a question package exists.
