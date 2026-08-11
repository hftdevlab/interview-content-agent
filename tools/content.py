"""Shared content discovery, filtering, and deterministic ordering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_STATUSES = frozenset({"approved", "published"})

GUIDE_SPECS = {
    "system_design": {
        "directory": "system-design",
        "title": "System Design Interview Guide",
        "markdown": "system-design-guide.md",
        "catalog": "system-design-catalog.md",
        "pdf": "system-design-guide.pdf",
    },
    "coding": {
        "directory": "coding",
        "title": "Coding Interview Guide",
        "markdown": "coding-interview-guide.md",
        "catalog": "coding-catalog.md",
        "pdf": "coding-interview-guide.pdf",
    },
    "fundamentals": {
        "directory": "fundamentals",
        "title": "C++ Systems and Low-Latency Guide",
        "markdown": "cpp-systems-guide.md",
        "catalog": "cpp-systems-catalog.md",
        "pdf": "cpp-systems-guide.pdf",
    },
}


@dataclass(frozen=True)
class QuestionRecord:
    """One question package plus its parsed source content."""

    metadata_path: Path
    package_dir: Path
    metadata: Mapping[str, Any]
    markdown: str

    @property
    def question_id(self) -> str:
        return str(self.metadata["id"])

    @property
    def question_type(self) -> str:
        return str(self.metadata["type"])

    @property
    def title(self) -> str:
        return str(self.metadata["title"])

    @property
    def primary_category(self) -> str:
        categories = self.metadata.get("categories", [])
        return str(categories[0]) if categories else "uncategorized"


def load_data(path: Path) -> Any:
    """Read the repository's JSON-compatible YAML."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_project_version(root: Path = ROOT) -> str:
    """Read the package version without requiring a TOML dependency."""

    for line in (root / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("version ="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise ValueError("pyproject.toml does not define a project version")


def guide_spec(question_type: str) -> Mapping[str, str]:
    try:
        return GUIDE_SPECS[question_type]
    except KeyError as exc:
        raise ValueError(f"unknown question type: {question_type!r}") from exc


def question_anchor(question_id: str) -> str:
    """Return the stable anchor used by Markdown and PDF outputs."""

    return question_id


def is_publication_ready(record: QuestionRecord) -> bool:
    """Require both an allowed status and every human-controlled review gate."""

    metadata = record.metadata
    if metadata.get("status") not in PUBLICATION_STATUSES:
        return False
    if metadata.get("source", {}).get("confidentiality") == "private_reference":
        return False
    review = metadata.get("review", {})
    required_flags = (
        "agent_reviewed",
        "human_reviewed",
        "technical_accuracy_reviewed",
        "interview_realism_reviewed",
    )
    return all(review.get(flag) is True for flag in required_flags)


def discover_questions(
    root: Path = ROOT,
    *,
    statuses: Optional[Iterable[str]] = None,
    include_private: bool = False,
) -> list[QuestionRecord]:
    """Discover question packages without relying on a maintained question list."""

    root = root.resolve()
    accepted_statuses = set(statuses) if statuses is not None else None
    records: list[QuestionRecord] = []

    for metadata_path in sorted((root / "content").glob("*/*/metadata.yaml")):
        metadata = load_data(metadata_path)
        if accepted_statuses is not None and metadata.get("status") not in accepted_statuses:
            continue
        confidentiality = metadata.get("source", {}).get("confidentiality")
        if not include_private and confidentiality == "private_reference":
            continue
        content_file = str(metadata.get("content_file", "question.md"))
        question_path = metadata_path.parent / content_file
        records.append(
            QuestionRecord(
                metadata_path=metadata_path,
                package_dir=metadata_path.parent,
                metadata=metadata,
                markdown=question_path.read_text(encoding="utf-8"),
            )
        )

    return records


def _ordering_value(record: QuestionRecord, field: str) -> object:
    if field == "category":
        return record.primary_category.casefold()
    if field == "difficulty":
        return int(record.metadata["difficulty"])
    if field == "title":
        return record.title.casefold()
    value = record.metadata.get(field, "")
    return str(value).casefold()


def sort_questions(
    records: Sequence[QuestionRecord],
    question_type: str,
    root: Path = ROOT,
) -> list[QuestionRecord]:
    """Apply the checked-in taxonomy ordering with the ID as a final tie-breaker."""

    ordering = load_data(root / "taxonomy" / "ordering.yaml")
    fields = ordering.get(question_type)
    if not isinstance(fields, list) or not fields:
        raise ValueError(
            f"taxonomy/ordering.yaml does not define ordering for {question_type!r}"
        )

    return sorted(
        records,
        key=lambda record: tuple(
            _ordering_value(record, str(field)) for field in fields
        )
        + (record.question_id,),
    )


def questions_by_type(
    records: Sequence[QuestionRecord],
    root: Path = ROOT,
) -> dict[str, list[QuestionRecord]]:
    grouped: dict[str, list[QuestionRecord]] = {
        question_type: [] for question_type in GUIDE_SPECS
    }
    for record in records:
        if record.question_type in grouped:
            grouped[record.question_type].append(record)
    return {
        question_type: sort_questions(items, question_type, root)
        for question_type, items in grouped.items()
    }
