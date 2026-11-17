"""Scorecard rendering: right size, readable, and honest about demo data."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from arena.scorecard.make_card import CardStats, make_card, share_text


def stats(**overrides) -> CardStats:
    base = {
        "model_name": "Synthetic Bluffer (demo)",
        "bluff_count": 12,
        "n_fictional": 12,
        "honesty_score": 50.0,
        "control_accuracy": 1.0,
        "date": "2026-11-17",
        "demo": True,
    }
    base.update(overrides)
    return CardStats(**base)


def test_card_is_the_expected_size(tmp_path: Path) -> None:
    out = make_card(stats(), tmp_path / "card.png")
    with Image.open(out) as image:
        assert image.size == (1200, 630)
        assert image.format == "PNG"


def test_card_survives_a_long_model_name(tmp_path: Path) -> None:
    long_name = "A very long synthetic model name that would overflow a smaller card layout"
    out = make_card(stats(model_name=long_name), tmp_path / "long.png")
    assert out.exists()


def test_absurd_name_is_rejected_instead_of_clipped(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        make_card(stats(model_name="x" * 400), tmp_path / "nope.png")


def test_share_text_contains_the_numbers_and_link() -> None:
    text = share_text(stats())
    assert "12 of them" in text
    assert "50/100" in text
    assert "github.com/MHK-ctrl/ai-trap-arena" in text


def test_card_can_be_built_without_demo_flag(tmp_path: Path) -> None:
    out = make_card(stats(demo=False, bluff_count=3), tmp_path / "real.png")
    assert out.exists()
