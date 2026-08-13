from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.editorial_memory import (
    EditorialMemoryError,
    approve_memory_candidate,
    list_memory_candidates,
    memory_prompt,
    record_memory_candidates,
    reject_memory_candidate,
)
from tools.ingest import ingest_question
from tools.validate import validate_repository


ROOT = Path(__file__).resolve().parents[1]


class EditorialMemoryTests(unittest.TestCase):
    def _root(self, temporary: str) -> Path:
        root = Path(temporary)
        shutil.copytree(ROOT / "schemas", root / "schemas")
        shutil.copytree(ROOT / "taxonomy", root / "taxonomy")
        shutil.copy2(ROOT / "editorial-memory.yaml", root / "editorial-memory.yaml")
        (root / "content").mkdir()
        return root

    def _package(self, root: Path, question_id: str) -> Path:
        source = root / f"{question_id}.txt"
        source.write_text("Design a bounded event delivery system.\n", encoding="utf-8")
        package = ingest_question(
            root=root,
            question_kind="system-design",
            input_path=source,
            question_id=question_id,
            title="Bounded event delivery",
        )
        feedback = package / "feedback/20260812T010000Z-review.md"
        feedback.parent.mkdir()
        feedback.write_text(
            "# Human feedback\n\nExplain overload ownership before listing mechanisms.\n",
            encoding="utf-8",
        )
        return package

    def _approve_package(self, package: Path) -> None:
        flags = {
            "agent_reviewed": True,
            "human_reviewed": True,
            "technical_accuracy_reviewed": True,
            "interview_realism_reviewed": True,
        }
        metadata_path = package / "metadata.yaml"
        review_path = package / "review.yaml"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        review = json.loads(review_path.read_text(encoding="utf-8"))
        metadata["status"] = "approved"
        metadata["review"] = flags
        review["checks"] = flags
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")

    def test_candidate_requires_human_approval_before_future_prompt_use(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            package = self._package(root, "sd-memory-source")
            recorded = record_memory_candidates(
                package=package,
                candidates=[
                    {
                        "principle": (
                            "State overload ownership before choosing backpressure mechanisms."
                        ),
                        "rationale": (
                            "Ownership determines which component may block, shed, or recover data."
                        ),
                        "question_types": ["system_design"],
                    }
                ],
            )
            self.assertEqual(len(recorded), 1)
            candidate_id = recorded[0]["id"]
            self.assertNotIn("State overload ownership", memory_prompt(root, "system_design"))

            with self.assertRaisesRegex(EditorialMemoryError, "exactly match"):
                approve_memory_candidate(
                    root=root,
                    candidate_id=candidate_id,
                    reviewer="Editor",
                    confirmation="yes",
                )
            with self.assertRaisesRegex(EditorialMemoryError, "source question"):
                approve_memory_candidate(
                    root=root,
                    candidate_id=candidate_id,
                    reviewer="Editor",
                    confirmation=f"REMEMBER {candidate_id}",
                )
            self._approve_package(package)
            approve_memory_candidate(
                root=root,
                candidate_id=candidate_id,
                reviewer="Editor",
                confirmation=f"REMEMBER {candidate_id}",
            )

            self.assertIn("State overload ownership", memory_prompt(root, "system_design"))
            self.assertNotIn("State overload ownership", memory_prompt(root, "coding"))
            self.assertEqual(list_memory_candidates(root), [])
            self.assertEqual(validate_repository(root), [])

    def test_rejected_candidate_remains_auditable_but_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            package = self._package(root, "sd-memory-rejected")
            candidate = record_memory_candidates(
                package=package,
                candidates=[
                    {
                        "principle": (
                            "Always require one specific transport for every delivery design."
                        ),
                        "rationale": (
                            "This proposed rule is intentionally too rigid for broad reuse."
                        ),
                        "question_types": ["system_design"],
                    }
                ],
            )[0]
            reject_memory_candidate(
                root=root,
                candidate_id=str(candidate["id"]),
                reviewer="Editor",
                reason="Transport choice depends on the interview contract.",
            )

            self.assertEqual(list_memory_candidates(root), [])
            decided = list_memory_candidates(root, include_decided=True)
            self.assertEqual(decided[0]["status"], "rejected")
            self.assertNotIn("Always require", memory_prompt(root, "system_design"))
            self.assertEqual(validate_repository(root), [])

    def test_same_lesson_from_two_questions_merges_after_separate_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            principle = "State overload ownership before choosing backpressure mechanisms."
            candidate_ids = []
            for question_id, scopes in (
                ("sd-memory-first", ["system_design"]),
                ("sd-memory-second", ["coding"]),
            ):
                package = self._package(root, question_id)
                self._approve_package(package)
                candidate = record_memory_candidates(
                    package=package,
                    candidates=[
                        {
                            "principle": principle,
                            "rationale": (
                                "Ownership determines which component may block, shed, or recover data."
                            ),
                            "question_types": scopes,
                        }
                    ],
                )[0]
                candidate_ids.append(str(candidate["id"]))

            self.assertNotEqual(candidate_ids[0], candidate_ids[1])
            first = approve_memory_candidate(
                root=root,
                candidate_id=candidate_ids[0],
                reviewer="Editor",
                confirmation=f"REMEMBER {candidate_ids[0]}",
            )
            second = approve_memory_candidate(
                root=root,
                candidate_id=candidate_ids[1],
                reviewer="Editor",
                confirmation=f"REMEMBER {candidate_ids[1]}",
            )
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(second["question_types"], ["coding", "system_design"])
            self.assertIn(principle, memory_prompt(root, "coding"))
            decided = list_memory_candidates(root, include_decided=True)
            merged = next(item for item in decided if item["id"] == candidate_ids[1])
            self.assertEqual(merged["merged_into"], candidate_ids[0])
            self.assertEqual(validate_repository(root), [])


if __name__ == "__main__":
    unittest.main()
