"""Deterministically shortlist potentially duplicate interview questions."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional, Protocol

from tools.content import ROOT, QuestionRecord, discover_questions


TOKEN = re.compile(r"[a-z0-9]+")
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "build",
        "design",
        "for",
        "how",
        "implement",
        "in",
        "of",
        "question",
        "system",
        "the",
        "to",
        "with",
    }
)


class SimilarityJudge(Protocol):
    """Future semantic judge interface; deterministic screening works without it."""

    def score(self, query: str, candidate: QuestionRecord) -> Optional[float]:
        """Return a semantic score in [0, 1], or None when unavailable."""


@dataclass(frozen=True)
class DuplicateCandidate:
    question_id: str
    title: str
    question_type: str
    deterministic_score: float
    semantic_score: Optional[float]
    reasons: tuple[str, ...]


def normalize_text(value: str) -> str:
    return " ".join(TOKEN.findall(value.casefold()))


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in TOKEN.findall(value.casefold())
        if token not in STOP_WORDS and len(token) > 1
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _prompt_excerpt(markdown: str) -> str:
    lines = markdown.splitlines()
    start = next(
        (
            index + 1
            for index, line in enumerate(lines)
            if line in {"## Interview prompt", "## Question"}
        ),
        0,
    )
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if not line.startswith(("#", "![")):
            body.append(line)
    return "\n".join(body).strip()


def duplicate_candidates(
    *,
    root: Path,
    title: str,
    prompt: str,
    question_type: str,
    question_id: Optional[str] = None,
    judge: Optional[SimilarityJudge] = None,
    minimum_score: float = 0.25,
) -> list[DuplicateCandidate]:
    """Return a stable shortlist; semantic scoring can be added without changing callers."""

    normalized_title = normalize_text(title)
    title_tokens = _tokens(title)
    prompt_tokens = _tokens(prompt)
    combined_tokens = title_tokens | prompt_tokens
    candidates: list[DuplicateCandidate] = []

    for record in discover_questions(root, include_private=True):
        reasons: list[str] = []
        record_title = normalize_text(record.title)
        record_prompt = _prompt_excerpt(record.markdown)
        candidate_title_tokens = _tokens(record.title)
        candidate_prompt_tokens = _tokens(record_prompt)
        title_score = _jaccard(title_tokens, candidate_title_tokens)
        prompt_score = _jaccard(prompt_tokens, candidate_prompt_tokens)
        combined_score = _jaccard(
            combined_tokens, candidate_title_tokens | candidate_prompt_tokens
        )

        score = max(title_score, prompt_score * 0.9, combined_score)
        if question_id and record.question_id == question_id:
            score = 1.0
            reasons.append("same stable ID")
        if normalized_title and normalized_title == record_title:
            score = 1.0
            reasons.append("same normalized title")
        if title_score >= 0.5:
            reasons.append("overlapping title terms")
        if prompt_score >= 0.4:
            reasons.append("overlapping prompt terms")
        if record.question_type == question_type:
            reasons.append("same question type")

        semantic = judge.score(prompt, record) if judge is not None else None
        ranking_score = max(score, semantic or 0.0)
        if ranking_score < minimum_score:
            continue
        candidates.append(
            DuplicateCandidate(
                question_id=record.question_id,
                title=record.title,
                question_type=record.question_type,
                deterministic_score=round(score, 4),
                semantic_score=semantic,
                reasons=tuple(reasons or ["shared question vocabulary"]),
            )
        )

    return sorted(
        candidates,
        key=lambda item: (
            -(item.semantic_score or item.deterministic_score),
            item.question_id,
        ),
    )


def report_dict(
    *,
    title: str,
    question_type: str,
    candidates: list[DuplicateCandidate],
    blocking_threshold: float = 0.82,
) -> dict[str, object]:
    blocking = [
        item.question_id
        for item in candidates
        if max(item.deterministic_score, item.semantic_score or 0.0)
        >= blocking_threshold
    ]
    return {
        "schema_version": 1,
        "algorithm": "token-jaccard-v1",
        "query": {"title": title, "question_type": question_type},
        "blocking_threshold": blocking_threshold,
        "blocking_candidates": blocking,
        "candidates": [asdict(item) for item in candidates],
        "human_decision": "pending" if blocking else "not_required",
        "human_reason": "",
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--type", required=True, dest="question_type")
    parser.add_argument("--title", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--id", dest="question_id")
    args = parser.parse_args(list(argv) if argv is not None else None)
    prompt = args.input.read_text(encoding="utf-8")
    candidates = duplicate_candidates(
        root=args.root.resolve(),
        title=args.title,
        prompt=prompt,
        question_type=args.question_type,
        question_id=args.question_id,
    )
    print(
        json.dumps(
            report_dict(
                title=args.title,
                question_type=args.question_type,
                candidates=candidates,
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
