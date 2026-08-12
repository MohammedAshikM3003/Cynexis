"""
CYNEXIS — Test Configuration
Shared fixtures for all tests.
"""

import sys
import asyncio
from pathlib import Path
import pytest
import pytest_asyncio

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_db():
    """Create an in-memory database for testing."""
    from Database.database import DatabaseManager
    db = DatabaseManager(":memory:")
    # Override the path to use in-memory SQLite
    db.db_path = Path(":memory:")
    import aiosqlite
    db._connection = await aiosqlite.connect(":memory:")
    db._connection.row_factory = aiosqlite.Row
    # Load schema
    schema_path = PROJECT_ROOT / "Database" / "schema.sql"
    if schema_path.exists():
        schema = schema_path.read_text(encoding="utf-8")
        await db._connection.executescript(schema)
        await db._connection.commit()
    yield db
    await db.close()
