"""Contactos autorizados (sección 3.6): a quién se nombra al escalar una
situación crítica (caída sin confirmar, riesgo crítico). Vive en
`contacts.json` (gitignorado — son datos personales de alguien real, no
pertenecen al repo). Sin ese archivo, `is_configured()` da False y las
alertas se siguen mandando igual (al canal de `integrations.py`), solo sin
nombrar a nadie — nunca se inventa un contacto que no existe.

Formato de contacts.json:
[
  {"name": "Mamá", "relation": "madre"},
  {"name": "Juan", "relation": "vecino"}
]
"""

import json
import os

CONTACTS_PATH = os.environ.get("CONTACTS_PATH", os.path.join(os.path.dirname(__file__), "..", "contacts.json"))


def is_configured() -> bool:
    return os.path.exists(CONTACTS_PATH)


def get_contacts() -> list[dict]:
    if not is_configured():
        return []
    with open(CONTACTS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def get_primary_contact() -> dict | None:
    """El primero de la lista: a quién se nombra en un mensaje de escalación."""
    contacts = get_contacts()
    return contacts[0] if contacts else None


def escalation_suffix() -> str:
    """' Notificando a X.' si hay un contacto configurado; si no, cadena vacía
    — así el mensaje de alerta no cambia de forma según haya o no contactos."""
    contact = get_primary_contact()
    return f" Notificando a {contact['name']}." if contact else ""
