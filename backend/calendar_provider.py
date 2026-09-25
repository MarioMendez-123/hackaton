"""Google Calendar (sección 3.5): "¿qué tengo hoy/mañana?".

Simple a propósito: en vez de credenciales OAuth (proyecto en Google Cloud,
API habilitada, pantalla de consentimiento, login de desarrollador), usa la
"dirección secreta en formato iCal" que Google ya genera para cada
calendario — una URL de solo lectura, sin cuenta de desarrollador de por
medio.

Cómo conseguirla (lo hace el dueño de la cuenta, una vez, ~30 segundos):
  Google Calendar -> ⚙ Configuración -> tu calendario (columna izquierda)
  -> "Integrar calendario" -> copiar "Dirección secreta en formato iCal"

Cada calendario de Google tiene SU propia URL (el principal, "Mi Rutina",
uno compartido...). Se guardan en `google_calendar_url.txt` (gitignorado),
una por línea, y los eventos de todos se juntan. Sin ninguna,
`is_configured()` da False y quien llame debe decir "no conectado", nunca
inventar eventos.
"""

import logging
import os
import re
import urllib.request
from datetime import date, datetime, timedelta
from urllib.parse import unquote

logger = logging.getLogger(__name__)

URL_FILE_PATH = os.environ.get(
    "GOOGLE_CALENDAR_URL_FILE", os.path.join(os.path.dirname(__file__), "..", "google_calendar_url.txt")
)


def _get_urls() -> list[str]:
    """URLs secretas de iCal: la variable de entorno (separadas por espacio) o
    el archivo, una por línea (las que empiezan con # se ignoran)."""
    env_urls = os.environ.get("GOOGLE_CALENDAR_ICAL_URL")
    if env_urls:
        return env_urls.split()
    if not os.path.exists(URL_FILE_PATH):
        return []
    with open(URL_FILE_PATH, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.strip().startswith("#")]


def is_configured() -> bool:
    return bool(_get_urls())


def account_email() -> str | None:
    """Cuenta de Google dueña de los calendarios, sacada de la propia URL
    (.../calendar/ical/<cuenta>/private-.../basic.ics). Sirve para abrir
    Google Calendar en ESA cuenta y no en otra sesión del navegador. Los
    calendarios secundarios tienen un id tipo ...@group.calendar.google.com,
    que no es una cuenta: se saltan."""
    for url in _get_urls():
        match = re.search(r"/calendar/ical/([^/]+)/", url)
        if match:
            calendar_id = unquote(match.group(1))
            if "@" in calendar_id and not calendar_id.endswith("calendar.google.com"):
                return calendar_id
    return None


def _events_from(url: str, target_day: date) -> list[dict]:
    import recurring_ical_events
    from icalendar import Calendar

    with urllib.request.urlopen(url, timeout=10) as response:
        calendar = Calendar.from_ical(response.read())
    # .between() con el mismo día en ambos extremos da un rango de ancho cero
    # (no devuelve nada, verificado a mano) -- hay que pedir el día completo.
    occurrences = recurring_ical_events.of(calendar).between(target_day, target_day + timedelta(days=1))
    events = []
    for component in occurrences:
        start = component.get("dtstart").dt
        start_str = start.isoformat() if isinstance(start, (date, datetime)) else str(start)
        events.append({"summary": str(component.get("summary", "(sin título)")), "start": start_str})
    return events


def get_events(day_offset: int = 0) -> list[dict]:
    """Eventos de hoy (`day_offset=0`) o mañana (`1`) de TODOS los calendarios
    guardados, expandiendo los que se repiten (RRULE). Si un calendario falla,
    se usan los demás; solo lanza si fallan todos. Lanza si no está
    configurado — revisa `is_configured()` antes de llamar."""
    urls = _get_urls()
    if not urls:
        raise RuntimeError("Google Calendar no está configurado.")

    target_day = date.today() + timedelta(days=day_offset)
    events: list[dict] = []
    failures = 0
    for url in urls:
        try:
            events.extend(_events_from(url, target_day))
        except Exception:
            failures += 1
            logger.warning("No se pudo leer uno de los calendarios.", exc_info=True)
            if failures == len(urls):
                raise

    # El mismo evento puede estar en dos calendarios (invitación compartida).
    unique = {(e["summary"], e["start"]): e for e in events}
    return sorted(unique.values(), key=lambda e: e["start"])
