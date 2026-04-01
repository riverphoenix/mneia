from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from mneia.config import LLMConfig

logger = logging.getLogger(__name__)

# Retry settings (mirrors Claude Code: min(500ms * 2^attempt, 32s) ± 25% jitter)
_MAX_RETRIES = 3
_BASE_DELAY_S = 0.5
_NON_RETRYABLE_STATUS = frozenset({400, 401, 403, 404, 422})

# Cost per million tokens (input, output) — approximate public pricing
_COST_PER_MT: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (0.8, 4.0),
    "gpt-4o": (5.0, 15.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.0, 30.0),
}


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token (matches Claude Code heuristic)."""
    return max(1, len(text) // 4)


class CircuitBreaker:
    def __init__(
        self, failure_threshold: int = 5, reset_timeout: float = 300,
    ) -> None:
        self._failure_count = 0
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._last_failure_time: float = 0
        self._open = False

    @property
    def is_open(self) -> bool:
        if self._open:
            import time

            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._reset_timeout:
                self._open = False
                self._failure_count = 0
                logger.info("Circuit breaker reset (half-open)")
                return False
        return self._open

    def record_failure(self) -> None:
        import time

        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._open = True
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} "
                f"failures, pausing for {self._reset_timeout}s"
            )

    def record_success(self) -> None:
        self._failure_count = 0
        self._open = False


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(timeout=120)
        self._circuit_breaker = CircuitBreaker()
        self._session_input_tokens: int = 0
        self._session_output_tokens: int = 0
        self._session_cost: float = 0.0

    # ------------------------------------------------------------------
    # Public API — blocking
    # ------------------------------------------------------------------

    async def generate(
        self, prompt: str, system: str = "", json_mode: bool = False,
    ) -> str:
        chunks: list[str] = []
        async for chunk in self.generate_stream(prompt, system=system, json_mode=json_mode):
            chunks.append(chunk)
        return "".join(chunks)

    # ------------------------------------------------------------------
    # Public API — streaming
    # ------------------------------------------------------------------

    async def generate_stream(
        self,
        prompt: str,
        system: str = "",
        json_mode: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Yield text tokens as they arrive from the LLM."""
        if self._circuit_breaker.is_open:
            raise RuntimeError("LLM circuit breaker is open — service unavailable")

        input_tokens = _estimate_tokens((system or "") + prompt)

        try:
            output_chars = 0
            async for chunk in self._stream_with_retry(prompt, system, json_mode):
                output_chars += len(chunk)
                yield chunk
            self._circuit_breaker.record_success()
            output_tokens = _estimate_tokens("x" * output_chars)
            self._track_tokens(input_tokens, output_tokens)
        except Exception:
            self._circuit_breaker.record_failure()
            raise

    # generator wrapper needed to satisfy mypy for async generator with error handling
    async def _stream_with_retry(
        self, prompt: str, system: str, json_mode: bool,
    ) -> AsyncGenerator[str, None]:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async for chunk in self._do_generate_stream(prompt, system, json_mode):
                    yield chunk
                return
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt == _MAX_RETRIES:
                    raise
                status = getattr(getattr(exc, "response", None), "status_code", 0)
                if status in _NON_RETRYABLE_STATUS:
                    raise
                delay = min(_BASE_DELAY_S * (2 ** attempt), 32.0)
                delay *= 0.75 + random.random() * 0.5
                logger.warning(
                    f"LLM request failed (attempt {attempt + 1}/{_MAX_RETRIES}), "
                    f"retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # Provider dispatch
    # ------------------------------------------------------------------

    async def _do_generate_stream(
        self, prompt: str, system: str, json_mode: bool,
    ) -> AsyncGenerator[str, None]:
        if self.config.provider == "ollama":
            async for chunk in self._ollama_stream(prompt, system, json_mode):
                yield chunk
        elif self.config.provider == "anthropic":
            async for chunk in self._anthropic_stream(prompt, system):
                yield chunk
        elif self.config.provider == "openai":
            async for chunk in self._openai_stream(prompt, system, json_mode):
                yield chunk
        elif self.config.provider == "google":
            # Google's REST endpoint doesn't support SSE; yield full response as one chunk
            text = await self._google_generate(prompt, system)
            yield text
        else:
            raise ValueError(f"Unknown LLM provider: {self.config.provider}")

    # ------------------------------------------------------------------
    # Ollama streaming
    # ------------------------------------------------------------------

    async def _ollama_stream(
        self, prompt: str, system: str, json_mode: bool,
    ) -> AsyncGenerator[str, None]:
        url = f"{self.config.ollama_base_url}/api/generate"
        payload: dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        async with self._client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    chunk = data.get("response", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

    # ------------------------------------------------------------------
    # Anthropic streaming
    # ------------------------------------------------------------------

    async def _anthropic_stream(
        self, prompt: str, system: str,
    ) -> AsyncGenerator[str, None]:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.config.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "stream": True,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        async with self._client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    event = json.loads(raw)
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            chunk = delta.get("text", "")
                            if chunk:
                                yield chunk
                except json.JSONDecodeError:
                    continue

    # ------------------------------------------------------------------
    # OpenAI streaming
    # ------------------------------------------------------------------

    async def _openai_stream(
        self, prompt: str, system: str, json_mode: bool,
    ) -> AsyncGenerator[str, None]:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json",
        }
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with self._client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    event = json.loads(raw)
                    delta = event["choices"][0].get("delta", {})
                    chunk = delta.get("content", "")
                    if chunk:
                        yield chunk
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        if self.config.provider == "ollama":
            return await self._ollama_embed(text)
        elif self.config.provider == "openai":
            return await self._openai_embed(text)
        raise NotImplementedError(f"Embeddings not implemented for {self.config.provider}")

    async def _ollama_embed(self, text: str) -> list[float]:
        url = f"{self.config.ollama_base_url}/api/embed"
        payload = {
            "model": self.config.embedding_model,
            "input": text,
        }
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["embeddings"][0]

    async def _openai_embed(self, text: str) -> list[float]:
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.embedding_model,
            "input": text,
        }
        resp = await self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self.config.provider == "openai":
            return await self._openai_embed_batch(texts)
        results = []
        for text in texts:
            results.append(await self.embed(text))
        return results

    async def _openai_embed_batch(self, texts: list[str]) -> list[list[float]]:
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.embedding_model,
            "input": texts,
        }
        resp = await self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()["data"]
        data.sort(key=lambda x: x["index"])
        return [item["embedding"] for item in data]

    # ------------------------------------------------------------------
    # Google (non-streaming fallback)
    # ------------------------------------------------------------------

    async def _google_generate(self, prompt: str, system: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.config.model}:generateContent"
            f"?key={self.config.google_api_key}"
        )
        contents: list[dict[str, Any]] = []
        if system:
            contents.append({"role": "user", "parts": [{"text": system}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            },
        }
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        candidates = resp.json().get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return ""

    # ------------------------------------------------------------------
    # JSON generation with repair fallback
    # ------------------------------------------------------------------

    async def generate_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        response = await self.generate(prompt, system, json_mode=True)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(response[start:end])
                except json.JSONDecodeError:
                    pass
            # Last resort: ask LLM to repair the JSON
            try:
                repair_prompt = (
                    "Fix this malformed JSON and return ONLY the corrected JSON, "
                    f"no explanation:\n{response}"
                )
                repaired = await self.generate(repair_prompt, json_mode=True)
                return json.loads(repaired)
            except Exception:
                return {}

    # ------------------------------------------------------------------
    # Token tracking
    # ------------------------------------------------------------------

    def _track_tokens(self, input_tokens: int, output_tokens: int) -> None:
        self._session_input_tokens += input_tokens
        self._session_output_tokens += output_tokens
        model_key = self.config.model.lower()
        for key, (in_cost, out_cost) in _COST_PER_MT.items():
            if key in model_key:
                self._session_cost += (
                    input_tokens * in_cost / 1_000_000
                    + output_tokens * out_cost / 1_000_000
                )
                break

    def session_cost_summary(self) -> str:
        total = self._session_input_tokens + self._session_output_tokens
        if total == 0:
            return ""
        if self._session_cost > 0:
            return f"~{total:,} tokens · ~${self._session_cost:.4f} this session"
        return f"~{total:,} tokens this session"

    def reset_session_stats(self) -> None:
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._session_cost = 0.0

    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.aclose()
