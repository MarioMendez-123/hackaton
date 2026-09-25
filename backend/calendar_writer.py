"""Agregar eventos a Google Calendar por voz ("agenda dentista mañana a las 5").

Dos caminos, del más simple al más automático:

1. Sin configurar nada: `template_url()` arma un enlace de Google Calendar
   con el evento ya lleno; la persona solo toca "Guardar".
2. Automático: un Google Apps Script publicado como aplicación web en la
   cuenta del dueño (ver apps_script_calendario.gs). Sin proyecto de Google
   Cloud ni OAuth: Google pide el permiso una sola vez al publicarlo. Su URL y
   un token secreto viven en `google_calendar_webapp.json` (gitignorado).

`parse_event_request()` entiende fechas y horas como se dicen en México y
nunca inventa: si falta cuándo o qué, lo dice.
"""

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote

CONFIG_PATH = os.environ.get(
    "GOOGLE_CALENDAR_WEBAPP_FILE", os.path.join(os.path.dirname(__file__), "..", "google_calendar_webapp.json")
)

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}  # fmt: skip
WEEKDAYS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
WEEKDAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTH_NAMES = [None, "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
               "agosto", "septiembre", "octubre", "noviembre", "diciembre"]  # fmt: skip
NUMBER_WORDS = {
    "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
}  # fmt: skip

_FOLD = str.maketrans("áéíóúüñ¿?¡!,;«»\"", "aeiouun         ")

_HOUR = r"(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")"
_PERIOD = r"(?:\s+(de\s+la\s+(?:manana|tarde|noche|madrugada)|en\s+la\s+(?:manana|tarde|noche)|del\s+mediodia|[ap]\.?\s*m\.?(?=\s|$)))?"
_RANGE_RE = re.compile(
    r"\bde\s+(?:las?\s+)?" + _HOUR + r"(?::(\d{2}))?\s+a\s+(?:las?\s+)?" + _HOUR + r"(?::(\d{2}))?" + _PERIOD
)
_TIME_RE = re.compile(
    r"\b(?:a\s+las?|a\s+la|las)\s+" + _HOUR + r"(?::(\d{2}))?(?:\s+y\s+(media|cuarto|\d{1,2}))?(?:\s+(?:hrs|horas))?" + _PERIOD
)
_NOON_RE = re.compile(r"\b(?:al|a)\s+medio\s*dia\b")
_DAY_AFTER_RE = re.compile(r"\bpasado\s+manana\b")
_TOMORROW_RE = re.compile(r"(?<!la )(?<!pasado )\bmanana\b")
_TODAY_RE = re.compile(r"\bhoy\b")
_WEEKDAY_RE = re.compile(
    r"\b(?:el\s+|este\s+|el\s+proximo\s+|proximo\s+)?(lunes|martes|miercoles|jueves|viernes|sabado|domingo)(?:\s+que\s+viene)?\b"
)
_DATE_RE = re.compile(r"\b(?:el\s+)?(\d{1,2})\s+de\s+(" + "|".join(MONTHS) + r")(?:\s+(?:de|del)\s+(\d{4}))?\b")
_MARKERS_RE = re.compile(
    r"\b(?:(?:en|a|para)\s+(?:mi|el|la)\s+(?:calendario|agenda)|(?:un\s+)?evento(?:\s+de)?)\b"
)
# "hoy en la noche a las 9": el momento del día puede ir antes de la hora.
_LOOSE_PERIOD_RE = re.compile(r"\b(?:en|de|por)\s+la\s+(manana|tarde|noche|madrugada)\b")
_EDGE_WORDS = {"el", "la", "los", "las", "para", "a", "de", "del", "al", "que", "y", "en", "un", "una", "con", "por"}


class EventRequestError(ValueError):
    """Falta algo para agendar; el mensaje se puede decir tal cual."""


def _hour_value(raw: str) -> int:
    return NUMBER_WORDS.get(raw) or int(raw)


def _resolve_hour(hour: int, period: str | None) -> int:
    period = (period or "").replace(".", "").replace(" ", "")
    if "tarde" in period or "noche" in period or period == "pm":
        return hour + 12 if hour < 12 else hour
    if "manana" in period or "madrugada" in period or period == "am":
        return 0 if hour == 12 else hour
    if "mediodia" in period:
        return 12
    # Sin "de la tarde": 1 a 7 casi siempre es en la tarde (citas, juntas).
    return hour + 12 if 1 <= hour <= 7 else hour


