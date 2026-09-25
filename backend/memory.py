"""Memoria de eventos (Bloque 4 / sección 11: backend/memory).

SQLite en un solo archivo — nada que instalar, nada que migrar todavía. Un
proceso, una tabla. Si el volumen de eventos del hackathon lo justifica,
crecer desde aquí; no antes.
"""

import json
import os
import sqlite3
from typing import Any

from backend.events import EventIn

DB_PATH = os.environ.get("LUMINA_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "events.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    location TEXT,
    confidence REAL,
    value REAL,
    unit TEXT,
    metadata TEXT NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    event = dict(row)
    event["metadata"] = json.loads(event["metadata"])
    return event


def save_event(event: EventIn) -> dict[str, Any]:
    """Guarda el evento y lo devuelve ya como dict (mismo shape que la API)."""
    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO events
               (event_id, timestamp, source, type, location, confidence, value, unit, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id,
                event.timestamp,
                event.source,
                event.type,
                event.location,
                event.confidence,
                event.value,
                event.unit,
                json.dumps(event.metadata),
            ),
        )
    return event.model_dump()


def get_recent(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def find_last_object_location(object_name: str) -> dict[str, Any]:
    """Última vez que se vio `object_name`. Nunca inventa (sección 2.1/17):
    si no hay evidencia, dice explícitamente que no la hay."""
    needle = object_name.strip().lower()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE type = 'object_detected' ORDER BY timestamp DESC"
        ).fetchall()
    for row in rows:
        event = _row_to_dict(row)
        if needle in str(event["metadata"].get("object", "")).lower():
            return {
                "found": True,
                "location": event["location"],
                "timestamp": event["timestamp"],
                "confidence": event["confidence"],
            }
    return {"found": False}
