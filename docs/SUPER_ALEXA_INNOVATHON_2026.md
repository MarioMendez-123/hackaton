# SUPER ALEXA — INNOVATHON 2026
## Documento maestro de desarrollo / Cloud Code

> **Concepto:** una casa que no solamente obedece órdenes: entiende lo que está pasando, detecta situaciones relevantes y puede actuar o pedir autorización.
>
> **Frase del producto:** **“No le digas a tu casa qué hacer. Deja que entienda lo que está pasando.”**

---

# 1. Objetivo del proyecto

Construir un prototipo funcional de un **agente doméstico multimodal** que integre:

- cámaras
- sensores IoT
- voz
- IA
- memoria contextual
- automatización
- comunicación con el usuario
- control de dispositivos

El sistema debe transformar señales aisladas en **situaciones contextualizadas**.

### Ejemplo

No queremos solamente:

`MQ-2 detecta humo`

Queremos:

`Cámara → detecta estufa encendida`
`+ sensor → temperatura anormal`
`+ PIR → no hay nadie en cocina`
`→ agente evalúa contexto`
`→ determina que existe una situación de riesgo`
`→ n8n ejecuta protocolo`
`→ WhatsApp/Telegram alerta`
`→ voz informa`
`→ actuador realiza una acción segura`

---

# 2. Funcionalidades del producto

## 2.1 Encontrar objetos perdidos

El usuario pregunta:

> “¿Dónde están mis llaves?”

El sistema analiza eventos/imágenes de las cámaras y responde con la última ubicación conocida.

Ejemplo:

> “Las vi por última vez sobre la mesa de la sala a las 12:43.”

### Requisitos

- cámaras
- visión por computadora / modelo multimodal
- registro de eventos
- base de datos de eventos
- agente conversacional

### Importante

La respuesta debe distinguir entre:

- ubicación confirmada
- última ubicación observada
- ubicación no encontrada

Nunca inventar una ubicación.

---

# 3.2 Comprensión general del hogar

La IA debe poder interpretar situaciones, no solamente objetos.

Ejemplos:

- puerta abierta mientras la casa está vacía
- persona detectada
- persona que abandona una zona dejando un riesgo
- dispositivo encendido en una habitación vacía
- actividad inusual
- caída de una persona
- posible humo/incendio
- situación que requiere confirmación del usuario

### Principio

**Evento + contexto = situación**

---

# 3.3 Protección contra incendios / cocina

La cámara vigila la zona de cocina.

Sensores disponibles:

- temperatura/humedad
- humo/gases
- flama
- movimiento

La IA combina las señales.

Ejemplo:

```text
Cámara:
estufa encendida

PIR:
nadie en la cocina

Temperatura:
subiendo

MQ-2:
anomalía

        ↓

AGENTE

        ↓

RIESGO POTENCIAL
```

El sistema puede:

- emitir alerta por voz
- mostrar alerta en pantalla
- enviar WhatsApp
- enviar Telegram
- registrar el evento
- ejecutar un actuador seguro de demostración

### Seguridad

No conectar el prototipo directamente a una estufa real ni presentar sensores hobby como sistemas certificados de seguridad.

Para la demo utilizar una maqueta/representación controlada.

---

# 3.4 Seguridad contextual de puertas

NO se utilizarán sensores magnéticos.

La puerta será analizada completamente mediante visión por computadora.

La cámara determinará:

- puerta abierta
- puerta cerrada
- persona entrando
- persona saliendo
- casa aparentemente vacía

Ejemplo:

```text
Puerta abierta
+
casa vacía
+
tiempo transcurrido
        ↓
situación relevante
        ↓
alerta al usuario
```

---

# 3.5 Integración con Google Calendar

El usuario puede preguntar:

> “¿Qué tengo hoy?”

> “¿Qué tengo mañana?”

> “Recuérdame esto antes de salir.”

El agente consulta el calendario y utiliza el contexto del hogar.

Ejemplo:

```text
Evento:
Clase 7:00 AM

+
Usuario sale de casa

→
recordatorio contextual
```

---

# 3.6 Contactos

El agente puede utilizar contactos autorizados para acciones como:

- enviar una alerta
- avisar de una situación
- solicitar ayuda
- compartir información de un evento

Las acciones sensibles requieren confirmación del usuario cuando corresponda.

---

# 3.7 WhatsApp

WhatsApp será uno de los canales principales de comunicación.

Ejemplo:

