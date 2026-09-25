"""Recordatorios de Lumina (sección 3.5: "Recuérdame esto antes de salir").

No son eventos de Google Calendar (eso es de solo lectura sin OAuth, ver
calendar_provider.py): son de Lumina, y se disparan con el contexto de la
casa — `leave` se dice al salir, `arrive` al llegar, `any` en ambos casos y
cuando se piden. Viven en la misma base SQLite que la memoria de eventos
(`memory.DB_PATH`, leído en cada llamada para que los tests lo puedan aislar).
"""

import sqlite3
from datetime import datetime, timezone
from typing import Any

from backend import memory

TRIGGERS = ("leave", "arrive", "any")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    trigger TEXT NOT NULL,
    created_at TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(memory.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": row["id"], "text": row["text"], "trigger": row["trigger"], "created_at": row["created_at"]}


def add(text: str, trigger: str = "any") -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("El recordatorio no puede estar vacío.")
    if trigger not in TRIGGERS:
        raise ValueError(f"trigger debe ser uno de {TRIGGERS}.")
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO reminders (text, trigger, created_at) VALUES (?, ?, ?)", (text, trigger, created_at)
        )
        reminder_id = cursor.lastrowid
    return {"id": reminder_id, "text": text, "trigger": trigger, "created_at": created_at}


def pending(moment: str | None = None) -> list[dict[str, Any]]:
    """Pendientes. Con `moment` ("leave"/"arrive") devuelve los de ese momento
    más los `any`; sin él, todos."""
    with _connect() as conn:
        if moment is None:
            rows = conn.execute("SELECT * FROM reminders WHERE done = 0 ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE done = 0 AND trigger IN (?, 'any') ORDER BY id", (moment,)
            ).fetchall()
    return [_row(row) for row in rows]


def complete(reminder_id: int) -> bool:
    with _connect() as conn:
        cursor = conn.execute("UPDATE reminders SET done = 1 WHERE id = ? AND done = 0", (reminder_id,))
    return cursor.rowcount > 0
