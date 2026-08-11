"""Generate stable, metadata-driven question catalogs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Optional, Sequence

from tools.content import (
    GUIDE_SPECS,
    ROOT,
    QuestionRecord,
    discover_questions,
    guide_spec,
    question_anchor,
    questions_by_type,
)


OUTPUT_ROOT = ROOT / "generated" / "catalogs"


def _display_slug(value: str) -> str:
    return value.replace("-", " ").title()


def category_counts(records: Sequence[QuestionRecord]) -> Counter[str]:
    """Count every assigned category, not only the primary category."""

    return Counter(
        str(category)
        for record in records
        for category in record.metadata.get("categories", [])
    )


def difficulty_counts(records: Sequence[QuestionRecord]) -> Counter[int]:
    return Counter(int(record.metadata["difficulty"]) for record in records)


def render_catalog_markdown(
    question_type: str,
    records: Sequence[QuestionRecord],
    *,
    link_prefix: str,
    heading_level: int = 1,
) -> str:
    """Render counts and a categorized question index.

    ``link_prefix`` should identify the generated guide. Stable question IDs are
    appended as anchors, so title or ordering changes do not break links.
    """

    spec = guide_spec(question_type)
    heading = "#" * heading_level
    subheading = "#" * (heading_level + 1)
    item_heading = "#" * (heading_level + 2)
    categories = category_counts(records)
    difficulties = difficulty_counts(records)

    lines = [
        f"{heading} {spec['title']} Catalog",
        "",
        "> Generated from question metadata. Do not edit manually.",
        "",
        f"**Questions:** {len(records)}",
        "",
        f"{subheading} Category counts",
        "",
        "| Category | Questions |",
        "| --- | ---: |",
    ]
    if categories:
        for category, count in sorted(categories.items()):
            lines.append(f"| {_display_slug(category)} | {count} |")
    else:
        lines.append("| No approved questions | 0 |")

    lines.extend(
        [
            "",
            f"{subheading} Difficulty counts",
            "",
            "| Difficulty | Questions |",
            "| ---: | ---: |",
        ]
    )
    for difficulty in range(1, 6):
        lines.append(f"| {difficulty} | {difficulties.get(difficulty, 0)} |")

    by_category: dict[str, list[QuestionRecord]] = defaultdict(list)
    for record in records:
        by_category[record.primary_category].append(record)

    lines.extend(["", f"{subheading} Questions", ""])
    if not records:
        lines.extend(
            [
                "No questions currently satisfy the selected publication status.",
                "",
            ]
        )
    else:
        for category, items in sorted(by_category.items()):
            lines.extend([f"{item_heading} {_display_slug(category)}", ""])
            for record in items:
                target = f"{link_prefix}#{question_anchor(record.question_id)}"
                duration = int(record.metadata["expected_duration_minutes"])
                difficulty = int(record.metadata["difficulty"])
                status = str(record.metadata["status"])
                lines.append(
                    f"- [{record.title}]({target}) - difficulty {difficulty}, "
                    f"{duration} minutes, `{status}`"
                )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate_catalogs(
    root: Path = ROOT,
    output_root: Optional[Path] = None,
) -> list[Path]:
    root = root.resolve()
    output_root = (
        output_root.resolve()
        if output_root is not None
        else root / "generated" / "catalogs"
    )
    output_root.mkdir(parents=True, exist_ok=True)

    grouped = questions_by_type(discover_questions(root), root)
    outputs: list[Path] = []
    for question_type, spec in GUIDE_SPECS.items():
        output = output_root / spec["catalog"]
        guide_target = f"../markdown/{spec['markdown']}"
        output.write_text(
            render_catalog_markdown(
                question_type,
                grouped[question_type],
                link_prefix=guide_target,
            ),
            encoding="utf-8",
        )
        outputs.append(output)
    return outputs


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(list(argv) if argv is not None else None)

    for output in generate_catalogs(args.root):
        print(f"built {output.relative_to(args.root.resolve())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
