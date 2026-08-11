from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.validate import (
    ROOT,
    SchemaValidator,
    duplicate_id_issues,
    load_data,
    validate_repository,
)


class SchemaValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = SchemaValidator(ROOT / "schemas")
        self.schema = ROOT / "schemas" / "coding.schema.json"

    def test_valid_fixture_passes(self) -> None:
        fixture = load_data(ROOT / "tests/fixtures/valid/coding-metadata.yaml")
        self.assertEqual([], self.validator.validate(fixture, self.schema))

    def test_invalid_fixture_has_useful_errors(self) -> None:
        fixture = load_data(ROOT / "tests/fixtures/invalid/coding-metadata.yaml")
        messages = "\n".join(
            str(issue) for issue in self.validator.validate(fixture, self.schema)
        )
        self.assertIn(".status", messages)
        self.assertIn(".difficulty", messages)
        self.assertIn(".expected_duration_minutes", messages)
        self.assertIn(".content_file", messages)
        self.assertIn("must be an ISO date", messages)

    def test_duplicate_ids_are_rejected(self) -> None:
        metadata = load_data(ROOT / "tests/fixtures/valid/coding-metadata.yaml")
        issues = duplicate_id_issues(
            [
                (Path("first/metadata.yaml"), metadata),
                (Path("second/metadata.yaml"), dict(metadata)),
            ]
        )
        self.assertEqual(1, len(issues))
        self.assertIn("duplicate question id", str(issues[0]))
        self.assertIn("code-valid-fixture", str(issues[0]))

    def test_repository_gold_fixtures_pass(self) -> None:
        self.assertEqual([], validate_repository(ROOT))


class RepositoryGateTests(unittest.TestCase):
    def _make_root(self, destination: Path) -> Path:
        for name in ("schemas", "taxonomy", "practice"):
            shutil.copytree(ROOT / name, destination / name)
        for content_type in ("system-design", "coding", "fundamentals"):
            shutil.copytree(
                ROOT / "content" / content_type,
                destination / "content" / content_type,
            )
        return destination

    def _issues_after(self, mutation) -> str:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._make_root(Path(temporary))
            mutation(root)
            return "\n".join(str(issue) for issue in validate_repository(root))

    def test_unrenderable_diagram_is_rejected(self) -> None:
        def mutate(root: Path) -> None:
            diagram = (
                root
                / "content"
                / "system-design"
                / "sd-market-data-feed"
                / "diagrams"
                / "architecture.mmd"
            )
            diagram.write_text(
                "stateDiagram-v2\n  [*] --> Live\n",
                encoding="utf-8",
            )

        self.assertIn("Mermaid source is not renderable", self._issues_after(mutate))

    def test_placeholder_and_broken_local_link_are_rejected(self) -> None:
        def mutate(root: Path) -> None:
            question = (
                root
                / "content"
                / "coding"
                / "code-multi-source-stream-merger"
                / "question.md"
            )
            question.write_text(
                question.read_text(encoding="utf-8")
                + "\nTODO: INSERT ANSWER\n[missing](missing.md)\n",
                encoding="utf-8",
            )

        messages = self._issues_after(mutate)
        self.assertIn("unresolved placeholder", messages)
        self.assertIn("broken local Markdown link", messages)

    def test_approved_content_requires_completed_review(self) -> None:
        def mutate(root: Path) -> None:
            metadata_path = (
                root
                / "content"
                / "coding"
                / "code-multi-source-stream-merger"
                / "metadata.yaml"
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["status"] = "approved"
            metadata_path.write_text(
                json.dumps(metadata, indent=2) + "\n",
                encoding="utf-8",
            )

        self.assertIn(
            "approved or published content requires every review flag",
            self._issues_after(mutate),
        )

    def test_approved_coding_content_requires_practice_package(self) -> None:
        def mutate(root: Path) -> None:
            package = (
                root
                / "content"
                / "coding"
                / "code-multi-source-stream-merger"
            )
            metadata_path = package / "metadata.yaml"
            review_path = package / "review.yaml"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            flags = {
                "agent_reviewed": True,
                "human_reviewed": True,
                "technical_accuracy_reviewed": True,
                "interview_realism_reviewed": True,
            }
            metadata["status"] = "approved"
            metadata["review"] = flags
            metadata["practice"] = None
            metadata_path.write_text(
                json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
            )
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["checks"] = flags
            review_path.write_text(
                json.dumps(review, indent=2) + "\n", encoding="utf-8"
            )

        self.assertIn(
            "approved or published coding content requires a practice package",
            self._issues_after(mutate),
        )

    def test_missing_practice_target_registration_is_rejected(self) -> None:
        def mutate(root: Path) -> None:
            cmake_path = root / "practice" / "CMakeLists.txt"
            cmake_path.write_text(
                cmake_path.read_text(encoding="utf-8").replace(
                    "add_subdirectory(questions/fund-sequence-lock)",
                    "",
                ),
                encoding="utf-8",
            )

        self.assertIn("missing root registration", self._issues_after(mutate))

    def test_missing_content_file_is_rejected(self) -> None:
        def mutate(root: Path) -> None:
            (
                root
                / "content"
                / "fundamentals"
                / "fund-sequence-lock"
                / "expert-notes.md"
            ).unlink()

        self.assertIn("required file is missing", self._issues_after(mutate))

    def test_broken_related_question_is_rejected(self) -> None:
        def mutate(root: Path) -> None:
            metadata_path = (
                root
                / "content"
                / "fundamentals"
                / "fund-sequence-lock"
                / "metadata.yaml"
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["related_questions"].append("fund-does-not-exist")
            metadata_path.write_text(
                json.dumps(metadata, indent=2) + "\n",
                encoding="utf-8",
            )

        self.assertIn("references unknown question id", self._issues_after(mutate))

    def test_missing_practice_directory_entry_is_rejected(self) -> None:
        def mutate(root: Path) -> None:
            (
                root
                / "practice"
                / "questions"
                / "fund-sequence-lock"
                / "README.md"
            ).unlink()

        self.assertIn(
            "required runnable_experiment path is missing",
            self._issues_after(mutate),
        )

    def test_more_than_three_followups_are_rejected(self) -> None:
        def mutate(root: Path) -> None:
            question = (
                root
                / "content"
                / "coding"
                / "code-multi-source-stream-merger"
                / "question.md"
            )
            markdown = question.read_text(encoding="utf-8")
            question.write_text(
                markdown.replace(
                    "\n## Related C++ knowledge",
                    "\n- **Extra follow-up?** Extra answer.\n\n"
                    "## Related C++ knowledge",
                ),
                encoding="utf-8",
            )

        self.assertIn("maximum is 3", self._issues_after(mutate))


if __name__ == "__main__":
    unittest.main()
