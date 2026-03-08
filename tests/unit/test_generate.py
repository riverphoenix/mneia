from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mneia.config import MneiaConfig
from mneia.memory.graph import GraphNode, KnowledgeGraph
from mneia.memory.store import MemoryStore
from mneia.pipeline.generate import generate_context_files


@pytest.fixture
def config(tmp_path):
    cfg = MneiaConfig()
    cfg.context_output_dir = str(tmp_path / "context")
    return cfg


async def test_generate_context_files(config, tmp_path):
    store = MemoryStore(db_path=tmp_path / "test.db")
    graph = KnowledgeGraph(db_path=tmp_path / "graph.db")

    graph.add_entity(GraphNode(
        id="person:alice", entity_type="person", name="Alice",
        properties={"description": "Product Manager"},
    ))
    graph.add_entity(GraphNode(
        id="project:falcon", entity_type="project", name="Falcon",
        properties={"description": "Main project"},
    ))

    llm = MagicMock()
    llm.generate = AsyncMock(return_value="This is an overview summary.")
    llm.close = AsyncMock()

    generated = await generate_context_files(config, store, graph, llm)
    assert "CLAUDE.md" in generated
    assert "people.md" in generated
    assert "projects.md" in generated

    claude_md = Path(config.context_output_dir) / "CLAUDE.md"
    assert claude_md.exists()
    content = claude_md.read_text()
    assert "Alice" in content


async def test_generate_empty_graph(config, tmp_path):
    store = MemoryStore(db_path=tmp_path / "test.db")
    graph = KnowledgeGraph(db_path=tmp_path / "graph.db")

    llm = MagicMock()
    llm.generate = AsyncMock(return_value="")
    llm.close = AsyncMock()

    generated = await generate_context_files(config, store, graph, llm)
    assert len(generated) > 0
