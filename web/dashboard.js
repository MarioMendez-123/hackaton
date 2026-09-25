/*
  La casa — la consola. Lee todo del mismo backend que sirve la página
  (mismo origen, sin CORS). Nunca inventa un estado: lo que no se sabe se
  dice "Sin verificar". Las únicas acciones son las que existen de verdad:
  cámara, búsqueda, calibración, protección, recordatorios, confirmar una
  caída, avisar al contacto y revisar un mensaje.

  `speak()` es la de lumina.js y `showToast()`/`switchToView()` las de
  app-shell.js: un solo motor de voz y un solo sistema de avisos.
*/

const OVERVIEW_MS = 3000;
const DETECTIONS_MS = 1500;
const CHANNELS_MS = 30000;
const AGENDA_MS = 60000;

const $ = (id) => document.getElementById(id);
const planEl = $("housePlan");

async function getJson(url) {
  const response = await fetch(url);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `error ${response.status}`);
  return body;
}

async function sendJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = new Error(body.detail || `error ${response.status}`);
    err.status = response.status;
    throw err;
  }
  return body;
}

/** Marca un botón como ocupado mientras corre `task`. */
async function withBusy(button, task) {
  button.setAttribute("aria-busy", "true");
  button.disabled = true;
  try {
    return await task();
  } finally {
    button.removeAttribute("aria-busy");
    button.disabled = false;
  }
}

// ============================================================================
// Estado de la casa: una sola petición (/home/overview) cada 3 s.
// ============================================================================

const SEVERITY_RANK = { normal: 0, warning: 1, critical: 2 };
const SEVERITY_DOT = { normal: "dot--calm", warning: "dot--warning", critical: "dot--critical" };
const SITUATION_ICON = {
  potential_kitchen_risk: "#i-flame",
  door_open_empty_house: "#i-door",
  door_open_while_armed: "#i-door",
};

let lastSituationKey = "normal";
let homeOnline = true;

async function refreshHome() {
  try {
    renderHome(await getJson("/home/overview?events=12"));
    homeOnline = true;
  } catch (err) {
    if (homeOnline) console.error("[casa] no se pudo leer el estado:", err);
    homeOnline = false;
    const detail = "No me puedo conectar con la casa. Sigo intentando.";
    $("summaryDetail").textContent = detail;
    $("houseChipDetail").textContent = detail;
  }
}
window.refreshHome = refreshHome;

const reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

/** Cambia el texto solo si cambió, con un fundido corto para que el cambio
 * de estado se note (sin movimiento: es texto que se está leyendo). */
function swapText(el, text) {
  if (el.textContent === text) return;
  const hadText = el.textContent !== "";
  el.textContent = text;
  if (!hadText || reduceMotionQuery.matches) return;
  el.animate([{ opacity: 0, filter: "blur(2px)" }, { opacity: 1, filter: "blur(0)" }], {
    duration: 250,
    easing: "cubic-bezier(0.23, 1, 0.32, 1)",
  });
}

function renderHome({ state, situation, summary, fall, events }) {
  document.documentElement.dataset.severity = situation.severity;

  swapText($("summaryHeadline"), summary.headline);
  swapText($("summaryDetail"), summary.detail);
  swapText($("houseChipHeadline"), summary.headline);
  swapText($("houseChipDetail"), summary.detail);
  $("houseChipDot").className = `dot ${SEVERITY_DOT[situation.severity] ?? "dot--calm"}`;

  const armed = state.home.security === "armed";
  $("protectionSwitch").setAttribute("aria-checked", String(armed));

  renderVitals(state, situation, armed);
  renderPlan(state, situation, armed, summary);
  renderAlerts(situation, summary);
  renderTimeline(events);
  renderFall(fall);
  announceIfNew(situation, summary);
}

/** Habla y avisa cuando empieza algo (o cambia a otra cosa), no en cada
 * consulta mientras sigue igual. Al volver a normal se rearma, así un
 * incidente nuevo más tarde se anuncia otra vez. */
function announceIfNew(situation, summary) {
  const key = situation.severity === "normal" ? "normal" : situation.situation;
  if (key === lastSituationKey) return;
  const escalated = SEVERITY_RANK[situation.severity] > 0;
  lastSituationKey = key;
  if (!escalated) return;

  const tone = situation.severity;
  if (situation.situation === "possible_fall") return; // lo pregunta renderFall, con su cuenta regresiva
  showToast({ title: summary.headline, body: summary.detail, tone });
  speak(`${summary.headline} ${summary.detail}`);
}

// ---- lecturas ----------------------------------------------------------------

const DOOR_TEXT = { open: "Abierta", closed: "Cerrada" };
const STOVE_TEXT = { on: "Encendida", off: "Apagada" };

/** Pinta una lectura; solo si de verdad cambió, entra con un fundido corto
 * (WAAPI: se reinicia sin forzar un reflow). Sin movimiento con "reducir
 * movimiento". */
