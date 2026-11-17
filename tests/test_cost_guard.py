"""The spend cap must stop a run before it overspends, not after."""

from __future__ import annotations

import pytest

from arena.runners.cost_guard import BudgetExceeded, CostGuard, Price, approx_tokens


def guard(cap: float = 0.01) -> CostGuard:
    return CostGuard(cap_usd=cap, prices={"paid": Price(3.0, 15.0)})


def test_estimate_uses_both_directions() -> None:
    estimate = guard().estimate("paid", prompt_tokens=1_000_000, max_output_tokens=1_000_000)
    assert estimate == pytest.approx(18.0)


def test_mock_models_are_free() -> None:
    assert guard().estimate("mock-bluffer", 10_000, 400, free=True) == 0.0


def test_unknown_model_without_free_flag_is_an_error() -> None:
    with pytest.raises(KeyError):
        guard().estimate("mystery", 10, 10)


def test_cap_is_enforced_before_the_call() -> None:
    g = guard(cap=0.001)
    g.check(0.0005)
    g.spent_usd = 0.0009
    with pytest.raises(BudgetExceeded):
        g.check(0.0002)


def test_charge_accumulates_and_remaining_tracks_it() -> None:
    g = guard(cap=0.01)
    cost = g.charge("paid", {"prompt_tokens": 1000, "completion_tokens": 100})
    assert cost == pytest.approx((1000 * 3.0 + 100 * 15.0) / 1_000_000)
    assert g.spent_usd == pytest.approx(cost)
    assert g.remaining_usd == pytest.approx(0.01 - cost)


def test_approx_tokens_is_conservative() -> None:
    assert approx_tokens("") == 1
    assert approx_tokens("abcd") == 1
    assert approx_tokens("a" * 401) == 101
