"""Build review-only combined Markdown guides from question packages."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

from tools.content import (
    GUIDE_SPECS,
    ROOT,
    QuestionRecord,
    discover_questions,
    question_anchor,
    questions_by_type,
)
from tools.generate_catalog import render_catalog_markdown

OUTPUT_ROOT = ROOT / "generated" / "markdown"

def _without_leading_title(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def build_guide(
    question_type: str,
    records: list[QuestionRecord],
    output_path: Path,
) -> Path:
    spec = GUIDE_SPECS[question_type]

    lines = [
        f"# {spec['title']} Review Preview",
        "",
        (
            "> Generated review preview. It may contain unapproved material and "
            "must not be distributed as a published guide."
        ),
        "",
        render_catalog_markdown(
            question_type,
            records,
            link_prefix="",
            heading_level=2,
        ).rstrip(),
        "",
    ]
    for record in records:
        lines.extend(
            [
                f'<a id="{question_anchor(record.question_id)}"></a>',
                "",
                f"# {record.title}",
                "",
                (
                    f"> `{record.question_id}` | status: "
                    f"`{record.metadata['status']}` | difficulty: "
                    f"{record.metadata['difficulty']} | expected time: "
                    f"{record.metadata['expected_duration_minutes']} minutes"
                ),
                "",
                _without_leading_title(record.markdown),
                "",
            ]
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output_path


def build_guides(root: Path = ROOT) -> list[Path]:
    root = root.resolve()
    grouped = questions_by_type(discover_questions(root), root)
    outputs = []
    for question_type, spec in GUIDE_SPECS.items():
        output = build_guide(
            question_type,
            grouped[question_type],
            root / "generated" / "markdown" / spec["markdown"],
        )
        outputs.append(output)
    return outputs


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(list(argv) if argv is not None else None)

    for output in build_guides(args.root):
        print(f"built {output.relative_to(args.root.resolve())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
