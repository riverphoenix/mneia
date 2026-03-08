from __future__ import annotations

from mneia.memory.persistent import PersistentMemory


def test_store_and_get(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)

    mem.store("pref:theme", "dark mode preferred", category="preference")
    entry = mem.get("pref:theme")

    assert entry is not None
    assert entry.value == "dark mode preferred"
    assert entry.category == "preference"
    assert entry.decay_weight == 1.0


def test_get_nonexistent(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)
    assert mem.get("nonexistent") is None


def test_store_updates_existing(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)

    mem.store("key1", "value1", category="general")
    mem.store("key1", "value2", category="general")

    entry = mem.get("key1")
    assert entry is not None
    assert entry.value == "value2"
    assert entry.access_count >= 1


def test_get_by_category(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)

    mem.store("p1", "likes dark mode", category="preference")
    mem.store("p2", "prefers concise answers", category="preference")
    mem.store("s1", "session about AI", category="session")

    prefs = mem.get_by_category("preference")
    assert len(prefs) == 2

    sessions = mem.get_by_category("session")
    assert len(sessions) == 1


def test_get_top(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)

    mem.store("a", "first", category="general")
    mem.store("b", "second", category="general")
    mem.store("c", "third", category="general")

    top = mem.get_top(limit=2)
    assert len(top) == 2


def test_delete(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)

    mem.store("del-me", "to be deleted")
    assert mem.delete("del-me") is True
    assert mem.get("del-me") is None
    assert mem.delete("nonexistent") is False


def test_apply_decay(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)

    mem.store("d1", "will decay")
    entry_before = mem.get("d1")
    assert entry_before is not None
    assert entry_before.decay_weight == 1.0

    mem.apply_decay()

    entry_after = mem.get("d1")
    assert entry_after is not None
    assert entry_after.decay_weight < 1.0
    assert entry_after.decay_weight == 1.0 * PersistentMemory.DECAY_FACTOR


def test_apply_decay_removes_low_weight(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)

    mem.store("low", "will be removed")
    conn = mem._get_conn()
    try:
        conn.execute(
            "UPDATE persistent_memory SET decay_weight = 0.005 WHERE key = ?",
            ("low",),
        )
        conn.commit()
    finally:
        conn.close()

    removed = mem.apply_decay()
    assert removed >= 1
    assert mem.get("low") is None


def test_reinforce(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)

    mem.store("r1", "reinforced")
    mem.apply_decay()

    entry = mem.get("r1")
    assert entry is not None
    decayed = entry.decay_weight

    mem.reinforce("r1", boost=0.3)

    entry2 = mem.get("r1")
    assert entry2 is not None
    assert entry2.decay_weight > decayed


def test_reinforce_caps_at_1(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)

    mem.store("cap", "capped")
    mem.reinforce("cap", boost=0.5)

    entry = mem.get("cap")
    assert entry is not None
    assert entry.decay_weight <= 1.0


def test_count(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)

    assert mem.count() == 0
    mem.store("a", "one")
    mem.store("b", "two")
    assert mem.count() == 2


def test_metadata_roundtrip(tmp_path):
    db = tmp_path / "pm.db"
    mem = PersistentMemory(db_path=db)

    mem.store("m1", "with meta", metadata={"source": "test", "count": 42})
    entry = mem.get("m1")
    assert entry is not None
    assert entry.metadata["source"] == "test"
    assert entry.metadata["count"] == 42
