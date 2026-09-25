/**
 * app-shell.js — une la cara de Lumina y la consola de la casa en un solo
 * producto, y guarda lo que las dos vistas comparten: el cambio de vista,
 * los avisos flotantes (toasts) y el reloj.
 *
 * `switchToView` es el único punto de entrada para cambiar de vista: lo usan
 * los botones, el teclado y los comandos de voz de lumina.js. Cada cambio
 * dispara el evento `viewchange` en document (dashboard.js lo escucha).
 */

const rootEl = document.documentElement;
const viewEls = {
  lumina: document.getElementById("view-lumina"),
  dashboard: document.getElementById("view-dashboard"),
};
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const canViewTransition = typeof document.startViewTransition === "function";

// Con View Transitions la cara viaja hasta el orbe de la consola (elemento
// compartido); sin ellas, o con movimiento reducido, queda el fundido CSS.
if (canViewTransition && !prefersReducedMotion.matches) rootEl.classList.add("has-vt");

function applyView(name) {
  const leaving = viewEls[rootEl.dataset.view];
  const focusWasInside = leaving && leaving.contains(document.activeElement);

  for (const [key, el] of Object.entries(viewEls)) {
    const active = key === name;
    el.classList.toggle("view--active", active);
    el.inert = !active;
  }
  rootEl.dataset.view = name;

  // El foco no se puede quedar en una vista inerte: se lleva a la nueva.
  if (focusWasInside) {
    const target = name === "dashboard" ? document.getElementById("summaryHeadline") : document.getElementById("houseChip");
    target?.focus({ preventScroll: true });
  }
  document.dispatchEvent(new CustomEvent("viewchange", { detail: { view: name } }));
}

/** Cambia de vista. `animate: false` para acciones de teclado (se repiten
 * mucho; animarlas las haría sentir lentas). */
function switchToView(name, { animate = true } = {}) {
  if (!viewEls[name] || rootEl.dataset.view === name) return;
  if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
  if (animate && rootEl.classList.contains("has-vt") && !document.hidden) {
    // Si el navegador la aborta (p. ej. la pestaña se oculta a medio camino),
    // la vista igual cambia: el rechazo no es un error real.
    document.startViewTransition(() => applyView(name)).ready.catch(() => {});
  } else {
    applyView(name);
  }
}
window.switchToView = switchToView;

// Son enlaces (#dashboard / #lumina): Ctrl/Cmd+clic sigue abriendo otra
// pestaña; el clic normal cambia de vista sin agregar entradas al historial.
document.querySelectorAll("[data-switch-view]").forEach((el) => {
  el.addEventListener("click", (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    switchToView(el.dataset.switchView);
  });
});

// La URL dice qué vista está activa: /#dashboard abre directo la consola.
rootEl.dataset.view = "";
applyView(location.hash === "#dashboard" ? "dashboard" : "lumina");
window.addEventListener("hashchange", () => {
  switchToView(location.hash === "#dashboard" ? "dashboard" : "lumina");
});

// Respaldo manual de la voz: "d" = la casa, "l" = Lumina.
document.addEventListener("keydown", (event) => {
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  const target = event.target;
  if (target.closest?.("input, textarea, select, [contenteditable]")) return;
  if (event.key === "d") switchToView("dashboard", { animate: false });
  if (event.key === "l") switchToView("lumina", { animate: false });
});

// ============================================================================
// Avisos flotantes. Entran desde abajo y salen por el mismo lado (ver
// .toast en app-shell.css); máximo tres a la vez. El tiempo se detiene
// mientras el puntero o el foco están encima, y con la pestaña oculta.
// ============================================================================

const toasterEl = document.getElementById("toaster");
const TOAST_ICON = { info: "i-info", ok: "i-check", warning: "i-alert", critical: "i-alert" };
const TOAST_MS = 5000;
const MAX_TOASTS = 3;

function dismissToast(toast) {
  if (toast.classList.contains("is-leaving")) return;
  clearTimeout(toast._timer);
  toast.classList.add("is-leaving");
  const remove = () => toast.remove();
  toast.addEventListener("transitionend", remove, { once: true });
  setTimeout(remove, 400); // por si no hay transición (movimiento reducido)
}

function armToastTimer(toast, ms) {
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    if (document.hidden) armToastTimer(toast, 1500);
    else dismissToast(toast);
  }, ms);
}

/** `action: { label, href, target }` agrega un enlace al aviso. Sirve para lo
 * que el navegador solo deja abrir con un toque del usuario (una ventana
 * nueva pedida por voz, por ejemplo). */
function showToast({ title, body = "", tone = "info", duration = TOAST_MS, action = null }) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.dataset.tone = tone;
  toast.innerHTML =
    `<svg class="icon" aria-hidden="true"><use href="#${TOAST_ICON[tone] || TOAST_ICON.info}"></use></svg>` +
    `<div><p class="toast-title"></p><p class="toast-body"></p></div>` +
    `<button type="button" class="toast-close" aria-label="Cerrar aviso">` +
    `<svg class="icon" aria-hidden="true"><use href="#i-close"></use></svg></button>`;
  toast.querySelector(".toast-title").textContent = title;
  const bodyEl = toast.querySelector(".toast-body");
  if (body) bodyEl.textContent = body;
  else bodyEl.remove();
  if (action) {
    const link = document.createElement("a");
    link.className = "toast-action";
    link.href = action.href;
    link.target = action.target || "_blank";
    link.rel = "noopener";
    link.textContent = action.label;
    link.addEventListener("click", () => dismissToast(toast));
    toast.querySelector(".toast-title").parentElement.append(link);
  }

  toast.querySelector(".toast-close").addEventListener("click", () => dismissToast(toast));
  const pause = () => clearTimeout(toast._timer);
  const resume = () => armToastTimer(toast, 2500);
  toast.addEventListener("pointerenter", pause);
  toast.addEventListener("pointerleave", resume);
  toast.addEventListener("focusin", pause);
  toast.addEventListener("focusout", resume);

  toasterEl.append(toast);
  const live = toasterEl.querySelectorAll(".toast:not(.is-leaving)");
  for (let i = 0; i < live.length - MAX_TOASTS; i++) dismissToast(live[i]);
  armToastTimer(toast, duration);
  return toast;
}
window.showToast = showToast;

// ============================================================================
// Reloj: el grande de la cara y el de la barra de la consola.
// ============================================================================

const ambientTimeEl = document.getElementById("ambientTime");
const ambientDateEl = document.getElementById("ambientDate");
const consoleClockEl = document.getElementById("clock");
const timeFormat = new Intl.DateTimeFormat("es-MX", { hour: "numeric", minute: "2-digit", hour12: false });
const dateFormat = new Intl.DateTimeFormat("es-MX", { weekday: "long", day: "numeric", month: "long" });

/** "jueves, 25 de septiembre" → "Jueves 25 de septiembre". */
function formatLongDate(date) {
  const text = dateFormat.format(date).replace(",", "");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
window.formatLongDate = formatLongDate;

let lastClockText = "";
function tickClock() {
  const now = new Date();
  const time = timeFormat.format(now);
  if (time === lastClockText) return;
  lastClockText = time;
  ambientTimeEl.textContent = time;
  ambientTimeEl.dateTime = now.toISOString();
  consoleClockEl.textContent = time;
  ambientDateEl.textContent = formatLongDate(now);
}
tickClock();
setInterval(tickClock, 1000);
