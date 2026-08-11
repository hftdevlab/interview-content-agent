from __future__ import annotations

import unittest

from tools.deduplicate import duplicate_candidates, normalize_text, report_dict
from tools.content import ROOT


class DeduplicationTests(unittest.TestCase):
    def test_normalization_is_case_and_punctuation_insensitive(self) -> None:
        self.assertEqual(
            normalize_text("Multi-Source Stream Merger!"),
            "multi source stream merger",
        )

    def test_exact_title_is_a_blocking_candidate(self) -> None:
        candidates = duplicate_candidates(
            root=ROOT,
            title="Merge Multiple Temporarily Available Ordered Record Sources",
            prompt="Merge ordered records from several sources.",
            question_type="coding",
        )
        self.assertTrue(candidates)
        self.assertEqual(
            candidates[0].question_id, "code-multi-source-stream-merger"
        )
        self.assertEqual(candidates[0].deterministic_score, 1.0)
        report = report_dict(
            title="Merge Multiple Temporarily Available Ordered Record Sources",
            question_type="coding",
            candidates=candidates,
        )
        self.assertIn(
            "code-multi-source-stream-merger", report["blocking_candidates"]
        )
        self.assertEqual(report["human_decision"], "pending")

    def test_unrelated_question_has_no_blocking_candidate(self) -> None:
        candidates = duplicate_candidates(
            root=ROOT,
            title="Calculate option settlement holidays",
            prompt="Given a civil calendar, calculate the next eligible settlement date.",
            question_type="coding",
        )
        report = report_dict(
            title="Calculate option settlement holidays",
            question_type="coding",
            candidates=candidates,
        )
        self.assertEqual(report["blocking_candidates"], [])
        self.assertEqual(report["human_decision"], "not_required")


if __name__ == "__main__":
    unittest.main()
