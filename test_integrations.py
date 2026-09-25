"""pytest -q — selección de proveedor de notificaciones (n8n/Twilio/mock),
sin depender de si n8n o Twilio están realmente configurados en la máquina
que corre las pruebas."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from backend import integrations


def test_build_notifier_sin_env_vars_es_mock(monkeypatch):
    monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_FROM", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert isinstance(integrations._build_notifier(), integrations.MockNotificationProvider)


def test_build_notifier_con_telegram_lo_incluye(monkeypatch):
    monkeypatch.delenv("N8N_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    provider = integrations._build_notifier()
    assert isinstance(provider, integrations.CompositeNotificationProvider)
    assert any(isinstance(p, integrations.TelegramProvider) for p in provider._providers)


def test_telegram_provider_postea_al_bot_correcto():
    import os

    os.environ["TELEGRAM_BOT_TOKEN"] = "123:abc"
    os.environ["TELEGRAM_CHAT_ID"] = "999"
    try:
        provider = integrations.TelegramProvider()
    finally:
        del os.environ["TELEGRAM_BOT_TOKEN"]
        del os.environ["TELEGRAM_CHAT_ID"]

    fake_response = MagicMock()
    fake_response.__enter__.return_value.read.return_value = b"{}"
    with patch("backend.integrations.urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
        provider.send("hola")
    request = mock_urlopen.call_args[0][0]
    assert request.full_url == "https://api.telegram.org/bot123:abc/sendMessage"
    assert json.loads(request.data) == {"chat_id": "999", "text": "hola"}


def test_build_notifier_con_n8n_url_lo_incluye(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/superalexa-alert")
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    provider = integrations._build_notifier()
    assert isinstance(provider, integrations.CompositeNotificationProvider)
    assert any(isinstance(p, integrations.N8nWebhookNotificationProvider) for p in provider._providers)


def test_n8n_provider_postea_json_al_webhook():
    provider = integrations.N8nWebhookNotificationProvider("http://localhost:5678/webhook/superalexa-alert")
    fake_response = MagicMock()
    fake_response.__enter__.return_value.read.return_value = b"{}"
    with patch("backend.integrations.urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
        provider.send("hola")
    request = mock_urlopen.call_args[0][0]
    assert request.full_url == "http://localhost:5678/webhook/superalexa-alert"
    assert json.loads(request.data) == {"message": "hola"}


def test_composite_sigue_con_los_demas_si_uno_falla():
    class Fails(integrations.NotificationProvider):
        def send(self, message):
            raise RuntimeError("caído")

    ok = integrations.MockNotificationProvider()
    composite = integrations.CompositeNotificationProvider([Fails(), ok])
    composite.send("hola")
    assert ok.sent == ["hola"]


def test_n8n_provider_propaga_timeout_pero_composite_lo_absorbe():
    provider = integrations.N8nWebhookNotificationProvider("http://localhost:5678/webhook/superalexa-alert")
    ok = integrations.MockNotificationProvider()
    composite = integrations.CompositeNotificationProvider([provider, ok])
    with patch("backend.integrations.urllib.request.urlopen", side_effect=urllib.error.URLError("n8n caído")):
        composite.send("hola")
    assert ok.sent == ["hola"]
