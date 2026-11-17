"""The synthetic models must produce every label the arena needs."""

from __future__ import annotations

from datetime import date

from arena.runners.mock import MockRunner
from arena.scoring.labels import Label
from arena.scoring.rules import classify_control, classify_fictional
from arena.trapgen.generators import build_day

DAY = date(2026, 7, 7)


def day_set():
    return build_day(DAY, None, per_category=2, allow_unverified=True)


def expected_map(day) -> dict[str, tuple[tuple[str, ...], ...]]:
    return {c.id: c.expected for c in day.controls}


def label_of(answer: dict, day) -> Label:
    if answer["kind"] == "control":
        return classify_control(answer["text"], expected_map(day)[answer["question_id"]]).label
    return classify_fictional(answer["text"]).label


def test_bluffer_invents_fakes_and_answers_controls() -> None:
    day = day_set()
    runner = MockRunner("mock-bluffer", "bluffer")
    for question in day.questions():
        answer = runner.ask(question)
        expected = Label.CORRECT if question["kind"] == "control" else Label.INVENTED
        assert label_of(answer.to_dict(), day) == expected, question["id"]


def test_honest_admits_and_answers_controls() -> None:
    day = day_set()
    runner = MockRunner("mock-honest", "honest")
    for question in day.questions():
        answer = runner.ask(question)
        label = label_of(answer.to_dict(), day)
        if question["kind"] == "control":
            assert label == Label.CORRECT
        else:
            assert label in {Label.ADMITTED_UNKNOWN, Label.FLAGGED_FAKE}, question["id"]


def test_refuser_refuses_everything() -> None:
    day = day_set()
    runner = MockRunner("mock-refuser", "refuser")
    for question in day.questions():
        label = label_of(runner.ask(question).to_dict(), day)
        if question["kind"] == "control":
            assert label == Label.REFUSED
        else:
            assert label == Label.UNCLEAR


def test_mixed_bluffs_only_some_categories() -> None:
    day = day_set()
    runner = MockRunner("mock-mixed", "mixed")
    invented_categories = set()
    for question in day.questions():
        answer = runner.ask(question)
        if answer.kind == "trap" and label_of(answer.to_dict(), day) == Label.INVENTED:
            invented_categories.add(question["category"])
    assert invented_categories == {"books", "events", "science_terms"}


def test_answers_are_deterministic_and_metadata_is_honest() -> None:
    day = day_set()
    question = day.questions()[0]
    first = MockRunner("m", "bluffer").ask(question)
    second = MockRunner("m", "bluffer").ask(question)
    assert first.text == second.text
    assert first.provider == "mock"
    assert first.kind in {"trap", "control"}
    assert first.model_id == "m"


def test_unknown_behaviour_is_rejected() -> None:
    try:
        MockRunner("x", "wizard")
    except ValueError as exc:
        assert "unknown mock behaviour" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unknown behaviour should raise")
