# Lumina: estructura de producto

Cómo ordenar todas las tecnologías de Super Alexa (las que ya funcionan y las
que faltan) en **funciones que se puedan vender y anunciar**.

> **Actualización (giro del producto):** en el hackathon hay otro proyecto de
> monitoreo de pacientes. El titular ya no es "cuidado de adultos mayores" sino
> **"Lumina entiende la casa, actúa por ti y te acompaña fuera"** (casa que
> actúa + WhatsApp/Ray-Ban Meta + anti-extorsión). Ver `PLAN_MAESTRO.md` §1.
> Los pilares y planes de abajo siguen valiendo; cambia el orden del anuncio.

**Estados que se usan en todo el documento:**

| Estado | Significa |
|---|---|
| **Disponible** | Funciona hoy y se puede demostrar |
| **Listo para activar** | El código ya está; falta una cuenta o credencial (Twilio, Telegram, ElevenLabs) |
| **Por construir** | Hay que programarlo (Zavu, Clerk, app para la familia…) |
| **Visión** | Idea para después del lanzamiento |

---

## 1. La promesa

> **Una casa conectada espera órdenes. Lumina entiende lo que pasa y cuida a
> quien vive ahí.**

### 1.1 Para quién

| Segmento | Su problema | Quién paga |
|---|---|---|
| **1. Adultos mayores que viven solos** (principal) | Caídas, estufa olvidada, soledad, extorsión telefónica | Los hijos o nietos adultos |
| **2. Personas que viven solas o pasan el día fuera** | ¿Dejé la estufa? ¿Cerré la puerta? ¿Qué tengo hoy? | La misma persona |
| **3. Familias preocupadas por la extorsión** | Llamadas y mensajes de "tenemos a tu hijo" | La familia |
| **4. Cuidadores y residencias** (B2B, después) | Vigilar a varias personas sin estar en cada cuarto | La empresa |

### 1.2 Por qué Lumina y no otra bocina o cámara

1. **Entiende el contexto, no solo un sensor:** "la estufa está encendida **y**
   no hay nadie **y** la temperatura sube".
2. **Pregunta antes de alarmar:** "¿Estás bien?" antes de llamar a nadie. Menos
   falsas alarmas y más confianza.
3. **Tu video no sale de tu casa:** la cámara se procesa en el equipo local.
   Solo salen avisos de texto. **Esto hay que mantenerlo cuando llegue la nube.**
4. **Habla como persona, en español de México,** con cara, voz y subtítulos.
   No hace falta saber usar una app.
5. **No inventa:** si no sabe algo, lo dice.

---

## 2. Estructura de uso: quién, por dónde y para qué

### 2.1 Roles

| Rol | Quién es | Qué necesita |
|---|---|---|
| **Persona en casa** | El usuario principal, a veces mayor y sin experiencia con tecnología | Hablar y que la entiendan; avisos claros; nada de menús |
| **Familiar** | Hijos o nietos, a distancia | Saber que todo está bien, recibir avisos y mandar mensajes |
| **Cuidador o administrador** | Quien instala y configura (familiar o profesional) | Contactos, horarios, cámaras, historial |
| **Soporte** (después) | El equipo de Lumina | Ver el estado del equipo, sin ver el video |

### 2.2 Canales

| Canal | Persona en casa | Familiar | Cuidador | Estado |
|---|---|---|---|---|
| **Pantalla de Lumina** (cara + voz) | Canal principal: habla y escucha | — | — | Disponible |
| **Consola en casa** (misma pantalla) | Ver la casa, agenda, recordatorios | — | Configurar y revisar | Disponible |
| **WhatsApp** | Recibir recordatorios; mandar recados por voz | Avisos, confirmar, mandar mensajes a la casa | Avisos | Por construir (Zavu). Alternativa: Twilio, listo para activar |
| **Llamada del agente de voz** | — | Recibe la llamada en una emergencia | Idem | Por construir (Zavu + ElevenLabs). Hoy: llamada con mensaje fijo por Twilio, listo para activar |
| **App o web para la familia** (con login) | — | Estado de la casa, historial, contactos | Varias casas y roles | Por construir (Clerk + nube) |
| **Telegram** | — | Avisos (alternativa a WhatsApp) | Avisos | Listo para activar |
| **Google Calendar** | Su agenda por voz | Agendarle cosas desde su celular | — | Disponible |

