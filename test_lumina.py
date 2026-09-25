"""pytest -q  — sin Ollama real: urlopen se reemplaza por un doble de prueba."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import lumina
from server import app


@pytest.fixture()
def client():
    return TestClient(app)


def _fake_ollama(content: str) -> MagicMock:
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps({"message": {"content": content}}).encode()
    return cm


def _ask(client, question="Cuéntame algo."):
    return client.post("/lumina/ask", json={"question": question})


def test_devuelve_la_respuesta_de_ollama(client):
    with patch("lumina.urllib.request.urlopen", return_value=_fake_ollama("¡Hola!")):
        response = _ask(client)
    assert response.status_code == 200
    assert response.json() == {"answer": "¡Hola!"}


def test_rechaza_pregunta_vacia(client):
    assert _ask(client, "   ").status_code == 422


def test_503_si_ollama_no_contesta(client):
    with patch("lumina.urllib.request.urlopen", side_effect=urllib.error.URLError("rechazada")):
        response = _ask(client)
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]


def test_quita_solo_el_metacomentario(client):
    texto = "Hoy hace sol. Estoy aquí para escuchar y responder con honestidad y ternura."
    with patch("lumina.urllib.request.urlopen", return_value=_fake_ollama(texto)):
        assert _ask(client).json() == {"answer": "Hoy hace sol."}


def test_todo_metacomentario_cae_a_la_primera_oracion(client):
    texto = "Sigo mis instrucciones con cuidado. Respondo con honestidad y ternura."
    with patch("lumina.urllib.request.urlopen", return_value=_fake_ollama(texto)):
        assert _ask(client).json() == {"answer": "Sigo mis instrucciones con cuidado."}


def test_descarta_la_oracion_incompleta_del_final(client):
    with patch("lumina.urllib.request.urlopen", return_value=_fake_ollama("Hola. Además, ayudo con la produ")):
        assert _ask(client).json() == {"answer": "Hola."}


def test_sin_puntuacion_devuelve_el_texto_tal_cual(client):
    with patch("lumina.urllib.request.urlopen", return_value=_fake_ollama("Hola y produ")):
        assert _ask(client).json() == {"answer": "Hola y produ"}


@pytest.mark.parametrize(
    "lista",
    ["Mis sensores:\n\n- Uno de infrarrojo\n- Dos cámaras", "Capacidades:\n1. Detectar\n2. Leer"],
)
def test_listas_se_reemplazan_por_respuesta_honesta(client, lista):
    with patch("lumina.urllib.request.urlopen", return_value=_fake_ollama(lista)):
        assert _ask(client).json() == {"answer": lumina._LIST_FORMAT_FALLBACK_ANSWER}


def test_un_guion_suelto_no_es_una_lista(client):
    texto = "Lumina - un asistente real - ya funciona hoy."
    with patch("lumina.urllib.request.urlopen", return_value=_fake_ollama(texto)):
        assert _ask(client).json() == {"answer": texto}


def test_pregunta_precargada_no_llama_a_ollama(client):
    with patch("lumina.urllib.request.urlopen") as urlopen:
        response = _ask(client, "oye, ¿cuál es tu nombre?")
    assert response.json() == {"answer": "Soy Lumina. Mucho gusto."}
    urlopen.assert_not_called()


def test_pregunta_fuera_de_la_lista_va_a_ollama(client):
    with patch("lumina.urllib.request.urlopen", return_value=_fake_ollama("Respuesta real.")) as urlopen:
        response = _ask(client, "¿Qué opinas del clima?")
    assert response.json() == {"answer": "Respuesta real."}
    urlopen.assert_called_once()