```text
SUPER ALEXA

🚨 Situación potencialmente peligrosa

Detecté:
- estufa encendida
- cocina vacía
- temperatura elevada

¿Quieres activar el protocolo?
```

La integración se realizará mediante las herramientas/API disponibles durante el evento y/o n8n.

**No se necesita hardware específico para WhatsApp.**

---

# 3.8 Telegram

Misma lógica que WhatsApp.

Telegram puede utilizarse como canal alternativo para:

- alertas
- comandos
- consultas
- confirmaciones
- eventos

---

# 3.9 Protección ante posibles extorsiones/fraudes

El sistema debe plantearse como **asistente de prevención**, no como detector infalible de extorsiones.

Puede analizar, con autorización del usuario:

- mensajes
- contenido recibido
- señales lingüísticas de riesgo
- solicitudes urgentes de dinero
- amenazas
- presión para actuar inmediatamente

Ejemplo:

> “Este mensaje contiene señales compatibles con un posible intento de fraude o extorsión. No he enviado ninguna respuesta. ¿Quieres analizarlo?”

El sistema debe evitar afirmar como hecho que un mensaje es una extorsión si no puede determinarlo.

---

# 3.10 Control de dispositivos

La IA podrá controlar dispositivos conectados.

Ejemplos:

- luces
- ventilación
- lámparas
- dispositivos representados mediante actuadores
- smart plugs

Ejemplo:

> “Apaga la luz de la sala.”

Flujo:

```text
Voz
 ↓
IA
 ↓
intención
 ↓
n8n
 ↓
IoT
 ↓
ESP32 / smart plug
 ↓
dispositivo
```

---

# 3.11 Memoria contextual del hogar

El sistema mantiene eventos recientes.

Ejemplos:

> “¿Cuándo viste mis llaves?”

> “Las vi por última vez a las 12:43 sobre la mesa.”

> “¿Quién estuvo en la sala?”

> “Detecté una persona entre 18:20 y 18:35.”

Las respuestas deben basarse únicamente en eventos registrados.

---

# 3.12 Detección de caídas / situaciones de emergencia

La cámara puede detectar una posible caída.

Flujo:

```text
Persona cae
 ↓
Sistema detecta postura/situación
 ↓
Espera confirmación
 ↓
“¿Estás bien?”
 ↓
Respuesta
```

Si no hay respuesta, el sistema puede ofrecer contactar a un contacto previamente autorizado.

Esta funcionalidad puede quedar como demo secundaria si el tiempo es limitado.

---

# 4. Arquitectura general

```text
                    ┌──────────────────────┐
                    │       CÁMARAS        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ VISIÓN / PERCEPCIÓN  │
                    └──────────┬───────────┘
                               │
                               ▼
┌───────────────┐      ┌──────────────────────┐
│    SENSORES   │─────►│   EVENTOS / CONTEXTO │
│    ESP32      │      └──────────┬───────────┘
└───────────────┘                 │
                                  ▼
                       ┌──────────────────────┐
                       │     AGENTE IA        │
                       │ percepción/contexto  │
                       │ razonamiento/acción  │
                       └──────────┬───────────┘
                                  │
                     ┌────────────┼─────────────┐
                     │            │             │
                     ▼            ▼             ▼
                  AWS IoT       n8n          Base de datos
                     │            │
                     │       ┌────┼─────┐
                     │       │    │     │
                     ▼       ▼    ▼     ▼
                  ESP32   WhatsApp Telegram Calendar
                     │
                     ▼
                Dispositivos

                     ▲
                     │
             ┌───────┴────────┐
             │                │
          MICRÓFONO        PANTALLA
             │                │
             ▼                ▼
          VOZ / IA       HOME DASHBOARD
```

---

# 5. Tecnologías

## IA

- Modelo multimodal/visión disponible durante el hackathon
- modelo conversacional/agente
- análisis de contexto
- clasificación de situaciones
- extracción de intención
- memoria de eventos

## Automatización

### n8n

Responsabilidades:

- recibir eventos
- ejecutar workflows
- conectar APIs
- enviar WhatsApp
- enviar Telegram
- consultar servicios
- disparar acciones
- orquestar respuestas

---

## AWS

AWS será la infraestructura cloud.

Posibles componentes:

- AWS IoT Core
- Lambda
- API Gateway
- almacenamiento de eventos
- servicios de IA disponibles
- autenticación/credenciales según arquitectura final

### AWS IoT Core

