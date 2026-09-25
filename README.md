# Super Alexa — un solo producto: cara + voz + consola + motor de situaciones

Un agente doméstico unificado, no dos páginas sueltas: una sola pantalla con
dos vistas (la cara de Lumina y la consola de percepción) que se cruzan con
una transición fluida — por voz ("Lumina, busca mi mochila") o con el botón
de la consola. Entiende el contexto del hogar (eventos de cámara/ESP32 →
memoria → motor de situaciones → alerta por voz y por WhatsApp/llamada).

```
lumina-agent/
├── lumina.py          Voz/chat: APIRouter FastAPI, POST /lumina/ask (Ollama + limpieza)
├── server.py          Monta lumina + backend y sirve web/
├── test_lumina.py     Pruebas de voz/chat (sin Ollama real)
├── test_backend.py    Pruebas del motor de situaciones, memoria y API
├── test_vision.py     Pruebas de visión (heurísticas + YOLO simulado, sin webcam real)
├── test_calendar_provider.py  Pruebas de Google Calendar (iCal + RRULE)
├── test_integrations.py       Pruebas de selección de proveedor (n8n/Twilio/mock)
├── requirements.txt
├── backend/
│   ├── events.py            Contrato de eventos (sección 12)
│   ├── memory.py            Memoria de eventos en SQLite (Bloque 4)
│   ├── agent.py             Estado del hogar + motor de situaciones + caídas (Bloque 3)
│   ├── vision.py            CameraProvider: YOLOv8n + MediaPipe Pose + puerta (Bloque 5)
│   ├── integrations.py      n8n + Twilio (WhatsApp/llamadas), con mock de respaldo
│   ├── calendar_provider.py Google Calendar vía URL secreta de iCal (sección 3.5)
│   ├── reminders.py         Recordatorios (al salir / al llegar / cuando sea)
│   ├── briefing.py          Resumen de la casa en una frase + frases de salida/llegada
│   └── api.py               /events, /home/*, /reminders, /calendar, /alerts, /vision/*
└── web/
    ├── index.html       Una sola página, dos vistas (#view-lumina / #view-dashboard)
    ├── tokens.css          Sistema de diseño: color (OKLCH), tipo, espacio, movimiento
    ├── app-shell.css/.js   Cambio de vista (View Transitions), avisos, reloj, atajos d/l
    ├── lumina.css/.js      Cara, voz, subtítulos en vivo, comandos de voz
    └── dashboard.css/.js   La casa: cámara, plano vivo, bitácora, agenda, recordatorios
```

## Estado real de cada integración (qué es código y qué falta que hagas tú)

Ninguna de estas necesitó una nueva abstracción rara: todas entran por
`NotificationProvider`/`CalendarProvider` (sección 23) sin tocar `api.py`.