---

## 3. Mapa de tecnologías por capa

Así se "segmenta" el producto técnicamente. Cada función que se vende (sección
4) combina piezas de varias capas.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. CUENTAS Y ACCESO   Clerk · app familiar · roles · varias casas         │
├─────────────────────────────────────────────────────────────────────────┤
│ 5. COMUNICACIÓN       n8n · WhatsApp (Zavu/Twilio) · Agente de llamadas     │
│                       (Zavu + ElevenLabs) · Telegram · Google Calendar     │
├─────────────────────────────────────────────────────────────────────────┤
│ 4. VOZ Y PRESENCIA    Cara de Lumina · voz del navegador → ElevenLabs ·    │
│                       subtítulos · palabra "Lumina"                        │
├─────────────────────────────────────────────────────────────────────────┤
│ 3. CEREBRO            Motor de situaciones · memoria · Ollama (Llama 3.2) · │
│                       comandos de voz · fechas en español · anti-extorsión │
├─────────────────────────────────────────────────────────────────────────┤
│ 2. SENTIDOS           Cámara (OpenCV, YOLOv8, MediaPipe) · micrófono ·     │
│                       sensores ESP32 (estufa, humo, temperatura, puerta)   │
├─────────────────────────────────────────────────────────────────────────┤
│ 1. PLATAFORMA         Equipo en casa (FastAPI local) · pantalla en modo     │
│                       kiosco · nube de Lumina (enlace casa ↔ familia)      │
└─────────────────────────────────────────────────────────────────────────┘
```

| Capa | Tecnología | Estado | Qué aporta |
|---|---|---|---|
| **1. Plataforma** | FastAPI + SQLite en el equipo de la casa | Disponible | Todo funciona local, incluso sin internet (salvo la voz del navegador) |
| | Pantalla en modo kiosco (arranca sola y se recupera sola) | Por construir | Producto físico "enchufar y listo" |
| | **Nube de Lumina** (enlace entre la casa y la familia) | Por construir | **Requisito** para Clerk, la app familiar y los WhatsApp entrantes |
| **2. Sentidos** | Webcam + OpenCV + YOLOv8n | Disponible | Personas, 12 objetos, ocupación |
| | MediaPipe Pose (caídas) | Disponible | Caída rápida con caída de altura |
| | Puerta por imagen | Disponible | Abierta o cerrada sin sensor |
| | Micrófono + reconocimiento del navegador | Disponible | Comandos y preguntas |
| | Sensores ESP32 (estufa, humo, temperatura, puerta magnética) | Por construir (el contrato `POST /events` ya existe) | Más precisión en la cocina |
| | Palabra "Lumina" y reconocimiento sin internet (Whisper, openWakeWord) | Visión | Privacidad y funcionar sin red |
| **3. Cerebro** | Motor de situaciones (reglas) | Disponible | Decide la severidad, sin inventar |
| | Memoria (historial, dónde se vio algo) | Disponible | "¿Dónde dejé…?" |
| | Ollama, Llama 3.2 local | Disponible | Conversación sin nube |
| | Reconocedor de comandos + fechas en español | Disponible | Entiende a la gente como habla |
| | Detector anti-extorsión | Disponible | Señales de riesgo en mensajes |
| **4. Voz y presencia** | Cara viva, subtítulos, voz del navegador | Disponible | Presencia y accesibilidad |
| | **ElevenLabs** (voz natural de Lumina) | Listo para activar (falta la clave) | La voz que se vende en el anuncio |
| **5. Comunicación** | n8n (orquestador de avisos) | Disponible | Conecta cualquier servicio sin programar |
| | Google Calendar (leer, abrir y agendar) | Disponible | Agenda por voz |
| | **WhatsApp vía Zavu** | Por construir (falta revisar su documentación). Twilio: listo para activar | Canal principal con la familia |
| | **Agente de llamadas vía Zavu + ElevenLabs** | Por construir | Llama y **conversa** en una emergencia |
| | Llamada con mensaje fijo (Twilio) | Listo para activar | Respaldo del agente |
| | Telegram | Listo para activar | Canal alternativo |
| | Actuadores (cortar la estufa, válvula) | Visión | Siempre con confirmación humana |
| **6. Cuentas** | **Clerk** (inicio de sesión, familia, roles, organizaciones) | Por construir (necesita la nube) | La familia entra desde su celular |

---

## 4. Las funciones que se venden: 6 pilares + 1 diferenciador

Cada pilar agrupa varias tecnologías en **un solo beneficio que se entiende
sin explicar la tecnología**. El nombre es **"Lumina + una palabra"**.

### Pilar 1. Lumina Casa Segura

> **"Si la estufa se queda prendida y no hay nadie, Lumina te avisa."**

| Qué hace | Tecnología | Estado |
|---|---|---|
| Estufa encendida sin nadie en la cocina (alerta o crítica según la temperatura) | Cámara + reglas (+ ESP32) | Disponible (ESP32 por construir) |
| Puerta abierta con la casa vacía | Cámara (puerta por imagen) + reglas | Disponible |
| **Salgo de casa / ya llegué:** protege, revisa, te recuerda | Voz + reglas + recordatorios + agenda | Disponible |
| Modo protección: aviso si se abre la puerta | Reglas + n8n | Disponible |
| Plano de la casa en vivo | Consola | Disponible |
| Aviso a la familia por WhatsApp | Zavu (o Twilio) | Por construir |

**Se mide con:** riesgos avisados, minutos hasta que alguien atiende.

### Pilar 2. Lumina Cuida (caídas y emergencias)

> **"Si alguien se cae, Lumina pregunta. Si no contesta, avisa a la familia."**

| Qué hace | Tecnología | Estado |
|---|---|---|
| Detecta posibles caídas | MediaPipe Pose + detector propio | Disponible |
| "¿Estás bien?" con cuenta regresiva, voz y respuestas habladas | Voz + interfaz | Disponible |
| Aviso automático si nadie contesta (aunque la pantalla esté apagada) | Vigilante del servidor + n8n | Disponible |
| "Me caí", "auxilio": pedir ayuda por voz | Voz | Disponible |
| **WhatsApp a la familia con lo que pasó** | Zavu (o Twilio) | Por construir |
| **Agente de llamadas:** llama a la familia, explica qué pasó con voz natural y pregunta si alguien va en camino | Zavu + ElevenLabs | Por construir |
| Si el primer contacto no contesta, llama al siguiente | Agente de llamadas + contactos | Por construir |

**Se mide con:** tiempo desde la caída hasta que un familiar confirma.

### Pilar 3. Lumina Escudo (anti-extorsión)

> **"Antes de depositar, pregúntale a Lumina."**

| Qué hace | Tecnología | Estado |
|---|---|---|
| Analiza un mensaje y dice qué señales de engaño tiene (urgencia, dinero, amenazas, familiar falso) | Detector propio | Disponible |
| Consejo claro: "no deposites, llama tú al número que conoces" | Voz | Disponible |
| **Verificación con la familia:** "Lumina, ¿mi hijo está bien?" y Lumina le escribe por WhatsApp para confirmar | Zavu, WhatsApp de ida y vuelta | Por construir |
| Reenviar a Lumina un WhatsApp sospechoso para que lo revise | Zavu (mensajes entrantes) | Por construir |
| Avisar a un familiar cuando alguien de la casa recibe un mensaje de alto riesgo | Zavu + contactos | Por construir |

**Se mide con:** mensajes revisados y verificaciones hechas antes de pagar.

### Pilar 4. Lumina Contigo (familia conectada)

> **"Tu familia sabe que estás bien, sin que tengas que llamar."**

| Qué hace | Tecnología | Estado |
|---|---|---|
| **"Lumina, dile a mi hija que ya llegué"**: manda el WhatsApp por voz | Zavu + comandos de voz | Por construir |
| Aviso automático a la familia al salir o llegar (si se activa) | Zavu + salir/llegar | Por construir |
| La familia manda un mensaje y **Lumina lo lee en voz alta** en casa | Zavu (entrante) + nube + voz | Por construir |
| **App o web para la familia con login:** estado de la casa, historial, contactos, recordatorios a distancia | Clerk + nube | Por construir |
| Roles: dueño, familiar, cuidador; varias casas por cuenta | Clerk (organizaciones) | Por construir |

**Se mide con:** familiares activos por casa y mensajes por semana.

### Pilar 5. Lumina Agenda (rutina del día)

> **"Tu día, en voz alta."**

| Qué hace | Tecnología | Estado |
|---|---|---|
| "¿Qué tengo hoy/mañana?" | Google Calendar (iCal) | Disponible |
| **"Agenda dentista mañana a las 5":** lo crea solo | Apps Script + lector de fechas | Disponible |
| "Abre mi calendario" | Google Calendar web | Disponible |
| Recordatorios al salir, al llegar o cuando sea | Recordatorios propios | Disponible |
| Hora y fecha habladas | Voz | Disponible |
| **Medicamentos:** "¿ya tomaste tu pastilla?" a su hora y, si no contesta, aviso a la familia | Recordatorios con hora + Zavu | Por construir |
| Resumen de la mañana: clima, agenda, pendientes | Agenda + voz | Visión |

**Se mide con:** recordatorios cumplidos y tomas confirmadas.

### Pilar 6. Lumina Memoria (objetos)

> **"¿Dónde dejé mi celular? Lumina lo busca."**

| Qué hace | Tecnología | Estado |
|---|---|---|
| Busca 12 objetos con la cámara, los marca y lo dice | YOLOv8n | Disponible |
| "¿Dónde dejé…?": responde con lo último que vio, sin inventar | Memoria | Disponible |
| Llaves, cartera, lentes (no vienen en el modelo actual) | Modelo entrenado propio | Visión |

### Diferenciador (no se vende suelto; va en todos los planes): Lumina Presencia

> **"No es una app. Es alguien en casa."**

| Qué es | Tecnología | Estado |
|---|---|---|
| Cara que respira, parpadea y reacciona | Interfaz propia | Disponible |
| Subtítulos de todo lo que dice y oye (baja audición) | Interfaz | Disponible |
| Español de México, sin menús | Voz + comandos | Disponible |
| **Voz natural y cálida** | ElevenLabs | Listo para activar |

---

## 5. Planes (paquetes)

La regla: **lo que corre en la casa va en todos los planes; lo que genera
costo por uso (mensajes, llamadas, voz natural, nube) sube de plan.**

| Función | **Lumina Hogar** | **Lumina Cuida** | **Lumina Familia+** | **Lumina Pro** (B2B) |
|---|---|---|---|---|
| Pantalla con Lumina (voz, cara, subtítulos) | ✓ | ✓ | ✓ | ✓ |
| Casa Segura (estufa, puerta, salir/llegar) | ✓ | ✓ | ✓ | ✓ |
| Agenda, recordatorios, hora | ✓ | ✓ | ✓ | ✓ |
| Memoria y búsqueda de objetos | ✓ | ✓ | ✓ | ✓ |
| Escudo: analizar mensajes | ✓ | ✓ | ✓ | ✓ |
| Caídas con "¿Estás bien?" | ✓ | ✓ | ✓ | ✓ |
| Avisos por n8n o Telegram | ✓ | ✓ | ✓ | ✓ |
| **Avisos por WhatsApp a la familia** | — | ✓ | ✓ | ✓ |
| **Agente de llamadas en emergencias** | — | ✓ | ✓ | ✓ |
| **Voz natural (ElevenLabs)** | — | ✓ | ✓ | ✓ |
| **App familiar con login (Clerk)** | — | 2 familiares | Ilimitados | Por organización |
| Recordatorio de medicamentos con aviso | — | ✓ | ✓ | ✓ |
| Mensajes de ida y vuelta con la familia | — | — | ✓ | ✓ |
| Verificación anti-extorsión con la familia | — | — | ✓ | ✓ |
| Varias cámaras y sensores ESP32 | — | — | ✓ | ✓ |
| Varias casas en un panel, roles, bitácora exportable | — | — | — | ✓ |

**Modelo de cobro sugerido:** equipo (pantalla + cámara) con pago único, más
suscripción mensual desde Lumina Cuida. **El precio está por definir.** Antes
de ponerlo hay que calcular estos costos por casa al mes:
- mensajes de WhatsApp (Zavu o Twilio);
- minutos del agente de llamadas;
- caracteres de voz de ElevenLabs;
- cuentas de Clerk;
- servidor en la nube.

Lumina Hogar no tiene costo por uso: puede ser gratis con el equipo, y sirve
como la puerta de entrada.

---

## 6. Cómo anunciarlo

### 6.1 Frase principal (elige una)

1. **"Lumina: la casa que entiende y cuida."**
2. **"Una casa conectada espera órdenes. Lumina entiende."**
3. **"Alguien en casa, aunque no estés."**

### 6.2 Los 3 beneficios del anuncio (en este orden)

1. **Previene:** avisa de la estufa olvidada y la puerta abierta. *(Casa Segura)*
2. **Cuida:** pregunta "¿estás bien?" y, si no contestas, avisa a tu familia.
   *(Cuida)*
3. **Protege:** te ayuda a detectar extorsiones antes de pagar. *(Escudo)*

La agenda, la memoria y la presencia van como "y además…".

### 6.3 Pitch de 30 segundos

> "En México, millones de adultos mayores viven solos, y sus familias viven
> con el pendiente. Lumina es una pantalla que vive en la casa: ve, escucha y
> entiende lo que pasa. Si la estufa se queda prendida y no hay nadie, avisa.
> Si alguien se cae, pregunta '¿estás bien?' y, si no contesta, llama a la
> familia. Si llega un mensaje de extorsión, te dice qué señales tiene antes de
> que deposites. Y todo se hace hablándole, sin apps ni menús. El video nunca
> sale de tu casa."

### 6.4 Una frase por función (para redes, landing o presentación)

| Función | Frase |
|---|---|
| Casa Segura | "¿Dejé la estufa? Pregúntale a Lumina." |
| Salgo de casa | "Di 'ya me voy' y Lumina revisa la casa por ti." |
| Cuida | "Si alguien se cae, Lumina pregunta. Si nadie contesta, avisa." |
| Agente de llamadas | "En una emergencia, Lumina llama a tu familia y les explica qué pasó." |
| Escudo | "Antes de depositar, pregúntale a Lumina." |
| Contigo | "'Lumina, dile a mi hija que ya llegué.' Listo." |
| Agenda | "Tu día en voz alta: 'agenda dentista mañana a las 5'." |
| Memoria | "¿Dónde dejé mi celular? Lumina lo busca." |
| Privacidad | "Tu video nunca sale de tu casa." |

### 6.5 Lo que NO se debe prometer (confianza y temas legales)

- ✗ "Detecta todas las caídas" → ✓ "Te ayuda a detectar caídas y pregunta si estás bien".
- ✗ "Evita las extorsiones" → ✓ "Te ayuda a reconocer señales de extorsión".
- ✗ "Reemplaza al 911 o a un cuidador" → ✓ "Avisa a tu familia; en una
  emergencia grave, llama al 911".
- ✗ "Dispositivo médico" → Lumina **no** diagnostica.
- ✗ Anunciar como disponible algo que está "por construir": en la presentación
  va como **"Próximamente"**.

---

## 7. Demo para la presentación (unos 4 minutos)

Solo con lo **disponible**. Lo demás se muestra como "Próximamente" en una
lámina final.

1. **Presencia (20 s):** "Lumina" → despierta, sonríe, "¿Cómo está la casa?".
2. **Casa Segura (60 s):** "Ya me voy" → "Antes de irte: la estufa sigue
   encendida…". Se ve el plano con la cocina "caliente".
3. **Cuida (70 s):** caída simulada → "¿Estás bien?" en toda la pantalla, con
   cuenta regresiva → se deja correr → "No me respondiste, ya avisé a tu
   contacto" (mostrar el aviso llegando a n8n o WhatsApp).
4. **Escudo (40 s):** "Analiza este mensaje: deposita ya o le pasa algo a tu
   hijo" → "Riesgo alto: urgencia, dinero, amenaza".
5. **Agenda y Memoria (40 s):** "Agenda dentista mañana a las 5" → aparece en
   Google Calendar. "Busca mi mochila" → la marca en la cámara.
6. **Cierre (10 s):** lámina "Próximamente": agente de llamadas con voz natural,
   WhatsApp con la familia, app familiar.

---

## 8. Hoja de ruta (en qué orden construir)

```
FASE 0 · HOY (hackathon)          Todo lo "Disponible"
        │
