"""AGENTE IA — estado del hogar + motor de situaciones (secciones 13-15, 21 Bloque 3).

Todo pasa por el mismo pipeline (sección 14):

    PERCEPCIÓN -> EVENTOS -> CONTEXTO -> SITUACIÓN -> DECISIÓN -> ACCIÓN

`apply_event` es CONTEXTO (actualiza el estado). `evaluate_home_state` es
SITUACIÓN + DECISIÓN (severidad, y si hace falta confirmación). Este módulo
nunca ejecuta la ACCIÓN (enviar WhatsApp, mover un actuador) — eso lo hace
`api.py` llamando a `integrations.py`, para respetar la separación de la
sección 15: la IA interpreta, no ejecuta.
"""

import math
from datetime import datetime, timezone
from typing import Any

# ponytail: umbrales fijos, no calibrados contra sensores reales.
# Ajustar aquí cuando se pruebe con el BME280/MQ-2 de verdad.
KITCHEN_TEMP_WARNING = 35.0
KITCHEN_TEMP_CRITICAL = 45.0
DOOR_OPEN_ALERT_SECONDS = 300  # 5 min (sección 3.4/18: "varios minutos")
# Caídas: 30 s para contestar "¿Estás bien?"; si nadie contesta, se avisa
# solo al contacto (api.check_fall_escalation). Una persona inconsciente no
# puede tocar un botón: esperar respuesta indefinidamente no protege a nadie.
FALL_RESPONSE_SECONDS = 30
FALL_ALERT_WINDOW_SECONDS = 120  # sin nada que la revise (ni cámara ni página), cuánto sigue abierta
FALL_HELP_WINDOW_SECONDS = 600  # ya se avisó: sigue visible hasta que digan "estoy bien"
# ponytail: retardo de salida fijo, como el de cualquier alarma casera —
# tiempo para cruzar la puerta después de armar sin dispararla. Ajustar en
# sitio según cuánto tarde la demo en "salir".
ARM_EXIT_DELAY_SECONDS = 45

# Descripción en español de cada situación, para voz y para el resumen de la
# consola. Un solo lugar: el frontend no inventa su propia redacción.
SITUATION_TEXT = {
    "potential_kitchen_risk": "la estufa sigue encendida y no hay nadie en la cocina",
    "door_open_empty_house": "la puerta lleva un rato abierta y la casa parece vacía",
    "door_open_while_armed": "la puerta está abierta con la protección activada",
    "possible_fall": "detecté una posible caída",
}

_STATE: dict[str, Any] = {}


def _default_state() -> dict[str, Any]:
    return {
        "home": {"occupancy": "unknown", "door": "unknown", "security": "disarmed", "risk_level": "normal"},
        "kitchen": {"stove": "unknown", "temperature": None, "smoke": "unknown", "flame": "unknown", "occupancy": "unknown"},
        # bookkeeping interno, no parte del contrato de la sección 13:
        # necesario para "tiempo transcurrido" (sección 3.4) sin reconsultar la BD.
        "_door_changed_at": None,
        "_armed_at": None,
        "_fall": None,
    }


_STATE = _default_state()


def get_state() -> dict[str, Any]:
    return {k: v for k, v in _STATE.items() if not k.startswith("_")}


def reset_state() -> None:
    """Solo para tests: vuelve al estado inicial."""
    global _STATE
    _STATE = _default_state()


def _normalize_level(raw: Any) -> str:
    """Sensor -> uno de los 4 estados de la sección 13. No inventa: cualquier
    valor no reconocido cae a 'unknown', nunca a 'normal'."""
    value = str(raw).strip().lower()
    return value if value in {"unknown", "normal", "warning", "critical"} else "unknown"


