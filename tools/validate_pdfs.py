"""Validate generated PDF structure, metadata, content gates, and page counts."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from tools.content import (
    GUIDE_SPECS,
    ROOT,
    discover_questions,
    is_publication_ready,
    load_project_version,
    questions_by_type,
)

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover - exercised by CLI setup failures
    raise SystemExit(
        "PDF validation requires pypdf. Run `python -m pip install -e .` "
        "inside the project virtual environment."
    ) from exc


@dataclass(frozen=True)
class PdfIssue:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _outline_destinations(items):
    for item in items:
        if isinstance(item, list):
            yield from _outline_destinations(item)
        else:
            yield item


def _page_budget(record) -> Optional[int]:
    if record.question_type == "coding":
        return 6
    if record.question_type == "system_design":
        is_extra_complex = (
            int(record.metadata["difficulty"]) >= 4
            and int(record.metadata["expected_duration_minutes"]) >= 60
        )
        return 14 if is_extra_complex else 10
    return None


def _page_budget_issues(reader, records, path: Path) -> list[PdfIssue]:
    destinations = list(_outline_destinations(reader.outline))
    by_title = {getattr(item, "title", ""): item for item in destinations}
    starts = []
    for record in records:
        destination = by_title.get(record.title)
        if destination is None:
            continue
        starts.append(
            (reader.get_destination_page_number(destination), record)
        )
    starts.sort(key=lambda item: item[0])

    issues: list[PdfIssue] = []
    for index, (start, record) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(reader.pages)
        page_count = end - start
        budget = _page_budget(record)
        if budget is not None and page_count > budget:
            issues.append(
                PdfIssue(
                    path,
                    f"{record.question_id} uses {page_count} pages; "
                    f"chapter budget is {budget}",
                )
            )
    return issues


def validate_pdf_outputs(
    root: Path = ROOT,
    *,
    review_preview: bool = False,
) -> list[PdfIssue]:
    root = root.resolve()
    selected_records = discover_questions(root)
    if not review_preview:
        selected_records = [
            record for record in selected_records if is_publication_ready(record)
        ]
    selected = questions_by_type(selected_records, root)
    all_records = questions_by_type(
        discover_questions(root, include_private=True),
        root,
    )
    output_root = (
        root / "generated" / "pdf-preview" if review_preview else root / "dist"
    )
    version = load_project_version(root)
    issues: list[PdfIssue] = []

    for question_type, spec in GUIDE_SPECS.items():
        path = output_root / spec["pdf"]
        if not path.is_file():
            issues.append(PdfIssue(path, "required PDF is missing"))
            continue
        if path.stat().st_size < 1_000:
            issues.append(PdfIssue(path, "PDF is unexpectedly small or empty"))
            continue

        try:
            reader = PdfReader(str(path))
        except Exception as exc:  # pypdf exposes several parser exception types
            issues.append(PdfIssue(path, f"cannot be parsed: {exc}"))
            continue

        if len(reader.pages) < 3:
            issues.append(PdfIssue(path, "must contain cover, contents, and catalog"))
            continue

        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        for required in (spec["title"], "Contents", "Question catalog"):
            if required not in text:
                issues.append(PdfIssue(path, f"missing required text {required!r}"))

        metadata = reader.metadata or {}
        if metadata.get("/Title") != spec["title"]:
            issues.append(PdfIssue(path, "PDF title metadata is missing or incorrect"))
        subject = str(metadata.get("/Subject", ""))
        keywords = str(metadata.get("/Keywords", ""))
        if version not in subject or "build date" not in subject:
            issues.append(
                PdfIssue(path, "subject metadata must contain version and build date")
            )
        if version not in keywords or "build date" not in keywords:
            issues.append(
                PdfIssue(path, "keyword metadata must contain version and build date")
            )

        selected_ids = {record.question_id for record in selected[question_type]}
        for record in selected[question_type]:
            if record.question_id not in text or record.title not in text:
                issues.append(
                    PdfIssue(
                        path,
                        f"selected question {record.question_id!r} is missing",
                    )
                )
        issues.extend(
            _page_budget_issues(reader, selected[question_type], path)
        )

        if not review_preview:
            for record in all_records[question_type]:
                if record.question_id not in selected_ids and record.question_id in text:
                    issues.append(
                        PdfIssue(
                            path,
                            f"unapproved or private question {record.question_id!r} leaked",
                        )
                    )

    return issues


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--review-preview", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    issues = validate_pdf_outputs(args.root, review_preview=args.review_preview)
    if issues:
        print(f"PDF validation failed with {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1

    output_kind = "review preview" if args.review_preview else "approved release"
    print(f"PDF validation passed: 3 {output_kind} guide(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
