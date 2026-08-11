"""Build deterministic, versioned release artifacts from approved content."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Iterable, Mapping, Optional

from tools.content import (
    GUIDE_SPECS,
    ROOT,
    discover_questions,
    is_publication_ready,
    load_project_version,
)


VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
EXCLUDED_ARCHIVE_NAMES = frozenset({".DS_Store", "__pycache__"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tar_info(path: Path, archive_name: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(archive_name)
    stat = path.stat()
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    if path.is_dir():
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
    else:
        info.size = stat.st_size
        info.mode = 0o755 if stat.st_mode & 0o111 else 0o644
    return info


def _archive_practice(root: Path, destination: Path) -> None:
    practice = root / "practice"
    paths = [practice]
    paths.extend(
        sorted(
            path
            for path in practice.rglob("*")
            if not any(part in EXCLUDED_ARCHIVE_NAMES for part in path.parts)
        )
    )
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for path in paths:
                    name = path.relative_to(root).as_posix()
                    info = _tar_info(path, name)
                    if path.is_file():
                        with path.open("rb") as stream:
                            archive.addfile(info, stream)
                    else:
                        archive.addfile(info)


def _version_key(value: str) -> tuple[int, int, int, str]:
    core, _, suffix = value.removeprefix("v").partition("-")
    major, minor, patch = (int(item) for item in core.split("."))
    return major, minor, patch, suffix


def _previous_manifest(releases_root: Path, version: str) -> Optional[Mapping[str, object]]:
    candidates: list[tuple[tuple[int, int, int, str], Path]] = []
    for path in releases_root.glob("v*/manifest.json"):
        candidate = path.parent.name
        try:
            key = _version_key(candidate)
        except (ValueError, TypeError):
            continue
        if key < _version_key(version):
            candidates.append((key, path))
    if not candidates:
        return None
    _, path = max(candidates, key=lambda item: item[0])
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def _change_summary(
    version: str,
    included: list[Mapping[str, str]],
    previous: Optional[Mapping[str, object]],
) -> str:
    current_by_id = {item["id"]: item for item in included}
    previous_items = previous.get("included_questions", []) if previous else []
    previous_by_id = {
        str(item.get("id")): item
        for item in previous_items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    added = sorted(set(current_by_id) - set(previous_by_id))
    removed = sorted(set(previous_by_id) - set(current_by_id))
    retained = sorted(set(current_by_id) & set(previous_by_id))
    lines = [f"# Release {version}", ""]
    if previous:
        lines.append(f"Compared with release {previous.get('version', 'unknown')}.")
    else:
        lines.append("Initial packaged release; no previous manifest was found.")
    lines.extend(["", "## Question changes", ""])
    lines.append("- Added: " + (", ".join(added) if added else "none"))
    lines.append("- Removed: " + (", ".join(removed) if removed else "none"))
    lines.append("- Retained: " + (", ".join(retained) if retained else "none"))
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- Three approved-only interview guide PDFs.",
            "- Runnable C++20 practice repository archive.",
            "- Machine-readable manifest and SHA-256 checksums.",
            "",
        ]
    )
    return "\n".join(lines)


def _artifact_record(path: Path, kind: str) -> dict[str, object]:
    return {
        "path": path.name,
        "kind": kind,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def package_release(
    *,
    root: Path,
    version: str,
    output_root: Optional[Path] = None,
    skip_build: bool = False,
) -> Path:
    root = root.resolve()
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError("version must use semantic form such as 0.1.0")
    project_version = load_project_version(root)
    if version != project_version:
        raise ValueError(
            f"release version {version!r} must match pyproject version {project_version!r}"
        )
    if not skip_build:
        subprocess.run(
            ["make", "all", f"PYTHON={sys.executable}"],
            cwd=root,
            check=True,
        )

    releases_root = (output_root or (root / "dist" / "releases")).resolve()
    releases_root.mkdir(parents=True, exist_ok=True)
    final_dir = releases_root / f"v{version}"
    if final_dir.exists():
        raise ValueError(f"release already exists: {final_dir}")

    previous = _previous_manifest(releases_root, version)
    ready = sorted(
        (record for record in discover_questions(root, include_private=False) if is_publication_ready(record)),
        key=lambda record: record.question_id,
    )
    included = [
        {
            "id": record.question_id,
            "type": record.question_type,
            "title": record.title,
            "status": str(record.metadata["status"]),
        }
        for record in ready
    ]

    with tempfile.TemporaryDirectory(dir=releases_root) as temporary:
        staging = Path(temporary) / f"v{version}"
        staging.mkdir()
        artifact_records: list[dict[str, object]] = []
        for spec in GUIDE_SPECS.values():
            source = root / "dist" / spec["pdf"]
            if not source.is_file():
                raise ValueError(f"missing built PDF: {source}")
            destination = staging / f"{source.stem}-v{version}.pdf"
            shutil.copyfile(source, destination)
            artifact_records.append(_artifact_record(destination, "pdf"))

        practice_archive = staging / f"practice-repository-v{version}.tar.gz"
        _archive_practice(root, practice_archive)
        artifact_records.append(_artifact_record(practice_archive, "practice-archive"))

        summary = staging / "CHANGE_SUMMARY.md"
        summary.write_text(
            _change_summary(version, included, previous), encoding="utf-8"
        )
        artifact_records.append(_artifact_record(summary, "change-summary"))

        manifest = {
            "schema_version": 1,
            "version": version,
            "project_version": project_version,
            "included_questions": included,
            "artifacts": sorted(artifact_records, key=lambda item: str(item["path"])),
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        hash_paths = sorted(
            path for path in staging.iterdir() if path.name != "SHA256SUMS"
        )
        (staging / "SHA256SUMS").write_text(
            "".join(f"{_sha256(path)}  {path.name}\n" for path in hash_paths),
            encoding="ascii",
        )
        os.replace(staging, final_dir)
    return final_dir


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--skip-build", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        release_dir = package_release(
            root=args.root,
            version=args.version,
            output_root=args.output_root,
            skip_build=args.skip_build,
        )
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"packaged release: {release_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
