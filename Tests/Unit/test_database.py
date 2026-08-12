"""Tests for database operations."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import pytest_asyncio
import aiosqlite


@pytest_asyncio.fixture
async def db():
    """In-memory database for testing."""
    from Database.database import DatabaseManager
    manager = DatabaseManager()
    manager._connection = await aiosqlite.connect(":memory:")
    manager._connection.row_factory = aiosqlite.Row
    schema_path = Path(__file__).resolve().parent.parent.parent / "Database" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    await manager._connection.executescript(schema)
    await manager._connection.commit()
    yield manager
    await manager.close()


@pytest.mark.asyncio
async def test_insert_and_fetch(db):
    row_id = await db.insert("events", {
        "event_type": "TEST",
        "source": "test",
        "message": "test event",
    })
    assert row_id is not None
    result = await db.fetch_one("SELECT * FROM events WHERE id = ?", (row_id,))
    assert result["event_type"] == "TEST"
    assert result["message"] == "test event"


@pytest.mark.asyncio
async def test_log_event(db):
    row_id = await db.log_event("SYSTEM", "test", "system started")
    assert row_id > 0


@pytest.mark.asyncio
async def test_log_command(db):
    row_id = await db.log_command("FORWARD", "api", "completed", duration_ms=42)
    assert row_id > 0
    cmd = await db.fetch_one("SELECT * FROM commands WHERE id = ?", (row_id,))
    assert cmd["action"] == "FORWARD"
    assert cmd["duration_ms"] == 42


@pytest.mark.asyncio
async def test_fetch_all(db):
    await db.log_event("A", "test", "first")
    await db.log_event("B", "test", "second")
    rows = await db.fetch_all("SELECT * FROM events")
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_tables_exist(db):
    tables = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    table_names = {t["name"] for t in tables}
    expected = {"robot_state", "events", "commands", "sensor_readings",
                "photos", "recordings", "conversations", "sync_queue", "system_errors"}
    assert expected.issubset(table_names)
