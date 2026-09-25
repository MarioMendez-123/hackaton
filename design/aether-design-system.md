---
name: interface-design-system
description: Sistema de diseño vigente de Aether (dashboard/index.html + inventory.html) — reemplaza toda versión anterior.
---

# Aether — sistema de diseño de interfaz

**Vigente desde:** adopción de la referencia visual definitiva del usuario
(campo de nodos 3D, casi negro, acento azul-violeta). Reemplaza por completo
el sistema anterior (grafito/acero/ámbar sobre Inter) — si algún archivo de
este proyecto sigue citando esos nombres de token, está desactualizado.

## Dirección y sensación
"Industrial systems" real, literalmente el subtítulo del wordmark: casi
negro absoluto, un solo acento azul-violeta, tipografía técnica de tres
familias con roles fijos. La portada abre con un campo de nodos 3D
(percepción/espacio, no datos) detrás de un hero centrado; el resto del
sitio (módulos, arquitectura, inventory.html) es denso, alineado, sin
adornos — panel de control, no landing.

## Tokens (dashboard/style.css, :root)
- **Superficie:** `--bg` `#05070A` (fondo), `--bg2` `#0A0F16` (degradado del
  hero), `--surface` (paneles/tarjetas, mismo tono que bg2),
  `--surface-raised` `#131A24` (hover, un paso arriba).
- **Texto:** `--ink` `#EDEFF3` (primario), `--ink-dim` `#8891A0`
  (terciario), más `--text-secondary`/`--text-muted` interpolados entre
  ambos. 4 niveles, igual que antes — cambió la paleta, no el sistema de
  jerarquía por opacidad.
- **Bordes:** `--line` `#1B222C` (base, la mayoría de los casos),
  `--border-strong` `#2A3442` (inputs, tags que necesitan más definición).
  Profundidad solo por línea, nunca sombra — principio que se mantiene sin
  cambios sobre el sistema anterior.
- **Acento único (interactivo):** `--accent` `#6E8CFF`, con `--node-a`
  `#4C7CE0` / `--node-b` `#9C6BE0` como el par azul→violeta del campo de
  nodos. Úsalo para todo lo clickeable: hover de tiles, subrayado de
  navlinks, foco de teclado, CTA primario.
- **Positivo (estado operativo):** `--positive` `#5FA779` — el mismo verde
  que ya trae el `.status-dot` de la referencia para "en línea". Reutilizado
  en todo el sistema para "Funcionando", nunca decorativo. Deliberadamente
  distinto de `--accent`: un tile puede ser interactivo (borde/reticle en
  accent) Y estar funcionando (dot/texto de estado en positive) — dos
  señales separadas, no una.
- **Atención (ámbar):** `--warn` `#E0A64A` — única adición sobre la
  referencia del usuario, necesaria para no perder la distinción de tres
  vías que ya existía en el sistema anterior (interactivo / funciona /
  necesita atención). Se usa SOLO para: sin identificar, pendiente de
  hardware, retirar producto, errores de formulario. Nunca decorativo.
- **Radios:** `--radius-sm` 4px (botones, inputs, tags), `--radius-md` 8px
  (paneles, tarjetas, diálogo).
- **Espaciado:** sin cambios — `--space-1..7` (4/8/12/16/24/32/48px).

## Tipografía — tres familias, roles fijos (ya no "una sola familia")
Corrección explícita sobre el sistema anterior (que exigía una sola
tipografía, Inter): la referencia del usuario trae tres familias con roles
claros, y ESO es la disciplina a mantener — no mezclar libremente, sino
respetar qué familia hace qué trabajo:
- **Big Shoulders Display** (600/700/800) — SOLO títulos grandes: el `h1`
  del hero y los `.section-title` de cada sección. En ningún otro lugar.
- **IBM Plex Sans** (400/500/600) — cuerpo de texto, en todas partes. Es el
  `font-family` de `body`; todo lo demás lo hereda salvo que se anote lo
  contrario.
- **IBM Plex Mono** (400/500/600) — SOLO anotación técnica: wordmark,
  kickers, status-pill, tags de tabla (`th`, `.module-tag`,
  `.decision-num`/`.decision-ref`), cifras (`panel-meta`,
  `.history-summary-time`, `.delta`), y el input de contraseña del diálogo
  de retirar (convención de campos de código/contraseña).

Import único en el `<head>` de ambas páginas:
```
family=Big+Shoulders+Display:wght@600;700;800
&family=IBM+Plex+Sans:wght@400;500;600
&family=IBM+Plex+Mono:wght@400;500;600
```

## Firma visual — esquinas de mira (reticle)
Se mantiene del sistema anterior, recoloreada a `--accent`: las cuatro
esquinas que YOLO dibuja alrededor de una detección, reutilizadas para
marcar "activo/interactivo". Su aplicación más literal es nueva: el
placeholder de cámara en la sección Percepción usa esquinas de mira más
grandes (16px) enmarcando el visor completo — un encuadre de cámara real,
honestamente marcado como sin señal todavía. También enmarca los tiles
activos de `.module-grid`. Los tiles pendientes de hardware NUNCA llevan
esquinas de mira — borde punteado en `--warn` en su lugar.

