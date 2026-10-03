from __future__ import annotations

import tempfile
import unittest
import json
from dataclasses import replace
from pathlib import Path

from tools.content import (
    GUIDE_SPECS,
    ROOT,
    discover_questions,
    question_anchor,
    questions_by_type,
)
from tools.generate_catalog import generate_catalogs, render_catalog_markdown


class CatalogGenerationTests(unittest.TestCase):
    def test_patterns_add_a_stable_linked_index_without_changing_legacy_catalogs(self) -> None:
        source = [
            record
            for record in discover_questions(ROOT)
            if record.question_type == "system_design"
        ][:2]
        records = [
            replace(record, metadata={**record.metadata, "design_patterns": ["scale-reads"]})
            for record in source
        ]
        forward = render_catalog_markdown(
            "system_design", records, link_prefix="guide.md"
        )
        reverse = render_catalog_markdown(
            "system_design", list(reversed(records)), link_prefix="guide.md"
        )
        index = forward.split("## Design patterns\n", 1)[1].split("## Questions\n", 1)[0]
        reverse_index = reverse.split("## Design patterns\n", 1)[1].split(
            "## Questions\n", 1
        )[0]
        self.assertEqual(index, reverse_index)
        self.assertIn("### Scale reads", index)
        self.assertIn('<a id="pattern-scale-reads"></a>', index)
        for record in records:
            self.assertIn(f"[{record.title}](guide.md#{record.question_id})", index)
        legacy = [
            replace(
                record,
                metadata={
                    key: value for key, value in record.metadata.items()
                    if key != "design_patterns"
                },
            )
            for record in source
        ]
        self.assertNotIn(
            "Design patterns",
            render_catalog_markdown("system_design", legacy, link_prefix="guide.md"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "taxonomy").mkdir()
            (root / "taxonomy/design-patterns.yaml").write_text(
                json.dumps({"patterns": [{"id": "scale-reads", "label": "Read scaling"}]}),
                encoding="utf-8",
            )
            custom = render_catalog_markdown(
                "system_design", records, link_prefix="guide.md", root=root
            )
            self.assertIn("### Read scaling", custom)
            self.assertIn('<a id="pattern-scale-reads"></a>', custom)

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
