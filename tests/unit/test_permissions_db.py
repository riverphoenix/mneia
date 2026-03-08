from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from mneia.core.permissions_db import PermissionsDB


@pytest.fixture
def db(tmp_path):
    return PermissionsDB(db_path=tmp_path / "perms.db")


def test_init_creates_db(db, tmp_path):
    assert (tmp_path / "perms.db").exists()


def test_not_approved_by_default(db):
    assert db.is_approved("memory.purge") is False


def test_approve_and_check(db):
    db.approve("memory.purge", ttl_hours=24)
    assert db.is_approved("memory.purge") is True


def test_revoke(db):
    db.approve("memory.purge", ttl_hours=24)
    assert db.is_approved("memory.purge") is True
    db.revoke("memory.purge")
    assert db.is_approved("memory.purge") is False


def test_expired_approval(db):
    import sqlite3

    conn = sqlite3.connect(str(db._db_path))
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    conn.execute(
        "INSERT INTO approvals (operation, approved_at, expires_at) "
        "VALUES (?, ?, ?)",
        ("test.expired", datetime.now(timezone.utc).isoformat(), past),
    )
    conn.commit()
    conn.close()

    assert db.is_approved("test.expired") is False


def test_list_approvals_empty(db):
    assert db.list_approvals() == []


def test_list_approvals_returns_active(db):
    db.approve("op1", ttl_hours=24)
    db.approve("op2", ttl_hours=48)
    result = db.list_approvals()
    assert len(result) == 2
    ops = {r["operation"] for r in result}
    assert "op1" in ops
    assert "op2" in ops


def test_list_approvals_excludes_expired(db):
    import sqlite3

    db.approve("active", ttl_hours=24)
    conn = sqlite3.connect(str(db._db_path))
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    conn.execute(
        "INSERT INTO approvals (operation, approved_at, expires_at) "
        "VALUES (?, ?, ?)",
        ("expired", datetime.now(timezone.utc).isoformat(), past),
    )
    conn.commit()
    conn.close()

    result = db.list_approvals()
    assert len(result) == 1
    assert result[0]["operation"] == "active"


def test_approve_overwrites_existing(db):
    db.approve("test.op", ttl_hours=1)
    db.approve("test.op", ttl_hours=48)
    result = db.list_approvals()
    assert len(result) == 1
    assert result[0]["operation"] == "test.op"
