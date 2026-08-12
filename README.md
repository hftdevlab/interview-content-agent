# C++ Quant Developer Interview Content Factory

This repository is the source of truth for a human-curated, AI-assisted
interview content system. It stores structured Markdown, JSON-compatible YAML,
Mermaid diagrams, and runnable C++20 exercises. Generated artifacts are kept
under `generated/` and `dist/` and must not be edited by hand.

The current implementation covers the deterministic workflow through release
packaging:

- repository and developer-command scaffolding;
- schemas, taxonomy, and deterministic metadata validation;
- one review-ready example for each question type;
- metadata-driven catalogs with stable document anchors;
- review-only Markdown previews and approved-only PDF guides;
- runnable multi-source stream-merger and sequence-snapshot exercises;
- starter-answer leakage checks, optional sanitizer builds, and Docker support;
- validation of content, links, publication rules, diagrams, and practice wiring.
- root and directory-specific Codex instructions;
- text and image ingestion with source preservation and visible transcription
  uncertainty;
- section-scoped expert-note refinement with reviewable diffs;
- idempotent C++ practice scaffolding and CMake registration;
- pull-request CI, Markdown integrity checks, and review-PDF artifacts;
- deterministic versioned releases with manifests, change summaries, archives,
  and SHA-256 checksums.

The examples are gold-standard candidates, not published content. They remain
in `needs_human_review` until a human editor approves them.

## Prerequisites

- Python 3.9 or newer
- CMake 3.20 or newer
- A C++20 compiler (Clang or GCC)
- Make
- ReportLab and pypdf, installed through this project
- Poppler (`pdftoppm` and `pdfinfo`) for visual PDF inspection

Create an isolated Python environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Metadata files use JSON syntax, which is valid YAML, so the deterministic
validator can read them with the Python standard library.

## Quick start

```bash
make help
make validate
make diagrams
make catalogs
make pdf-preview
make practice-test
make ci
make all
```

`make pdf-preview` produces internal review artifacts under
`generated/pdf-preview/`. `make pdfs` produces the three distributable files
under `dist/`, but includes only questions whose status is `approved` or
`published` and whose review gate is complete. The current examples remain
`needs_human_review`, so the distributable guides intentionally contain covers,
contents, and zero-count catalogs without the draft answers.

The practice project can also be built directly:

```bash
cmake -S practice -B build/practice
cmake --build build/practice
ctest --test-dir build/practice --output-on-failure
```

CTest runs both the solution suites and negative starter gates. The latter use
CTest's `WILL_FAIL` property: an unchanged starter is expected to fail the
behavioral suite, while accidentally copying the solution into a starter makes
the gate fail.

Optional sanitizer run:

```bash
make practice-sanitize
```

This default gate uses UBSan. AddressSanitizer and ThreadSanitizer remain
available as separate CMake options (`PRACTICE_ENABLE_ASAN` and
`PRACTICE_ENABLE_TSAN`) because runtime support varies by compiler and host.

Reproducible container run:

```bash
make docker-test
```

## Content workflow

### Human-in-the-loop agent workflow

`contentctl` provides the CLI-first orchestration layer. Run it from a clean
`main` worktree; a normal submission creates `question/<id>`, preserves the raw
input, records early duplicate candidates, invokes the relevant repository
skills, builds coding practice when required, and requests an independent
read-only agent review.

```bash
contentctl submit \
  --type coding \
  --input inbox/question.txt \
  --expert-note "The interviewer cared about ownership and shutdown."

contentctl status --id code-example
contentctl next --id code-example
```

`status` includes a `next_action` field; `next` prints only that recommendation.

Question-type aliases include `design` for system design and `general` or
`general-system` for systems fundamentals. Image submissions can include
`--transcription`; otherwise Codex attempts a faithful image transcription and
pauses when unreadable text changes the core contract.

When duplicate screening or the drafting agent needs human input:

```bash
contentctl resolve-duplicate \
  --id code-example \
  --decision distinct \
  --reason "Same container, but this question tests iterator invalidation."

contentctl clarify \
  --id code-example \
  --response "The API owns its input records and close() is idempotent." \
  --continue
```

Record feedback from a file or directly in the command. Either form preserves
the exact human wording, then resumes the drafting and independent-review loop:

```bash
contentctl feedback \
  --id code-example \
  --file inbox/feedback.md \
  --continue

contentctl feedback \
  --id code-example \
  --text "Derive shutdown behavior from the ownership contract." \
  --continue
```

