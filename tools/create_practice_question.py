"""Create idempotent C++20 practice scaffolding and register it with CMake."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Iterable, Optional

from tools.content import PUBLICATION_STATUSES, ROOT, load_data
from tools.validate import validate_repository


REGISTRATION = re.compile(r"^add_subdirectory\(questions/([a-z0-9-]+)\)\s*$")


def _target_base(question_id: str) -> str:
    return re.sub(r"^(?:sd|code|fund)-", "", question_id).replace("-", "_")


def _namespace(question_id: str) -> str:
    return f"practice_{_target_base(question_id)}"


def _replace_section(markdown: str, heading: str, body: str) -> str:
    lines = markdown.splitlines()
    try:
        start = lines.index(heading)
    except ValueError as exc:
        raise ValueError(f"content is missing required heading {heading!r}") from exc
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    lines[start:end] = [heading, "", body.strip(), ""]
    return "\n".join(lines).rstrip() + "\n"


def _root_cmake_with_registration(cmake: str, question_id: str) -> str:
    registrations = {question_id}
    retained: list[str] = []
    for line in cmake.splitlines():
        match = REGISTRATION.match(line)
        if match:
            registrations.add(match.group(1))
        else:
            retained.append(line)
    while retained and not retained[-1].strip():
        retained.pop()
    retained.extend([""] + [f"add_subdirectory(questions/{item})" for item in sorted(registrations)])
    return "\n".join(retained) + "\n"


def _scaffold_files(question_id: str, title: str) -> dict[str, str]:
    base = _target_base(question_id)
    namespace = _namespace(question_id)
    starter_target = f"{base}_starter"
    solution_target = f"{base}_solution"
    test_target = f"{base}_test"
    header = f"""#pragma once

namespace {namespace} {{

int solve();

}}  // namespace {namespace}
"""
    starter = f"""#include \"exercise.hpp\"

namespace {namespace} {{

int solve() {{
    // TODO: replace this scaffold with the candidate implementation.
    return 0;
}}

}}  // namespace {namespace}
"""
    solution = f"""#include \"exercise.hpp\"

namespace {namespace} {{

int solve() {{
    return 1;
}}

}}  // namespace {namespace}
"""
    test = f"""#include \"exercise.hpp\"

#include <cstdlib>
#include <iostream>

int main() {{
    if ({namespace}::solve() != 1) {{
        std::cerr << \"FAILED: implement the question-specific behavior\\n\";
        return EXIT_FAILURE;
    }}
    std::cout << \"practice scaffold test passed\\n\";
    return EXIT_SUCCESS;
}}
"""
    cmake = f"""add_library({starter_target} STATIC
    starter/exercise.cpp
)
target_include_directories({starter_target} PUBLIC starter)

add_library({solution_target} STATIC
    solution/exercise.cpp
)
target_include_directories({solution_target} PUBLIC solution)

foreach(target {starter_target} {solution_target})
    practice_configure_target(${{target}})
endforeach()

add_executable({test_target}
    tests/exercise_test.cpp
)
target_link_libraries({test_target} PRIVATE {solution_target})
practice_configure_target({test_target})

add_executable({base}_starter_test
    tests/exercise_test.cpp
)
target_link_libraries({base}_starter_test PRIVATE {starter_target})
practice_configure_target({base}_starter_test)

