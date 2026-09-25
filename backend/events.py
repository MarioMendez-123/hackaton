"""Contrato de eventos (sección 12 del doc maestro).

Cualquier fuente (cámara, ESP32, voz) manda el mismo shape. `event_id` y
`timestamp` se generan solos si la fuente no los manda — un ESP32 sin RTC no
debería bloquear el evento por no tener hora propia.

`metadata` es libre a propósito: cada tipo de evento usa las llaves que
necesita (p.ej. `object_detected` usa `metadata.object`; `motion` usa
`metadata.person_present`). Documentado en cada handler de `agent.py`, no aquí,
para no mantener dos catálogos de tipos de evento sincronizados a mano.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str
    type: str
    location: str | None = None
    confidence: float | None = None
    value: float | None = None
    unit: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
