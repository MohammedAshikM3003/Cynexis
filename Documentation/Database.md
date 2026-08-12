# CYNEXIS — Database Documentation

## Engine
SQLite 3 via `aiosqlite` (async).

## Location
```
Database/cynexis.db     (auto-created on first run)
Database/schema.sql     (source of truth for table definitions)
Database/database.py    (async manager)
```

## Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `robot_state` | Periodic state snapshots | mode, battery, rover, arm, gripper |
| `events` | System events | event_type, source, message, metadata |
| `commands` | Every command received | action, source, result, duration_ms |
| `sensor_readings` | High-frequency sensor data | sensor_type, value, unit |
| `photos` | Captured images | filename, filepath, sync_status |
| `recordings` | Video recordings | filename, duration_s, sync_status |
| `conversations` | AI chat history | role, content, intent, action_triggered |
| `sync_queue` | Cloud sync queue | table_name, record_id, status, retry_count |
| `system_errors` | Error log | error_code, module, message, resolved |

## Usage Example

```python
from Database.database import db

# Initialize (creates tables if not exist)
await db.initialize()

# Log an event
await db.log_event("SYSTEM", "server", "CYNEXIS started")

# Log a command
await db.log_command("FORWARD", "api", "completed", duration_ms=12)

# Custom query
photos = await db.fetch_all("SELECT * FROM photos ORDER BY timestamp DESC LIMIT 10")

# Insert
row_id = await db.insert("sensor_readings", {
    "sensor_type": "flex",
    "sensor_id": "thumb",
    "value": 2450,
    "unit": "adc",
})

# Cleanup
await db.close()
```

## Sync Queue States

```
PENDING → SYNCING → SYNCED
                  → FAILED (retry with exponential backoff)
```
