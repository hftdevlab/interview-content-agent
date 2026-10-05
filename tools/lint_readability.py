"""Deterministic reader-experience lint for tutorial Markdown.

Why this exists: every previous system-design draft passed schema validation
and agent review, yet read as a wall of text. The defects were measurable --
long paragraphs, long runs of prose without a visual anchor, and dense
caveat/negation language -- so they are checked by a script, not by taste.

The lint does not judge correctness or teaching quality. It flags the shape
problems that make a technically correct chapter tiring to read. Thresholds
live in ``THRESHOLDS`` so editors can tune them in one place.

Usage:
    python -m tools.lint_readability content/system-design/<id>/question.md
    python -m tools.lint_readability --json <file> [<file> ...]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


THRESHOLDS = {
    # A paragraph is a unit of thought. Past ~80 words readers start skimming.
    "paragraph_words_warn": 80,
    "paragraph_words_error": 110,
    "paragraph_sentences_warn": 5,
    # Consecutive prose (paragraph words) without a heading, list, table,
    # code block, figure, or callout between them.
    "prose_run_words_warn": 220,
    "prose_run_words_error": 320,
    # Average sentence length; above ~24 words prose feels legal, not spoken.
    "sentence_words_mean_warn": 24.0,
    "long_sentence_words": 38,
    "long_sentence_share_warn": 0.12,
    # Negations and caveats per 100 prose words. Reported for trend; warn only when extreme.
    "caveat_density_warn": 3.0,
    # A system-design chapter needs pictures that grow with the design.
    "min_figures": 2,
    # Code in a design chapter shows an interface, not an implementation.
    "code_block_lines_warn": 15,
    # Wider lines wrap in the printed preview and break the alignment.
    "code_line_chars_warn": 80,
}

# Language features that make a reader parse C++ instead of the design.
# Pseudocode, field lists, REST calls, and short SQL are preferred in API sections.
LANGUAGE_SPECIFIC_CODE = re.compile(
    r"std::|template\s*<|\bvirtual\b|\balignas\b|static_assert|unique_ptr|shared_ptr|"
    r"#include|\bconstexpr\b|memory_order|\bnoexcept\b|\boverride\b"
)

CAVEAT_PATTERN = re.compile(
    r"\b(?:not|never|cannot|can't|doesn't|don't|isn't|aren't|won't|"
    r"illustrative|merely|rather than|unless|however|although)\b",
    re.IGNORECASE,
)

# Phrases that signal narration about the writing instead of the system.
FILLER_PHRASES = (
    "i want us to",
    "it is important to note",
    "it's important to note",
    "i want us to notice",
    "this is not a",
    "these are illustrative",
    "illustrative assumptions",
    "not requirements supplied",
    "the reusable idea",
    "the reusable lesson",
    "in this walkthrough",
)

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z0-9`*\"(\[])")
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’_\-/.]*")


@dataclass
class Block:
    kind: str  # heading | paragraph | list | table | code | figure | quote | rule
    text: str
    line: int
    level: int = 0


@dataclass
class Finding:
    severity: str  # error | warn
    line: int
    message: str

    def render(self) -> str:
        return f"{self.severity.upper():5} line {self.line}: {self.message}"


@dataclass
class Report:
    path: str
    prose_words: int = 0
    paragraphs: int = 0
    paragraph_words_mean: float = 0.0
    paragraph_words_p90: float = 0.0
    paragraph_words_max: int = 0
    sentence_words_mean: float = 0.0
    long_sentence_share: float = 0.0
    max_prose_run: int = 0
    anchors_per_1000_words: float = 0.0
    caveat_density: float = 0.0
    figures: int = 0
    tables: int = 0
    lists: int = 0
    callouts: int = 0
    filler_hits: int = 0
    findings: List[Finding] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for item in self.findings if item.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for item in self.findings if item.severity == "warn")

    def summary(self) -> dict:
        data = {
            key: value
            for key, value in self.__dict__.items()
            if key not in {"findings"}
        }
        data["errors"] = self.errors
        data["warnings"] = self.warnings
        return data


def _strip_inline(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`[^`]*`", "code", text)
    text = re.sub(r"[*_]{1,3}", "", text)
    return text


def words(text: str) -> List[str]:
    return WORD.findall(_strip_inline(text))


def sentences(text: str) -> List[str]:
    cleaned = _strip_inline(text).strip()
    if not cleaned:
        return []
    return [part for part in SENTENCE_SPLIT.split(cleaned) if words(part)]


def parse_blocks(markdown: str) -> List[Block]:
    """Split Markdown into coarse blocks. Good enough for prose metrics."""
    lines = markdown.splitlines()
    blocks: List[Block] = []
    index = 0
    in_comment = False
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            index += 1
            continue
        if stripped.startswith("<!--"):
            in_comment = "-->" not in stripped
            index += 1
            continue
        if not stripped:
            index += 1
            continue
        if stripped.startswith("```"):
            start = index
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                index += 1
            body = "\n".join(lines[start + 1:index])
            index += 1
            blocks.append(Block("code", body, start + 1))
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            blocks.append(Block("heading", heading.group(2), index + 1, len(heading.group(1))))
            index += 1
            continue
        if re.match(r"^(-{3,}|\*{3,})$", stripped):
            blocks.append(Block("rule", "", index + 1))
            index += 1
            continue
        if re.match(r"^!\[[^\]]*\]\([^)]*\)", stripped):
            blocks.append(Block("figure", stripped, index + 1))
            index += 1
            continue
        if stripped.startswith("|"):
            start = index
            while index < len(lines) and lines[index].strip().startswith("|"):
                index += 1
            blocks.append(Block("table", "", start + 1))
            continue
        if stripped.startswith(">"):
            start = index
            body = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                body.append(lines[index].strip().lstrip(">").strip())
                index += 1
            blocks.append(Block("quote", " ".join(body), start + 1))
            continue
        if re.match(r"^(?:[-*+]\s|\d+[.)]\s)", stripped):
            start = index
            body = []
            while index < len(lines):
                current = lines[index]
                if not current.strip():
                    # A blank line ends the list unless the next line continues it.
                    nxt = lines[index + 1] if index + 1 < len(lines) else ""
                    if re.match(r"^\s*(?:[-*+]\s|\d+[.)]\s)", nxt) or nxt.startswith("   "):
                        index += 1
                        continue
                    break
                if current.strip().startswith(("#", "```", "|", ">")):
                    break
                body.append(current.strip())
                index += 1
            blocks.append(Block("list", " ".join(body), start + 1))
            continue
        start = index
        body = []
        while index < len(lines):
            current = lines[index].strip()
            if not current or current.startswith(("#", "```", "|", ">", "![")):
                break
            if re.match(r"^(?:[-*+]\s|\d+[.)]\s)", current):
                break
            body.append(current)
            index += 1
        blocks.append(Block("paragraph", " ".join(body), start + 1))
    return blocks


def _percentile(values: Sequence[int], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return float(ordered[position])


def lint_text(markdown: str, path: str = "<memory>", *, min_figures: Optional[int] = None) -> Report:
    report = Report(path=path)
    blocks = parse_blocks(markdown)
    paragraph_lengths: List[int] = []
    sentence_lengths: List[int] = []
    caveats = 0
    run = 0
    run_start = 0
    anchors = 0

    def flush_run(at_end: bool = False) -> None:
        suffix = " at end of file" if at_end else ""
        if run > THRESHOLDS["prose_run_words_error"]:
            report.findings.append(Finding("error", run_start, f"{run} words of uninterrupted prose{suffix} (max {THRESHOLDS['prose_run_words_error']}); add a list, table, figure, or split the idea"))
        elif run > THRESHOLDS["prose_run_words_warn"]:
            report.findings.append(Finding("warn", run_start, f"{run} words of uninterrupted prose{suffix} (aim <= {THRESHOLDS['prose_run_words_warn']})"))

    for block in blocks:
        if block.kind == "paragraph":
            # A paragraph that is only bold text acts as a callout label.
            plain = block.text.strip()
            if re.fullmatch(r"\*\*[^*]+\*\*:?", plain):
                anchors += 1
                flush_run()
                run = 0
                continue
            count = len(words(block.text))
            paragraph_lengths.append(count)
            report.prose_words += count
            caveats += len(CAVEAT_PATTERN.findall(block.text))
            lowered = block.text.casefold()
            report.filler_hits += sum(lowered.count(phrase) for phrase in FILLER_PHRASES)
            parts = sentences(block.text)
            sentence_lengths.extend(len(words(part)) for part in parts)
            if count > THRESHOLDS["paragraph_words_error"]:
                report.findings.append(Finding("error", block.line, f"paragraph has {count} words (max {THRESHOLDS['paragraph_words_error']})"))
            elif count > THRESHOLDS["paragraph_words_warn"]:
                report.findings.append(Finding("warn", block.line, f"paragraph has {count} words (aim <= {THRESHOLDS['paragraph_words_warn']})"))
            if len(parts) > THRESHOLDS["paragraph_sentences_warn"]:
                report.findings.append(Finding("warn", block.line, f"paragraph has {len(parts)} sentences (aim <= {THRESHOLDS['paragraph_sentences_warn']})"))
            if run == 0:
                run_start = block.line
            run += count
            if run > report.max_prose_run:
                report.max_prose_run = run
            continue

        # Everything else is a visual anchor that resets the prose run.
        flush_run()
        run = 0
        if block.kind in {"heading", "rule"}:
            anchors += 1
        elif block.kind == "figure":
            anchors += 1
            report.figures += 1
        elif block.kind == "table":
            anchors += 1
            report.tables += 1
        elif block.kind == "list":
            anchors += 1
            report.lists += 1
        elif block.kind == "quote":
            anchors += 1
            report.callouts += 1
        elif block.kind == "code":
            anchors += 1
            code_lines = [line for line in block.text.splitlines() if line.strip()]
            if len(code_lines) > THRESHOLDS["code_block_lines_warn"]:
                report.findings.append(Finding("warn", block.line, f"code block has {len(code_lines)} lines (aim <= {THRESHOLDS['code_block_lines_warn']}); show the interface, not the implementation"))
            widest = max((len(line) for line in code_lines), default=0)
            if widest > THRESHOLDS["code_line_chars_warn"]:
                report.findings.append(Finding("warn", block.line, f"code block has a {widest}-character line (aim <= {THRESHOLDS['code_line_chars_warn']}); it wraps in print, so break it or move the note below"))
            constructs = sorted(set(LANGUAGE_SPECIFIC_CODE.findall(block.text)))
            if constructs:
                report.findings.append(Finding("warn", block.line, "code block uses language-specific constructs (" + ", ".join(c.strip() for c in constructs) + "); prefer pseudocode or a field list"))

    flush_run(at_end=True)

    report.paragraphs = len(paragraph_lengths)
    if paragraph_lengths:
        report.paragraph_words_mean = round(statistics.mean(paragraph_lengths), 1)
        report.paragraph_words_p90 = _percentile(paragraph_lengths, 0.9)
        report.paragraph_words_max = max(paragraph_lengths)
    if sentence_lengths:
        report.sentence_words_mean = round(statistics.mean(sentence_lengths), 1)
        long_share = sum(1 for n in sentence_lengths if n > THRESHOLDS["long_sentence_words"]) / len(sentence_lengths)
        report.long_sentence_share = round(long_share, 3)
        if report.sentence_words_mean > THRESHOLDS["sentence_words_mean_warn"]:
            report.findings.append(Finding("warn", 1, f"mean sentence length {report.sentence_words_mean} words (aim <= {THRESHOLDS['sentence_words_mean_warn']})"))
        if long_share > THRESHOLDS["long_sentence_share_warn"]:
            report.findings.append(Finding("warn", 1, f"{long_share:.0%} of sentences exceed {THRESHOLDS['long_sentence_words']} words"))
    if report.prose_words:
        report.caveat_density = round(100.0 * caveats / report.prose_words, 2)
        report.anchors_per_1000_words = round(1000.0 * anchors / report.prose_words, 1)
        if report.caveat_density > THRESHOLDS["caveat_density_warn"]:
            report.findings.append(Finding("warn", 1, f"caveat/negation density {report.caveat_density} per 100 words (aim <= {THRESHOLDS['caveat_density_warn']}); state what the design does, then its one limit"))
    if report.filler_hits:
        report.findings.append(Finding("warn", 1, f"{report.filler_hits} narration/filler phrases (see FILLER_PHRASES)"))
    needed = THRESHOLDS["min_figures"] if min_figures is None else min_figures
    if report.figures < needed:
        report.findings.append(Finding("error", 1, f"{report.figures} figures; a system-design chapter needs at least {needed}"))
    return report


def lint_file(path: Path, *, min_figures: Optional[int] = None) -> Report:
    return lint_text(path.read_text(encoding="utf-8"), str(path), min_figures=min_figures)


UNSTARTED_STATUSES = {"normalized", "needs_clarification"}


def _is_unstarted(question: Path) -> bool:
    """A freshly ingested package holds a scaffold, not a chapter, so it is not linted yet."""

    metadata = question.parent / "metadata.yaml"
    if not metadata.is_file():
        return False
    try:
        status = json.loads(metadata.read_text(encoding="utf-8")).get("status")
    except (OSError, ValueError):
        return False
    return status in UNSTARTED_STATUSES


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="print machine-readable summaries")
    parser.add_argument("--min-figures", type=int, default=None)
    parser.add_argument("--quiet", action="store_true", help="print summaries only")
    parser.add_argument(
        "--skip-unstarted",
        action="store_true",
        help="skip packages still at intake (status normalized or needs_clarification)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    files = list(args.files)
    if args.skip_unstarted:
        files = [path for path in files if not _is_unstarted(path)]
    reports = [lint_file(path, min_figures=args.min_figures) for path in files]
    if args.json:
        print(json.dumps([report.summary() for report in reports], indent=2))
    else:
        for report in reports:
            s = report.summary()
            print(
                f"{report.path}: {s['prose_words']} prose words, {s['paragraphs']} paragraphs "
                f"(mean {s['paragraph_words_mean']}, p90 {s['paragraph_words_p90']}, max {s['paragraph_words_max']}), "
                f"max prose run {s['max_prose_run']}, sentence mean {s['sentence_words_mean']}, "
                f"caveats/100w {s['caveat_density']}, figures {s['figures']}, tables {s['tables']}, "
                f"lists {s['lists']}, callouts {s['callouts']} -> {report.errors} errors, {report.warnings} warnings"
            )
            if not args.quiet:
                for finding in report.findings:
                    print("  " + finding.render())
    return 1 if any(report.errors for report in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
