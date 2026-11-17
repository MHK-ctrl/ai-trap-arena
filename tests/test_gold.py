"""The gold set is the only evidence for the scorer's accuracy, so it is tested like data."""

from __future__ import annotations

from pathlib import Path

from arena.scoring import gold_agreement, load_gold
from arena.scoring.labels import Label

GOLD = Path(__file__).resolve().parents[1] / "data" / "gold" / "answers.jsonl"


def test_gold_set_size_and_shape() -> None:
    rows = load_gold(GOLD)
    assert len(rows) >= 50
    assert len({row["id"] for row in rows}) == len(rows)
    for row in rows:
        assert row["answer"].strip()
        assert row["expected"] in {label.value for label in Label}
        assert row["note"].strip()
        if row["kind"] == "control":
            assert row.get("expected_groups"), row["id"]
            assert row["expected"] in {"CORRECT", "WRONG", "REFUSED", "UNCLEAR"}
        else:
            assert row["kind"] == "trap"
            assert row["expected"] in {"INVENTED", "ADMITTED_UNKNOWN", "FLAGGED_FAKE", "UNCLEAR"}


def test_gold_set_covers_every_label() -> None:
    covered = {row["expected"] for row in load_gold(GOLD)}
    assert covered == {label.value for label in Label}


def test_measured_agreement_meets_the_documented_threshold() -> None:
    agreement = gold_agreement(GOLD)
    assert agreement["rate"] >= 0.85, agreement["disagreements"]
    assert agreement["n"] == len(load_gold(GOLD))


def test_agreement_is_reproducible() -> None:
    assert gold_agreement(GOLD)["agree"] == gold_agreement(GOLD)["agree"]
