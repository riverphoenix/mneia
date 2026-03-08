from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from mneia.config import MneiaConfig
from mneia.memory.persistent import PersistentMemory
from mneia.memory.session_manager import SessionManager


def _make_manager(tmp_path) -> SessionManager:
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)
    config = MneiaConfig()
    mgr = SessionManager(config=config, persistent_memory=mem)
    mgr._llm = MagicMock()
    mgr._llm.generate = AsyncMock(return_value="Session about AI topics.")
    mgr._llm.close = AsyncMock()
    return mgr


def test_record_interaction(tmp_path):
    mgr = _make_manager(tmp_path)
    mgr.record_interaction("user", "Hello")
    mgr.record_interaction("assistant", "Hi there")
    assert len(mgr._interactions) == 2
    assert mgr._interactions[0]["role"] == "user"


def test_get_personal_context_empty(tmp_path):
    mgr = _make_manager(tmp_path)
    ctx = mgr.get_personal_context()
    assert ctx == ""


def test_get_personal_context_with_data(tmp_path):
    mgr = _make_manager(tmp_path)
    mgr._memory.store("p1", "prefers dark mode", category="preference")
    mgr._memory.store("pat1", "asks about AI often", category="pattern")

    ctx = mgr.get_personal_context()
    assert "dark mode" in ctx
    assert "AI often" in ctx
    assert "User preferences:" in ctx
    assert "Known patterns:" in ctx


async def test_end_session_saves_summary(tmp_path):
    mgr = _make_manager(tmp_path)
    mgr.record_interaction("user", "Tell me about AI")
    mgr.record_interaction("assistant", "AI is a broad field...")

    summary = await mgr.end_session()

    assert summary is not None
    assert summary == "Session about AI topics."
    assert mgr._memory.count() == 1

    entries = mgr._memory.get_by_category("session")
    assert len(entries) == 1
    assert "AI topics" in entries[0].value


async def test_end_session_too_few_interactions(tmp_path):
    mgr = _make_manager(tmp_path)
    mgr.record_interaction("user", "Hello")

    summary = await mgr.end_session()
    assert summary is None
    assert mgr._memory.count() == 0


async def test_end_session_llm_failure(tmp_path):
    mgr = _make_manager(tmp_path)
    mgr.record_interaction("user", "Q1")
    mgr.record_interaction("assistant", "A1")
    mgr._llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))

    summary = await mgr.end_session()
    assert summary is None


async def test_close(tmp_path):
    mgr = _make_manager(tmp_path)
    await mgr.close()
    mgr._llm.close.assert_called_once()