function setVital(id, text, tone) {
  const el = $(id);
  if (tone) el.dataset.tone = tone;
  else delete el.dataset.tone;
  if (el.textContent === text) return;
  el.textContent = text;
  const from = reduceMotionQuery.matches ? { opacity: 0.3 } : { opacity: 0.3, transform: "translateY(4px)" };
  el.animate([from, { opacity: 1, transform: "none" }], { duration: 250, easing: "cubic-bezier(0.23, 1, 0.32, 1)" });
}

function renderVitals(state, situation, armed) {
  const { home, kitchen } = state;
  const doorAlert = situation.situation.startsWith("door_open");
  setVital(
    "vDoor",
    DOOR_TEXT[home.door] ?? "Sin verificar",
    home.door === "unknown" ? "unknown" : doorAlert ? situation.severity : null,
  );

  const someone = home.occupancy === "occupied" || kitchen.occupancy === "occupied";
  const nobody = home.occupancy === "empty" && kitchen.occupancy !== "occupied";
  setVital("vPeople", someone ? "Hay alguien" : nobody ? "Nadie" : "Sin verificar", someone || nobody ? null : "unknown");

  const kitchenAlert = situation.situation === "potential_kitchen_risk";
  setVital(
    "vStove",
    STOVE_TEXT[kitchen.stove] ?? "Sin verificar",
    kitchen.stove === "unknown" ? "unknown" : kitchenAlert ? situation.severity : null,
  );

  setVital(
    "vTemp",
    kitchen.temperature != null ? `${kitchen.temperature.toFixed(1)} °C` : "Sin lectura",
    kitchen.temperature != null ? (kitchenAlert ? situation.severity : null) : "unknown",
  );
  setVital("vArmed", armed ? "Activada" : "Desactivada", armed ? "calm" : null);
}

// ---- plano -------------------------------------------------------------------

function renderPlan(state, situation, armed, summary) {
  const { home, kitchen } = state;
  const d = planEl.dataset;
  d.door = home.door;
  d.stove = kitchen.stove;
  d.armed = String(armed);
  d.homePerson = String(home.occupancy === "occupied");
  d.kitchenPerson = String(kitchen.occupancy === "occupied");
  d.kitchen = situation.situation === "potential_kitchen_risk" ? situation.severity : "none";
  $("planTitle").textContent = `Plano de la casa. ${summary.detail}`;
}

// El plano se dibuja solo la primera vez que se abre la consola.
function drawPlanOnce() {
  if (!planEl.classList.contains("is-pending")) return;
  requestAnimationFrame(() => requestAnimationFrame(() => planEl.classList.remove("is-pending")));
}

// ---- avisos --------------------------------------------------------------------

function renderAlerts(situation, summary) {
  const isFall = situation.situation === "possible_fall";
  const isRisk = situation.severity !== "normal" && !isFall;

  $("riskSlot").classList.toggle("is-visible", isRisk);
  if (!isRisk) return;

  $("riskAlert").dataset.tone = situation.severity;
  $("riskIcon").setAttribute("href", SITUATION_ICON[situation.situation] ?? "#i-alert");
  $("riskTitle").textContent = summary.headline;
  $("riskBody").textContent = summary.detail;
  $("disarmFromAlertBtn").hidden = situation.situation !== "door_open_while_armed";
}

$("escalateBtn").addEventListener("click", (event) =>
  withBusy(event.currentTarget, async () => {
    try {
      await sendJson("/alerts/escalate");
      showToast({ title: "Aviso enviado", body: "Le mandé la alerta a tu contacto.", tone: "ok" });
    } catch (err) {
      showToast({ title: "No pude avisar", body: err.message, tone: "warning" });
    }
  }),
);

$("disarmFromAlertBtn").addEventListener("click", () => setProtection(false));

// ============================================================================
// "¿Estás bien?" tras una posible caída. El servidor lleva la cuenta (30 s) y
// avisa solo al contacto si nadie contesta — aunque esta página esté cerrada.
// Aquí se pregunta en voz alta, se muestra el reloj, se recuerda a la mitad y
// se reciben las respuestas: botones o voz (lumina.js llama respondToFall).
// ============================================================================

const FALL_POLL_MS = 1000; // con una caída abierta cada segundo cuenta
const FALL_PLACE = { kitchen: " en la cocina", livingroom: " en la sala", living_room: " en la sala", home: " en casa" };
const fallPromptEl = $("fallPrompt");
const fall = {
  status: null,
  location: null,
  deadline: 0,
  total: 30,
  reminded: false,
  spokeFor: null,
  ticker: null,
  // true mientras la respuesta (botón o voz) va al servidor: una consulta que
  // salió ANTES todavía dice "asking" y reabriría el aviso.
  answering: false,
};
let focusBeforeFall = null;
window.fallAlertState = { active: false, status: null };

