from __future__ import annotations

import time
from pathlib import Path

from mneia.core.agent_stats import AgentStatsDB


def test_record_and_get_stats(tmp_path: Path) -> None:
    db = AgentStatsDB(tmp_path / "stats.db")
    db.record("worker", "start")
    db.record("worker", "cycle")
    db.record("worker", "cycle")
    db.record("worker", "error", "timeout")

    stats = db.get_stats_24h()
    assert "worker" in stats
    assert stats["worker"]["start"] == 1
    assert stats["worker"]["cycle"] == 2
    assert stats["worker"]["error"] == 1
    db.close()


def test_get_recent_events(tmp_path: Path) -> None:
    db = AgentStatsDB(tmp_path / "stats.db")
    db.record("listener-obsidian", "start")
    db.record("listener-obsidian", "cycle")
    db.record("worker", "start")

    events = db.get_recent_events(limit=10)
    assert len(events) == 3
    assert events[0].agent_name == "worker"

    events = db.get_recent_events(agent_name="listener-obsidian")
    assert len(events) == 2
    db.close()


def test_empty_stats(tmp_path: Path) -> None:
    db = AgentStatsDB(tmp_path / "stats.db")
    stats = db.get_stats_24h()
    assert stats == {}
    db.close()


def test_cleanup_old(tmp_path: Path) -> None:
    db = AgentStatsDB(tmp_path / "stats.db")
    db.record("worker", "start")
    old_ts = time.time() - (8 * 86400)
    db._conn.execute(
        "INSERT INTO agent_events (agent_name, event_type, timestamp) VALUES (?, ?, ?)",
        ("worker", "old_event", old_ts),
    )
    db._conn.commit()

    removed = db.cleanup_old(days=7)
    assert removed == 1

    events = db.get_recent_events()
    assert len(events) == 1
    assert events[0].event_type == "start"
    db.close()


def test_event_details(tmp_path: Path) -> None:
    db = AgentStatsDB(tmp_path / "stats.db")
    db.record("autonomous", "error", "LLM timeout after 120s")

    events = db.get_recent_events()
    assert events[0].details == "LLM timeout after 120s"
    db.close()