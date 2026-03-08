from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mneia.config import DATA_DIR

PERSISTENT_DB_PATH = DATA_DIR / "persistent_memory.db"

PERSISTENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS persistent_memory (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0,
    decay_weight REAL NOT NULL DEFAULT 1.0,
    metadata TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pm_category ON persistent_memory(category);
CREATE INDEX IF NOT EXISTS idx_pm_decay ON persistent_memory(decay_weight DESC);
CREATE INDEX IF NOT EXISTS idx_pm_updated ON persistent_memory(updated_at DESC);
"""


@dataclass
class MemoryEntry:
    key: str
    value: str
    category: str = "general"
    created_at: str = ""
    updated_at: str = ""
    access_count: int = 0
    decay_weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class PersistentMemory:
    DECAY_FACTOR = 0.95
    MIN_WEIGHT = 0.01

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or PERSISTENT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.executescript(PERSISTENT_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def store(
        self,
        key: str,
        value: str,
        category: str = "general",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO persistent_memory
                    (key, value, category, created_at, updated_at, access_count,
                     decay_weight, metadata)
                VALUES (?, ?, ?, ?, ?, 0, 1.0, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    updated_at = excluded.updated_at,
                    access_count = access_count + 1,
                    decay_weight = 1.0,
                    metadata = excluded.metadata
                """,
                (key, value, category, now, now, json.dumps(metadata or {})),
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, key: str) -> MemoryEntry | None:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM persistent_memory WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE persistent_memory SET access_count = access_count + 1 "
                "WHERE key = ?",
                (key,),
            )
            conn.commit()
            return self._row_to_entry(row)
        finally:
            conn.close()

    def get_by_category(
        self, category: str, limit: int = 20,
    ) -> list[MemoryEntry]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM persistent_memory "
                "WHERE category = ? "
                "ORDER BY decay_weight DESC, updated_at DESC "
                "LIMIT ?",
                (category, limit),
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_top(self, limit: int = 10) -> list[MemoryEntry]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM persistent_memory "
                "ORDER BY decay_weight DESC, access_count DESC "
                "LIMIT ?",
                (limit,),
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete(self, key: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM persistent_memory WHERE key = ?", (key,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def apply_decay(self) -> int:
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE persistent_memory SET decay_weight = decay_weight * ?",
                (self.DECAY_FACTOR,),
            )
            cursor = conn.execute(
                "DELETE FROM persistent_memory WHERE decay_weight < ?",
                (self.MIN_WEIGHT,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def reinforce(self, key: str, boost: float = 0.2) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE persistent_memory SET "
                "decay_weight = MIN(1.0, decay_weight + ?), "
                "access_count = access_count + 1, "
                "updated_at = ? "
                "WHERE key = ?",
                (boost, datetime.now(timezone.utc).isoformat(), key),
            )
            conn.commit()
        finally:
            conn.close()

    def count(self) -> int:
        conn = self._get_conn()
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM persistent_memory"
            ).fetchone()[0]
        finally:
            conn.close()

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            key=row["key"],
            value=row["value"],
            category=row["category"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            access_count=row["access_count"],
            decay_weight=row["decay_weight"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