let pollTimer = null;
let pollEvery = 0;
function schedulePoll(ms) {
  if (ms === pollEvery) return;
  pollEvery = ms;
  clearInterval(pollTimer);
  pollTimer = setInterval(refreshHome, ms);
}

function fallAlarm() {
  if (typeof playTone !== "function") return;
  playTone({ freqStart: 880, freqEnd: 660, duration: 0.28, gain: 0.09 });
  setTimeout(() => playTone({ freqStart: 880, freqEnd: 660, duration: 0.28, gain: 0.09 }), 380);
}

function face(expression) {
  if (typeof setFaceExpression === "function") setFaceExpression(expression);
}

function openFallPrompt() {
  if (!fallPromptEl.hidden) return;
  focusBeforeFall = document.activeElement;
  fallPromptEl.hidden = false;
  $("fallOkBtn").focus({ preventScroll: true });
}

function closeFallPrompt() {
  stopFallTicker();
  if (fallPromptEl.hidden) return;
  fallPromptEl.hidden = true;
  if (focusBeforeFall && document.contains(focusBeforeFall)) focusBeforeFall.focus({ preventScroll: true });
}

function tickFall() {
  const left = Math.max(0, Math.ceil((fall.deadline - Date.now()) / 1000));
  $("fallCount").textContent = String(left);
  $("fallRing").style.strokeDashoffset = String(1 - left / fall.total);
  if (left <= fall.total / 2 && left > 0 && !fall.reminded) {
    fall.reminded = true;
    speak(`¿Me escuchas? Si no me contestas, en ${left} segundos aviso a tu contacto.`);
  }
}

function startFallTicker() {
  stopFallTicker();
  tickFall();
  fall.ticker = setInterval(tickFall, 250);
}

function stopFallTicker() {
  clearInterval(fall.ticker);
  fall.ticker = null;
}

function showFallStep(status) {
  const where = FALL_PLACE[fall.location] ?? "";
  fallPromptEl.dataset.status = status;
  if (status === "asking") {
    $("fallTitle").textContent = "¿Estás bien?";
    $("fallBody").textContent = `Vi algo que parece una caída${where}. Si no me contestas, aviso a tu contacto.`;
    $("fallOkBtn").textContent = "Estoy bien";
  } else {
    $("fallTitle").textContent = status === "help" ? "Pediste ayuda" : "Ya avisé a tu contacto";
    $("fallBody").textContent =
      status === "help"
        ? "Le avisé a tu contacto. Aquí sigo contigo."
        : "Nadie contestó, así que le avisé a tu contacto. Cuando estés bien, dímelo.";
    $("fallOkBtn").textContent = "Ya estoy bien";
  }
  openFallPrompt();
}

/** Lo llama cada consulta de /home/overview con el estado de la caída. */
function renderFall(info) {
  if (fall.answering) return;
  const status = info?.active ? info.status : null;
  window.fallAlertState = { active: Boolean(status), status };
  if (status === "asking") {
    fall.deadline = Date.now() + info.seconds_left * 1000; // se re-sincroniza con el servidor
    fall.total = info.respond_seconds || fall.total;
  }
  if (status === fall.status) return;
  fall.status = status;
  fall.location = info?.location ?? fall.location;
  schedulePoll(status ? FALL_POLL_MS : OVERVIEW_MS);

  if (!status) {
    closeFallPrompt();
    fall.spokeFor = null;
    return;
  }
  showFallStep(status);
  if (status === "asking") {
    fall.reminded = false;
    startFallTicker();
    fallAlarm();
    face("sorprendido");
    speak(`¿Estás bien? Vi algo que parece una caída. Si no me contestas en ${info.seconds_left} segundos, aviso a tu contacto.`);
  } else {
    stopFallTicker();
    face("triste");
    if (fall.spokeFor !== status) {
      speak(
        status === "help"
          ? "Le avisé a tu contacto. Aquí sigo contigo."
          : "No me respondiste, así que ya le avisé a tu contacto. Aquí sigo contigo. Cuando estés bien, dime «estoy bien».",
      );
    }
  }
  fall.spokeFor = status;
}

/** Respuesta a "¿Estás bien?" (botones, o voz desde lumina.js). */
async function respondToFall(ok) {
  if (!window.fallAlertState.active) return false;
  if (!ok && fall.status === "help") {
    speak("Ya le avisé a tu contacto. Aquí sigo contigo.");
    return true;
  }
  if (ok) {
    fall.status = null;
    fall.spokeFor = null; // la próxima emergencia se anuncia completa
    window.fallAlertState = { active: false, status: null };
    closeFallPrompt();
    schedulePoll(OVERVIEW_MS);
    face("feliz");
    speak("Qué bueno. Descarté la alerta.", {
      onend: () => face(typeof restingExpression === "function" ? restingExpression() : "neutral"),
    });
  } else {
    fall.spokeFor = "help"; // ya se dice aquí; que el siguiente poll no lo repita
    fall.status = "help";
    window.fallAlertState = { active: true, status: "help" };
    stopFallTicker();
    showFallStep("help");
    face("triste");
    speak("Le estoy avisando a tu contacto. Aquí sigo contigo.");
  }
  fall.answering = true;
  try {
    await sendJson("/vision/fall/confirm", { ok });
  } catch {
    speak(ok ? "No pude cerrar la alerta. Toca «Estoy bien» otra vez." : "No pude avisar a tu contacto. Si puedes, llama al 911.");
  } finally {
    fall.answering = false;
  }
  refreshHome();
  return true;
}
window.respondToFall = respondToFall;

