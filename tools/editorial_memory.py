"""Curate human-approved, reusable editorial lessons from question feedback."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from tools.content import load_data


MEMORY_FILE = "editorial-memory.yaml"
CANDIDATES_FILE = "memory-candidates.yaml"
QUESTION_TYPES = frozenset({"all", "coding", "system_design", "fundamentals"})
TOKEN = re.compile(r"[a-z0-9]+")


class EditorialMemoryError(ValueError):
    """Raised when an editorial-memory operation is invalid."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _normalize(value: str) -> str:
    return " ".join(TOKEN.findall(value.casefold()))


def _memory_id(principle: str, source_key: str) -> str:
    identity = f"{_normalize(principle)}\n{source_key}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    return f"memory-{digest}"


def load_editorial_memory(root: Path) -> dict[str, object]:
    path = root.resolve() / MEMORY_FILE
    if not path.is_file():
        return {"schema_version": 1, "entries": []}
    value = load_data(path)
    if not isinstance(value, dict):
        raise EditorialMemoryError(f"{MEMORY_FILE} must contain an object")
    return dict(value)


def applicable_memory(
    root: Path, question_type: str
) -> list[dict[str, object]]:
    memory = load_editorial_memory(root)
    entries = memory.get("entries", [])
    if not isinstance(entries, list):
        raise EditorialMemoryError(f"{MEMORY_FILE}.entries must be an array")
    applicable: list[dict[str, object]] = []
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        scopes = raw.get("question_types", [])
        if isinstance(scopes, list) and (
            "all" in scopes or question_type in scopes
        ):
            applicable.append(dict(raw))
    return sorted(applicable, key=lambda item: str(item.get("id", "")))


def memory_prompt(root: Path, question_type: str) -> str:
    entries = applicable_memory(root, question_type)
    if not entries:
        return "No active editorial-memory lessons apply to this question type."
    lines = [
        "Apply these human-approved editorial-memory lessons when relevant; source fidelity "
        "and the current human notes still take precedence:"
    ]
    for entry in entries:
        lines.append(
            f"- [{entry.get('id')}] {entry.get('principle')} "
            f"Why: {entry.get('rationale')}"
        )
    return "\n".join(lines)


def _latest_feedback(package: Path) -> str:
    paths = sorted((package / "feedback").glob("*.md"))
    if not paths:
        raise EditorialMemoryError(
            "memory candidates require preserved human feedback under feedback/"
        )
    return paths[-1].relative_to(package).as_posix()


