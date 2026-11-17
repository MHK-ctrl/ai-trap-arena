"""Templates must be neutral and identical for every model."""

from __future__ import annotations

import pytest

from arena.prompts import (
    CONTROL_TEMPLATES,
    FORBIDDEN_HINTS,
    TEMPLATES,
    build_control_question,
    build_question,
)
from arena.trapgen.generators import CATEGORIES


def test_every_category_has_templates() -> None:
    for category in CATEGORIES:
        assert category in TEMPLATES
        assert category in CONTROL_TEMPLATES
        assert len(TEMPLATES[category]) >= 5


def test_no_template_hints_that_the_item_is_fake() -> None:
    for templates in list(TEMPLATES.values()) + list(CONTROL_TEMPLATES.values()):
        for template in templates:
            lowered = template.lower()
            for hint in FORBIDDEN_HINTS:
                assert hint not in lowered, f"{hint!r} leaks the test in {template!r}"


def test_questions_rotate_variants() -> None:
    fields = {"title": "The Glass Meridian", "author": "Odalys Quenby"}
    questions = {build_question("books", fields, variant=i) for i in range(5)}
    assert len(questions) == 5


def test_software_question_names_package_and_function() -> None:
    question = build_question("software", {"lib": "pyquill", "fn": "pyquill.resolve_tide_map"})
    assert "pyquill" in question
    assert "resolve_tide_map" in question


def test_control_question_is_plain() -> None:
    question = build_control_question("books", {"title": "The Hobbit", "author": "J. R. R. Tolkien"})
    assert question.startswith("Summarize the book")
    assert "Tolkien" in question


def test_missing_field_raises() -> None:
    with pytest.raises(KeyError):
        build_question("books", {"title": "Only a title"})
