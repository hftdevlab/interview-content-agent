from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.content import GUIDE_SPECS
from tools.release import package_release


class ReleasePackagingTests(unittest.TestCase):
    def _root(self, parent: Path, name: str) -> Path:
        root = parent / name
        root.mkdir()
        (root / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        (root / "content").mkdir()
        dist = root / "dist"
        dist.mkdir()
        for spec in GUIDE_SPECS.values():
            (dist / spec["pdf"]).write_bytes(
                f"fixture:{spec['pdf']}\n".encode("ascii")
            )
        practice = root / "practice"
        practice.mkdir()
        (practice / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n", encoding="utf-8"
        )
        question = practice / "questions/example"
        question.mkdir(parents=True)
        (question / "README.md").write_text("# Example\n", encoding="utf-8")
        return root

    def test_release_contains_required_artifacts_and_valid_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = self._root(parent, "source")
            release = package_release(
                root=root,
                version="0.1.0",
                output_root=root / "releases",
                skip_build=True,
            )

            manifest = json.loads((release / "manifest.json").read_text())
            self.assertEqual(manifest["version"], "0.1.0")
            self.assertEqual(len([item for item in manifest["artifacts"] if item["kind"] == "pdf"]), 3)
            archive = release / "practice-repository-v0.1.0.tar.gz"
            with tarfile.open(archive, "r:gz") as bundle:
                names = bundle.getnames()
            self.assertIn("practice/CMakeLists.txt", names)
            self.assertIn("practice/questions/example/README.md", names)

            for line in (release / "SHA256SUMS").read_text().splitlines():
                expected, filename = line.split("  ", 1)
                actual = hashlib.sha256((release / filename).read_bytes()).hexdigest()
                self.assertEqual(actual, expected)

    def test_practice_archive_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            first_root = self._root(parent, "first")
            second_root = self._root(parent, "second")
            first = package_release(
                root=first_root,
                version="0.1.0",
                output_root=first_root / "releases",
                skip_build=True,
            )
            second = package_release(
                root=second_root,
                version="0.1.0",
                output_root=second_root / "releases",
                skip_build=True,
            )
            self.assertEqual(
                (first / "practice-repository-v0.1.0.tar.gz").read_bytes(),
                (second / "practice-repository-v0.1.0.tar.gz").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
