"""pytest -q — nodo de visión de la Raspberry (vision_node/) y su lado del
servidor (backend/nodes.py), sin cámaras reales: imágenes y detecciones falsas."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import agent, api, memory, nodes
from backend.vision import camera
from server import app
from vision_node.logic import CameraLogic, small_gray
from vision_node.runtime import Reporter


@pytest.fixture(autouse=True)
def _fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "DB_PATH", str(tmp_path / "events.db"))
    monkeypatch.setattr(nodes, "DEVICE_TOKEN", "")
    agent.reset_state()
    camera.reset()
    nodes.reset()
    api._search_via = "local"
    yield


def frame(value: int) -> np.ndarray:
    return np.full((480, 640, 3), value, dtype=np.uint8)


PERSON = [{"label": "person", "confidence": 0.9, "box": [10, 10, 100, 200]}]


# ---- lógica de cada cámara ---------------------------------------------------------


def test_solo_analiza_si_algo_se_mueve_o_si_ya_toca_revisar():
    cam = CameraLogic("cocina", "kitchen", ["people"])
    quieto = small_gray(frame(100))
    assert cam.needs_inference(quieto, 0.0) is True  # primera vez: siempre
    cam.on_detections([], 0.0)
    assert cam.needs_inference(quieto, 1.0) is False  # nada se movió
    assert cam.needs_inference(small_gray(frame(160)), 2.0) is True  # se movió algo
    cam.on_detections([], 2.0)
    assert cam.needs_inference(small_gray(frame(160)), 7.5) is True  # 5 s sin revisar


def test_presencia_solo_se_reporta_cuando_se_sostiene():
    cam = CameraLogic("cocina", "kitchen", ["people"])
    assert cam.on_detections(PERSON, 0.0) == []
    assert cam.on_detections(PERSON, 1.0) == []
    [event] = cam.on_detections(PERSON, 2.1)
    assert event == {
        "source": "pi_cocina",
        "type": "motion",
        "location": "kitchen",
        "metadata": {"camera": "cocina", "person_present": True},
    }
    assert cam.on_detections(PERSON, 3.0) == []  # sigue igual: no repite
    assert cam.on_detections([], 4.0) == []
    assert cam.on_detections([], 6.5)[0]["metadata"]["person_present"] is False


def test_detecciones_quedan_en_espanol_para_la_consola():
    cam = CameraLogic("sala", "hallway", ["people"])
    cam.on_detections([{"label": "cup", "confidence": 0.71, "box": [0, 0, 5, 5]}], 0.0)
    assert cam.detections == [{"label": "taza", "confidence": 0.71}]


def test_puerta_necesita_calibrar_y_avisa_al_cambiar():
    cam = CameraLogic("entrada", "entrance", ["door"])
    assert cam.door_update(small_gray(frame(100)), 0.0) == []  # sin calibrar: no inventa
    cam.request_calibration()
    cam.door_update(small_gray(frame(100)), 1.0)
    assert cam.door_update(small_gray(frame(100)), 2.1)[0]["type"] == "door_closed"
    assert cam.door_update(small_gray(frame(200)), 3.0) == []  # tiene que sostenerse
    assert cam.door_update(small_gray(frame(200)), 4.1)[0]["type"] == "door_open"


def test_caida_se_reporta_una_vez_con_la_pose():
    cam = CameraLogic("sala", "hallway", ["people", "falls"])
    cam.on_detections(PERSON, 0.0)
    assert cam.wants_pose(1.0) is True
    events = []
    for t, torso in [(0.0, (5, 0.5)), (0.5, (85, 0.8)), (3.1, (85, 0.8)), (4.0, (85, 0.8))]:
        events += cam.fall_update(torso, t)
    assert [e["type"] for e in events] == ["possible_fall"]
    assert events[0]["location"] == "hallway"


def test_pose_solo_donde_se_vio_a_alguien_hace_poco():
    cam = CameraLogic("sala", "hallway", ["people", "falls"])
    assert cam.wants_pose(0.0) is False
    cam.on_detections(PERSON, 10.0)
    assert cam.wants_pose(13.0) is True
    assert cam.wants_pose(20.0) is False
    assert CameraLogic("entrada", "entrance", ["door"]).wants_pose(0.0) is False


def test_encuentra_el_objeto_buscado():
    cam = CameraLogic("cocina", "kitchen", ["people"])
    detections = [{"label": "backpack", "confidence": 0.62, "box": [0, 0, 1, 1]}]
    assert cam.found(detections, "backpack") == 0.62
    assert cam.found(detections, "cell phone") is None


# ---- varias cámaras: la casa está vacía solo si ninguna ve a alguien -----------------


def motion(zone, present):
    agent.apply_event({"type": "motion", "location": zone, "metadata": {"person_present": present}})


def test_una_camara_sin_nadie_no_vacia_la_casa_si_otra_ve_a_alguien():
    motion("hallway", True)
    motion("entrance", False)
    assert agent.get_state()["home"]["occupancy"] == "occupied"
    motion("hallway", False)
    assert agent.get_state()["home"]["occupancy"] == "empty"


def test_alguien_en_la_cocina_tambien_cuenta_como_casa_ocupada():
    motion("entrance", False)
    motion("kitchen", True)
    state = agent.get_state()
    assert (state["home"]["occupancy"], state["kitchen"]["occupancy"]) == ("occupied", "occupied")


def test_salgo_de_casa_por_voz_vacia_todas_las_zonas():
    motion("kitchen", True)
    motion("hallway", True)
    motion("home", False)
    state = agent.get_state()
    assert (state["home"]["occupancy"], state["kitchen"]["occupancy"]) == ("empty", "empty")


# ---- envíos al servidor --------------------------------------------------------------


def test_eventos_se_reintentan_hasta_que_el_servidor_responde():
    sent, attempts = [], []

    def flaky(path, payload):
        attempts.append(path)
        if len(attempts) < 3:
            raise OSError("servidor reiniciando")
        sent.append(payload)

    reporter = Reporter(post=flaky, sleep=lambda s: None)
    reporter.send("/vision/nodes/pi/events", {"type": "possible_fall"})
    reporter.deliver_one()
    assert sent == [{"type": "possible_fall"}] and len(attempts) == 3


def test_lo_que_caduca_no_se_reintenta():
    attempts = []

    def down(path, payload):
        attempts.append(path)
        raise OSError("sin red")

    reporter = Reporter(post=down, sleep=lambda s: None)
    reporter.send("/vision/nodes/pi/heartbeat", {}, retry=False)
    reporter.deliver_one()
    assert len(attempts) == 1


# ---- servidor --------------------------------------------------------------------------


@pytest.fixture()
def client():
    return TestClient(app)


def heartbeat(client, **extra):
    return client.post(
        "/vision/nodes/pi/heartbeat",
        json={
            "cameras": [{"id": "cocina", "zone": "kitchen", "ok": True}, {"id": "sala", "zone": "hallway", "ok": True}],
            "stream_url": "http://raspberrypi.local:8001",
            **extra,
        },
    )


def test_latido_registra_el_nodo_y_sus_camaras(client):
    assert heartbeat(client, temp_c=61.5).status_code == 200
    [node] = client.get("/vision/nodes").json()
    assert node["online"] is True and node["temp_c"] == 61.5
    assert [c["id"] for c in node["cameras"]] == ["cocina", "sala"]
    assert client.get("/integrations/status").json()["camera"] is True


def test_con_token_configurado_rechaza_a_quien_no_lo_trae(client, monkeypatch):
    monkeypatch.setattr(nodes, "DEVICE_TOKEN", "secreto")
    assert heartbeat(client).status_code == 401
    ok = client.post("/vision/nodes/pi/heartbeat", json={}, headers={"X-Lumina-Token": "secreto"})
    assert ok.status_code == 200


def test_evento_del_nodo_entra_al_motor_de_situaciones(client):
    body = client.post(
        "/vision/nodes/pi/events",
        json={"source": "pi_sala", "type": "possible_fall", "location": "hallway"},
    ).json()
    assert body["situation"]["situation"] == "possible_fall"
    assert agent.fall_status()["status"] == "asking"


def test_busqueda_repartida_en_las_camaras_del_nodo(client):
    heartbeat(client)
    assert client.post("/vision/find", json={"object": "mochila"}).json() == {"status": "searching"}
    commands = client.get("/vision/nodes/pi/commands").json()["commands"]
    assert commands == [{"do": "find", "object": "backpack", "label": "mochila"}]
    assert client.get("/vision/find/status").json()["status"] == "searching"

    closed = client.post("/vision/nodes/pi/found", json={"camera": "sala", "zone": "hallway", "confidence": 0.62})
    assert closed.json() == {"closed": True}
    status = client.get("/vision/find/status").json()
    assert (status["status"], status["object"], status["location"]) == ("found", "mochila", "hallway")
    assert client.get("/events/recent?limit=1").json()[0]["type"] == "object_detected"


def test_objeto_que_no_se_puede_buscar_es_422_tambien_con_nodos(client):
    heartbeat(client)
    assert client.post("/vision/find", json={"object": "llaves"}).status_code == 422


def test_detecciones_del_nodo_llegan_a_la_consola(client):
    heartbeat(client)
    client.post("/vision/nodes/pi/detections", json={"cocina": [{"label": "persona", "confidence": 0.9}]})
    body = client.get("/vision/detections").json()
    assert body["running"] is True
    assert body["detections"] == [{"label": "persona", "confidence": 0.9, "camera": "cocina", "zone": "kitchen"}]


def test_calibrar_puerta_se_manda_al_nodo(client):
    heartbeat(client)
    assert client.post("/vision/calibrate_door").json() == {"calibrated": True}
    assert client.get("/vision/nodes/pi/commands").json()["commands"] == [{"do": "calibrate_door"}]


def test_nodo_sin_latido_se_marca_desconectado(client, monkeypatch):
    heartbeat(client)
    monkeypatch.setattr(nodes, "ONLINE_SECONDS", -1)
    assert client.get("/vision/nodes").json()[0]["online"] is False
    assert client.get("/integrations/status").json()["camera"] is False
