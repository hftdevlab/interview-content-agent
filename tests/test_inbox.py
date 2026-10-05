from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from tools.inbox import InboxError, parse_inbox_file, pending_items
from tools.validate import validate_repository
from tools.workflow import WorkflowError, process_inbox


ROOT = Path(__file__).resolve().parents[1]

TEMPLATE_STYLE = """---
title: Bounded order audit stream
id: sd-order-audit-stream
---

## Prompt

> Design a bounded order audit stream.

## Notes

Read this as an internal compliance feed. Go deep on loss policy.
"""


class InboxParsingTests(unittest.TestCase):
    def _write(self, directory: Path, name: str, text: str) -> Path:
        path = directory / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_bare_file_is_the_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._write(Path(temporary), "q.md", "Design a price dashboard.\n")
            item = parse_inbox_file(path, "system-design")
            self.assertEqual(item.prompt, "Design a price dashboard.")
            self.assertEqual(item.notes, "")
            self.assertFalse(item.needs_prompt_only_copy)

    def test_template_splits_front_matter_prompt_and_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._write(Path(temporary), "q.md", TEMPLATE_STYLE)
            item = parse_inbox_file(path, "system-design")
            self.assertEqual(item.prompt, "Design a bounded order audit stream.")
            self.assertIn("loss policy", item.notes)
            self.assertEqual(item.title, "Bounded order audit stream")
            self.assertEqual(item.question_id, "sd-order-audit-stream")
            self.assertTrue(item.needs_prompt_only_copy)

    def test_unknown_front_matter_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._write(Path(temporary), "q.md", "---\nowner: me\n---\nDesign X.\n")
            with self.assertRaisesRegex(InboxError, "unknown front matter key"):
                parse_inbox_file(path, "system-design")

    def test_empty_prompt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._write(Path(temporary), "q.md", "## Notes\nOnly notes here.\n")
            with self.assertRaisesRegex(InboxError, "no prompt"):
                parse_inbox_file(path, "system-design")

    def test_pending_items_skip_readme_and_order_by_age(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "inbox" / "system-design"
            folder.mkdir(parents=True)
            (root / "inbox" / "README.md").write_text("# Inbox\n", encoding="utf-8")
            (folder / "README.md").write_text("ignored\n", encoding="utf-8")
            older = self._write(folder, "b.md", "Design B.\n")
            newer = self._write(folder, "a.md", "Design A.\n")
            now = time.time()
            os.utime(older, (now - 60, now - 60))
            os.utime(newer, (now, now))
            (root / "inbox" / "stray.md").write_text("not in a type folder\n", encoding="utf-8")
            items = pending_items(root)
            self.assertEqual([item.path.name for item in items], ["b.md", "a.md"])


class InboxWorkflowTests(unittest.TestCase):
    def _root(self, temporary: str) -> Path:
        root = Path(temporary)
        shutil.copytree(ROOT / "schemas", root / "schemas")
        shutil.copytree(ROOT / "taxonomy", root / "taxonomy")
        shutil.copy2(ROOT / "editorial-memory.yaml", root / "editorial-memory.yaml")
        (root / "content").mkdir()
        (root / "inbox" / "system-design").mkdir(parents=True)
        return root

    def test_offline_intake_archives_notes_and_moves_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            inbox_file = root / "inbox" / "system-design" / "audit.md"
            inbox_file.write_text(TEMPLATE_STYLE, encoding="utf-8")

            packages = process_inbox(
                root=root, runner=None, create_branch=False, run_agent=False
            )

            self.assertEqual(len(packages), 1)
            package = packages[0]
            self.assertEqual(package.name, "sd-order-audit-stream")
            notes = (package / "expert-notes.md").read_text(encoding="utf-8")
            self.assertIn("loss policy", notes)
            question = (package / "question.md").read_text(encoding="utf-8")
            self.assertIn("Design a bounded order audit stream.", question)
            self.assertNotIn("loss policy", question)
            metadata = json.loads((package / "metadata.yaml").read_text(encoding="utf-8"))
            self.assertIn("source/inbox-audit.md", metadata["source"]["original_files"])
            self.assertTrue((package / "source" / "inbox-audit.md").is_file())
            self.assertFalse(inbox_file.exists())
            processed = list((root / "inbox" / "processed").glob("*audit.md"))
            self.assertEqual(len(processed), 1)
            workflow = json.loads((package / "workflow.yaml").read_text(encoding="utf-8"))
            self.assertIn("inbox_file_processed", [event["type"] for event in workflow["events"]])
            self.assertEqual(validate_repository(root), [])
            self.assertEqual(pending_items(root), [])

    def test_batch_with_branches_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            folder = root / "inbox" / "system-design"
            (folder / "one.md").write_text("Design one thing.\n", encoding="utf-8")
            (folder / "two.md").write_text("Design another thing.\n", encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "one file per run"):
                process_inbox(
                    root=root,
                    runner=None,
                    process_all=True,
                    create_branch=True,
                    run_agent=False,
                )
            self.assertEqual(len(pending_items(root)), 2)


if __name__ == "__main__":
    unittest.main()
