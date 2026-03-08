from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from mneia.config import DATA_DIR
from mneia.core.connector import RawDocument

DB_PATH = DATA_DIR / "mneia.db"

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    content TEXT NOT NULL,
    content_type TEXT NOT NULL,
    title TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    url TEXT,
    participants TEXT DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source, source_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title,
    content,
    source,
    content='documents',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, title, content, source)
    VALUES (new.id, new.title, new.content, new.source);
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, content, source)
    VALUES ('delete', old.id, old.title, old.content, old.source);
END;

CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, content, source)
    VALUES ('delete', old.id, old.title, old.content, old.source);
    INSERT INTO documents_fts(rowid, title, content, source)
    VALUES (new.id, new.title, new.content, new.source);
END;

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    properties TEXT DEFAULT '{}',
    source_doc_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_doc_id) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS associations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_a_id INTEGER NOT NULL,
    entity_b_id INTEGER NOT NULL,
    relation TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    evidence TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (entity_a_id) REFERENCES entities(id),
    FOREIGN KEY (entity_b_id) REFERENCES entities(id)
);

CREATE TABLE IF NOT EXISTS checkpoints (
    connector_name TEXT PRIMARY KEY,
    last_timestamp TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_timestamp ON documents(timestamp);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_associations_entities ON associations(entity_a_id, entity_b_id);
"""


@dataclass
class StoredDocument:
    id: int
    source: str
    source_id: str
    content: str
    content_type: str
    title: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)
    url: str | None = None
    participants: list[str] = field(default_factory=list)


@dataclass
class Entity:
    id: int | None
    name: str
    entity_type: str
    description: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    source_doc_id: int | None = None


class MemoryStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.executescript(SCHEMA)
            cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
            row = cursor.fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
            self._migrate(conn)
            conn.commit()
        finally:
            conn.close()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
        if "processed" not in columns:
            conn.execute("ALTER TABLE documents ADD COLUMN processed INTEGER DEFAULT 0")

    async def store_document(self, doc: RawDocument) -> int:
        import json

        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                INSERT INTO documents (source, source_id, content, content_type, title,
                                       timestamp, metadata, url, participants)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, source_id) DO UPDATE SET
                    content = excluded.content,
                    title = excluded.title,
                    timestamp = excluded.timestamp,
                    metadata = excluded.metadata,
                    url = excluded.url,
                    participants = excluded.participants
                """,
                (
                    doc.source,
                    doc.source_id,
                    doc.content,
                    doc.content_type,
                    doc.title,
                    doc.timestamp.isoformat(),
                    json.dumps(doc.metadata),
                    doc.url,
                    json.dumps(doc.participants),
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0
        finally:
            conn.close()

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        import re

        tokens = re.findall(r"\w+", query)
        if not tokens:
            return '""'
        return " OR ".join(f'"{t}"' for t in tokens)

    async def search(self, query: str, limit: int = 10) -> list[StoredDocument]:
        conn = self._get_conn()
        try:
            fts_query = self._sanitize_fts_query(query)
            cursor = conn.execute(
                """
                SELECT d.* FROM documents d
                JOIN documents_fts fts ON d.id = fts.rowid
                WHERE documents_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, limit),
            )
            return [self._row_to_doc(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    async def get_by_id(self, doc_id: int) -> StoredDocument | None:
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            return self._row_to_doc(row) if row else None
        finally:
            conn.close()

    async def get_recent(self, limit: int = 10, source: str | None = None) -> list[StoredDocument]:
        conn = self._get_conn()
        try:
            if source:
                cursor = conn.execute(
                    "SELECT * FROM documents WHERE source = ? ORDER BY id DESC LIMIT ?",
                    (source, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM documents ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            return [self._row_to_doc(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    async def get_stats(self) -> dict[str, Any]:
        conn = self._get_conn()
        try:
            total_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            total_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            total_assocs = conn.execute("SELECT COUNT(*) FROM associations").fetchone()[0]

            by_source: dict[str, int] = {}
            for row in conn.execute(
                "SELECT source, COUNT(*) as cnt FROM documents GROUP BY source"
            ):
                by_source[row["source"]] = row["cnt"]

            return {
                "total_documents": total_docs,
                "total_entities": total_entities,
                "total_associations": total_assocs,
                "by_source": by_source,
            }
        finally:
            conn.close()

    async def purge(self, source: str | None = None) -> None:
        conn = self._get_conn()
        try:
            if source:
                conn.execute("DELETE FROM documents WHERE source = ?", (source,))
                conn.execute("DELETE FROM checkpoints WHERE connector_name = ?", (source,))
            else:
                conn.execute("DELETE FROM documents")
                conn.execute("DELETE FROM entities")
                conn.execute("DELETE FROM associations")
                conn.execute("DELETE FROM checkpoints")
            conn.commit()
        finally:
            conn.close()

    async def get_checkpoint(self, connector_name: str) -> str | None:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT last_timestamp FROM checkpoints WHERE connector_name = ?",
                (connector_name,),
            )
            row = cursor.fetchone()
            return row["last_timestamp"] if row else None
        finally:
            conn.close()

    async def set_checkpoint(self, connector_name: str, timestamp: str) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO checkpoints (connector_name, last_timestamp)
                VALUES (?, ?)
                ON CONFLICT(connector_name) DO UPDATE SET
                    last_timestamp = excluded.last_timestamp,
                    updated_at = datetime('now')
                """,
                (connector_name, timestamp),
            )
            conn.commit()
        finally:
            conn.close()

    async def store_entity(self, entity: Entity) -> int:
        import json

        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                INSERT INTO entities (name, entity_type, description, properties, source_doc_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entity.name,
                    entity.entity_type,
                    entity.description,
                    json.dumps(entity.properties),
                    entity.source_doc_id,
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0
        finally:
            conn.close()

    async def get_document_count(self, source: str | None = None) -> int:
        conn = self._get_conn()
        try:
            if source:
                row = conn.execute(
                    "SELECT COUNT(*) FROM documents WHERE source = ?", (source,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM documents").fetchone()
            return row[0]
        finally:
            conn.close()

    async def get_unprocessed(self, limit: int = 50) -> list[StoredDocument]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM documents WHERE processed = 0 ORDER BY id ASC LIMIT ?",
                (limit,),
            )
            return [self._row_to_doc(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    async def mark_processed(self, doc_id: int) -> None:
        conn = self._get_conn()
        try:
            conn.execute("UPDATE documents SET processed = 1 WHERE id = ?", (doc_id,))
            conn.commit()
        finally:
            conn.close()

    async def get_documents_in_range(
        self, start: str, end: str, limit: int = 100
    ) -> list[StoredDocument]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM documents WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp DESC LIMIT ?",
                (start, end, limit),
            )
            return [self._row_to_doc(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _row_to_doc(self, row: sqlite3.Row) -> StoredDocument:
        import json

        return StoredDocument(
            id=row["id"],
            source=row["source"],
            source_id=row["source_id"],
            content=row["content"],
            content_type=row["content_type"],
            title=row["title"],
            timestamp=row["timestamp"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            url=row["url"],
            participants=json.loads(row["participants"]) if row["participants"] else [],
        )
