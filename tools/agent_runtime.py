"""Programmatic Codex execution boundary for the content workflow."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, Sequence


@dataclass(frozen=True)
class AgentResult:
    thread_id: str
    final_output: str
    events: tuple[dict[str, object], ...]


class AgentRunner(Protocol):
    def run(
        self,
        prompt: str,
        *,
        root: Path,
        sandbox: str,
        images: Sequence[Path] = (),
        output_schema: Optional[Path] = None,
    ) -> AgentResult:
        """Start a fresh agent thread."""

    def resume(
        self,
        thread_id: str,
        prompt: str,
        *,
        root: Path,
        images: Sequence[Path] = (),
        output_schema: Optional[Path] = None,
    ) -> AgentResult:
        """Resume an existing agent thread."""


def _codex_binary() -> str:
    configured = os.environ.get("CODEX_BIN")
    if configured:
        return configured
    discovered = shutil.which("codex")
    if discovered:
        return discovered
    app_binary = Path("/Applications/Codex.app/Contents/Resources/codex")
    if app_binary.is_file():
        return str(app_binary)
    raise RuntimeError(
        "Codex CLI was not found; install it or set CODEX_BIN to its absolute path"
    )


def _consume(command: list[str], *, root: Path) -> AgentResult:
    process = subprocess.Popen(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        encoding="utf-8",
    )
    assert process.stdout is not None
    events: list[dict[str, object]] = []
    thread_id = ""
    final_output = ""
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        if event.get("type") == "thread.started":
            thread_id = str(event.get("thread_id", ""))
        if event.get("type") == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                final_output = str(item.get("text", final_output))
    exit_code = process.wait()
    if exit_code:
        raise RuntimeError(f"Codex exited with status {exit_code}")
    if not final_output:
        raise RuntimeError("Codex completed without a final agent message")
    return AgentResult(thread_id, final_output, tuple(events))


class CodexExecRunner:
    """Run Codex non-interactively with saved local auth or OPENAI_API_KEY."""

    def __init__(self, codex_bin: Optional[str] = None) -> None:
        self.codex_bin = codex_bin or _codex_binary()

    def run(
        self,
        prompt: str,
        *,
        root: Path,
        sandbox: str,
        images: Sequence[Path] = (),
        output_schema: Optional[Path] = None,
    ) -> AgentResult:
        command = [
            self.codex_bin,
            "exec",
            "--json",
            "--color",
            "never",
            "--sandbox",
            sandbox,
            "--cd",
            str(root.resolve()),
        ]
        for image in images:
            command.extend(["--image", str(image.resolve())])
        if output_schema is not None:
            command.extend(["--output-schema", str(output_schema.resolve())])
        command.append(prompt)
        return _consume(command, root=root.resolve())

    def resume(
        self,
        thread_id: str,
        prompt: str,
        *,
        root: Path,
        images: Sequence[Path] = (),
        output_schema: Optional[Path] = None,
    ) -> AgentResult:
        if not thread_id:
            raise ValueError("cannot resume an empty Codex thread ID")
        command = [
            self.codex_bin,
            "exec",
            "--color",
            "never",
            "--sandbox",
            "workspace-write",
            "--cd",
            str(root.resolve()),
            "resume",
            "--json",
        ]
        for image in images:
            command.extend(["--image", str(image.resolve())])
        if output_schema is not None:
            command.extend(["--output-schema", str(output_schema.resolve())])
        command.extend([thread_id, prompt])
        return _consume(command, root=root.resolve())
