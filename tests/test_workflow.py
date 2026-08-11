from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Sequence

from tools.agent_runtime import AgentResult
from tools.ingest import ingest_question
from tools.validate import validate_repository
from tools.workflow import (
    WorkflowError,
    _review_path_allowed,
    add_feedback,
    approve_question,
    continue_question,
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


READY = {
    "outcome": "ready",
    "summary": "Draft completed.",
    "clarification_questions": [],
    "validation_commands": ["python -m tools.validate"],
}
PASSED = {"passed": True, "summary": "Review passed.", "issues": []}


class WorkflowTests(unittest.TestCase):
    def _root(self, temporary: str) -> Path:
        root = Path(temporary)
        shutil.copytree(ROOT / "schemas", root / "schemas")
        shutil.copytree(ROOT / "taxonomy", root / "taxonomy")
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

    def test_agent_review_feedback_and_human_approval_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            source = root / "prompt.txt"
            source.write_text("Design a bounded risk-event stream.\n", encoding="utf-8")
            package = submit_question(
                root=root,
                question_kind="system-design",
                input_path=source,
                runner=FakeRunner([READY, PASSED]),
                question_id="sd-risk-event-stream",
                title="Bounded risk event stream",
                create_branch=False,
                run_agent=True,
            )
            status = question_status(root=root, question_id=package.name)
            self.assertEqual(status["status"], "needs_human_review")
            self.assertTrue(status["review"]["agent_reviewed"])

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
                runner=FakeRunner([READY, PASSED]),
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
            self.assertEqual(validate_repository(root), [])

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


if __name__ == "__main__":
    unittest.main()