| Integración | Estado | Qué falta (y por qué solo tú puedes hacerlo) |
|---|---|---|
| **ElevenLabs** | ✅ Conectado de punta a punta (frontend + backend) | Nada de código — pega tu `ELEVENLABS_API_KEY` (ver tabla de abajo) |
| **n8n** | ✅ Instalado local (`npm i -g n8n`), workflow "Super Alexa - Alertas" creado y activo, probado de extremo a extremo | Nada para que reciba alertas. Si quieres que además mande WhatsApp/Telegram de verdad, agrégalo dentro de n8n (`http://localhost:5678`, con tu usuario local de n8n) — un nodo nuevo, sin tocar Python |
| **WhatsApp + llamadas (Twilio)** | Código completo (`TwilioWhatsAppProvider`, `TwilioCallProvider`), cae a mock si faltan credenciales | Crear una cuenta Twilio (verificación de identidad/pago — nadie más puede hacerlo por ti) y pegar `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `TWILIO_CALL_FROM` en `.env`, con `TWILIO_ALERT_PHONE` (el número que recibe las alertas) |
| **Google Calendar** | ✅ Conectado (URL secreta de iCal, sin OAuth) | Nada de código — pásame la URL (ver abajo) y la guardo yo |
| **Zavu** | ❌ No implementado | No tengo documentación, API ni credenciales de Zavu — el doc del evento dice "revisar documentación durante el evento". Compárteme su API/docs y lo conecto igual que los demás |

Notificaciones se mandan por **todos** los canales configurados a la vez
(n8n y/o Twilio); si uno falla, los demás siguen (regla 12 del doc: una
función caída no debe tumbar la demo).

### Conectar tu Google Calendar (30 segundos, sin Google Cloud Console)

1. Abre Google Calendar en el navegador
2. ⚙ Configuración -> en la columna izquierda, clic en tu calendario
3. "Integrar calendario" -> copia **"Dirección secreta en formato iCal"**
4. Pégamela en el chat y yo la guardo en `google_calendar_url.txt`

(o, si prefieres hacerlo tú: pega esa URL en un archivo llamado
`google_calendar_url.txt` en esta carpeta.)

**Cada calendario tiene su propia URL.** El que se llama igual que tu correo
es el principal; si tus eventos están en otro ("Mi Rutina", "Aprendamos
juntos"...), copia la URL de ESE calendario. Puedes guardar varias, una por
línea: Lumina junta los eventos de todas. Los calendarios que otra persona
compartió contigo no tienen dirección secreta de tu lado: pídesela a quien lo
creó. Google Calendar se abre en la cuenta dueña de esas URLs (`authuser`).

### Agregar eventos a Google Calendar ("Lumina, agenda dentista mañana a las 5")

Funciona sin configurar nada: Lumina entiende la fecha y abre Google Calendar
con el evento ya lleno; solo tocas **Guardar**. Para que quede creado solo, sin
tocar nada (una vez, ~3 minutos, sin Google Cloud ni `credentials.json`):

1. Con la sesión de la cuenta del calendario, abre https://script.google.com
   y crea un **Nuevo proyecto**.
2. Borra lo que trae y pega `apps_script_calendario.gs`. En `TOKEN` pon el
   `token` de `google_calendar_webapp.json` (gitignorado).
3. **Implementar → Nueva implementación → tipo "Aplicación web"**.
   Ejecutar como: **Yo**. Quién tiene acceso: **Cualquier usuario**.
4. Google pide permiso para "ver y editar tus calendarios": **Permitir**
   (si dice "Google no verificó esta app": Configuración avanzada → Ir al
   proyecto). Es tu propio script, en tu propia cuenta.
5. Copia la **URL de la aplicación web** (termina en `/exec`) y pégamela, o
   ponla en `"url"` dentro de `google_calendar_webapp.json`.

El token evita que alguien más cree eventos aunque conozca la URL. Por defecto
se agregan al calendario principal; para otro, cambia `calendario()` en el script.

## Correrla sola

```
pip install -r requirements.txt
ollama pull llama3.2:1b          # y deja `ollama serve` corriendo

n8n start                        # http://localhost:5678 (una vez instalado: npm i -g n8n)
                                 # e importa n8n/superalexa-alertas.json y actívalo

copy .env.example .env           # una vez; pon ahí tu n8n, número de alertas, claves
python server.py
                                  # http://localhost:8000  (usa Chrome o Edge)