$("fallOkBtn").addEventListener("click", () => respondToFall(true));
$("fallHelpBtn").addEventListener("click", () => respondToFall(false));

// ---- protección --------------------------------------------------------------

async function setProtection(armed) {
  const switchEl = $("protectionSwitch");
  switchEl.setAttribute("aria-checked", String(armed)); // optimista; el poll corrige
  try {
    await sendJson("/home/protection", { armed });
    showToast(
      armed
        ? { title: "Protección activada", body: "Tienes 45 segundos para salir antes de que vigile la puerta.", tone: "ok" }
        : { title: "Protección desactivada", tone: "info" },
    );
  } catch (err) {
    switchEl.setAttribute("aria-checked", String(!armed));
    showToast({ title: "No pude cambiar la protección", body: err.message, tone: "warning" });
  }
  refreshHome();
}

$("protectionSwitch").addEventListener("click", (event) => {
  setProtection(event.currentTarget.getAttribute("aria-checked") !== "true");
});

// ---- lo que pasó -------------------------------------------------------------

const PLACE = { kitchen: "la cocina", home: "casa", living_room: "la sala", entrance: "la entrada" };
const place = (location) => PLACE[location] ?? location ?? "la casa";

const EVENT_VIEW = {
  stove_on: { icon: "i-flame", tone: "warning", text: () => "Se encendió la estufa" },
  stove_off: { icon: "i-flame", text: () => "Se apagó la estufa" },
  door_open: { icon: "i-door", text: () => "Se abrió la puerta" },
  door_closed: { icon: "i-door", text: () => "Se cerró la puerta" },
  motion: {
    icon: "i-person",
    text: (ev) => {
      const where = place(ev.location);
      if (ev.metadata?.person_present) return `Hay alguien en ${where}`;
      return ev.location === "home" ? "La casa se quedó sola" : `No hay nadie en ${where}`;
    },
  },
  temperature: { icon: "i-thermo", text: (ev) => `${ev.value} °C en ${place(ev.location)}` },
  smoke: { icon: "i-alert", tone: "critical", text: (ev) => `Humo, nivel ${ev.metadata?.level ?? "desconocido"}` },
  flame: { icon: "i-flame", tone: "critical", text: (ev) => `Flama, nivel ${ev.metadata?.level ?? "desconocido"}` },
  possible_fall: { icon: "i-fall", tone: "critical", text: () => "Posible caída" },
  object_detected: {
    icon: "i-search",
    tone: "ok",
    text: (ev) => `Encontré lo que buscabas: ${ev.metadata?.object ?? "un objeto"}`,
  },
};

const clockFormat = new Intl.DateTimeFormat("es-MX", { hour: "numeric", minute: "2-digit", hour12: false });

function relativeTime(iso) {
  const date = new Date(iso);
  const seconds = (Date.now() - date.getTime()) / 1000;
  if (seconds < 45) return "ahora";
  if (seconds < 3600) return `hace ${Math.round(seconds / 60)} min`;
  const sameDay = date.toDateString() === new Date().toDateString();
  return sameDay ? clockFormat.format(date) : `ayer ${clockFormat.format(date)}`;
}

const timelineItems = new Map(); // event_id -> <li>

function buildTimelineItem(ev) {
  const view = EVENT_VIEW[ev.type] ?? { icon: "i-info", text: () => ev.type };
  const li = document.createElement("li");
  li.className = "tl-item";
  if (view.tone) li.dataset.tone = view.tone;
  li.innerHTML =
    `<span class="tl-icon" aria-hidden="true"><svg class="icon"><use href="#${view.icon}"></use></svg></span>` +
    `<span class="tl-text"></span><time class="tl-time"></time>`;
  const text = view.text(ev) + (ev.source === "voice" ? " (por voz)" : "");
  li.querySelector(".tl-text").textContent = text;
  const time = li.querySelector(".tl-time");
  time.dateTime = ev.timestamp;
  time.title = new Date(ev.timestamp).toLocaleString("es-MX");
  return li;
}

/** Render con llave por evento: las filas existentes no se rehacen (no
 * parpadean); solo entran las nuevas, con su animación de entrada. */
