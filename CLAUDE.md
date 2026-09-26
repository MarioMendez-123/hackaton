# Super Alexa (Lumina) — contexto para Claude Code

Agente doméstico multimodal para el Innovathon 2026. Una sola página web con
dos vistas: **la cara de Lumina** (voz, subtítulos, reloj) y **la consola de la
casa** (cámara, plano, bitácora, agenda). Corre en una pantalla física de la
casa. Todo el texto de interfaz y de voz está en **español de México**.

Principios del documento maestro (`docs/SUPER_ALEXA_INNOVATHON_2026.md`): pipeline `PERCEPCIÓN → EVENTOS → CONTEXTO → SITUACIÓN → DECISIÓN →
ACCIÓN`; **la IA interpreta, las reglas deciden, n8n ejecuta**; **nunca
inventar un estado** (lo desconocido se dice "Sin verificar").

**Empieza por `PLAN_MAESTRO.md`**: diferenciador, qué está hecho, la
Raspberry Pi con 4 cámaras (nodo de visión), todas las comunicaciones y los
pasos de ElevenLabs, Zavu, n8n, AWS y Clerk. **Diferenciador:** "Ellos vigilan
a un paciente; Lumina entiende la casa, actúa por ti (relés/ESP32) y te acompaña
fuera (WhatsApp + Ray-Ban Meta)". No posicionar como cuidado de pacientes.

## Arrancar y probar

```bash
pip install -r requirements.txt   # Python 3.11
copy .env.example .env            # y llenar (ver "Archivos privados")
python server.py                  # http://localhost:8000  (Chrome o Edge)
python -m pytest -q               # incluye voice_commands_check.js (necesita node)
node voice_commands_check.js      # solo los comandos de voz
```

Servicios externos locales: **Ollama** (`ollama pull llama3.2:1b`, preguntas
libres), **n8n** (`n8n start`, importar `n8n/superalexa-alertas.json`).

## Mapa

```
server.py                 FastAPI: carga .env, monta lumina + backend, sirve web/, arranca el vigilante de caídas
lumina.py                 /lumina/ask (respuestas fijas, memoria de objetos, agenda, Ollama) y /lumina/speak (ElevenLabs)
backend/
  events.py               contrato de eventos (EventIn)
  memory.py               historial en SQLite (events.db)
  agent.py                estado de la casa + motor de situaciones (cocina, puerta, protección, caídas)
  api.py                  endpoints; _ingest(); check_fall_escalation() + vigilante; calendario; visión
  briefing.py             textos: resumen de la casa, frases de salida/llegada
  reminders.py            recordatorios (al salir / al llegar / cuando sea)
  vision.py               webcam: YOLOv8n (objetos/personas), puerta por diferencia de imagen, FallDetector (MediaPipe Pose)
  calendar_provider.py    leer Google Calendar (URLs secretas iCal, varias)
  calendar_writer.py      agendar por voz: entiende fechas en español; Apps Script o enlace "toca Guardar"
  integrations.py         avisos: n8n, Telegram, WhatsApp/llamadas Twilio, mocks
  contacts.py             contacto de emergencia (contacts.json)
  fraud_detector.py       anti-extorsión por señales (nunca afirma "es estafa")
web/
  tokens.css              ÚNICA fuente de color/tipo/espacio/movimiento
  app-shell.css/.js       cambio de vista (View Transitions), toasts, reloj, aviso "¿Estás bien?"
  lumina.css/.js          cara, voz (speak), subtítulos, reconocimiento, handlers de comandos
  voice-commands.js       ÚNICO lugar que decide qué frase es qué comando (función pura)
  dashboard.css/.js       consola: /home/overview cada 3 s, cámara, plano, agenda, controlador de caídas
apps_script_calendario.gs script de Google para crear eventos (se pega en script.google.com)
n8n/superalexa-alertas.json  flujo de n8n (webhook superalexa-alert)
voice_commands_check.js   frases reales de Chrome/Edge -> comando esperado
```

## Reglas del proyecto

