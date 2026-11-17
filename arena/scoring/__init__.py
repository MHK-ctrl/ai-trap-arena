"""Scoring pipeline: turn raw answers into labels, then into metrics.

`score_answers` is the only function that decides a label. It reads the day's file so control
questions can be checked against their expected facts, and it never edits the answer text.
"""

from __future__ import annotations

import json
from pathlib import Path

from arena.scoring.judge import Judge
from arena.scoring.labels import Label
from arena.scoring.rules import Score, classify_control, classify_fictional
from arena.scoring.stats import format_ci, format_pct, model_metrics, rate_block, wilson_interval

__all__ = [
    "Judge",
    "Score",
    "classify_control",
    "classify_fictional",
    "format_ci",
    "format_pct",
    "gold_agreement",
    "load_gold",
    "model_metrics",
    "rate_block",
    "score_answers",
    "summarise",
    "wilson_interval",
]


def _control_expected(day: dict) -> dict[str, tuple[tuple[str, ...], ...]]:
    expected: dict[str, tuple[tuple[str, ...], ...]] = {}
    for control in day.get("controls", []):
        expected[control["id"]] = tuple(tuple(group) for group in control.get("expected", []))
    return expected


def score_answers(
    answers: list[dict],
    day: dict,
    *,
    min_chars: int = 180,
    judge: Judge | None = None,
    questions: dict[str, dict] | None = None,
) -> list[dict]:
    """Label every answer. Errors are recorded and marked excluded, never silently dropped."""
    expected = _control_expected(day)
    question_text = {q["id"]: q["question"] for q in day.get("traps", []) + day.get("controls", [])}
    if questions:
        question_text.update({k: v["question"] for k, v in questions.items()})

    scores: list[dict] = []
    for answer in answers:
        if answer.get("error"):
            scores.append(
                {
                    "question_id": answer["question_id"],
                    "model_id": answer["model_id"],
                    "kind": answer["kind"],
                    "category": answer["category"],
                    "label": Label.UNCLEAR.value,
                    "rationale": f"call failed: {answer['error']}",
                    "signals": [],
                    "scorer": "none",
                    "excluded": True,
                }
            )
            continue

        if answer["kind"] == "control":
            score = classify_control(answer["text"], expected.get(answer["question_id"], ()))
        else:
            score = classify_fictional(answer["text"], min_chars=min_chars)

        if score.label == Label.UNCLEAR and judge is not None:
            judged = judge.label(
                question_text.get(answer["question_id"], "(question text unavailable)"),
                answer["text"],
                answer["kind"],
            )
            if judged is not None:
                score = judged
                # A judged control answer must still be one of the control labels.
                control_labels = {Label.CORRECT, Label.WRONG, Label.REFUSED, Label.UNCLEAR}
                if answer["kind"] == "control" and judged.label not in control_labels:
                    score = classify_control(answer["text"], expected.get(answer["question_id"], ()))

        scores.append(
            {
                "question_id": answer["question_id"],
                "model_id": answer["model_id"],
                "kind": answer["kind"],
                "category": answer["category"],
                "label": score.label.value,
                "rationale": score.rationale,
                "signals": score.signals,
                "scorer": score.scorer,
                "excluded": False,
            }
        )
    return scores


def summarise(scores: list[dict]) -> dict[str, dict]:
    """Per-model metrics, excluding failed calls so a provider outage is not a score."""
    by_model: dict[str, list[dict]] = {}
    for score in scores:
        if score.get("excluded"):
            continue
        by_model.setdefault(score["model_id"], []).append(score)

    out: dict[str, dict] = {}
    for model_id, rows in by_model.items():
        metrics = model_metrics([r["label"] for r in rows], [r["kind"] for r in rows])
        by_category: dict[str, dict] = {}
        for category in sorted({r["category"] for r in rows}):
            cat_rows = [r for r in rows if r["category"] == category]
            by_category[category] = {
                "n": len(cat_rows),
                "invented": sum(1 for r in cat_rows if r["label"] == Label.INVENTED.value),
                "admitted": sum(1 for r in cat_rows if r["label"] == Label.ADMITTED_UNKNOWN.value),
                "flagged": sum(1 for r in cat_rows if r["label"] == Label.FLAGGED_FAKE.value),
                "correct": sum(1 for r in cat_rows if r["label"] == Label.CORRECT.value),
                "wrong": sum(1 for r in cat_rows if r["label"] == Label.WRONG.value),
                "refused": sum(1 for r in cat_rows if r["label"] == Label.REFUSED.value),
                "unclear": sum(1 for r in cat_rows if r["label"] == Label.UNCLEAR.value),
            }
        metrics["by_category"] = by_category
        out[model_id] = metrics
    return out


def load_gold(path: Path | str) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def gold_agreement(path: Path | str) -> dict:
    """Measure the rules against the hand-labelled gold set."""
    rows = load_gold(path)
    disagreements: list[dict] = []
    agree = 0
    for row in rows:
        expected = row["expected"]
        if row["kind"] == "control":
            groups = tuple(tuple(group) for group in row.get("expected_groups", []))
            predicted = classify_control(row["answer"], groups).label.value
        else:
            predicted = classify_fictional(
                row["answer"], min_chars=int(row.get("min_chars", 180))
            ).label.value
        if predicted == expected:
            agree += 1
        else:
            disagreements.append(
                {
                    "id": row["id"],
                    "expected": expected,
                    "predicted": predicted,
                    "note": row.get("note", ""),
                }
            )
    n = len(rows)
    low, high = wilson_interval(agree, n)
    return {
        "n": n,
        "agree": agree,
        "rate": agree / n if n else 0.0,
        "ci_low": low,
        "ci_high": high,
        "disagreements": disagreements,
    }
