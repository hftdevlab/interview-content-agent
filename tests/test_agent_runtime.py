from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tools.agent_runtime import (
    AgentResult,
    CodexExecRunner,
    _is_recoverable_diagnostic,
    _progress_summary,
)


class AgentRuntimeTests(unittest.TestCase):
    def test_known_incompatible_models_cache_diagnostic_is_suppressed(self) -> None:
        self.assertTrue(
            _is_recoverable_diagnostic(
                "ERROR codex_models_manager::cache: failed to load models cache: "
                "missing field `base_instructions` at line 94 column 5"
            )
        )
        self.assertFalse(_is_recoverable_diagnostic("ERROR authentication failed"))

    def test_structured_agent_summary_becomes_progress_text(self) -> None:
        self.assertEqual(
            _progress_summary('{"outcome":"ready","summary":"Focused revision done."}'),
            "Focused revision done.",
        )
        self.assertEqual(_progress_summary("not JSON"), "")

    def test_new_thread_uses_requested_sandbox_and_schema(self) -> None:
        runner = CodexExecRunner(codex_bin="/opt/codex")
        result = AgentResult("thread-1", "{}", ())

        with patch("tools.agent_runtime._consume", return_value=result) as consume:
            runner.run(
                "draft",
                root=Path("/tmp/repository"),
                sandbox="workspace-write",
                images=[Path("/tmp/question.png")],
                output_schema=Path("/tmp/output.schema.json"),
            )

        command = consume.call_args.args[0]
        self.assertEqual(command[:3], ["/opt/codex", "exec", "--json"])
        self.assertIn("workspace-write", command)
        self.assertIn(str(Path("/tmp/question.png").resolve()), command)
        self.assertIn(str(Path("/tmp/output.schema.json").resolve()), command)

    def test_resume_uses_only_supported_resume_options(self) -> None:
        runner = CodexExecRunner(codex_bin="/opt/codex")
        result = AgentResult("thread-1", "{}", ())

        with patch("tools.agent_runtime._consume", return_value=result) as consume:
            runner.resume(
                "thread-1",
                "revise",
                root=Path("/tmp/repository"),
                output_schema=Path("/tmp/output.schema.json"),
            )

        command = consume.call_args.args[0]
        self.assertEqual(command[:2], ["/opt/codex", "exec"])
        self.assertIn("workspace-write", command)
        self.assertEqual(command[command.index("resume") + 1], "--json")
        self.assertEqual(command[-2:], ["thread-1", "revise"])


if __name__ == "__main__":
    unittest.main()