```

Sin `N8N_WEBHOOK_URL` (o si n8n no está corriendo), las alertas caen solas al
mock (`print` + lista en memoria) — la demo principal sigue funcionando
igual, solo sin el canal real.

Pantalla de espera al inicio: di **"Lumina"** o toca la pantalla para
encenderla. Después habla normal: lo que no sea un comando va al LLM.

- **http://localhost:8000/** — Super Alexa (cara + consola, misma página)
- **http://localhost:8000/docs** — Swagger de la API

Cambiar de vista: el resumen de la casa bajo la cara abre la consola; el
orbe de Lumina arriba a la izquierda regresa (la cara "viaja" al orbe con View
Transitions). Por voz: "muéstrame la casa" / "vuelve". Atajos de teclado de
respaldo: `d` (consola), `l` (Lumina).

## Visión (backend/vision.py)

Una webcam local + YOLOv8n (COCO, 80 clases) para personas/objetos +
MediaPipe Pose (Tasks API) para postura de caída + diferencia de frames para
la puerta. Los pesos (`yolov8n.pt`, `pose_landmarker_lite.task`) se
descargan solos la primera vez que arranca la cámara — no hace falta bajarlos
a mano, solo tener internet esa primera vez.

Apagada por default (no siempre está grabando): se enciende desde el botón
"Encender" del dashboard, o `POST /vision/start` / `POST /vision/stop`.

- **Riesgo de cocina / ocupación**: la cámara reporta `motion`
  (`person_present`) con el mismo contrato de eventos de siempre — se combina
  con los sensores (temperatura/humo/flama) exactamente igual que si vinieran
  de un ESP32.
- **Puerta**: NO usa un sensor magnético (sección 3.4) — compara el frame
  actual contra una foto de referencia de "puerta cerrada". Hay que calibrar
  al inicio de la demo con la puerta cerrada: botón "Calibrar puerta" o
  `POST /vision/calibrate_door`. Sin calibrar, no inventa el estado.
- **Caídas** (automático con la cámara encendida): MediaPipe Pose mide el
  ángulo del torso y la altura de la cadera. Es caída solo si pasan las tres
  cosas: de pie a horizontal en menos de 1.5 s, la cadera baja de golpe, y se
  queda abajo 2.5 s (`FallDetector`; acostarse despacio, recostarse desde
  sentado o agacharse y levantarse no la disparan). Nunca afirma una
  emergencia médica: pregunta.
  1. Suena una alerta, la cara reacciona y sale **"¿Estás bien?"** encima de
     cualquier vista, con un reloj de 30 s. Lumina lo pregunta en voz alta y
     lo recuerda a la mitad.
  2. Se contesta con los botones o por voz, sin decir "Lumina": "estoy bien",
     "no me caí", "falsa alarma"… cierran; "necesito ayuda", "me caí", "no me
     puedo levantar", "no"… avisan al contacto. Si no entiende, vuelve a preguntar.
  3. **Si nadie contesta en 30 s, avisa solo** al contacto (mensaje + llamada).
     Lo hace un vigilante del servidor (`check_fall_escalation`), así que
     funciona aunque la página esté cerrada.
  4. Después de avisar, el aviso sigue hasta que alguien diga "estoy bien".
  - "Me caí", "auxilio", "pide ayuda" funcionan también **sin** que la cámara
    haya visto nada: abren la alerta ya como "pidió ayuda".
  - Ajustes por variable de entorno: `FALL_ANGLE_DEGREES`, `FALL_FAST_SECONDS`,
    `FALL_MIN_DROP`, `FALL_STAY_DOWN_SECONDS`. Otra fuente (un ESP32, un
    wearable) puede reportarla con `POST /events {"type": "possible_fall"}`.
- **Cualquier situación se anuncia por voz sola**: la consola narra cuando
  la severidad SUBE (normal -> alerta/crítico) — nunca la repite cada 3
  segundos mientras se queda igual — usando el mismo motor de voz de Lumina.
- **Buscar objetos perdidos por voz**: decir "Lumina, busca mi celular" (o
  el botón "Buscar" de la consola) enciende la cámara sola si hace falta,
  cambia de vista y llama a `POST /vision/find` + poll a
  `GET /vision/find/status`. Al encontrarlo lo resalta en el stream de la
  cámara (`GET /vision/stream`, MJPEG) y lo anuncia en voz alta con el mismo
  motor de Lumina (ElevenLabs si está configurado, si no la voz del
  navegador). **Límite real**: YOLO solo ve las 80 clases de COCO
  (`backend/vision.py:OBJECT_NAME_MAP`) — celular,
  mochila, control remoto, laptop, libro, etc. **No incluye "llaves" ni
  "cartera"**, COCO no tiene esa clase; para esos objetos la única fuente
  confiable sigue siendo la memoria manual/otra cámara (`/memory/object`),
  nunca inventar una detección.

## Meterla en otro proyecto

- **Backend FastAPI:** copia `lumina.py` y haz `app.include_router(router)`
  (`from lumina import router`).
- **Frontend:** copia `web/` donde sirvas estáticos. Si tu API no está en
  `/lumina/ask`, define antes de cargar `lumina.js`:
  `<script>window.LUMINA_ASK_URL = "https://mi-api/lumina/ask";</script>`
- **Otro backend (Node, etc.):** solo replica el contrato:
  `POST {question}` → `{answer}`. Todo lo demás es frontend.

## Personalizarla

| Qué | Dónde |
|---|---|
| Hechos reales de tu proyecto (para que no invente) | env `LUMINA_PROJECT_CONTEXT` |
| Modelo / URL / tope de tokens | env `OLLAMA_MODEL`, `OLLAMA_URL`, `OLLAMA_NUM_PREDICT` |
| Voz real con ElevenLabs (opcional, si no se configura cae sola a speechSynthesis) | env `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL_ID` |
| Respuestas instantáneas sin LLM | `PRELOADED_ANSWERS` en `lumina.py` |
| Personalidad base | `_BASE_PROMPT` en `lumina.py` |
| Colores, tipografía, movimiento | `web/tokens.css` (único lugar) |
| Nueva expresión | una fila en `EXPRESSIONS` de `lumina.js` |
| Voz | `localStorage.setItem('lumina_voice_override', 'jorge')` y recargar |
| n8n | env `N8N_WEBHOOK_URL` (ej. `http://localhost:5678/webhook/superalexa-alert`) |
| WhatsApp/llamadas reales | `.env`: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `TWILIO_CALL_FROM`, `TWILIO_ALERT_PHONE` (número que recibe las alertas) |
| Google Calendar | Pega la URL secreta en `google_calendar_url.txt` (ver abajo) |
| Cámara | env `CAMERA_INDEX`, `CAMERA_LOCATION` (default `kitchen`) |

