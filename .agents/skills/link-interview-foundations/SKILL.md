---
name: link-interview-foundations
description: "Add concise prerequisite references from an interview question to the companion HFT engineer handbook or authoritative external sources. Use when a draft mentions C++ concurrency, memory, networking, market-data, low-latency, replay, or trading-system foundations that should be linked instead of retaught."
---

# Link Interview Foundations

Use references to protect the question's page budget and keep its prose focused
on interview decisions.

## Inputs

- The selected question and the concepts it assumes.
- The handbook catalog at `release1/handbook-markdown/INDEX.md`.
- [Handbook topic map](references/foundations-map.md).

Read the map only for relevant concepts. Consult the handbook chapter when its
exact scope or terminology matters.

## Source selection

1. Prefer the companion handbook when it covers the prerequisite.
2. Prefer an existing related question when the reader needs interview practice
   rather than foundational teaching.
3. Use a primary specification, standard, official project documentation, or
   authoritative publisher when the handbook lacks the topic or an exact claim
   needs support.
4. Use Wikipedia only as a concise orientation link for a stable general term,
   not as authority for protocol, language, kernel, or performance guarantees.

Add the link at the first useful mention or in a compact related-foundations
sentence. Explain why the reference matters in this question. Do not append a
generic bibliography or duplicate a handbook tutorial.

## Outputs and edit boundary

Edit only the selected package's `question.md` and, when existing repository
IDs justify it, `metadata.yaml` prerequisites or related questions. Preserve
source files, expert notes, review decisions, and publication status. Do not
edit the handbook, the topic map, or generated guides while applying links.

## Validation

Verify every local path and external destination, then run:

```bash
python -m tools.validate --id <id>
make pdf-preview
```

Inspect the rendered link text and pagination. Leave the package in
human-review-required status.
