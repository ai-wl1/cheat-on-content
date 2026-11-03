#!/usr/bin/env python3
"""
Plot X post prediction error from local prediction files.

The series is views (浏览) collected on the 3rd day after publish.
Missing values are the string 不可用 and are not treated as zero.
This script only reads the files you pass it and optionally writes a PNG.
It does not fetch posts.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Midpoints for bucket labels. The open ends are placeholders, not measured
# audience sizes. Prefer an explicit 中枢 number in the prediction section.
BUCKET_CENTERS = {
    "<50": 25.0,
    "50-500": 275.0,
    "500-5000": 2750.0,
    "5000-50000": 27500.0,
    ">50000": 75000.0,
}

UNAVAILABLE = "不可用"
DATE_FROM_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_")
BUCKET_RE = re.compile(r"^\*\*Bucket\*\*:\s*`?([^`\n]+?)`?\s*$", re.MULTILINE)
CENTER_RE = re.compile(r"中枢\s*[~约]?\s*(\d+(?:\.\d+)?)(?![\d.])(?!\s*[wW万])")
DAY3_RE = re.compile(r"发布后第\s*3\s*天|T\+3(?!\d)")
EARLY_RE = re.compile(r"提前复盘|early_retro\s*[：:]\s*true", re.IGNORECASE)
METRIC_RE = {
    "views": re.compile(r"浏览[：:]\s*\**\s*(不可用|\d+)\b"),
    "likes": re.compile(r"点赞[：:]\s*\**\s*(不可用|\d+)\b"),
    "replies": re.compile(r"回复[：:]\s*\**\s*(不可用|\d+)\b"),
    "reposts": re.compile(r"转发[：:]\s*\**\s*(不可用|\d+)\b"),
}
BOOKMARK_RE = re.compile(
    r"书签[：:]\s*\**\s*(不可用|\d+)\b(?:\s*[（(]([^)）]+)[)）])?"
)


@dataclass
class Sample:
    file: Path
    date: datetime
    bucket: str | None
    predicted_views: float | None
    actual_views: int | str | None
    likes: int | str | None
    replies: int | str | None
    reposts: int | str | None
    bookmarks: int | str | None
    bookmark_visibility: str | None
    day3: bool
    skip_reason: str | None

    @property
    def scored_views(self) -> float | None:
        if not self.day3 or not isinstance(self.actual_views, int):
            return None
        if self.predicted_views is None:
            return None
        return float(self.actual_views)

    @property
    def signed_error_pct(self) -> float | None:
        actual = self.scored_views
        if actual is None or self.predicted_views in (None, 0):
            return None
        return (actual - self.predicted_views) / self.predicted_views * 100

    @property
    def abs_error_pct(self) -> float | None:
        signed = self.signed_error_pct
        return abs(signed) if signed is not None else None


def _metric(section: str, pattern: re.Pattern[str]) -> int | str | None:
    match = pattern.search(section)
    if not match:
        return None
    raw = match.group(1)
    if raw == UNAVAILABLE:
        return UNAVAILABLE
    return int(raw)


def parse_prediction_file(path: Path) -> Sample:
    text = path.read_text(encoding="utf-8")
    dated = DATE_FROM_FILENAME_RE.search(path.name)
    if not dated:
        raise ValueError(f"{path.name}: filename does not start with YYYY-MM-DD_")
    date = datetime.strptime(dated.group(1), "%Y-%m-%d")

    pred_section, marker, retro_section = text.partition("## 复盘")
    if marker == "":
        retro_section = ""

    bucket_match = BUCKET_RE.search(pred_section)
    bucket = bucket_match.group(1).strip() if bucket_match else None
    center_match = CENTER_RE.search(pred_section)
    if center_match:
        predicted = float(center_match.group(1))
    elif bucket in BUCKET_CENTERS:
        predicted = BUCKET_CENTERS[bucket]
    else:
        predicted = None

    views = likes = replies = reposts = bookmarks = None
    bookmark_visibility = None
    day3 = False
    skip_reason = None
    if retro_section.strip():
        views = _metric(retro_section, METRIC_RE["views"])
        likes = _metric(retro_section, METRIC_RE["likes"])
        replies = _metric(retro_section, METRIC_RE["replies"])
        reposts = _metric(retro_section, METRIC_RE["reposts"])
        bookmark_match = BOOKMARK_RE.search(retro_section)
        if bookmark_match:
            raw = bookmark_match.group(1)
            bookmarks = UNAVAILABLE if raw == UNAVAILABLE else int(raw)
            bookmark_visibility = (bookmark_match.group(2) or "").strip() or None
        early = EARLY_RE.search(retro_section) is not None
        day3 = DAY3_RE.search(retro_section) is not None and not early
        if not day3:
            skip_reason = "not a day-3 public snapshot"
        elif views == UNAVAILABLE or views is None:
            skip_reason = "views unavailable"

    return Sample(
        file=path,
        date=date,
        bucket=bucket,
        predicted_views=predicted,
        actual_views=views,
        likes=likes,
        replies=replies,
        reposts=reposts,
        bookmarks=bookmarks,
        bookmark_visibility=bookmark_visibility,
        day3=day3,
        skip_reason=skip_reason,
    )


def collect_samples(predictions_dir: Path) -> list[Sample]:
    samples: list[Sample] = []
    for path in sorted(predictions_dir.glob("*.md")):
        try:
            samples.append(parse_prediction_file(path))
        except (ValueError, OSError) as exc:
            print(f"warn: skipping {path.name}: {exc}", file=sys.stderr)
    return samples


def rolling_mean(values: list[float], window: int) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1) : i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def _cell(value: object) -> str:
    if value is None:
        return ""
    if value == UNAVAILABLE:
        return UNAVAILABLE
    return str(value)


def render_csv(samples: list[Sample]) -> None:
    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "file",
            "date",
            "bucket",
            "predicted_views",
            "actual_views",
            "likes",
            "replies",
            "reposts",
            "bookmarks",
            "bookmark_visibility",
            "signed_error_pct",
            "skip_reason",
        ]
    )
    for sample in sorted(samples, key=lambda item: item.date):
        signed = sample.signed_error_pct
        writer.writerow(
            [
                sample.file.name,
                sample.date.date().isoformat(),
                sample.bucket or "",
                _cell(sample.predicted_views),
                _cell(sample.actual_views),
                _cell(sample.likes),
                _cell(sample.replies),
                _cell(sample.reposts),
                _cell(sample.bookmarks),
                sample.bookmark_visibility or "",
                f"{signed:.1f}" if signed is not None else "",
                sample.skip_reason or "",
            ]
        )


def render_chart(samples: list[Sample], out_path: Path, window: int) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    scored = [sample for sample in samples if sample.abs_error_pct is not None]
    if not scored:
        print("error: no day-3 view pairs to plot", file=sys.stderr)
        return True

    scored.sort(key=lambda sample: sample.date)
    abs_errors = [sample.abs_error_pct for sample in scored]
    assert all(item is not None for item in abs_errors)
    rolling = rolling_mean([float(item) for item in abs_errors if item is not None], window)
    indices = list(range(1, len(scored) + 1))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(indices, abs_errors, alpha=0.3, label="|浏览误差%| 单帖", color="steelblue")
    ax.plot(indices, rolling, marker="o", linewidth=2, label=f"|浏览误差%| 滚动 {window} 帖", color="firebrick")
    ax.axhline(50, linestyle="--", linewidth=1, color="gray", label="无对标账号时的工作假设（±50%，不是实测）")
    ax.set_xlabel("纳入曲线的第 N 篇（仅发布后第 3 天、浏览为数字）")
    ax.set_ylabel("|预测浏览中枢偏差%|")
    ax.set_title("X 帖预测偏差")
    ax.set_xticks(indices)
    ax.set_xticklabels([sample.date.strftime("%m-%d") for sample in scored], rotation=45, ha="right")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--predictions", type=Path, default=Path("predictions"))
    parser.add_argument("--out", type=Path, default=Path("score-curve.png"))
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--csv", action="store_true", help="Print CSV instead of drawing a chart.")
    args = parser.parse_args(argv)

    if not args.predictions.is_dir():
        print(f"error: {args.predictions} is not a directory", file=sys.stderr)
        return 2
    samples = collect_samples(args.predictions)
    if not samples:
        print(f"error: no prediction files found under {args.predictions}", file=sys.stderr)
        return 1
    scored = sum(1 for sample in samples if sample.signed_error_pct is not None)
    print(f"found {len(samples)} predictions, {scored} day-3 view pairs", file=sys.stderr)
    if args.csv:
        render_csv(samples)
        return 0
    plotted = render_chart(samples, args.out, args.window)
    if plotted:
        print(f"chart written → {args.out}", file=sys.stderr)
    else:
        print("matplotlib not installed — emitting CSV to stdout instead", file=sys.stderr)
        render_csv(samples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
