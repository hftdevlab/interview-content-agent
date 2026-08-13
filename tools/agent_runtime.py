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


@dataclass(frozen=True)
class CodexFailure:
    """Normalized failure details extracted from a Codex JSON event."""

    code: str
    message: str
    status: Optional[int] = None


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


def _failure_from_message(raw: object) -> CodexFailure:
    """Normalize nested Codex/API error payloads into a stable user-facing shape."""

    value: object = raw
    if isinstance(value, dict) and "message" in value:
        value = value["message"]
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return CodexFailure("agent_failure", value.strip() or "unknown Codex failure")
        value = decoded
    if not isinstance(value, dict):
        return CodexFailure("agent_failure", str(value) or "unknown Codex failure")

    status = value.get("status")
    error = value.get("error", value)
    if isinstance(error, dict):
        code = str(error.get("code") or error.get("type") or "agent_failure")
        message = str(error.get("message") or value.get("message") or "unknown Codex failure")
    else:
        code = "agent_failure"
        message = str(error)
    return CodexFailure(
        code=code,
        message=" ".join(message.split()),
        status=status if isinstance(status, int) else None,
    )


def _failure_text(failure: CodexFailure) -> str:
    status = f" (HTTP {failure.status})" if failure.status is not None else ""
    guidance = ""
    if failure.code == "invalid_json_schema":
        guidance = (
            " The agent response schema is incompatible with the current Codex structured-"
            "output subset; this is a tooling error, not a content error."
        )
    message = failure.message.rstrip(".")
    return f"Codex agent failed [{failure.code}]{status}: {message}.{guidance}"


def _process_failure(exit_code: int, stderr_lines: Sequence[str]) -> str:
    cache_error = next(
        (line for line in stderr_lines if _is_recoverable_diagnostic(line)),
        "",
    )
    if cache_error:
        return (
            "Codex startup failed [incompatible_models_cache]: the local Codex models cache "
            "does not match this CLI version (missing base_instructions). Restart or update "
            "Codex so it refreshes ~/.codex/models_cache.json, then rerun contentctl continue."
        )
    meaningful = [line.strip() for line in stderr_lines if line.strip()]
    detail = " | ".join(meaningful[-8:])
    suffix = f" Stderr: {detail}" if detail else " No stderr detail was emitted."
    return f"Codex process failed [process_exit]: exit status {exit_code}.{suffix}"


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
    failure: Optional[CodexFailure] = None
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
        if event.get("type") == "turn.failed":
            failure = _failure_from_message(event.get("error", event))
        elif event.get("type") == "error" and failure is None:
            failure = _failure_from_message(event.get("message", event))
    exit_code = process.wait()
    stderr_thread.join()
    if failure is not None:
        raise RuntimeError(_failure_text(failure))
    if exit_code:
        raise RuntimeError(_process_failure(exit_code, stderr_lines))
    if not final_output:
        raise RuntimeError(
            "Codex agent failed [missing_final_message]: the process exited successfully "
            "without a final agent message. Inspect the preceding Codex events and retry."
        )
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
