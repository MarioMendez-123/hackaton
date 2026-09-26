# Super Alexa · Lumina: tecnologías y librerías

Inventario de todo lo que usa el proyecto, con las versiones instaladas y
probadas (septiembre 2026). Sale del código real: lo que importa cada archivo,
`requirements.txt` y las APIs que llama.

**En una línea:** backend en **Python 3.11 + FastAPI**, visión con **OpenCV +
YOLOv8n + MediaPipe**, memoria en **SQLite**, lenguaje con **Ollama** (local),
frontend en **HTML/CSS/JavaScript sin frameworks** con las **APIs de voz del
navegador**, alertas con **n8n** y calendario con **Google Calendar + Apps Script**.

---

## 1. Lenguajes

| Lenguaje | Dónde |
|---|---|
| **Python 3.11** | Todo el servidor (`server.py`, `lumina.py`, `backend/`) y las pruebas |
| **JavaScript** (ES2022, sin compilar) | Frontend (`web/*.js`) y la prueba de comandos de voz (`voice_commands_check.js`, con Node) |
| **HTML5 + CSS** (moderno, sin preprocesador) | La interfaz (`web/index.html`, `web/*.css`) |
| **Google Apps Script** (JavaScript de Google) | `apps_script_calendario.gs`, para crear eventos en Google Calendar |
| **SQL** (SQLite) | Historial de eventos y recordatorios |
| **SVG** | Cara de Lumina, plano de la casa, orbe e iconos |

---

## 2. Backend (Python): librerías que usa el código directamente

Están todas en `requirements.txt`.

| Librería | Versión | Para qué | Dónde |
|---|---|---|---|
| **FastAPI** | 0.141.1 | API web (31 endpoints), archivos estáticos y validación | `server.py`, `backend/api.py`, `lumina.py` |
| **Uvicorn** `[standard]` | 0.53.0 | Servidor que corre FastAPI (`python server.py` → puerto 8000) | `server.py` |
| **Pydantic** | 2.13.4 | Modelos de datos de las peticiones (eventos, recordatorios, calendario…) | `backend/api.py`, `backend/events.py`, `lumina.py` |
| **OpenCV** (`opencv-python`) | 4.10.0.84 | Leer la webcam, procesar imágenes, dibujar recuadros y codificar JPEG para el video en vivo | `backend/vision.py` |
| **Ultralytics** (YOLOv8) | 8.4.162 | Detectar personas y objetos en la cámara | `backend/vision.py` |
| **MediaPipe** | 0.10.35 | Postura del cuerpo (Tasks API, `PoseLandmarker`) para detectar caídas | `backend/vision.py` |
| **NumPy** | 2.4.6 | Cálculos con imágenes (puerta por diferencia de imagen) | `backend/vision.py` |
| **icalendar** | 7.3.0 | Leer el calendario de Google (formato iCal) | `backend/calendar_provider.py` |
| **recurring-ical-events** | 3.8.2 | Expandir eventos que se repiten (clases diarias, etc.) | `backend/calendar_provider.py` |
| **Twilio** | 9.11.1 | WhatsApp y llamadas reales (se activa con credenciales) | `backend/integrations.py` |
| **pytest** | 9.1.1 | Pruebas automáticas (147) | `test_*.py` |
| **httpx** | 0.28.1 | Cliente que usa el `TestClient` de FastAPI en las pruebas | pruebas |

### 2.1 Dependencias que se instalan solas (vienen con las anteriores)