add_test(NAME {test_target} COMMAND {test_target})
set_tests_properties({test_target} PROPERTIES LABELS \"solution\")

add_test(NAME {base}_starter_rejected COMMAND {base}_starter_test)
set_tests_properties(
    {base}_starter_rejected
    PROPERTIES
        WILL_FAIL TRUE
        LABELS \"starter-negative\"
)
"""
    readme = f"""# {title} practice

This generated C++20 scaffold separates candidate and reference targets. Replace
the generic `solve()` contract, solution, and behavioral test with the reviewed
question-specific API before publication.

From the repository root:

```bash
cmake -S practice -B build/practice
cmake --build build/practice --target {starter_target}
cmake --build build/practice --target {solution_target}
cmake --build build/practice --target {test_target}
ctest --test-dir build/practice -R {test_target} --output-on-failure
ctest --test-dir build/practice -R {base}_starter_rejected --output-on-failure
```

The starter-negative test is intentionally marked `WILL_FAIL`: the untouched
starter must fail the behavioral suite.
"""
    metadata = json.dumps(
        {
            "schema_version": 1,
            "question_id": question_id,
            "language": "C++20",
            "starter_target": starter_target,
            "solution_target": solution_target,
            "test_target": test_target,
        },
        indent=2,
    ) + "\n"
    return {
        "starter/exercise.hpp": header,
        "starter/exercise.cpp": starter,
        "solution/exercise.hpp": header,
        "solution/exercise.cpp": solution,
        "tests/exercise_test.cpp": test,
        "CMakeLists.txt": cmake,
        "README.md": readme,
        "metadata.yaml": metadata,
    }


def create_practice_question(*, root: Path, question_id: str) -> Path:
    root = root.resolve()
    matches = list((root / "content").glob(f"*/{question_id}/metadata.yaml"))
    if len(matches) != 1:
        raise ValueError(f"question ID {question_id!r} does not identify one package")
    metadata_path = matches[0]
    content_dir = metadata_path.parent
    metadata = dict(load_data(metadata_path))
    question_type = metadata.get("type")
    if question_type not in {"coding", "fundamentals"}:
        raise ValueError("practice scaffolding supports coding and fundamentals questions")
    if metadata.get("status") in PUBLICATION_STATUSES:
        raise ValueError("refuse to alter practice linkage for approved or published content")

    practice_dir = root / "practice" / "questions" / question_id
    created = not practice_dir.exists()
    if created:
        files = _scaffold_files(question_id, str(metadata["title"]))
        for relative, content in files.items():
            path = practice_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    else:
        required = {
            "CMakeLists.txt",
            "README.md",
            "metadata.yaml",
            "starter",
            "solution",
            "tests",
        }
        missing = sorted(item for item in required if not (practice_dir / item).exists())
        if missing:
            raise ValueError(
                "existing practice package is incomplete; refusing to overwrite: "
                + ", ".join(missing)
            )

    practice_metadata = load_data(practice_dir / "metadata.yaml")
    if question_type == "coding":
        metadata["practice"] = {
            "path": f"practice/questions/{question_id}",
            "cmake_target": practice_metadata["solution_target"],
            "test_target": practice_metadata["test_target"],
        }
        heading = "## Practice repository"
    else:
        metadata["runnable_experiment"] = {
            "path": f"practice/questions/{question_id}"
        }
        heading = "## Runnable experiment"

    question_path = content_dir / "question.md"
    old_metadata = metadata_path.read_text(encoding="utf-8")
    old_question = question_path.read_text(encoding="utf-8")
    root_cmake_path = root / "practice" / "CMakeLists.txt"
    old_cmake = root_cmake_path.read_text(encoding="utf-8")
    question = _replace_section(
        old_question,
        heading,
        f"[Runnable C++20 practice package](../../../practice/questions/{question_id}/README.md)",
    )
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    question_path.write_text(question, encoding="utf-8")
    root_cmake_path.write_text(
        _root_cmake_with_registration(old_cmake, question_id), encoding="utf-8"
    )

    issues = validate_repository(root)
    if issues:
        metadata_path.write_text(old_metadata, encoding="utf-8")
        question_path.write_text(old_question, encoding="utf-8")
        root_cmake_path.write_text(old_cmake, encoding="utf-8")
        if created:
            shutil.rmtree(practice_dir)
        rendered = "\n".join(f"- {issue}" for issue in issues)
        raise ValueError(f"practice creation failed validation and was rolled back:\n{rendered}")
    return practice_dir


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--id", required=True, dest="question_id")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        package = create_practice_question(root=args.root, question_id=args.question_id)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"practice package ready: {package.relative_to(args.root.resolve())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
