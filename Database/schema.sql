-- ============================================================
-- CYNEXIS — SQLite Schema
-- Version: 1.0
-- ============================================================

-- Robot state snapshots (periodic logging)
CREATE TABLE IF NOT EXISTS robot_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    mode TEXT NOT NULL,
    battery_pct INTEGER,
    battery_mv INTEGER,
    current_ma INTEGER,
    temperature_c REAL,
    rover_speed INTEGER,
    rover_direction TEXT,
    arm_shoulder REAL,
    arm_elbow REAL,
    arm_wrist REAL,
    gripper_position REAL,
    distance_cm REAL,
    rssi INTEGER
);

-- System events
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT,
    metadata TEXT  -- JSON blob
);

-- Command log (every command received)
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    action TEXT NOT NULL,
    source TEXT NOT NULL,  -- 'gesture', 'voice', 'api', 'sequence'
    parameters TEXT,       -- JSON blob
    result TEXT,           -- 'accepted', 'rejected', 'error', 'completed'
    error_message TEXT,
    duration_ms INTEGER
);

-- Sensor readings (high-frequency logging)
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    sensor_type TEXT NOT NULL,
    sensor_id TEXT,
    value REAL NOT NULL,
    unit TEXT
);

-- Photos captured
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    resolution TEXT,
    size_bytes INTEGER,
    camera_id TEXT DEFAULT 'main',
    sync_status TEXT DEFAULT 'PENDING'
);

-- Video recordings
CREATE TABLE IF NOT EXISTS recordings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    duration_s REAL,
    size_bytes INTEGER,
    camera_id TEXT DEFAULT 'main',
    sync_status TEXT DEFAULT 'PENDING'
);

-- AI conversation history
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    role TEXT NOT NULL,       -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    session_id TEXT,
    intent TEXT,
    action_triggered TEXT
);

-- Cloud sync queue
CREATE TABLE IF NOT EXISTS sync_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    operation TEXT NOT NULL,  -- 'INSERT', 'UPDATE', 'DELETE'
    status TEXT DEFAULT 'PENDING',
    retry_count INTEGER DEFAULT 0,
    last_attempt TEXT,
    error_message TEXT
);

-- System errors
CREATE TABLE IF NOT EXISTS system_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    error_code TEXT NOT NULL,
    module TEXT NOT NULL,
    message TEXT NOT NULL,
    stack_trace TEXT,
    resolved INTEGER DEFAULT 0
);

-- Indices for common queries
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_commands_timestamp ON commands(timestamp);
CREATE INDEX IF NOT EXISTS idx_commands_action ON commands(action);
CREATE INDEX IF NOT EXISTS idx_sync_status ON sync_queue(status);
CREATE INDEX IF NOT EXISTS idx_photos_sync ON photos(sync_status);
