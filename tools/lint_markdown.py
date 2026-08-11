"""Run lightweight dependency-free Markdown integrity checks."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, Optional

from tools.content import ROOT


EXCLUDED_PARTS = frozenset(
    {".git", ".venv", "build", "dist", "generated", "release1", "tmp", "human_example"}
)
BAD_HEADING = re.compile(r"^#{1,6}[^ #]\S*")


def discover_markdown(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if not any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts)
    )


def lint_file(path: Path) -> list[str]:
    data = path.read_bytes()
    issues: list[str] = []
    if b"\x00" in data:
        issues.append("contains a NUL byte")
    if data and not data.endswith(b"\n"):
        issues.append("must end with a newline")
    text = data.decode("utf-8")
    fences = 0
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("```"):
            fences += 1
            in_fence = not in_fence
            continue
        if not in_fence and BAD_HEADING.match(line):
            issues.append(f"line {number}: heading marker must be followed by a space")
    if fences % 2:
        issues.append("contains an unclosed fenced code block")
    return issues


def lint_repository(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    issues: list[str] = []
    for path in discover_markdown(root):
        try:
            file_issues = lint_file(path)
        except UnicodeDecodeError as exc:
            file_issues = [f"is not valid UTF-8: {exc}"]
        issues.extend(
            f"{path.relative_to(root)}: {message}" for message in file_issues
        )
    return issues


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(list(argv) if argv is not None else None)
    issues = lint_repository(args.root)
    if issues:
        print(f"Markdown lint failed with {len(issues)} issue(s):")
        for issue in issues:
            print(f"- {issue}")
        return 1
    count = len(discover_markdown(args.root.resolve()))
    print(f"Markdown lint passed: {count} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
