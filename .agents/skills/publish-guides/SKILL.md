---
name: publish-guides
description: "Build, validate, preview, and package the three interview guides and runnable practice archive. Use when producing review PDFs, checking publication gates, or creating a deterministic semantic-versioned release from human-approved content."
---

# Publish Interview Guides

Publishing is deterministic packaging, not an approval mechanism.

## Inputs

- Repository source, review metadata, and a semantic release version matching
  `pyproject.toml`.
- Explicit human approval already recorded for any content intended for the
  distributable guides.

## Workflow

For internal review, run:

```bash
make pdf-preview
```

Inspect the PDFs under `generated/pdf-preview/`. They may include
human-review-stage content and must not be distributed as approved guides.
When a viewer appears to crop a header or footer, verify the actual raster file
and positioned PDF text before changing the publisher. The PDF validation gate
checks running-furniture coordinates on every non-cover page.

For a release:

1. Confirm intended questions are `approved` or `published` and all four review
   flags are true. Never change these values as part of publishing.
2. Run `make ci`.
3. Run `make release VERSION=<version>`.
4. Verify `manifest.json`, `CHANGE_SUMMARY.md`, `SHA256SUMS`, the three
   approved-only PDFs, and the deterministic practice archive.
5. Report excluded questions and their review status.

The release command refuses to overwrite an existing version. Choose a new
version rather than deleting a prior release.

## Outputs and edit boundary

Build commands may write only to `generated/`, `dist/`, and `build/`. Change
`pyproject.toml` only when the human explicitly requests a version update.
Never edit generated files by hand, alter question prose, delete prior release
artifacts, or promote review state.

## Validation

The required gate is:

```bash
make ci
make release VERSION=<version>
```

Confirm the command exits successfully and the hashes listed in `SHA256SUMS`
match the packaged files.
