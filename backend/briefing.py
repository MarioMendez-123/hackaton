"""Lo que Lumina dice de la casa, en español llano.

Tres textos, todos compuestos solo con hechos que el sistema de verdad tiene
(regla del doc maestro: nunca inventar un estado sin evidencia):

- `house_summary`: titular + detalle para la consola y para "¿cómo está la casa?".
- `departure_speech`: lo que dice al salir (riesgos, recordatorios, agenda).
- `arrival_speech`: lo que dice al llegar.

El frontend solo muestra/lee estos textos; la redacción vive aquí para que
se pueda probar y no se duplique entre la voz y la pantalla.
"""

import logging
from datetime import datetime
from typing import Any

from backend import agent, calendar_provider, reminders

logger = logging.getLogger("briefing")

_HEADLINES = {
    "potential_kitchen_risk": {"warning": "Revisa la cocina.", "critical": "Atención en la cocina."},
    "door_open_empty_house": {"warning": "Revisa la puerta.", "critical": "Revisa la puerta."},
    "door_open_while_armed": {"warning": "La puerta se abrió.", "critical": "La puerta se abrió."},
    "possible_fall": {"warning": "¿Estás bien?", "critical": "¿Estás bien?"},
}


_FALL_DETAIL = {
    "help": "Pediste ayuda y ya avisé a tu contacto.",
    "escalated": "Nadie contestó, así que ya avisé a tu contacto.",
}


def _sentence(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:] + ("" if text.endswith((".", "?", "!")) else ".")


def join_es(items: list[str]) -> str:
    """["a"] -> "a"; ["a","b"] -> "a y b"; ["a","b","c"] -> "a, b y c"."""
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} y {items[-1]}"


def _known_facts(state: dict[str, Any]) -> list[str]:
    """Hechos en orden de importancia; lo desconocido se omite, no se adivina."""
    home, kitchen = state["home"], state["kitchen"]
    facts = []
    if home["door"] == "closed":
        facts.append("La puerta está cerrada.")
    elif home["door"] == "open":
        facts.append("La puerta está abierta.")

    if kitchen["stove"] == "on":
        facts.append("La estufa está encendida.")
    if home["occupancy"] == "occupied" or kitchen["occupancy"] == "occupied":
        facts.append("Hay alguien en casa.")
    elif home["occupancy"] == "empty":
        facts.append("No hay nadie en casa.")

    if kitchen["temperature"] is not None:
        facts.append(f"La cocina está a {kitchen['temperature']:.0f} °C.")
    return facts


def house_summary(state: dict[str, Any], situation: dict[str, Any]) -> dict[str, str]:
    name, severity = situation["situation"], situation["severity"]
    if name != "normal":
        headline = _HEADLINES.get(name, {}).get(severity, "Revisa la casa.")
        detail = _sentence(agent.SITUATION_TEXT.get(name, name))
        if name == "possible_fall":
            detail = _FALL_DETAIL.get(agent.fall_status().get("status"), detail)
        if name == "potential_kitchen_risk" and state["kitchen"]["smoke"] in ("warning", "critical"):
            detail += " El sensor detecta humo."
        return {"headline": headline, "detail": detail}

    headline = "La casa está protegida." if state["home"]["security"] == "armed" else "Todo en calma."
    facts = _known_facts(state)
    if not facts:
        return {"headline": headline, "detail": "Todavía no tengo lecturas. Enciende la cámara para empezar."}
    return {"headline": headline, "detail": " ".join(facts[:2])}


def _format_event(event: dict[str, Any]) -> str | None:
    """"Clase a las 7:00", o None si el evento ya pasó hoy."""
    start = event["start"]
    if len(start) == 10:  # evento de todo el día: "2026-09-25"
        return event["summary"]
    starts_at = datetime.fromisoformat(start).astimezone()
    if starts_at < datetime.now().astimezone():
        return None
    return f"{event['summary']} a las {starts_at.hour}:{starts_at.minute:02d}"


def _upcoming_events_today(limit: int = 2) -> list[str]:
    if not calendar_provider.is_configured():
        return []
    try:
        events = calendar_provider.get_events(0)
    except Exception as exc:  # red caída o URL revocada: el briefing sigue sin agenda
        logger.warning("No se pudo leer el calendario para el briefing (%s).", exc)
        return []
    formatted = [text for text in (_format_event(e) for e in events) if text]
    return formatted[:limit]


def departure_speech(state: dict[str, Any], situation: dict[str, Any]) -> str:
    parts = []
    if situation["severity"] != "normal":
        parts.append(f"Antes de irte: {agent.SITUATION_TEXT.get(situation['situation'], situation['situation'])}.")
    if state["home"]["door"] == "open":
        parts.append("Cierra la puerta al salir.")

    pending = [r["text"] for r in reminders.pending("leave")]
    if pending:
        parts.append(f"Recuerda: {join_es(pending)}.")

    events = _upcoming_events_today()
    if events:
        parts.append(f"Hoy tienes {join_es(events)}.")

    parts.append("Activé la protección. Que te vaya bien.")
    return " ".join(parts)


def arrival_speech(situation: dict[str, Any]) -> str:
    parts = ["Qué bueno que llegaste."]
    if situation["severity"] != "normal":
        parts.append(f"Ojo: {agent.SITUATION_TEXT.get(situation['situation'], situation['situation'])}.")

    pending = [r["text"] for r in reminders.pending("arrive")]
    if pending:
        parts.append(f"Tenías pendiente: {join_es(pending)}.")

    parts.append("Desactivé la protección.")
    return " ".join(parts)
