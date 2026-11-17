"""History is recomputed from raw labels, so a scoring fix updates the trend."""

from __future__ import annotations

import json
from pathlib import Path

from arena.leaderboard.history import latest_day, load_jsonl, series, trend_svg


def write_day(root: Path, day: str, labels: list[tuple[str, str, str]]) -> None:
    directory = root / "daily" / day
    directory.mkdir(parents=True)
    rows = [
        {
            "question_id": f"{day}-{i}",
            "model_id": model,
            "kind": kind,
            "category": "books",
            "label": label,
            "rationale": "",
            "signals": [],
            "scorer": "rules",
            "excluded": False,
        }
        for i, (model, kind, label) in enumerate(labels)
    ]
    (directory / "scores.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def test_series_aggregates_by_model_and_date(tmp_path: Path) -> None:
    write_day(
        tmp_path,
        "2026-01-01",
        [("m1", "trap", "INVENTED"), ("m1", "trap", "FLAGGED_FAKE"), ("m2", "trap", "INVENTED")],
    )
    write_day(tmp_path, "2026-01-02", [("m1", "trap", "FLAGGED_FAKE")])
    data = series(tmp_path)
    assert [point["date"] for point in data["m1"]] == ["2026-01-01", "2026-01-02"]
    assert data["m1"][0]["metrics"]["bluff_rate"]["rate"] == 0.5
    assert data["m2"][0]["metrics"]["bluff_rate"]["rate"] == 1.0


def test_latest_day_and_jsonl_helpers(tmp_path: Path) -> None:
    write_day(tmp_path, "2026-01-01", [("m", "trap", "INVENTED")])
    write_day(tmp_path, "2026-01-03", [("m", "trap", "INVENTED")])
    assert latest_day(tmp_path) == "2026-01-03"
    assert load_jsonl(tmp_path / "daily" / "2026-01-03" / "scores.jsonl")
    assert load_jsonl(tmp_path / "missing.jsonl") == []


def test_trend_svg_needs_two_points(tmp_path: Path) -> None:
    write_day(tmp_path, "2026-01-01", [("m", "trap", "INVENTED")])
    one = series(tmp_path)["m"]
    assert trend_svg(one) == ""
    write_day(tmp_path, "2026-01-02", [("m", "trap", "FLAGGED_FAKE")])
    two = series(tmp_path)["m"]
    svg = trend_svg(two)
    assert svg.startswith("<svg")
    assert "Bluff rate" in svg
