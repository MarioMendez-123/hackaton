"""Endpoints del backend (sección 11: backend/api). Cámara/ESP32/voz mandan
eventos aquí; la consola y Lumina leen el estado/memoria de aquí.
"""

import logging
import os
import threading
import time
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend import agent, briefing, calendar_provider, calendar_writer, contacts, fraud_detector, memory, nodes, reminders
from backend.events import EventIn
from backend.integrations import caller, channel_status, notifier
from backend.vision import OBJECT_NAME_MAP, SEARCHABLE_OBJECTS, camera, map_object_name

router = APIRouter()
logger = logging.getLogger(__name__)

# ponytail: cooldown fijo en memoria de proceso, no por situación individual
# — suficiente para no llamar cada vez que llega un sensor mientras la cocina
# sigue en crítico. Subir si la demo dispara llamadas de más.
CRITICAL_CALL_COOLDOWN_SECONDS = 120
_last_critical_call_at = 0.0

_SEVERITY_ES = {"warning": "alerta", "critical": "crítica"}


def _situation_message(situation: dict) -> str:
    detail = agent.SITUATION_TEXT.get(situation["situation"], situation["situation"])
    return f"Super Alexa: {detail}. Severidad {_SEVERITY_ES.get(situation['severity'], situation['severity'])}."


def _maybe_call_critical(situation: dict) -> None:
    global _last_critical_call_at
    now = time.time()
    if now - _last_critical_call_at < CRITICAL_CALL_COOLDOWN_SECONDS:
        return
    _last_critical_call_at = now
    caller.call(f"Alerta de Super Alexa. {_situation_message(situation)}{contacts.escalation_suffix()}")


def _ingest(event: EventIn) -> tuple[dict, dict]:
    """Un evento entra, se guarda, mueve el estado y se reevalúa — y si la
    situación lo pide, sale la alerta. Lo usan /events y los atajos de voz
    (/home/depart, /home/arrive), así un "salgo de casa" con la estufa
    encendida avisa igual que si lo hubiera visto la cámara."""
    stored = memory.save_event(event)
    agent.apply_event(stored)
    situation = agent.evaluate_home_state()

    # Una caída no avisa al detectarse: primero se le pregunta a la persona
    # ("¿Estás bien?") y solo si no contesta avisa check_fall_escalation().
    if situation["requires_confirmation"] and situation["situation"] != "possible_fall":
        notifier.send(f"{_situation_message(situation)} ¿Quieres activar el protocolo?")
        if situation["severity"] == "critical":
            _maybe_call_critical(situation)
    return stored, situation


_PLACES = {"kitchen": " en la cocina", "livingroom": " en la sala", "living_room": " en la sala", "home": " en casa"}


def check_fall_escalation() -> bool:
    """Si nadie contestó el "¿Estás bien?" a tiempo, avisa solo al contacto
    (mensaje y llamada). Corre cada segundo en el vigilante de abajo y en cada
    /home/overview; solo actúa una vez por caída."""
    if not agent.fall_due_for_escalation():
        return False
    agent.mark_fall_escalated()
    where = _PLACES.get(agent.fall_status().get("location") or "", "")
    suffix = contacts.escalation_suffix()
    seconds = agent.FALL_RESPONSE_SECONDS
    notifier.send(f"Super Alexa: detecté una posible caída{where} y nadie respondió en {seconds} segundos.{suffix}")
    caller.call(f"Alerta de Super Alexa. Se detectó una posible caída{where} y la persona no respondió.{suffix}")
    return True


def _fall_watchdog() -> None:
    while True:
        try:
            check_fall_escalation()
        except Exception:
            logger.exception("Falló la revisión de caídas sin respuesta.")
        time.sleep(1)


def start_fall_watchdog() -> None:
    """El aviso automático no depende de que haya una página abierta: lo
    arranca server.py al iniciar (las pruebas no lo arrancan)."""
    threading.Thread(target=_fall_watchdog, name="vigilante-caidas", daemon=True).start()


@router.post("/events")
def ingest_event(event: EventIn) -> dict:
    stored, situation = _ingest(event)
    return {"event": stored, "state": agent.get_state(), "situation": situation}


@router.get("/state")
def get_home_state() -> dict:
    return agent.get_state()


@router.get("/situation")
def get_situation() -> dict:
    """Reevalúa ahora mismo (no solo tras el último evento): situaciones como
    'puerta abierta hace rato' dependen del reloj, no solo de eventos nuevos."""
    return agent.evaluate_home_state()


