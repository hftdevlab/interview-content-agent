# Repository instructions

## Purpose and authority

- This repository produces human-reviewed C++ quant-developer interview
  material and runnable practice exercises.
- Markdown, JSON-compatible YAML, Mermaid, C++, tests, schemas, and taxonomy are
  the source of truth. Never edit `generated/`, `dist/`, or `build/` by hand.
- Preserve original source inputs and `expert-notes.md`. Human expert notes
  override generated suggestions.
- Never invent interview provenance or employer attribution. Remove confidential
  and identifying details from published-facing content.
- Never mark AI-created or AI-revised content `approved` or `published`; final
  publication authority belongs to the human editor.
- Never invoke `contentctl approve`. It is an interactive, human-only lifecycle
  transition even when an agent has completed every technical review.
- During a `contentctl` run, never edit `workflow.yaml` or advance lifecycle
  status/review flags. The controller owns those transitions and requires a
  separate read-only agent review before human approval.

## Change discipline

- Use stable question IDs and controlled taxonomy values. Keep related-question
  references valid.
- Make deterministic workflow logic a script with tests rather than an agent
  convention alone.
- Keep starter code independent from reference solutions and prevent solution
  leakage into candidate files.
- Do not manually preserve generated diffs. Rebuild them from source after a
  source or renderer change.

## Required checks

- Run `make validate` after content, metadata, schema, taxonomy, template, or
  reference changes.
- Run `make practice-test` after C++ practice or CMake changes.
- Run `make pdf-preview` after content, diagram, or renderer changes and inspect
  the rendered pages when layout could change.
- Add or update deterministic tests when changing tools.
- Run `make all` before declaring a repository-wide task complete.

## Completion report

Summarize source files changed, validation performed, generated outputs rebuilt,
and any content still awaiting human review. A task is not complete while a
required check is failing or an unsafe publication-state change is pending.
