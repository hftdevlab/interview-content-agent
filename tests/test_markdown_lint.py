from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.lint_markdown import lint_file


class MarkdownLintTests(unittest.TestCase):
    def test_valid_markdown_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "valid.md"
            path.write_text("# Heading\n\n```cpp\nint value = 1;\n```\n", encoding="utf-8")
            self.assertEqual(lint_file(path), [])

    def test_unclosed_fence_and_bad_heading_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.md"
            path.write_text("#Bad\n\n```cpp\n", encoding="utf-8")
            issues = lint_file(path)
            self.assertTrue(any("heading marker" in issue for issue in issues))
            self.assertTrue(any("unclosed" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
