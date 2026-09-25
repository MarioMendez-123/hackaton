"""pytest -q — heurísticas puras de visión (sin cámara ni YOLO/MediaPipe reales)
y los endpoints de /vision que no dependen de tener la webcam encendida."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import agent, memory
from backend.integrations import caller, notifier
from backend.vision import (
    camera,
    door_state_from_diff,
    fall_angle_from_points,
    is_fallen_posture,
    map_object_name,
    mean_gray_diff,
)
from server import app


@pytest.fixture(autouse=True)
def _fresh_state(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "DB_PATH", str(tmp_path / "events.db"))
    agent.reset_state()
    camera.reset()
    yield
    camera.reset()


@pytest.fixture()
def client():
    return TestClient(app)


class _FakeBox:
    """Doble de prueba de una caja de ultralytics: solo lo que usa `_detect_and_draw`."""

    def __init__(self, cls_id: int, conf: float, xyxy: list[int]) -> None:
        self.cls = [cls_id]
        self.conf = [conf]
        self.xyxy = [xyxy]


class _FakeYoloResult:
    def __init__(self, boxes: list[_FakeBox]) -> None:
        self.boxes = boxes


class _FakeYolo:
    """Doble de prueba de un modelo YOLO cargado: sin pesos ni inferencia real,
    para probar `_detect_and_draw`/`_register_found_object` sin depender de
    que algo reconocible esté físicamente frente a la webcam."""

    names = {0: "person", 67: "cell phone"}

    def __init__(self, boxes: list[_FakeBox]) -> None:
        self._boxes = boxes

    def __call__(self, frame, verbose: bool = False):
        return [_FakeYoloResult(self._boxes)]


def test_mapea_nombres_en_espanol_a_clases_de_coco():
    assert map_object_name("Celular") == "cell phone"
    assert map_object_name(" mochila ") == "backpack"


def test_objeto_sin_clase_de_coco_no_se_inventa():
    assert map_object_name("llaves") is None
    assert map_object_name("algo que no existe") is None


def test_mean_gray_diff_identico_es_cero():
    frame = np.full((10, 10), 100, dtype=np.uint8)
    assert mean_gray_diff(frame, frame) == 0.0


def test_mean_gray_diff_detecta_cambio():
    a = np.full((10, 10), 100, dtype=np.uint8)
    b = np.full((10, 10), 200, dtype=np.uint8)
    assert mean_gray_diff(a, b) == pytest.approx(100.0)


def test_door_state_from_diff_respeta_umbral():
    assert door_state_from_diff(0.0) == "closed"
    assert door_state_from_diff(1000.0) == "open"


def test_fall_angle_de_pie_es_cercano_a_cero():
    # hombro justo arriba de la cadera (misma x, y menor) = de pie
    angle = fall_angle_from_points(shoulder_mid=(100.0, 50.0), hip_mid=(100.0, 150.0))
    assert angle < 5


def test_fall_angle_acostado_es_cercano_a_noventa():
    # hombro y cadera a la misma altura (y igual), separados en x = acostado
    angle = fall_angle_from_points(shoulder_mid=(50.0, 100.0), hip_mid=(150.0, 100.0))
    assert angle > 85


def test_is_fallen_posture_usa_el_umbral_configurado():
    assert is_fallen_posture((100.0, 50.0), (100.0, 150.0)) is False
    assert is_fallen_posture((50.0, 100.0), (150.0, 100.0)) is True


def _run(detector, frames):
    """frames: (segundo, ángulo del torso, altura de la cadera 0-1)."""
    return [detector.update(t, angle, hip_y) for t, angle, hip_y in frames]


def test_caida_real_rapida_con_caida_de_altura_y_se_queda_abajo():
    from backend.vision import FallDetector

    fired = _run(
        FallDetector(),
        [(0.0, 5, 0.50), (0.3, 10, 0.52), (0.6, 40, 0.62), (0.9, 80, 0.80), (2.0, 85, 0.82), (3.5, 85, 0.82)],
    )
    assert fired == [False, False, False, False, False, True]  # a los 2.6 s abajo


def test_caida_avisa_una_sola_vez_mientras_sigue_abajo():
    from backend.vision import FallDetector

    fired = _run(FallDetector(), [(0, 5, 0.5), (0.5, 85, 0.8), (3.1, 85, 0.8), (4, 85, 0.8), (9, 85, 0.8)])
    assert fired.count(True) == 1


def test_acostarse_despacio_no_es_caida():
    from backend.vision import FallDetector

    # sentarse (a medio camino) varios segundos y luego acostarse
    frames = [(0, 5, 0.5), (1, 40, 0.6), (3, 45, 0.62), (5, 80, 0.8), (9, 85, 0.8)]
    assert True not in _run(FallDetector(), frames)


def test_acostarse_rapido_desde_sentado_no_es_caida_porque_la_cadera_no_baja():
    from backend.vision import FallDetector

    # sentado en el sillón (torso casi vertical, cadera ya baja) y se recuesta
    frames = [(0, 20, 0.75), (0.6, 80, 0.78), (4, 85, 0.78)]
    assert True not in _run(FallDetector(), frames)


def test_agacharse_y_levantarse_no_es_caida():
    from backend.vision import FallDetector

    frames = [(0, 5, 0.5), (0.4, 70, 0.7), (1.5, 70, 0.7), (2.0, 10, 0.5), (5, 10, 0.5)]
    assert True not in _run(FallDetector(), frames)


def test_despues_de_levantarse_puede_detectar_otra_caida():
    from backend.vision import FallDetector

    detector = FallDetector()
    first = _run(detector, [(0, 5, 0.5), (0.5, 85, 0.8), (3.1, 85, 0.8)])
    second = _run(detector, [(10, 5, 0.5), (10.5, 85, 0.8), (13.1, 85, 0.8)])
    assert first[-1] is True and second[-1] is True


def test_caida_reportada_es_critica_y_requiere_confirmacion():
    agent.report_possible_fall("kitchen", confidence=None)
    assert agent.evaluate_fall_state() == {
        "situation": "possible_fall",
        "severity": "critical",
        "requires_confirmation": True,
    }


def test_confirmar_estoy_bien_cierra_la_alerta_de_caida():
    agent.report_possible_fall("kitchen", confidence=None)
    agent.confirm_fall(True)
    assert agent.evaluate_fall_state()["situation"] == "normal"


def test_caida_gana_por_severidad_sobre_riesgo_de_cocina(client):
    client.post("/events", json={"source": "camera_kitchen", "type": "stove_on", "location": "kitchen"})
    client.post(
        "/events",
        json={"source": "pir_kitchen", "type": "motion", "location": "kitchen", "metadata": {"person_present": False}},
    )
    agent.report_possible_fall("livingroom", confidence=None)
    situation = client.get("/situation").json()
    assert situation["situation"] == "possible_fall"
    assert situation["severity"] == "critical"


def test_buscar_objeto_no_soportado_explica_cuales_si(client):
    response = client.post("/vision/find", json={"object": "llaves"})
    assert response.status_code == 422
    assert "celular" in response.json()["detail"]


def test_buscar_objeto_soportado_queda_en_busqueda(client):
    response = client.post("/vision/find", json={"object": "celular"})
    assert response.json() == {"status": "searching"}
    assert client.get("/vision/find/status").json()["status"] == "searching"


def test_cancelar_busqueda_la_corta_sin_esperar_el_timeout(client):
    client.post("/vision/find", json={"object": "celular"})
    response = client.post("/vision/find/cancel")
    assert response.json() == {"status": "idle"}
    assert client.get("/vision/find/status").json()["status"] == "idle"


def test_confirmar_caida_ok_falso_avisa_por_notificacion_y_llama(client):
    agent.report_possible_fall("livingroom", confidence=None)
    notify_before, call_before = len(notifier.sent), len(caller.calls)
    client.post("/vision/fall/confirm", json={"ok": False})
    assert len(notifier.sent) == notify_before + 1
    assert len(caller.calls) == call_before + 1
    assert agent.evaluate_fall_state()["situation"] == "possible_fall"


def test_confirmar_caida_nombra_al_contacto_si_esta_configurado(client, monkeypatch, tmp_path):
    import json as json_module

    from backend import contacts

    path = tmp_path / "contacts.json"
    path.write_text(json_module.dumps([{"name": "Mamá"}]), encoding="utf-8")
    monkeypatch.setattr(contacts, "CONTACTS_PATH", str(path))

    agent.report_possible_fall("livingroom", confidence=None)
    client.post("/vision/fall/confirm", json={"ok": False})
    assert "Notificando a Mamá" in notifier.sent[-1]
    assert "Notificando a Mamá" in caller.calls[-1]


def test_confirmar_caida_ok_verdadero_limpia_la_situacion(client):
    agent.report_possible_fall("livingroom", confidence=None)
    client.post("/vision/fall/confirm", json={"ok": True})
    assert client.get("/situation").json()["situation"] == "normal"


# ---- "¿Estás bien?" con cuenta regresiva y aviso automático -------------------------


def _backdate_fall(seconds):
    from datetime import datetime, timedelta, timezone

    agent._STATE["_fall"]["detected_at"] = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def test_caida_nueva_pregunta_con_cuenta_regresiva(client):
    agent.report_possible_fall("kitchen", confidence=None)
    fall = client.get("/home/overview").json()["fall"]
    assert fall["active"] is True and fall["status"] == "asking"
    assert 29 <= fall["seconds_left"] <= 30


def test_nadie_contesta_y_avisa_solo_una_vez():
    from backend import api

    agent.report_possible_fall("kitchen", confidence=None)
    assert api.check_fall_escalation() is False  # todavía hay tiempo
    _backdate_fall(31)
    notify_before, call_before = len(notifier.sent), len(caller.calls)
    assert api.check_fall_escalation() is True
    assert api.check_fall_escalation() is False  # no vuelve a avisar
    assert len(notifier.sent) == notify_before + 1 and len(caller.calls) == call_before + 1
    assert "nadie respondió" in notifier.sent[-1]
    assert agent.fall_status()["status"] == "escalated"


def test_si_contesta_estoy_bien_a_tiempo_no_avisa_a_nadie(client):
    from backend import api

    agent.report_possible_fall("kitchen", confidence=None)
    client.post("/vision/fall/confirm", json={"ok": True})
    _backdate_fall(31)
    notify_before = len(notifier.sent)
    assert api.check_fall_escalation() is False
    assert len(notifier.sent) == notify_before


def test_despues_de_avisar_estoy_bien_cierra_la_alerta(client):
    from backend import api

    agent.report_possible_fall("kitchen", confidence=None)
    _backdate_fall(31)
    api.check_fall_escalation()
    assert client.get("/home/overview").json()["summary"]["detail"] == "Nadie contestó, así que ya avisé a tu contacto."
    client.post("/vision/fall/confirm", json={"ok": True})
    assert client.get("/situation").json()["situation"] == "normal"


def test_una_caida_nueva_no_reinicia_la_cuenta_de_la_que_sigue_abierta():
    agent.report_possible_fall("kitchen", confidence=None)
    _backdate_fall(20)
    assert agent.report_possible_fall("kitchen", confidence=None) is False
    assert agent.fall_status()["seconds_left"] <= 10


def test_otra_fuente_puede_reportar_caida_por_eventos_sin_avisar_de_inmediato(client):
    notify_before = len(notifier.sent)
    client.post("/events", json={"source": "demo", "type": "possible_fall", "location": "kitchen"})
    assert agent.fall_status()["status"] == "asking"
    assert len(notifier.sent) == notify_before  # primero se pregunta, luego se avisa


def test_calibrar_puerta_sin_frame_todavia_no_inventa(client):
    response = client.post("/vision/calibrate_door")
    assert response.status_code == 503


def test_vision_status_sin_arrancar(client):
    assert client.get("/vision/status").json() == {"running": False}


# ---------------------------------------------------------------------------
# Pipeline de detección real (YOLO simulado): sin webcam apuntando a un
# objeto reconocible no se puede probar el flujo "encontrado" en vivo, así
# que se ejercita el mismo código (`_detect_and_draw`/`_register_found_object`)
# que corre en el loop real, con un modelo falso en vez de pesos de verdad.
# ---------------------------------------------------------------------------


def test_persona_detectada_actualiza_ocupancia_de_cocina(client):
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    yolo = _FakeYolo([_FakeBox(cls_id=0, conf=0.9, xyxy=[10, 10, 50, 50])])  # person
    person_present = camera._detect_and_draw(frame, yolo)
    assert person_present is True

    camera._apply_occupancy(person_present)
    assert client.get("/state").json()["kitchen"]["occupancy"] == "occupied"


def test_buscar_objeto_lo_encuentra_lo_muestra_y_lo_registra_en_memoria(client):
    camera.start_search("celular")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    yolo = _FakeYolo([_FakeBox(cls_id=67, conf=0.83, xyxy=[5, 5, 40, 40])])  # cell phone

    camera._detect_and_draw(frame, yolo)

    status = camera.get_search_status()
    assert status["status"] == "found"
    assert status["object"] == "celular"
    assert status["location"] == "kitchen"

    remembered = client.get("/memory/object", params={"name": "celular"}).json()
    assert remembered["found"] is True


def test_deteccion_por_debajo_del_umbral_de_confianza_se_ignora(client):
    camera.start_search("celular")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    yolo = _FakeYolo([_FakeBox(cls_id=67, conf=0.1, xyxy=[5, 5, 40, 40])])  # bajo YOLO_CONF_THRESHOLD

    camera._detect_and_draw(frame, yolo)

    assert camera.get_search_status()["status"] == "searching"


def test_calibrar_puerta_y_luego_detectar_cambio_emite_evento(client):
    camera._last_frame_gray = np.zeros((10, 10), dtype=np.uint8)
    assert camera.calibrate_door() is True

    changed_frame = np.full((10, 10), 255, dtype=np.uint8)
    camera._apply_door_state(changed_frame)

    assert client.get("/state").json()["home"]["door"] == "open"
