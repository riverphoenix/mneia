from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from mneia.config import STATS_DB_PATH


@dataclass
class AgentEvent:
    agent_name: str
    event_type: str
    timestamp: float
    details: str = ""


class AgentStatsDB:
    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or STATS_DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS agent_events ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  agent_name TEXT NOT NULL,"
            "  event_type TEXT NOT NULL,"
            "  timestamp REAL NOT NULL,"
            "  details TEXT DEFAULT ''"
            ")"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_ts ON agent_events(timestamp)"
        )
        self._conn.commit()

    def record(self, agent_name: str, event_type: str, details: str = "") -> None:
        self._conn.execute(
            "INSERT INTO agent_events (agent_name, event_type, timestamp, details) "
            "VALUES (?, ?, ?, ?)",
            (agent_name, event_type, time.time(), details),
        )
        self._conn.commit()

    def get_stats_24h(self) -> dict[str, dict[str, int | float]]:
        cutoff = time.time() - 86400
        rows = self._conn.execute(
            "SELECT agent_name, event_type, COUNT(*) "
            "FROM agent_events WHERE timestamp > ? "
            "GROUP BY agent_name, event_type",
            (cutoff,),
        ).fetchall()

        stats: dict[str, dict[str, int | float]] = {}
        for agent_name, event_type, count in rows:
            if agent_name not in stats:
                stats[agent_name] = {}
            stats[agent_name][event_type] = count
        return stats

    def get_recent_events(
        self, agent_name: str | None = None, limit: int = 20,
    ) -> list[AgentEvent]:
        if agent_name:
            rows = self._conn.execute(
                "SELECT agent_name, event_type, timestamp, details "
                "FROM agent_events WHERE agent_name = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (agent_name, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT agent_name, event_type, timestamp, details "
                "FROM agent_events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            AgentEvent(
                agent_name=r[0], event_type=r[1],
                timestamp=r[2], details=r[3],
            )
            for r in rows
        ]

    def cleanup_old(self, days: int = 7) -> int:
        cutoff = time.time() - (days * 86400)
        cursor = self._conn.execute(
            "DELETE FROM agent_events WHERE timestamp < ?", (cutoff,),
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()
