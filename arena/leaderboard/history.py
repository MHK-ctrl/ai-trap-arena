"""Rolling history and the trend sparkline.

Reads every `data/daily/YYYY-MM-DD/` directory that has a `scores.jsonl`, recomputes metrics
from the labels (not from a cached summary), and returns a per-model series. Recomputing means
a scoring fix is reflected in the whole history the next time the site is built.
"""

from __future__ import annotations

import json
from datetime import date as Date
from pathlib import Path

from arena.scoring import summarise

MAX_DAYS = 30


def day_dirs(data_root: Path) -> list[Path]:
    daily = data_root / "daily"
    if not daily.exists():
        return []
    dirs = [d for d in daily.iterdir() if d.is_dir() and d.name[:4].isdigit()]
    return sorted(dirs, key=lambda d: d.name)[-MAX_DAYS:]


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_day(data_root: Path, day: str) -> dict | None:
    directory = data_root / "daily" / day
    traps_path = directory / "traps.json"
    scores_path = directory / "scores.jsonl"
    if not traps_path.exists() or not scores_path.exists():
        return None
    return {
        "date": day,
        "traps": json.loads(traps_path.read_text(encoding="utf-8")),
        "answers": load_jsonl(directory / "answers.jsonl"),
        "scores": load_jsonl(scores_path),
    }


def series(data_root: Path, model_ids: list[str] | None = None) -> dict[str, list[dict]]:
    """{model_id: [{date, metrics}]} across the last 30 scored days."""
    out: dict[str, list[dict]] = {}
    for directory in day_dirs(data_root):
        scores = load_jsonl(directory / "scores.jsonl")
        if not scores:
            continue
        metrics = summarise(scores)
        for model_id, values in metrics.items():
            if model_ids and model_id not in model_ids:
                continue
            out.setdefault(model_id, []).append({"date": directory.name, "metrics": values})
    return out


def latest_day(data_root: Path) -> str | None:
    dirs = [d.name for d in day_dirs(data_root) if (d / "scores.jsonl").exists()]
    return dirs[-1] if dirs else None


def trend_svg(points: list[dict], *, width: int = 520, height: int = 90, colour: str = "#3b82f6") -> str:
    """A tiny inline sparkline of bluff rate over time. No JavaScript, no external assets."""
    if len(points) < 2:
        return ""
    values = [p["metrics"]["bluff_rate"]["rate"] * 100 for p in points]
    max_value = max(max(values), 1.0)
    step = width / (len(values) - 1)
    coords = []
    for i, value in enumerate(values):
        x = round(i * step, 1)
        y = round(height - (value / max_value) * (height - 8) - 4, 1)
        coords.append(f"{x},{y}")
    last = points[-1]
    first = points[0]
    label = (
        f"Bluff rate {first['date']} to {last['date']}: "
        f"{values[0]:.0f}% to {values[-1]:.0f}%"
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img" '
        f'aria-label="{label}" class="trend">'
        f'<polyline fill="none" stroke="{colour}" stroke-width="2" points="{" ".join(coords)}"/>'
        f"</svg>"
    )


def today_string() -> str:
    return Date.today().isoformat()
