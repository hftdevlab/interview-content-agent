from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.validate import ROOT, validate_repository


class TrackKnowledgeGraphTests(unittest.TestCase):
    def _issues_after(self, mutation) -> str:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("schemas", "taxonomy", "practice", "content", "generated", "release1"):
                if (ROOT / name).exists():
                    shutil.copytree(ROOT / name, root / name)
            mutation(root)
            return "\n".join(str(issue) for issue in validate_repository(root))

    @staticmethod
    def _edit_metadata(root: Path, question_id: str, edit) -> None:
        path = root / "content" / "system-design" / question_id / "metadata.yaml"
        data = json.loads(path.read_text(encoding="utf-8"))
        edit(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def test_move_introduced_twice_is_rejected(self) -> None:
        def mutate(root: Path) -> None:
            self._edit_metadata(
                root,
                "sd-news-feed",
                lambda d: d["design_moves"]["introduces"].append("idempotency-key"),
            )

        self.assertIn("'idempotency-key' is introduced by 'sd-notification-system'", self._issues_after(mutate))

    def test_unknown_move_is_rejected(self) -> None:
        def mutate(root: Path) -> None:
            self._edit_metadata(
                root,
                "sd-news-feed",
                lambda d: d["design_moves"]["reuses"].append("not-a-move"),
            )

        self.assertIn("unknown design move 'not-a-move'", self._issues_after(mutate))

    def test_question_number_reference_is_rejected(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "content" / "system-design" / "sd-news-feed" / "question.md"
            path.write_text(path.read_text(encoding="utf-8") + "\nAs we saw in Q2, batching helps.\n", encoding="utf-8")

        self.assertIn("refer to other questions by title, not as 'Q2'", self._issues_after(mutate))

    def test_introduced_move_needs_a_callout(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "content" / "system-design" / "sd-news-feed" / "question.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("Design move — Normalize at the edge", "Normalize at the edge"), encoding="utf-8")

        self.assertIn("has no 'Design move — Normalize at the edge, keep the raw' callout", self._issues_after(mutate))

    def test_unknown_handbook_chapter_is_rejected(self) -> None:
        def mutate(root: Path) -> None:
            self._edit_metadata(
                root,
                "sd-risk-limit-fanout",
                lambda d: d["handbook_chapters"].append("z9-not-a-chapter"),
            )

        self.assertIn("unknown handbook chapter 'z9-not-a-chapter'", self._issues_after(mutate))


if __name__ == "__main__":
    unittest.main()


class TrackMapTests(unittest.TestCase):
    def test_map_draws_only_strong_links_and_shows_levels(self) -> None:
        from tools.build_track_map import build_dot

        moves = {
            "a": {"label": "Move A", "introduced_in": "q1"},
            "b": {"label": "Move B", "introduced_in": "q1"},
            "c": {"label": "Move C", "introduced_in": "q1"},
        }
        records = [
            {"id": "q1", "title": "Design One", "short_title": "One", "difficulty": 2, "track_order": 1,
             "design_moves": {"introduces": ["a", "b", "c"], "reuses": []}},
            {"id": "q2", "title": "Design Two", "short_title": "Two", "difficulty": 3, "track_order": 2,
             "design_moves": {"introduces": [], "reuses": ["a", "b"]}},
            {"id": "q3", "title": "Design Three", "short_title": "Three", "difficulty": 4, "track_order": 3,
             "design_moves": {"introduces": [], "reuses": ["c"]}},
        ]
        dot = build_dot(records, moves)
        self.assertIn('"q1" -> "q2"', dot)
        self.assertNotIn('"q1" -> "q3"', dot)
        self.assertIn("One · Foundation", dot)
        self.assertIn("Three · Advanced", dot)