## Componentes clave
- **`.site-nav`** — componente compartido entre ambas páginas. Base sin
  posicionamiento; `.site-nav--fixed` (solo portada) la fija sobre el campo
  de nodos; `.site-nav--framed` (solo inventory.html) la deja en flujo
  normal con borde inferior. Contiene `.wordmark` (siempre linkea a `/`),
  `.navlinks`, y `.status-pill` — en la portada muestra el estado estático
  de módulos ("Percepción · Inventory Engine · Backend — funcionando"), en
  inventory.html muestra el conteo en vivo de Declared Inventory (mismo
  dato que `app.js` ya trae para la tabla, sin pedir nada nuevo a la API).
- **`.btn`** — un solo componente para CTA de hero, diálogo y acciones de
  tabla. Modificadores: `--primary` (acento, la acción principal),
  `--warn` (ámbar, cambia estado con consecuencia — ej. "Retirar"; nunca se
  usa un rojo de peligro que no existe en la paleta), `--sm` (escala de
  fila de tabla). Sin modificador de color = ghost (transparente,
  `--text-tertiary`), usado para "Cancelar" y el CTA secundario del hero.
- **`.module-card`** — tile de navegación real: `<a>` si el módulo tiene
  interfaz propia (todo el tile es el link, reticle + borde `--accent`,
  hover sube a `--surface-raised`), `<div aria-disabled="true">` si no
  (borde punteado `--warn`, `cursor:not-allowed`, texto explícito "sin
  interfaz" — nunca un link roto).
- **`.camera-placeholder`** — visor de cámara honesto: borde + reticle
  grande, aspect-ratio 16:9, label superior en mono ("CAM_01 · SIN SEÑAL",
  color `--warn`) y texto centrado explicando que la vista en vivo llega en
  una fase posterior. No implementa cámara real — es deliberadamente
  austero para no prometer más de lo que hay.
- **`.retire-dialog`** — `<dialog>` nativo, nunca `prompt()`/`confirm()`.
  `.field-input` más oscuro que la superficie que lo rodea, en mono.
- **`.page-section`** — full-bleed con `.section-shell` centrado (max-width
  1180px) adentro; cubre con `--bg` sólido el campo de nodos fijo conforme
  se hace scroll. Todo section usa `.section-kicker` (mono, tracked) +
  `.section-title` (Big Shoulders Display).

## Campo de nodos — fondo persistente, no solo del hero
El canvas (`node-field.js`) y el `.veil` son de fondo fijo en las TRES
pantallas (portada completa, no solo el hero, e inventory.html), no un
efecto exclusivo de arriba del pliegue. `.page-section` no lleva fondo
sólido a propósito — si alguna sección nueva necesita ocultar el canvas,
eso es una regresión a corregir, no una opción de diseño. Legibilidad se
protege en dos niveles: (1) cualquier superficie con texto real ya trae su
propio fondo opaco `var(--surface)` (paneles, tiles, tablas) — nunca
depender del fondo de página para eso; (2) `data-density="low"` en el
`<canvas>` (leído por `node-field.js`) reduce nodos y opacidad de
líneas/puntos, usado en inventory.html por ser la pantalla con más texto
suelto y datos reales; `.veil--dense` refuerza el vignette ahí también. La
portada usa densidad normal.

## Micro-interacciones — convención fija para todo elemento clickeable
Todo botón/link/checkbox real necesita un estado `:active` que se sienta
físico, no solo `:hover`. Dos técnicas, una por tipo de elemento — no se
mezclan arbitrariamente:
- **Elementos con forma de botón/tarjeta** (`.btn`, `.module-card--active`):
  `transform: scale()` (nunca por debajo de 0.95) + un glow de
  `box-shadow` con el color semántico del propio elemento (`--accent-soft`
  para primary/tiles, `--warn-soft` para warn). Entrada rápida (~100ms),
  salida a la duración base del hover (~140-200ms) — se logra con
  `transition-duration` más corta dentro de la regla `:active` misma.
- **Links de texto inline** (`.navlinks a`, `.wordmark b`): sin scale
  (se ve raro en texto corto) — en su lugar, color a `--accent` +
  `text-shadow` de glow, transición ~80-100ms.
- **Checkbox nativo** (`.toggle-field input[type=checkbox]`): anillo de
  `box-shadow` en `--accent-soft` sobre el input mismo al presionar, más
  `:focus-visible` explícito (los navegadores no siempre dan uno legible
  sobre fondo casi negro).
- Filas de tabla con `<summary>` (bitácora expandible): hover sube a
  `--surface-raised`, `:active` baja a `--bg` — el mismo par
  claro-al-pasar/oscuro-al-presionar que un botón físico.

## Páginas actuales
- `dashboard/index.html` — portada: campo de nodos (`node-field.js`, sin
  tocar la API, puramente decorativo) + hero + secciones Percepción
  (placeholder de cámara) / Módulos del sistema (bento) / Arquitectura
  (tabla de 8 decisiones) / footer.
- `dashboard/inventory.html` — Declared Inventory + Bitácora + retirar
  producto con contraseña, mismo sistema visual, nav en flujo normal.
- `dashboard/app.js` — datos de inventory.html (fetch real, cache en
  `allEntries`, nunca números fabricados).
- `dashboard/portada.js` — único dato dinámico de la portada (conteo de
  Declared Inventory vía `GET /inventory`, mostrado dentro del tile
  Backend + Dashboard).
- `dashboard/node-field.js` — animación del campo de nodos del hero.
  Respeta `prefers-reduced-motion` (un solo cuadro estático, sin parallax).