def _minutes(clock: str | None, extra: str | None) -> int:
    if clock:
        return int(clock)
    if extra == "media":
        return 30
    if extra == "cuarto":
        return 15
    return int(extra) if extra else 0


def _loose_period(folded: str, removed: list[tuple[int, int]]) -> str | None:
    match = _LOOSE_PERIOD_RE.search(folded)
    if not match:
        return None
    removed.append(match.span())
    return match.group(1)


def parse_event_request(text: str, now: datetime | None = None) -> dict:
    """"dentista mañana a las 5 de la tarde" -> {title, start, end, all_day}.

    Lanza EventRequestError con una frase lista para decir si falta el qué o
    el cuándo. `now` es para las pruebas."""
    now = now or datetime.now().astimezone()
    original = " ".join(text.split())  # conserva mayúsculas: "Junta con Ana"
    folded = original.lower().translate(_FOLD)
    removed: list[tuple[int, int]] = []

    def take(match: re.Match) -> re.Match:
        removed.append(match.span())
        return match

    start_time: time | None = None
    end_time: time | None = None
    if (m := _RANGE_RE.search(folded)) :
        take(m)
        h1, m1, h2, m2, period = m.groups()
        period = period or _loose_period(folded, removed)
        start_time = time(_resolve_hour(_hour_value(h1), period), int(m1 or 0))
        end_time = time(_resolve_hour(_hour_value(h2), period), int(m2 or 0))
    elif (m := _TIME_RE.search(folded)) :
        take(m)
        hour, clock, extra, period = m.groups()
        period = period or _loose_period(folded, removed)
        start_time = time(_resolve_hour(_hour_value(hour), period), _minutes(clock, extra))
    elif (m := _NOON_RE.search(folded)) :
        take(m)
        start_time = time(12, 0)

    today = now.date()
    day: date | None = None
    if (m := _DAY_AFTER_RE.search(folded)) :
        take(m)
        day = today + timedelta(days=2)
    elif (m := _TOMORROW_RE.search(folded)) :
        take(m)
        day = today + timedelta(days=1)
    elif (m := _TODAY_RE.search(folded)) :
        take(m)
        day = today
    elif (m := _DATE_RE.search(folded)) :
        take(m)
        number, month_name, year = m.groups()
        day = date(int(year) if year else today.year, MONTHS[month_name], int(number))
        if not year and day < today:
            day = day.replace(year=today.year + 1)
    elif (m := _WEEKDAY_RE.search(folded)) :
        take(m)
        ahead = (WEEKDAYS[m.group(1)] - today.weekday()) % 7
        if ahead == 0 and (start_time is None or start_time <= now.time()):
            ahead = 7
        day = today + timedelta(days=ahead)

    if day is None and start_time is None:
        raise EventRequestError("¿Para qué día y hora? Dímelo así: agenda dentista mañana a las 5.")
    if day is None:  # solo hora: hoy si todavía no pasa, si no mañana
        day = today if start_time > now.time() else today + timedelta(days=1)

    for pattern in (_MARKERS_RE, _LOOSE_PERIOD_RE):
        removed.extend(m.span() for m in pattern.finditer(folded))
    kept = [ch for i, ch in enumerate(original) if not any(a <= i < b for a, b in removed)]
    words = "".join(kept).replace(":", " ").split()
    while words and words[0].lower() in _EDGE_WORDS:
        words.pop(0)
    while words and words[-1].lower() in _EDGE_WORDS:
        words.pop()
    title = " ".join(words).strip(" .")
    if not title:
        raise EventRequestError("¿Qué evento agendo? Dímelo así: agenda dentista mañana a las 5.")
    title = title[0].upper() + title[1:]

    tz = now.tzinfo
    if start_time is None:
        return {"title": title, "start": datetime.combine(day, time(12), tz), "end": None, "all_day": True}
    start = datetime.combine(day, start_time, tz)
    end = datetime.combine(day, end_time, tz) if end_time else start + timedelta(hours=1)
    if end <= start:
        end += timedelta(days=1)
    return {"title": title, "start": start, "end": end, "all_day": False}


