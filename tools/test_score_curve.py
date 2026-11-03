#!/usr/bin/env python3
"""Parser tests for score-curve.py. They use temp files only."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "score-curve.py"
_SPEC = importlib.util.spec_from_file_location("score_curve", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
score_curve = importlib.util.module_from_spec(_SPEC)
sys.modules["score_curve"] = score_curve
_SPEC.loader.exec_module(score_curve)


def _write(root: Path, name: str, body: str) -> Path:
    path = root / name
    path.write_text(body, encoding="utf-8")
    return path


class ParseTests(unittest.TestCase):
    def test_day3_views_are_compared_and_zero_stays_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(
                Path(tmp),
                "2026-11-01_abc_note.md",
                """
## 预测
**Bucket**: `50-500`
中枢 ~ 200

## 复盘
采集窗口：发布后第 3 天
- 浏览：0
- 点赞：3
- 回复：不可用
- 转发：1
- 书签：不可用（公开页面不可见）
""",
            )
            sample = score_curve.parse_prediction_file(path)
            self.assertEqual(sample.actual_views, 0)
            self.assertEqual(sample.predicted_views, 200)
            self.assertEqual(sample.replies, "不可用")
            self.assertEqual(sample.bookmarks, "不可用")
            self.assertEqual(sample.bookmark_visibility, "公开页面不可见")
            self.assertAlmostEqual(sample.signed_error_pct or 0, -100.0)

    def test_unavailable_and_video_plays_are_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = _write(
                Path(tmp),
                "2026-11-02_abc_note.md",
                """
## 预测
中枢 ~ 500

## 复盘
采集窗口：发布后第 3 天
- 浏览：不可用
- 点赞：4
""",
            )
            sample = score_curve.parse_prediction_file(missing)
            self.assertEqual(sample.actual_views, "不可用")
            self.assertIsNone(sample.signed_error_pct)
            self.assertNotEqual(sample.actual_views, 0)

            video = _write(
                Path(tmp),
                "2026-11-03_abc_note.md",
                """
## 预测
中枢 ~50w

## 复盘
采集窗口：发布后第 3 天
- 播放：71.1w
""",
            )
            video_sample = score_curve.parse_prediction_file(video)
            self.assertIsNone(video_sample.predicted_views)
            self.assertIsNone(video_sample.actual_views)
            self.assertIsNone(video_sample.signed_error_pct)

    def test_early_snapshot_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(
                Path(tmp),
                "2026-11-04_abc_note.md",
                """
## 预测
中枢 ~ 100

## 复盘
提前复盘
采集窗口：发布后第 1 天
- 浏览：9999
""",
            )
            sample = score_curve.parse_prediction_file(path)
            self.assertFalse(sample.day3)
            self.assertIsNone(sample.signed_error_pct)
            self.assertEqual(sample.actual_views, 9999)


if __name__ == "__main__":
    unittest.main()
