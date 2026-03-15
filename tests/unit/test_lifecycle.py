from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mneia.config import MneiaConfig
from mneia.core.agent import AgentState, BaseAgent
from mneia.core.lifecycle import AgentManager


@pytest.fixture
def config():
    return MneiaConfig()


@pytest.fixture
def manager(config):
    return AgentManager(config)


def test_manager_init(manager):
    assert manager._agents == {}
    assert manager._tasks == {}
    assert manager._running is False


def test_signal_stop(manager):
    manager._running = True
    manager._signal_stop()
    assert manager._running is False


async def test_stop_agents(manager):
    agent = MagicMock(spec=BaseAgent)
    agent.stop = AsyncMock()
    agent.state = AgentState.RUNNING

    task = MagicMock()
    task.cancel = MagicMock()

    async def noop():
        pass

    manager._agents = {"test-agent": agent}
    manager._tasks = {"test-agent": asyncio.ensure_future(noop())}

    await manager._stop_agents()

    agent.stop.assert_called_once()
    assert len(manager._agents) == 0
    assert len(manager._tasks) == 0


async def test_run_agent_exception(manager):
    agent = MagicMock(spec=BaseAgent)
    agent.name = "test"
    agent.run = AsyncMock(side_effect=Exception("boom"))
    agent._state = AgentState.RUNNING

    await manager._run_agent(agent)
    assert agent._state == AgentState.ERROR


async def test_handle_ipc_stop(manager):
    manager._running = True

    reader = AsyncMock()
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader.read = AsyncMock(return_value=json.dumps({"action": "stop"}).encode())

    await manager._handle_ipc(reader, writer)

    assert manager._running is False
    written = writer.write.call_args[0][0]
    response = json.loads(written.decode())
    assert response["ok"] is True


async def test_handle_ipc_status(manager):
    agent = MagicMock(spec=BaseAgent)
    agent.state = AgentState.RUNNING
    agent._state = AgentState.RUNNING
    manager._agents = {"listener-obsidian": agent}
    manager._running = True

    reader = AsyncMock()
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader.read = AsyncMock(return_value=json.dumps({"action": "status"}).encode())

    await manager._handle_ipc(reader, writer)

    written = writer.write.call_args[0][0]
    response = json.loads(written.decode())
    assert response["running"] is True
    assert len(response["agents"]) == 1
    assert response["agents"][0]["name"] == "listener-obsidian"


async def test_handle_ipc_list_agents(manager):
    agent = MagicMock(spec=BaseAgent)
    agent.state = AgentState.RUNNING
    manager._agents = {"worker": agent}

    reader = AsyncMock()
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader.read = AsyncMock(return_value=json.dumps({"action": "list_agents"}).encode())

    await manager._handle_ipc(reader, writer)

    written = writer.write.call_args[0][0]
    response = json.loads(written.decode())
    assert "agents" in response
    assert len(response["agents"]) == 1
    assert response["agents"][0]["name"] == "worker"


async def test_handle_ipc_stop_agent(manager):
    agent = MagicMock(spec=BaseAgent)
    agent.stop = AsyncMock()
    agent.state = AgentState.RUNNING

    async def noop():
        await asyncio.sleep(100)

    task = asyncio.ensure_future(noop())
    manager._agents = {"listener-obsidian": agent}
    manager._tasks = {"listener-obsidian": task}

    reader = AsyncMock()
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader.read = AsyncMock(return_value=json.dumps({
        "action": "stop_agent", "name": "listener-obsidian"
    }).encode())

    await manager._handle_ipc(reader, writer)

    agent.stop.assert_called_once()
    written = writer.write.call_args[0][0]
    response = json.loads(written.decode())
    assert response["ok"] is True
    assert response["stopped"] == "listener-obsidian"
    task.cancel()


async def test_handle_ipc_stop_agent_not_found(manager):
    reader = AsyncMock()
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader.read = AsyncMock(return_value=json.dumps({
        "action": "stop_agent", "name": "nonexistent"
    }).encode())

    await manager._handle_ipc(reader, writer)

    written = writer.write.call_args[0][0]
    response = json.loads(written.decode())
    assert "error" in response


