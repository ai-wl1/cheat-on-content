#!/usr/bin/env python3
"""Local tests for the prediction guard. No network and no adapter scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prediction_guard as guard

ROOT = Path(__file__).resolve().parent
HOOK = ROOT / "prediction-immutability.sh"


def _prediction(body: str) -> str:
    return textwrap.dedent(body).lstrip("\n")


SAMPLE = _prediction(
    """
    # title

    header line

    ## 预测
    secret alpha
    still secret

    ## 复盘
    retro visible

    ## 预测 v2
    second secret

    ## 其他
    tail note
    """
)


class GuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        self.pred = self.cwd / "predictions"
        self.pred.mkdir()
        self.file = self.pred / "2026-01-01_abc_post.md"
        self.file.write_text(SAMPLE, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def decide(self, payload: object) -> guard.Decision:
        override = self.cwd
        if isinstance(payload, dict):
            raw_cwd = payload.get("cwd")
            if isinstance(raw_cwd, str) and raw_cwd.strip():
                override = Path(raw_cwd)
            else:
                payload["cwd"] = str(self.cwd)
        return guard.decide(payload, cwd=override)

    def edit(self, old: str, path: Path | None = None) -> guard.Decision:
        return self.decide(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(path or self.file),
                    "old_string": old,
                    "new_string": "rewritten",
                },
            }
        )

    def test_edit_outside_prediction_sections_allowed(self) -> None:
        self.assertTrue(self.edit("header line").allow)
        self.assertTrue(self.edit("retro visible").allow)
        self.assertTrue(self.edit("tail note").allow)

    def test_edit_inside_every_prediction_section_denied(self) -> None:
        self.assertFalse(self.edit("secret alpha").allow)
        self.assertFalse(self.edit("second secret").allow)

    def test_cross_section_and_duplicate_text_denied(self) -> None:
        self.assertFalse(self.edit("still secret\n\n## 复盘").allow)
        self.file.write_text(SAMPLE.replace("secret alpha", "dup").replace("retro visible", "dup"), encoding="utf-8")
        self.assertFalse(self.edit("dup").allow)

    def test_missing_match_empty_old_string_and_missing_heading_denied(self) -> None:
        self.assertFalse(self.edit("not in file").allow)
        self.assertFalse(self.edit("").allow)
        self.file.write_text("no headings here\n", encoding="utf-8")
        self.assertFalse(self.edit("no headings here").allow)

    def test_multiline_match_inside_section_denied(self) -> None:
        self.assertFalse(self.edit("secret alpha\nstill secret").allow)

    def test_write_new_allowed_and_overwrite_denied(self) -> None:
        new_path = self.pred / "new.md"
        created = self.decide(
            {"tool_name": "Write", "tool_input": {"file_path": str(new_path), "content": SAMPLE}}
        )
        self.assertTrue(created.allow)
        overwritten = self.decide(
            {"tool_name": "Write", "tool_input": {"file_path": str(self.file), "content": "nope"}}
        )
        self.assertFalse(overwritten.allow)

    def test_path_normalization_and_symlink(self) -> None:
        outside = self.cwd / "notes.md"
        outside.write_text("safe\n", encoding="utf-8")
        escaped = self.decide(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": "predictions/../notes.md",
                    "old_string": "safe",
                    "new_string": "x",
                },
            }
        )
        self.assertTrue(escaped.allow)

        nested = self.cwd / "wrap" / "inner"
        nested.mkdir(parents=True)
        relative = self.decide(
            {
                "tool_name": "Edit",
                "cwd": str(nested),
                "tool_input": {
                    "file_path": "../../predictions/2026-01-01_abc_post.md",
                    "old_string": "secret alpha",
                    "new_string": "x",
                },
            }
        )
        self.assertFalse(relative.allow)

        link_dir = self.cwd / "elsewhere"
        link_dir.mkdir()
        link = link_dir / "link.md"
        link.symlink_to(self.file)
        via_link = self.edit("secret alpha", link)
        self.assertFalse(via_link.allow)

        dotted = self.edit("secret alpha", self.cwd / "predictions" / "." / self.file.name)
        self.assertFalse(dotted.allow)

    def test_other_write_tools_and_unknown_tools(self) -> None:
        self.assertTrue(
            self.decide({"tool_name": "Read", "tool_input": {"file_path": str(self.file)}}).allow
        )
        self.assertFalse(
            self.decide({"tool_name": "Delete", "tool_input": {"path": str(self.file)}}).allow
        )
        self.assertFalse(
            self.decide(
                {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": str(self.file)}}
            ).allow
        )
        self.assertFalse(self.decide({"tool_name": "Edit", "tool_input": {}}).allow)
        self.assertFalse(self.decide({"tool_name": "", "tool_input": {}}).allow)
        self.assertFalse(self.decide(["not", "an", "object"]).allow)
        self.assertFalse(
            self.decide(
                {
                    "tool_name": "Task",
                    "tool_input": {"prompt": "edit predictions/2026-01-01_abc_post.md"},
                }
            ).allow
        )
        self.assertTrue(self.decide({"tool_name": "CustomTool", "tool_input": {"query": "hello"}}).allow)
        self.assertFalse(
            self.decide(
                {
                    "tool_name": "ApplyPatch",
                    "tool_input": {"patch": "*** Update File: predictions/a.md\n"},
                }
            ).allow
        )
        inside = self.decide(
            {
                "cwd": str(self.pred),
                "tool_name": "ApplyPatch",
                "tool_input": {"patch": "*** Update File: a.md\n"},
            }
        )
        self.assertFalse(inside.allow)

    def test_shell_fail_closed(self) -> None:
        def shell(command: str) -> guard.Decision:
            return self.decide({"tool_name": "Bash", "tool_input": {"command": command}})

        self.assertTrue(shell("cat predictions/2026-01-01_abc_post.md").allow)
        self.assertTrue(shell("echo hello").allow)
        self.assertFalse(shell("").allow)
        self.assertFalse(shell("echo hi > predictions/2026-01-01_abc_post.md").allow)
        self.assertFalse(shell("echo hi >predictions/out.md").allow)
        self.assertFalse(shell('echo hi > "$OUT"').allow)
        self.assertFalse(shell("rm -rf predictions/2026-01-01_abc_post.md").allow)
        self.assertFalse(shell('rm -rf "$dst"').allow)
        self.assertFalse(shell("eval echo hi").allow)
        self.assertFalse(shell("python3 -c 'print(1)'").allow)
        self.assertFalse(shell("echo 'unterminated").allow)
        self.assertTrue(shell("echo $(date)").allow)
        self.assertFalse(shell("cp $(echo predictions/a.md) /tmp/a.md").allow)

    def test_bypass_environment_variable_is_ignored(self) -> None:
        os.environ["CHEAT_BYPASS_IMMUTABILITY"] = "1"
        try:
            decision = self.edit("secret alpha")
        finally:
            os.environ.pop("CHEAT_BYPASS_IMMUTABILITY", None)
        self.assertFalse(decision.allow)


class HookScriptTests(unittest.TestCase):
    def run_hook(self, payload: str, env_bypass: bool = False) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if env_bypass:
            env["CHEAT_BYPASS_IMMUTABILITY"] = "1"
        else:
            env.pop("CHEAT_BYPASS_IMMUTABILITY", None)
        return subprocess.run(
            ["bash", str(HOOK)],
            input=payload,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_empty_and_unparseable_input_denied(self) -> None:
        empty = self.run_hook("", env_bypass=True)
        self.assertEqual(empty.returncode, 1)
        self.assertIn("empty hook input", empty.stderr)
        self.assertIn("ignored", empty.stderr)

        bad = self.run_hook("{", env_bypass=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("unparseable", bad.stderr)

    def test_script_blocks_prediction_edit_when_bypass_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            pred = cwd / "predictions"
            pred.mkdir()
            path = pred / "post.md"
            path.write_text(SAMPLE, encoding="utf-8")
            payload = json.dumps(
                {
                    "cwd": str(cwd),
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": str(path),
                        "old_string": "second secret",
                        "new_string": "changed",
                    },
                }
            )
            result = self.run_hook(payload, env_bypass=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("prediction section", result.stderr)
            self.assertIn("not been verified", result.stderr)


if __name__ == "__main__":
    unittest.main()