## Comandos de voz

Después de despertarla, **no hace falta decir "Lumina"** antes de cada comando
(solo en los de la cara). Las órdenes ("busca…", "apaga la cámara") van al
inicio de la frase; se vale empezar con "oye", "Lumina", "por favor" o
"¿puedes…?". Lo que no sea comando va al LLM. Cada frase de esta tabla está
probada en `voice_commands_check.js` (lo corre `pytest`), escrita como la
transcriben Chrome y Edge.

| Qué | Ejemplos |
|---|---|
| Salir de casa (arma, revisa la estufa y la puerta, lee pendientes y agenda) | "salgo de casa", "ya me voy", "voy de salida" |
| Llegar (desarma, avisa si pasó algo, lee pendientes de llegada) | "ya llegué", "llegué a casa" |
| Solo proteger / desproteger | "activa la protección", "desactiva la protección" |
| Estado de la casa | "¿cómo está la casa?", "¿está todo bien?" |
| Buscar con la cámara (mientras busca, solo acepta comandos) | "busca mi mochila", "cancela" |
| Recordatorios | "recuérdame sacar la basura cuando salga", "recuérdame llamar a mamá cuando llegue", "¿qué pendientes tengo?" |
| Agenda (Google Calendar) | "¿qué tengo hoy?", "¿qué tengo en mi agenda hoy?", "¿qué hay en mi calendario?", "¿qué tengo mañana?" |
| Agregar un evento a Google Calendar | "agenda dentista mañana a las 5", "agéndame una cita con el doctor el lunes a las 10", "crea un evento: examen el viernes a las 8", "añade pagar la luz a mi calendario mañana" |
| Abrir Google Calendar (abre la vista de agenda en su pestaña, lleva la consola a "Hoy" y te dice lo de hoy) | "abre mi calendario", "abre Google Calendar", "muéstrame mi agenda", "quiero ver mi agenda" |
| Dónde quedó algo (memoria) | "¿dónde dejé mi mochila?" |
| Anti-extorsión | "analiza este mensaje: deposita ya o le pasa algo a tu hijo" |
| Emergencia (funciona siempre, aunque la cámara no haya visto nada) | "me caí", "auxilio", "socorro", "pide ayuda", "necesito ayuda", "no me puedo levantar" |
| Responder "¿Estás bien?" tras una caída (sin decir "Lumina") | "estoy bien", "no me caí", "falsa alarma" / "necesito ayuda", "me duele", "no" |
| Avisar a tu contacto (alerta activa) | "avisa a mi contacto" |
| Cámara | "enciende la cámara", "apaga la cámara", "calibra la puerta" |
| Hora y fecha | "¿qué hora es?", "¿qué día es hoy?" |
| Vistas | "muéstrame la casa", "vuelve" |
| Cara (prueba, estas sí con "Lumina") | "Lumina, feliz", "Lumina, triste", "Lumina, presentación" |

Chrome y Edge no dejan que una página abra otra pestaña sin un clic: la
primera vez que digas "abre mi calendario" sale un aviso con el enlace. Para
que la voz la abra directo, en la barra de direcciones toca el ícono de
"ventana emergente bloqueada" y elige *Permitir siempre* para `localhost:8000`.

Consola del navegador: `setFaceExpression('feliz')`, `askLumina('hola')`.

## Límites reales (no los prometas de más)

- Las expresiones son estados visuales predefinidos, no emociones de un modelo.
- La boca es una animación procedural, no análisis de audio (la Web Speech API
  no lo permite).
- No se puede clonar la voz de Jarvis: se elige la mejor voz en español que
  tenga instalada el navegador/sistema.
- Sin memoria: cada pregunta es independiente.
- El reconocimiento de voz es la Web Speech API del navegador (Chrome/Edge).

## Qué se quitó respecto a Aether

Modo Cámara (`/perception/stream`, YOLO), panel de detecciones, guion de la
presentación de Aether, y el system prompt / respuestas precargadas con datos
de Aether. Lo demás (cara, voz, limpieza del LLM) es idéntico en lógica.

## Diseño de Aether (referencia para el resto de tu proyecto)

`design/` trae el sistema de diseño completo de Aether, copiado tal cual:
`aether-design-system.md` (las reglas: tokens, tipografía, componentes) y
`aether-style.css` (su implementación). Lumina NO depende de ellos — `web/`
funciona sola — pero si el resto de tu app debe verse como Aether, úsalos.
Nota: Super Alexa ya no usa esa paleta; su sistema propio ("la casa de
noche": índigo y luz de luna en calma, ámbar/brasa solo para riesgo) vive en
`web/tokens.css`.