FASE 1 · ACTIVAR (días)           ElevenLabs (clave) · Twilio o Telegram (cuenta)
        │                          · contacts.json · revisar la API de Zavu
        │
FASE 2 · CONECTAR A LA FAMILIA    Nube de Lumina ──┬── Clerk + app familiar
        (semanas)                                  ├── WhatsApp de ida y vuelta (Zavu)
        │                                          ├── Agente de llamadas (Zavu + ElevenLabs)
        │                                          └── Verificación anti-extorsión
        │
FASE 3 · PRODUCTO FÍSICO          Modo kiosco · sensores ESP32 · varias cámaras
        (meses)                    · medicamentos con aviso · palabra "Lumina" sin internet
        │
FASE 4 · EMPRESAS (B2B)           Panel de varias casas (organizaciones de Clerk)
                                   · roles · bitácora exportable · soporte
```

**Qué depende de qué** (no se puede saltar):
- **Clerk, la app familiar y los WhatsApp entrantes necesitan la nube de
  Lumina.** Hoy el servidor solo escucha dentro de la casa (`127.0.0.1`), y así
  debe seguir para el video. La nube solo mueve avisos, mensajes y estado,
  nunca video.
- **El agente de llamadas necesita** a Zavu (o Twilio), ElevenLabs y
  `contacts.json` con teléfonos.
- **La verificación anti-extorsión necesita** WhatsApp de salida **y** de entrada.
- **El recordatorio de medicamentos necesita** recordatorios con hora (hoy son
  al salir o al llegar) y WhatsApp para avisar a la familia.

**Lo que ya está listo en el código para crecer:**
- Los canales de aviso son intercambiables (`NotificationProvider` y
  `CallProvider`): Zavu entra como un proveedor más, sin tocar el resto.
- Los sensores entran por `POST /events`, con el mismo contrato que la cámara.

---

## 9. Riesgos a revisar antes de lanzar

| Tema | Qué revisar |
|---|---|
| **Zavu** | Qué ofrece de verdad (WhatsApp, llamadas, agente de voz), precios, límites y cómo se autentica. Hasta confirmarlo, Twilio queda como plan B, que ya está programado |
| **Reglas de WhatsApp para empresas** | Los mensajes que inicia la empresa suelen necesitar plantillas aprobadas y el consentimiento de quien los recibe. Confirmarlo con el proveedor |
| **Privacidad** (Ley Federal de Protección de Datos Personales) | Aviso de privacidad y consentimiento para cámara, voz y contactos; que el video siga sin salir de casa |
| **Salud** | Presentarlo como asistente, no como dispositivo médico |
| **Costos por uso** | Mensajes, minutos, voz y nube por casa al mes, antes de fijar precios |
| **Dependencia de internet** | Hoy el reconocimiento de voz usa la nube del navegador; en la fase 3, reconocimiento local |