| Librería | Versión | Viene con | Qué hace ahí |
|---|---|---|---|
| Starlette | 1.6.0 | FastAPI | Base web de FastAPI |
| AnyIO | 4.14.0 | FastAPI | Concurrencia asíncrona |
| httptools / websockets / watchfiles | 0.8.0 / 17.1 / 1.3.0 | uvicorn[standard] | Servidor más rápido, websockets, recarga |
| python-dotenv | 1.2.3 | uvicorn[standard] | (El proyecto **no** la usa: tiene su propio lector de `.env` en `server.py`) |
| **PyTorch** (`torch`) | 2.12.1 | Ultralytics | Motor de la red neuronal de YOLO (es lo más pesado de instalar) |
| torchvision | 0.27.1 | Ultralytics | Operaciones de visión para PyTorch |
| ultralytics-thop | 2.1.6 | Ultralytics | Medición del modelo |
| Pillow / Matplotlib / SciPy / PyYAML / Polars / psutil / requests | 12.2.0 / 3.11.0 / 1.17.1 / 6.0.3 / 1.44.2 / 7.2.2 / 2.34.2 | Ultralytics | Imágenes, gráficas internas, configuración, sistema, descargas |
| opencv-contrib-python | 5.0.0.93 | MediaPipe | OpenCV con módulos extra (convive con `opencv-python`) |
| protobuf / flatbuffers / sounddevice | 7.35.1 / 25.12.19 / 0.5.5 | MediaPipe | Formatos del modelo y audio de MediaPipe |
| python-dateutil / tzdata / x-wr-timezone | 2.9.0.post0 / 2026.2 / 2.0.1 | icalendar | Fechas y zonas horarias del calendario |
| aiohttp | 3.14.1 | Twilio | Peticiones HTTP de Twilio |

### 2.2 Biblioteca estándar de Python usada (no se instala)

| Módulo | Para qué |
|---|---|
| `sqlite3` | Base de datos local (`events.db`: historial y recordatorios) |
| `urllib.request` / `urllib.parse` / `urllib.error` | Llamar a Ollama, ElevenLabs, Telegram, n8n, Apps Script y Google Calendar; armar URLs |
| `threading` | Hilo de la cámara y el **vigilante de caídas** (revisa cada segundo) |
| `json`, `re`, `datetime`, `math`, `uuid` | Datos, patrones de texto (fechas en español, anti-extorsión), tiempo, cálculos, identificador de cada evento de calendario |
| `logging`, `os`, `sys`, `time`, `pathlib`, `contextlib`, `typing` | Registro, variables de entorno, rutas y arranque del servidor |
| `subprocess`, `shutil`, `unittest.mock` | Solo en pruebas (correr la prueba de voz con Node, simular Google y la red) |

---

## 3. Modelos de inteligencia artificial

| Modelo | Qué es | Tamaño | De dónde sale | Para qué |
|---|---|---|---|---|
| **YOLOv8n** (`yolov8n.pt`) | Red neuronal de detección, entrenada con COCO (80 clases) | ~6.5 MB | Ultralytics (se descarga solo) | Personas y objetos: celular, mochila, taza, laptop… |
| **MediaPipe Pose Landmarker lite** (`pose_landmarker_lite.task`, float16) | Modelo de postura: 33 puntos del cuerpo | ~5.8 MB | Google (`storage.googleapis.com/mediapipe-models`, se descarga solo) | Ángulo del torso y altura de la cadera → caídas |
| **Llama 3.2 1B** (`llama3.2:1b`) vía **Ollama** | Modelo de lenguaje, local y sin internet | ~1.3 GB | `ollama pull llama3.2:1b` | Responder preguntas libres. En la PC también están `llama3.2:3b`, `llama3` y `llava:7b` (opcionales) |
| **Reconocimiento de voz del navegador** | Servicio de voz a texto de Google (Chrome) o Microsoft (Edge) | — | Integrado en el navegador (usa internet) | Entender lo que dices (español de México) |
| **Voces del sistema** (`speechSynthesis`) | Texto a voz del navegador y Windows | — | Integrado | La voz de Lumina (se prefiere una voz de es-MX) |
| **ElevenLabs** `eleven_multilingual_v2` | Texto a voz natural en la nube | — | api.elevenlabs.io | Voz más natural (opcional, necesita clave) |

