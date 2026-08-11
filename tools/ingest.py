"""Create a normalized question package while preserving the raw input."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from tools.content import ROOT, load_data
from tools.validate import validate_repository


TYPE_CONFIG: Mapping[str, Mapping[str, object]] = {
    "system-design": {
        "metadata_type": "system_design",
        "directory": "system-design",
        "prefix": "sd",
        "categories": ["distributed-systems"],
        "tags": ["backpressure", "capacity-planning"],
        "duration": 45,
    },
    "coding": {
        "metadata_type": "coding",
        "directory": "coding",
        "prefix": "code",
        "categories": ["algorithms"],
        "tags": ["ordering", "move-semantics"],
        "duration": 45,
    },
    "fundamentals": {
        "metadata_type": "fundamentals",
        "directory": "fundamentals",
        "prefix": "fund",
        "categories": ["cpp-language"],
        "tags": ["atomics", "memory-ordering"],
        "duration": 30,
    },
}

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"})


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized or "question"


def _safe_source_name(path: Path) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", path.name).strip("-.")
    return name or f"original{path.suffix.casefold()}"


def _title_from(text: str, source: Path, explicit: Optional[str]) -> str:
    if explicit:
        title = explicit.strip()
    else:
        first = next((line.strip("# ") for line in text.splitlines() if line.strip()), "")
        title = first or source.stem.replace("-", " ").replace("_", " ").strip()
    if len(title) < 8:
        title = f"Interview question: {title or source.stem}"
    return title[:160].rstrip()


def _normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def _markdown(question_type: str, title: str, prompt: str, question_id: str) -> str:
    if question_type == "system_design":
        return f"""# {title}

## Interview prompt

{prompt}

## What the interviewer is testing

- Content drafting should identify the core system boundary and engineering invariants.

## Clarifying questions

- Which requirements, scale assumptions, and failure contracts should control the design?

## Requirements and assumptions

The source has been normalized; requirements remain subject to expert review.

## Good solution

![Normalized system context awaiting detailed drafting.](../../../generated/diagrams/{question_id}/context.svg)

The package is ready for an invariant-led design draft.

## Great solution improvements

- Add only improvements justified by the agreed interview requirements.

## Failure scenarios

- Identify failures after the good solution establishes ownership and state.

## Common pitfalls

- Do not invent scale, latency, or reliability requirements absent from the source.

## Follow-up questions

### Which component should the interview examine in depth?

Choose after clarifying the system boundary and the interviewer's priorities.

## Evaluation rubric

Evaluation criteria will be calibrated during content drafting and human review.
"""
    if question_type == "coding":
        return f"""# {title}

## Interview prompt

{prompt}

## API contract

The precise API, ownership rules, and boundary behavior remain to be derived from the source.

## Clarifying questions

- Which constraints and error semantics are material to the intended interview?

## Primary approach

The invariant and data structure will be established during content drafting.

## Reference solution

The candidate-owned implementation will be added after the contract is confirmed.

## Complexity analysis

Complexity depends on the confirmed contract and primary approach.

## Common mistakes

- Do not infer missing constraints or repeat code already supplied by the prompt.

## Optional improvements

- Add only an improvement that changes a material requirement or trade-off.

## Follow-up questions

### Which constraint should the interviewer tighten?

Select a realistic extension after the primary solution is complete.

## Practice repository

A runnable package is created after the API and reference behavior are reviewed.
"""
    return f"""# {title}

## Question

{prompt}

## Concise interview answer

The concise answer will be grounded in the controlling language, OS, network, or hardware rule.

## Deep explanation

The package is ready for a learning-first technical draft.

## Pass-level answer framework

- State the governing rule before discussing an implementation technique.

## Great answer improvements

- Add one improvement only when it sharpens correctness or engineering judgment.

## Example

The worked example will be selected after the source assumptions are confirmed.

## Common misconception

Do not turn an implementation convention into a portable guarantee.

## Interview trap

Call out the most realistic ambiguity after technical review.

## Follow-up questions

### Which assumption changes the answer?

Use a platform or correctness boundary that follows naturally from the question.

## Related concepts

Link prerequisites rather than reproducing a general tutorial.

## Runnable experiment

