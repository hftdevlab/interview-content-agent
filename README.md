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
