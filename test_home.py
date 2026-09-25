"""pytest -q — modo protección, salida/llegada, recordatorios, resumen de la
casa y los endpoints nuevos de la consola."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import agent, api, briefing, calendar_provider, calendar_writer, memory, reminders
from backend.vision import camera
from server import app


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "DB_PATH", str(tmp_path / "events.db"))
    # Hay una URL real de Google Calendar guardada en el repo: sin esto, cada
    # "salgo de casa" de las pruebas saldría a la red.
    monkeypatch.setattr(calendar_provider, "is_configured", lambda: False)
    monkeypatch.setattr(calendar_writer, "is_configured", lambda: False)
    agent.reset_state()
    camera.reset()
    api._last_critical_call_at = 0.0
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def _post(client, **event):
    return client.post("/events", json=event).json()


# ---- modo protección -------------------------------------------------------


def test_armar_y_abrir_la_puerta_dentro_del_retardo_de_salida_no_alerta():
    agent.set_protection(True)
    agent.apply_event({"type": "door_open", "timestamp": datetime.now(timezone.utc).isoformat()})
    assert agent.evaluate_home_state()["situation"] == "normal"


def test_puerta_abierta_con_proteccion_armada_pasado_el_retardo_es_critica():
    agent.set_protection(True)
    agent._STATE["_armed_at"] = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    agent.apply_event({"type": "door_open", "timestamp": datetime.now(timezone.utc).isoformat()})
    assert agent.evaluate_home_state() == {
        "situation": "door_open_while_armed",
        "severity": "critical",
        "requires_confirmation": True,
    }


def test_desarmar_quita_la_alerta_de_puerta():
    agent.set_protection(True)
    agent._STATE["_armed_at"] = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    agent.apply_event({"type": "door_open", "timestamp": datetime.now(timezone.utc).isoformat()})
    agent.set_protection(False)
    assert agent.evaluate_home_state()["situation"] == "normal"


def test_endpoint_de_proteccion_cambia_el_estado(client):
    assert client.post("/home/protection", json={"armed": True}).json()["armed"] is True
    assert client.get("/state").json()["home"]["security"] == "armed"
    client.post("/home/protection", json={"armed": False})
    assert client.get("/state").json()["home"]["security"] == "disarmed"


# ---- salida / llegada -------------------------------------------------------


def test_salir_arma_vacia_la_casa_y_se_despide(client):
    body = client.post("/home/depart").json()
    assert body["state"]["home"]["security"] == "armed"
    assert body["state"]["home"]["occupancy"] == "empty"
    assert body["state"]["kitchen"]["occupancy"] == "empty"
    assert body["speech"].endswith("Activé la protección. Que te vaya bien.")


def test_salir_con_la_estufa_encendida_lo_dice_primero(client):
    _post(client, source="camera_kitchen", type="stove_on", location="kitchen")
    body = client.post("/home/depart").json()
    assert body["situation"]["situation"] == "potential_kitchen_risk"
    assert body["speech"].startswith("Antes de irte: la estufa sigue encendida")


def test_salir_con_la_puerta_abierta_pide_cerrarla(client):
    _post(client, source="camera_door", type="door_open")
    assert "Cierra la puerta al salir." in client.post("/home/depart").json()["speech"]


def test_salir_lee_recordatorios_de_salida_y_generales_pero_no_los_de_llegada(client):
    reminders.add("sacar la basura", "leave")
    reminders.add("comprar leche", "any")
    reminders.add("regar las plantas", "arrive")
    speech = client.post("/home/depart").json()["speech"]
    assert "Recuerda: sacar la basura y comprar leche." in speech
    assert "regar las plantas" not in speech


def test_llegar_desarma_y_lee_lo_pendiente_de_llegada(client):
    client.post("/home/depart")
    reminders.add("regar las plantas", "arrive")
    body = client.post("/home/arrive").json()
    assert body["state"]["home"]["security"] == "disarmed"
    assert body["state"]["home"]["occupancy"] == "occupied"
    assert body["speech"] == "Qué bueno que llegaste. Tenías pendiente: regar las plantas. Desactivé la protección."


# ---- recordatorios -----------------------------------------------------------


def test_recordatorios_crear_listar_y_completar(client):
    created = client.post("/reminders", json={"text": "llamar a mamá", "trigger": "arrive"}).json()
    assert [r["text"] for r in client.get("/reminders").json()] == ["llamar a mamá"]
    assert client.post(f"/reminders/{created['id']}/done").json() == {"done": True}
    assert client.get("/reminders").json() == []
    assert client.post(f"/reminders/{created['id']}/done").status_code == 404


def test_recordatorio_vacio_o_con_momento_invalido_es_422(client):
    assert client.post("/reminders", json={"text": "  "}).status_code == 422
    assert client.post("/reminders", json={"text": "algo", "trigger": "manana"}).status_code == 422


# ---- resumen de la casa ------------------------------------------------------


def test_resumen_sin_lecturas_no_inventa_nada():
    summary = briefing.house_summary(agent.get_state(), agent.evaluate_home_state())
    assert summary == {"headline": "Todo en calma.", "detail": "Todavía no tengo lecturas. Enciende la cámara para empezar."}


def test_resumen_con_hechos_conocidos():
    agent.apply_event({"type": "door_closed"})
    agent.apply_event({"type": "motion", "location": "home", "metadata": {"person_present": True}})
    summary = briefing.house_summary(agent.get_state(), agent.evaluate_home_state())
    assert summary == {"headline": "Todo en calma.", "detail": "La puerta está cerrada. Hay alguien en casa."}


def test_resumen_con_riesgo_de_cocina():
    agent.apply_event({"type": "stove_on", "location": "kitchen"})
    agent.apply_event({"type": "motion", "location": "kitchen", "metadata": {"person_present": False}})
    summary = briefing.house_summary(agent.get_state(), agent.evaluate_home_state())
    assert summary["headline"] == "Revisa la cocina."
    assert summary["detail"] == "La estufa sigue encendida y no hay nadie en la cocina."


def test_resumen_con_proteccion_armada():
    agent.set_protection(True)
    assert briefing.house_summary(agent.get_state(), agent.evaluate_home_state())["headline"] == "La casa está protegida."


def test_overview_trae_todo_en_una_peticion(client):
    _post(client, source="camera_door", type="door_closed")
    body = client.get("/home/overview").json()
    assert set(body) == {"state", "situation", "summary", "fall", "events"}
    assert body["fall"] == {"active": False}
    assert body["summary"]["detail"] == "La puerta está cerrada."
    assert body["events"][0]["type"] == "door_closed"


def test_join_es():
    assert briefing.join_es(["a"]) == "a"
    assert briefing.join_es(["a", "b"]) == "a y b"
    assert briefing.join_es(["a", "b", "c"]) == "a, b y c"


def test_formato_de_eventos_de_calendario():
    future = (datetime.now().astimezone() + timedelta(hours=2)).replace(minute=5, second=0, microsecond=0)
    past = datetime.now().astimezone() - timedelta(hours=2)
    assert briefing._format_event({"summary": "Clase", "start": future.isoformat()}) == (
        f"Clase a las {future.hour}:05"
    )
    assert briefing._format_event({"summary": "Ya pasó", "start": past.isoformat()}) is None
    assert briefing._format_event({"summary": "Cumpleaños", "start": "2026-09-25"}) == "Cumpleaños"


# ---- alertas, canales, calendario, visión --------------------------------------


def test_avisar_a_contacto_sin_situacion_activa_es_409(client):
    assert client.post("/alerts/escalate").status_code == 409


def test_avisar_a_contacto_con_riesgo_manda_la_notificacion(client):
    from backend.integrations import notifier

    _post(client, source="camera_kitchen", type="stove_on", location="kitchen")
    _post(client, source="pir_kitchen", type="motion", location="kitchen", metadata={"person_present": False})
    before = len(notifier.sent)
    assert client.post("/alerts/escalate").json() == {"sent": True}
    assert len(notifier.sent) == before + 1
    assert "la estufa sigue encendida" in notifier.sent[-1]


def test_estado_de_canales(client):
    body = client.get("/integrations/status").json()
    assert {"n8n", "telegram", "whatsapp", "calls", "elevenlabs", "calendar", "contacts", "camera"} <= set(body)
    assert body["calendar"] is False
    assert body["camera"] is False


def test_calendario_no_configurado(client):
    assert client.get("/calendar").json() == {
        "configured": False,
        "events": [],
        "open_url": "https://calendar.google.com/calendar/r/agenda",
        "can_write": False,
    }


def test_calendario_se_abre_en_la_cuenta_dueña(client, monkeypatch):
    monkeypatch.setattr(calendar_provider, "is_configured", lambda: True)
    monkeypatch.setattr(calendar_provider, "account_email", lambda: "alguien@gmail.com")
    monkeypatch.setattr(calendar_provider, "get_events", lambda day: [])
    body = client.get("/calendar").json()
    assert body["open_url"] == "https://calendar.google.com/calendar/r/agenda?authuser=alguien%40gmail.com"


def test_objetos_buscables_y_detecciones_con_camara_apagada(client):
    assert "celular" in client.get("/vision/objects").json()
    assert client.get("/vision/detections").json() == {"running": False, "detections": []}


class _Box:
    def __init__(self, cls_id, conf):
        self.cls, self.conf, self.xyxy = [cls_id], [conf], [[1, 1, 20, 20]]


class _Yolo:
    names = {0: "person", 41: "cup"}

    def __init__(self, boxes):
        self._boxes = boxes

    def __call__(self, frame, verbose=False):
        return [type("R", (), {"boxes": self._boxes})()]


def test_detecciones_se_guardan_en_espanol():
    camera._detect_and_draw(np.zeros((40, 40, 3), dtype=np.uint8), _Yolo([_Box(0, 0.9), _Box(41, 0.7)]))
    assert camera._last_detections == [
        {"label": "persona", "confidence": 0.9},
        {"label": "taza", "confidence": 0.7},
    ]
