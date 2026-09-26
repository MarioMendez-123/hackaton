# Super Alexa · Lumina: especificación de marca, diseño y software

Documento de referencia de cómo se ve, cómo se mueve, cómo habla y cómo está
construida la interfaz. Todos los valores salen del código real
(`web/tokens.css`, `web/*.css`, `web/*.js`). Si cambias algo aquí, cámbialo
también allá, y viceversa.

---

## 1. Marca

### 1.1 Nombres

| Nombre | Qué es | Cómo se usa |
|---|---|---|
| **Super Alexa** | El producto o proyecto (el sistema completo) | Título de la página, documentos, presentación |
| **Lumina** | La persona: la voz y la cara que vive en la pantalla | "Lumina, …" para hablarle; ella habla en primera persona |

> Nota: "Alexa" es marca registrada de Amazon. Para la competencia sirve como
> nombre de proyecto; si algún día se usa en público o de forma comercial,
> conviene quedarse solo con **Lumina**, que ya funciona como marca propia.

### 1.2 Concepto: "la casa de noche"

La pantalla vive en una cocina o un pasillo, como una **luz de noche**.
- **La calma es fría:** índigo nocturno con acento de **luz de luna**.
- **El peligro es calor:** **ámbar**, y luego **brasa**. El riesgo principal
  del producto es, literalmente, una estufa.
- El color fuerte **solo aparece cuando algo necesita atención**. Si todo
  está bien, la interfaz casi no se nota.

### 1.3 Personalidad

