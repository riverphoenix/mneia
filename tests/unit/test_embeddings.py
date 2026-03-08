from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mneia.memory.embeddings import EmbeddingClient


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
    llm.embed_batch = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
    return llm


def test_embedding_client_init(mock_llm):
    client = EmbeddingClient(mock_llm)
    assert client._available is None
    assert client.available is True


async def test_embed_success(mock_llm):
    client = EmbeddingClient(mock_llm)
    result = await client.embed("test text")
    assert result == [0.1, 0.2, 0.3]
    assert client._available is True
    mock_llm.embed.assert_called_once_with("test text")


async def test_embed_failure_marks_unavailable(mock_llm):
    mock_llm.embed = AsyncMock(side_effect=Exception("connection refused"))
    client = EmbeddingClient(mock_llm)
    result = await client.embed("test")
    assert result is None
    assert client._available is False


async def test_embed_returns_none_when_unavailable(mock_llm):
    client = EmbeddingClient(mock_llm)
    client._available = False
    result = await client.embed("test")
    assert result is None
    mock_llm.embed.assert_not_called()


async def test_check_availability_success(mock_llm):
    client = EmbeddingClient(mock_llm)
    result = await client.check_availability()
    assert result is True
    assert client._available is True


async def test_check_availability_failure(mock_llm):
    mock_llm.embed = AsyncMock(side_effect=Exception("no ollama"))
    client = EmbeddingClient(mock_llm)
    result = await client.check_availability()
    assert result is False
    assert client._available is False


async def test_embed_batch_success(mock_llm):
    client = EmbeddingClient(mock_llm)
    result = await client.embed_batch(["text1", "text2"])
    assert len(result) == 2
    mock_llm.embed_batch.assert_called_once_with(["text1", "text2"])


async def test_embed_batch_empty(mock_llm):
    client = EmbeddingClient(mock_llm)
    result = await client.embed_batch([])
    assert result == []


async def test_embed_batch_returns_none_when_unavailable(mock_llm):
    client = EmbeddingClient(mock_llm)
    client._available = False
    result = await client.embed_batch(["text"])
    assert result == [None]


async def test_embed_batch_falls_back_to_individual(mock_llm):
    mock_llm.embed_batch = AsyncMock(side_effect=Exception("batch unsupported"))
    mock_llm.embed = AsyncMock(return_value=[0.5, 0.6])
    client = EmbeddingClient(mock_llm)
    result = await client.embed_batch(["text1", "text2"])
    assert len(result) == 2
    assert result[0] == [0.5, 0.6]


async def test_embed_document(mock_llm):
    client = EmbeddingClient(mock_llm)
    result = await client.embed_document("My Note", "Some content here", "obsidian")
    assert result == [0.1, 0.2, 0.3]
    call_text = mock_llm.embed.call_args[0][0]
    assert "My Note" in call_text
    assert "obsidian" in call_text
    assert "Some content here" in call_text


async def test_embed_entity(mock_llm):
    client = EmbeddingClient(mock_llm)
    result = await client.embed_entity("Alice", "person", "Product Manager at ACME")
    assert result == [0.1, 0.2, 0.3]
    call_text = mock_llm.embed.call_args[0][0]
    assert "Alice" in call_text
    assert "person" in call_text
    assert "Product Manager" in call_text


async def test_embed_entity_no_description(mock_llm):
    client = EmbeddingClient(mock_llm)
    result = await client.embed_entity("Alice", "person", "")
    assert result == [0.1, 0.2, 0.3]
    call_text = mock_llm.embed.call_args[0][0]
    assert "Alice (person)" in call_text


async def test_embed_for_search(mock_llm):
    client = EmbeddingClient(mock_llm)
    result = await client.embed_for_search("who is alice?")
    assert result == [0.1, 0.2, 0.3]


def test_truncate(mock_llm):
    client = EmbeddingClient(mock_llm)
    short = "hello"
    assert client._truncate(short) == short
    long_text = "x" * 10000
    assert len(client._truncate(long_text)) == 8000