**Reglas propias (no son modelos):** el detector de caídas (`FallDetector`), la
puerta por diferencia de imagen, el motor de situaciones, el reconocedor de
comandos de voz, el lector de fechas en español y el detector anti-extorsión
son **código propio basado en reglas**, no IA entrenada. Así lo pide el
documento maestro: "la IA interpreta, las reglas deciden".

---

## 4. Frontend (navegador)

**Sin frameworks ni compilación:** no usa React, Vue, Tailwind, Bootstrap,
jQuery ni bundlers. Son 5 archivos JavaScript y 4 CSS que el servidor entrega
tal cual.

### 4.1 APIs del navegador

| API | Para qué |
|---|---|
| **Web Speech API: `SpeechRecognition`** (`webkitSpeechRecognition`) | Escuchar continuo en es-MX, con resultados parciales para los subtítulos |
| **Web Speech API: `speechSynthesis`** + `SpeechSynthesisUtterance` | Hablar; `onboundary` sincroniza la boca y los subtítulos palabra por palabra |
| **Web Audio API** (`AudioContext`, osciladores) | Tonos de Lumina (encendido, "te oí", alarma de caída), sin archivos de audio |
| **View Transitions API** (`document.startViewTransition`) | La cara que viaja hasta el orbe al cambiar de vista |
| **Web Animations API** (`element.animate`) | Fundido del titular y de las lecturas cuando cambian |
| **Canvas 2D** + `requestAnimationFrame` | Fondo de estrellas; motor de la cara (boca, parpadeo y mirada en cada cuadro) |
| **Fetch** | Hablar con el servidor (consulta cada 3 s, o cada 1 s durante una caída) |
| **`<img>` con MJPEG** (`multipart/x-mixed-replace`) | Video en vivo de la cámara sin librerías de video |
| **Permissions API** | Saber si el micrófono está permitido o bloqueado |
| **`window.open`** | Abrir Google Calendar (en su pestaña "google-calendar") |
| **Blob URL + `Audio`** | Reproducir la voz de ElevenLabs |
| **`localStorage`** | Forzar una voz específica (opcional) |
| **`matchMedia`** | Detectar movimiento reducido y tipo de puntero |
| **`Intl.DateTimeFormat`** | Reloj y fechas en español de México |
| **Atributo `inert`** | Desactivar la vista que no se ve (accesibilidad) |
| **Expresiones regulares con índices** (bandera `d`) + `String.normalize` | Recortar del texto original lo que dijiste (recordatorios y mensajes con acentos) |
| **SVG** (`<use>`, `pathLength`, `stroke-dashoffset`) | Iconos, cara, plano que "se dibuja", anillo de la cuenta regresiva |

### 4.2 CSS moderno

| Característica | Para qué |
|---|---|
| **Variables CSS** (design tokens en `tokens.css`) | Una sola fuente de colores, tamaños y tiempos |
| **OKLCH** + `color-mix()` | Paleta con claridad uniforme; halos y bordes derivados del color de alerta |
| **`@starting-style`** | Animar entradas sin JavaScript (toasts, bitácora, video, aviso de caída) |
| **View Transitions** (`view-transition-name`, `::view-transition-*`) | Elemento compartido entre vistas |
| **Container queries** (`container-type`, unidad `cqh`) | Barrido de la cámara del tamaño exacto del video |
| **CSS Grid** (`grid-template-rows` 0fr → 1fr) | Diseño de la consola y avisos que se despliegan |
| **`backdrop-filter`** | Materiales translúcidos (barra, toasts, rótulos, aviso de caída) |
| **`text-wrap: balance / pretty`** | Titulares y párrafos sin palabras sueltas |
| **Consultas de preferencias** (`prefers-reduced-motion`, `prefers-reduced-transparency`, `prefers-contrast`, `hover`, `pointer`) | Accesibilidad y táctil |
| **`env(safe-area-inset-*)`**, `dvh` | Pantallas con muesca y alto real del navegador |

### 4.3 Tipografías