@router.get("/events/recent")
def recent_events(limit: int = 20) -> list[dict]:
    return memory.get_recent(limit)


@router.get("/memory/object")
def object_location(name: str = Query(...)) -> dict:
    return memory.find_last_object_location(name)


# ---------------------------------------------------------------------------
# La casa: una sola petición para la consola (estado + situación + resumen
# en palabras + bitácora), y los atajos de entrada/salida (sección 3.4/3.5).
# ---------------------------------------------------------------------------


@router.get("/home/overview")
def home_overview(events: int = 12) -> dict:
    check_fall_escalation()  # respaldo del vigilante: nunca de más, actúa una vez
    situation = agent.evaluate_home_state()
    state = agent.get_state()
    return {
        "state": state,
        "situation": situation,
        "summary": briefing.house_summary(state, situation),
        "fall": agent.fall_status(),
        "events": memory.get_recent(events),
    }


class ProtectionRequest(BaseModel):
    armed: bool


@router.post("/home/protection")
def set_protection(body: ProtectionRequest) -> dict:
    agent.set_protection(body.armed)
    return {"armed": body.armed, "situation": agent.evaluate_home_state()}


@router.post("/home/depart")
def depart() -> dict:
    """"Lumina, salgo de casa": arma la protección, marca la casa vacía y
    devuelve lo que hay que decir antes de irse (riesgos, recordatorios, agenda)."""
    agent.set_protection(True)
    _ingest(EventIn(source="voice", type="motion", location="home", metadata={"person_present": False}))
    _, situation = _ingest(
        EventIn(source="voice", type="motion", location="kitchen", metadata={"person_present": False})
    )
    state = agent.get_state()
    return {"speech": briefing.departure_speech(state, situation), "situation": situation, "state": state}


@router.post("/home/arrive")
def arrive() -> dict:
    agent.set_protection(False)
    _, situation = _ingest(
        EventIn(source="voice", type="motion", location="home", metadata={"person_present": True})
    )
    return {"speech": briefing.arrival_speech(situation), "situation": situation, "state": agent.get_state()}


@router.post("/alerts/escalate")
def escalate_alert() -> dict:
    """Botón "Avisar a mi contacto" de la consola: manda la situación actual
    por todos los canales configurados (n8n/Telegram/WhatsApp o el mock)."""
    situation = agent.evaluate_home_state()
    if situation["situation"] == "normal":
        raise HTTPException(status_code=409, detail="No hay ninguna situación activa que avisar.")
    notifier.send(f"{_situation_message(situation)}{contacts.escalation_suffix()}")
    return {"sent": True}


# ---------------------------------------------------------------------------
# Recordatorios de Lumina y agenda (sección 3.5).
# ---------------------------------------------------------------------------


class ReminderRequest(BaseModel):
    text: str
    trigger: str = "any"


@router.get("/reminders")
def list_reminders(moment: str | None = None) -> list[dict]:
    return reminders.pending(moment)


@router.post("/reminders")
def create_reminder(body: ReminderRequest) -> dict:
    try:
        return reminders.add(body.text, body.trigger)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/reminders/{reminder_id}/done")
def complete_reminder(reminder_id: int) -> dict:
    if not reminders.complete(reminder_id):
        raise HTTPException(status_code=404, detail="Ese recordatorio no existe o ya estaba hecho.")
    return {"done": True}


GOOGLE_CALENDAR_WEB = "https://calendar.google.com/calendar/r/agenda"


def _calendar_web_url() -> str:
    """Google Calendar en la vista de agenda, en la cuenta dueña de los
    calendarios (authuser): si el navegador tiene varias cuentas de Google, sin
    esto se abre la que Google tenga por defecto."""
    email = calendar_provider.account_email()
    return f"{GOOGLE_CALENDAR_WEB}?authuser={quote(email)}" if email else GOOGLE_CALENDAR_WEB


@router.get("/calendar")
def calendar_events(day: int = 0) -> dict:
    if not calendar_provider.is_configured():
        return {
            "configured": False,
            "events": [],
            "open_url": GOOGLE_CALENDAR_WEB,
            "can_write": calendar_writer.is_configured(),
        }
    try:
        return {
            "configured": True,
            "events": calendar_provider.get_events(day),
            "open_url": _calendar_web_url(),
            "can_write": calendar_writer.is_configured(),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"No se pudo leer el calendario: {exc}") from exc


class NewEventRequest(BaseModel):
    text: str