Utilizar MQTT para comunicación con ESP32 cuando sea viable.

Ejemplo de tópico:

```text
home/sensors/kitchen/temperature
home/sensors/kitchen/smoke
home/sensors/kitchen/flame
home/sensors/livingroom/motion
home/security/door
home/events
home/actions
```

---

# 6. Zavu

Zavu se utilizará como parte del stack proporcionado por el evento según las capacidades/API disponibles.

Antes del hackathon:

- revisar autenticación
- revisar documentación
- identificar qué funcionalidad puede aportar
- preparar integración mínima

No construir una dependencia crítica sobre una función que no haya sido probada.

---

# 7. ElevenLabs

ElevenLabs se utilizará para la personalidad/voz de Super Alexa cuando esté disponible.

Ejemplo:

```text
Evento
 ↓
Agente genera respuesta
 ↓
ElevenLabs genera audio
 ↓
Bocina
```

Durante el viernes, como no hay acceso a ElevenLabs, utilizar:

- texto
- TTS local del navegador
- audio temporal
- voz del sistema

El objetivo es poder reemplazar posteriormente la capa de voz sin cambiar la lógica del agente.

---

# 8. Hardware

## Control

- 3 × ESP32
- protoboards
- cables Dupont
- resistencias
- cables USB
- fuentes/cargadores 5V

## Sensores

- 3 × PIR HC-SR501
- 2 × BME280/BME680
- 1 × MQ-2
- 1 × KY-026

## Voz

- 1 × INMP441
- 1 × MAX98357A
- 1 × bocina pequeña 4–8 Ω

## Actuadores

- 1 × módulo de relé
- 1–2 × smart plugs Wi-Fi
- LEDs
- tira LED RGB opcional
- botones

## Ya disponibles

- cámaras
- pantalla
- impresora 3D

## Material

- cinta doble cara
- tornillos/separadores
- conectores
- filamento
- cableado adicional

---

# 9. Distribución recomendada de ESP32

## ESP32 #1 — Sensores

Conectar:

- PIR
- BME280/BME680
- MQ-2
- sensor de flama

Responsabilidad:

```text
sensores → MQTT → backend
```

## ESP32 #2 — Actuadores

Conectar:

- relé
- LEDs
- botones

Responsabilidad:

```text
comando → MQTT → acción física
```

## ESP32 #3 — Reserva / audio

Inicialmente:

- dejar como respaldo

Si el tiempo alcanza:

- micrófono
- audio
- interacción física

**No desperdiciar horas intentando hacer todo el audio embebido si el navegador/computadora resuelve la demo.**

---

# 10. Hardware que NO necesitamos

No comprar:

- sensores magnéticos de puerta
- hardware específico para WhatsApp
- hardware específico para Telegram
- hardware específico para Google Calendar
- sensores para cada habitación
- Raspberry Pi adicional si las cámaras/computadora pueden procesarse localmente
- sensores industriales caros para una demo de hackathon

La puerta será visión + IA.

---

# 11. Arquitectura de software

Crear el repositorio:

```text
super-alexa/
│
├── README.md
├── ARCHITECTURE.md
├── PRODUCT.md
├── DEMO.md
├── .env.example
├── .gitignore
│
├── backend/
│   ├── api/
│   ├── agent/
│   ├── vision/
│   ├── memory/
│   └── integrations/
│
├── frontend/
│   ├── dashboard/
│   └── display/
│
├── hardware/
│   ├── esp32-sensors/
│   └── esp32-actuators/
│
├── workflows/
│   └── n8n/
│
├── docs/
│   ├── hardware.md
│   ├── integrations.md
│   └── decisions.md
│
└── tests/
```

---

# 12. Contrato de eventos

TODOS los módulos deben intercambiar datos con una estructura consistente.

Ejemplo:

```json
{
  "event_id": "evt_001",
  "timestamp": "2026-09-25T14:30:00",
  "source": "camera_kitchen",
  "type": "stove_on",
  "location": "kitchen",
  "confidence": 0.94,
  "metadata": {
    "person_present": false
  }
}
```

Otro:

```json
{
  "event_id": "evt_002",
  "timestamp": "2026-09-25T14:31:00",
  "source": "bme280_kitchen",
  "type": "temperature",
  "location": "kitchen",
  "value": 38.4,
  "unit": "celsius"
}
```

La IA debe poder recibir eventos de diferentes fuentes sin importar si vienen de cámara o sensores.

