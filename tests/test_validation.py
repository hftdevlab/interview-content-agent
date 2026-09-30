from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.validate import (
    REQUIRED_HEADINGS,
    ROOT,
    SchemaValidator,
    _heading_issues,
    _load_design_patterns,
    _section_item_issues,
    duplicate_id_issues,
    load_data,
    validate_repository,
)


TUTORIAL_MARKDOWN = """# Design a notification system

## Question and clarifications

Deliver a notification through the user's selected channel.

## Requirements

### Functional requirements

Accept a request and attempt delivery.

### Non-functional requirements

Preserve accepted work across a worker restart.

## Core entities

A notification and a channel delivery attempt.

## High-level architecture

![Durable requests feed delivery workers.](../../../generated/diagrams/sd-example/context.svg)

## Deep dives

Retry an uncertain delivery without claiming exactly-once external effects.
"""


class SystemDesignStructureTests(unittest.TestCase):
    def _issues(self, markdown: str) -> list:
        return _heading_issues(
            "question.md", markdown, "system_design", [{"rendered_file": "context.svg"}]
        )

    def test_tutorial_does_not_require_api_comparisons_or_followups(self) -> None:
        self.assertEqual([], self._issues(TUTORIAL_MARKDOWN))

    def test_complete_legacy_outline_is_still_supported(self) -> None:
        legacy = "\n\n".join(
            f"{heading}\n\nA substantive explanation belongs here."
            for heading in REQUIRED_HEADINGS["system_design"]
        )
        self.assertEqual([], self._issues(legacy))

    def test_missing_tutorial_sections_and_requirement_types_are_rejected(self) -> None:
        for heading in (
            "## Question and clarifications",
            "## Requirements",
            "### Functional requirements",
            "### Non-functional requirements",
            "## Core entities",
            "## High-level architecture",
            "## Deep dives",
        ):
            with self.subTest(heading=heading):
                issues = self._issues(TUTORIAL_MARKDOWN.replace(heading, "An explanation"))
                self.assertTrue(issues)
                self.assertIn(heading, "\n".join(str(issue) for issue in issues))

    def test_requirements_must_be_inside_the_requirements_section(self) -> None:
        document = TUTORIAL_MARKDOWN.replace("### Non-functional requirements", "Reliability")
        document += "\n### Non-functional requirements\n\nToo late in the chapter.\n"
        self.assertIn(
            "Requirements must contain",
            "\n".join(str(issue) for issue in self._issues(document)),
        )

    def test_heading_mentions_and_fenced_examples_do_not_satisfy_structure(self) -> None:
        for replacement in (
            "The section is called ## Core entities.",
            "```markdown\n## Core entities\n```",
            "~~~markdown\n## Core entities\n~~~",
        ):
            with self.subTest(replacement=replacement):
                document = TUTORIAL_MARKDOWN.replace("## Core entities", replacement)
                self.assertIn(
                    "missing required heading '## Core entities'",
                    "\n".join(str(issue) for issue in self._issues(document)),
                )

    def test_architecture_requires_a_declared_diagram_in_that_section(self) -> None:
        image = "![Durable requests feed delivery workers.](../../../generated/diagrams/sd-example/context.svg)"
        for replacement in ("", image.replace("context.svg", "unknown.svg"), f"```\n{image}\n```"):
            with self.subTest(replacement=replacement):
                document = TUTORIAL_MARKDOWN.replace(image, replacement)
                self.assertIn(
                    "must reference at least one declared diagram",
                    "\n".join(str(issue) for issue in self._issues(document)),
                )
        misplaced = TUTORIAL_MARKDOWN.replace(image, "") + "\n" + image
        self.assertTrue(self._issues(misplaced))

    def test_followups_and_pitfalls_have_separate_three_item_caps(self) -> None:
        combined = (
            "## Follow-ups and pitfalls\n\n"
            "### Follow-ups\n\n- First extension.\n- Second extension.\n- Third extension.\n\n"
            "### Pitfalls\n\n- First mistake.\n- Second mistake.\n- Third mistake.\n"
        )

        def issues(document: str) -> list:
            return _section_item_issues(ROOT, ROOT / "question.md", document, "system_design")

        self.assertEqual([], issues(combined))
        for heading in ("## Follow-ups", "## Pitfalls", "## Improvements"):
            with self.subTest(heading=heading):
                standalone = heading + "\n\n- One.\n- Two.\n- Three.\n"
                self.assertEqual([], issues(standalone))
                self.assertIn(
                    "has 4 items; maximum is 3",
                    "\n".join(str(issue) for issue in issues(standalone + "- Four.\n")),
                )
        for marker, label in (("### Pitfalls", "Follow-ups"), ("Third mistake.", "Pitfalls")):
            with self.subTest(label=label):
                replacement = (
                    "- Fourth extension.\n\n### Pitfalls"
                    if label == "Follow-ups" else "Third mistake.\n- Fourth mistake."
                )
                messages = "\n".join(str(issue) for issue in issues(combined.replace(marker, replacement)))
                self.assertIn(f"/ {label}' has 4 items; maximum is 3", messages)
        headed = combined.replace("- First extension.", "#### First extension").replace(
            "- Second extension.", "#### Second extension"
        ).replace("- Third extension.", "#### Third extension")
        self.assertEqual([], issues(headed))
        self.assertEqual(
            [], issues(combined.replace("### Follow-ups", "### Follow-up questions").replace(
                "### Pitfalls", "### Common pitfalls"
            ))
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
        shutil.copy2(ROOT / "editorial-memory.yaml", destination / "editorial-memory.yaml")
        for name in ("schemas", "taxonomy", "practice"):
            shutil.copytree(ROOT / name, destination / name)
        for content_type in ("system-design", "coding", "fundamentals"):
            shutil.copytree(
                ROOT / "content" / content_type,
                destination / "content" / content_type,
            )
        for reference in (ROOT / "content").glob("*.md"):
            shutil.copy2(reference, destination / "content" / reference.name)
        shutil.copytree(
            ROOT / "release1/handbook-markdown",
            destination / "release1/handbook-markdown",
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

    def test_system_design_patterns_are_optional_unique_and_controlled(self) -> None:
        for values, expected in (
            (None, None),
            (["scale-reads", "high-reliability"], None),
            (["invented-pattern"], "unknown taxonomy value 'invented-pattern'"),
            (["scale-reads", "scale-reads"], "items must be unique"),
        ):
            with self.subTest(values=values):
                def mutate(root: Path) -> None:
                    path = root / "content/system-design/sd-market-data-feed/metadata.yaml"
                    metadata = load_data(path)
                    if values is None:
                        metadata.pop("design_patterns", None)
                    else:
                        metadata["design_patterns"] = values
                    path.write_text(json.dumps(metadata) + "\n", encoding="utf-8")

                messages = self._issues_after(mutate)
                if expected:
                    self.assertIn(expected, messages)
                else:
                    self.assertEqual("", messages)

    def test_design_patterns_are_not_allowed_on_coding_metadata(self) -> None:
        metadata = load_data(ROOT / "tests/fixtures/valid/coding-metadata.yaml")
        metadata["design_patterns"] = ["scale-reads"]
        messages = "\n".join(
            str(issue)
            for issue in SchemaValidator(ROOT / "schemas").validate(
                metadata, ROOT / "schemas/coding.schema.json"
            )
        )
        self.assertIn("design_patterns: additional property is not allowed", messages)

    def test_system_design_still_requires_declared_diagrams(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "content/system-design/sd-market-data-feed/metadata.yaml"
            metadata = load_data(path)
            metadata["diagrams"] = []
            path.write_text(json.dumps(metadata) + "\n", encoding="utf-8")

        self.assertIn("diagrams: must contain at least 1", self._issues_after(mutate))

    def test_pattern_registry_rejects_duplicates_and_missing_guidance(self) -> None:
        original = load_data(ROOT / "taxonomy/design-patterns.yaml")
        for change, expected in (
            (lambda entries: entries.append(dict(entries[0])), "duplicate pattern ID"),
            (lambda entries: entries[0].pop("caveat"), "requires non-empty"),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "taxonomy").mkdir()
                registry = json.loads(json.dumps(original))
                change(registry["patterns"])
                (root / "taxonomy/design-patterns.yaml").write_text(
                    json.dumps(registry) + "\n", encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, expected):
                    _load_design_patterns(root)

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