Add an experiment only when it can test a material claim.
"""


def _context_diagram() -> str:
    return """flowchart LR
    SO[\"Normalized source\"] --> BO[\"System boundary\"]
    BO[\"System boundary\"] --> DE[\"Interview deep dive\"]
"""


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def ingest_question(
    *,
    root: Path,
    question_kind: str,
    input_path: Path,
    transcription_path: Optional[Path] = None,
    question_id: Optional[str] = None,
    title: Optional[str] = None,
    categories: Optional[Sequence[str]] = None,
    tags: Optional[Sequence[str]] = None,
    difficulty: int = 3,
    duration: Optional[int] = None,
    confidentiality: str = "public",
    company_removed: bool = False,
    expert_note: Optional[str] = None,
) -> Path:
    root = root.resolve()
    input_path = input_path.resolve()
    if question_kind not in TYPE_CONFIG:
        raise ValueError(f"unknown question type: {question_kind}")
    if not input_path.is_file():
        raise ValueError(f"input file does not exist: {input_path}")

    config = TYPE_CONFIG[question_kind]
    is_image = input_path.suffix.casefold() in IMAGE_SUFFIXES
    original_paths = [input_path]
    uncertainty: list[str] = []
    if is_image:
        if transcription_path is not None:
            transcription_path = transcription_path.resolve()
            if not transcription_path.is_file():
                raise ValueError(f"transcription file does not exist: {transcription_path}")
            raw_prompt = transcription_path.read_text(encoding="utf-8")
            original_paths.append(transcription_path)
        else:
            raw_prompt = "[uncertain: no transcription supplied; human transcription required]"
            uncertainty.append("The image has not been transcribed.")
    else:
        raw_prompt = input_path.read_text(encoding="utf-8")

    prompt = _normalize_text(raw_prompt)
    resolved_title = _title_from(prompt, input_path, title)
    prefix = str(config["prefix"])
    resolved_id = question_id or f"{prefix}-{_slug(resolved_title)}"
    if not resolved_id.startswith(f"{prefix}-") or re.fullmatch(
        r"(?:sd|code|fund)-[a-z0-9]+(?:-[a-z0-9]+)*", resolved_id
    ) is None:
        raise ValueError(f"invalid ID for {question_kind}: {resolved_id}")

    package_dir = root / "content" / str(config["directory"]) / resolved_id
    if package_dir.exists():
        raise ValueError(f"question package already exists: {package_dir}")
    source_dir = package_dir / "source"
    source_dir.mkdir(parents=True)

    copied_sources: list[str] = []
    used_names: set[str] = set()
    for source in original_paths:
        name = _safe_source_name(source)
        if name in used_names:
            name = f"transcription-{name}"
        used_names.add(name)
        shutil.copy2(source, source_dir / name)
        copied_sources.append(f"source/{name}")

    metadata_type = str(config["metadata_type"])
    review_flags = {
        "agent_reviewed": False,
        "human_reviewed": False,
        "technical_accuracy_reviewed": False,
        "interview_realism_reviewed": False,
    }
    metadata: dict[str, object] = {
        "schema_version": 1,
        "id": resolved_id,
        "type": metadata_type,
        "title": resolved_title,
        "status": "normalized",
        "difficulty": difficulty,
        "expected_duration_minutes": duration or int(config["duration"]),
        "categories": list(categories or config["categories"]),
        "tags": list(tags or config["tags"]),
        "prerequisites": [],
        "related_questions": [],
        "source": {
            "input_type": "image" if is_image else "text",
            "confidentiality": confidentiality,
            "original_company_removed": company_removed,
            "original_files": copied_sources,
        },
        "review": review_flags,
        "last_updated": dt.date.today().isoformat(),
        "content_file": "question.md",
    }
    if metadata_type == "system_design":
        metadata["diagrams"] = [
            {
                "source_file": "diagrams/context.mmd",
                "rendered_file": "context.svg",
                "caption": "Normalized system context awaiting detailed drafting.",
                "alt_text": "The normalized source establishes a system boundary from which the interviewer selects a focused design deep dive.",
            }
        ]
        diagram_dir = package_dir / "diagrams"
        diagram_dir.mkdir()
        (diagram_dir / "context.mmd").write_text(_context_diagram(), encoding="utf-8")
    elif metadata_type == "coding":
        metadata["practice"] = None
    else:
        metadata["runnable_experiment"] = None

    _write_json(package_dir / "metadata.yaml", metadata)
    (package_dir / "question.md").write_text(
        _markdown(metadata_type, resolved_title, prompt, resolved_id),
        encoding="utf-8",
    )
    note_lines = ["# Expert notes", ""]
    note_lines.append(expert_note.strip() if expert_note else "No expert notes were supplied during ingestion.")
    if uncertainty:
        note_lines.extend(["", "## Transcription uncertainty", ""])
        note_lines.extend(f"- {item}" for item in uncertainty)
    (package_dir / "expert-notes.md").write_text(
        "\n".join(note_lines) + "\n", encoding="utf-8"
    )
    _write_json(
        package_dir / "review.yaml",
        {
            "question_id": resolved_id,
            "checks": review_flags,
            "review_notes": [
                "Source archived and prompt normalized; content drafting and human review remain required."
            ]
            + uncertainty,
        },
    )

    issues = validate_repository(root)
    if issues:
        shutil.rmtree(package_dir)
        rendered = "\n".join(f"- {issue}" for issue in issues)
        raise ValueError(f"ingested package failed validation and was rolled back:\n{rendered}")
    return package_dir


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--type", required=True, choices=sorted(TYPE_CONFIG))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--transcription", type=Path)
    parser.add_argument("--id")
    parser.add_argument("--title")
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--tag", action="append", dest="tags")
    parser.add_argument("--difficulty", type=int, default=3)
    parser.add_argument("--duration", type=int)
    parser.add_argument(
        "--confidentiality",
        choices=("public", "sanitized_real_interview", "private_reference"),
        default="public",
    )
    parser.add_argument("--company-removed", action="store_true")
    parser.add_argument("--expert-note")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        package = ingest_question(
            root=args.root,
            question_kind=args.type,
            input_path=args.input,
            transcription_path=args.transcription,
            question_id=args.id,
            title=args.title,
            categories=args.categories,
            tags=args.tags,
            difficulty=args.difficulty,
            duration=args.duration,
            confidentiality=args.confidentiality,
            company_removed=args.company_removed,
            expert_note=args.expert_note,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"created normalized question package: {package.relative_to(args.root.resolve())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
