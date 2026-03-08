from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from mneia.config import LLMConfig

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(timeout=120)

    async def generate(self, prompt: str, system: str = "", json_mode: bool = False) -> str:
        if self.config.provider == "ollama":
            return await self._ollama_generate(prompt, system, json_mode)
        elif self.config.provider == "anthropic":
            return await self._anthropic_generate(prompt, system)
        elif self.config.provider == "openai":
            return await self._openai_generate(prompt, system, json_mode)
        else:
            raise ValueError(f"Unknown LLM provider: {self.config.provider}")

    async def embed(self, text: str) -> list[float]:
        if self.config.provider == "ollama":
            return await self._ollama_embed(text)
        elif self.config.provider == "openai":
            return await self._openai_embed(text)
        raise NotImplementedError(f"Embeddings not implemented for {self.config.provider}")

    async def _ollama_generate(self, prompt: str, system: str, json_mode: bool) -> str:
        url = f"{self.config.ollama_base_url}/api/generate"
        payload: dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()["response"]

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

    async def _anthropic_generate(self, prompt: str, system: str) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.config.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        resp = await self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

    async def _openai_generate(self, prompt: str, system: str, json_mode: bool) -> str:
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
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        resp = await self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

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

    async def generate_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        response = await self.generate(prompt, system, json_mode=True)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
            raise

    async def close(self) -> None:
        await self._client.aclose()
