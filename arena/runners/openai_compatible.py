"""Runner for any OpenAI-compatible chat-completions endpoint.

Works with OpenAI, DeepSeek, Together, Groq, a local vLLM server, and anything else that
implements `POST {base_url}/chat/completions`.

The key is read from the environment variable named in `config/models.yaml`. It is never
logged, never written to disk and never included in an error message: errors carry the HTTP
status and a truncated response body only.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from arena.runners.base import MissingAPIKey, ModelRunner


class OpenAICompatibleRunner(ModelRunner):
    provider = "openai_compatible"

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
                "messages": [{"role": "user", "content": question}],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"HTTP {exc.code} from {self.base_url}: {detail}") from exc

        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError(f"no choices in response from {self.base_url}")
        text = (choices[0].get("message") or {}).get("content") or ""
        usage = payload.get("usage") or {}
        return text, {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }
