"""Programmatic Codex execution boundary for the content workflow."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Optional, Protocol, Sequence


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


RECOVERABLE_DIAGNOSTICS = (
    "codex_models_manager::cache: failed to load models cache: "
    "missing field `base_instructions`",
)


def _is_recoverable_diagnostic(line: str) -> bool:
    return any(marker in line for marker in RECOVERABLE_DIAGNOSTICS)


def _forward_stderr(stream: IO[str], captured: list[str]) -> None:
    for line in stream:
        captured.append(line.rstrip())
        if not _is_recoverable_diagnostic(line):
            sys.stderr.write(line)
            sys.stderr.flush()


def _progress_summary(message: str) -> str:
    try:
        parsed = json.loads(message)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    return str(parsed.get("summary", "")).strip()


def _consume(command: list[str], *, root: Path) -> AgentResult:
    process = subprocess.Popen(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert process.stdout is not None
    assert process.stderr is not None
    stderr_lines: list[str] = []
    stderr_thread = threading.Thread(
        target=_forward_stderr,
        args=(process.stderr, stderr_lines),
        daemon=True,
    )
    stderr_thread.start()
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
                summary = _progress_summary(final_output)
                if summary:
                    print(f"[contentctl] {summary}", file=sys.stderr, flush=True)
    exit_code = process.wait()
    stderr_thread.join()
    if exit_code:
        tail = "\n".join(stderr_lines[-20:])
        detail = f"\n{tail}" if tail else ""
        raise RuntimeError(f"Codex exited with status {exit_code}{detail}")
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
