"""Control items must be real, checkable and stable."""

from __future__ import annotations

from datetime import date

from arena.prompts import FORBIDDEN_HINTS
from arena.trapgen.controls import CONTROL_POOL, controls_for_tests, pick_controls
from arena.trapgen.generators import CATEGORIES


def test_every_category_has_enough_controls() -> None:
    for category in CATEGORIES:
        assert len(CONTROL_POOL[category]) >= 4


def test_controls_have_facts_and_expected_groups() -> None:
    for control in controls_for_tests():
        assert control.fact.strip()
        assert control.expected, control.id
        for group in control.expected:
            assert group, f"{control.id} has an empty keyword group"
            assert all(word.strip() for word in group)


def test_control_questions_are_neutral() -> None:
    for control in controls_for_tests():
        lowered = control.question.lower()
        for hint in FORBIDDEN_HINTS:
            assert hint not in lowered


def test_pick_controls_is_deterministic_and_rotates() -> None:
    first = pick_controls(date(2026, 5, 1), 2)
    second = pick_controls(date(2026, 5, 1), 2)
    assert [c.id for c in first] == [c.id for c in second]
    other = pick_controls(date(2026, 5, 8), 2)
    assert [c.id for c in first] != [c.id for c in other]
    assert len(first) == 2 * len(CATEGORIES)


def test_control_ids_are_unique() -> None:
    controls = controls_for_tests()
    assert len({c.id for c in controls}) == len(controls)
