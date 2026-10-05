---
# Everything in this block is optional. Delete it if you do not need it.
title: Design a Distributed Task Scheduler
id: sd-task-scheduler
confidentiality: public        # public | sanitized_real_interview | private_reference
---

## Prompt

Design a distributed task scheduler: it should be able to schedule tasks
asynchronously. Support priority based scheduling. Clients can query the status
of scheduled tasks.

## Notes

Optional direction for the author. It is saved to expert-notes.md and never
shown as part of the prompt. For example:

- Read this as an internal batch scheduler at a trading firm, not cron for a web fleet.
- Go lower-level than usual on how workers claim tasks.
- Do not repeat the notification system's lessons; reuse them in a sentence each.