function renderTimeline(events) {
  const list = $("timeline");
  const ids = new Set(events.map((ev) => ev.event_id));
  for (const [id, li] of timelineItems) {
    if (!ids.has(id)) {
      li.remove();
      timelineItems.delete(id);
    }
  }
  let previous = null;
  for (const ev of events) {
    let li = timelineItems.get(ev.event_id);
    if (!li) {
      li = buildTimelineItem(ev);
      timelineItems.set(ev.event_id, li);
    }
    const expected = previous ? previous.nextElementSibling : list.firstElementChild;
    if (li !== expected) list.insertBefore(li, expected);
    li.querySelector(".tl-time").textContent = relativeTime(ev.timestamp);
    previous = li;
  }
  $("timelineEmpty").hidden = events.length > 0;
}

// ============================================================================
// Cámara, búsqueda y calibración.
// ============================================================================

const cameraFrameEl = $("cameraFrame");
const cameraFeedEl = $("cameraFeed");
let cameraOn = false;
let detectionsTimer = null;

function setCameraUi(running) {
  cameraOn = running;
  $("cameraToggleBtn").textContent = running ? "Apagar" : "Encender";
  $("cameraPlaceholder").hidden = running;
  $("osdLive").hidden = !running;
  $("calibrateDoorBtn").disabled = !running;
  planEl.dataset.camera = running ? "on" : "off";
  cameraFeedEl.hidden = !running;
  if (running) {
    // cache-bust: conexión MJPEG nueva cada vez que se enciende
    if (!cameraFeedEl.src.includes("/vision/stream")) cameraFeedEl.src = `/vision/stream?_=${Date.now()}`;
  } else {
    cameraFeedEl.removeAttribute("src");
    $("osdSees").hidden = true;
  }
  syncDetectionsPoll();
}
// La cámara también se prende por voz ("Lumina, enciende la cámara").
window.setCameraUiFromVoice = setCameraUi;

cameraFeedEl.addEventListener("error", () => {
  if (!cameraOn) return;
  setCameraUi(false);
  showToast({ title: "Se perdió la señal de la cámara", body: "Vuelve a encenderla cuando quieras.", tone: "warning" });
});

async function toggleCamera(button) {
  await withBusy(button, async () => {
    try {
      const { running } = await sendJson(cameraOn ? "/vision/stop" : "/vision/start");
      setCameraUi(running);
    } catch (err) {
      showToast({ title: "No pude encender la cámara", body: err.message, tone: "warning" });
    }
  });
}

$("cameraToggleBtn").addEventListener("click", (event) => toggleCamera(event.currentTarget));
$("cameraEmptyBtn").addEventListener("click", (event) => toggleCamera(event.currentTarget));

$("calibrateDoorBtn").addEventListener("click", (event) =>
  withBusy(event.currentTarget, async () => {
    try {
      await sendJson("/vision/calibrate_door");
      showToast({ title: "Puerta calibrada", body: "Tomé esta imagen como la puerta cerrada.", tone: "ok" });
    } catch (err) {
      showToast({ title: "No pude calibrar la puerta", body: err.message, tone: "warning" });
    }
  }),
);

// "Veo: persona, taza" — solo con la cámara encendida, la consola a la vista
// y la pestaña visible; si no, no tiene sentido preguntar.
function syncDetectionsPoll() {
  const shouldPoll = cameraOn && !document.hidden && document.documentElement.dataset.view === "dashboard";
  if (shouldPoll && detectionsTimer === null) {
    refreshDetections();
    detectionsTimer = setInterval(refreshDetections, DETECTIONS_MS);
  } else if (!shouldPoll && detectionsTimer !== null) {
    clearInterval(detectionsTimer);
    detectionsTimer = null;
  }
}

async function refreshDetections() {
  try {
    const { running, detections } = await getJson("/vision/detections");
    const labels = [...new Set(detections.map((d) => d.label))];
    const sees = $("osdSees");
    sees.hidden = !running || labels.length === 0;
    sees.textContent = `Veo: ${labels.slice(0, 4).join(", ")}`;
  } catch {
    // transitorio: el siguiente intento lo corrige
  }
}

document.addEventListener("visibilitychange", syncDetectionsPoll);

// ---- búsqueda ------------------------------------------------------------------

const searchStatusEl = $("searchStatus");
let searchPollTimer = null;
let foundTimer = null;

function setSearchStatus(text, tone) {
  searchStatusEl.textContent = text;
  if (tone) searchStatusEl.dataset.tone = tone;
  else delete searchStatusEl.dataset.tone;
}

function stopSearchPoll() {
  clearInterval(searchPollTimer);
  searchPollTimer = null;
}

/** Modo búsqueda en tres lugares a la vez: Lumina deja de contestar lo que
 * no sea un comando (lumina.js), la cámara muestra el encuadre y el barrido,
 * y el formulario ofrece cancelar. */
function setSearchUiActive(objectName) {
  const active = Boolean(objectName);
  cameraFrameEl.classList.toggle("is-scanning", active);
  $("osdSearch").hidden = !active;
  if (active) $("osdSearch").textContent = `Buscando: ${objectName}`;
  $("cancelSearchBtn").hidden = !active;
  if (typeof window.setSearchMode === "function") window.setSearchMode(active);
}

