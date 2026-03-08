from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from mneia.config import DATA_DIR

PERMISSIONS_DB = DATA_DIR / "permissions.db"

PERMISSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    operation TEXT PRIMARY KEY,
    approved_at TEXT NOT NULL,
    expires_at TEXT,
    granted_by TEXT DEFAULT 'user'
);
"""


class PermissionsDB:
    def __init__(self, db_path: Any = None) -> None:
        self._db_path = db_path or PERMISSIONS_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.executescript(PERMISSIONS_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def is_approved(self, operation: str) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM approvals WHERE operation = ?",
                (operation,),
            ).fetchone()
            if not row:
                return False
            expires = row["expires_at"]
            if expires:
                exp_dt = datetime.fromisoformat(expires)
                if exp_dt < datetime.now(timezone.utc):
                    conn.execute(
                        "DELETE FROM approvals WHERE operation = ?",
                        (operation,),
                    )
                    conn.commit()
                    return False
            return True
        finally:
            conn.close()

    def approve(self, operation: str, ttl_hours: int = 24) -> None:
        conn = self._get_conn()
        try:
            now = datetime.now(timezone.utc)
            from datetime import timedelta
            expires = now + timedelta(hours=ttl_hours)
            conn.execute(
                """
                INSERT INTO approvals (operation, approved_at, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(operation) DO UPDATE SET
                    approved_at = excluded.approved_at,
                    expires_at = excluded.expires_at
                """,
                (
                    operation,
                    now.isoformat(),
                    expires.isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def revoke(self, operation: str) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                "DELETE FROM approvals WHERE operation = ?",
                (operation,),
            )
            conn.commit()
        finally:
            conn.close()

    def list_approvals(self) -> list[dict[str, Any]]:
        conn = self._get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            rows = conn.execute(
                "SELECT * FROM approvals "
                "WHERE expires_at IS NULL OR expires_at > ?",
                (now,),
            ).fetchall()
            return [
                {
                    "operation": r["operation"],
                    "approved_at": r["approved_at"],
                    "expires_at": r["expires_at"],
                    "granted_by": r["granted_by"],
                }
                for r in rows
            ]
        finally:
            conn.close()
