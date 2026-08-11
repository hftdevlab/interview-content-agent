"""Apply section-scoped expert-note refinements and emit a reviewable diff."""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
from pathlib import Path
from typing import Iterable, Mapping, Optional

from tools.content import ROOT, load_data
from tools.validate import validate_repository


def _section_bounds(lines: list[str], heading: str) -> tuple[int, int]:
    normalized = heading if heading.startswith("## ") else f"## {heading}"
    matches = [index for index, line in enumerate(lines) if line == normalized]
    if len(matches) != 1:
        raise ValueError(
            f"section {normalized!r} must occur exactly once; found {len(matches)}"
        )
    start = matches[0]
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    return start, end


def apply_section_revisions(markdown: str, revisions: Mapping[str, str]) -> str:
    lines = markdown.splitlines()
    resolved: list[tuple[int, int, str, str]] = []
    for heading, body in revisions.items():
        if not isinstance(heading, str) or not isinstance(body, str) or not body.strip():
            raise ValueError("revision headings and bodies must be non-empty strings")
        if any(line.startswith("## ") for line in body.splitlines()):
            raise ValueError(
                f"revision for {heading!r} contains another level-two heading"
            )
        start, end = _section_bounds(lines, heading)
        normalized = heading if heading.startswith("## ") else f"## {heading}"
        resolved.append((start, end, normalized, body.strip()))

    for start, end, heading, body in sorted(resolved, reverse=True):
        replacement = [heading, "", *body.splitlines(), ""]
        lines[start:end] = replacement
    return "\n".join(lines).rstrip() + "\n"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def refine_question(
    *,
    root: Path,
    question_id: str,
    revisions_path: Path,
    diff_output: Optional[Path] = None,
    dry_run: bool = False,
) -> str:
    root = root.resolve()
    matches = list((root / "content").glob(f"*/{question_id}/metadata.yaml"))
    if len(matches) != 1:
        raise ValueError(f"question ID {question_id!r} does not identify one package")
    package_dir = matches[0].parent
    notes_path = package_dir / "expert-notes.md"
    notes = notes_path.read_text(encoding="utf-8").strip()
    if not notes or "No expert notes" in notes or "No human expert notes" in notes:
        raise ValueError("expert-notes.md does not contain actionable human guidance")

    revisions = load_data(revisions_path.resolve())
    if not isinstance(revisions, dict) or not revisions:
        raise ValueError("revisions file must be a non-empty JSON object")

    question_path = package_dir / "question.md"
    metadata_path = package_dir / "metadata.yaml"
    review_path = package_dir / "review.yaml"
    old_question = question_path.read_text(encoding="utf-8")
    new_question = apply_section_revisions(old_question, revisions)
    if new_question == old_question:
        raise ValueError("revisions did not change question.md")

    diff = "".join(
        difflib.unified_diff(
            old_question.splitlines(keepends=True),
            new_question.splitlines(keepends=True),
            fromfile=str(question_path.relative_to(root)),
            tofile=str(question_path.relative_to(root)),
        )
    )
    if dry_run:
        return diff

    metadata = dict(load_data(metadata_path))
    review = dict(load_data(review_path))
    review_flags = {
        "agent_reviewed": True,
        "human_reviewed": False,
        "technical_accuracy_reviewed": False,
        "interview_realism_reviewed": False,
    }
    metadata["status"] = "needs_human_review"
    metadata["review"] = review_flags
    metadata["last_updated"] = dt.date.today().isoformat()
    review["checks"] = review_flags
    notes_list = list(review.get("review_notes", []))
    notes_list.append(
        "Expert-note refinement applied to sections: "
        + ", ".join(sorted(str(key) for key in revisions))
        + ". Human review is required."
    )
    review["review_notes"] = notes_list

    originals = {
        question_path: old_question,
        metadata_path: metadata_path.read_text(encoding="utf-8"),
        review_path: review_path.read_text(encoding="utf-8"),
    }
    question_path.write_text(new_question, encoding="utf-8")
    _write_json(metadata_path, metadata)
    _write_json(review_path, review)
    issues = validate_repository(root)
    if issues:
        for path, content in originals.items():
            path.write_text(content, encoding="utf-8")
        rendered = "\n".join(f"- {issue}" for issue in issues)
        raise ValueError(f"refinement failed validation and was rolled back:\n{rendered}")

    destination = diff_output or (
        root / "generated" / "refinement-diffs" / f"{question_id}.diff"
    )
    destination = destination.resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise ValueError("diff output must remain inside the repository") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(diff, encoding="utf-8")
    return diff


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--id", required=True, dest="question_id")
    parser.add_argument("--revisions", required=True, type=Path)
    parser.add_argument("--diff-output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        diff = refine_question(
            root=args.root,
            question_id=args.question_id,
            revisions_path=args.revisions,
            diff_output=args.diff_output,
            dry_run=args.dry_run,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(diff, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
