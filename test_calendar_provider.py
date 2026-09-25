"""pytest -q — backend/calendar_provider.py: URL secreta de iCal en vez de
OAuth, incluyendo que expanda eventos recurrentes (RRULE) de verdad."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from backend import calendar_provider


def _make_ics(fixed_event_date: str) -> bytes:
    return (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "BEGIN:VEVENT\n"
        "UID:1\n"
        f"DTSTART:{fixed_event_date}T070000Z\n"
        f"DTEND:{fixed_event_date}T080000Z\n"
        "SUMMARY:Clase de matematicas\n"
        "END:VEVENT\n"
        "BEGIN:VEVENT\n"
        "UID:2\n"
        "DTSTART:20200101T090000Z\n"
        "DTEND:20200101T100000Z\n"
        "RRULE:FREQ=DAILY\n"
        "SUMMARY:Reunion diaria\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    ).encode()


def test_is_configured_false_sin_url(monkeypatch, tmp_path):
    monkeypatch.setattr(calendar_provider, "URL_FILE_PATH", str(tmp_path / "no_existe.txt"))
    monkeypatch.delenv("GOOGLE_CALENDAR_ICAL_URL", raising=False)
    assert calendar_provider.is_configured() is False


def test_is_configured_true_con_archivo_guardado(monkeypatch, tmp_path):
    url_file = tmp_path / "url.txt"
    url_file.write_text("http://fake/calendar.ics")
    monkeypatch.setattr(calendar_provider, "URL_FILE_PATH", str(url_file))
    monkeypatch.delenv("GOOGLE_CALENDAR_ICAL_URL", raising=False)
    assert calendar_provider.is_configured() is True


def test_get_events_lee_evento_fijo_y_expande_el_recurrente(monkeypatch, tmp_path):
    today_str = datetime.now().strftime("%Y%m%d")
    ics_bytes = _make_ics(today_str)

    url_file = tmp_path / "url.txt"
    url_file.write_text("http://fake/calendar.ics")
    monkeypatch.setattr(calendar_provider, "URL_FILE_PATH", str(url_file))
    monkeypatch.delenv("GOOGLE_CALENDAR_ICAL_URL", raising=False)

    fake_response = MagicMock()
    fake_response.__enter__.return_value.read.return_value = ics_bytes
    with patch("backend.calendar_provider.urllib.request.urlopen", return_value=fake_response):
        events = calendar_provider.get_events(day_offset=0)

    summaries = {e["summary"] for e in events}
    assert "Clase de matematicas" in summaries
    assert "Reunion diaria" in summaries  # 2020-01-01 + RRULE:FREQ=DAILY -> también hoy


def test_varios_calendarios_se_juntan_y_uno_caido_no_tumba_a_los_demas(monkeypatch, tmp_path):
    today_str = datetime.now().strftime("%Y%m%d")
    url_file = tmp_path / "url.txt"
    url_file.write_text("http://fake/principal.ics\n# comentario\n\nhttp://fake/rutina.ics\nhttp://fake/caido.ics\n")
    monkeypatch.setattr(calendar_provider, "URL_FILE_PATH", str(url_file))
    monkeypatch.delenv("GOOGLE_CALENDAR_ICAL_URL", raising=False)

    def fake_urlopen(url, timeout):
        if "caido" in url:
            raise OSError("404")
        response = MagicMock()
        response.__enter__.return_value.read.return_value = _make_ics(today_str)
        return response

    with patch("backend.calendar_provider.urllib.request.urlopen", side_effect=fake_urlopen):
        events = calendar_provider.get_events(0)

    # dos calendarios con los mismos 2 eventos -> sin duplicados
    assert sorted(e["summary"] for e in events) == ["Clase de matematicas", "Reunion diaria"]


def test_cuenta_dueña_sale_de_la_url(monkeypatch, tmp_path):
    url_file = tmp_path / "url.txt"
    url_file.write_text(
        "https://calendar.google.com/calendar/ical/abc123%40group.calendar.google.com/private-x/basic.ics\n"
        "https://calendar.google.com/calendar/ical/alguien%40gmail.com/private-y/basic.ics\n"
    )
    monkeypatch.setattr(calendar_provider, "URL_FILE_PATH", str(url_file))
    monkeypatch.delenv("GOOGLE_CALENDAR_ICAL_URL", raising=False)
    assert calendar_provider.account_email() == "alguien@gmail.com"


def test_get_events_lanza_si_no_esta_configurado(monkeypatch, tmp_path):
    monkeypatch.setattr(calendar_provider, "URL_FILE_PATH", str(tmp_path / "no_existe.txt"))
    monkeypatch.delenv("GOOGLE_CALENDAR_ICAL_URL", raising=False)
    try:
        calendar_provider.get_events(0)
        assert False, "debía lanzar RuntimeError"
    except RuntimeError:
        pass