---

# 13. Estados del hogar

Mantener un estado conceptual:

```json
{
  "home": {
    "occupancy": "unknown",
    "door": "unknown",
    "security": "normal",
    "risk_level": "normal"
  },
  "kitchen": {
    "stove": "unknown",
    "temperature": null,
    "smoke": null,
    "flame": null,
    "occupancy": "unknown"
  }
}
```

Estados posibles:

```text
unknown
normal
warning
critical
```

No inventar estados cuando no exista evidencia suficiente.

---

# 14. Motor de situaciones

No construir cada funcionalidad como un sistema separado.

Construir una capa común:

```text
PERCEPCIÓN
    ↓
EVENTOS
    ↓
CONTEXTO
    ↓
SITUACIÓN
    ↓
DECISIÓN
    ↓
ACCIÓN
```

Ejemplo:

```text
EVENTOS

stove_on
temperature_high
no_person_detected
smoke_normal

        ↓

CONTEXTO

Casa aparentemente vacía.
Estufa encendida.
Temperatura elevada.

        ↓

SITUACIÓN

POTENTIAL_KITCHEN_RISK

        ↓

ACCIÓN

alert_user
```

---

# 15. Principio fundamental del agente

El agente NO debe ejecutar acciones peligrosas simplemente porque un modelo de IA lo sugirió.

Separar:

### IA

Interpreta:

> “Creo que existe riesgo.”

### Motor de reglas

Determina:

> “¿Se cumplen las condiciones necesarias?”

### n8n

Ejecuta:

> “Enviar alerta / pedir confirmación / controlar dispositivo.”

Esto reduce errores y hace la arquitectura más defendible.

---

# 16. Demo principal

La demo debe tener una historia.

## Escenario

La casa está aparentemente vacía.

Una persona sale de la cocina.

La cámara detecta:

```text
persona salió
estufa continúa encendida
```

Los sensores reportan:

```text
temperatura aumentando
```

El sistema determina:

```text
situación potencialmente peligrosa
```

Super Alexa responde:

> “Detecté que la cocina está vacía y la estufa permanece encendida. ¿Quieres que active el protocolo de seguridad?”

Después:

```text
n8n
 ↓
WhatsApp
 ↓
alerta
```

Y en la maqueta:

```text
LED rojo
pantalla de alerta
actuador de demostración
```

---

# 17. Demo secundaria — objetos perdidos

Usuario:

> “Super Alexa, ¿dónde están mis llaves?”

Sistema:

```text
consulta memoria de eventos
 ↓
busca última observación
 ↓
responde
```

Respuesta:

> “Las vi por última vez sobre la mesa de la sala a las 12:43.”

Si no existe evidencia:

> “No tengo una observación reciente de tus llaves.”

Nunca inventar.

---

# 18. Demo secundaria — seguridad

Simular:

```text
puerta abierta
+
casa vacía
```

La cámara determina el estado de la puerta.

Sistema:

> “La puerta principal lleva abierta varios minutos y no detecto actividad dentro de la casa.”

Después:

- alerta en pantalla
- WhatsApp/Telegram
- acción opcional

---

# 19. Demo secundaria — caída

Simular una caída controlada.

Sistema:

```text
visión
 ↓
posible caída
 ↓
“¿Estás bien?”
 ↓
sin respuesta
 ↓
solicitar confirmación para contactar contacto autorizado
```

No afirmar que existe una emergencia médica únicamente por una detección visual.

---

# 20. Dashboard

La pantalla debe mostrar el estado de la casa.

Ejemplo:

```text
╔══════════════════════════════════╗
║          SUPER ALEXA             ║
║                                  ║
║ 🏠 ESTADO: NORMAL                ║
║                                  ║
║ 👤 Personas: 0                   ║
║ 🚪 Puerta: CERRADA               ║
║ 🔥 Cocina: NORMAL                ║
║ 🌡️ 24.3°C                        ║
║                                  ║
║ ÚLTIMO EVENTO                    ║
║ Llaves detectadas en sala        ║
║ 12:43 PM                         ║
╚══════════════════════════════════╝
```

En riesgo:

```text
╔══════════════════════════════════╗
║ 🚨 SITUACIÓN DE RIESGO           ║
║                                  ║
║ Cocina                           ║
║ Estufa encendida                 ║
║ Cocina aparentemente vacía       ║
║                                  ║
║ Protocolo: ESPERANDO CONFIRMACIÓN║
╚══════════════════════════════════╝
```

