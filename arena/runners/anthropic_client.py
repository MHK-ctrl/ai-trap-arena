"""Runner for the Anthropic Messages API.

Same contract as the OpenAI-compatible runner: one user message, no system prompt,
temperature 0, key from an environment variable, no key material in errors.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from arena.runners.base import MissingAPIKey, ModelRunner

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicRunner(ModelRunner):
    provider = "anthropic"

    def __init__(
        self,
        model_id: str,
        base_url: str,
        model: str,
        api_key_env: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 400,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(model_id)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _complete(self, question: str) -> tuple[str, dict]:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise MissingAPIKey(
                f"{self.api_key_env} is not set; export it or disable this model in config/models.yaml"
            )
        body = json.dumps(
            {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [{"role": "user", "content": question}],
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url}/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"HTTP {exc.code} from {self.base_url}: {detail}") from exc

        blocks = payload.get("content") or []
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        usage = payload.get("usage") or {}
        return text, {
            "prompt_tokens": usage.get("input_tokens"),
            "completion_tokens": usage.get("output_tokens"),
        }
