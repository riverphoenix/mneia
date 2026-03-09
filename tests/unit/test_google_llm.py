from __future__ import annotations

import httpx
import pytest
import respx

from mneia.config import LLMConfig
from mneia.core.llm import LLMClient


@pytest.fixture
def google_config() -> LLMConfig:
    return LLMConfig(
        provider="google",
        model="gemini-2.0-flash",
        google_api_key="test-key-123",
    )


@respx.mock
async def test_google_generate(google_config: LLMConfig) -> None:
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.0-flash:generateContent"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [{
                    "content": {
                        "parts": [{"text": "Hello from Gemini!"}]
                    }
                }]
            },
        )
    )

    client = LLMClient(google_config)
    result = await client.generate("test prompt", system="be helpful")
    assert result == "Hello from Gemini!"
    assert route.called
    await client.close()


@respx.mock
async def test_google_generate_empty_candidates(google_config: LLMConfig) -> None:
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.0-flash:generateContent"
    ).mock(
        return_value=httpx.Response(200, json={"candidates": []})
    )

    client = LLMClient(google_config)
    result = await client.generate("test prompt")
    assert result == ""
    await client.close()


@respx.mock
async def test_google_generate_with_system_prompt(google_config: LLMConfig) -> None:
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.0-flash:generateContent"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [{
                    "content": {"parts": [{"text": "OK"}]}
                }]
            },
        )
    )

    client = LLMClient(google_config)
    await client.generate("hello", system="You are a test bot")
    request = route.calls[0].request
    body = request.content.decode()
    assert "You are a test bot" in body
    await client.close()