---

# 21. Plan de desarrollo — VIERNES SIN AWS/N8N/ELEVENLABS

Objetivo:

**dejar listo el 60–70% del producto antes de tener acceso a las tecnologías del evento.**

## Bloque 1 — Repositorio

Crear:

- estructura
- README
- variables de entorno
- contratos de eventos
- documentación
- Git

Resultado:

```text
Todos saben dónde está cada cosa.
```

---

## Bloque 2 — Dashboard

Construir:

- pantalla principal
- estado del hogar
- eventos
- alertas
- historial

Usar datos simulados.

Ejemplo:

```json
{
  "type": "stove_on",
  "temperature": 38,
  "occupancy": false
}
```

---

## Bloque 3 — Motor de situaciones

Crear funciones como:

```python
evaluate_home_state()
evaluate_kitchen_risk()
evaluate_security_state()
find_last_object_location()
```

No depender todavía de AWS.

Entrada:

```json
{
  "stove_on": true,
  "person_present": false,
  "temperature": 38.5
}
```

Salida:

```json
{
  "situation": "potential_kitchen_risk",
  "severity": "warning",
  "requires_confirmation": true
}
```

---

## Bloque 4 — Memoria de eventos

Crear almacenamiento local.

Puede ser:

- SQLite
- JSON durante el prototipo inicial

Guardar:

- timestamp
- fuente
- evento
- ubicación
- confianza
- metadata

Esto permite desarrollar "¿dónde están mis cosas?" antes del hackathon.

---

## Bloque 5 — Visión

Implementar una capa desacoplada:

```text
CameraProvider
```

Debe permitir posteriormente cambiar:

```text
video local
        ↓
modelo local

POR

video
 ↓
AWS/modelo/API
```

sin reescribir todo el proyecto.

---

## Bloque 6 — ESP32

Programar los ESP32 para enviar eventos locales.

Primero:

```text
ESP32
 ↓
Wi-Fi
 ↓
JSON
 ↓
servidor local
```

Después, durante el evento:

```text
ESP32
 ↓
MQTT
 ↓
AWS IoT Core
```

---

## Bloque 7 — Voz provisional

Viernes:

- Web Speech API
- TTS del sistema
- entrada por micrófono del navegador

Durante el evento:

```text
ElevenLabs
```

se conecta como reemplazo de la salida de voz.

---

# 22. Lo que NO desarrollar el viernes

No gastar tiempo en:

- AWS
- n8n
- ElevenLabs
- WhatsApp real
- Telegram real
- integración final con Calendar
- infraestructura cloud completa

Si no tienen acceso, construir **interfaces/mocks**.

Ejemplo:

```python
send_whatsapp(message)
```

Viernes:

```python
print("[MOCK WHATSAPP]", message)
```

Evento:

```python
send_whatsapp(message)
```

con integración real.

La aplicación no debería saber ni importarle qué proveedor existe detrás.

---

# 23. Mock de integraciones

Crear interfaces:

```python
class NotificationProvider:
    def send(self, message):
        pass
```

Implementaciones:

```text
MockNotificationProvider
WhatsAppProvider
TelegramProvider
```

Igual para:

```text
CalendarProvider
VoiceProvider
IoTProvider
VisionProvider
```

Esto permite que el equipo trabaje sin bloquearse por credenciales.

---

# 24. Trabajo en equipo

Dividir por módulos.

## Persona A — Agente / Backend

Responsable:

- lógica
- eventos
- situaciones
- memoria
- APIs

## Persona B — Frontend / Dashboard

Responsable:

- pantalla
- UI
- estados
- historial
- alertas

## Persona C — Hardware / IoT

Responsable:

- ESP32
- sensores
- actuadores
- MQTT
- maqueta

## Persona D — Integraciones

Si existe una cuarta persona:

- n8n
- AWS
- WhatsApp
- Telegram
- Calendar
- ElevenLabs

Si son menos personas, combinar responsabilidades.

---

# 25. Reglas de desarrollo

1. **No mezclar hardware con lógica de negocio.**
2. **No meter API keys en Git.**
3. Usar `.env`.
4. Cada módulo debe tener una interfaz clara.
5. Cada funcionalidad debe poder ejecutarse con mocks.
6. No construir una funcionalidad que no pueda demostrarse.
7. Priorizar integración sobre cantidad de features.
8. Todo evento importante debe tener timestamp.
9. Toda detección de visión debe incluir confianza cuando sea posible.
10. La IA no debe ejecutar directamente acciones sensibles.
11. Las acciones críticas deben pasar por reglas/confirmación.
12. Si una función falla, la demo principal debe continuar.