@router.post("/calendar/events")
def add_calendar_event(body: NewEventRequest) -> dict:
    """"Lumina, agenda dentista mañana a las 5": con el Apps Script configurado
    lo crea directo; si no (o si Google falla), devuelve Google Calendar con
    el evento ya lleno para que la persona solo toque Guardar."""
    try:
        event = calendar_writer.parse_event_request(body.text)
    except calendar_writer.EventRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    when = calendar_writer.spoken_when(event)
    summary = {
        "title": event["title"],
        "start": event["start"].isoformat(),
        "end": event["end"].isoformat() if event["end"] else None,
        "all_day": event["all_day"],
    }
    if calendar_writer.is_configured():
        try:
            calendar_writer.create_event(event)
            return {"created": True, "event": summary, "speech": f"Listo, agendé {event['title']} {when}."}
        except calendar_writer.CalendarUnconfirmed as exc:
            # Pudo haberse creado: ofrecer "toca Guardar" aquí es como salían
            # los eventos duplicados. Se manda a revisar, no a guardar otra vez.
            logger.warning("Google no confirmó el evento: %s", exc)
            return {
                "created": False,
                "unconfirmed": True,
                "event": summary,
                "open_url": _calendar_web_url(),
                "speech": (
                    f"Google tardó demasiado en contestar y no pude confirmar si {event['title']} quedó guardado. "
                    "Revisa tu calendario antes de agendarlo otra vez."
                ),
            }
        except Exception as exc:  # token malo, script borrado...
            logger.warning("No se pudo crear el evento en Google Calendar: %s", exc)
            fallback = "No pude agendarlo directo, así que"
    else:
        fallback = None

    open_url = calendar_writer.template_url(event, calendar_provider.account_email())
    ready = f"te dejé {event['title']} {when} listo en Google Calendar. Solo toca Guardar."
    speech = f"{fallback} {ready}" if fallback else ready[0].upper() + ready[1:]
    return {"created": False, "event": summary, "open_url": open_url, "speech": speech}


@router.get("/integrations/status")
def integrations_status() -> dict:
    return {
        **channel_status(),
        "calendar": calendar_provider.is_configured(),
        "contacts": contacts.is_configured(),
        "camera": camera.is_running() or nodes.any_online(),
        "voice_key": bool(os.environ.get("ELEVENLABS_API_KEY")),
    }


# ---------------------------------------------------------------------------
# Visión (Bloque 5): la cámara vive en backend/vision.py, aquí solo se
# expone. Arranca/para bajo demanda — no siempre encendida.
# ---------------------------------------------------------------------------


@router.post("/vision/start")
def start_vision() -> dict:
    try:
        camera.start()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"running": True}


@router.post("/vision/stop")
def stop_vision() -> dict:
    camera.stop()
    return {"running": False}


@router.get("/vision/status")
def vision_status() -> dict:
    return {"running": camera.is_running()}


@router.get("/vision/detections")
def vision_detections() -> dict:
    if not camera.is_running() and nodes.any_online():
        return {"running": True, "detections": nodes.labels_seen()}
    return {"running": camera.is_running(), "detections": camera.get_detections()}


@router.get("/vision/objects")
def searchable_objects() -> list[str]:
    return list(SEARCHABLE_OBJECTS)


@router.get("/vision/stream")
def vision_stream() -> StreamingResponse:
    def frames():
        while True:
            jpeg = camera.get_latest_jpeg()
            if jpeg is not None:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            # limita a ~15 fps salgan o no frames nuevos: sin esto el generador
            # reenvía el mismo jpeg sin parar y satura la conexión (visto en
            # pruebas: >300MB en 3s de un solo cliente).
            time.sleep(1 / 15)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.post("/vision/calibrate_door")
def calibrate_door() -> dict:
    if not camera.is_running() and nodes.any_online():
        nodes.enqueue({"do": "calibrate_door"})  # la cámara de la entrada toma su foto de referencia
        return {"calibrated": True}
    if not camera.calibrate_door():
        raise HTTPException(status_code=503, detail="Todavía no hay un frame de la cámara para calibrar.")
    return {"calibrated": True}


class FindRequest(BaseModel):
    object: str


# Quién lleva la búsqueda en curso: la cámara de esta computadora o los nodos
# (la Raspberry). Así el estado y el cancelar le preguntan al correcto.
_search_via = "local"