/** Punto único de "buscar objeto": lo usan el formulario, los chips y el
 * comando de voz "Lumina, busca X". Enciende la cámara sola si hace falta. */
async function runObjectSearch(objectName) {
  stopSearchPoll();
  clearTimeout(foundTimer);
  cameraFrameEl.classList.remove("is-found");

  if (!cameraOn) {
    setSearchStatus("Encendiendo la cámara…");
    try {
      const { running } = await sendJson("/vision/start");
      setCameraUi(running);
    } catch (err) {
      setSearchStatus(`No pude encender la cámara: ${err.message}`, "warning");
      speak(`No pude encender la cámara: ${err.message}`);
      return;
    }
  }

  try {
    await sendJson("/vision/find", { object: objectName });
  } catch (err) {
    setSearchStatus(err.message, "warning");
    speak(`No sé buscar ${objectName} con la cámara.`);
    return;
  }
  setSearchStatus(`Buscando ${objectName} frente a la cámara…`);
  setSearchUiActive(objectName);
  searchPollTimer = setInterval(() => pollSearchStatus(objectName), 1000);
}
window.startCameraObjectSearch = runObjectSearch;

async function pollSearchStatus(objectName) {
  let result;
  try {
    result = await getJson("/vision/find/status");
  } catch {
    return;
  }
  if (result.status === "searching") return;

  stopSearchPoll();
  setSearchUiActive(null);
  if (result.status === "found") {
    const where = place(result.location);
    setSearchStatus(`Encontré ${objectName} en ${where}.`, "ok");
    cameraFrameEl.classList.add("is-found");
    foundTimer = setTimeout(() => cameraFrameEl.classList.remove("is-found"), 2400);
    showToast({ title: `Encontré ${objectName}`, body: `Está en ${where}, marcado en la cámara.`, tone: "ok" });
    speak(`Encontré tu ${objectName}. Está en ${where}.`);
    refreshHome();
  } else if (result.status === "idle") {
    setSearchStatus("Búsqueda cancelada.");
  } else {
    setSearchStatus(`No encontré ${objectName} frente a la cámara.`, "warning");
    speak(`No encontré tu ${objectName} con la cámara.`);
  }
}

window.cancelCameraObjectSearch = async function cancelCameraObjectSearch() {
  stopSearchPoll();
  setSearchUiActive(null);
  setSearchStatus("Búsqueda cancelada.");
  try {
    await sendJson("/vision/find/cancel");
  } catch (err) {
    console.error("[casa] no se pudo cancelar la búsqueda:", err);
  }
};

$("searchForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const objectName = $("searchInput").value.trim();
  if (objectName) runObjectSearch(objectName);
  else $("searchInput").focus();
});

$("cancelSearchBtn").addEventListener("click", () => window.cancelCameraObjectSearch());

async function loadObjectChips() {
  try {
    const objects = await getJson("/vision/objects");
    const list = $("objectChips");
    list.textContent = "";
    for (const name of objects) {
      const li = document.createElement("li");
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.textContent = name;
      chip.addEventListener("click", () => {
        $("searchInput").value = name;
        runObjectSearch(name);
      });
      li.append(chip);
      list.append(li);
    }
  } catch (err) {
    console.error("[casa] no se pudieron leer los objetos buscables:", err);
  }
}

// ============================================================================
// Hoy: agenda de Google Calendar + recordatorios.
// ============================================================================

const TRIGGER_TAG = { leave: "Al salir", arrive: "Al llegar" };
// true si el Apps Script está configurado: los eventos se crean solos.
let calendarCanWrite = false;

async function refreshAgenda() {
  $("todayDate").textContent = formatLongDate(new Date());
  const list = $("agendaList");
  const empty = $("agendaEmpty");
  try {
    const { configured, events, open_url: openUrl, can_write: canWrite } = await getJson("/calendar");
    // Abre en la cuenta dueña del calendario (la usa también la voz).
    if (openUrl) $("openCalendarLink").href = openUrl;
    calendarCanWrite = Boolean(canWrite);
    list.textContent = "";
    if (!configured) {
      empty.textContent = "Conecta tu Google Calendar para ver tu día aquí.";
    } else if (events.length === 0) {
      empty.textContent = "No tienes nada en el calendario hoy.";
    }
    empty.hidden = configured && events.length > 0;
    const now = new Date();
    for (const ev of events) {
      const allDay = ev.start.length === 10;
      const starts = new Date(ev.start);
      const li = document.createElement("li");
      li.className = "agenda-item";
      if (!allDay && starts < now) li.classList.add("is-past");
      const time = document.createElement("time");
      time.className = "agenda-time";
      time.dateTime = ev.start;
      time.textContent = allDay ? "Todo el día" : clockFormat.format(starts);
      const text = document.createElement("span");
      text.textContent = ev.summary;
      li.append(time, text);
      list.append(li);
    }
  } catch (err) {
    list.textContent = "";
    empty.hidden = false;
    empty.textContent = "No pude leer tu calendario. Vuelvo a intentar en un minuto.";
    console.error("[casa] calendario:", err);
  }
}

