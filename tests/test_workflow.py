from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Sequence
from unittest.mock import patch

from tools.agent_runtime import AgentResult
from tools.editorial_memory import approve_memory_candidate
from tools.ingest import ingest_question
from tools.render_diagrams import render_source
from tools.validate import validate_repository
from tools.workflow import (
    WorkflowError,
    _draft_prompt,
    _feedback_revision_prompt,
    _run_deterministic_gates,
    _review_path_allowed,
    add_feedback,
    approve_question,
    continue_question,
    open_review_pr,
    question_status,
    resolve_duplicate,
    submit_question,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeRunner:
    def __init__(self, outputs: Sequence[dict[str, object]]) -> None:
        self.outputs = list(outputs)
        self.calls: list[tuple[str, str]] = []

    def _result(self, action: str, prompt: str) -> AgentResult:
        if not self.outputs:
            raise AssertionError("fake agent received an unexpected call")
        self.calls.append((action, prompt))
        value = self.outputs.pop(0)
        return AgentResult(
            thread_id=f"thread-{len(self.calls)}",
            final_output=json.dumps(value),
            events=(),
        )

    def run(
        self,
        prompt: str,
        *,
        root: Path,
        sandbox: str,
        images: Sequence[Path] = (),
        output_schema: Optional[Path] = None,
    ) -> AgentResult:
        return self._result(f"run:{sandbox}", prompt)

    def resume(
        self,
        thread_id: str,
        prompt: str,
        *,
        root: Path,
        images: Sequence[Path] = (),
        output_schema: Optional[Path] = None,
    ) -> AgentResult:
        return self._result("resume", prompt)


class LifecycleMutatingRunner(FakeRunner):
    """Reproduce a drafting skill trying to take over controller lifecycle state."""

    def run(
        self,
        prompt: str,
        *,
        root: Path,
        sandbox: str,
        images: Sequence[Path] = (),
        output_schema: Optional[Path] = None,
    ) -> AgentResult:
        if sandbox == "workspace-write":
            package = root / "content/system-design/sd-lifecycle-race"
            metadata_path = package / "metadata.yaml"
            review_path = package / "review.yaml"
            workflow_path = package / "workflow.yaml"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            review = json.loads(review_path.read_text(encoding="utf-8"))
            workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
            flags = dict(metadata["review"])
            flags["agent_reviewed"] = True
            metadata["status"] = "needs_human_review"
            metadata["review"] = flags
            review["checks"] = flags
            workflow["state"] = "needs_human_review"
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
            review_path.write_text(json.dumps(review, indent=2) + "\n")
            workflow_path.write_text(json.dumps(workflow, indent=2) + "\n")
        return super().run(
            prompt,
            root=root,
            sandbox=sandbox,
            images=images,
            output_schema=output_schema,
        )


class DiagramRevisingRunner(FakeRunner):
    def __init__(self, outputs, source: Path, replacement: str) -> None:
        super().__init__(outputs)
        self.source = source
        self.replacement = replacement

    def run(self, prompt: str, *, root: Path, sandbox: str, **kwargs) -> AgentResult:
        if sandbox == "workspace-write":
            self.source.write_text(self.replacement, encoding="utf-8")
        return super().run(prompt, root=root, sandbox=sandbox, **kwargs)


READY = {
    "outcome": "ready",
    "summary": "Draft completed.",
    "clarification_questions": [],
    "validation_commands": ["python -m tools.validate"],
    "memory_candidates": [],
}
REVISION_READY = {
    **READY,
    "memory_candidates": [
        {
            "principle": (
                "For bounded systems, make overload ownership and the saturation policy explicit."
            ),
            "rationale": (
                "This exposes the decision that determines backpressure, loss, and recovery behavior."
            ),
            "question_types": ["system_design"],
        }
    ],
}
PASSED = {"passed": True, "summary": "Review passed.", "issues": []}


class WorkflowTests(unittest.TestCase):
    def _root(self, temporary: str) -> Path:
        root = Path(temporary)
        shutil.copytree(ROOT / "schemas", root / "schemas")
        shutil.copytree(ROOT / "taxonomy", root / "taxonomy")
        shutil.copy2(ROOT / "editorial-memory.yaml", root / "editorial-memory.yaml")
        (root / "content").mkdir()
        return root

    def test_offline_submission_persists_audit_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            source = root / "prompt.txt"
            source.write_text("Design a bounded order audit stream.\n", encoding="utf-8")
            package = submit_question(
                root=root,
                question_kind="design",
                input_path=source,
                runner=None,
                question_id="sd-order-audit-stream",
                title="Bounded order audit stream",
                create_branch=False,
                run_agent=False,
            )

            status = question_status(root=root, question_id=package.name)
            self.assertEqual(status["status"], "normalized")
            self.assertEqual(status["workflow_state"], "normalized")
            self.assertTrue((package / "workflow.yaml").is_file())
            self.assertTrue((package / "deduplication.yaml").is_file())
            self.assertEqual(validate_repository(root), [])

            with self.assertRaisesRegex(WorkflowError, "contentctl continue"):
                submit_question(
                    root=root,
                    question_kind="design",
                    input_path=source,
                    runner=None,
                    question_id="sd-order-audit-stream",
                    title="Bounded order audit stream",
                    create_branch=False,
                    run_agent=False,
                )

    def test_duplicate_submission_pauses_until_human_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            first = root / "first.txt"
            first.write_text("Merge records from ordered sources.\n", encoding="utf-8")
            ingest_question(
                root=root,
                question_kind="coding",
                input_path=first,
                question_id="code-first-merger",
                title="Ordered source merger",
            )
            second = root / "second.txt"
            second.write_text("Merge records from ordered sources.\n", encoding="utf-8")
            package = submit_question(
                root=root,
                question_kind="coding",
                input_path=second,
                runner=None,
                question_id="code-second-merger",
                title="Ordered source merger",
                create_branch=False,
                run_agent=False,
            )
            self.assertEqual(
                question_status(root=root, question_id=package.name)["status"],
                "needs_clarification",
            )
            with self.assertRaisesRegex(WorkflowError, "duplicate candidates"):
                continue_question(
                    root=root,
                    question_id=package.name,
                    runner=FakeRunner([READY, PASSED]),
                )

            resolve_duplicate(
                root=root,
                question_id=package.name,
                decision="distinct",
                reason="The second question adds a watermark and close contract.",
            )
            self.assertEqual(
                question_status(root=root, question_id=package.name)["status"],
                "normalized",
            )
            self.assertEqual(validate_repository(root), [])

    def test_foundational_trials_preserve_source_and_review_gate_on_rerun(self) -> None:
        cases = (
            ("news-feed", "Design a News Feed"),
            ("notifications", "Design a Notification System"),
            ("log-publishing-query", "Design a Log Publishing and Query System"),
        )
        for name, title in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = self._root(temporary)
                source = ROOT / "tests/e2e/system-design" / f"{name}.md"
                note = "Foundational readability trial; label illustrative assumptions."
                package = submit_question(
                    root=root,
                    question_kind="design",
                    input_path=source,
                    runner=FakeRunner([READY, PASSED]),
                    question_id=f"sd-e2e-{name}",
                    title=title,
                    expert_note=note,
                    create_branch=False,
                )
                preserved_notes = (package / "expert-notes.md").read_bytes()
                # Re-evaluating after a global prompt/skill change must run a new
                # independent review; an earlier pass cannot authorize handoff.
                failed_review = {
                    "passed": False,
                    "summary": "The core explanation needs revision.",
                    "issues": [{"severity": "important", "message": "Core is not self-contained."}],
                }
                runner = FakeRunner([READY, failed_review])
                continue_question(
                    root=root,
                    question_id=package.name,
                    runner=runner,
                    max_revision_rounds=0,
                )
                status = question_status(root=root, question_id=package.name)
                self.assertEqual(status["workflow_state"], "agent_review_failed")
                self.assertFalse(any(status["review"].values()))
                self.assertEqual(runner.calls[0][0], "resume")
                self.assertEqual(runner.calls[1][0], "run:read-only")
                self.assertEqual((package / "source" / source.name).read_bytes(), source.read_bytes())
                self.assertEqual((package / "expert-notes.md").read_bytes(), preserved_notes)
                self.assertEqual(validate_repository(root), [])
                retry = FakeRunner([READY, PASSED])
                continue_question(root=root, question_id=package.name, runner=retry)
                self.assertIn("Core is not self-contained.", retry.calls[0][1])
                self.assertEqual(retry.calls[1][0], "run:read-only")
                recovered = question_status(root=root, question_id=package.name)
                self.assertEqual(recovered["workflow_state"], "needs_human_review")
                self.assertFalse(recovered["review"]["human_reviewed"])

    def test_diagram_revision_refreshes_svg_before_validation(self) -> None:
        for valid in (True, False):
            with self.subTest(valid=valid), tempfile.TemporaryDirectory() as temporary:
                root = self._root(temporary)
                source = ROOT / "tests/e2e/system-design/news-feed.md"
                package = submit_question(
                    root=root,
                    question_kind="design",
                    input_path=source,
                    runner=None,
                    question_id="sd-diagram-revision",
                    create_branch=False,
                    run_agent=False,
                )
                diagram = package / "diagrams/context.mmd"
                output = root / "generated/diagrams" / package.name / "context.svg"
                output.parent.mkdir(parents=True)
                original_svg = render_source(diagram.read_text())
                output.write_text(original_svg)
                replacement = (
                    'flowchart LR\n    A["Client request"] --> B["Application process"]\n'
                    if valid else "not a supported diagram\n"
                )
                runner = DiagramRevisingRunner([READY, PASSED], diagram, replacement)
                if valid:
                    continue_question(
                        root=root, question_id=package.name, runner=runner,
                        max_revision_rounds=0,
                    )
                    self.assertEqual(output.read_text(), render_source(replacement))
                    self.assertEqual(len(runner.calls), 2)
                    self.assertEqual(runner.calls[1][0], "run:read-only")
                    self.assertEqual(validate_repository(root), [])
                else:
                    with self.assertRaisesRegex(WorkflowError, "not renderable"):
                        continue_question(
                            root=root, question_id=package.name, runner=runner,
                            max_revision_rounds=0,
                        )
                    self.assertEqual(output.read_text(), original_svg)
                    self.assertEqual(len(runner.calls), 1)
                    self.assertEqual(
                        question_status(root=root, question_id=package.name)["workflow_state"],
                        "agent_validation_failed",
                    )

    def test_agent_review_feedback_and_human_approval_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            source = root / "prompt.txt"
            source.write_text("Design a bounded risk-event stream.\n", encoding="utf-8")
            runner = FakeRunner([READY, PASSED])
            package = submit_question(
                root=root,
                question_kind="system-design",
                input_path=source,
                runner=runner,
                question_id="sd-risk-event-stream",
                title="Bounded risk event stream",
                create_branch=False,
                run_agent=True,
            )
            status = question_status(root=root, question_id=package.name)
            self.assertEqual(status["status"], "needs_human_review")
            self.assertTrue(status["review"]["agent_reviewed"])
            self.assertIn("system-design tutorial", runner.calls[0][1])
            self.assertIn("metadata.design_patterns", runner.calls[0][1])
            self.assertIn("reject a technically correct answer", runner.calls[1][1])

            add_feedback(
                root=root,
                question_id=package.name,
                feedback="Make overload ownership explicit.",
                reviewer="Human Editor",
            )
            status = question_status(root=root, question_id=package.name)
            self.assertEqual(status["status"], "changes_requested")
            self.assertFalse(status["review"]["agent_reviewed"])
            self.assertIn(
                "Make overload ownership explicit",
                (package / "expert-notes.md").read_text(encoding="utf-8"),
            )

            continue_question(
                root=root,
                question_id=package.name,
                runner=(revision_runner := FakeRunner([REVISION_READY, PASSED])),
            )
            self.assertIn("focused contentctl revision", revision_runner.calls[0][1])
            self.assertIn("freely restructure or rewrite", revision_runner.calls[0][1])
            self.assertIn("$draft-system-design", revision_runner.calls[0][1])
            self.assertIn("content/STYLE_GUIDE.md", revision_runner.calls[0][1])
            self.assertEqual(revision_runner.calls[0][0], "run:workspace-write")
            workflow = json.loads((package / "workflow.yaml").read_text())
            self.assertTrue(
                any(
                    event.get("type") == "draft_context_rotated"
                    for event in workflow["events"]
                )
            )
            with self.assertRaisesRegex(WorkflowError, "exactly match"):
                approve_question(
                    root=root,
                    question_id=package.name,
                    reviewer="Human Editor",
                    confirmation="yes",
                )
            approve_question(
                root=root,
                question_id=package.name,
                reviewer="Human Editor",
                confirmation=f"APPROVE {package.name}",
            )
            status = question_status(root=root, question_id=package.name)
            self.assertEqual(status["status"], "approved")
            self.assertTrue(all(status["review"].values()))
            self.assertEqual(len(status["pending_memory_candidates"]), 1)
            candidate_id = status["pending_memory_candidates"][0]["id"]
            self.assertIn("memory-list", status["next_action"])
            approve_memory_candidate(
                root=root,
                candidate_id=candidate_id,
                reviewer="Human Editor",
                confirmation=f"REMEMBER {candidate_id}",
            )
            status = question_status(root=root, question_id=package.name)
            self.assertEqual(status["pending_memory_candidates"], [])
            self.assertEqual(status["active_editorial_memory_count"], 1)
            self.assertEqual(validate_repository(root), [])

    def test_drafting_guidance_is_routed_by_question_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            for question_type, skill in (
                ("system_design", "$draft-system-design"),
                ("coding", "$draft-coding-question"),
                ("fundamentals", "$draft-fundamentals-question"),
            ):
                with self.subTest(question_type=question_type):
                    metadata = {"id": "test-guidance", "type": question_type}
                    prompt = _draft_prompt(root, root / "unused-package", metadata)
                    revision = _feedback_revision_prompt(root, root / "unused-package", metadata)
                    self.assertIn(skill, prompt)
                    self.assertIn(skill, revision)
                    self.assertEqual("metadata.design_patterns" in prompt, question_type == "system_design")
                    self.assertEqual("$build-practice-question" in prompt, question_type == "coding")
                    self.assertEqual("runnable experiment" in prompt, question_type == "fundamentals")

    def test_feedback_is_accepted_after_agent_review_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            source = root / "prompt.txt"
            source.write_text("Design a bounded risk-event stream.\n", encoding="utf-8")
            package = submit_question(
                root=root,
                question_kind="system-design",
                input_path=source,
                runner=None,
                question_id="sd-review-failed-feedback",
                title="Risk event stream needing revision",
                create_branch=False,
                run_agent=False,
            )
            metadata_path = package / "metadata.yaml"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["status"] = "draft"
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            workflow_path = package / "workflow.yaml"
            workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
            workflow["state"] = "agent_review_failed"
            workflow_path.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")

            add_feedback(
                root=root,
                question_id=package.name,
                feedback="Turn the specification into a scenario-led tutorial.",
                reviewer="Human Editor",
            )

            status = question_status(root=root, question_id=package.name)
            self.assertEqual(status["status"], "changes_requested")
            self.assertEqual(status["workflow_state"], "changes_requested")
            self.assertIn(
                "Turn the specification into a scenario-led tutorial.",
                (package / "expert-notes.md").read_text(encoding="utf-8"),
            )

    def test_controller_reclaims_lifecycle_and_runs_independent_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            source = root / "prompt.txt"
            source.write_text("Design a bounded event stream.\n", encoding="utf-8")
            runner = LifecycleMutatingRunner([READY, PASSED])

            with patch("tools.workflow._run_deterministic_gates") as gates:
                package = submit_question(
                    root=root,
                    question_kind="design",
                    input_path=source,
                    runner=runner,
                    question_id="sd-lifecycle-race",
                    title="Bounded lifecycle race stream",
                    create_branch=False,
                    run_agent=True,
                )

            status = question_status(root=root, question_id=package.name)
            self.assertEqual(status["workflow_state"], "needs_human_review")
            self.assertEqual(status["attempts"]["draft"], 1)
            self.assertEqual(status["attempts"]["review"], 1)
            self.assertTrue((package / "agent-review.yaml").is_file())
            gates.assert_called_once()
            self.assertEqual(validate_repository(root), [])

    def test_approval_rejects_missing_independent_review_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            source = root / "prompt.txt"
            source.write_text("Design a bounded audit stream.\n", encoding="utf-8")
            package = submit_question(
                root=root,
                question_kind="design",
                input_path=source,
                runner=None,
                question_id="sd-no-independent-review",
                title="Bounded audit stream without review",
                create_branch=False,
                run_agent=False,
            )
            metadata_path = package / "metadata.yaml"
            review_path = package / "review.yaml"
            workflow_path = package / "workflow.yaml"
            metadata = json.loads(metadata_path.read_text())
            review = json.loads(review_path.read_text())
            workflow = json.loads(workflow_path.read_text())
            metadata["status"] = "needs_human_review"
            metadata["review"]["agent_reviewed"] = True
            review["checks"] = metadata["review"]
            workflow["state"] = "needs_human_review"
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
            review_path.write_text(json.dumps(review, indent=2) + "\n")
            workflow_path.write_text(json.dumps(workflow, indent=2) + "\n")

            validation = "\n".join(str(issue) for issue in validate_repository(root))
            self.assertIn("requires a completed independent review", validation)
            self.assertIn("requires an independent review report", validation)
            with self.assertRaisesRegex(WorkflowError, "independent agent review record"):
                approve_question(
                    root=root,
                    question_id=package.name,
                    reviewer="Human Editor",
                    confirmation=f"APPROVE {package.name}",
                )

    def test_controller_gate_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
            with patch("tools.workflow._run_gate") as gate:
                _run_deterministic_gates(root, {"type": "coding"})
            self.assertEqual(gate.call_count, 2)
            self.assertEqual(gate.call_args_list[0].args[1], ("make", "practice-test"))
            self.assertEqual(gate.call_args_list[1].args[1], ("make", "pdf-preview"))

            with patch("tools.workflow._run_gate") as gate:
                _run_deterministic_gates(root, {"type": "system_design"})
            gate.assert_called_once_with(
                root, ("make", "pdf-preview"), "review PDF gate"
            )

    def test_image_transcription_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            image = root / "question.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            transcription = {
                "transcription": "Design a bounded quote fan-out service.",
                "uncertainties": [],
                "clarification_questions": [],
            }
            runner = FakeRunner([transcription, READY, PASSED])
            package = submit_question(
                root=root,
                question_kind="design",
                input_path=image,
                runner=runner,
                question_id="sd-image-fanout",
                title="Bounded quote fan-out service",
                create_branch=False,
                run_agent=True,
            )
            metadata = json.loads((package / "metadata.yaml").read_text())
            archived = [
                package / item for item in metadata["source"]["original_files"]
            ]
            self.assertEqual(len(archived), 2)
            self.assertTrue(any(path.name == "transcription.txt" for path in archived))
            self.assertEqual(
                question_status(root=root, question_id=package.name)["status"],
                "needs_human_review",
            )

    def test_review_pr_scope_excludes_unrelated_changes(self) -> None:
        root = Path("/repository")
        package = root / "content/coding/code-example"

        self.assertTrue(
            _review_path_allowed(
                "content/coding/code-example/question.md",
                package,
                root,
                "code-example",
            )
        )
        self.assertTrue(
            _review_path_allowed(
                "practice/questions/code-example/tests/test.cpp",
                package,
                root,
                "code-example",
            )
        )
        self.assertTrue(
            _review_path_allowed(
                "practice/CMakeLists.txt", package, root, "code-example"
            )
        )
        self.assertTrue(
            _review_path_allowed(
                "editorial-memory.yaml", package, root, "code-example"
            )
        )
        self.assertFalse(
            _review_path_allowed("tools/workflow.py", package, root, "code-example")
        )
        self.assertFalse(
            _review_path_allowed(
                "content/coding/code-other/question.md",
                package,
                root,
                "code-example",
            )
        )

    def test_review_pr_handoff_updates_and_readies_existing_approved_pr(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            source = root / "prompt.txt"
            source.write_text("Design a bounded event stream.\n", encoding="utf-8")
            package = submit_question(
                root=root,
                question_kind="design",
                input_path=source,
                runner=None,
                question_id="sd-repeatable-pr",
                title="Repeatable review PR",
                create_branch=False,
                run_agent=False,
            )
            metadata_path = package / "metadata.yaml"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["status"] = "approved"
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")

            git_calls: list[tuple[str, ...]] = []
            process_calls: list[tuple[str, ...]] = []

            def fake_git(_root: Path, *args: str, **_kwargs: object):
                git_calls.append(args)
                stdout = "question/sd-repeatable-pr\n" if args[0] == "branch" else ""
                return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

            def fake_process(command, **_kwargs):
                call = tuple(str(item) for item in command)
                process_calls.append(call)
                stdout = (
                    '{"url":"https://example.test/pr/7","isDraft":true}'
                    if call[:3] == ("gh", "pr", "view")
                    else ""
                )
                return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

            changed = f"content/system-design/{package.name}/workflow.yaml"
            with patch(
                "tools.workflow._git", side_effect=fake_git
            ), patch(
                "tools.workflow._changed_paths", return_value=[changed]
            ), patch(
                "tools.workflow.validate_repository", return_value=[]
            ), patch(
                "tools.workflow.subprocess.run", side_effect=fake_process
            ):
                url = open_review_pr(root=root, question_id=package.name)

            self.assertEqual(url, "https://example.test/pr/7")
            self.assertTrue(any(call[:3] == ("gh", "pr", "edit") for call in process_calls))
            self.assertTrue(any(call[:3] == ("gh", "pr", "ready") for call in process_calls))
            self.assertFalse(any(call[:3] == ("gh", "pr", "create") for call in process_calls))
            self.assertIn(("push", "-u", "origin", "question/sd-repeatable-pr"), git_calls)


if __name__ == "__main__":
    unittest.main()