def record_memory_candidates(
    *,
    package: Path,
    candidates: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Persist agent-proposed generalizations as pending human decisions."""

    if not candidates:
        return []
    feedback_file = _latest_feedback(package)
    path = package / CANDIDATES_FILE
    if path.is_file():
        document = load_data(path)
        if not isinstance(document, dict):
            raise EditorialMemoryError(f"{path} must contain an object")
        value = dict(document)
    else:
        value = {
            "schema_version": 1,
            "question_id": package.name,
            "candidates": [],
        }
    existing = value.get("candidates", [])
    if not isinstance(existing, list):
        raise EditorialMemoryError(f"{path}.candidates must be an array")
    by_id = {
        str(item.get("id")): dict(item)
        for item in existing
        if isinstance(item, dict) and item.get("id")
    }
    recorded: list[dict[str, object]] = []
    for raw in candidates[:3]:
        principle = str(raw.get("principle", "")).strip()
        rationale = str(raw.get("rationale", "")).strip()
        question_types = sorted(
            {
                str(item)
                for item in raw.get("question_types", [])
                if str(item) in QUESTION_TYPES
            }
        )
        if len(principle) < 20 or len(rationale) < 20 or not question_types:
            continue
        candidate_id = _memory_id(
            principle,
            f"{package.name}:{feedback_file}",
        )
        if candidate_id in by_id:
            recorded.append(by_id[candidate_id])
            continue
        candidate: dict[str, object] = {
            "id": candidate_id,
            "status": "pending",
            "principle": principle,
            "rationale": rationale,
            "question_types": question_types,
            "source": {
                "question_id": package.name,
                "feedback_file": feedback_file,
            },
            "proposed_at": _now(),
        }
        by_id[candidate_id] = candidate
        recorded.append(candidate)
    value["candidates"] = sorted(by_id.values(), key=lambda item: str(item["id"]))
    _write_json(path, value)
    return recorded


def list_memory_candidates(
    root: Path,
    *,
    question_id: Optional[str] = None,
    include_decided: bool = False,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    pattern = f"*/{question_id}/{CANDIDATES_FILE}" if question_id else f"*/*/{CANDIDATES_FILE}"
    for path in sorted((root.resolve() / "content").glob(pattern)):
        value = load_data(path)
        if not isinstance(value, dict):
            continue
        for raw in value.get("candidates", []):
            if not isinstance(raw, dict):
                continue
            candidate = dict(raw)
            if include_decided or candidate.get("status") == "pending":
                candidates.append(candidate)
    return sorted(candidates, key=lambda item: str(item.get("id", "")))


def _candidate_location(root: Path, candidate_id: str) -> tuple[Path, dict[str, object], int]:
    matches: list[tuple[Path, dict[str, object], int]] = []
    for path in sorted((root.resolve() / "content").glob(f"*/*/{CANDIDATES_FILE}")):
        value = load_data(path)
        if not isinstance(value, dict):
            continue
        items = value.get("candidates", [])
        if not isinstance(items, list):
            continue
        for index, raw in enumerate(items):
            if isinstance(raw, dict) and raw.get("id") == candidate_id:
                matches.append((path, dict(value), index))
    if len(matches) != 1:
        raise EditorialMemoryError(
            f"memory candidate {candidate_id!r} does not identify exactly one record"
        )
    return matches[0]


def approve_memory_candidate(
    *,
    root: Path,
    candidate_id: str,
    reviewer: str,
    confirmation: str,
) -> dict[str, object]:
    if not reviewer.strip():
        raise EditorialMemoryError("memory approval requires a reviewer")
    expected = f"REMEMBER {candidate_id}"
    if confirmation != expected:
        raise EditorialMemoryError(
            f"memory confirmation must exactly match {expected!r}"
        )
    path, document, index = _candidate_location(root, candidate_id)
    metadata = load_data(path.parent / "metadata.yaml")
    if not isinstance(metadata, dict) or metadata.get("status") not in {
        "approved",
        "published",
    }:
        raise EditorialMemoryError(
            "approve the source question before activating its reusable lesson"
        )
    items = list(document["candidates"])
    candidate = dict(items[index])
    if candidate.get("status") != "pending":
        raise EditorialMemoryError("only pending memory candidates can be approved")

    memory = load_editorial_memory(root)
    entries = memory.get("entries", [])
    if not isinstance(entries, list):
        raise EditorialMemoryError(f"{MEMORY_FILE}.entries must be an array")
    existing_index = next(
        (
            position
            for position, item in enumerate(entries)
            if isinstance(item, dict)
            and _normalize(str(item.get("principle", "")))
            == _normalize(str(candidate.get("principle", "")))
        ),
        None,
    )
    now = _now()
    if existing_index is None:
        entry = {
            "id": candidate["id"],
            "principle": candidate["principle"],
            "rationale": candidate["rationale"],
            "question_types": candidate["question_types"],
            "source": candidate["source"],
            "approved_by": reviewer,
            "approved_at": now,
        }
        entries.append(entry)
    else:
        entry = dict(entries[existing_index])
        scopes = set(str(item) for item in entry.get("question_types", []))
        scopes.update(str(item) for item in candidate.get("question_types", []))
        entry["question_types"] = ["all"] if "all" in scopes else sorted(scopes)
        entries[existing_index] = entry
        candidate["merged_into"] = entry["id"]

    memory["entries"] = sorted(entries, key=lambda item: str(item.get("id", "")))
    _write_json(root.resolve() / MEMORY_FILE, memory)

    candidate["status"] = "approved"
    candidate["decided_by"] = reviewer
    candidate["decided_at"] = now
    items[index] = candidate
    document["candidates"] = items
    _write_json(path, document)
    return entry


def reject_memory_candidate(
    *, root: Path, candidate_id: str, reviewer: str, reason: str
) -> dict[str, object]:
    if not reviewer.strip():
        raise EditorialMemoryError("memory rejection requires a reviewer")
    if not reason.strip():
        raise EditorialMemoryError("memory rejection requires a reason")
    path, document, index = _candidate_location(root, candidate_id)
    items = list(document["candidates"])
    candidate = dict(items[index])
    if candidate.get("status") != "pending":
        raise EditorialMemoryError("only pending memory candidates can be rejected")
    candidate["status"] = "rejected"
    candidate["decided_by"] = reviewer
    candidate["decided_at"] = _now()
    candidate["decision_reason"] = reason.strip()
    items[index] = candidate
    document["candidates"] = items
    _write_json(path, document)
    return candidate


def active_memory_entries(root: Path) -> Iterable[dict[str, object]]:
    value = load_editorial_memory(root)
    entries = value.get("entries", [])
    return (
        dict(item) for item in entries if isinstance(item, dict)
    ) if isinstance(entries, list) else iter(())
