"""Validate question metadata and repository-level content relationships.

The repository deliberately keeps the first implementation dependency-free.
Metadata uses JSON syntax in ``.yaml`` files (JSON is a YAML subset), and this
module implements the JSON Schema keywords used by the checked-in schemas.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple

from tools.render_diagrams import render_source


ROOT = Path(__file__).resolve().parents[1]

SCHEMA_BY_TYPE = {
    "system_design": "system-design.schema.json",
    "coding": "coding.schema.json",
    "fundamentals": "fundamentals.schema.json",
}

DIRECTORY_BY_TYPE = {
    "system_design": "system-design",
    "coding": "coding",
    "fundamentals": "fundamentals",
}

ID_PREFIX_BY_TYPE = {
    "system_design": "sd-",
    "coding": "code-",
    "fundamentals": "fund-",
}

REQUIRED_HEADINGS = {
    "system_design": [
        "## Interview prompt",
        "## What the interviewer is testing",
        "## Good solution",
        "## Great solution improvements",
        "## Failure scenarios",
        "## Common pitfalls",
        "## Follow-up questions",
        "## Evaluation rubric",
    ],
    "coding": [
        "## Interview prompt",
        "## API contract",
        "## Primary approach",
        "## Reference solution",
        "## Complexity analysis",
        "## Common mistakes",
        "## Optional improvements",
        "## Follow-up questions",
        "## Practice repository",
    ],
    "fundamentals": [
        "## Concise interview answer",
        "## Deep explanation",
        "## Example",
        "## Common misconception",
        "## Interview trap",
        "## Follow-up questions",
        "## Runnable experiment",
    ],
}

PLACEHOLDER_PATTERN = re.compile(
    r"\b(?:TODO|TBD|FIXME|INSERT\s+ANSWER|NEEDS\s+DIAGRAM|"
    r"UNKNOWN\s+COMPLEXITY|PLACEHOLDER)\b",
    re.IGNORECASE,
)
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
PUBLICATION_STATUSES = frozenset({"approved", "published"})
SECTION_ITEM_LIMITS = {
    "system_design": (
        "## Great solution improvements",
        "## Follow-up questions",
    ),
    "coding": (
        "## Optional improvements",
        "## Follow-up questions",
    ),
    "fundamentals": (
        "## Great answer improvements",
        "## Follow-up questions",
    ),
}


@dataclass(frozen=True)
class ValidationIssue:
    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.location}: {self.message}"


def load_data(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path}: expected JSON-compatible YAML; "
            f"parse error at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


class SchemaValidator:
    """Small validator for the JSON Schema subset used in this repository."""

    def __init__(self, schema_root: Path):
        self.schema_root = schema_root
        self._cache: dict[Path, Mapping[str, Any]] = {}

    def _load_schema(self, path: Path) -> Mapping[str, Any]:
        path = path.resolve()
        if path not in self._cache:
            schema = load_data(path)
            if not isinstance(schema, dict):
                raise ValueError(f"{path}: schema root must be an object")
            self._cache[path] = schema
        return self._cache[path]

    def _resolve_ref(
        self, ref: str, current_schema_path: Path
    ) -> Tuple[Mapping[str, Any], Path]:
        filename, marker, fragment = ref.partition("#")
        target_path = (
            current_schema_path
            if not filename
            else (current_schema_path.parent / filename).resolve()
        )
        target: Any = self._load_schema(target_path)
        if marker and fragment:
            if not fragment.startswith("/"):
                raise ValueError(f"unsupported schema reference fragment: {ref}")
            for raw_part in fragment.lstrip("/").split("/"):
                part = raw_part.replace("~1", "/").replace("~0", "~")
                target = target[part]
        if not isinstance(target, dict):
            raise ValueError(f"schema reference does not resolve to an object: {ref}")
        return target, target_path

    def validate(
        self, instance: Any, schema_path: Path, location: str = "$"
    ) -> List[ValidationIssue]:
        path = schema_path.resolve()
        schema = self._load_schema(path)
        issues: List[ValidationIssue] = []
        self._validate(instance, schema, path, location, issues)
        return issues

    def _validate(
        self,
        value: Any,
        schema: Mapping[str, Any],
        schema_path: Path,
        location: str,
        issues: List[ValidationIssue],
    ) -> None:
        if "$ref" in schema:
            target, target_path = self._resolve_ref(schema["$ref"], schema_path)
            self._validate(value, target, target_path, location, issues)
            schema = {key: item for key, item in schema.items() if key != "$ref"}

        for child_schema in schema.get("allOf", []):
            self._validate(value, child_schema, schema_path, location, issues)

        expected_type = schema.get("type")
        if expected_type is not None:
            expected_types = (
                expected_type if isinstance(expected_type, list) else [expected_type]
            )
            if not any(_json_type_matches(value, item) for item in expected_types):
                joined = " or ".join(expected_types)
                issues.append(
                    ValidationIssue(
                        location, f"expected type {joined}, got {type(value).__name__}"
                    )
                )
                return

        if "const" in schema and value != schema["const"]:
            issues.append(
                ValidationIssue(location, f"must equal {schema['const']!r}")
            )

        if "enum" in schema and value not in schema["enum"]:
            allowed = ", ".join(repr(item) for item in schema["enum"])
            issues.append(
                ValidationIssue(location, f"value {value!r} is not one of: {allowed}")
            )

        if isinstance(value, dict):
            required = schema.get("required", [])
            for key in required:
                if key not in value:
                    issues.append(
                        ValidationIssue(location, f"missing required property {key!r}")
                    )

            properties = schema.get("properties", {})
            for key, child_value in value.items():
                child_location = f"{location}.{key}"
                if key in properties:
                    self._validate(
                        child_value,
                        properties[key],
                        schema_path,
                        child_location,
                        issues,
                    )
                elif schema.get("additionalProperties") is False:
                    issues.append(
                        ValidationIssue(
                            child_location, "additional property is not allowed"
                        )
                    )

        if isinstance(value, list):
            if len(value) < schema.get("minItems", 0):
                issues.append(
                    ValidationIssue(
                        location,
                        f"must contain at least {schema['minItems']} item(s)",
                    )
                )
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                issues.append(
                    ValidationIssue(
                        location,
                        f"must contain at most {schema['maxItems']} item(s)",
                    )
                )
            if schema.get("uniqueItems"):
                canonical = [json.dumps(item, sort_keys=True) for item in value]
                if len(canonical) != len(set(canonical)):
                    issues.append(ValidationIssue(location, "items must be unique"))
            if "items" in schema:
                for index, child_value in enumerate(value):
                    self._validate(
                        child_value,
                        schema["items"],
                        schema_path,
                        f"{location}[{index}]",
                        issues,
                    )

        if isinstance(value, str):
            if len(value) < schema.get("minLength", 0):
                issues.append(
                    ValidationIssue(
                        location,
                        f"must be at least {schema['minLength']} characters long",
                    )
                )
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                issues.append(
                    ValidationIssue(
                        location,
                        f"must be at most {schema['maxLength']} characters long",
                    )
                )
            if "pattern" in schema and re.search(schema["pattern"], value) is None:
                issues.append(
                    ValidationIssue(
                        location, f"must match pattern {schema['pattern']!r}"
                    )
                )
            if schema.get("format") == "date":
                try:
                    dt.date.fromisoformat(value)
                except ValueError:
                    issues.append(
                        ValidationIssue(location, "must be an ISO date (YYYY-MM-DD)")
                    )

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                issues.append(
                    ValidationIssue(
                        location, f"must be greater than or equal to {schema['minimum']}"
                    )
                )
            if "maximum" in schema and value > schema["maximum"]:
                issues.append(
                    ValidationIssue(
                        location, f"must be less than or equal to {schema['maximum']}"
                    )
                )
            if "multipleOf" in schema and value % schema["multipleOf"] != 0:
                issues.append(
                    ValidationIssue(
                        location, f"must be a multiple of {schema['multipleOf']}"
                    )
                )


def duplicate_id_issues(
    records: Sequence[Tuple[Path, Mapping[str, Any]]]
) -> List[ValidationIssue]:
    by_id: dict[str, List[Path]] = {}
    for path, metadata in records:
        question_id = metadata.get("id")
        if isinstance(question_id, str):
            by_id.setdefault(question_id, []).append(path)

    issues = []
    for question_id, paths in sorted(by_id.items()):
        if len(paths) > 1:
            locations = ", ".join(str(path) for path in paths)
            issues.append(
                ValidationIssue(
                    "content",
                    f"duplicate question id {question_id!r} in {locations}",
                )
            )
    return issues


def _load_taxonomy(root: Path, name: str) -> set[str]:
    data = load_data(root / "taxonomy" / f"{name}.yaml")
    values = data.get("values")
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise ValueError(f"taxonomy/{name}.yaml: 'values' must be a string array")
    if len(values) != len(set(values)):
        raise ValueError(f"taxonomy/{name}.yaml: values must be unique")
    return set(values)


def _review_file_issues(
    package_dir: Path, metadata: Mapping[str, Any]
) -> List[ValidationIssue]:
    review_path = package_dir / "review.yaml"
    if not review_path.is_file():
        return [ValidationIssue(str(review_path), "required file is missing")]
    try:
        review = load_data(review_path)
    except ValueError as exc:
        return [ValidationIssue(str(review_path), str(exc))]
    if review.get("question_id") != metadata.get("id"):
        return [
            ValidationIssue(
                str(review_path),
                "question_id must match metadata id",
            )
        ]
    if review.get("checks") != metadata.get("review"):
        return [
            ValidationIssue(
                str(review_path),
                "checks must match metadata review flags",
            )
        ]
    return []


def _workflow_file_issues(
    root: Path, package_dir: Path, metadata: Mapping[str, Any]
) -> List[ValidationIssue]:
    path = package_dir / "workflow.yaml"
    status = metadata.get("status")
    if not path.is_file():
        if status in {"needs_clarification", "changes_requested"}:
            return [
                ValidationIssue(
                    str(path.relative_to(root)),
                    f"status {status!r} requires workflow state",
                )
            ]
        return []
    try:
        workflow = load_data(path)
    except (OSError, ValueError) as exc:
        return [ValidationIssue(str(path.relative_to(root)), str(exc))]
    issues: List[ValidationIssue] = []
    if not isinstance(workflow, dict):
        return [ValidationIssue(str(path.relative_to(root)), "must contain an object")]
    required = {
        "schema_version",
        "run_id",
        "question_id",
        "question_type",
        "state",
        "branch",
        "agent_threads",
        "attempts",
        "pending_clarifications",
        "created_at",
        "updated_at",
        "events",
    }
    missing = sorted(required - set(workflow))
    if missing:
        issues.append(
            ValidationIssue(
                str(path.relative_to(root)),
                "missing workflow fields: " + ", ".join(missing),
            )
        )
    if workflow.get("schema_version") != 1:
        issues.append(ValidationIssue(str(path.relative_to(root)), "schema_version must be 1"))
    if workflow.get("question_id") != metadata.get("id"):
        issues.append(ValidationIssue(str(path.relative_to(root)), "question_id must match metadata"))
    if workflow.get("question_type") != metadata.get("type"):
        issues.append(ValidationIssue(str(path.relative_to(root)), "question_type must match metadata"))
    state = workflow.get("state")
    allowed_status_by_state = {
        "normalized": "normalized",
        "needs_clarification": "needs_clarification",
        "drafting": "draft",
        "agent_failed": "draft",
        "agent_validation_failed": "draft",
        "agent_review_failed": "draft",
        "needs_human_review": "needs_human_review",
        "changes_requested": "changes_requested",
        "approved": "approved",
        "rejected_duplicate": "deprecated",
    }
    expected_status = allowed_status_by_state.get(state)
    if expected_status is None:
        issues.append(ValidationIssue(str(path.relative_to(root)), "invalid workflow state"))
    elif metadata.get("status") != expected_status:
        issues.append(
            ValidationIssue(
                str(path.relative_to(root)),
                f"workflow state {state!r} requires status {expected_status!r}",
            )
        )
    if not isinstance(workflow.get("branch"), str):
        issues.append(ValidationIssue(str(path.relative_to(root)), "branch must be a string"))
    if not isinstance(workflow.get("agent_threads"), dict):
        issues.append(ValidationIssue(str(path.relative_to(root)), "agent_threads must be an object"))
    if not isinstance(workflow.get("attempts"), dict):
        issues.append(ValidationIssue(str(path.relative_to(root)), "attempts must be an object"))
    if not isinstance(workflow.get("pending_clarifications"), list):
        issues.append(
            ValidationIssue(str(path.relative_to(root)), "pending_clarifications must be an array")
        )
    events = workflow.get("events")
    if not isinstance(events, list) or any(not isinstance(item, dict) for item in events):
        issues.append(ValidationIssue(str(path.relative_to(root)), "events must be an object array"))
    if state == "needs_human_review":
        attempts = workflow.get("attempts", {})
        review_attempts = attempts.get("review", 0) if isinstance(attempts, dict) else 0
        report_path = package_dir / "agent-review.yaml"
        if not isinstance(review_attempts, int) or review_attempts < 1:
            issues.append(
                ValidationIssue(
                    str(path.relative_to(root)),
                    "needs_human_review requires a completed independent review attempt",
                )
            )
        if not report_path.is_file():
            issues.append(
                ValidationIssue(
                    str(report_path.relative_to(root)),
                    "needs_human_review requires an independent review report",
                )
            )
        else:
            try:
                report = load_data(report_path)
            except (OSError, ValueError) as exc:
                issues.append(ValidationIssue(str(report_path.relative_to(root)), str(exc)))
            else:
                report_issues = report.get("issues") if isinstance(report, dict) else None
                blocking = [
                    item
                    for item in report_issues
                    if isinstance(item, dict)
                    and item.get("severity") in {"blocking", "important"}
                ] if isinstance(report_issues, list) else ["invalid report"]
                if (
                    not isinstance(report, dict)
                    or report.get("passed") is not True
                    or not isinstance(report_issues, list)
                    or blocking
                ):
                    issues.append(
                        ValidationIssue(
                            str(report_path.relative_to(root)),
                            "independent review must pass without unresolved blocking issues",
                        )
                    )
    return issues


def _deduplication_file_issues(
    root: Path, package_dir: Path, metadata: Mapping[str, Any]
) -> List[ValidationIssue]:
    path = package_dir / "deduplication.yaml"
    if not path.is_file():
        return []
    try:
        report = load_data(path)
    except (OSError, ValueError) as exc:
        return [ValidationIssue(str(path.relative_to(root)), str(exc))]
    if not isinstance(report, dict):
        return [ValidationIssue(str(path.relative_to(root)), "must contain an object")]
    issues: List[ValidationIssue] = []
    if report.get("schema_version") != 1:
        issues.append(ValidationIssue(str(path.relative_to(root)), "schema_version must be 1"))
    if report.get("human_decision") not in {
        "pending",
        "not_required",
        "distinct",
        "duplicate",
    }:
        issues.append(ValidationIssue(str(path.relative_to(root)), "invalid human_decision"))
    candidates = report.get("candidates")
    blocking = report.get("blocking_candidates")
    if not isinstance(blocking, list) or any(
        not isinstance(item, str) for item in blocking
    ):
        issues.append(
            ValidationIssue(
                str(path.relative_to(root)),
                "blocking_candidates must be a string array",
            )
        )
    if not isinstance(candidates, list):
        issues.append(ValidationIssue(str(path.relative_to(root)), "candidates must be an array"))
    else:
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict) or not isinstance(
                candidate.get("question_id"), str
            ):
                issues.append(
                    ValidationIssue(
                        f"{path.relative_to(root)}.candidates[{index}]",
                        "candidate must contain a question_id",
                    )
                )
    if report.get("human_decision") == "pending" and metadata.get("status") not in {
        "needs_clarification",
        "deprecated",
    }:
        issues.append(
            ValidationIssue(
                str(path.relative_to(root)),
                "pending duplicate review must pause the question lifecycle",
            )
        )
    return issues


def _publication_issues(
    metadata_path: Path,
    metadata: Mapping[str, Any],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    status = metadata.get("status")
    review = metadata.get("review", {})
    confidentiality = metadata.get("source", {}).get("confidentiality")

    if status == "needs_human_review" and not review.get("agent_reviewed"):
        issues.append(
            ValidationIssue(
                f"{metadata_path}.review.agent_reviewed",
                "needs_human_review content must have completed agent review",
            )
        )

    if status in PUBLICATION_STATUSES:
        incomplete = sorted(key for key, value in review.items() if value is not True)
        if incomplete:
            issues.append(
                ValidationIssue(
                    f"{metadata_path}.review",
                    "approved or published content requires every review flag; "
                    f"incomplete: {', '.join(incomplete)}",
                )
            )
        if confidentiality == "private_reference":
            issues.append(
                ValidationIssue(
                    f"{metadata_path}.source.confidentiality",
                    "private-reference content cannot be approved or published",
                )
            )
        if metadata.get("type") == "coding" and not isinstance(
            metadata.get("practice"), dict
        ):
            issues.append(
                ValidationIssue(
                    f"{metadata_path}.practice",
                    "approved or published coding content requires a practice package",
                )
            )
    return issues


def _markdown_link_issues(
    root: Path,
    content_path: Path,
    markdown: str,
    generated_diagrams: set[Path],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for raw_target in MARKDOWN_LINK.findall(markdown):
        target = raw_target.strip().split("#", 1)[0].split("?", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        resolved = (content_path.parent / target).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            issues.append(
                ValidationIssue(
                    str(content_path.relative_to(root)),
                    f"local Markdown link escapes the repository: {raw_target!r}",
                )
            )
            continue
        if not resolved.exists() and resolved not in generated_diagrams:
            issues.append(
                ValidationIssue(
                    str(content_path.relative_to(root)),
                    f"broken local Markdown link: {raw_target!r}",
                )
            )
    return issues


def _placeholder_issues(
    root: Path,
    package_dir: Path,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for filename in ("question.md", "expert-notes.md"):
        path = package_dir / filename
        if not path.is_file():
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = PLACEHOLDER_PATTERN.search(line)
            if match:
                issues.append(
                    ValidationIssue(
                        f"{path.relative_to(root)}:{line_number}",
                        f"unresolved placeholder {match.group(0)!r}",
                    )
                )
    return issues


def _section_item_issues(
    root: Path,
    content_path: Path,
    markdown: str,
    question_type: str,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    lines = markdown.splitlines()
    for section_heading in SECTION_ITEM_LIMITS[question_type]:
        try:
            start = lines.index(section_heading) + 1
        except ValueError:
            continue
        end = next(
            (
                index
                for index in range(start, len(lines))
                if lines[index].startswith("## ")
            ),
            len(lines),
        )
        section = lines[start:end]
        subsection_count = sum(line.startswith("### ") for line in section)
        top_level_bullets = sum(
            line.startswith(("- ", "* ")) for line in section
        )
        item_count = subsection_count if subsection_count else top_level_bullets
        if item_count > 3:
            issues.append(
                ValidationIssue(
                    str(content_path.relative_to(root)),
                    f"{section_heading!r} has {item_count} items; maximum is 3",
                )
            )
    return issues


def _diagram_issues(
    root: Path,
    package_dir: Path,
    question_id: str,
    diagrams: Sequence[Mapping[str, Any]],
) -> Tuple[List[ValidationIssue], set[Path]]:
    issues: List[ValidationIssue] = []
    generated_paths: set[Path] = set()

    for diagram in diagrams:
        source_path = package_dir / str(diagram.get("source_file", ""))
        rendered_name = str(diagram.get("rendered_file", ""))
        generated_path = (
            root / "generated" / "diagrams" / question_id / rendered_name
        ).resolve()
        generated_paths.add(generated_path)

        if not source_path.is_file():
            issues.append(
                ValidationIssue(
                    str(source_path.relative_to(root)),
                    "declared Mermaid source is missing",
                )
            )
            continue

        expected_name = source_path.with_suffix(".svg").name
        if rendered_name != expected_name:
            issues.append(
                ValidationIssue(
                    str(source_path.relative_to(root)),
                    f"rendered_file must be {expected_name!r}",
                )
            )

        try:
            expected_svg = render_source(source_path.read_text(encoding="utf-8"))
            ET.fromstring(expected_svg)
        except (OSError, ValueError, ET.ParseError) as exc:
            issues.append(
                ValidationIssue(
                    str(source_path.relative_to(root)),
                    f"Mermaid source is not renderable: {exc}",
                )
            )
            continue

        if generated_path.is_file():
            actual_svg = generated_path.read_text(encoding="utf-8")
            try:
                ET.fromstring(actual_svg)
            except ET.ParseError as exc:
                issues.append(
                    ValidationIssue(
                        str(generated_path.relative_to(root)),
                        f"generated SVG is invalid XML: {exc}",
                    )
                )
                continue
            if actual_svg != expected_svg:
                issues.append(
                    ValidationIssue(
                        str(generated_path.relative_to(root)),
                        "generated SVG is stale; run `make diagrams`",
                    )
                )

    return issues, generated_paths


def _practice_issues(
    root: Path,
    question_id: str,
    field: str,
    practice_link: Mapping[str, Any],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    practice_path = root / str(practice_link.get("path", ""))
    required_paths = (
        "README.md",
        "metadata.yaml",
        "CMakeLists.txt",
        "starter",
        "solution",
        "tests",
    )
    for required in required_paths:
        if not (practice_path / required).exists():
            issues.append(
                ValidationIssue(
                    str((practice_path / required).relative_to(root)),
                    f"required {field} path is missing",
                )
            )
    if issues:
        return issues

    practice_metadata_path = practice_path / "metadata.yaml"
    try:
        practice_metadata = load_data(practice_metadata_path)
    except ValueError as exc:
        return [
            ValidationIssue(str(practice_metadata_path.relative_to(root)), str(exc))
        ]

    expected_fields = {
        "schema_version": 1,
        "question_id": question_id,
        "language": "C++20",
    }
    for key, expected in expected_fields.items():
        if practice_metadata.get(key) != expected:
            issues.append(
                ValidationIssue(
                    f"{practice_metadata_path.relative_to(root)}.{key}",
                    f"must equal {expected!r}",
                )
            )

    for target_field in ("starter_target", "solution_target", "test_target"):
        target = practice_metadata.get(target_field)
        if not isinstance(target, str) or re.fullmatch(r"[a-z][a-z0-9_]+", target) is None:
            issues.append(
                ValidationIssue(
                    f"{practice_metadata_path.relative_to(root)}.{target_field}",
                    "must be a valid lowercase CMake target",
                )
            )

    if field == "practice":
        if practice_link.get("cmake_target") != practice_metadata.get(
            "solution_target"
        ):
            issues.append(
                ValidationIssue(
                    str(practice_metadata_path.relative_to(root)),
                    "solution_target must match content practice.cmake_target",
                )
            )
        if practice_link.get("test_target") != practice_metadata.get("test_target"):
            issues.append(
                ValidationIssue(
                    str(practice_metadata_path.relative_to(root)),
                    "test_target must match content practice.test_target",
                )
            )

    question_cmake = (practice_path / "CMakeLists.txt").read_text(encoding="utf-8")
    readme = (practice_path / "README.md").read_text(encoding="utf-8")
    for target_field in ("starter_target", "solution_target", "test_target"):
        target = practice_metadata.get(target_field)
        if isinstance(target, str):
            if target not in question_cmake:
                issues.append(
                    ValidationIssue(
                        str((practice_path / "CMakeLists.txt").relative_to(root)),
                        f"declared target {target!r} is not defined",
                    )
                )
            if target not in readme:
                issues.append(
                    ValidationIssue(
                        str((practice_path / "README.md").relative_to(root)),
                        f"question-specific command for {target!r} is missing",
                    )
                )

    root_cmake = (root / "practice" / "CMakeLists.txt").read_text(encoding="utf-8")
    expected_registration = f"add_subdirectory(questions/{practice_path.name})"
    if expected_registration not in root_cmake:
        issues.append(
            ValidationIssue(
                "practice/CMakeLists.txt",
                f"missing root registration {expected_registration!r}",
            )
        )

    for directory in ("starter", "solution", "tests"):
        source_files = sorted((practice_path / directory).glob("*.[ch]pp"))
        source_files.extend(sorted((practice_path / directory).glob("*.hpp")))
        if not source_files:
            issues.append(
                ValidationIssue(
                    str((practice_path / directory).relative_to(root)),
                    "must contain C++ source or header files",
                )
            )

    starter_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((practice_path / "starter").glob("*"))
        if path.is_file()
    )
    if PLACEHOLDER_PATTERN.search(starter_text) is None:
        issues.append(
            ValidationIssue(
                str((practice_path / "starter").relative_to(root)),
                "starter must retain at least one explicit candidate TODO",
            )
        )

    for solution_path in sorted((practice_path / "solution").glob("*")):
        if not solution_path.is_file():
            continue
        match = PLACEHOLDER_PATTERN.search(
            solution_path.read_text(encoding="utf-8")
        )
        if match:
            issues.append(
                ValidationIssue(
                    str(solution_path.relative_to(root)),
                    f"reference solution contains unresolved placeholder {match.group(0)!r}",
                )
            )

    return issues


def validate_repository(root: Path = ROOT) -> List[ValidationIssue]:
    root = root.resolve()
    validator = SchemaValidator(root / "schemas")
    issues: List[ValidationIssue] = []

    try:
        allowed_categories = _load_taxonomy(root, "categories")
        allowed_tags = _load_taxonomy(root, "tags")
        difficulty = load_data(root / "taxonomy" / "difficulty.yaml")
        expected_levels = {str(number) for number in range(1, 6)}
        if set(difficulty.get("levels", {})) != expected_levels:
            issues.append(
                ValidationIssue(
                    "taxonomy/difficulty.yaml",
                    "levels must define exactly 1 through 5",
                )
            )
        ordering = load_data(root / "taxonomy" / "ordering.yaml")
        allowed_order_fields = {"category", "difficulty", "title"}
        for question_type in SCHEMA_BY_TYPE:
            fields = ordering.get(question_type)
            if (
                not isinstance(fields, list)
                or not fields
                or any(field not in allowed_order_fields for field in fields)
                or len(fields) != len(set(fields))
            ):
                issues.append(
                    ValidationIssue(
                        "taxonomy/ordering.yaml",
                        f"{question_type!r} must define unique supported sort fields",
                    )
                )
    except (OSError, ValueError) as exc:
        return [ValidationIssue("taxonomy", str(exc))]

    records: List[Tuple[Path, Mapping[str, Any]]] = []
    metadata_paths = sorted((root / "content").glob("*/*/metadata.yaml"))
    if not metadata_paths:
        issues.append(ValidationIssue("content", "no question metadata found"))
        return issues

    for metadata_path in metadata_paths:
        relative = metadata_path.relative_to(root)
        try:
            metadata = load_data(metadata_path)
        except (OSError, ValueError) as exc:
            issues.append(ValidationIssue(str(relative), str(exc)))
            continue
        if not isinstance(metadata, dict):
            issues.append(ValidationIssue(str(relative), "metadata root must be an object"))
            continue

        records.append((relative, metadata))
        question_type = metadata.get("type")
        schema_name = SCHEMA_BY_TYPE.get(question_type)
        if schema_name is None:
            issues.append(
                ValidationIssue(
                    str(relative), f"unknown question type {question_type!r}"
                )
            )
            continue

        for issue in validator.validate(
            metadata,
            root / "schemas" / schema_name,
            location=str(relative),
        ):
            issues.append(issue)

        expected_directory = DIRECTORY_BY_TYPE[question_type]
        if metadata_path.parent.parent.name != expected_directory:
            issues.append(
                ValidationIssue(
                    str(relative),
                    f"type {question_type!r} must be stored under "
                    f"content/{expected_directory}",
                )
            )

        question_id = metadata.get("id")
        if isinstance(question_id, str):
            if not question_id.startswith(ID_PREFIX_BY_TYPE[question_type]):
                issues.append(
                    ValidationIssue(
                        f"{relative}.id",
                        f"must start with {ID_PREFIX_BY_TYPE[question_type]!r}",
                    )
                )
            if metadata_path.parent.name != question_id:
                issues.append(
                    ValidationIssue(
                        str(relative),
                        "parent directory name must match question id",
                    )
                )

        for field, allowed in (
            ("categories", allowed_categories),
            ("tags", allowed_tags),
        ):
            for value in metadata.get(field, []):
                if value not in allowed:
                    issues.append(
                        ValidationIssue(
                            f"{relative}.{field}",
                            f"unknown taxonomy value {value!r}",
                        )
                    )

        package_dir = metadata_path.parent
        for required_name in ("question.md", "expert-notes.md", "review.yaml"):
            required_path = package_dir / required_name
            if not required_path.is_file():
                issues.append(
                    ValidationIssue(
                        str(required_path.relative_to(root)),
                        "required file is missing",
                    )
                )
            elif not required_path.read_text(encoding="utf-8").strip():
                issues.append(
                    ValidationIssue(
                        str(required_path.relative_to(root)),
                        "required file must not be empty",
                    )
                )

        issues.extend(_publication_issues(relative, metadata))
        issues.extend(_placeholder_issues(root, package_dir))

        question_id_text = question_id if isinstance(question_id, str) else ""
        diagram_issues, generated_diagrams = _diagram_issues(
            root,
            package_dir,
            question_id_text,
            metadata.get("diagrams", []),
        )
        issues.extend(diagram_issues)

        content_path = package_dir / str(metadata.get("content_file", "question.md"))
        if content_path.is_file():
            markdown = content_path.read_text(encoding="utf-8")
            for heading in REQUIRED_HEADINGS[question_type]:
                if heading not in markdown:
                    issues.append(
                        ValidationIssue(
                            str(content_path.relative_to(root)),
                            f"missing required heading {heading!r}",
                        )
                    )
            issues.extend(
                _section_item_issues(
                    root,
                    content_path,
                    markdown,
                    question_type,
                )
            )

            for diagram in metadata.get("diagrams", []):
                rendered_name = diagram.get("rendered_file", "")
                if rendered_name and rendered_name not in markdown:
                    issues.append(
                        ValidationIssue(
                            str(content_path.relative_to(root)),
                            f"diagram {rendered_name!r} is not referenced",
                        )
                    )
            issues.extend(
                _markdown_link_issues(
                    root,
                    content_path,
                    markdown,
                    generated_diagrams,
                )
            )

        for source_file in metadata.get("source", {}).get("original_files", []):
            source_path = package_dir / source_file
            if not source_path.is_file():
                issues.append(
                    ValidationIssue(
                        str(source_path.relative_to(root)),
                        "declared original source file is missing",
                    )
                )

        issues.extend(_review_file_issues(package_dir, metadata))
        issues.extend(_workflow_file_issues(root, package_dir, metadata))
        issues.extend(_deduplication_file_issues(root, package_dir, metadata))

        practice_links = []
        for field in ("practice", "runnable_experiment"):
            practice_link = metadata.get(field)
            if isinstance(practice_link, dict):
                practice_links.append((field, practice_link))

        for field, practice_link in practice_links:
            issues.extend(
                _practice_issues(
                    root,
                    question_id_text,
                    field,
                    practice_link,
                )
            )

    issues.extend(duplicate_id_issues(records))

    known_ids = {
        metadata["id"]
        for _, metadata in records
        if isinstance(metadata.get("id"), str)
    }
    for relative, metadata in records:
        for field in ("prerequisites", "related_questions"):
            for target in metadata.get(field, []):
                if target not in known_ids:
                    issues.append(
                        ValidationIssue(
                            f"{relative}.{field}",
                            f"references unknown question id {target!r}",
                        )
                    )
                if target == metadata.get("id"):
                    issues.append(
                        ValidationIssue(
                            f"{relative}.{field}",
                            "a question cannot reference itself",
                        )
                    )

    return issues


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root (defaults to the current project)",
    )
    parser.add_argument(
        "--id",
        dest="question_id",
        help="require this question ID to exist while validating the repository",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.question_id:
        matching = list(
            (args.root.resolve() / "content").glob(
                f"*/{args.question_id}/metadata.yaml"
            )
        )
        if len(matching) != 1:
            print(
                f"validation failed: question id {args.question_id!r} "
                "does not identify exactly one package",
                file=sys.stderr,
            )
            return 1

    issues = validate_repository(args.root)
    if issues:
        print(f"validation failed with {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1

    metadata_count = len(list((args.root / "content").glob("*/*/metadata.yaml")))
    scope = f" including {args.question_id}" if args.question_id else ""
    print(f"validation passed: {metadata_count} question package(s){scope}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
