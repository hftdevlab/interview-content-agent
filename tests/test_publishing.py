from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from tools.build_pdfs import _styles, build_all_pdfs, markdown_flowables
from tools.content import ROOT, QuestionRecord
from tools.render_diagrams import main as render_diagrams
from tools.validate_pdfs import validate_pdf_outputs


class PdfPublishingTests(unittest.TestCase):
    def test_heading_stays_with_first_list_item_and_long_lists_split(self) -> None:
        from pypdf import PdfReader
        from reportlab.platypus import SimpleDocTemplate, Spacer

        for ordered in (False, True):
            for item_count in (1, 2, 24):
                with self.subTest(ordered=ordered, item_count=item_count):
                    items = []
                    for number in range(1, item_count + 1):
                        marker = f"{number}." if ordered else "-"
                        items.append(
                            f"{marker} Item-{number:02d} marker. "
                            + "Explanation with useful detail. " * 6
                        )
                    record = QuestionRecord(
                        metadata_path=Path("/unused/metadata.yaml"),
                        package_dir=Path("/unused"),
                        metadata={"id": "sd-list", "type": "system_design", "diagrams": []},
                        markdown="# Fixture\n\n## Follow-up marker\n\n" + "\n".join(items),
                    )
                    output = BytesIO()
                    document = SimpleDocTemplate(
                        output, pagesize=(300, 300), leftMargin=20,
                        rightMargin=20, topMargin=20, bottomMargin=20,
                    )
                    # There is room for the heading, but not for its first item.
                    document.build([
                        Spacer(1, 195),
                        *markdown_flowables(record, _styles("#0F6B78"), 700, 248),
                    ])
                    pages = [page.extract_text() or "" for page in PdfReader(output).pages]
                    heading_page = next(page for page in pages if "Follow-up marker" in page)
                    self.assertIn("Item-01 marker", heading_page)
                    all_text = "\n".join(pages)
                    for number in range(1, item_count + 1):
                        self.assertEqual(all_text.count(f"Item-{number:02d} marker"), 1)
                    if ordered and item_count > 1:
                        # Splitting after the first item must not restart numbering.
                        self.assertIn("2\nItem-02 marker", all_text)
                    if item_count == 24:
                        self.assertGreater(len(pages), 3)

    def _make_root(self, destination: Path) -> Path:
        shutil.copy2(ROOT / "pyproject.toml", destination / "pyproject.toml")
        shutil.copytree(ROOT / "taxonomy", destination / "taxonomy")
        for content_type in ("system-design", "coding", "fundamentals"):
            source = ROOT / "content" / content_type
            shutil.copytree(source, destination / "content" / content_type)
        return destination

    def test_publication_requires_status_and_all_review_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._make_root(Path(temporary))
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

            build_all_pdfs(root)
            coding_pdf = root / "dist" / "coding-interview-guide.pdf"
            self.assertEqual([], validate_pdf_outputs(root))
            from pypdf import PdfReader

            text = "\n".join(
                page.extract_text() or "" for page in PdfReader(coding_pdf).pages
            )
            self.assertNotIn("code-multi-source-stream-merger", text)

            metadata["review"] = {
                "agent_reviewed": True,
                "human_reviewed": True,
                "technical_accuracy_reviewed": True,
                "interview_realism_reviewed": True,
            }
            metadata_path.write_text(
                json.dumps(metadata, indent=2) + "\n",
                encoding="utf-8",
            )
            build_all_pdfs(root)
            self.assertEqual([], validate_pdf_outputs(root))
            text = "\n".join(
                page.extract_text() or "" for page in PdfReader(coding_pdf).pages
            )
            self.assertIn("code-multi-source-stream-merger", text)

    def test_review_preview_preserves_running_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._make_root(Path(temporary))
            render_diagrams(["--root", str(root)])

            build_all_pdfs(root, review_preview=True)

            self.assertEqual(
                [],
                validate_pdf_outputs(root, review_preview=True),
            )
            from pypdf import PdfReader

            system_design_pdf = (
                root / "generated" / "pdf-preview" / "system-design-guide.pdf"
            )
            pages = PdfReader(system_design_pdf).pages
            text = "\n".join(page.extract_text() or "" for page in pages)
            self.assertNotIn("|---|", text)
            for page in pages[1:]:
                stream = page.get_contents().get_data()
                self.assertGreater(
                    stream.rfind(b"System Design Interview Guide"),
                    len(stream) // 2,
                )

    def test_blockquote_markers_do_not_leak_into_rendered_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            record = QuestionRecord(
                metadata_path=package / "metadata.yaml",
                package_dir=package,
                metadata={"id": "sd-quote", "type": "system_design", "diagrams": []},
                markdown=(
                    "# Quote fixture\n\n"
                    "> Gate7 may use one complete committed version, and\n"
                    "> must become stale when proof expires.\n"
                ),
            )

            flowables = markdown_flowables(
                record,
                _styles("#0F6B78"),
                diagram_width=700,
                body_width=450,
            )

            self.assertEqual(len(flowables), 1)
            self.assertEqual(
                flowables[0].getPlainText(),
                "Gate7 may use one complete committed version, and must become stale when proof expires.",
            )

    def test_short_markdown_table_is_kept_as_one_reader_unit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            record = QuestionRecord(
                metadata_path=package / "metadata.yaml",
                package_dir=package,
                metadata={"id": "sd-table", "type": "system_design", "diagrams": []},
                markdown=(
                    "# Table fixture\n\n"
                    "| Failure | Expected outcome |\n"
                    "|---|---|\n"
                    "| Slow reader | Disconnect it. |\n"
                ),
            )

            flowables = markdown_flowables(
                record,
                _styles("#0F6B78"),
                diagram_width=700,
                body_width=450,
            )

            self.assertEqual(len(flowables), 1)
            self.assertEqual(type(flowables[0]).__name__, "KeepTogether")
            table = flowables[0]._content[0]
            self.assertEqual(type(table).__name__, "Table")
            self.assertEqual(
                [[cell.getPlainText() for cell in row] for row in table._cellvalues],
                [["Failure", "Expected outcome"], ["Slow reader", "Disconnect it."]],
            )


if __name__ == "__main__":
    unittest.main()