- **Comandos de voz**: toda regla nueva va en `web/voice-commands.js` y **con su
  frase de prueba** en `voice_commands_check.js`. El texto se "dobla" (sin
  acentos ni puntuación, 1 a 1) porque en JS `\b` no reconoce letras con
  acento. Las órdenes van al inicio de la frase (`start: true`); después de
  despertar no se exige "Lumina" (solo en comandos de la cara).
- **Caídas**: detectar != afirmar. Se pregunta "¿Estás bien?" con 30 s; si nadie
  contesta, el servidor avisa solo (no depende de la página). Respuestas por
  voz en `routeFallReply`. Cualquier cambio: correr `test_vision.py`.
- **Calendario**: el Apps Script tarda 10-30 s y a veces responde 404 aunque sí
  creó el evento: por eso `requestId` + reintentos + estado "sin confirmar".
  Nunca ofrecer "guárdalo otra vez" si no se sabe si se creó.
- **Diseño** ("la casa de noche"): índigo + luz de luna en calma; ámbar/brasa
  SOLO para riesgo. Newsreader (voz de Lumina) + Schibsted Grotesk (UI). Sin
  monoespaciada, sin neón, sin mayúsculas en etiquetas. Colores y tiempos solo
  desde `tokens.css`. Movimiento: `--ease-out` para entrar/salir, <300 ms en UI,
  `transform`/`opacity`, `prefers-reduced-motion` más suave (no cero), hover
  solo con `(hover: hover) and (pointer: fine)`.
- **Caché del navegador**: `server.py` manda `Cache-Control: no-cache`; al
  cambiar CSS/JS también se sube el `?v=` en `web/index.html`.
- Los scripts de `web/` son clásicos y comparten el ámbito global: nombres de
  nivel superior únicos (revisar con el truco de `new Function` sobre los 4 juntos).
- Nunca inventar estados ni eventos; si falta un dato, decirlo.

## Archivos privados (NO están en el repo, ver .gitignore)

| Archivo | Qué es |
|---|---|
| `.env` | `N8N_WEBHOOK_URL`, `TWILIO_ALERT_PHONE` y claves (ver `.env.example`) |
| `google_calendar_url.txt` | URL(s) secreta(s) iCal de Google Calendar, una por línea |
| `google_calendar_webapp.json` | `{"url": ".../exec", "token": "..."}` del Apps Script |
| `contacts.json` | `[{"name": "Mamá", "relation": "madre"}]` (opcional) |
| `events.db` | historial (se crea solo) |
| `yolov8n.pt`, `pose_landmarker_lite.task` | modelos (se descargan solos al encender la cámara) |

El repo es **público**: nunca subir teléfonos, correos, URLs secretas ni tokens.

## Cosas que ya pasaron (para no repetirlas)

- Claude Code apaga procesos en segundo plano cuando falta RAM: el servidor
  conviene correrlo en una terminal propia. Matar procesos **por PID**, nunca
  todos los `python.exe`.
- El navegador bloquea abrir pestañas desde un comando de voz: hay que permitir
  ventanas emergentes para `localhost:8000` (o usar el botón).
- Web Speech (reconocimiento) solo en Chrome/Edge, con internet, en
  `localhost` o HTTPS, y con permiso de micrófono.
- La URL iCal de Google tarda minutos en reflejar eventos nuevos.
- En reposo de la PC el servidor se pausa (no se apaga); al despertar la webcam
  puede quedar congelada (apagar/encender la cámara) y el reconocimiento de
  voz puede detenerse (recargar la página). Para el uso real: sin reposo.

## Pendiente / siguientes pasos

Credenciales reales de Twilio (WhatsApp y llamadas), Telegram y ElevenLabs;
`contacts.json`; Zavu (sin documentación todavía); sensores ESP32 reales
(estufa, temperatura, humo) por `POST /events`; modelo de caídas entrenado y
varias cámaras; palabra de activación sin internet; modo kiosco en el
hardware; editar/borrar eventos y completar recordatorios por voz;
autenticación si el servidor se expone fuera de `localhost`.
