from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.build_pdfs import _styles, build_all_pdfs, markdown_flowables
from tools.content import ROOT, QuestionRecord
from tools.render_diagrams import main as render_diagrams
from tools.validate_pdfs import validate_pdf_outputs


class PdfPublishingTests(unittest.TestCase):
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

    def test_review_preview_renders_markdown_tables(self) -> None:
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
            self.assertIn("Failure\nExpected outcome", text)
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


if __name__ == "__main__":
    unittest.main()