def spoken_when(event: dict, now: datetime | None = None) -> str:
    """"mañana a las 5 de la tarde", "el viernes 3 de octubre"."""
    now = now or datetime.now().astimezone()
    start: datetime = event["start"]
    delta = (start.date() - now.date()).days
    if delta == 0:
        day = "hoy"
    elif delta == 1:
        day = "mañana"
    elif delta == 2:
        day = "pasado mañana"
    else:
        day = f"el {WEEKDAY_NAMES[start.weekday()]} {start.day} de {MONTH_NAMES[start.month]}"
    if event["all_day"]:
        return day
    hour12 = start.hour % 12 or 12
    minutes = "" if start.minute == 0 else " y media" if start.minute == 30 else f" y {start.minute}"
    period = (
        "de la madrugada" if start.hour < 6 else
        "de la mañana" if start.hour < 12 else
        "de la tarde" if start.hour < 19 else "de la noche"
    )  # fmt: skip
    article = "a la" if hour12 == 1 else "a las"
    return f"{day} {article} {hour12}{minutes} {period}"


def template_url(event: dict, account: str | None = None) -> str:
    """Google Calendar con el evento ya lleno: solo falta tocar "Guardar"."""
    if event["all_day"]:
        first = event["start"].date()
        dates = f"{first:%Y%m%d}/{first + timedelta(days=1):%Y%m%d}"
    else:
        utc = timezone.utc
        dates = f"{event['start'].astimezone(utc):%Y%m%dT%H%M%SZ}/{event['end'].astimezone(utc):%Y%m%dT%H%M%SZ}"
    url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={quote(event['title'])}&dates={dates}"
    return f"{url}&authuser={quote(account)}" if account else url


def _config() -> dict:
    env_url = os.environ.get("GOOGLE_CALENDAR_WEBAPP_URL")
    if env_url:
        return {"url": env_url, "token": os.environ.get("GOOGLE_CALENDAR_WEBAPP_TOKEN", "")}
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def is_configured() -> bool:
    return bool(_config().get("url"))


# Medido contra el script real: tarda 10-30 s en contestar, y ~2 de cada 5
# veces Google responde 404 al entregar la respuesta AUNQUE el evento sí se
# creó. Por eso se reintenta con el mismo requestId (el script no duplica).
ATTEMPTS = 3
TIMEOUT_SECONDS = 40


class CalendarUnconfirmed(RuntimeError):
    """Google no contestó a tiempo: el evento pudo o no haberse creado."""


def _post(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        # Con el User-Agent por defecto ("Python-urllib/…") la redirección de
        # abajo responde 404 siempre (verificado contra un script real).
        headers={"Content-Type": "application/json", "User-Agent": "LuminaAgent/1.0 (Super Alexa)"},
        method="POST",
    )
    # Apps Script responde con una redirección a googleusercontent.com;
    # urllib la sigue sola (como GET) y ahí viene la respuesta del script.
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def create_event(event: dict) -> None:
    """Lo crea de verdad vía el Apps Script. Lanza RuntimeError si el script
    lo rechaza y CalendarUnconfirmed si Google nunca contestó."""
    config = _config()
    payload = {
        "token": config.get("token", ""),
        "requestId": uuid.uuid4().hex,
        "title": event["title"],
        "start": event["start"].isoformat(),
        "end": event["end"].isoformat() if event["end"] else None,
        "allDay": event["all_day"],
    }
    last_error: Exception | None = None
    for _ in range(ATTEMPTS):
        try:
            body = _post(config["url"], payload)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):  # el script pide sesión: reintentar no sirve
                raise RuntimeError("El script de Google pide iniciar sesión (revisa 'Quién tiene acceso').") from exc
            last_error = exc
            continue
        except (OSError, ValueError) as exc:  # tiempo agotado, red, respuesta que no es JSON
            last_error = exc
            continue
        if not body.get("ok"):
            raise RuntimeError(body.get("error", "Google no confirmó el evento."))
        return
    raise CalendarUnconfirmed(f"Google no contestó ({last_error}).")