- **Tranquila, cercana y honesta.** Acompaña; no alarma de más.
- **Nunca inventa:** lo que no sabe, lo dice ("Sin verificar", "No tengo un
  registro reciente de eso").
- **Nunca afirma una emergencia ni una estafa como hecho:** pregunta ("¿Estás
  bien?") o describe señales ("encontré 3 señales de riesgo").
- **Presente:** respira, parpadea, mira y reacciona. Se siente viva sin pedir
  atención.

### 1.4 Marca visual (el orbe)

No hay logotipo aparte: **el rostro de Lumina es la marca**.
- **Versión mínima: el orbe** de la barra de la consola.
  - SVG de `viewBox 0 0 64 64`.
  - Halo: círculo de radio 30, relleno `--dusk-raised`, borde `--line-strong`.
  - Ojos: rectángulos de 12×7 con radio 3.5 en (15, 24) y (37, 24).
  - Boca: `M22 41 Q32 47 42 41`, trazo de 3.5, puntas redondas.
- **El orbe también cambia con el estado:**
  - Su color sigue la severidad: luz de luna, ámbar o brasa.
  - Escuchando, respira. Hablando, mueve la boca. Pensando, entrecierra los ojos.
- **Tamaño mínimo:** 32 px. En la barra se usa a 44 px.

---

## 2. Color

Todos los colores están en **OKLCH**, porque ahí la claridad percibida es
uniforme. El valor hexadecimal es solo referencia. **Única fuente:
`web/tokens.css`.** Ningún otro archivo define colores sueltos (salvo fondos
translúcidos derivados de estos).

### 2.1 Paleta

| Token | OKLCH | Hex | Uso |
|---|---|---|---|
| `--night` | `20.5% 0.04 268` | `#0f1629` | Fondo general |
| `--night-deep` | `17% 0.036 268` | `#090e1f` | "Pozos": cámara, cara, campos de texto |
| `--dusk` | `24.5% 0.042 268` | `#181f35` | Superficies (plano, avisos, resultados) |
| `--dusk-raised` | `29% 0.044 268` | `#222a41` | Elevado: chips, interruptor, toasts |
| `--ink` | `95% 0.012 268` | `#ebeef7` | Texto principal |
| `--ink-2` | `79% 0.03 268` | `#b2bacf` | Texto secundario |
| `--ink-3` | `66% 0.04 268` | `#8892ab` | Metadatos, pistas (solo sobre `night`/`dusk`) |
| `--moon` | `86% 0.065 268` | `#bfd0fd` | Acento: calma, interactivo, foco |
| `--moon-strong` | `78% 0.1 268` | `#9cb5f8` | Acento activo (interruptor encendido, hover del primario) |
| `--amber` | `82% 0.135 72` | `#fab558` | **Alerta** (solo severidad) |
| `--ember` | `70% 0.175 30` | `#f86c59` | **Crítico** (solo severidad) |
| `--ember-text` | `76% 0.14 30` | `#fd8c7b` | Texto crítico en tamaño chico |
| `--mint` | `84% 0.09 165` | `#91debc` | Confirmación: encontrado, conectado, hecho (con cuentagotas) |
| `--line` | `86% 0.065 268 / 0.12` | luna translúcida | Bordes y separadores |
| `--line-strong` | `86% 0.065 268 / 0.22` | luna translúcida | Bordes de controles |

**Reglas de color**
- El ámbar y la brasa significan **riesgo y nada más**. No se usan de adorno.
- El menta se reserva para "salió bien": objeto encontrado, canal conectado,
  recordatorio hecho.
- Los bordes son luz de luna translúcida, nunca gris plano.
- **Prohibido:**
  - neón sobre negro, cian sobre fondo oscuro o degradados morado-azul;
  - tarjetas con borde grueso de color a la izquierda;
  - negro puro `#000`, y usar color para decorar.
- Con `prefers-contrast: more`, `--line` sube a 35% y `--line-strong` a 55%.

### 2.2 Contraste medido (WCAG)

| Texto \ fondo | night-deep | night | dusk | dusk-raised |
|---|---|---|---|---|
| ink | 16.55 | 15.51 | 14.08 | 12.27 |
| ink-2 | 9.89 | 9.27 | 8.41 | 7.33 |
| ink-3 | 6.17 | 5.78 | 5.25 | **4.57** (solo texto grande) |
| moon | 12.48 | 11.70 | 10.62 | 9.25 |
| amber | 10.80 | 10.12 | 9.19 | 8.01 |
| ember | 6.65 | 6.24 | 5.66 | 4.93 |
| ember-text | 8.42 | 7.89 | 7.16 | 6.24 |
| mint | 12.23 | 11.46 | 10.40 | 9.07 |

- Texto oscuro (`--night`) sobre botón luz de luna: **11.70**.
- El peor par que se usa en texto normal es `ink-3` sobre `dusk` (**5.25**).
  Todos cumplen AA, y casi todos AAA.

### 2.3 Estados globales de color

`dashboard.js` escribe `data-severity` en `<html>`, con el valor `normal`,
`warning` o `critical`. De ese atributo dependen:
- el resplandor detrás de la cara, que pasa a ámbar o brasa (`--face-heat`);
- el orbe de la consola;
- el punto del resumen de la casa: calma, alerta o crítico.

---

## 3. Tipografía

| Rol | Familia | Por qué |
|---|---|---|
| **Voz de Lumina**: subtítulos de lo que dice, titular del resumen, reloj grande, "¿Estás bien?" | **Newsreader** (serif, 300–600, eje óptico 6–72) | Distingue quién habla sin poner "Lumina:" |
| **Interfaz** (todo lo demás) | **Schibsted Grotesk** (400, 500, 600) | Grotesca clara y cálida, legible de lejos |

- Se cargan desde Google Fonts con `display=swap`.
- Respaldos: `"Iowan Old Style", Georgia, serif` y `"Helvetica Neue", Arial, sans-serif`.
- **Prohibido:** monoespaciadas, Inter/Roboto/Arial como elección y mayúsculas
  en etiquetas.

### 3.1 Escala

| Token | Tamaño | Uso |
|---|---|---|
| `--t-micro` | 0.75rem (12) | Rótulos sobre el video, etiquetas de recordatorio |
| `--t-small` | 0.875rem (14) | Metadatos, notas, estados |
| `--t-body` | 1rem (16) | Texto base |
| `--t-lead` | 1.125rem (18) | Detalle del resumen, lecturas, subtítulo de lo que dijiste |
| `--t-title` | 1.25rem (20) | Títulos de sección, título de avisos |
| `--t-headline` | `clamp(1.5rem, 1.15rem + 1.2vw, 2.125rem)` | Titular del resumen ("Todo en calma.") |
| `--t-caption` | `clamp(1.5rem, 1.1rem + 1.6vw, 2.375rem)` | Lo que dice Lumina (subtítulo) |
| `--t-display` | `clamp(2.75rem, 1.9rem + 3.2vw, 4.25rem)` | Reloj de la cara, "¿Estás bien?" |

**Detalles**
- **Cuerpo:** `line-height` 1.5 y espaciado de +0.01em, porque el texto claro
  sobre oscuro se ve más pesado.
- **Títulos grandes:** interlineado de 1.05 a 1.22 y espaciado de -0.012 a
  -0.02em. Se usa `text-wrap: balance` en titulares y `pretty` en párrafos.
- **Cifras:**
  - Tabulares (`tabular-nums`) solo donde cambian seguido y se comparan:
    tiempos de la bitácora y cuenta regresiva.
  - **No** en el reloj de la consola, las lecturas ni la agenda, porque en
    Schibsted separan los ":" y los ".".
  - Newsreader ya trae cifras tabulares.
- **Largo de línea:** máximo 60ch en el resumen, 44ch en los subtítulos y
  34ch en el aviso de caída.

---

## 4. Espacio, forma y capas

**Espaciado (base 4)**

| Token | `--s-1` | `--s-2` | `--s-3` | `--s-4` | `--s-5` | `--s-6` | `--s-8` | `--s-10` | `--s-12` | `--s-16` |
|---|---|---|---|---|---|---|---|---|---|---|
| px | 4 | 8 | 12 | 16 | 20 | 24 | 32 | 40 | 48 | 64 |

**Radios por jerarquía** (no uno para todo)
- `--r-sm` de 10 px para botones y campos.
- `--r-md` de 16 px para la cámara, el plano, avisos, toasts y botones de caída.
- `--r-pill` de 999 px para chips, interruptor, estado y pastilla de la casa.

**Capas**
- `--z-view` 1: vistas.
- `--z-sticky` 10: barra fija.
- `--z-toast` 100: toasts.
- `--z-boot` 1000: pantalla de espera.
- Aviso de caída: `--z-boot` + 10, encima de todo, incluso de la pantalla de espera.

**Materiales translúcidos**, solo para lo que flota sobre algo vivo (la barra
fija, los toasts, los rótulos del video, la pastilla de la casa, el estado de
voz y el aviso de caída):
- fondo oscuro al 60–86% de opacidad;
- `backdrop-filter: blur(10–18px)`.

Con `prefers-reduced-transparency` se vuelven sólidos.

**Sombras:** casi no hay. Solo el toast (`0 16px 40px -16px`). La jerarquía la
dan las superficies y el aire, no las sombras.

---

## 5. Iconografía

- **Una sola familia de trazo:** cuadrícula de 24×24, trazo de 1.75, puntas y
  uniones redondas, sin relleno, color `currentColor`.
- **Tamaños:** 20 px en general, 16 px en la bitácora, 24 px en avisos y 32 px
  en el estado vacío de la cámara.
- Van en un sprite al inicio de `index.html` y se usan con
  `<svg class="icon"><use href="#i-…">`.
- **Iconos disponibles** (`i-`): chevron, flame, door, person, thermo, alert,
  fall, search, camera, camera-off, shield, check, close, info, home, bell.
- Los iconos decorativos llevan `aria-hidden="true"`. **Prohibido usar emoji**
  como iconos.

---

## 6. Voz y tono (texto de interfaz y lo que dice Lumina)

- **Español de México.** Mayúscula solo al inicio de frase ("Abrir Google
  Calendar", no "Abrir Google Calendar Ahora").
- **Lumina habla en primera persona y te habla de tú:** "Te aviso si se abre la
  puerta", "Le avisé a tu contacto".
- **Frases cortas, verbos claros.** El botón dice lo que hace ("Revisar
  mensaje", "Agendar", "Estoy bien"), y el aviso usa el mismo verbo.
- **Errores:** qué pasó y qué hacer ("No pude leer tu calendario. Vuelvo a
  intentar en un minuto."). Sin disculpas vacías ni "¡Ups!".
- **Estados vacíos que invitan a actuar:** "La cámara está apagada. Enciéndela
  para vigilar la puerta, la cocina y buscar cosas."
- **Tipografía del texto:**
  - comillas « » para citar lo que se dice ("Di «Lumina, busca mi celular»");
  - "…" en cosas que están en curso ("Revisando…", "Pensando…");
  - números con cifras ("30 segundos").
- **Honestidad:**
  - "Sin verificar" en vez de adivinar.
  - "Nunca afirmo que ES una estafa; te digo qué señales tiene".
  - Ante una caída, pregunta primero.
- **Nada de:** mayúsculas en etiquetas, emoji, "Loading…" en inglés ni
  palabras de sistema ("webhook", "endpoint") en la pantalla principal.

---

## 7. Composición

### 7.1 Vista "Lumina" (la cara)

```
┌──────────────────────────────────────────────┐
│ 01:08                              ● Te escucho│  reloj (display, serif) + estado de voz
│ Viernes 25 de septiembre                      │
│                                               │
│              ( ▭      ▭ )                     │  cara: ~74vw, proporción 5:3
│                 ╰────╯                        │
│               ▮▯▮▯▮▯▮▯▮▯▮▯                    │  barras de voz (12)
│                                               │
│ «Lumina, ¿cómo está la casa?»   ┌───────────┐ │  subtítulos (izq.) + pastilla de la casa (der.)
│ Todo en calma. La puerta        │● Todo en… >│ │
│ está cerrada…                   └───────────┘ │
│                          Di «Lumina, …»       │  sugerencia rotativa (7 s)
└──────────────────────────────────────────────┘
```

- **Fila superior:** a la izquierda, el reloj y la fecha; a la derecha, el
  estado de voz (Dormida, En espera, Te escucho, Pensando…, Hablando, Buscando
  con la cámara o Micrófono bloqueado).
- **Centro:** la cara, con ancho `min(74vw, (100dvh − 380px) × 1.667)` y
  mínimo 240 px, con las barras de voz debajo.
- **Pie:** los subtítulos a la izquierda (máximo 44ch) y, a la derecha, la
  pastilla con el resumen de la casa (abre la consola) y una sugerencia rotativa.
- **Fondo:** degradado radial de `--night` a `--night-deep`, campo de
  "estrellas" (canvas, 45 nodos luz de luna) y viñeta.

### 7.2 Vista "La casa" (consola)

```
┌ ◉ Lumina ──────────────────────── [◯ Protección]  01:08 ┐  barra fija translúcida
│ Todo en calma.                                           │  titular serif + detalle
│ La puerta está cerrada. Hay alguien en casa.             │
│ ┌ aviso de riesgo (se despliega cuando hay) ───────────┐ │
│ ┌──────── Cámara ────────┐   ┌──── La casa ─────┐       │
│ │  video 4:3 + rótulos   │   │ plano animado     │       │
│ │                        │   │ lecturas (3×2)    │       │
│ └────────────────────────┘   ├──── Hoy ──────────┤       │
│  Buscar un objeto [____][Buscar]  agenda + agendar       │
│  (chips de objetos)          │ recordatorios     │       │
│ Lo que pasó (bitácora)       ├─ Cómo te aviso ───┤       │
│ Revisar un mensaje           │ canales           │       │
└──────────────────────────────────────────────────────────┘
```

- **Ancho máximo** de 1440 px, con márgenes de `clamp(16px, 3vw, 40px)`.
- **Dos columnas** de 1.3fr y 1fr que **fluyen por separado** (la cámara es
  alta y el plano no), con 48 px entre bloques verticales y 40 px entre columnas.
- **Solo dos elementos tienen superficie propia:** la cámara (pozo
  `--night-deep`) y el plano (`--dusk`). Lo demás es texto directo sobre la
  noche, separado por aire y líneas finas, sin tarjetas idénticas.

### 7.3 Puntos de quiebre

| Ancho | Cambio |
|---|---|
| ≤ 1024 px | Consola a una columna, en orden: cámara, casa, hoy, bitácora, mensaje, canales |
| ≤ 720 px | Cara al 88vw; los subtítulos y la pastilla se apilan; se ocultan las sugerencias |
| ≤ 560 px | Lecturas en 2 columnas; se oculta el texto "Lumina" del orbe |
| ≤ 480 px | Botones del aviso de caída apilados |
| altura ≤ 520 px | Reloj más chico, subtítulos sin alto mínimo |

- Los controles miden **44 px mínimo en pantallas táctiles**.
- Se respetan las zonas seguras (`env(safe-area-inset-*)`).

---

## 8. Componentes

| Componente | Especificación |
|---|---|
| **Botón** `.btn` | Alto de 44, radio de 10, borde `--line-strong`, texto de 15/500. Al presionar: `scale(0.97)`. Variantes: **primario** (fondo luna, texto `--night`, 600), **silencioso** (sin borde, `--ink-2`), **urgente** (fondo brasa, texto `--night-deep`), **chico** (36; 44 en táctil). Deshabilitado u ocupado (`aria-busy`): opacidad 0.5 |
| **Campo** `.field` | Alto de 44, fondo `--night-deep`, borde `--line-strong` que pasa a `--moon` con el foco. El `select` usa una flecha dibujada con degradados |
| **Chip** `.chip` | Píldora de 36 (44 en táctil), fondo `--dusk-raised`, texto `--ink-2` |
| **Interruptor** `.switch` (`role="switch"`) | Pista de 40×24, bolita de 18. Encendido: pista luna fuerte y bolita que se mueve 16 px |
| **Punto de estado** `.dot` | 8 px: `--ok` menta, `--calm` luna, `--warning` ámbar, `--critical` brasa. Siempre acompañado de texto |
| **Toast** | Abajo a la derecha, 380 px, máximo 3 a la vez, 5 s en pantalla (se pausa con el puntero, con el foco o con la pestaña oculta). Tonos info, ok, warning y critical con su icono. Puede llevar un enlace de acción |
| **Aviso de riesgo** | Superficie `--dusk` con un halo del color de la severidad en la esquina y borde del mismo color al 38%. Título de 20/600, cuerpo y acciones |
| **Aviso "¿Estás bien?"** | Pantalla completa con fondo oscuro y halo de brasa, y tarjeta centrada de 560 px máximo. Anillo de cuenta regresiva de 132 px con número serif de 48. Título a tamaño display. Botones de 72 px de alto y texto de 20. Diálogo `role="alertdialog"` |
| **Cámara** | Proporción 4:3, pozo `--night-deep`, radio de 16. Rótulos translúcidos: "En vivo" (punto brasa que parpadea), "Buscando: X" y "Veo: persona, taza…". En búsqueda: esquinas de encuadre y un barrido. Al encontrar: anillo menta y esquinas que se cierran |
| **Plano de la casa** | SVG de 400×260 (máximo 560 px), con sala, cocina, recámara y entrada. Puerta con bisagra en (56, 244) que gira -80° al abrirse. Estufa con 4 quemadores (ámbar si está encendida). Calor en la cocina (degradado recortado al cuarto). Personas: punto luna con halo. Escudo cuando está protegida. Cono de visión de la cámara |
| **Lecturas** | Rejilla de 3×2: etiqueta en `--ink-3` de 14 y valor de 18/500. "Sin verificar" en `--ink-3`. Los riesgos van en ámbar o brasa |
| **Bitácora** | Filas con icono en círculo de 32, texto y hora relativa ("ahora", "hace 3 min", "14:05"). Borde inferior `--line` |
| **Recordatorio** | Casilla de 22 dentro de un área tocable de 44, texto y etiqueta "Al salir" o "Al llegar". Al completarse: menta y la fila se cierra |
| **Pastilla de la casa** (en la cara) | Píldora translúcida con punto de severidad, titular de 15/600, detalle de 13 y chevron |
| **Estado de voz** | Píldora translúcida con un punto de 8: gris en reposo, luna que parpadea al escuchar, ámbar si hay un problema |

---

## 9. El rostro de Lumina

- SVG de `viewBox 0 0 1000 600`, **sin contorno de cabeza**: solo ojos y
  boca, para que se lea como presencia y no como icono.
- **Ojos:** "cápsulas" de 208×92 centradas en (270, 235) y (730, 235).
- **Boca:** línea de 380 de ancho a la altura y = 460.
- **Trazo** de 22 con puntas redondas, en el color de acento de la expresión.
- **Brillo en dos capas:** `drop-shadow` de 10 a 26 px más 22 a 48 px. Crece
  con la energía de la voz (`--talk-glow`, calculado en cada cuadro).
- **Tres capas de transform:** parallax con el mouse (inclinación de hasta
  ±5°), la respiración y los gestos de cada expresión.

### 9.1 Expresiones

| Expresión | Ojos | Boca | Acento | Extra |
|---|---|---|---|---|
| inactivo | cápsula | recta | luna | parpadeo y mirada que se mueve |
| neutral | cápsula | recta | luna | mirada que se mueve |
| **escuchando** (reposo normal) | cápsula | sonrisa | luna | ondas de escucha, parpadeo y mirada |
| feliz | "^" | sonrisa | menta | — |
| sorprendido | círculos | "o" | luna | cejas arriba |
| confundido | entrecerrado + cápsula | zigzag | ámbar | ceja y cabeza ladeada |
| pensando | arco girando | recta | luna | puntos flotando |
| triste | caídos | curva abajo | ink-3 | cejas tristes |
| error | "×" | recta | ámbar | pulso |
| activando | círculos | "o" | menta | pulso (al encender) |

**Qué expresión usa en cada situación**
- **En reposo:** "escuchando" si el micrófono funciona, "inactivo" si no.
- **Posible caída:** "sorprendido". Si nadie contesta o se pidió ayuda: "triste".
- **"Estoy bien":** "feliz", y después vuelve al reposo.
- **Buscando con la cámara:** "pensando".
- **Al responder:** depende del tono de su última frase: feliz, confundida
  (cuando no sabe algo) o triste (cuando se disculpa).

### 9.2 Sonidos (sintetizados, sin archivos)

| Momento | Tono |
|---|---|
| Expresión positiva | 480 → 760 Hz, 0.18 s |
| Expresión negativa | 480 → 260 Hz, 0.22 s |
| Encendido | 392 → 523 Hz y luego 523 → 784 Hz |
| Cambio neutro | 420 Hz, 0.08 s, muy suave |
| "Lumina" (te oí) | 660 → 880 Hz, 0.12 s |
| Posible caída | 880 → 660 Hz, dos veces, 0.28 s cada una |

---

## 10. Movimiento y animación

### 10.1 Principios

1. **Cada animación tiene un porqué:** confirmar una acción, mostrar de dónde
   viene algo, hacer visible un cambio de estado, suavizar un salto brusco o
   (solo en momentos raros) dar un toque de gusto.
2. **Lo frecuente no se anima, o casi no.** Los atajos de teclado (`d` y `l`)
   cambian de vista **sin animación**.
3. **Solo `transform` y `opacity`.** Excepciones permitidas: `clip-path`,
   `stroke-dashoffset` en SVG y `grid-template-rows` para desplegar avisos.
4. **Menos de 300 ms en la interfaz.** Los momentos raros pueden durar más:
   encendido, primer dibujo del plano, puerta y caída.
5. **Transiciones, no `@keyframes`, en lo que se dispara seguido**, para que
   se pueda interrumpir.
6. **Nunca `scale(0)`** (se entra desde 0.94–0.97), **nunca `ease-in`** y
   **nunca `transition: all`**.
7. **El hover** solo aplica con `@media (hover: hover) and (pointer: fine)`.
8. **Con "reducir movimiento"** hay menos movimiento, pero no cero: se quitan
   desplazamientos y bucles y se quedan los fundidos que ayudan a entender.

### 10.2 Curvas y duraciones (tokens)

| Token | Valor | Cuándo |
|---|---|---|
| `--ease-out` | `cubic-bezier(0.23, 1, 0.32, 1)` | Entrar y salir (la opción por defecto) |
| `--ease-in-out` | `cubic-bezier(0.77, 0, 0.175, 1)` | Algo que ya está en pantalla y se mueve (la puerta, la cara que viaja) |
| `--ease-drawer` | `cubic-bezier(0.32, 0.72, 0, 1)` | Reservada para cajones o paneles |
| `ease` | — | Cambios de color o borde (hover) |
| `linear` | — | Movimiento constante (barrido, anillo de la cuenta) |
| `--d-press` | 160 ms | Presionar |
| `--d-fast` | 200 ms | Hover, fundido de vista, cambios chicos |
| `--d-base` | 250 ms | Entradas de elementos, avisos, lecturas |
| `--d-view` | 380 ms | Viaje de la cara, puerta, tarjeta de caída |

### 10.3 Catálogo de animaciones

**Transiciones entre vistas**

| Qué | Propiedades | Duración y curva | Propósito |
|---|---|---|---|
| Cambiar de vista (con View Transitions) | la raíz hace un fundido y **la cara viaja y se encoge hasta el orbe** (elemento compartido `lumina`) | raíz 250 ms `--ease-out`; cara 380 ms `--ease-in-out` | Continuidad: es la misma Lumina |
| Cambiar de vista (sin View Transitions o con movimiento reducido) | opacity | 200 ms `--ease-out` | Evitar un salto brusco |

**La cara (siempre viva)**

| Qué | Detalle |
|---|---|
| Respiración | scale 1 → 1.02, 3.6 s `ease-in-out`, en bucle |
| Parpadeo | scaleY hacia 0.05. Cierra rápido (factor 0.55 por cuadro) y abre lento (0.16), cada 2.5–6 s, doble el 15% de las veces |
| Mirada | La pupila se desplaza hasta ±20/±14, cada 1.5–3.5 s, con suavizado por cuadro |
| Escuchando | Mancha de luz (opacidad 0.06 ↔ 0.13, 2.4 s) y 2 ondas desfasadas 0.8 s (scale 0.85 → 1.35 con fundido) |
| Pensando | El arco del ojo gira (1.3 s `linear`) con un pulso (0.55 s) y tres puntos flotan (−10 px, 1.2 s) |
| Error o encendido | Pulso de escala 1 ↔ 1.04, 500 ms |
| Confundida | Ladea la cabeza −5° |
| Hablando | La boca se abre y se cierra (3 bandas que se re-sortean cada 70–140 ms, más un empujón en cada palabra real) y el brillo crece con la energía |
| Parallax | Sigue al mouse: inclinación de ±5° y desplazamiento de ±8 px, 150 ms (solo con puntero fino) |

**Voz**

| Qué | Detalle |
|---|---|
| Barras | En reposo: cortas y quietas. Escuchando: 4 ritmos distintos de 0.7 a 1.3 s, para que se vea orgánico. Pensando: ola en cadena (1.6 s, con 90 ms de retraso por barra). Hablando: siguen la energía de la boca en cada cuadro |
| Punto de escucha | Parpadeo de opacidad 1 ↔ 0.35, 1.4 s |
| Subtítulos | Cada palabra pasa de opacidad 0.38 a 1 (140 ms) **al ritmo real de la voz** (evento `onboundary` o avance del audio; si no llegan, se estima a 13 caracteres por segundo). Desaparecen 8 s después (250 ms) |
| Sugerencias | Fundido de salida y entrada de 300 ms cada 7 s, solo si la cara está a la vista |

**Encendido**

| Qué | Detalle |
|---|---|
| Pista "Di «Lumina»…" | Aparece a los 1.2 s: sube 6 px con fundido, 800 ms `--ease-out` |
| Destello al despertar | Destello radial de luz de luna: scale 0.6 → 1 → 1.4 con opacidad 0 → 0.8 → 0, 550 ms. La pantalla de espera se desvanece en 700 ms |

**Consola**

| Qué | Detalle |
|---|---|
| Titular del resumen | Cuando cambia: fundido con desenfoque de 2 px a nítido, 250 ms (Web Animations API) |
| Lecturas | Solo cuando el valor cambia: opacidad 0.3 → 1 y subida de 4 px, 250 ms |
| Aviso de riesgo | Se despliega con `grid-template-rows` de 0fr a 1fr más opacidad, 250 ms. Empuja el contenido en vez de taparlo |
| Bitácora | Las entradas nuevas aparecen (`@starting-style`: opacidad 0 y −6 px), 250 ms. Las que ya estaban no se vuelven a dibujar |
| Recordatorio completado | La casilla se pone menta, la palomita aparece en 200 ms y la fila se cierra en 250 ms |
| Resultado anti-extorsión | Entrada con opacidad y 6 px, 250 ms |
| Foco en un panel ("abre mi agenda") | Desplazamiento suave hasta el panel y un contorno luz de luna que se enciende en 200 ms y se apaga en 600 ms |
| Punto de estado | Cambio de color, 250 ms |

**Plano de la casa**

| Qué | Detalle |
|---|---|
| Primer dibujo | Los muros "se dibujan" (`stroke-dashoffset` 1 → 0, 900 ms `--ease-out`), **solo la primera vez que se abre la consola** |
| Puerta | Gira sobre su bisagra a −80°, 380 ms `--ease-in-out`, y se pone ámbar. Aparece el arco de apertura |
| Persona | Aparece con scale 0.6 → 1 y opacidad, 250 ms. Un halo que se expande cada 2.8 s |
| Calor en la cocina | Opacidad a 0.55 (alerta) o 0.75 (crítico). En crítico late (0.55 ↔ 0.85, 2.4 s) |
| Estufa, cámara y escudo | Cambian de color u opacidad en 250 ms |

**Cámara**

| Qué | Detalle |
|---|---|
| Video al encender | Fundido de entrada, 250 ms (`@starting-style`) |
| "En vivo" | Punto brasa que parpadea, 2 s |
| Buscando | Esquinas de encuadre que aparecen y una línea que barre de arriba abajo (`translateY` hasta `100cqh`, 2.6 s `linear`) |
| Encontrado | Anillo menta y las 4 esquinas que se cierran 10 px hacia el centro, 250 ms |

**Botones, chips, interruptor y toasts**

| Qué | Detalle |
|---|---|
| Presionar | scale 0.97, 160 ms `--ease-out`. En la casilla del recordatorio, 0.9. En el cerrar del toast, 0.94 |
| Hover | Solo cambios de color o borde (`ease`, 200 ms). Nada se mueve con hover |
| Interruptor | La bolita se desliza 16 px, 200 ms `--ease-out` |
| Toast | Entra desde abajo (`translateY(100%)` a 0) con fundido, 400 ms. **Sale por donde entró**, en 300 ms |

**"¿Estás bien?" (caída)**

| Qué | Detalle |
|---|---|
| Aparición | Fondo en fundido de 250 ms y tarjeta de scale 0.94 a 1 en 380 ms `--ease-out` |
| Cuenta regresiva | Anillo que se vacía (`stroke-dashoffset`, se actualiza cada 250 ms `linear`) y número serif |
| Calor | Mientras corre el tiempo, el fondo late entre oscuro y brasa cada 2.4 s |

### 10.4 Movimiento reducido (`prefers-reduced-motion: reduce`)

- **Se detienen:**
  - respiración, ondas, pulsos, puntos y el giro del ojo;
  - barras de voz animadas, parallax y parpadeo del punto;
  - barrido de la cámara, halos, latido del calor y del aviso de caída;
  - el destello de encendido y el campo de estrellas (queda un solo cuadro fijo).
- **Se quedan sin desplazamiento:**
  - el cambio de vista (fundido de 200 ms, sin viaje de la cara);
  - los toasts, las lecturas, la bitácora y el resultado anti-extorsión (solo fundido);
  - la puerta (cambia de posición sin animarse);
  - los muros del plano (aparecen ya dibujados).
- Los cambios de color y los fundidos que ayudan a entender se quedan.

### 10.5 Rendimiento

- **La vista oculta pausa todas sus animaciones** (`animation-play-state: paused`).
- **El canvas de estrellas** solo se anima con la cara a la vista y la pestaña visible.
- **El motor de la cara** (un solo `requestAnimationFrame`) deja de mover el
  rostro mientras se ve la consola.
- **`--talk-glow`** se escribe en el `<svg>` de la cara, no en el contenedor
  de la vista, para no recalcular estilos de todo. Solo se escribe cuando cambia.
- Los bucles de la interfaz son `@keyframes` de CSS, que no bloquean el hilo
  principal. Lo dinámico, como la boca, usa `requestAnimationFrame`.

---

## 11. Accesibilidad

- **Foco visible** en todo: contorno luz de luna de 2 px con 2 px de separación.
- **"Saltar al contenido"** para teclado.
- **Vistas:** la oculta queda `inert`. Al cambiar de vista, el foco se lleva a
  la nueva (el titular o la pastilla).
- **La barra fija no tapa el foco** (`scroll-padding-top: 88px`).
- **Regiones vivas:**
  - el estado de voz (`aria-live="polite"`);
  - los toasts (`region` + `aria-live`);
  - el estado de búsqueda y de agendar (`role="status"`);
  - el resultado anti-extorsión.
- **El aviso de caída** es un `role="alertdialog"` con `aria-modal`; el foco va
  a "Estoy bien" y vuelve adonde estaba al cerrarse.
- **Nombres accesibles:** el orbe ("Volver con Lumina"), la casilla del
  recordatorio ("Marcar como hecho: …"), los campos (etiquetas ocultas pero
  presentes) y el plano (su título se actualiza con el resumen de la casa).
- **Toque:** 44 px mínimo, `touch-action: manipulation` y sin el resaltado
  gris del sistema.
- También respeta `prefers-reduced-transparency`, `prefers-contrast: more` y
  `color-scheme: dark`.

---

## 12. Diseño de software del frontend

### 12.1 Pila

- **HTML, CSS y JavaScript sin frameworks ni compilación.** Los sirve FastAPI
  (`StaticFiles`).
- **APIs del navegador:**
  - Web Speech (`SpeechRecognition` y `speechSynthesis`);
  - Web Audio (tonos);
  - View Transitions;
  - Web Animations;
  - `@starting-style`;
  - Canvas 2D;
  - container queries (`cqh`).
- **Backend:** FastAPI, OpenCV, YOLOv8n, MediaPipe Pose, SQLite y Ollama (ver
  `CLAUDE.md` y `README.md`).

### 12.2 Archivos y orden de carga

```
tokens.css → app-shell.css → lumina.css → dashboard.css
lumina-field.js → app-shell.js → voice-commands.js → lumina.js → dashboard.js
```

- Son scripts clásicos que comparten el ámbito global, así que **los nombres
  de nivel superior no deben repetirse** entre archivos.
- Cada archivo publica en `window` lo que otros usan: `switchToView`,
  `showToast`, `refreshHome`, `refreshReminders`, `respondToFall`,
  `setSearchMode`, `startCameraObjectSearch`, entre otros.
- **Caché:** el servidor responde `Cache-Control: no-cache`, y `index.html`
  lleva `?v=N` en cada recurso; hay que subirlo al cambiar un archivo.

### 12.3 Estado visible en `<html>`

| Atributo | Valores | Quién lo escribe | Quién lo lee |
|---|---|---|---|
| `data-view` | `lumina` · `dashboard` | app-shell.js | CSS, el canvas, el motor de la cara, la bitácora |
| `data-severity` | `normal` · `warning` · `critical` | dashboard.js | Resplandor de la cara, orbe, pastilla |
| `data-voice` | `idle` · `listening` · `processing` · `speaking` | lumina.js | El orbe de la consola |

### 12.4 Flujos

**Voz**

```
micrófono → SpeechRecognition (es-MX, continuo, parciales al subtítulo)
  → buffer de 600 ms (junta "Lumina," + "busca mi mochila")
  → handleVoiceCommand
      1. ¿alerta de caída abierta? → routeFallReply → respondToFall (o vuelve a preguntar)
      2. ¿pantalla de espera? → solo la palabra "Lumina"
      3. routeVoiceCommand (voice-commands.js, función pura y probada) → COMMAND_HANDLERS
      4. ¿buscando con la cámara? → "Sigo buscando…"
      5. si no es comando → askLumina (servidor: respuestas fijas, memoria, agenda y luego Ollama)
```

**Habla**

```
speak(texto) → apaga el micrófono (para que no se escuche a sí misma)
  → subtítulo palabra por palabra → ElevenLabs (si hay clave) o voz del navegador
  → boca y barras con la energía → al terminar: vuelve el micrófono y el subtítulo se desvanece
```

**Consultas al servidor**
- `/home/overview` cada 3 s (cada **1 s** si hay una caída abierta).
- Lo que ve la cámara, cada 1.5 s (solo con la cámara encendida, la consola a
  la vista y la pestaña visible).
- La agenda cada 60 s y los canales cada 30 s.

**Caída** (el servidor manda; la página solo muestra y pregunta)

```
detector (o "me caí", o POST /events) → asking (30 s)
   ├─ "estoy bien" ─────────────→ ok (se cierra)
   ├─ "necesito ayuda" ─────────→ help (se avisa al contacto)
   └─ nadie contesta (vigilante del servidor, cada 1 s) → escalated (se avisa al contacto)
help / escalated → siguen visibles hasta "estoy bien" (máximo 10 min)
```

La página ignora datos viejos mientras envía tu respuesta (`fall.answering`),
para no reabrir el aviso.

### 12.5 Cómo agregar cosas sin romper el sistema

- **Un color o un tiempo nuevo:** se agrega como token en `tokens.css`. Nunca
  un valor suelto.
- **Un componente:** se reutilizan `.btn`, `.field`, `.chip`, `.switch`, `.dot`
  y los toasts. Lleva estados de foco, hover (condicionado), presionado,
  deshabilitado y ocupado, y su versión con movimiento reducido.
- **Una animación:** antes de escribirla, responder qué tan seguido se ve, para
  qué sirve y si cabe en menos de 300 ms. Solo `transform` y `opacity`, con los
  tokens de curva, y su versión con movimiento reducido.
- **Un comando de voz:** una regla en `voice-commands.js` más su frase de
  prueba en `voice_commands_check.js` y un handler en `COMMAND_HANDLERS`.
- **Un texto:** seguir la sección 6 (voz y tono).
- **Siempre:** `python -m pytest -q` y revisar la pantalla a 1440, 820 y 390
  px de ancho.

---

## 13. Qué NO hacer (lista rápida)

- Neón o acentos brillantes sobre negro, cian sobre oscuro, degradados morado-azul.
- Tarjetas idénticas con la misma sombra, o bordes gruesos de color a la izquierda.
- Mayúsculas en etiquetas, monoespaciada para datos, "·" como separador de
  metadatos, emoji como iconos.
- `transition: all`, `scale(0)`, `ease-in`, animar `width`, `height` o `top`,
  y hover sin condición de puntero.
- Animar lo que se usa todo el tiempo (atajos, cambios por teclado).
- Afirmar como hecho una emergencia, una estafa o un estado que no se sabe.
- Poner colores, tiempos o curvas fuera de `tokens.css`.
