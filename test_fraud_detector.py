"""pytest -q — backend/fraud_detector.py: nunca afirma que algo ES fraude,
solo reporta señales encontradas (sección 3.9)."""

import pytest
from fastapi.testclient import TestClient

from backend import fraud_detector
from server import app


@pytest.fixture()
def client():
    return TestClient(app)


def test_mensaje_normal_no_encuentra_senales():
    result = fraud_detector.analyze("Hola, ¿cómo estás? Nos vemos mañana en la clase.")
    assert result["signals_found"] == []
    assert result["risk_level"] == "bajo"


def test_mensaje_con_varias_senales_es_riesgo_alto():
    message = (
        "Es urgente, tienes 5 minutos: transfiere el dinero ahora mismo o "
        "sabemos dónde vives. No le digas a nadie."
    )
    result = fraud_detector.analyze(message)
    assert result["risk_level"] == "alto"
    assert "urgencia extrema" in result["signals_found"]
    assert "solicitud de dinero o datos financieros" in result["signals_found"]
    assert "amenaza" in result["signals_found"]


def test_extorsion_telefonica_tipica_es_riesgo_alto():
    result = fraud_detector.analyze("Deposita ya o le pasa algo a tu hijo. No llames a la policía.")
    assert result["risk_level"] == "alto"
    assert {"urgencia extrema", "solicitud de dinero o datos financieros", "amenaza"} <= set(result["signals_found"])


def test_falso_familiar_se_marca():
    result = fraud_detector.analyze("¿Sabes quién habla? Soy tu sobrino, estoy en problemas.")
    assert "supuesta emergencia de un familiar" in result["signals_found"]


def test_mensaje_familiar_normal_no_se_marca():
    assert fraud_detector.analyze("Mamá ya llegó a la casa, paso por pan rápido.")["signals_found"] == []


def test_nunca_afirma_que_es_fraude_con_certeza(client):
    response = client.post(
        "/messages/analyze", json={"text": "Transfiere el dinero ahora mismo o habrá consecuencias."}
    )
    body = response.json()
    assert "indicio automático" in body["note"]
    assert "es una extorsión" not in body["note"].lower()
    assert "es fraude" not in body["note"].lower()


def test_analizar_mensaje_vacio_es_422(client):
    response = client.post("/messages/analyze", json={"text": "   "})
    assert response.status_code == 422