def apply_event(event: dict[str, Any]) -> dict[str, Any]:
    """Actualiza `_STATE` según `event['type']`. Tipos no reconocidos se
    ignoran (se guardan en memoria igual, solo no mueven el estado)."""
    event_type = event["type"]
    location = event.get("location")
    metadata = event.get("metadata") or {}

    if event_type in ("stove_on", "stove_off"):
        _STATE["kitchen"]["stove"] = "on" if event_type == "stove_on" else "off"
    elif event_type == "temperature" and location == "kitchen" and event.get("value") is not None:
        _STATE["kitchen"]["temperature"] = event["value"]
    elif event_type == "smoke":
        _STATE["kitchen"]["smoke"] = _normalize_level(metadata.get("level"))
    elif event_type == "flame":
        _STATE["kitchen"]["flame"] = _normalize_level(metadata.get("level"))
    elif event_type == "motion" and "person_present" in metadata:
        occupancy = "occupied" if metadata["person_present"] else "empty"
        if location == "kitchen":
            _STATE["kitchen"]["occupancy"] = occupancy
        else:
            _STATE["home"]["occupancy"] = occupancy
    elif event_type == "possible_fall":
        # Otra fuente (un ESP32, un wearable, la demo) también puede reportarla.
        report_possible_fall(location, event.get("confidence"))
    elif event_type in ("door_open", "door_closed"):
        _STATE["home"]["door"] = "open" if event_type == "door_open" else "closed"
        _STATE["_door_changed_at"] = event.get("timestamp") or datetime.now(timezone.utc).isoformat()

    return get_state()


def evaluate_kitchen_risk(kitchen: dict[str, Any]) -> dict[str, Any]:
    """Bloque 3 de la sección 21. Mismo shape de salida que el ejemplo del doc."""
    if kitchen["stove"] != "on":
        return {"situation": "normal", "severity": "normal", "requires_confirmation": False}

    empty = kitchen["occupancy"] == "empty"
    temperature = kitchen["temperature"]
    danger_signal = kitchen["smoke"] in ("warning", "critical") or kitchen["flame"] in ("warning", "critical")
    temp_critical = temperature is not None and temperature >= KITCHEN_TEMP_CRITICAL

    if not empty and not danger_signal:
        return {"situation": "normal", "severity": "normal", "requires_confirmation": False}

    severity = "critical" if (danger_signal or temp_critical) else "warning"
    return {"situation": "potential_kitchen_risk", "severity": severity, "requires_confirmation": True}


def set_protection(armed: bool) -> None:
    """Modo protección (sección 3.4): "salgo de casa" lo arma, "llegué" lo
    desarma. Armado, una puerta abierta pasado el retardo de salida es
    crítica de inmediato — no espera los 5 minutos de la regla sin armar."""
    _STATE["home"]["security"] = "armed" if armed else "disarmed"
    _STATE["_armed_at"] = datetime.now(timezone.utc).isoformat() if armed else None


def evaluate_security_state(
    home: dict[str, Any], door_changed_at: str | None, armed_at: str | None = None
) -> dict[str, Any]:
    """Sección 3.4/18: puerta abierta + casa vacía + tiempo transcurrido; o,
    con la protección armada, puerta abierta tras el retardo de salida."""
    if home.get("security") == "armed" and home["door"] == "open" and armed_at:
        armed_for = (datetime.now(timezone.utc) - datetime.fromisoformat(armed_at)).total_seconds()
        if armed_for >= ARM_EXIT_DELAY_SECONDS:
            return {"situation": "door_open_while_armed", "severity": "critical", "requires_confirmation": True}

    if home["door"] != "open" or home["occupancy"] != "empty" or not door_changed_at:
        return {"situation": "normal", "severity": "normal", "requires_confirmation": False}

    opened_at = datetime.fromisoformat(door_changed_at)
    elapsed = (datetime.now(timezone.utc) - opened_at).total_seconds()
    if elapsed < DOOR_OPEN_ALERT_SECONDS:
        return {"situation": "normal", "severity": "normal", "requires_confirmation": False}

    return {"situation": "door_open_empty_house", "severity": "warning", "requires_confirmation": True}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seconds_since(iso: str) -> float:
    return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds()


