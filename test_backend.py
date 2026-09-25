"""pytest -q — motor de situaciones, memoria y API del backend."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend import agent, api, calendar_provider, memory
from backend.integrations import caller
from server import app


@pytest.fixture(autouse=True)
def _fresh_state_and_db(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "DB_PATH", str(tmp_path / "events.db"))
    agent.reset_state()
    api._last_critical_call_at = 0.0
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def test_estufa_encendida_cocina_vacia_dispara_riesgo(client):
    client.post("/events", json={"source": "camera_kitchen", "type": "stove_on", "location": "kitchen"})
    client.post(
        "/events",
        json={"source": "pir_kitchen", "type": "motion", "location": "kitchen", "metadata": {"person_present": False}},
    )
    response = client.post(
        "/events",
        json={"source": "bme280_kitchen", "type": "temperature", "location": "kitchen", "value": 38.5},
    )
    body = response.json()
    assert body["situation"] == {"situation": "potential_kitchen_risk", "severity": "warning", "requires_confirmation": True}
    assert body["state"]["home"]["risk_level"] == "warning"


def test_estufa_encendida_con_alguien_presente_no_es_riesgo(client):
    client.post("/events", json={"source": "camera_kitchen", "type": "stove_on", "location": "kitchen"})
    response = client.post(
        "/events",
        json={"source": "pir_kitchen", "type": "motion", "location": "kitchen", "metadata": {"person_present": True}},
    )
    assert response.json()["situation"]["situation"] == "normal"


def test_humo_o_flama_es_critico_aunque_no_haya_temperatura(client):
    client.post("/events", json={"source": "camera_kitchen", "type": "stove_on", "location": "kitchen"})
    client.post(
        "/events",
        json={"source": "mq2_kitchen", "type": "smoke", "location": "kitchen", "metadata": {"level": "critical"}},
    )
    response = client.post(
        "/events",
        json={"source": "pir_kitchen", "type": "motion", "location": "kitchen", "metadata": {"person_present": False}},
    )
    assert response.json()["situation"]["severity"] == "critical"


def test_situacion_critica_dispara_una_llamada(client):
    before = len(caller.calls)
    client.post("/events", json={"source": "camera_kitchen", "type": "stove_on", "location": "kitchen"})
    client.post(
        "/events",
        json={"source": "mq2_kitchen", "type": "smoke", "location": "kitchen", "metadata": {"level": "critical"}},
    )
    client.post(
        "/events",
        json={"source": "pir_kitchen", "type": "motion", "location": "kitchen", "metadata": {"person_present": False}},
    )
    assert len(caller.calls) == before + 1


def test_situacion_critica_no_repite_llamada_en_cada_evento(client):
    events = [
        {"source": "camera_kitchen", "type": "stove_on", "location": "kitchen"},
        {"source": "mq2_kitchen", "type": "smoke", "location": "kitchen", "metadata": {"level": "critical"}},
        {"source": "pir_kitchen", "type": "motion", "location": "kitchen", "metadata": {"person_present": False}},
        {"source": "bme280_kitchen", "type": "temperature", "location": "kitchen", "value": 90},
    ]
    before = len(caller.calls)
    for event in events:
        client.post("/events", json=event)
    assert len(caller.calls) == before + 1


def test_nivel_de_sensor_desconocido_no_se_inventa_como_normal(client):
    client.post(
        "/events",
        json={"source": "mq2_kitchen", "type": "smoke", "location": "kitchen", "metadata": {"level": "algo_raro"}},
    )
    assert client.get("/state").json()["kitchen"]["smoke"] == "unknown"


def test_objeto_no_encontrado_no_inventa_ubicacion(client):
    response = client.get("/memory/object", params={"name": "llaves"})
    assert response.json() == {"found": False}


def test_objeto_encontrado_devuelve_ultima_ubicacion_observada(client):
    client.post(
        "/events",
        json={
            "source": "camera_livingroom",
            "type": "object_detected",
            "location": "sala",
            "confidence": 0.9,
            "metadata": {"object": "llaves"},
        },
    )
    result = client.get("/memory/object", params={"name": "llaves"}).json()
    assert result["found"] is True
    assert result["location"] == "sala"


def test_puerta_abierta_poco_tiempo_no_alerta():
    home = {"door": "open", "occupancy": "empty"}
    recent = datetime.now(timezone.utc).isoformat()
    assert agent.evaluate_security_state(home, recent)["situation"] == "normal"


def test_puerta_abierta_mucho_tiempo_casa_vacia_alerta():
    home = {"door": "open", "occupancy": "empty"}
    long_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    result = agent.evaluate_security_state(home, long_ago)
    assert result == {"situation": "door_open_empty_house", "severity": "warning", "requires_confirmation": True}


def test_endpoint_situation_reevalua_por_reloj_sin_evento_nuevo(client):
    long_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    client.post("/events", json={"source": "camera_door", "type": "door_open", "timestamp": long_ago})
    client.post(
        "/events",
        json={"source": "pir_livingroom", "type": "motion", "location": "livingroom", "metadata": {"person_present": False}},
    )
    # Sin postear ningún evento nuevo: /situation debe reflejar que ya pasó el umbral de tiempo.
    assert client.get("/situation").json()["situation"] == "door_open_empty_house"


def test_lumina_responde_objeto_con_memoria_real(client):
    client.post(
        "/events",
        json={
            "source": "camera_livingroom",
            "type": "object_detected",
            "location": "mesa de la sala",
            "confidence": 0.9,
            "metadata": {"object": "llaves"},
            "timestamp": "2026-09-24T12:43:00+00:00",
        },
    )
    response = client.post("/lumina/ask", json={"question": "¿Dónde están mis llaves?"})
    assert response.json() == {"answer": "La última vez que lo vi fue en mesa de la sala, a las 12:43."}


def test_lumina_sin_registro_no_inventa_ubicacion(client):
    response = client.post("/lumina/ask", json={"question": "¿Dónde está mi cartera?"})
    assert response.json() == {"answer": "No tengo un registro reciente de eso."}


def test_lumina_calendario_no_conectado_no_inventa(client, monkeypatch):
    monkeypatch.setattr(calendar_provider, "is_configured", lambda: False)
    response = client.post("/lumina/ask", json={"question": "¿Qué tengo hoy?"})
    assert response.json() == {"answer": "Todavía no tengo tu Google Calendar conectado."}


def test_lumina_calendario_responde_con_eventos_reales(client, monkeypatch):
    monkeypatch.setattr(calendar_provider, "is_configured", lambda: True)
    monkeypatch.setattr(
        calendar_provider, "get_events", lambda day_offset: [{"summary": "Clase", "start": "2026-09-25T07:00:00"}]
    )
    response = client.post("/lumina/ask", json={"question": "¿Qué tengo mañana?"})
    assert response.json() == {"answer": "Para mañana tienes: Clase."}


@pytest.mark.parametrize(
    ("question", "day"),
    [
        ("¿Qué tengo hoy?", 0),
        ("¿Qué tengo en mi agenda hoy?", 0),
        ("¿Qué hay en mi calendario?", 0),
        ("¿Qué tengo que hacer hoy?", 0),
        ("¿Qué tengo hoy en la mañana?", 0),
        ("¿Qué tengo mañana?", 1),
        ("¿Qué tengo para mañana?", 1),
        ("mi agenda de mañana", 1),
        ("¿Cómo estás?", None),
    ],
)
def test_lumina_entiende_preguntas_de_agenda(question, day):
    from lumina import _match_calendar_query

    assert _match_calendar_query(question) == day


def test_lumina_calendario_sin_eventos_lo_dice_tal_cual(client, monkeypatch):
    monkeypatch.setattr(calendar_provider, "is_configured", lambda: True)
    monkeypatch.setattr(calendar_provider, "get_events", lambda day_offset: [])
    response = client.post("/lumina/ask", json={"question": "¿Qué tengo hoy?"})
    assert response.json() == {"answer": "No tienes nada agendado para hoy."}