/** Lleva la vista al panel "Hoy" y lo resalta un momento (lo usa la voz:
 * "Lumina, abre mi agenda"). Espera a que la consola ya esté a la vista. */
window.spotlightAgenda = function spotlightAgenda() {
  const panel = $("todayTitle").closest(".panel");
  const run = () => {
    refreshAgenda();
    requestAnimationFrame(() => {
      panel.scrollIntoView({ block: "start", behavior: reduceMotionQuery.matches ? "auto" : "smooth" });
      panel.classList.add("is-spotlight");
      setTimeout(() => panel.classList.remove("is-spotlight"), 1600);
    });
  };
  if (document.documentElement.dataset.view === "dashboard") run();
  else document.addEventListener("viewchange", run, { once: true });
};

// Agendar desde la consola: el mismo endpoint que la voz. Aquí sí hay un
// clic, así que el navegador deja abrir Google Calendar sin bloquearlo.
$("eventForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("eventInput");
  const text = input.value.trim();
  if (!text) return;
  const status = $("eventStatus");
  const button = event.currentTarget.querySelector("button[type=submit]");
  // Sin el Apps Script hay que abrir Google Calendar: se abre YA, dentro del
  // clic (después del await el navegador lo bloquearía) y luego se le pone
  // la dirección del evento. Con el script no hace falta ninguna pestaña.
  const calendarTab = calendarCanWrite ? null : window.open("", "google-calendar");
  status.textContent = "Agendando… Google tarda unos segundos en contestar.";
  delete status.dataset.tone;
  await withBusy(button, async () => {
    try {
      const result = await sendJson("/calendar/events", { text });
      input.value = "";
      if (result.unconfirmed) {
        calendarTab?.close();
        status.textContent = `No pude confirmar si ${result.event.title} quedó guardado. Revisa tu calendario antes de agendarlo otra vez.`;
        status.dataset.tone = "warning";
      } else if (result.created) {
        calendarTab?.close();
        status.textContent = "";
        showToast({ title: "Agendado en Google Calendar", body: result.event.title, tone: "ok" });
        refreshAgenda();
      } else {
        if (calendarTab) calendarTab.location.href = result.open_url;
        status.textContent = `Listo para guardar: ${result.event.title}. Toca «Guardar» en Google Calendar.`;
        delete status.dataset.tone;
      }
    } catch (err) {
      calendarTab?.close();
      status.textContent = err.message;
      status.dataset.tone = "warning";
    }
  });
});

const reminderItems = new Map(); // id -> <li>

function buildReminderItem(reminder) {
  const li = document.createElement("li");
  li.className = "reminder";
  li.innerHTML =
    `<div class="reminder-inner">` +
    `<button type="button" class="reminder-check"><span class="reminder-check-box">` +
    `<svg class="icon" aria-hidden="true"><use href="#i-check"></use></svg></span></button>` +
    `<span class="reminder-text"></span></div>`;
  li.querySelector(".reminder-text").textContent = reminder.text;
  const check = li.querySelector(".reminder-check");
  check.setAttribute("aria-label", `Marcar como hecho: ${reminder.text}`);
  if (TRIGGER_TAG[reminder.trigger]) {
    const tag = document.createElement("span");
    tag.className = "reminder-tag";
    tag.textContent = TRIGGER_TAG[reminder.trigger];
    li.querySelector(".reminder-inner").append(tag);
  }
  check.addEventListener("click", () => completeReminder(reminder.id, li));
  return li;
}

async function refreshReminders() {
  try {
    const items = await getJson("/reminders");
    const list = $("reminderList");
    const ids = new Set(items.map((r) => r.id));
    for (const [id, li] of reminderItems) {
      if (!ids.has(id) && !li.classList.contains("is-done")) {
        li.remove();
        reminderItems.delete(id);
      }
    }
    for (const reminder of items) {
      if (reminderItems.has(reminder.id)) continue;
      const li = buildReminderItem(reminder);
      reminderItems.set(reminder.id, li);
      list.append(li);
    }
    $("reminderEmpty").hidden = items.length > 0;
  } catch (err) {
    console.error("[casa] recordatorios:", err);
  }
}
window.refreshReminders = refreshReminders;

async function completeReminder(id, li) {
  li.classList.add("is-done");
  li.querySelector(".reminder-check").disabled = true;
  try {
    await sendJson(`/reminders/${id}/done`);
  } catch (err) {
    li.classList.remove("is-done");
    li.querySelector(".reminder-check").disabled = false;
    showToast({ title: "No pude marcarlo como hecho", body: err.message, tone: "warning" });
    return;
  }
  // Se deja ver la palomita un momento antes de cerrar la fila.
  setTimeout(() => {
    li.remove();
    reminderItems.delete(id);
    $("reminderEmpty").hidden = reminderItems.size > 0;
  }, 450);
}

