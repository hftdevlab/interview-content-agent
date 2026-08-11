from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.build_pdfs import build_all_pdfs
from tools.content import ROOT
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


if __name__ == "__main__":
    unittest.main()

