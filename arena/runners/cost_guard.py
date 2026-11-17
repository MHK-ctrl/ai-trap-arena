"""Daily spend cap.

Two jobs:

* `estimate` answers "what would this run cost?" before anything is spent, so `--dry-run` is
  accurate rather than decorative.
* `charge` accumulates real usage and raises `BudgetExceeded` *before* the call that would
  cross the cap, so a runaway loop stops at the limit rather than after it.

Prices are per million tokens and written in `config/models.yaml`. A model with no price
configured is treated as free for the local mocks and as an error for anything else, because
silently assuming zero cost for a paid endpoint is how budgets disappear.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    """Raised when the next call would cross the daily cap."""


@dataclass
class Price:
    input_per_mtok: float
    output_per_mtok: float


@dataclass
class CostGuard:
    cap_usd: float
    prices: dict[str, Price] = field(default_factory=dict)
    spent_usd: float = 0.0

    def price_for(self, model_id: str, *, free: bool = False) -> Price:
        if model_id in self.prices:
            return self.prices[model_id]
        if free:
            return Price(0.0, 0.0)
        raise KeyError(f"no price configured for model {model_id!r}; refusing to guess cost")

    def estimate(self, model_id: str, prompt_tokens: int, max_output_tokens: int, *, free: bool = False) -> float:
        price = self.price_for(model_id, free=free)
        return (
            prompt_tokens * price.input_per_mtok + max_output_tokens * price.output_per_mtok
        ) / 1_000_000

    def check(self, estimate_usd: float) -> None:
        if self.spent_usd + estimate_usd > self.cap_usd:
            raise BudgetExceeded(
                f"cap ${self.cap_usd:.2f} would be exceeded: spent ${self.spent_usd:.4f}, "
                f"next call ${estimate_usd:.4f}"
            )

    def charge(self, model_id: str, usage: dict, *, free: bool = False) -> float:
        price = self.price_for(model_id, free=free)
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        cost = (
            prompt_tokens * price.input_per_mtok + completion_tokens * price.output_per_mtok
        ) / 1_000_000
        self.spent_usd += cost
        return cost

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.cap_usd - self.spent_usd)


def approx_tokens(text: str) -> int:
    """Cheap, conservative token estimate: ~4 characters per token, rounded up."""
    return max(1, (len(text) + 3) // 4)
