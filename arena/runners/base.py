"""Runner interface and the raw answer record.

An `Answer` is written to disk exactly as the provider returned it. Nothing downstream may
edit `text`; scoring reads it and produces a separate record. That separation is what makes
the raw data auditable when someone disputes a label.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime


class MissingAPIKey(RuntimeError):
    """Raised when a provider's key is not present in the environment."""


@dataclass
class Answer:
    question_id: str
    model_id: str
    text: str
    prompt: str
    category: str
    kind: str
    provider: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    usage: dict = field(default_factory=dict)
    latency_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "model_id": self.model_id,
            "text": self.text,
            "prompt": self.prompt,
            "category": self.category,
            "kind": self.kind,
            "provider": self.provider,
            "timestamp": self.timestamp,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


class ModelRunner(ABC):
    """One model, asked one question at a time, with no system prompt and temperature 0."""

    provider: str = "unknown"

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id

    @abstractmethod
    def _complete(self, question: str) -> tuple[str, dict]:
        """Return (answer text, usage dict)."""

    def ask(self, question: dict) -> Answer:
        started = time.monotonic()
        text, usage, error = "", {}, None
        try:
            text, usage = self._complete(question["question"])
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
            error = f"{type(exc).__name__}: {exc}"
        latency = int((time.monotonic() - started) * 1000)
        return Answer(
            question_id=question["id"],
            model_id=self.model_id,
            text=text,
            prompt=question["question"],
            category=question["category"],
            kind=question["kind"],
            provider=self.provider,
            usage=usage,
            latency_ms=latency,
            error=error,
        )