Feedback starts a fresh, focused drafting context while retaining the previous
thread ID in the workflow audit log. The controller runs the complete C++ and
PDF gates once after the revision, then requires a new independent review.
Structured agent summaries are streamed as progress while longer revisions run.
When feedback contains a broadly useful quality rule, the revision agent may
propose up to three reusable editorial-memory candidates. They remain local and
inactive until a human explicitly approves them.

Once the independent review passes, build the preview bundle and open a draft
pull request for human review. This command validates the repository, builds the
PDF previews and any required C++ practice, and refuses to stage unrelated
worktree changes:

```bash
contentctl open-pr --id code-example
```

Approval is deliberately interactive and cannot run from a non-interactive
agent process:

```bash
contentctl approve --id code-example
```

The command requires the human to type `APPROVE <id>` exactly. Review any
proposed reusable lessons separately:

```bash
contentctl memory-list --id code-example
contentctl memory-approve --id memory-0123456789ab
contentctl memory-reject \
  --id memory-abcdef012345 \
  --reason "This is specific to the current contract."
```

Memory approval is available after the source question is approved and requires
typing `REMEMBER <memory-id>` exactly. Approved lessons retain their source
feedback and apply only to future drafts and reviews of matching question
types. Rejected lessons remain auditable but inactive.

Run `contentctl open-pr --id <id>` again after feedback or approval. It updates
the existing PR instead of creating a duplicate and marks an approved draft PR
ready for merge. Publishing remains a separate approved-only operation through
`make release` and the `$publish-guides` skill.

If a submission command is interrupted after its package is created, resume it
with `contentctl continue --id <id>`. Re-running `submit` for that stable ID is
rejected with a direct resume instruction.

Use `--offline --no-branch` on `contentctl submit` only for deterministic intake
testing. Workflow, duplicate, and pending-memory audit records are stored beside
the question as JSON-compatible `workflow.yaml`, `deduplication.yaml`, and (when
needed) `memory-candidates.yaml`. Human-approved reusable lessons live in root
`editorial-memory.yaml`.

### Deterministic low-level commands

Archive and normalize a text prompt:

```bash
python -m tools.ingest \
  --type system-design \
  --input inbox/market-data.txt \
  --id sd-market-data
```

Image intake preserves the image. Supply a human transcription when available;
without one, the normalized package remains valid but visibly marks the prompt
as uncertain:

```bash
python -m tools.ingest \
  --type coding \
  --input inbox/question.png \
  --transcription inbox/question.txt
```

Apply expert feedback to exact level-two sections with a JSON mapping. The
command leaves unrelated sections byte-stable, resets human review gates, and
writes a unified diff under `generated/refinement-diffs/`:

```bash
python -m tools.refine \
  --id fund-sequence-lock \
  --revisions inbox/sequence-lock-revisions.json
```

Create or register a runnable C++ scaffold after the question contract is
settled:

```bash
python -m tools.create_practice_question --id code-example
```

The generated generic `solve()` scaffold is only a safe starting point. Replace
it with the reviewed question-specific API, solution, and behavioral tests
before publication.

## CI and releases

`.github/workflows/ci.yml` runs `make ci` for pushes to `main` and pull
requests. Configure the `validate-build-test` job as a required status check in
the GitHub branch rules after connecting this repository to GitHub.

Create a release whose version matches `pyproject.toml`:

```bash
make release VERSION=0.1.0
```

The command rebuilds from source and writes approved-only PDFs, a deterministic
practice archive, `manifest.json`, `CHANGE_SUMMARY.md`, and `SHA256SUMS` under
`dist/releases/v<version>/`. It never changes approval or review metadata.

## Repository layout

```text
content/      Reviewable question packages and original source notes
.agents/      Focused repository Codex skills
.github/      Pull-request validation workflow
schemas/      JSON Schemas for common and type-specific metadata
taxonomy/     Controlled categories, tags, difficulty, and ordering
practice/     C++20 starter and reference implementations
tools/        Deterministic validation and build commands
templates/    Placeholders for later ingestion and drafting workflows
generated/    Rebuildable catalogs, diagrams, Markdown, and review PDFs
dist/         Approved-only PDF artifacts
tests/        Tooling tests and deliberately valid/invalid fixtures
```

See `PROJECT_PLAN.md` for the full product roadmap.
