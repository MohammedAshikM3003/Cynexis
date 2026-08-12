"""
CYNEXIS — Database Manager
Async SQLite interface with auto-initialization from schema.sql.
"""

import aiosqlite
from pathlib import Path
from typing import Any, Optional

from core.config import settings, PROJECT_ROOT
from core.logger import get_logger

log = get_logger("database")

import re

SCHEMA_PATH = PROJECT_ROOT / "Database" / "schema.sql"

# Whitelist of tables allowed in insert/update operations.
# Prevents SQL injection via table name interpolation.
ALLOWED_TABLES = frozenset({
    "robot_state", "events", "commands", "sensor_readings",
    "photos", "recordings", "conversations", "sync_queue", "system_errors",
})

# Regex for safe SQL identifiers (alphanumeric + underscore only)
_SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class DatabaseManager:
    """Async SQLite database manager."""

    def __init__(self, db_path: Optional[str] = None):
        path = db_path or settings.database_path
        self.db_path = settings.resolve_path(path)
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Create database and tables from schema.sql."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(str(self.db_path))
        self._connection.row_factory = aiosqlite.Row

        # Load and execute schema
        if SCHEMA_PATH.exists():
            schema = SCHEMA_PATH.read_text(encoding="utf-8")
            await self._connection.executescript(schema)
            await self._connection.commit()
            log.info(f"Database initialized at {self.db_path}")
        else:
            log.warning(f"Schema file not found: {SCHEMA_PATH}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            log.info("Database connection closed")

    async def execute(self, query: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a single query."""
        assert self._connection, "Database not initialized"
        cursor = await self._connection.execute(query, params)
        await self._connection.commit()
        return cursor

    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Fetch a single row as a dictionary."""
        assert self._connection, "Database not initialized"
        cursor = await self._connection.execute(query, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows as a list of dictionaries."""
        assert self._connection, "Database not initialized"
        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def insert(self, table: str, data: dict[str, Any]) -> int:
        """
        Insert a row and return the row ID.

        Security:
            - Table name validated against ALLOWED_TABLES whitelist.
            - Column names validated against safe identifier regex.
            - Values use parameterized SQL (? placeholders).
        """
        # Validate table name
        if table not in ALLOWED_TABLES:
            raise ValueError(
                f"Table '{table}' is not in the allowed tables whitelist. "
                f"Allowed: {sorted(ALLOWED_TABLES)}"
            )

        # Validate column names
        for col in data.keys():
            if not _SAFE_IDENTIFIER.match(col):
                raise ValueError(
                    f"Invalid column identifier: '{col}'. "
                    "Only alphanumeric characters and underscores are allowed."
                )

        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cursor = await self.execute(query, tuple(data.values()))
        return cursor.lastrowid

    async def log_event(self, event_type: str, source: str,
                        message: str, metadata: str = "") -> int:
        """Convenience: insert an event record."""
        return await self.insert("events", {
            "event_type": event_type,
            "source": source,
            "message": message,
            "metadata": metadata,
        })

    async def log_command(self, action: str, source: str,
                          result: str, parameters: str = "",
                          error_message: str = "",
                          duration_ms: int = 0) -> int:
        """Convenience: insert a command record."""
        return await self.insert("commands", {
            "action": action,
            "source": source,
            "parameters": parameters,
            "result": result,
            "error_message": error_message,
            "duration_ms": duration_ms,
        })


# Singleton instance
db = DatabaseManager()