| Fuente | Pesos | De dónde | Uso |
|---|---|---|---|
| **Newsreader** | 300–600 (eje óptico 6–72) | Google Fonts | La voz de Lumina: subtítulos, titular, reloj, "¿Estás bien?" |
| **Schibsted Grotesk** | 400, 500, 600 | Google Fonts | Toda la interfaz |

Los iconos son **propios** (sprite SVG en `index.html`): no se usan fuentes
de iconos ni emoji.

---

## 5. Servicios externos y APIs

| Servicio | Cómo se usa | ¿Obligatorio? |
|---|---|---|
| **Google Calendar: URL secreta iCal** | Leer la agenda (hoy y mañana, eventos que se repiten), sin OAuth | Para la agenda |
| **Google Apps Script** (aplicación web) | Crear eventos por voz. Usa `CalendarApp`, `CacheService` (no duplicar), `LockService` y `ContentService` | Para agendar solo, sin tocar nada |
| **Google Calendar (web)** | Abrir la agenda (`/calendar/r/agenda?authuser=…`) o un evento prellenado (`render?action=TEMPLATE`) | No, es un enlace |
| **Google Fonts** | Tipografías | Sí, con internet (si falla, usa fuentes de respaldo) |
| **Google Cloud Storage** / **Ultralytics** | Descargar los modelos la primera vez | Solo la primera vez |
| **n8n** (local, `localhost:5678`) | Recibir cada alerta en un webhook (`superalexa-alert`) y automatizar lo que se quiera | Recomendado |
| **Ollama** (local, `localhost:11434`) | Modelo de lenguaje sin internet | Para preguntas libres |
| **Twilio** | WhatsApp y llamadas reales al contacto | Opcional (sin él, simulado) |
| **Telegram Bot API** | Mensajes de alerta | Opcional |
| **ElevenLabs** | Voz natural | Opcional (sin él, voz del navegador) |
| **GitHub** | Repositorio del código (público) | Para compartir y respaldar |

---

## 6. Herramientas de desarrollo y ejecución

| Herramienta | Versión | Para qué |
|---|---|---|
| Python + pip + venv | 3.11.9 | Correr e instalar el backend |
| Node.js + npm | 24.20.0 | Prueba de comandos de voz e instalar n8n |
| n8n | 2.40.6 | Automatización de alertas |
| Ollama | 0.34.4 | Servidor del modelo de lenguaje |
| Git + GitHub | 2.54 | Control de versiones (`github.com/MarioMendez-123/hackaton`) |
| Chrome / Edge | actuales | Ejecutar Lumina (voz), DevTools; Edge sin ventana para capturas de pantalla en pruebas visuales |
| Claude Code (+ skills de diseño y animación) | — | Desarrollo, auditorías de diseño, animación y accesibilidad |
| Swagger UI (incluido en FastAPI) | — | Probar la API en `http://localhost:8000/docs` |

---

## 7. Hardware

| Qué | Para qué |
|---|---|
| Webcam | Personas, objetos, puerta y caídas |
| Micrófono y bocinas | Hablar con Lumina |
| Pantalla | La cara de Lumina y la consola |
| **16 GB de RAM o más** (recomendado) | YOLO + MediaPipe + Ollama + n8n + navegador a la vez |
| Sensores ESP32 (futuro) | Estufa, temperatura, humo y puerta magnética. El contrato ya existe: `POST /events` |

---

## 8. Lo que NO usa (a propósito)

- **Frameworks de frontend ni compilación** (React, Vue, Next, Tailwind, Vite):
  no hacen falta para una sola pantalla y hacen la instalación más pesada.
- **Servidor de base de datos** (Postgres, MySQL): basta SQLite, un archivo local.
- **Nube propia ni cuentas de Google Cloud / OAuth**: el calendario usa la URL
  secreta y un Apps Script, sin proyecto de Google Cloud.
- **Librería para `.env`**: `server.py` tiene su propio lector de 10 líneas.
- **Fuentes de iconos ni emoji**: iconos SVG propios.
- **Archivos de audio**: los tonos se generan con Web Audio.
