from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.content import (
    GUIDE_SPECS,
    ROOT,
    discover_questions,
    question_anchor,
    questions_by_type,
)
from tools.generate_catalog import generate_catalogs


class CatalogGenerationTests(unittest.TestCase):
    def test_all_catalogs_include_counts_and_stable_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            outputs = generate_catalogs(ROOT, output_root)

            self.assertEqual(3, len(outputs))
            self.assertEqual(
                {spec["catalog"] for spec in GUIDE_SPECS.values()},
                {path.name for path in outputs},
            )

            coding = (output_root / "coding-catalog.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("Category counts", coding)
            self.assertIn("Difficulty counts", coding)
            self.assertIn("| Algorithms | 1 |", coding)
            self.assertIn(
                "../markdown/coding-interview-guide.md"
                "#code-multi-source-stream-merger",
                coding,
            )

    def test_repository_ordering_is_deterministic(self) -> None:
        records = discover_questions(ROOT)
        first = questions_by_type(records, ROOT)
        second = questions_by_type(list(reversed(records)), ROOT)
        for question_type in GUIDE_SPECS:
            self.assertEqual(
                [record.question_id for record in first[question_type]],
                [record.question_id for record in second[question_type]],
            )

    def test_anchor_does_not_depend_on_title_or_difficulty(self) -> None:
        self.assertEqual(
            "code-multi-source-stream-merger",
            question_anchor("code-multi-source-stream-merger"),
        )


if __name__ == "__main__":
    unittest.main()

