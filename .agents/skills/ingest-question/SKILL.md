---
name: ingest-question
description: "Archive and normalize a raw text prompt, screenshot, or photograph into a structurally valid interview-question package. Use when adding a new system-design, coding, or C++ fundamentals question from inbox material while preserving the source and exposing uncertain transcription."
---

# Ingest Question

Create the package with the deterministic ingestion command. Do not draft a
finished answer during intake.

## Inputs

- Question type: `system-design`, `coding`, or `fundamentals`.
- One text or image input.
- For an image, an optional human transcription.
- Optional title, stable ID, taxonomy values, confidentiality, and expert note.

Inspect `taxonomy/` before overriding the command defaults. Treat missing image
text as unknown; never infer unreadable constraints.

## Workflow

1. Read `AGENTS.md` and `content/AGENTS.md`.
2. Run `python -m tools.ingest --type <type> --input <path>` with supplied
   options. Add `--transcription <path>` when one exists.
3. Confirm that every input was copied into the new package's `source/`
   directory and listed in `metadata.yaml`.
4. Review the normalized prompt for accidental company identifiers,
   confidentiality issues, and visible uncertainty markers.
5. Leave the package at `normalized`. Do not mark any human review flag true.

## Outputs and edit boundary

Create one new directory under `content/<type>/<id>/`. The workflow may create
its metadata, question draft, review file, expert-notes file, source archive,
and initial Mermaid context diagram. Never edit or delete the original input,
another question package, existing expert notes, `generated/`, or `dist/`.

## Validation

Run:

```bash
python -m tools.validate --id <id>
git diff -- content/<type>/<id>
```

Report unresolved transcription or confidentiality questions to the human
editor before drafting.
