"""Google Gemini provider (REST API, no SDK needed).

Free-tier Gemini models are often busy (503) or rate-limited (429). Each call tries the main model, retries once
on a 503, then moves to the backup models (GEMINI_FALLBACK_MODELS) before giving up and letting the rules answer.
"""
import time

import httpx

from app.config import settings
from app.providers.llm import LLMProvider

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
BUSY = {429, 500, 502, 503, 504}


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float | None = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        self.models = list(dict.fromkeys([self.model] + settings.gemini_fallback_models))
        self.timeout = timeout or settings.ai_timeout_s
        self.last_model = self.model
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set")

    def _post(self, model: str, body: dict) -> httpx.Response:
        return httpx.post(GEMINI_URL.format(model=model), json=body, timeout=self.timeout,
                          headers={"x-goog-api-key": self.api_key})

    def _complete(self, system: str, user: str, json_mode: bool) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.5 if not json_mode else 0.1},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        if settings.gemini_thinking:
            body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": settings.gemini_thinking}
        last_error: Exception | None = None
        for i, model in enumerate(self.models):
            try:
                r = self._post(model, body)
                if r.status_code == 503 and i == 0:  # main model busy: one quick retry before switching
                    time.sleep(0.6)
                    r = self._post(model, body)
                if r.status_code == 400 and "thinking" in r.text.lower() and "thinkingConfig" in body["generationConfig"]:
                    body["generationConfig"].pop("thinkingConfig")  # a model without thinking levels: retry plainly
                    r = self._post(model, body)
                if r.status_code in BUSY or r.status_code == 404:
                    last_error = httpx.HTTPStatusError(f"{model}: HTTP {r.status_code}", request=r.request, response=r)
                    continue
                r.raise_for_status()
                parts = r.json()["candidates"][0]["content"]["parts"]
                self.last_model = model
                return "".join(p.get("text", "") for p in parts)
            except httpx.TimeoutException as e:
                last_error = e
                if i >= 1:  # don't stack many slow timeouts in one chat turn
                    break
        raise last_error or RuntimeError("no Gemini model available")
