"""Pick up interview questions dropped into ``inbox/`` as Markdown files.

Layout (the folder decides the question type)::

    inbox/system-design/<anything>.md
    inbox/coding/<anything>.md
    inbox/fundamentals/<anything>.md

One question per file. The whole file is the prompt unless it uses the
optional sections below; see ``templates/system-design/inbox-question.md``::

    ---
    title: Design a Distributed Task Scheduler     # optional
    id: sd-task-scheduler                           # optional
    confidentiality: public                         # optional
    ---

    ## Prompt
    The question exactly as it was asked.

    ## Notes
    Interpretation, emphasis, or direction for the author. Saved to
    expert-notes.md, never shown as part of the prompt.

Processed files move to ``inbox/processed/`` so they are never picked up
twice. The original file is also archived in the package's ``source/``.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

INBOX_TYPE_FOLDERS: Dict[str, str] = {
    "system-design": "system-design",
    "coding": "coding",
    "fundamentals": "fundamentals",
}
PROCESSED_DIR = "processed"
FRONT_MATTER_KEYS = {"title", "id", "confidentiality", "company_removed", "difficulty"}
CONFIDENTIALITY_VALUES = {"public", "sanitized_real_interview", "private_reference"}
PROMPT_HEADINGS = {"prompt", "question", "the question"}
NOTES_HEADINGS = {
    "notes",
    "notes for the author",
    "author notes",
    "expert notes",
    "editorial notes",
    "guidance",
}
HEADING = re.compile(r"^#{1,3}\s+(.+?)\s*$")


class InboxError(ValueError):
    """Raised when an inbox file cannot be turned into a question."""


@dataclass
class InboxItem:
    path: Path
    question_kind: str
    prompt: str
    notes: str = ""
    options: Dict[str, str] = field(default_factory=dict)

    @property
    def title(self) -> Optional[str]:
        return self.options.get("title") or None

    @property
    def question_id(self) -> Optional[str]:
        return self.options.get("id") or None

    @property
    def confidentiality(self) -> str:
        return self.options.get("confidentiality", "public")

    @property
    def company_removed(self) -> bool:
        return self.options.get("company_removed", "").casefold() in {"true", "yes", "1"}

    @property
    def needs_prompt_only_copy(self) -> bool:
        """True when the file holds more than the bare prompt."""

        return bool(self.notes or self.options) or self.path.read_text(
            encoding="utf-8"
        ).strip() != self.prompt


def _split_front_matter(text: str) -> tuple[Dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            break
    else:
        raise InboxError("front matter starts with '---' but never closes")
    options: Dict[str, str] = {}
    for raw in lines[1:end]:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise InboxError(f"front matter line is not 'key: value': {raw!r}")
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.casefold().replace("-", "_")
        if key not in FRONT_MATTER_KEYS:
            raise InboxError(
                f"unknown front matter key {key!r}; expected one of {sorted(FRONT_MATTER_KEYS)}"
            )
        options[key] = value.strip("\"'")
    if options.get("confidentiality") and options["confidentiality"] not in CONFIDENTIALITY_VALUES:
        raise InboxError(
            f"confidentiality must be one of {sorted(CONFIDENTIALITY_VALUES)}"
        )
    return options, "\n".join(lines[end + 1:])


def _split_sections(body: str) -> tuple[str, str]:
    """Return (prompt, notes). Without section headings the body is the prompt."""

    prompt_lines: List[str] = []
    notes_lines: List[str] = []
    target = prompt_lines
    saw_prompt_heading = False
    for line in body.splitlines():
        match = HEADING.match(line.strip())
        if match:
            name = match.group(1).strip().rstrip(":").casefold()
            if name in PROMPT_HEADINGS:
                target = prompt_lines
                saw_prompt_heading = True
                continue
            if name in NOTES_HEADINGS:
                target = notes_lines
                continue
        target.append(line)
    prompt = "\n".join(prompt_lines).strip()
    if saw_prompt_heading:
        prompt = re.sub(r"^\s*>\s?", "", prompt, flags=re.MULTILINE).strip()
    return prompt, "\n".join(notes_lines).strip()


def parse_inbox_file(path: Path, question_kind: str) -> InboxItem:
    text = path.read_text(encoding="utf-8")
    options, body = _split_front_matter(text)
    prompt, notes = _split_sections(body)
    if not prompt:
        raise InboxError(f"{path.name} has no prompt text")
    return InboxItem(path=path, question_kind=question_kind, prompt=prompt, notes=notes, options=options)


def pending_items(root: Path) -> List[InboxItem]:
    """Every unprocessed inbox file, oldest first."""

    inbox = root / "inbox"
    found: List[tuple[float, str, Path, str]] = []
    for folder, kind in INBOX_TYPE_FOLDERS.items():
        directory = inbox / folder
        if not directory.is_dir():
            continue
        for path in directory.glob("*.md"):
            if path.name.casefold() == "readme.md" or path.name.startswith((".", "_")):
                continue
            found.append((path.stat().st_mtime, path.name, path, kind))
    found.sort()
    return [parse_inbox_file(path, kind) for _, _, path, kind in found]


def write_prompt_only_copy(item: InboxItem, directory: Path) -> Path:
    """The prompt alone, under the original file name, for normalization."""

    target = directory / item.path.name
    target.write_text(item.prompt.rstrip() + "\n", encoding="utf-8")
    return target


def archive_original(item: InboxItem, package: Path) -> str:
    """Copy the full inbox file into the package's source/ directory."""

    source_dir = package / "source"
    source_dir.mkdir(exist_ok=True)
    name = f"inbox-{item.path.name}"
    shutil.copy2(item.path, source_dir / name)
    return f"source/{name}"


def mark_processed(root: Path, item: InboxItem, question_id: str) -> Path:
    processed = root / "inbox" / PROCESSED_DIR
    processed.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    target = processed / f"{stamp}-{question_id}-{item.path.name}"
    shutil.move(str(item.path), target)
    return target


def describe(item: InboxItem, root: Path) -> str:
    relative = item.path.relative_to(root) if item.path.is_relative_to(root) else item.path
    first_line = item.prompt.splitlines()[0][:90]
    parts = [f"{relative}  [{item.question_kind}]", f"  prompt: {first_line}"]
    if item.title:
        parts.append(f"  title:  {item.title}")
    if item.question_id:
        parts.append(f"  id:     {item.question_id}")
    if item.notes:
        parts.append(f"  notes:  {len(item.notes.split())} words → expert-notes.md")
    return "\n".join(parts)


def temporary_directory() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="contentctl-inbox-")
