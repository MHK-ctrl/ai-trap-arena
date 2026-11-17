"""Generators: seeded, complete, verifier-gated."""

from __future__ import annotations

from datetime import date

import pytest

from arena.prompts import FORBIDDEN_HINTS
from arena.trapgen.generators import (
    CATEGORIES,
    VerificationError,
    build_day,
    candidates,
    day_seed,
)


def test_same_day_produces_the_same_set() -> None:
    day = date(2026, 3, 14)
    first = build_day(day, None, per_category=2, allow_unverified=True)
    second = build_day(day, None, per_category=2, allow_unverified=True)
    assert [t.name for t in first.traps] == [t.name for t in second.traps]
    assert [t.id for t in first.traps] == [t.id for t in second.traps]


def test_different_days_differ() -> None:
    one = build_day(date(2026, 3, 14), None, per_category=2, allow_unverified=True)
    two = build_day(date(2026, 3, 15), None, per_category=2, allow_unverified=True)
    assert [t.name for t in one.traps] != [t.name for t in two.traps]


def test_counts_and_categories() -> None:
    day_set = build_day(date(2026, 4, 2), None, per_category=3, allow_unverified=True)
    assert len(day_set.traps) == 3 * len(CATEGORIES)
    assert {t.category for t in day_set.traps} == set(CATEGORIES)
    assert len({t.id for t in day_set.traps}) == len(day_set.traps)
    assert len({t.name for t in day_set.traps}) == len(day_set.traps)


def test_questions_are_neutral_and_name_the_item() -> None:
    day_set = build_day(date(2026, 4, 3), None, per_category=2, allow_unverified=True)
    for trap in day_set.traps:
        assert trap.name
        assert trap.name.split()[0] in trap.question or trap.name in trap.question
        lowered = trap.question.lower()
        for hint in FORBIDDEN_HINTS:
            assert hint not in lowered


def test_offline_sets_are_marked_unverified() -> None:
    day_set = build_day(date(2026, 4, 4), None, per_category=1, allow_unverified=True)
    assert all(t.verification["status"] == "unverified" for t in day_set.traps)


def test_collision_is_regenerated(fake_verifier) -> None:
    day = date(2026, 6, 1)
    first_name = next(candidates(day, "books"))[0]
    fake_verifier.collision_names = {first_name}
    day_set = build_day(day, fake_verifier, per_category=2)
    assert first_name not in {t.name for t in day_set.traps}
    assert all(t.verification["status"] == "clear" for t in day_set.traps)


def test_strict_mode_aborts_on_verification_error(fake_verifier) -> None:
    fake_verifier.status = "error"
    with pytest.raises(VerificationError):
        build_day(date(2026, 6, 2), fake_verifier, per_category=1)


def test_verifier_error_is_allowed_offline_but_stamped(fake_verifier) -> None:
    fake_verifier.status = "error"
    day_set = build_day(date(2026, 6, 3), fake_verifier, per_category=1, allow_unverified=True)
    assert all(t.verification["status"] == "unverified" for t in day_set.traps)


def test_seed_depends_on_salt() -> None:
    day = date(2026, 6, 4)
    assert day_seed(day, "books", "a") != day_seed(day, "books", "b")


def test_traps_are_labelled_fictional() -> None:
    day_set = build_day(date(2026, 6, 5), None, per_category=1, allow_unverified=True)
    for trap in day_set.traps:
        assert trap.label == "FICTIONAL"
        assert trap.kind == "trap"
        assert trap.why_fictional
