"""Human-in-the-loop CLI orchestrator for interview content production."""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from tools.agent_runtime import AgentResult, AgentRunner, CodexExecRunner
from tools.content import ROOT, load_data
from tools.deduplicate import duplicate_candidates, report_dict
from tools.editorial_memory import (
    EditorialMemoryError,
    active_memory_entries,
    approve_memory_candidate,
    list_memory_candidates,
    memory_prompt,
    record_memory_candidates,
    reject_memory_candidate,
)
from tools.ingest import IMAGE_SUFFIXES, TYPE_CONFIG, ingest_question
from tools.validate import validate_repository


TYPE_ALIASES = {
    "coding": "coding",
    "design": "system-design",
    "system-design": "system-design",
    "fundamentals": "fundamentals",
    "general": "fundamentals",
    "general-system": "fundamentals",
    "systems": "fundamentals",
}
SKILL_BY_METADATA_TYPE = {
    "system_design": "$draft-system-design",
    "coding": "$draft-coding-question",
    "fundamentals": "$draft-fundamentals-question",
}
REVIEW_FLAGS_FALSE = {
    "agent_reviewed": False,
    "human_reviewed": False,
    "technical_accuracy_reviewed": False,
    "interview_realism_reviewed": False,
}


class WorkflowError(ValueError):
    """Raised when a requested lifecycle transition is not allowed."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _package(root: Path, question_id: str) -> Path:
    matches = list((root / "content").glob(f"*/{question_id}/metadata.yaml"))
    if len(matches) != 1:
        raise WorkflowError(f"question ID {question_id!r} does not identify one package")
    return matches[0].parent


def _load_workflow(package: Path) -> dict[str, object]:
    path = package / "workflow.yaml"
    if not path.is_file():
        raise WorkflowError(f"workflow state is missing: {path}")
    value = load_data(path)
    if not isinstance(value, dict):
        raise WorkflowError(f"workflow state must be an object: {path}")
    return dict(value)


def _event(
    workflow: dict[str, object],
    event_type: str,
    *,
    actor: str,
    detail: object,
) -> None:
    events = list(workflow.get("events", []))
    events.append(
        {
            "at": _now(),
            "actor": actor,
            "type": event_type,
            "detail": detail,
        }
    )
    workflow["events"] = events
    workflow["updated_at"] = _now()


def _save_workflow(package: Path, workflow: Mapping[str, object]) -> None:
    _write_json(package / "workflow.yaml", workflow)


def _sync_status(
    package: Path,
    status: str,
    flags: Mapping[str, bool],
    *,
    review_note: Optional[str] = None,
) -> None:
    metadata_path = package / "metadata.yaml"
    review_path = package / "review.yaml"
    metadata = dict(load_data(metadata_path))
    review = dict(load_data(review_path))
    resolved_flags = dict(flags)
    metadata["status"] = status
    metadata["review"] = resolved_flags
    metadata["last_updated"] = dt.date.today().isoformat()
    review["checks"] = resolved_flags
    if review_note:
        notes = list(review.get("review_notes", []))
        notes.append(review_note)
        review["review_notes"] = notes
    _write_json(metadata_path, metadata)
    _write_json(review_path, review)


def _suggest_title(prompt: str, source: Path, explicit: Optional[str]) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    first = next((line.strip("# ") for line in prompt.splitlines() if line.strip()), "")
    return (first or source.stem.replace("-", " ").replace("_", " ")).strip()[:160]


def _resolve_kind(value: str) -> str:
    try:
        return TYPE_ALIASES[value]
    except KeyError as exc:
        choices = ", ".join(sorted(TYPE_ALIASES))
        raise WorkflowError(f"unknown question type {value!r}; choose one of: {choices}") from exc


def _parse_agent_json(result: AgentResult, stage: str) -> dict[str, object]:
    try:
        value = json.loads(result.final_output)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{stage} agent returned invalid structured output") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{stage} agent output must be an object")
    return dict(value)


def _transcribe_image(
    runner: AgentRunner,
    *,
    root: Path,
    image: Path,
) -> tuple[str, list[dict[str, object]], list[str], str]:
    prompt = (
        "Transcribe the attached interview-question image faithfully. Preserve code, "
        "constraints, examples, and formatting where meaningful. Do not complete or "
        "solve the question. Mark unreadable text as uncertainty and ask only questions "
        "whose answers are required to recover the core contract."
    )
    result = runner.run(
        prompt,
        root=root,
        sandbox="read-only",
        images=[image],
        output_schema=root / "schemas/image-transcription-output.schema.json",
    )
    parsed = _parse_agent_json(result, "transcription")
    transcription = str(parsed.get("transcription", "")).strip()
    if not transcription:
        raise WorkflowError("image transcription agent returned empty text")
    uncertainties = [
        dict(item)
        for item in parsed.get("uncertainties", [])
        if isinstance(item, dict)
    ]
    questions = [
        str(item) for item in parsed.get("clarification_questions", []) if str(item)
    ]
    return transcription, uncertainties, questions, result.thread_id


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=check,
        capture_output=True,
        text=True,
    )


def _start_question_branch(root: Path, question_id: str) -> str:
    branch = f"question/{question_id}"
    current = _git(root, "branch", "--show-current").stdout.strip()
    if current == branch:
        return branch
    _git(root, "switch", "-c", branch)
    return branch


def submit_question(
    *,
    root: Path,
    question_kind: str,
    input_path: Path,
    runner: Optional[AgentRunner],
    transcription_path: Optional[Path] = None,
    question_id: Optional[str] = None,
    title: Optional[str] = None,
    expert_note: Optional[str] = None,
    confidentiality: str = "public",
    company_removed: bool = False,
    create_branch: bool = True,
    run_agent: bool = True,
) -> Path:
    """Archive a submission, screen duplicates, and optionally run the agent pipeline."""

    root = root.resolve()
    input_path = input_path.resolve()
    resolved_kind = _resolve_kind(question_kind)
    if question_id:
        matches = list((root / "content").glob(f"*/{question_id}/metadata.yaml"))
        if matches:
            if (matches[0].parent / "workflow.yaml").is_file():
                raise WorkflowError(
                    f"question workflow {question_id!r} already exists; "
                    f"run 'contentctl continue --id {question_id}'"
                )
            raise WorkflowError(f"question ID {question_id!r} already exists")
    is_image = input_path.suffix.casefold() in IMAGE_SUFFIXES
    transcription: Optional[str] = None
    uncertainties: list[dict[str, object]] = []
    clarification_questions: list[str] = []
    transcription_thread = ""

    if create_branch:
        dirty = _git(root, "status", "--porcelain").stdout.strip()
        if dirty:
            raise WorkflowError(
                "submission requires a clean Git worktree before creating a question branch"
            )

    if transcription_path is not None:
        transcription_path = transcription_path.resolve()
        transcription = transcription_path.read_text(encoding="utf-8")
    elif is_image and runner is not None and run_agent:
        try:
            (
                transcription,
                uncertainties,
                clarification_questions,
                transcription_thread,
            ) = _transcribe_image(runner, root=root, image=input_path)
        except (OSError, RuntimeError, WorkflowError) as exc:
            clarification_questions.append(f"Image transcription failed: {exc}")

    prompt = transcription or ("" if is_image else input_path.read_text(encoding="utf-8"))
    resolved_title = _suggest_title(prompt, input_path, title)
    metadata_type = str(TYPE_CONFIG[resolved_kind]["metadata_type"])
    candidates = duplicate_candidates(
        root=root,
        title=resolved_title,
        prompt=prompt,
        question_type=metadata_type,
        question_id=question_id,
    )
    deduplication = report_dict(
        title=resolved_title,
        question_type=metadata_type,
        candidates=candidates,
    )

    temporary: Optional[tempfile.TemporaryDirectory[str]] = None
    generated_transcription: Optional[Path] = None
    try:
        effective_transcription = transcription_path
        if transcription is not None and transcription_path is None:
            temporary = tempfile.TemporaryDirectory()
            generated_transcription = Path(temporary.name) / "transcription.txt"
            generated_transcription.write_text(transcription.rstrip() + "\n", encoding="utf-8")
            effective_transcription = generated_transcription
        package = ingest_question(
            root=root,
            question_kind=resolved_kind,
            input_path=input_path,
            transcription_path=effective_transcription,
            question_id=question_id,
            title=resolved_title,
            confidentiality=confidentiality,
            company_removed=company_removed,
            expert_note=expert_note,
        )
    finally:
        if temporary is not None:
            temporary.cleanup()

    _write_json(package / "deduplication.yaml", deduplication)
    if is_image:
        _write_json(
            package / "transcription-review.yaml",
            {
                "schema_version": 1,
                "uncertainties": uncertainties,
                "clarification_questions": clarification_questions,
                "human_confirmed": False,
            },
        )

    branch = _start_question_branch(root, package.name) if create_branch else ""
    blocking_uncertainty = any(bool(item.get("blocking")) for item in uncertainties)
    pending = list(clarification_questions)
    if deduplication["blocking_candidates"]:
        pending.append(
            "Confirm whether this is distinct from: "
            + ", ".join(str(item) for item in deduplication["blocking_candidates"])
        )
    if is_image and transcription is None:
        pending.append("Provide or confirm a readable transcription of the image.")
    if blocking_uncertainty and not clarification_questions:
        pending.append("Confirm the blocking transcription uncertainties.")

    workflow: dict[str, object] = {
        "schema_version": 1,
        "run_id": str(uuid.uuid4()),
        "question_id": package.name,
        "question_type": metadata_type,
        "state": "needs_clarification" if pending else "normalized",
        "branch": branch,
        "agent_threads": {
            "transcription": transcription_thread,
            "draft": "",
            "review": "",
        },
        "attempts": {"draft": 0, "review": 0},
        "pending_clarifications": pending,
        "created_at": _now(),
        "updated_at": _now(),
        "events": [],
    }
    _event(
        workflow,
        "submission_archived",
        actor="human",
        detail={"input": input_path.name, "question_type": metadata_type},
    )
    if candidates:
        _event(
            workflow,
            "duplicate_candidates_found",
            actor="system",
            detail=[item.question_id for item in candidates],
        )
    _save_workflow(package, workflow)

    if pending:
        _sync_status(
            package,
            "needs_clarification",
            REVIEW_FLAGS_FALSE,
            review_note="Automation paused for clarification or duplicate review.",
        )
    elif run_agent:
        if runner is None:
            raise WorkflowError("agent execution was requested without an agent runner")
        continue_question(root=root, question_id=package.name, runner=runner)

    issues = validate_repository(root)
    if issues:
        rendered = "\n".join(f"- {issue}" for issue in issues)
        raise WorkflowError(f"submission workflow failed validation:\n{rendered}")
    return package


def _draft_prompt(
    root: Path, package: Path, metadata: Mapping[str, object]
) -> str:
    question_id = str(metadata["id"])
    skill = SKILL_BY_METADATA_TYPE[str(metadata["type"])]
    practice = (
        " After the content contract is settled, use $build-practice-question to "
        "create and fully tailor the runnable package; the generic scaffold is not a final solution."
        if metadata["type"] == "coding"
        else " Add a runnable experiment only when it tests a material claim."
    )
    editorial_guidance = memory_prompt(root, str(metadata["type"]))
    return (
        f"Use {skill} to draft the normalized question {question_id}. Also use "
        "$link-interview-foundations where prerequisites are already taught. Read the "
        "package source, expert notes, workflow.yaml, and deduplication.yaml. Keep the core "
        "idea while enriching incomplete wording to realistic interview standard. Do not "
        "invent a missing constraint that changes the problem; return needs_clarification "
        "when that decision requires the human. Generate the tested skills, natural reasoning, "
        "primary solution, concise improvements, pitfalls, realistic follow-ups, and evaluation "
        f"criteria according to the repository rules.{practice} This run is controlled by "
        "contentctl: never edit workflow.yaml; keep metadata status draft and every review flag "
        "false. The controller owns lifecycle transitions, full PDF builds, and repository-wide "
        "gates. Run only targeted package validation and question-specific practice tests. "
        "Never approve or publish.\n\n"
        f"Editorial memory:\n{editorial_guidance}\n\n"
        "This is an initial draft, not a response to new human feedback, so return an empty "
        "memory_candidates array. In the final structured response, report ready only when "
        "all required source edits and tests are complete."
    )


def _feedback_revision_prompt(
    root: Path, package: Path, metadata: Mapping[str, object]
) -> str:
    editorial_guidance = memory_prompt(root, str(metadata["type"]))
    return (
        f"Revise {metadata['id']} using only the newest human feedback appended to "
        "expert-notes.md and its matching file under feedback/. Preserve accepted material "
        "unless the feedback requires it to change, and reconcile the linked practice package. "
        "This is a focused contentctl revision: do not edit workflow.yaml; keep metadata status "
        "draft and every review flag false. Do not rebuild or visually inspect PDFs and do not "
        "run repository-wide gates; the controller will do those once. Run targeted package "
        "validation and only the affected question-specific practice tests. Never approve or "
        "publish.\n\n"
        f"Editorial memory:\n{editorial_guidance}\n\n"
        "In memory_candidates, propose zero to three concise lessons only when the newest "
        "human feedback contains a rule that should improve other questions. Generalize the "
        "lesson: exclude this question's answer facts, company details, and project-specific "
        "instructions. Return an empty array for question-specific feedback. Candidates are "
        "only proposals for later human approval; do not edit editorial-memory.yaml or "
        "memory-candidates.yaml. Return the required structured stage result."
    )


def _review_prompt(
    root: Path, package: Path, metadata: Mapping[str, object]
) -> str:
    editorial_guidance = memory_prompt(root, str(metadata["type"]))
    return (
        f"Use $review-question to independently review {metadata['id']}. Do not edit any files. "
        "Read the preserved source, expert notes, deduplication report, question, metadata, "
        "and linked practice code. Judge source fidelity, interview realism, reasoning flow, "
        "technical correctness, page-budget discipline, follow-up quality, and runnable-code "
        "consistency. A coding question cannot pass without a question-specific runnable package. "
        f"Also verify applicable approved guidance below:\n{editorial_guidance}\n"
        "Return blocking or important issues precisely; suggestions alone do not fail the review."
    )


def _agent_threads(workflow: Mapping[str, object]) -> dict[str, str]:
    value = workflow.get("agent_threads", {})
    return {str(key): str(item) for key, item in value.items()} if isinstance(value, dict) else {}


def _attempts(workflow: Mapping[str, object]) -> dict[str, int]:
    value = workflow.get("attempts", {})
    return {str(key): int(item) for key, item in value.items()} if isinstance(value, dict) else {}


def _record_agent_result(
    package: Path,
    workflow: dict[str, object],
    *,
    stage: str,
    result: AgentResult,
    parsed: Mapping[str, object],
) -> None:
    threads = _agent_threads(workflow)
    threads[stage] = result.thread_id
    workflow["agent_threads"] = threads
    attempts = _attempts(workflow)
    attempts[stage] = attempts.get(stage, 0) + 1
    workflow["attempts"] = attempts
    _event(
        workflow,
        f"agent_{stage}_completed",
        actor="agent",
        detail=dict(parsed),
    )
    _save_workflow(package, workflow)


def _run_draft(
    *,
    root: Path,
    package: Path,
    metadata: Mapping[str, object],
    workflow: dict[str, object],
    runner: AgentRunner,
    revision_message: Optional[str] = None,
) -> dict[str, object]:
    schema = root / "schemas/agent-stage-output.schema.json"
    threads = _agent_threads(workflow)
    thread_id = threads.get("draft", "")
    prompt = revision_message or _draft_prompt(root, package, metadata)
    if thread_id:
        result = runner.resume(
            thread_id,
            prompt,
            root=root,
            output_schema=schema,
        )
    else:
        result = runner.run(
            prompt,
            root=root,
            sandbox="workspace-write",
            output_schema=schema,
        )
    parsed = _parse_agent_json(result, "draft")
    _record_agent_result(
        package, workflow, stage="draft", result=result, parsed=parsed
    )
    return parsed


def _run_review(
    *,
    root: Path,
    package: Path,
    metadata: Mapping[str, object],
    workflow: dict[str, object],
    runner: AgentRunner,
) -> dict[str, object]:
    result = runner.run(
        _review_prompt(root, package, metadata),
        root=root,
        sandbox="read-only",
        output_schema=root / "schemas/agent-review-output.schema.json",
    )
    parsed = _parse_agent_json(result, "review")
    _record_agent_result(
        package, workflow, stage="review", result=result, parsed=parsed
    )
    _write_json(package / "agent-review.yaml", parsed)
    return parsed


def _run_gate(root: Path, command: Sequence[str], label: str) -> None:
    print(f"[contentctl] {label}...", file=sys.stderr, flush=True)
    result = subprocess.run(
        list(command),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        output = "\n".join(
            line for line in (result.stdout + "\n" + result.stderr).splitlines() if line
        )
        tail = "\n".join(output.splitlines()[-40:])
        raise WorkflowError(f"{label} failed:\n{tail}")


def _run_deterministic_gates(root: Path, metadata: Mapping[str, object]) -> None:
    """Run expensive gates once under controller ownership, not inside agent turns."""

    if not (root / "Makefile").is_file():
        return
    if metadata.get("type") == "coding" or isinstance(
        metadata.get("runnable_experiment"), dict
    ):
        _run_gate(root, ("make", "practice-test"), "C++ practice gate")
    _run_gate(root, ("make", "pdf-preview"), "review PDF gate")


def continue_question(
    *,
    root: Path,
    question_id: str,
    runner: AgentRunner,
    max_revision_rounds: int = 1,
) -> Path:
    """Run or resume drafting, deterministic gates, and independent review."""

    root = root.resolve()
    package = _package(root, question_id)
    workflow = _load_workflow(package)
    metadata = dict(load_data(package / "metadata.yaml"))
    if metadata.get("status") in {"approved", "published", "deprecated"}:
        raise WorkflowError(f"cannot run agents for status {metadata.get('status')!r}")
    deduplication = dict(load_data(package / "deduplication.yaml"))
    if deduplication.get("human_decision") == "pending":
        raise WorkflowError("resolve duplicate candidates before continuing")
    if workflow.get("pending_clarifications"):
        raise WorkflowError("resolve pending clarifications before continuing")

    starting_status = str(metadata.get("status", ""))
    is_feedback_revision = starting_status == "changes_requested"
    proposed_memory: list[Mapping[str, object]] = []
    _sync_status(package, "draft", REVIEW_FLAGS_FALSE)
    workflow["state"] = "drafting"
    if starting_status == "changes_requested":
        threads = _agent_threads(workflow)
        previous_thread = threads.get("draft", "")
        threads["draft"] = ""
        workflow["agent_threads"] = threads
        _event(
            workflow,
            "draft_context_rotated",
            actor="system",
            detail={"previous_thread": previous_thread},
        )
    _event(workflow, "draft_started", actor="system", detail={})
    _save_workflow(package, workflow)

    revision_message: Optional[str] = (
        _feedback_revision_prompt(root, package, metadata)
        if is_feedback_revision
        else None
    )
    for round_number in range(max_revision_rounds + 1):
        metadata = dict(load_data(package / "metadata.yaml"))
        draft = _run_draft(
            root=root,
            package=package,
            metadata=metadata,
            workflow=workflow,
            runner=runner,
            revision_message=revision_message,
        )
        # Lifecycle state belongs to the controller. Reassert it after every agent
        # turn so a drafting skill cannot accidentally bypass independent review.
        _sync_status(package, "draft", REVIEW_FLAGS_FALSE)
        workflow["state"] = "drafting"
        _save_workflow(package, workflow)
        outcome = str(draft.get("outcome", "failed"))
        if outcome == "needs_clarification":
            questions = [str(item) for item in draft.get("clarification_questions", [])]
            workflow["pending_clarifications"] = questions
            workflow["state"] = "needs_clarification"
            _sync_status(
                package,
                "needs_clarification",
                REVIEW_FLAGS_FALSE,
                review_note="Drafting agent paused for human clarification.",
            )
            _save_workflow(package, workflow)
            return package
        if outcome != "ready":
            workflow["state"] = "agent_failed"
            _save_workflow(package, workflow)
            raise WorkflowError(f"drafting agent outcome was {outcome!r}")

        if is_feedback_revision:
            current_candidates = draft.get("memory_candidates", [])
            if isinstance(current_candidates, list) and current_candidates:
                proposed_memory = [
                    dict(item) for item in current_candidates if isinstance(item, dict)
                ]

        issues = validate_repository(root)
        if issues:
            revision_message = (
                "Fix these deterministic validation failures without changing the core question:\n"
                + "\n".join(f"- {issue}" for issue in issues)
            )
            if round_number < max_revision_rounds:
                continue
            workflow["state"] = "agent_validation_failed"
            _event(
                workflow,
                "validation_failed",
                actor="system",
                detail=[str(issue) for issue in issues],
            )
            _save_workflow(package, workflow)
            raise WorkflowError(revision_message)

        metadata = dict(load_data(package / "metadata.yaml"))
        if metadata.get("type") == "coding" and not isinstance(
            metadata.get("practice"), dict
        ):
            revision_message = (
                "The coding draft is incomplete: create and tailor the required runnable "
                "practice package, register it with CMake, and run its tests."
            )
            if round_number < max_revision_rounds:
                continue
            workflow["state"] = "agent_validation_failed"
            _save_workflow(package, workflow)
            raise WorkflowError(revision_message)

        try:
            _run_deterministic_gates(root, metadata)
        except WorkflowError as exc:
            revision_message = (
                "Fix this controller-owned deterministic gate failure without changing the "
                f"core question:\n- {exc}"
            )
            if round_number < max_revision_rounds:
                continue
            workflow["state"] = "agent_validation_failed"
            _event(
                workflow,
                "validation_failed",
                actor="system",
                detail=[str(exc)],
            )
            _save_workflow(package, workflow)
            raise

        review = _run_review(
            root=root,
            package=package,
            metadata=metadata,
            workflow=workflow,
            runner=runner,
        )
        blocking = [
            item
            for item in review.get("issues", [])
            if isinstance(item, dict)
            and item.get("severity") in {"blocking", "important"}
        ]
        if bool(review.get("passed")) and not blocking:
            recorded_memory = record_memory_candidates(
                package=package,
                candidates=proposed_memory,
            )
            if recorded_memory:
                _event(
                    workflow,
                    "memory_candidates_proposed",
                    actor="agent",
                    detail=[str(item["id"]) for item in recorded_memory],
                )
            flags = dict(REVIEW_FLAGS_FALSE)
            flags["agent_reviewed"] = True
            _sync_status(
                package,
                "needs_human_review",
                flags,
                review_note="Independent agent review passed; human review is required.",
            )
            workflow["state"] = "needs_human_review"
            _event(
                workflow,
                "human_review_requested",
                actor="system",
                detail={"summary": review.get("summary", "")},
            )
            _save_workflow(package, workflow)
            final_issues = validate_repository(root)
            if final_issues:
                raise WorkflowError(
                    "post-review validation failed:\n"
                    + "\n".join(f"- {issue}" for issue in final_issues)
                )
            return package

        revision_message = (
            "Address the independent review findings below. Preserve source and expert notes, "
            "then rerun applicable tests.\n"
            + json.dumps(blocking or review.get("issues", []), indent=2)
        )
        if round_number >= max_revision_rounds:
            workflow["state"] = "agent_review_failed"
            _event(
                workflow,
                "agent_review_failed",
                actor="agent",
                detail=review,
            )
            _save_workflow(package, workflow)
            return package

    return package


def resolve_duplicate(
    *,
    root: Path,
    question_id: str,
    decision: str,
    reason: str,
) -> Path:
    package = _package(root.resolve(), question_id)
    if decision not in {"distinct", "duplicate"}:
        raise WorkflowError("duplicate decision must be 'distinct' or 'duplicate'")
    if not reason.strip():
        raise WorkflowError("duplicate resolution requires a human reason")
    report = dict(load_data(package / "deduplication.yaml"))
    report["human_decision"] = decision
    report["human_reason"] = reason.strip()
    _write_json(package / "deduplication.yaml", report)
    workflow = _load_workflow(package)
    _event(
        workflow,
        "duplicate_review_resolved",
        actor="human",
        detail={"decision": decision, "reason": reason.strip()},
    )
    pending = [
        item
        for item in workflow.get("pending_clarifications", [])
        if not str(item).startswith("Confirm whether this is distinct from:")
    ]
    workflow["pending_clarifications"] = pending
    if decision == "duplicate":
        workflow["state"] = "rejected_duplicate"
        _sync_status(package, "deprecated", REVIEW_FLAGS_FALSE)
    elif not pending:
        workflow["state"] = "normalized"
        _sync_status(package, "normalized", REVIEW_FLAGS_FALSE)
    _save_workflow(package, workflow)
    return package


def resolve_clarifications(
    *,
    root: Path,
    question_id: str,
    response: str,
    reviewer: str,
) -> Path:
    if not response.strip():
        raise WorkflowError("clarification response must not be empty")
    package = _package(root.resolve(), question_id)
    feedback_dir = package / "feedback"
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = feedback_dir / f"{stamp}-clarification.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Clarification\n\nReviewer: {reviewer}\n\n{response.strip()}\n",
        encoding="utf-8",
    )
    expert_path = package / "expert-notes.md"
    expert_path.write_text(
        expert_path.read_text(encoding="utf-8").rstrip()
        + f"\n\n## Human clarification {stamp}\n\n{response.strip()}\n",
        encoding="utf-8",
    )
    workflow = _load_workflow(package)
    workflow["pending_clarifications"] = []
    workflow["state"] = "normalized"
    _event(
        workflow,
        "clarification_received",
        actor=reviewer,
        detail={"file": str(path.relative_to(package))},
    )
    _save_workflow(package, workflow)
    _sync_status(package, "normalized", REVIEW_FLAGS_FALSE)
    return package


def add_feedback(
    *,
    root: Path,
    question_id: str,
    feedback: str,
    reviewer: str,
    runner: Optional[AgentRunner] = None,
    run_agent: bool = False,
) -> Path:
    if not feedback.strip():
        raise WorkflowError("feedback must not be empty")
    package = _package(root.resolve(), question_id)
    metadata = dict(load_data(package / "metadata.yaml"))
    if metadata.get("status") not in {"needs_human_review", "changes_requested"}:
        raise WorkflowError("feedback is accepted only during human review")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{stamp}-{uuid.uuid4().hex[:8]}.md"
    feedback_path = package / "feedback" / filename
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    feedback_path.write_text(
        f"# Human feedback\n\nReviewer: {reviewer}\n\n{feedback.strip()}\n",
        encoding="utf-8",
    )
    expert_path = package / "expert-notes.md"
    expert_path.write_text(
        expert_path.read_text(encoding="utf-8").rstrip()
        + f"\n\n## Human feedback {stamp}\n\n{feedback.strip()}\n",
        encoding="utf-8",
    )
    _sync_status(
        package,
        "changes_requested",
        REVIEW_FLAGS_FALSE,
        review_note=f"Human feedback recorded in feedback/{filename}.",
    )
    workflow = _load_workflow(package)
    workflow["state"] = "changes_requested"
    _event(
        workflow,
        "human_feedback_received",
        actor=reviewer,
        detail={"file": f"feedback/{filename}"},
    )
    _save_workflow(package, workflow)
    if run_agent:
        if runner is None:
            raise WorkflowError("feedback refinement requires an agent runner")
        continue_question(root=root, question_id=question_id, runner=runner)
    return package


def approve_question(
    *,
    root: Path,
    question_id: str,
    reviewer: str,
    confirmation: str,
) -> Path:
    """Perform the human-only approval transition after an explicit challenge."""

    package = _package(root.resolve(), question_id)
    expected = f"APPROVE {question_id}"
    if confirmation != expected:
        raise WorkflowError(f"approval confirmation must exactly match {expected!r}")
    metadata = dict(load_data(package / "metadata.yaml"))
    workflow = _load_workflow(package)
    if metadata.get("status") != "needs_human_review":
        raise WorkflowError("only content awaiting human review can be approved")
    if workflow.get("state") != "needs_human_review":
        raise WorkflowError("workflow must complete independent review before approval")
    attempts = _attempts(workflow)
    agent_review_path = package / "agent-review.yaml"
    if attempts.get("review", 0) < 1 or not agent_review_path.is_file():
        raise WorkflowError("independent agent review record is required before approval")
    agent_review = load_data(agent_review_path)
    if not isinstance(agent_review, dict) or agent_review.get("passed") is not True:
        raise WorkflowError("independent agent review must pass before approval")
    review_issues = agent_review.get("issues")
    if not isinstance(review_issues, list):
        raise WorkflowError("independent agent review record is malformed")
    blocking = [
        item
        for item in review_issues
        if isinstance(item, dict)
        and item.get("severity") in {"blocking", "important"}
    ]
    if blocking:
        raise WorkflowError("independent agent review still contains unresolved issues")
    if not metadata.get("review", {}).get("agent_reviewed"):
        raise WorkflowError("independent agent review must pass before human approval")
    if metadata.get("type") == "coding" and not isinstance(metadata.get("practice"), dict):
        raise WorkflowError("coding content cannot be approved without runnable practice")

    flags = {key: True for key in REVIEW_FLAGS_FALSE}
    _sync_status(
        package,
        "approved",
        flags,
        review_note=f"Approved interactively by {reviewer} at {_now()}.",
    )
    workflow["state"] = "approved"
    _event(
        workflow,
        "human_approved",
        actor=reviewer,
        detail={"confirmation": expected},
    )
    _save_workflow(package, workflow)
    issues = validate_repository(root.resolve())
    if issues:
        raise WorkflowError(
            "approval failed validation:\n" + "\n".join(f"- {issue}" for issue in issues)
        )
    return package


def question_status(*, root: Path, question_id: str) -> dict[str, object]:
    root = root.resolve()
    package = _package(root, question_id)
    metadata = dict(load_data(package / "metadata.yaml"))
    workflow = _load_workflow(package)
    dedup = dict(load_data(package / "deduplication.yaml"))
    pending_memory = list_memory_candidates(root, question_id=question_id)
    return {
        "question_id": question_id,
        "title": metadata.get("title"),
        "status": metadata.get("status"),
        "workflow_state": workflow.get("state"),
        "branch": workflow.get("branch"),
        "review": metadata.get("review"),
        "pending_clarifications": workflow.get("pending_clarifications", []),
        "duplicate_candidates": dedup.get("candidates", []),
        "duplicate_decision": dedup.get("human_decision"),
        "attempts": workflow.get("attempts", {}),
        "pending_memory_candidates": pending_memory,
        "active_editorial_memory_count": sum(1 for _ in active_memory_entries(root)),
        "next_action": recommended_next_action(
            metadata=metadata,
            workflow=workflow,
            deduplication=dedup,
            pending_memory=pending_memory,
        ),
    }


def recommended_next_action(
    *,
    metadata: Mapping[str, object],
    workflow: Mapping[str, object],
    deduplication: Mapping[str, object],
    pending_memory: Sequence[Mapping[str, object]],
) -> str:
    """Return the safest useful CLI action for the current lifecycle state."""

    question_id = str(metadata.get("id", ""))
    status = str(metadata.get("status", ""))
    if deduplication.get("human_decision") == "pending":
        return f"contentctl resolve-duplicate --id {question_id} ..."
    if workflow.get("pending_clarifications"):
        return f"contentctl clarify --id {question_id} --response ... --continue"
    if status in {"normalized", "draft", "changes_requested", "needs_clarification"}:
        return f"contentctl continue --id {question_id}"
    if status == "needs_human_review":
        return f"contentctl open-pr --id {question_id}"
    if status == "approved" and pending_memory:
        return "contentctl memory-list (then approve or reject each proposed lesson)"
    if status == "approved":
        return f"contentctl open-pr --id {question_id}"
    if status == "published":
        return "No action required; this question is published."
    if status == "deprecated":
        return "No action required; this question is deprecated."
    return "Inspect contentctl status and workflow.yaml before continuing."


def _review_path_allowed(path: str, package: Path, root: Path, question_id: str) -> bool:
    package_relative = package.relative_to(root).as_posix()
    return (
        path in {"practice/CMakeLists.txt", "editorial-memory.yaml"}
        or path.startswith(f"{package_relative}/")
        or path.startswith(f"practice/questions/{question_id}/")
    )


def _changed_paths(root: Path) -> list[str]:
    result = _git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    paths: list[str] = []
    entries = result.stdout.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        if "R" in status or "C" in status:
            if index >= len(entries):
                raise WorkflowError("could not parse renamed Git path")
            path = entries[index]
            index += 1
        paths.append(path)
    return sorted(set(paths))


def open_review_pr(*, root: Path, question_id: str, base: str = "main") -> str:
    """Build, commit, and create or update the question's review PR."""

    root = root.resolve()
    package = _package(root, question_id)
    metadata = dict(load_data(package / "metadata.yaml"))
    workflow = _load_workflow(package)
    if metadata.get("status") not in {"needs_human_review", "approved"}:
        raise WorkflowError(
            "a review PR requires status 'needs_human_review' or 'approved'"
        )
    branch = _git(root, "branch", "--show-current").stdout.strip()
    expected_branch = str(workflow.get("branch", ""))
    if not branch or branch == base:
        raise WorkflowError("review PR must be opened from a question branch")
    if expected_branch and branch != expected_branch:
        raise WorkflowError(
            f"current branch {branch!r} does not match workflow branch {expected_branch!r}"
        )
    _event(
        workflow,
        "draft_pr_prepared",
        actor="system",
        detail={"branch": branch, "base": base},
    )
    _save_workflow(package, workflow)

    _write_json(
        package / "review-bundle.yaml",
        {
            "schema_version": 1,
            "question_id": question_id,
            "generated_at": _now(),
            "status": metadata.get("status"),
            "review": metadata.get("review"),
            "validation_commands": [
                f"python -m tools.validate --id {question_id}",
                "make practice-test" if isinstance(metadata.get("practice"), dict) else "",
                "make pdf-preview",
            ],
            "preview_artifacts": [
                "generated/pdf-preview/system-design-guide.pdf",
                "generated/pdf-preview/coding-interview-guide.pdf",
                "generated/pdf-preview/cpp-systems-guide.pdf",
            ],
        },
    )
    bundle = dict(load_data(package / "review-bundle.yaml"))
    bundle["validation_commands"] = [
        item for item in bundle["validation_commands"] if item
    ]
    _write_json(package / "review-bundle.yaml", bundle)

    issues = validate_repository(root)
    if issues:
        raise WorkflowError(
            "cannot open review PR while validation fails:\n"
            + "\n".join(f"- {issue}" for issue in issues)
        )
    subprocess.run(["make", "pdf-preview"], cwd=root, check=True)
    if isinstance(metadata.get("practice"), dict):
        subprocess.run(["make", "practice-test"], cwd=root, check=True)

    changed = _changed_paths(root)
    disallowed = [
        path
        for path in changed
        if not _review_path_allowed(path, package, root, question_id)
    ]
    if disallowed:
        raise WorkflowError(
            "refusing to include unrelated changes in the question PR: "
            + ", ".join(disallowed)
        )
    if changed:
        _git(root, "add", "--", *changed)
        _git(root, "commit", "-m", f"Update {question_id} review package")
        _git(root, "push", "-u", "origin", branch)
    body = (
        f"## Question review\n\n"
        f"- Question: `{question_id}`\n"
        f"- Type: `{metadata.get('type')}`\n"
        f"- Status: `{metadata.get('status')}`\n"
        f"- Agent review: passed\n"
        f"- Human approval: "
        f"{'complete' if metadata.get('status') == 'approved' else 'required'}\n\n"
        + (
            "Human approval is complete. Confirm CI and merge when ready."
            if metadata.get("status") == "approved"
            else "Review source fidelity, technical accuracy, interview realism, the page "
            "budget, and any runnable practice before approval."
        )
        + " Preview PDFs are produced by CI."
    )
    existing = subprocess.run(
        ["gh", "pr", "view", branch, "--json", "url,isDraft"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if existing.returncode == 0:
        details = json.loads(existing.stdout)
        url = str(details.get("url", "")).strip()
        if not url:
            raise WorkflowError("GitHub returned an existing PR without a URL")
        subprocess.run(
            ["gh", "pr", "edit", url, "--body", body],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        if metadata.get("status") == "approved" and details.get("isDraft") is True:
            subprocess.run(
                ["gh", "pr", "ready", url],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
        return url

    command = ["gh", "pr", "create"]
    if metadata.get("status") != "approved":
        command.append("--draft")
    command.extend(
        [
            "--base", base,
            "--head", branch,
            "--title", f"Review {question_id}: {metadata.get('title')}",
            "--body", body,
        ]
    )
    result = subprocess.run(
        command,
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _default_reviewer(root: Path) -> str:
    result = _git(root, "config", "user.name", check=False)
    return result.stdout.strip() or getpass.getuser()


def _runner() -> CodexExecRunner:
    return CodexExecRunner()


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="contentctl", description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    submit = subparsers.add_parser("submit", help="archive and process a new question")
    submit.add_argument("--type", required=True, dest="question_kind")
    submit.add_argument("--input", required=True, type=Path)
    submit.add_argument("--transcription", type=Path)
    submit.add_argument("--id", dest="question_id")
    submit.add_argument("--title")
    submit.add_argument("--expert-note")
    submit.add_argument(
        "--confidentiality",
        choices=("public", "sanitized_real_interview", "private_reference"),
        default="public",
    )
    submit.add_argument("--company-removed", action="store_true")
    submit.add_argument("--offline", action="store_true")
    submit.add_argument("--no-branch", action="store_true")
    submit.add_argument("--open-pr", action="store_true")

    continue_parser = subparsers.add_parser("continue", help="resume agent processing")
    continue_parser.add_argument("--id", required=True, dest="question_id")
    continue_parser.add_argument("--open-pr", action="store_true")

    status_parser = subparsers.add_parser("status", help="show workflow state")
    status_parser.add_argument("--id", required=True, dest="question_id")

    next_parser = subparsers.add_parser("next", help="show the next recommended action")
    next_parser.add_argument("--id", required=True, dest="question_id")

    duplicate_parser = subparsers.add_parser(
        "resolve-duplicate", help="record the human duplicate decision"
    )
    duplicate_parser.add_argument("--id", required=True, dest="question_id")
    duplicate_parser.add_argument("--decision", choices=("distinct", "duplicate"), required=True)
    duplicate_parser.add_argument("--reason", required=True)

    clarify = subparsers.add_parser("clarify", help="answer blocking intake questions")
    clarify.add_argument("--id", required=True, dest="question_id")
    clarify.add_argument("--response", required=True)
    clarify.add_argument("--reviewer")
    clarify.add_argument("--continue", action="store_true", dest="run_agent")

    feedback_parser = subparsers.add_parser("feedback", help="record human feedback")
    feedback_parser.add_argument("--id", required=True, dest="question_id")
    feedback_source = feedback_parser.add_mutually_exclusive_group(required=True)
    feedback_source.add_argument("--file", type=Path)
    feedback_source.add_argument("--text")
    feedback_parser.add_argument("--reviewer")
    feedback_parser.add_argument("--continue", action="store_true", dest="run_agent")

    approve = subparsers.add_parser("approve", help="interactively approve reviewed content")
    approve.add_argument("--id", required=True, dest="question_id")
    approve.add_argument("--reviewer")

    pr_parser = subparsers.add_parser("open-pr", help="create or update the review PR")
    pr_parser.add_argument("--id", required=True, dest="question_id")
    pr_parser.add_argument("--base", default="main")

    memory_list = subparsers.add_parser(
        "memory-list", help="list proposed reusable feedback lessons"
    )
    memory_list.add_argument("--id", dest="question_id")
    memory_list.add_argument("--all", action="store_true", dest="include_decided")

    memory_approve = subparsers.add_parser(
        "memory-approve", help="interactively activate a reusable feedback lesson"
    )
    memory_approve.add_argument("--id", required=True, dest="candidate_id")
    memory_approve.add_argument("--reviewer")

    memory_reject = subparsers.add_parser(
        "memory-reject", help="reject a proposed reusable feedback lesson"
    )
    memory_reject.add_argument("--id", required=True, dest="candidate_id")
    memory_reject.add_argument("--reason", required=True)
    memory_reject.add_argument("--reviewer")

    args = parser.parse_args(list(argv) if argv is not None else None)
    root = args.root.resolve()
    try:
        if args.command == "submit":
            package = submit_question(
                root=root,
                question_kind=args.question_kind,
                input_path=args.input,
                transcription_path=args.transcription,
                question_id=args.question_id,
                title=args.title,
                expert_note=args.expert_note,
                confidentiality=args.confidentiality,
                company_removed=args.company_removed,
                create_branch=not args.no_branch,
                run_agent=not args.offline,
                runner=None if args.offline else _runner(),
            )
            print(f"question workflow created: {package.relative_to(root)}")
            if args.open_pr:
                print(open_review_pr(root=root, question_id=package.name))
        elif args.command == "continue":
            package = continue_question(
                root=root, question_id=args.question_id, runner=_runner()
            )
            print(json.dumps(question_status(root=root, question_id=package.name), indent=2))
            if args.open_pr:
                print(open_review_pr(root=root, question_id=package.name))
        elif args.command == "status":
            print(json.dumps(question_status(root=root, question_id=args.question_id), indent=2))
        elif args.command == "next":
            status = question_status(root=root, question_id=args.question_id)
            print(status["next_action"])
        elif args.command == "resolve-duplicate":
            package = resolve_duplicate(
                root=root,
                question_id=args.question_id,
                decision=args.decision,
                reason=args.reason,
            )
            print(json.dumps(question_status(root=root, question_id=package.name), indent=2))
        elif args.command == "clarify":
            reviewer = args.reviewer or _default_reviewer(root)
            package = resolve_clarifications(
                root=root,
                question_id=args.question_id,
                response=args.response,
                reviewer=reviewer,
            )
            if args.run_agent:
                continue_question(root=root, question_id=package.name, runner=_runner())
            print(json.dumps(question_status(root=root, question_id=package.name), indent=2))
        elif args.command == "feedback":
            reviewer = args.reviewer or _default_reviewer(root)
            feedback = (
                args.text
                if args.text is not None
                else args.file.read_text(encoding="utf-8")
            )
            package = add_feedback(
                root=root,
                question_id=args.question_id,
                feedback=feedback,
                reviewer=reviewer,
                run_agent=args.run_agent,
                runner=_runner() if args.run_agent else None,
            )
            print(json.dumps(question_status(root=root, question_id=package.name), indent=2))
        elif args.command == "approve":
            if not sys.stdin.isatty():
                raise WorkflowError(
                    "approval requires an interactive terminal and cannot run non-interactively"
                )
            reviewer = args.reviewer or _default_reviewer(root)
            expected = f"APPROVE {args.question_id}"
            print(f"Type {expected!r} to confirm human approval:")
            confirmation = input().strip()
            package = approve_question(
                root=root,
                question_id=args.question_id,
                reviewer=reviewer,
                confirmation=confirmation,
            )
            print(json.dumps(question_status(root=root, question_id=package.name), indent=2))
        elif args.command == "open-pr":
            print(
                open_review_pr(
                    root=root, question_id=args.question_id, base=args.base
                )
            )
        elif args.command == "memory-list":
            print(
                json.dumps(
                    list_memory_candidates(
                        root,
                        question_id=args.question_id,
                        include_decided=args.include_decided,
                    ),
                    indent=2,
                )
            )
        elif args.command == "memory-approve":
            if not sys.stdin.isatty():
                raise WorkflowError(
                    "memory approval requires an interactive terminal and cannot run "
                    "non-interactively"
                )
            reviewer = args.reviewer or _default_reviewer(root)
            expected = f"REMEMBER {args.candidate_id}"
            print(f"Type {expected!r} to activate this lesson for future questions:")
            confirmation = input().strip()
            entry = approve_memory_candidate(
                root=root,
                candidate_id=args.candidate_id,
                reviewer=reviewer,
                confirmation=confirmation,
            )
            issues = validate_repository(root)
            if issues:
                raise WorkflowError(
                    "memory approval failed validation:\n"
                    + "\n".join(f"- {issue}" for issue in issues)
                )
            print(json.dumps(entry, indent=2))
        elif args.command == "memory-reject":
            reviewer = args.reviewer or _default_reviewer(root)
            candidate = reject_memory_candidate(
                root=root,
                candidate_id=args.candidate_id,
                reviewer=reviewer,
                reason=args.reason,
            )
            issues = validate_repository(root)
            if issues:
                raise WorkflowError(
                    "memory rejection failed validation:\n"
                    + "\n".join(f"- {issue}" for issue in issues)
                )
            print(json.dumps(candidate, indent=2))
    except (
        EditorialMemoryError,
        OSError,
        RuntimeError,
        WorkflowError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
