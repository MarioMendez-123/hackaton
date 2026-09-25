"""pytest -q — backend/contacts.py: sin contacts.json no inventa a nadie."""

import json

from backend import contacts


def test_sin_archivo_no_hay_contactos(monkeypatch, tmp_path):
    monkeypatch.setattr(contacts, "CONTACTS_PATH", str(tmp_path / "no_existe.json"))
    assert contacts.is_configured() is False
    assert contacts.get_contacts() == []
    assert contacts.get_primary_contact() is None
    assert contacts.escalation_suffix() == ""


def test_con_archivo_nombra_al_primer_contacto(monkeypatch, tmp_path):
    path = tmp_path / "contacts.json"
    path.write_text(json.dumps([{"name": "Mamá", "relation": "madre"}, {"name": "Juan"}]), encoding="utf-8")
    monkeypatch.setattr(contacts, "CONTACTS_PATH", str(path))

    assert contacts.is_configured() is True
    assert contacts.get_primary_contact() == {"name": "Mamá", "relation": "madre"}
    assert contacts.escalation_suffix() == " Notificando a Mamá."