---

# 26. Prioridad de funcionalidades

## P0 — DEBE FUNCIONAR

- [ ] cámara
- [ ] detección de situación de cocina
- [ ] sensores ESP32
- [ ] motor de contexto
- [ ] dashboard
- [ ] alerta
- [ ] control de al menos un dispositivo
- [ ] memoria de eventos

## P1 — MUY IMPORTANTE

- [ ] encontrar objetos
- [ ] puerta mediante visión
- [ ] WhatsApp
- [ ] Telegram
- [ ] voz
- [ ] AWS IoT
- [ ] n8n

## P2 — SI SOBRA TIEMPO

- [ ] Google Calendar
- [ ] caída
- [ ] contactos
- [ ] protección contra posibles fraudes/extorsión
- [ ] memoria más avanzada
- [ ] personalidad avanzada de voz

---

# 27. Qué NO intentar

No intentar crear:

- una Alexa comercial completa
- un sistema de seguridad certificado
- un modelo de IA desde cero
- una infraestructura cloud gigantesca
- una aplicación móvil completa
- una integración perfecta con todas las plataformas
- diez demos independientes

El objetivo es:

**un MVP coherente, funcional y demostrable.**

---

# 28. Criterio de éxito

Al terminar el hackathon debemos poder mostrar:

### 1.
La casa recibe información de sensores/cámaras.

### 2.
El sistema entiende el contexto.

### 3.
El agente identifica una situación.

### 4.
El sistema decide qué acción corresponde.

### 5.
n8n/AWS ejecuta la automatización.

### 6.
El usuario recibe respuesta por voz/pantalla/WhatsApp/Telegram.

### 7.
Un dispositivo físico cambia de estado.

### 8.
El sistema puede consultar memoria reciente.

---

# 29. Pitch conceptual

> “Una casa inteligente tradicional espera órdenes.
>
> Super Alexa hace algo diferente.
>
> Conectamos cámaras, sensores y dispositivos para crear un agente que entiende el contexto del hogar.
>
> No solamente detecta que una estufa está encendida. Puede entender que la estufa está encendida, que la cocina está vacía y que la temperatura está aumentando.
>
> No solamente graba una cámara. Puede responder dónde vio por última vez tus llaves.
>
> No solamente recibe una alerta. Puede convertir esa situación en una acción.
>
> Super Alexa convierte una casa conectada en una casa que entiende.”

---

# 30. Definición técnica en una frase

**Super Alexa es un agente doméstico multimodal que fusiona visión, sensores IoT, contexto, memoria, voz y automatización para detectar situaciones y ejecutar acciones de manera controlada.**

---

# 31. Checklist antes del evento

## Software

- [ ] GitHub funcionando
- [ ] proyecto corre localmente
- [ ] dashboard funciona
- [ ] eventos simulados funcionan
- [ ] memoria funciona
- [ ] motor de situaciones funciona
- [ ] visión desacoplada
- [ ] mocks funcionando
- [ ] `.env.example`
- [ ] documentación

## Hardware

- [ ] ESP32 probado
- [ ] PIR probado
- [ ] BME probado
- [ ] MQ-2 probado
- [ ] sensor de flama probado
- [ ] relé probado
- [ ] smart plug probado
- [ ] cámaras probadas
- [ ] pantalla probada
- [ ] cables extra
- [ ] ESP32 de respaldo

## Demo

- [ ] escenario principal definido
- [ ] objetos para demostrar búsqueda
- [ ] maqueta lista
- [ ] alertas listas
- [ ] WhatsApp preparado
- [ ] n8n probado
- [ ] AWS probado
- [ ] ElevenLabs probado
- [ ] fallback local funcionando

---

# 32. Regla final del proyecto

**Si una funcionalidad no mejora la historia de “la casa entiende lo que está pasando”, probablemente no merece tiempo durante las 12 horas.**

El producto no se trata de tener muchas funciones.

Se trata de demostrar:

```text
              VE
               ↓
           PERCIBE
               ↓
           ENTIENDE
               ↓
            RECUERDA
               ↓
            RAZONA
               ↓
             ACTÚA
               ↓
           TE AVISA
```

## SUPER ALEXA

### Una casa que entiende.
