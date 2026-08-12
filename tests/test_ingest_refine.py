from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.ingest import ingest_question
from tools.create_practice_question import create_practice_question
from tools.refine import refine_question
from tools.validate import validate_repository


ROOT = Path(__file__).resolve().parents[1]


class IngestAndRefineTests(unittest.TestCase):
    def _root(self, temporary: str) -> Path:
        root = Path(temporary)
        shutil.copytree(ROOT / "schemas", root / "schemas")
        shutil.copytree(ROOT / "taxonomy", root / "taxonomy")
        shutil.copy2(ROOT / "editorial-memory.yaml", root / "editorial-memory.yaml")
        (root / "content").mkdir()
        return root

    def test_text_ingestion_preserves_source_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            source = root / "raw prompt.txt"
            source.write_text(
                "Design a bounded quote fan-out service.\n",
                encoding="utf-8",
            )
            package = ingest_question(
                root=root,
                question_kind="system-design",
                input_path=source,
                question_id="sd-quote-fanout",
                expert_note="Focus on slow-consumer isolation.",
            )

            metadata = json.loads((package / "metadata.yaml").read_text())
            self.assertEqual(metadata["status"], "normalized")
            self.assertEqual(metadata["source"]["input_type"], "text")
            copied = package / metadata["source"]["original_files"][0]
            self.assertEqual(copied.read_bytes(), source.read_bytes())
            self.assertEqual(validate_repository(root), [])

    def test_image_ingestion_flags_missing_transcription(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            image = root / "whiteboard.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\nexample")
            package = ingest_question(
                root=root,
                question_kind="coding",
                input_path=image,
                question_id="code-whiteboard-question",
                title="Whiteboard coding question",
            )

            question = (package / "question.md").read_text(encoding="utf-8")
            review = json.loads((package / "review.yaml").read_text())
            metadata = json.loads((package / "metadata.yaml").read_text())
            self.assertIn("[uncertain:", question)
            self.assertIn("has not been transcribed", review["review_notes"][1])
            self.assertIsNone(metadata["practice"])
            self.assertEqual(validate_repository(root), [])

    def test_refinement_changes_only_named_sections_and_resets_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            source = root / "source.txt"
            source.write_text(
                "Explain cache-line contention in a trading loop.\n",
                encoding="utf-8",
            )
            package = ingest_question(
                root=root,
                question_kind="fundamentals",
                input_path=source,
                question_id="fund-cache-contention",
                expert_note="Use a two-writer counter example.",
            )
            original = (package / "question.md").read_text(encoding="utf-8")
            revisions = root / "revisions.json"
            revisions.write_text(
                json.dumps(
                    {
                        "Deep explanation": (
                            "Two writers repeatedly invalidate one shared cache line. "
                            "Separate ownership before considering atomics."
                        )
                    }
                ),
                encoding="utf-8",
            )

            diff = refine_question(
                root=root,
                question_id="fund-cache-contention",
                revisions_path=revisions,
            )
            revised = (package / "question.md").read_text(encoding="utf-8")
            metadata = json.loads((package / "metadata.yaml").read_text())
            self.assertIn("Separate ownership", revised)
            self.assertIn("## Concise interview answer", revised)
            self.assertIn("+Two writers repeatedly", diff)
            self.assertNotEqual(original, revised)
            self.assertEqual(metadata["status"], "needs_human_review")
            self.assertTrue(metadata["review"]["agent_reviewed"])
            self.assertFalse(metadata["review"]["human_reviewed"])
            self.assertTrue(
                (root / "generated/refinement-diffs/fund-cache-contention.diff").is_file()
            )
            self.assertEqual(validate_repository(root), [])

    def test_practice_generation_is_registered_buildable_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            practice_root = root / "practice"
            practice_root.mkdir()
            cmake = (ROOT / "practice/CMakeLists.txt").read_text(encoding="utf-8")
            cmake = "\n".join(
                line
                for line in cmake.splitlines()
                if not line.startswith("add_subdirectory(questions/")
            ).rstrip() + "\n"
            (practice_root / "CMakeLists.txt").write_text(cmake, encoding="utf-8")
            source = root / "prompt.txt"
            source.write_text("Implement a bounded integer transform.\n", encoding="utf-8")
            content = ingest_question(
                root=root,
                question_kind="coding",
                input_path=source,
                question_id="code-bounded-transform",
                expert_note="Use a small value-semantic API.",
            )

            package = create_practice_question(
                root=root, question_id="code-bounded-transform"
            )
            starter_before = (package / "starter/exercise.cpp").read_text()
            second = create_practice_question(
                root=root, question_id="code-bounded-transform"
            )
            self.assertEqual(package, second)
            self.assertEqual(
                starter_before, (package / "starter/exercise.cpp").read_text()
            )
            metadata = json.loads((content / "metadata.yaml").read_text())
            self.assertEqual(
                metadata["practice"]["path"],
                "practice/questions/code-bounded-transform",
            )
            self.assertEqual(validate_repository(root), [])

            build = root / "build"
            subprocess.run(
                ["cmake", "-S", str(practice_root), "-B", str(build)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["cmake", "--build", str(build)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["ctest", "--test-dir", str(build), "--output-on-failure"],
                check=True,
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    unittest.main()