async def test_handle_ipc_unknown_action(manager):
    reader = AsyncMock()
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader.read = AsyncMock(return_value=json.dumps({"action": "unknown"}).encode())

    await manager._handle_ipc(reader, writer)

    written = writer.write.call_args[0][0]
    response = json.loads(written.decode())
    assert "error" in response


async def test_handle_ipc_empty_data(manager):
    reader = AsyncMock()
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    reader.read = AsyncMock(return_value=b"")

    await manager._handle_ipc(reader, writer)
    writer.write.assert_not_called()


def test_failed_connectors_initialized(manager):
    assert manager._failed_connectors == {}


async def test_start_agents_unknown_connector(manager):
    from mneia.config import ConnectorConfig

    manager.config.connectors = {
        "nonexistent": ConnectorConfig(
            connector_type="nonexistent",
            enabled=True,
            settings={},
        ),
    }

    with patch("mneia.connectors.create_connector", return_value=None), \
         patch("mneia.agents.listener.ListenerAgent", MagicMock()), \
         patch("mneia.agents.worker.WorkerAgent", MagicMock()), \
         patch("mneia.agents.meta.MetaAgent", MagicMock()), \
         patch("mneia.memory.store.MemoryStore"), \
         patch("mneia.memory.graph.KnowledgeGraph"), \
         patch("mneia.memory.vector_store.VectorStore") as mock_vs, \
         patch("mneia.memory.embeddings.EmbeddingClient"), \
         patch("mneia.core.llm.LLMClient"):
        mock_vs.return_value.available = False
        await manager._start_agents()

    assert "nonexistent" in manager._failed_connectors
    assert "Unknown connector type" in manager._failed_connectors["nonexistent"]


async def test_start_agents_auth_exception(manager):
    from mneia.config import ConnectorConfig

    mock_connector = MagicMock()
    mock_connector.authenticate = AsyncMock(side_effect=RuntimeError("auth boom"))
    mock_connector.manifest.name = "test-conn"

    manager.config.connectors = {
        "test-conn": ConnectorConfig(
            connector_type="test-conn",
            enabled=True,
            settings={},
        ),
    }

    with patch("mneia.connectors.create_connector", return_value=mock_connector), \
         patch("mneia.agents.listener.ListenerAgent", MagicMock()), \
         patch("mneia.agents.worker.WorkerAgent", MagicMock()), \
         patch("mneia.agents.meta.MetaAgent", MagicMock()), \
         patch("mneia.memory.store.MemoryStore"), \
         patch("mneia.memory.graph.KnowledgeGraph"), \
         patch("mneia.memory.vector_store.VectorStore") as mock_vs, \
         patch("mneia.memory.embeddings.EmbeddingClient"), \
         patch("mneia.core.llm.LLMClient"):
        mock_vs.return_value.available = False
        await manager._start_agents()

    assert "test-conn" in manager._failed_connectors
    assert "auth boom" in manager._failed_connectors["test-conn"]


async def test_start_agents_auth_failed_with_last_error(manager):
    from mneia.config import ConnectorConfig

    mock_connector = MagicMock()
    mock_connector.authenticate = AsyncMock(return_value=False)
    mock_connector.last_error = "Invalid token"
    mock_connector.manifest.name = "test-conn"

    manager.config.connectors = {
        "test-conn": ConnectorConfig(
            connector_type="test-conn",
            enabled=True,
            settings={},
        ),
    }

    with patch("mneia.connectors.create_connector", return_value=mock_connector), \
         patch("mneia.agents.listener.ListenerAgent", MagicMock()), \
         patch("mneia.agents.worker.WorkerAgent", MagicMock()), \
         patch("mneia.agents.meta.MetaAgent", MagicMock()), \
         patch("mneia.memory.store.MemoryStore"), \
         patch("mneia.memory.graph.KnowledgeGraph"), \
         patch("mneia.memory.vector_store.VectorStore") as mock_vs, \
         patch("mneia.memory.embeddings.EmbeddingClient"), \
         patch("mneia.core.llm.LLMClient"):
        mock_vs.return_value.available = False
        await manager._start_agents()

    assert "test-conn" in manager._failed_connectors
    assert "Invalid token" in manager._failed_connectors["test-conn"]
