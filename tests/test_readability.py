from __future__ import annotations

import unittest

from tools.lint_readability import lint_text


GOOD = """# Title

## Section

A short paragraph that makes one point.

- a list item
- another item

![figure](a.svg)

Another short paragraph.

![figure](b.svg)
"""


class ReadabilityLintTests(unittest.TestCase):
    def test_short_structured_text_passes(self) -> None:
        report = lint_text(GOOD)
        self.assertEqual(0, report.errors)
        self.assertEqual(2, report.figures)
        self.assertEqual(1, report.lists)

    def test_long_paragraph_is_an_error(self) -> None:
        long_paragraph = " ".join(["word"] * 130) + "."
        report = lint_text(GOOD + "\n" + long_paragraph + "\n")
        self.assertTrue(any("paragraph has 130 words" in f.message for f in report.findings))
        self.assertGreaterEqual(report.errors, 1)

    def test_uninterrupted_prose_run_is_an_error(self) -> None:
        paragraph = " ".join(["word"] * 70) + "."
        wall = "\n\n".join([paragraph] * 6)
        report = lint_text(GOOD + "\n" + wall + "\n\n## Next\n")
        self.assertTrue(any("uninterrupted prose" in f.message for f in report.findings))

    def test_prose_run_before_a_bold_label_is_still_reported(self) -> None:
        paragraph = " ".join(["word"] * 60) + "."
        wall = "\n\n".join([paragraph] * 4)
        report = lint_text(GOOD + "\n" + wall + "\n\n**Label only.**\n\nShort.\n")
        self.assertTrue(any("240 words of uninterrupted prose" in f.message for f in report.findings))

    def test_prose_run_at_end_of_file_warns(self) -> None:
        paragraph = " ".join(["word"] * 60) + "."
        wall = "\n\n".join([paragraph] * 4)
        report = lint_text(GOOD + "\n" + wall + "\n")
        self.assertTrue(any("at end of file" in f.message and f.severity == "warn" for f in report.findings))

    def test_language_specific_code_warns(self) -> None:
        code = "```cpp\nstd::vector<std::unique_ptr<Iterator>> read(const Request& r);\n```\n"
        report = lint_text(GOOD + "\n" + code)
        self.assertTrue(any("language-specific constructs" in f.message for f in report.findings))
        self.assertEqual(0, report.errors)

    def test_pseudocode_does_not_warn(self) -> None:
        code = "```text\nread(series[], [t0, t1), columns[], as_of?)  ->  iterators\n```\n"
        report = lint_text(GOOD + "\n" + code)
        self.assertFalse(any("code block" in f.message for f in report.findings))

    def test_long_code_block_warns(self) -> None:
        code = "```text\n" + "\n".join(f"line {i}" for i in range(20)) + "\n```\n"
        report = lint_text(GOOD + "\n" + code)
        self.assertTrue(any("code block has 20 lines" in f.message for f in report.findings))

    def test_missing_figures_is_an_error(self) -> None:
        report = lint_text("# Title\n\nOne paragraph.\n")
        self.assertTrue(any("figures" in f.message for f in report.findings))
        self.assertEqual(0, lint_text("# Title\n\nOne paragraph.\n", min_figures=0).errors)

    def test_code_blocks_and_comments_are_not_prose(self) -> None:
        text = GOOD + "\n```\n" + "code " * 300 + "\n```\n<!-- " + "note " * 300 + " -->\n"
        report = lint_text(text)
        self.assertEqual(0, report.errors)


if __name__ == "__main__":
    unittest.main()