def report_possible_fall(location: str | None, confidence: float | None) -> bool:
    """Sección 3.12: la visión detecta postura de caída. Esto NO afirma una
    emergencia médica (regla de la sección 19): abre una pregunta, "¿Estás
    bien?", con cuenta regresiva. Si ya hay una abierta no la reinicia (la
    cuenta sigue corriendo). Devuelve True si abrió una nueva."""
    if fall_status()["active"]:
        return False
    _STATE["_fall"] = {
        "detected_at": _now_iso(),
        "location": location,
        "confidence": confidence,
        "status": "asking",  # asking -> ok | help | escalated
        "escalated_at": None,
    }
    return True


def confirm_fall(ok: bool) -> None:
    """Respuesta a "¿Estás bien?" (botón o voz). `ok=True` cierra la alerta en
    cualquier momento, incluso después de haber avisado. `ok=False` marca que
    la persona pidió ayuda; api.py es quien avisa al contacto."""
    fall = _STATE.get("_fall")
    if fall is None:
        return
    if ok:
        fall["status"] = "ok"
    else:
        fall["status"] = "help"
        fall["escalated_at"] = _now_iso()


def fall_due_for_escalation() -> bool:
    """Nadie contestó a tiempo: toca avisar solo al contacto."""
    fall = _STATE.get("_fall")
    return bool(fall) and fall["status"] == "asking" and _seconds_since(fall["detected_at"]) >= FALL_RESPONSE_SECONDS


def mark_fall_escalated() -> None:
    fall = _STATE.get("_fall")
    if fall is not None:
        fall["status"] = "escalated"
        fall["escalated_at"] = _now_iso()


def fall_status() -> dict[str, Any]:
    """Lo que la pantalla necesita para el aviso: si hay alerta, en qué paso
    va y cuántos segundos quedan para contestar."""
    fall = _STATE.get("_fall")
    if fall is None or fall["status"] == "ok":
        return {"active": False}
    if fall["status"] == "asking":
        elapsed = _seconds_since(fall["detected_at"])
        if elapsed > FALL_ALERT_WINDOW_SECONDS:
            return {"active": False}
        seconds_left = max(0, math.ceil(FALL_RESPONSE_SECONDS - elapsed))
        return {
            "active": True,
            "status": "asking",
            "location": fall["location"],
            "seconds_left": seconds_left,
            "respond_seconds": FALL_RESPONSE_SECONDS,
        }
    if _seconds_since(fall["escalated_at"]) > FALL_HELP_WINDOW_SECONDS:
        return {"active": False}
    return {"active": True, "status": fall["status"], "location": fall["location"], "seconds_left": 0}


def evaluate_fall_state() -> dict[str, Any]:
    if not fall_status()["active"]:
        return {"situation": "normal", "severity": "normal", "requires_confirmation": False}
    return {"situation": "possible_fall", "severity": "critical", "requires_confirmation": True}


_SEVERITY_RANK = {"normal": 0, "warning": 1, "critical": 2}


def evaluate_home_state(state: dict[str, Any] | None = None) -> dict[str, Any]:
    """SITUACIÓN + DECISIÓN a nivel casa: la peor de las situaciones activas
    gana, y esa severidad se refleja también en `home.risk_level`."""
    state = state if state is not None else get_state()
    kitchen_risk = evaluate_kitchen_risk(state["kitchen"])
    security_risk = evaluate_security_state(state["home"], _STATE.get("_door_changed_at"), _STATE.get("_armed_at"))
    fall_risk = evaluate_fall_state()

    worst = max((kitchen_risk, security_risk, fall_risk), key=lambda r: _SEVERITY_RANK[r["severity"]])
    _STATE["home"]["risk_level"] = worst["severity"]
    return worst
