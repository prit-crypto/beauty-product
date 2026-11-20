"""OpenAI provider (Chat Completions REST API, no SDK needed). OPENAI_BASE_URL allows any compatible endpoint."""
import time

import httpx

from app.config import settings
from app.providers.llm import LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float | None = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self.timeout = timeout or settings.ai_timeout_s
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set")

    def _complete(self, system: str, user: str, json_mode: bool) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        for attempt in range(2):  # one quick retry on a temporary server error
            r = httpx.post(f"{settings.openai_base_url.rstrip('/')}/chat/completions", json=body, timeout=self.timeout,
                           headers={"Authorization": f"Bearer {self.api_key}"})
            if r.status_code in (500, 502, 503) and attempt == 0:
                time.sleep(0.8)
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or ""
        raise RuntimeError("unreachable")
