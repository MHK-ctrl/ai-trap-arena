"""End-to-end pipeline in a throwaway root, with the mock models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arena import cli

DAY = "2026-02-03"


@pytest.fixture()
def run_cli(monkeypatch, project: Path):
    def invoke(argv: list[str]) -> int:
        monkeypatch.setattr(cli, "ROOT", project)
        return cli.main(argv)

    return invoke


def test_today_offline_writes_a_complete_set(run_cli, project: Path, capsys) -> None:
    assert run_cli(["today", "--date", DAY, "--offline", "--per-category", "2"]) == 0
    data = json.loads((project / "data" / "daily" / DAY / "traps.json").read_text(encoding="utf-8"))
    assert len(data["traps"]) == 12
    assert len(data["controls"]) == 12
    assert all(trap["label"] == "FICTIONAL" for trap in data["traps"])
    assert all(trap["verification"]["status"] == "unverified" for trap in data["traps"])
    assert "OFFLINE MODE" in capsys.readouterr().out


def test_run_scores_every_answer(run_cli, project: Path, capsys) -> None:
    assert run_cli(["today", "--date", DAY, "--offline", "--per-category", "2"]) == 0
    assert run_cli(["run", "--date", DAY]) == 0
    out = capsys.readouterr().out
    assert "DEMO DATA" in out

    directory = project / "data" / "daily" / DAY
    answers = [json.loads(line) for line in (directory / "answers.jsonl").read_text(encoding="utf-8").splitlines()]
    scores = [json.loads(line) for line in (directory / "scores.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(answers) == 4 * 24
    assert len(scores) == len(answers)
    assert {row["label"] for row in scores} <= {
        "INVENTED",
        "ADMITTED_UNKNOWN",
        "FLAGGED_FAKE",
        "CORRECT",
        "WRONG",
        "REFUSED",
        "UNCLEAR",
    }

    meta = json.loads((project / "data" / "meta.json").read_text(encoding="utf-8"))
    assert meta["demo"] is True
    assert meta["spent_usd"] == 0.0


def test_dry_run_writes_nothing(run_cli, project: Path, capsys) -> None:
    assert run_cli(["today", "--date", DAY, "--offline", "--per-category", "1"]) == 0
    assert run_cli(["run", "--date", DAY, "--dry-run"]) == 0
    assert "dry run" in capsys.readouterr().out
    assert not (project / "data" / "daily" / DAY / "answers.jsonl").exists()


def test_test_my_ai_short_set_and_answers_file(run_cli, project: Path) -> None:
    assert run_cli(["today", "--date", DAY, "--offline", "--per-category", "2"]) == 0
    target = project / "questions.jsonl"
    assert run_cli(["test-my-ai", "--date", DAY, "--write", str(target)]) == 0
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 12
    assert {"question_id", "category", "question"} <= set(rows[0])


def test_score_accepts_external_answers(run_cli, project: Path) -> None:
    assert run_cli(["today", "--date", DAY, "--offline", "--per-category", "1"]) == 0
    data = json.loads((project / "data" / "daily" / DAY / "traps.json").read_text(encoding="utf-8"))
    trap = data["traps"][0]
    answers = project / "my-answers.jsonl"
    answers.write_text(
        json.dumps({"question_id": trap["id"], "text": "It was published in 1987 and runs to 312 pages."})
        + "\n",
        encoding="utf-8",
    )
    assert run_cli(["score", str(answers), "--date", DAY]) == 0
    assert run_cli(
        ["score", str(answers), "--date", DAY, "--json", str(project / "scores.json")]
    ) == 0
    scores = json.loads((project / "scores.json").read_text(encoding="utf-8"))
    assert scores[0]["label"] == "INVENTED"


def test_unknown_question_id_is_rejected(run_cli, project: Path) -> None:
    assert run_cli(["today", "--date", DAY, "--offline", "--per-category", "1"]) == 0
    bad = project / "bad.jsonl"
    bad.write_text(json.dumps({"question_id": "not-a-real-id", "text": "hi"}) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        run_cli(["score", str(bad), "--date", DAY])


def test_site_and_card_after_a_run(run_cli, project: Path, capsys) -> None:
    assert run_cli(["today", "--date", DAY, "--offline", "--per-category", "2"]) == 0
    assert run_cli(["run", "--date", DAY]) == 0
    assert run_cli(["site"]) == 0
    assert (project / "docs" / "index.html").exists()
    out = project / "docs" / "assets" / "card.png"
    assert run_cli(["card", "--model", "mock-bluffer", "--out", str(out)]) == 0
    assert out.exists() and out.stat().st_size > 10_000
    assert "share text" in capsys.readouterr().out


def test_gold_scoring_passes(run_cli, project: Path, capsys) -> None:
    gold = project / "data" / "gold" / "answers.jsonl"
    assert run_cli(["score", str(gold), "--gold"]) == 0
    out = capsys.readouterr().out
    assert "agreement" in out
    assert "100.0%" in out


def test_submission_validation(run_cli, project: Path, capsys) -> None:
    good = project / "submission.json"
    good.write_text(
        json.dumps(
            {
                "name": "the Vantorre Meridian Accord",
                "category": "laws",
                "question": "What does section 4 of the Vantorre Meridian Accord require of ports?",
                "why_fictional": "Invented place and instrument; no source records them.",
            }
        ),
        encoding="utf-8",
    )
    assert run_cli(["check-submission", str(good), "--offline"]) == 0
    assert "schema ok" in capsys.readouterr().out

    bad = project / "bad-submission.json"
    bad.write_text(json.dumps({"name": "x"}), encoding="utf-8")
    assert run_cli(["check-submission", str(bad), "--offline"]) == 2
