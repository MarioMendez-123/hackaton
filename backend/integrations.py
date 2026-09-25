"""Integraciones reales (sección 3.7/3.10/23): n8n + Twilio (WhatsApp y
llamadas de voz). La app nunca sabe qué proveedor hay detrás — `api.py` solo
usa `notifier`/`caller`; cuál implementación se activa depende de qué
variables de entorno existan, nunca de una detección "ambiental" (si n8n
resulta estar corriendo o no) — así el comportamiento es el mismo en tests
que en producción, sin sorpresas según qué esté prendido en la máquina.

Sin credenciales de Twilio (no hay forma de generarlas por código: requiere
crear una cuenta, verificar identidad y un número — eso solo lo puede hacer
el dueño de la cuenta), cae sola al mock y lo dice en el log, nunca falla en
silencio ni finge haber mandado algo.
"""

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger("integrations")

# Número al que se manda toda alerta/llamada mientras no haya una lista real
# de contactos autorizados (sección 3.6). Vive en el .env local (ver
# .env.example), nunca en el código: el repositorio es público.
ALERT_PHONE = os.environ.get("TWILIO_ALERT_PHONE", "")


class NotificationProvider:
    def send(self, message: str) -> None:
        raise NotImplementedError


class MockNotificationProvider(NotificationProvider):
    def __init__(self) -> None:
        self.sent: list[str] = []  # para inspección en tests/demo

    def send(self, message: str) -> None:
        print("[MOCK NOTIFY]", message)
        self.sent.append(message)


class N8nWebhookNotificationProvider(NotificationProvider):
    """Manda la alerta al workflow "Super Alexa - Alertas" de n8n
    (Webhook -> Code, ver README). n8n es quien orquesta de ahí en adelante
    (sección 4/23): agregar WhatsApp/Telegram real es un nodo nuevo dentro de
    n8n, no un cambio aquí."""

    def __init__(self, url: str) -> None:
        self._url = url

    def send(self, message: str) -> None:
        request = urllib.request.Request(
            self._url,
            data=json.dumps({"message": message}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()


class CompositeNotificationProvider(NotificationProvider):
    """Manda por todos los canales configurados; si uno falla, los demás
    siguen (sección 25, regla 12: una función que falla no debe tumbar la
    demo principal)."""

    def __init__(self, providers: list[NotificationProvider]) -> None:
        self._providers = providers

    def send(self, message: str) -> None:
        for provider in self._providers:
            try:
                provider.send(message)
            except Exception:
                logger.exception("Un canal de notificación falló (%s); sigo con los demás.", type(provider).__name__)


class TelegramProvider(NotificationProvider):
    """Sección 3.8: mismo canal que WhatsApp, pero un bot de Telegram se
    consigue gratis e instantáneo con @BotFather — sin cuenta empresarial ni
    verificación de pago, a diferencia de Twilio. Requiere TELEGRAM_BOT_TOKEN
    y TELEGRAM_CHAT_ID."""

    def __init__(self) -> None:
        self._token = os.environ["TELEGRAM_BOT_TOKEN"]
        self._chat_id = os.environ["TELEGRAM_CHAT_ID"]

    def send(self, message: str) -> None:
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self._token}/sendMessage",
            data=json.dumps({"chat_id": self._chat_id, "text": message}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()


class TwilioWhatsAppProvider(NotificationProvider):
    """Requiere TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
    (ej. "whatsapp:+14155238886", el sandbox de Twilio) y TWILIO_ALERT_PHONE."""

    def __init__(self) -> None:
        from twilio.rest import Client

        self._client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        self._from = os.environ["TWILIO_WHATSAPP_FROM"]
        self._to = f"whatsapp:{ALERT_PHONE}"

    def send(self, message: str) -> None:
        self._client.messages.create(from_=self._from, to=self._to, body=message)


class CallProvider:
    def call(self, message: str) -> None:
        raise NotImplementedError


class MockCallProvider(CallProvider):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def call(self, message: str) -> None:
        print("[MOCK LLAMADA]", message)
        self.calls.append(message)


class TwilioCallProvider(CallProvider):
    """Requiere TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_CALL_FROM (un
    número de voz comprado en Twilio) y TWILIO_ALERT_PHONE. Solo se usa para
    severidad crítica (sección 15: acciones con más consecuencia, canal más
    intrusivo) — nunca para avisos normales."""

    def __init__(self) -> None:
        from twilio.rest import Client

        self._client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        self._from = os.environ["TWILIO_CALL_FROM"]
        self._to = ALERT_PHONE

    def call(self, message: str) -> None:
        safe_message = message.replace("&", "y").replace("<", "").replace(">", "")
        twiml = f'<Response><Say language="es-MX">{safe_message}</Say></Response>'
        self._client.calls.create(twiml=twiml, from_=self._from, to=self._to)


def _build_notifier() -> NotificationProvider:
    providers: list[NotificationProvider] = []

    n8n_url = os.environ.get("N8N_WEBHOOK_URL")
    if n8n_url:
        providers.append(N8nWebhookNotificationProvider(n8n_url))
        logger.info("Notificaciones: n8n (%s).", n8n_url)

    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        try:
            providers.append(TelegramProvider())
            logger.info("Notificaciones: Telegram real.")
        except Exception:
            logger.exception("No se pudo inicializar Telegram.")

    if os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_WHATSAPP_FROM") and ALERT_PHONE:
        try:
            providers.append(TwilioWhatsAppProvider())
            logger.info("Notificaciones: WhatsApp real vía Twilio (%s).", ALERT_PHONE)
        except Exception:
            logger.exception("No se pudo inicializar Twilio WhatsApp.")

    if not providers:
        logger.info("Notificaciones: mock (configura N8N_WEBHOOK_URL, TELEGRAM_* y/o TWILIO_*).")
        return MockNotificationProvider()
    return CompositeNotificationProvider(providers)


def _build_caller() -> CallProvider:
    if os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_CALL_FROM") and ALERT_PHONE:
        try:
            provider = TwilioCallProvider()
            logger.info("Llamadas: Twilio real (%s).", ALERT_PHONE)
            return provider
        except Exception:
            logger.exception("No se pudo inicializar Twilio Voice; usando el mock.")
    logger.info("Llamadas: mock (faltan TWILIO_ACCOUNT_SID/TWILIO_CALL_FROM).")
    return MockCallProvider()


def channel_status() -> dict[str, bool]:
    """Qué canales están configurados de verdad (mismo criterio que usa
    `_build_notifier`/`_build_caller`), para que la consola no prometa un
    WhatsApp que no existe."""
    env = os.environ.get
    return {
        "n8n": bool(env("N8N_WEBHOOK_URL")),
        "telegram": bool(env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID")),
        "whatsapp": bool(env("TWILIO_ACCOUNT_SID") and env("TWILIO_WHATSAPP_FROM") and env("TWILIO_ALERT_PHONE")),
        "calls": bool(env("TWILIO_ACCOUNT_SID") and env("TWILIO_CALL_FROM") and env("TWILIO_ALERT_PHONE")),
        "elevenlabs": bool(env("ELEVENLABS_API_KEY")),
    }


notifier = _build_notifier()
caller = _build_caller()