$("reminderForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("reminderInput");
  const text = input.value.trim();
  if (!text) return;
  const button = event.currentTarget.querySelector("button[type=submit]");
  await withBusy(button, async () => {
    try {
      await sendJson("/reminders", { text, trigger: $("reminderTrigger").value });
      input.value = "";
      refreshReminders();
    } catch (err) {
      showToast({ title: "No pude guardar el recordatorio", body: err.message, tone: "warning" });
    }
  });
  input.focus();
});

// ============================================================================
// Revisar un mensaje (sección 3.9). Nunca afirma que ES una estafa: solo
// lista las señales que encontró backend/fraud_detector.py.
// ============================================================================

const RISK_LEVEL_LABEL = { bajo: "Riesgo bajo", medio: "Riesgo medio", alto: "Riesgo alto" };

$("fraudForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = $("fraudInput").value.trim();
  if (!text) return;
  const button = event.currentTarget.querySelector("button[type=submit]");

  let result;
  try {
    result = await withBusy(button, () => sendJson("/messages/analyze", { text }));
  } catch (err) {
    showToast({ title: "No pude revisar el mensaje", body: err.message, tone: "warning" });
    return;
  }

  const resultEl = $("fraudResult");
  resultEl.hidden = true; // reinicia la entrada si ya estaba visible
  resultEl.dataset.level = result.risk_level;
  $("fraudLevel").textContent = RISK_LEVEL_LABEL[result.risk_level] ?? result.risk_level;
  const signals = $("fraudSignals");
  signals.textContent = "";
  const lines = result.signals_found.length ? result.signals_found : ["No encontré señales conocidas de engaño."];
  for (const line of lines) {
    const li = document.createElement("li");
    li.textContent = line;
    signals.append(li);
  }
  $("fraudNote").textContent = result.note;
  resultEl.hidden = false;
});

// ============================================================================
// Cómo te aviso: qué canales están conectados de verdad.
// ============================================================================

const CHANNELS = [
  { key: "camera", name: "Cámara", desc: "Vigila la puerta y la cocina, busca objetos", on: "Encendida", off: "Apagada" },
  { key: "calendar", name: "Google Calendar", desc: "Tu agenda del día, en voz" },
  { key: "contacts", name: "Contacto de emergencia", desc: "A quién aviso si algo pasa" },
  { key: "whatsapp", name: "WhatsApp", desc: "Mensajes de alerta" },
  { key: "telegram", name: "Telegram", desc: "Mensajes de alerta" },
  { key: "calls", name: "Llamadas", desc: "Llamo si algo es crítico" },
  { key: "n8n", name: "n8n", desc: "Manda cada alerta a tus flujos" },
  { key: "elevenlabs", name: "Voz natural", desc: "ElevenLabs. Sin ella hablo con la voz del navegador" },
];

async function refreshChannels() {
  let status;
  try {
    status = await getJson("/integrations/status");
  } catch (err) {
    console.error("[casa] canales:", err);
    return;
  }
  const list = $("channelList");
  list.textContent = "";
  for (const channel of CHANNELS) {
    const on = Boolean(status[channel.key]);
    const li = document.createElement("li");
    li.className = "channel";
    li.innerHTML =
      `<div><p class="channel-name"></p><p class="channel-desc"></p></div>` +
      `<span class="channel-status" data-on="${on}"><span class="dot ${on ? "dot--ok" : ""}" aria-hidden="true"></span><span></span></span>`;
    li.querySelector(".channel-name").textContent = channel.name;
    li.querySelector(".channel-desc").textContent = channel.desc;
    li.querySelector(".channel-status span:last-child").textContent = on
      ? (channel.on ?? "Conectado")
      : (channel.off ?? "Sin configurar");
    list.append(li);
  }
}

async function loadContact() {
  try {
    const contacts = await getJson("/contacts");
    if (contacts.length) setVital("vContact", contacts[0].name, null);
  } catch (err) {
    console.error("[casa] contactos:", err);
  }
}

// ============================================================================
// Arranque.
// ============================================================================

document.addEventListener("viewchange", (event) => {
  if (event.detail.view === "dashboard") drawPlanOnce();
  syncDetectionsPoll();
});
if (document.documentElement.dataset.view === "dashboard") drawPlanOnce();

refreshHome();
schedulePoll(OVERVIEW_MS);

getJson("/vision/status")
  .then(({ running }) => setCameraUi(running))
  .catch((err) => console.error("[casa] cámara:", err));

loadObjectChips();
loadContact();
refreshReminders();
refreshAgenda();
setInterval(refreshAgenda, AGENDA_MS);
refreshChannels();
setInterval(refreshChannels, CHANNELS_MS);
