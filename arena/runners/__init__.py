"""Runner registry: turn `config/models.yaml` entries into runnable models."""

from __future__ import annotations

from arena.runners.anthropic_client import AnthropicRunner
from arena.runners.base import Answer, MissingAPIKey, ModelRunner
from arena.runners.cost_guard import BudgetExceeded, CostGuard, Price, approx_tokens
from arena.runners.mock import MockRunner
from arena.runners.openai_compatible import OpenAICompatibleRunner

__all__ = [
    "Answer",
    "AnthropicRunner",
    "BudgetExceeded",
    "CostGuard",
    "MissingAPIKey",
    "MockRunner",
    "ModelRunner",
    "OpenAICompatibleRunner",
    "Price",
    "approx_tokens",
    "build_runner",
    "enabled_models",
    "prices_from_config",
]


def enabled_models(models_config: dict) -> list[dict]:
    return [m for m in models_config.get("models", []) if m.get("enabled")]


def prices_from_config(models_config: dict) -> dict[str, Price]:
    prices: dict[str, Price] = {}
    for model in models_config.get("models", []):
        if "input_price_per_mtok" in model and "output_price_per_mtok" in model:
            prices[model["id"]] = Price(
                float(model["input_price_per_mtok"]), float(model["output_price_per_mtok"])
            )
    return prices


def build_runner(model: dict, settings: dict) -> ModelRunner:
    provider = model.get("provider")
    model_id = model["id"]
    if provider == "mock":
        return MockRunner(model_id, model.get("behaviour", "bluffer"))
    if provider == "openai_compatible":
        return OpenAICompatibleRunner(
            model_id,
            base_url=model["base_url"],
            model=model.get("model", model_id),
            api_key_env=model["api_key_env"],
            temperature=settings.get("temperature", 0.0),
            max_tokens=settings.get("max_output_tokens", 400),
            timeout=settings.get("request_timeout_seconds", 60),
        )
    if provider == "anthropic":
        return AnthropicRunner(
            model_id,
            base_url=model.get("base_url", "https://api.anthropic.com"),
            model=model.get("model", model_id),
            api_key_env=model["api_key_env"],
            temperature=settings.get("temperature", 0.0),
            max_tokens=settings.get("max_output_tokens", 400),
            timeout=settings.get("request_timeout_seconds", 60),
        )
    raise ValueError(f"unknown provider {provider!r} for model {model_id!r}")
