"""pytest -q — agregar eventos a Google Calendar por voz: fechas y horas
dichas como en México, el enlace de "solo toca Guardar" y el endpoint."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend import calendar_provider, calendar_writer
from backend.calendar_writer import EventRequestError, parse_event_request, spoken_when, template_url
from server import app

CHIHUAHUA = timezone(timedelta(hours=-6))
# Viernes 25 de septiembre de 2026, 10:00.
NOW = datetime(2026, 9, 25, 10, 0, tzinfo=CHIHUAHUA)


def at(day: int, hour: int, minute: int = 0, month: int = 9) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=CHIHUAHUA)


@pytest.mark.parametrize(
    ("text", "title", "start", "end"),
    [
        ("dentista mañana a las 5 de la tarde", "Dentista", at(26, 17), at(26, 18)),
        ("una cita con el dentista mañana a las 5", "Cita con el dentista", at(26, 17), at(26, 18)),
        ("Junta con Ana el lunes a las 10", "Junta con Ana", at(28, 10), at(28, 11)),
        ("clase de inglés hoy a las 18:30", "Clase de inglés", at(25, 18, 30), at(25, 19, 30)),
        ("gym a las 7 de la mañana", "Gym", at(26, 7), at(26, 8)),  # ya pasó hoy -> mañana
        ("comida familiar el domingo al mediodía", "Comida familiar", at(27, 12), at(27, 13)),
        ("reunión de 4 a 6 el viernes", "Reunión", at(25, 16), at(25, 18)),
        ("Dentista mañana a las 5:00 p. m.", "Dentista", at(26, 17), at(26, 18)),
        ("un evento: examen pasado mañana a las nueve", "Examen", at(27, 9), at(27, 10)),
        ("hoy en la noche a las 9 cenar con Luis", "Cenar con Luis", at(25, 21), at(25, 22)),
        ("llamar al banco mañana a las 9 y media", "Llamar al banco", at(26, 9, 30), at(26, 10, 30)),
        ("pagar la luz a mi calendario mañana a la una", "Pagar la luz", at(26, 13), at(26, 14)),
    ],
)
def test_entiende_fecha_hora_y_titulo(text, title, start, end):
    event = parse_event_request(text, NOW)
    assert (event["title"], event["start"], event["end"], event["all_day"]) == (title, start, end, False)


def test_sin_hora_es_de_todo_el_dia():
    event = parse_event_request("cumpleaños de mamá el 3 de octubre", NOW)
    assert event["title"] == "Cumpleaños de mamá"
    assert event["all_day"] is True
    assert event["start"].date().isoformat() == "2026-10-03"


def test_fecha_que_ya_paso_este_año_es_el_siguiente():
    assert parse_event_request("aniversario el 2 de enero", NOW)["start"].year == 2027


@pytest.mark.parametrize("text", ["dentista", "mañana a las 5", "un evento"])
def test_si_falta_que_o_cuando_lo_dice_en_vez_de_inventar(text):
    with pytest.raises(EventRequestError):
        parse_event_request(text, NOW)


def test_como_lo_dice_lumina():
    assert spoken_when(parse_event_request("dentista mañana a las 5", NOW), NOW) == "mañana a las 5 de la tarde"
    assert spoken_when(parse_event_request("x hoy a la 1 y media", NOW), NOW) == "hoy a la 1 y media de la tarde"
    assert spoken_when(parse_event_request("fiesta el 3 de octubre", NOW), NOW) == "el sábado 3 de octubre"


def test_enlace_de_google_calendar_con_el_evento_lleno():
    url = template_url(parse_event_request("dentista mañana a las 5", NOW), "alguien@gmail.com")
    assert url == (
        "https://calendar.google.com/calendar/render?action=TEMPLATE&text=Dentista"
        "&dates=20260926T230000Z/20260927T000000Z&authuser=alguien%40gmail.com"
    )
    all_day = template_url(parse_event_request("fiesta el 3 de octubre", NOW))
    assert all_day.endswith("&dates=20261003/20261004")


# ---- reintentos contra Google (medido: 404 al entregar aunque sí se creó) ----------


def _http_error(code):
    import urllib.error

    return urllib.error.HTTPError("https://script.googleusercontent.com/macros/echo", code, "x", {}, None)


def test_reintenta_con_el_mismo_request_id_para_no_duplicar(monkeypatch):
    sent = []

    def fake_post(url, payload):
        sent.append(payload["requestId"])
        if len(sent) == 1:
            raise _http_error(404)  # Google falló al entregar la respuesta
        return {"ok": True, "id": "abc"}

    monkeypatch.setattr(calendar_writer, "_config", lambda: {"url": "https://x/exec", "token": "t"})
    monkeypatch.setattr(calendar_writer, "_post", fake_post)
    calendar_writer.create_event(parse_event_request("dentista mañana a las 5", NOW))
    assert len(sent) == 2 and sent[0] == sent[1]


def test_si_google_nunca_contesta_es_sin_confirmar(monkeypatch):
    def always_timeout(url, payload):
        raise TimeoutError("read timed out")

    monkeypatch.setattr(calendar_writer, "_config", lambda: {"url": "https://x/exec", "token": "t"})
    monkeypatch.setattr(calendar_writer, "_post", always_timeout)
    with pytest.raises(calendar_writer.CalendarUnconfirmed):
        calendar_writer.create_event(parse_event_request("dentista mañana a las 5", NOW))


def test_script_que_pide_sesion_no_se_reintenta(monkeypatch):
    calls = []

    def needs_login(url, payload):
        calls.append(1)
        raise _http_error(401)

    monkeypatch.setattr(calendar_writer, "_config", lambda: {"url": "https://x/exec", "token": "t"})
    monkeypatch.setattr(calendar_writer, "_post", needs_login)
    with pytest.raises(RuntimeError, match="iniciar sesión"):
        calendar_writer.create_event(parse_event_request("dentista mañana a las 5", NOW))
    assert len(calls) == 1


# ---- endpoint ------------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(calendar_provider, "account_email", lambda: None)
    return TestClient(app)


def test_sin_script_deja_el_evento_listo_para_guardar(client, monkeypatch):
    monkeypatch.setattr(calendar_writer, "is_configured", lambda: False)
    body = client.post("/calendar/events", json={"text": "dentista mañana a las 5"}).json()
    assert body["created"] is False
    assert body["open_url"].startswith("https://calendar.google.com/calendar/render?action=TEMPLATE&text=Dentista")
    assert body["speech"] == "Te dejé Dentista mañana a las 5 de la tarde listo en Google Calendar. Solo toca Guardar."


def test_con_script_lo_crea_de_verdad(client, monkeypatch):
    created = []
    monkeypatch.setattr(calendar_writer, "is_configured", lambda: True)
    monkeypatch.setattr(calendar_writer, "create_event", created.append)
    body = client.post("/calendar/events", json={"text": "dentista mañana a las 5"}).json()
    assert body["created"] is True
    assert body["speech"] == "Listo, agendé Dentista mañana a las 5 de la tarde."
    assert created[0]["title"] == "Dentista"


def test_si_google_falla_cae_al_enlace(client, monkeypatch):
    def boom(event):
        raise OSError("sin red")

    monkeypatch.setattr(calendar_writer, "is_configured", lambda: True)
    monkeypatch.setattr(calendar_writer, "create_event", boom)
    body = client.post("/calendar/events", json={"text": "dentista mañana a las 5"}).json()
    assert body["created"] is False
    assert "action=TEMPLATE" in body["open_url"]
    assert body["speech"].startswith("No pude agendarlo directo")


def test_sin_confirmar_manda_a_revisar_no_a_guardar_otra_vez(client, monkeypatch):
    def unconfirmed(event):
        raise calendar_writer.CalendarUnconfirmed("sin respuesta")

    monkeypatch.setattr(calendar_writer, "is_configured", lambda: True)
    monkeypatch.setattr(calendar_writer, "create_event", unconfirmed)
    body = client.post("/calendar/events", json={"text": "dentista mañana a las 5"}).json()
    assert body["unconfirmed"] is True
    assert "action=TEMPLATE" not in body["open_url"]  # abre la agenda, no un evento nuevo
    assert "Revisa tu calendario antes de agendarlo otra vez" in body["speech"]


def test_falta_el_cuando_es_422_con_la_frase_para_decir(client):
    response = client.post("/calendar/events", json={"text": "dentista"})
    assert response.status_code == 422
    assert response.json()["detail"].startswith("¿Para qué día y hora?")