@router.post("/vision/find")
def find_object(body: FindRequest) -> dict:
    global _search_via
    if not camera.is_running() and nodes.any_online():
        target = map_object_name(body.object)
        if target is None:
            raise HTTPException(
                status_code=422,
                detail=f"No sé buscar '{body.object}' con la cámara. Objetos que sí reconozco: "
                f"{', '.join(sorted(set(OBJECT_NAME_MAP)))}.",
            )
        nodes.start_search(body.object.strip(), target)
        _search_via = "nodes"
        return {"status": "searching"}
    _search_via = "local"
    result = camera.start_search(body.object)
    if not result["ok"]:
        raise HTTPException(
            status_code=422,
            detail=f"No sé buscar '{body.object}' con la cámara. Objetos que sí reconozco: "
            f"{', '.join(result['supported'])}.",
        )
    return {"status": "searching"}


@router.get("/vision/find/status")
def find_object_status() -> dict:
    return nodes.search_status() if _search_via == "nodes" else camera.get_search_status()


@router.post("/vision/find/cancel")
def cancel_find_object() -> dict:
    camera.cancel_search()
    nodes.cancel_search()
    return {"status": "idle"}


# ---------------------------------------------------------------------------
# Nodos de visión (la Raspberry Pi con 4 cámaras, vision_node/). Mandan solo
# lo que cambió; el servidor decide igual que con cualquier otra fuente.
# Protegidos con X-Lumina-Token (DEVICE_TOKEN en .env) cuando está configurado.
# ---------------------------------------------------------------------------


def _check_device(token: str | None) -> None:
    if not nodes.token_ok(token):
        raise HTTPException(status_code=401, detail="Token de dispositivo inválido.")


class NodeHeartbeat(BaseModel):
    cameras: list[dict] = []
    stream_url: str | None = None
    temp_c: float | None = None


class NodeFound(BaseModel):
    camera: str
    zone: str | None = None
    confidence: float = 0.0


@router.get("/vision/nodes")
def list_nodes() -> list[dict]:
    return nodes.summary()


@router.post("/vision/nodes/{node_id}/heartbeat")
def node_heartbeat(node_id: str, body: NodeHeartbeat, x_lumina_token: str | None = Header(default=None)) -> dict:
    _check_device(x_lumina_token)
    nodes.heartbeat(node_id, body.model_dump())
    return {"ok": True}


@router.post("/vision/nodes/{node_id}/detections")
def node_detections(
    node_id: str, body: dict[str, list[dict]], x_lumina_token: str | None = Header(default=None)
) -> dict:
    _check_device(x_lumina_token)
    nodes.set_detections(node_id, body)
    return {"ok": True}


@router.post("/vision/nodes/{node_id}/events")
def node_event(node_id: str, event: EventIn, x_lumina_token: str | None = Header(default=None)) -> dict:
    _check_device(x_lumina_token)
    _, situation = _ingest(event)
    return {"situation": situation}


@router.post("/vision/nodes/{node_id}/found")
def node_found(node_id: str, body: NodeFound, x_lumina_token: str | None = Header(default=None)) -> dict:
    _check_device(x_lumina_token)
    if not nodes.search_found(body.camera, body.zone, body.confidence):
        return {"closed": False}
    label = nodes.search_status().get("object")
    memory.save_event(
        EventIn(
            source=f"{node_id}_{body.camera}",
            type="object_detected",
            location=body.zone,
            confidence=body.confidence,
            metadata={"object": label, "camera": body.camera},
        )
    )
    return {"closed": True}


@router.get("/vision/nodes/{node_id}/commands")
def node_commands(node_id: str, x_lumina_token: str | None = Header(default=None)) -> dict:
    _check_device(x_lumina_token)
    return {"commands": nodes.pop_commands(node_id)}


class FallConfirmRequest(BaseModel):
    ok: bool


@router.post("/vision/fall/confirm")
def confirm_fall(body: FallConfirmRequest) -> dict:
    agent.confirm_fall(body.ok)
    if not body.ok:
        suffix = contacts.escalation_suffix()
        notifier.send(f"Posible caída sin confirmar: la persona indicó que necesita ayuda.{suffix}")
        caller.call(f"Alerta de Super Alexa. Se detectó una posible caída y la persona pidió ayuda.{suffix}")
    return {"acknowledged": True}


@router.get("/contacts")
def list_contacts() -> list[dict]:
    return contacts.get_contacts()


# ---------------------------------------------------------------------------
# Protección ante fraudes/extorsión (sección 3.9): asistente de prevención,
# nunca afirma que un mensaje ES una extorsión — solo qué señales encontró.
# ---------------------------------------------------------------------------


class AnalyzeMessageRequest(BaseModel):
    text: str


@router.post("/messages/analyze")
def analyze_message(body: AnalyzeMessageRequest) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text no puede estar vacío.")
    return fraud_detector.analyze(text)
