/**
 * Lumina — cara animada + voz + conversación con un LLM local.
 *
 * Todo el archivo es el frontend del agente. Flujo:
 *   pantalla negra ── oír "Lumina" (o botón invisible arriba a la izquierda)
 *   ──► animación de encendido ──► Modo Conversación: el micrófono escucha,
 *   cada frase va a POST /lumina/ask (ver ../lumina.py), la respuesta se dice
 *   en voz alta con speechSynthesis y la cara reacciona.
 *
 * CONFIGURACIÓN (opcional, antes de cargar este script):
 *   <script>window.LUMINA_ASK_URL = "https://mi-servidor/lumina/ask";</script>
 *   <script>window.LUMINA_SPEAK_URL = "https://mi-servidor/lumina/speak";</script>
 *
 * VOZ: speak() intenta primero POST LUMINA_SPEAK_URL (ElevenLabs, ver
 * lumina.py) y si no está configurado (501) o falla, cae sola a
 * speechSynthesis del navegador — nunca corta la conversación por esto.
 *
 * COMANDOS DE CONSOLA
 *   setFaceExpression('feliz')   // inactivo neutral feliz confundido sorprendido
 *                                // pensando triste error escuchando activando
 *   askLumina('¿qué hora es?')   // manda una pregunta sin hablar
 *   localStorage.setItem('lumina_voice_override', 'jorge')  // fuerza una voz
 *   localStorage.removeItem('lumina_voice_override')        // vuelve a automática
 *
 * COMANDOS DE VOZ ("Lumina, ..."), en el orden en que se evalúan (ver
 * handleVoiceCommand):
 *   "analiza este mensaje: <texto>"   detector de fraude/extorsión (3.9)
 *   "recuérdame <algo> [cuando salga | cuando llegue]"   recordatorio
 *   "¿qué pendientes tengo?"          lee los recordatorios
 *   "busca <objeto>" / "cancela"      búsqueda con la cámara (modo búsqueda:
 *                                     mientras busca, nada más va al LLM)
 *   "activa / desactiva la protección"   solo arma/desarma
 *   "salgo de casa" / "ya llegué"     salida y llegada completas (3.4/3.5):
 *                                     arma/desarma, revisa riesgos, lee
 *                                     pendientes y agenda
 *   "¿cómo está la casa?"             resumen en una frase
 *   "enciende / apaga la cámara", "calibra la puerta"
 *   "avisa a mi contacto"             manda la alerta activa por los canales
 *   "muéstrame la casa" / "vuelve"    cambia de vista
 *   "feliz", "triste", "presentación"...   expresiones de prueba
 * Lo que no es comando va al LLM (/lumina/ask), que también responde la
 * agenda ("¿qué tengo hoy?") y dónde quedó un objeto.
 *
 * HONESTIDAD (no describir esto de otra forma frente a terceros):
 *  - Las expresiones son estados visuales predefinidos; no hay ningún modelo
 *    que "sienta" nada. setFaceExpression() es el único gancho si algún día
 *    otro modelo decide la expresión.
 *  - La boca NO es un analizador de audio: speechSynthesis no se puede
 *    conectar a un AnalyserNode. Es una animación procedural con un empujón
 *    real en cada evento onboundary del motor de voz.
 *  - No se puede clonar la voz de un personaje (Jarvis, etc.): solo se elige
 *    la mejor voz en español instalada en el navegador/sistema.
 *  - El reconocimiento de voz es la Web Speech API del navegador (Chrome/Edge).
 *  - Los sonidos se generan con osciladores Web Audio; no hay archivos de audio.
 */

const ASK_URL = window.LUMINA_ASK_URL || "/lumina/ask";
const SPEAK_URL = window.LUMINA_SPEAK_URL || "/lumina/speak";
const VOICE_OVERRIDE_KEY = "lumina_voice_override";

// 'boot' (pantalla negra) | 'conversation'
let mode = "boot";
// 'listening' | 'thinking' | 'speaking' — solo se mandan preguntas nuevas al
// LLM cuando es 'listening', para no pisar una pregunta en curso.
let conversationSubState = "listening";
let presentationModeActive = false;

const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
// false si no hay Web Speech API o se denegó el micrófono: mostrar
// 'escuchando' sin eso mentiría (ver restingExpression).
let voiceAvailable = !!SpeechRecognitionImpl;

let recognition = null;
let shouldKeepListening = true;
// true mientras el reconocimiento está apagado A PROPÓSITO porque Lumina habla.
let recognitionPausedForSpeech = false;

/** Apaga el micrófono justo antes de hablar. Bug real: seguía activo mientras
 * sonaba la respuesta, se transcribía a sí misma como pregunta nueva ("eco") y
 * disparaba una segunda respuesta que cortaba la primera. Se reinicia SOLO en
 * resumeRecognitionAfterSpeech(). */
function pauseRecognitionForSpeech() {
  if (!recognition) return;
  recognitionPausedForSpeech = true;
  try {
    recognition.stop();
  } catch {
    // ya estaba detenido
  }
}

function resumeRecognitionAfterSpeech() {
  if (!recognition) return;
  recognitionPausedForSpeech = false;
  if (!shouldKeepListening) return; // permiso denegado u otro error fatal
  try {
    recognition.start();
  } catch {
    // ya estaba corriendo (carrera esperada con el "end" del stop())
  }
}

// ============================================================================
// Motor de expresiones de la cara
// ============================================================================

// Coordenadas dentro del viewBox 0 0 1000 600 de index.html.
const EYE_L = { x: 270, y: 235 };
const EYE_R = { x: 730, y: 235 };

/** `d` de un ojo según su forma — parametrizado para que una expresión nueva
 * sea una fila de EXPRESSIONS y no un path nuevo dibujado a mano. */
function eyePath(shape, cx, cy) {
  switch (shape) {
    case "closed":
      return `M ${cx - 62} ${cy} L ${cx + 62} ${cy}`;
    case "happy": // "^"
      return `M ${cx - 64} ${cy + 18} Q ${cx} ${cy - 62} ${cx + 64} ${cy + 18}`;
    case "sad":
      return `M ${cx - 64} ${cy - 26} Q ${cx} ${cy + 46} ${cx + 64} ${cy - 26}`;
    case "wide": // sorpresa
      return circlePath(cx, cy, 94);
    case "squint": // confundido
      return `M ${cx - 64} ${cy} Q ${cx} ${cy - 28} ${cx + 64} ${cy} Q ${cx} ${cy + 28} ${cx - 64} ${cy} Z`;
    case "arc": // "pensando": 270° con hueco de 90° para leerse como spinner
      return arcPath(cx, cy, 68, 270);
    case "x": // error
      return `M ${cx - 48} ${cy - 48} L ${cx + 48} ${cy + 48} M ${cx - 48} ${cy + 48} L ${cx + 48} ${cy - 48}`;
    case "open":
    default:
      // Cápsula/visor: se lee como visor sci-fi, no como ojo de muñeca.
      return capsulePath(cx, cy, 104, 46);
  }
}

function circlePath(cx, cy, r) {
  return `M ${cx - r} ${cy} a ${r} ${r} 0 1 0 ${r * 2} 0 a ${r} ${r} 0 1 0 ${-r * 2} 0`;
}

/** Cápsula horizontal; hw/hh = medio-ancho y medio-alto totales. */
function capsulePath(cx, cy, hw, hh) {
  const left = cx - hw + hh;
  const right = cx + hw - hh;
  const top = cy - hh;
  const bottom = cy + hh;
  return (
    `M ${left} ${top} L ${right} ${top} ` +
    `A ${hh} ${hh} 0 0 1 ${right} ${bottom} ` +
    `L ${left} ${bottom} ` +
    `A ${hh} ${hh} 0 0 1 ${left} ${top} Z`
  );
}

/** Arco parcial desde arriba (-90°) en sentido horario. */
function arcPath(cx, cy, r, sweepDeg) {
  const startDeg = -90;
  const endDeg = startDeg + sweepDeg;
  const toRad = (d) => (d * Math.PI) / 180;
  const sx = (cx + r * Math.cos(toRad(startDeg))).toFixed(1);
  const sy = (cy + r * Math.sin(toRad(startDeg))).toFixed(1);
  const ex = (cx + r * Math.cos(toRad(endDeg))).toFixed(1);
  const ey = (cy + r * Math.sin(toRad(endDeg))).toFixed(1);
  const largeArc = sweepDeg > 180 ? 1 : 0;
  return `M ${sx} ${sy} A ${r} ${r} 0 ${largeArc} 1 ${ex} ${ey}`;
}

/** Ceja: "raised" (sorpresa/confusión) o "sad" (caída hacia el centro). */
function browPath(shape, cx, cy) {
  const y = cy - 132;
  if (shape === "sad") return `M ${cx - 72} ${y + 28} L ${cx + 72} ${y - 18}`;
  return `M ${cx - 72} ${y} L ${cx + 72} ${y - 36}`;
}

/** Boca de reposo: ancho fijo, altura del arco según el tipo. */
function mouthPath(shape) {
  const cx = 500;
  const y = 460;
  const w = 190;
  switch (shape) {
    case "smile":
      return `M ${cx - w} ${y} Q ${cx} ${y + 145} ${cx + w} ${y}`;
    case "frown":
      return `M ${cx - w} ${y + 80} Q ${cx} ${y - 68} ${cx + w} ${y + 80}`;
    case "o":
      return circlePath(cx, y + 28, 62);
    case "zigzag": // confundido
      return `M ${cx - w} ${y} L ${cx - w / 2} ${y + 70} L ${cx} ${y} L ${cx + w / 2} ${y + 70} L ${cx + w} ${y}`;
    case "flat":
    default:
      return `M ${cx - w} ${y} L ${cx + w} ${y}`;
  }
}

/** Las 10 expresiones: 3 funcionales (inactivo, escuchando, activando) + 7
 * emocionales. Cada una es declarativa: forma de ojo/ceja/boca, pupila, color
 * de acento y animaciones especiales. Agregar una = agregar una fila aquí.
 *   idleBlink: parpadea solo de vez en cuando
 *   gazeDrift: la pupila deriva sola (solo en reposo prolongado; se omite en
 *              las que ya tienen un gesto propio)
 */
const EXPRESSIONS = {
  inactivo: { eye: "open", mouth: "flat", pupil: true, accent: "accent", idleBlink: true, gazeDrift: true },
  neutral: { eye: "open", mouth: "flat", pupil: true, accent: "accent", gazeDrift: true },
  feliz: { eye: "happy", mouth: "smile", pupil: false, accent: "positive" },
  confundido: {
    eye: "squint",
    eyeR: "open",
    mouth: "zigzag",
    pupil: true,
    browL: "raised",
    accent: "warn",
    tilt: true,
  },
  sorprendido: {
    eye: "wide",
    mouth: "o",
    pupil: true,
    browL: "raised",
    browR: "raised",
    accent: "accent",
  },
  pensando: { eye: "arc", eyeSpin: true, mouth: "flat", pupil: false, accent: "accent", dots: true },
  triste: { eye: "sad", mouth: "frown", pupil: false, browL: "sad", browR: "sad", accent: "muted" },
  error: { eye: "x", mouth: "flat", pupil: false, accent: "warn", pulse: true },
  // Estado de reposo real de Modo Conversación: necesita sentirse vivo.
  escuchando: {
    eye: "open",
    mouth: "smile",
    pupil: true,
    accent: "accent",
    ring: true,
    idleBlink: true,
    gazeDrift: true,
  },
  activando: { eye: "wide", mouth: "o", pupil: true, accent: "positive", pulse: true },
};

const ACCENT_VAR = {
  accent: "--accent",
  positive: "--positive",
  warn: "--warn",
  muted: "--text-muted",
};

const faceScreenEl = document.getElementById("face-screen");
const faceSvg = document.getElementById("face-svg");
const eyeLeftEl = document.getElementById("eye-left");
const eyeRightEl = document.getElementById("eye-right");
const browLeftEl = document.getElementById("brow-left");
const browRightEl = document.getElementById("brow-right");
const pupilLeftEl = document.getElementById("pupil-left");
const pupilRightEl = document.getElementById("pupil-right");
const mouthEl = document.getElementById("face-mouth");
const thinkingDotsEl = document.getElementById("thinking-dots");
const listeningGlowEls = ["listening-ring", "listening-ring-2", "listening-ring-3"].map((id) =>
  document.getElementById(id),
);
const faceStageEl = document.getElementById("face-stage");
const statusIndicatorEl = document.getElementById("status-indicator");
const waveformEl = document.getElementById("waveform");
const waveformBarEls = Array.from(document.querySelectorAll(".waveform-bar"));

let currentExpression = null;
let idleBlinkTimer = null;

function applyExpression(cfg) {
  eyeLeftEl.setAttribute("d", eyePath(cfg.eyeL || cfg.eye, EYE_L.x, EYE_L.y));
  eyeRightEl.setAttribute("d", eyePath(cfg.eyeR || cfg.eye, EYE_R.x, EYE_R.y));

  // 'pensando' gira por CSS: se limpia el transform inline del parpadeo para
  // que no compitan por la misma propiedad.
  eyeLeftEl.classList.toggle("face-eye--spin", !!cfg.eyeSpin);
  eyeRightEl.classList.toggle("face-eye--spin", !!cfg.eyeSpin);
  if (cfg.eyeSpin) {
    eyeLeftEl.style.transform = "";
    eyeRightEl.style.transform = "";
  }

  browLeftEl.classList.toggle("face-brow--visible", !!cfg.browL);
  browRightEl.classList.toggle("face-brow--visible", !!cfg.browR);
  if (cfg.browL) browLeftEl.setAttribute("d", browPath(cfg.browL, EYE_L.x, EYE_L.y));
  if (cfg.browR) browRightEl.setAttribute("d", browPath(cfg.browR, EYE_R.x, EYE_R.y));

  mouthEl.setAttribute("d", mouthPath(cfg.mouth));

  // cx/cy y visibilidad de las pupilas las gobierna livelinessFrame; aquí solo
  // se fija el OBJETIVO y se limpia la deriva de la expresión anterior.
  gazeBaseOffset = cfg.pupilOffset || { dx: 0, dy: 0 };
  gazeDriftOffset = { dx: 0, dy: 0 };

  thinkingDotsEl.classList.toggle("face-dots--visible", !!cfg.dots);
  listeningGlowEls.forEach((el) => el.classList.toggle("face-glow--active", !!cfg.ring));
  faceSvg.classList.toggle("face--pulse", !!cfg.pulse);
  faceSvg.classList.toggle("face--tilt", !!cfg.tilt);

  // En #face-screen: lo heredan tanto el SVG como .face-ambient.
  const varName = ACCENT_VAR[cfg.accent] || ACCENT_VAR.accent;
  faceScreenEl.style.setProperty("--face-accent", `var(${varName})`);
}

/** Mueve eyeOpennessTarget entre 0 y 1; livelinessFrame anima scaleY hacia él
 * (cierre rápido, apertura más lenta). Parpadeo variado a propósito: cuánto
 * se queda cerrado cambia, y el 15% de las veces es doble. */
function triggerBlink() {
  const name = currentExpression;
  const cfg = EXPRESSIONS[name];
  if (!cfg || !cfg.idleBlink) return;

  const holdClosedMs = 90 + Math.random() * 70;
  const isDoubleBlink = Math.random() < 0.15;

  eyeOpennessTarget = 0;
  setTimeout(() => {
    if (currentExpression !== name) return;
    eyeOpennessTarget = 1;
    if (isDoubleBlink) {
      setTimeout(() => {
        if (currentExpression !== name) return;
        eyeOpennessTarget = 0;
        setTimeout(() => {
          if (currentExpression === name) eyeOpennessTarget = 1;
        }, holdClosedMs);
      }, 100);
    }
  }, holdClosedMs);
}

/** Siguiente parpadeo a intervalo aleatorio (recursivo, no setInterval fijo);
 * se detiene solo cuando la expresión activa ya no tiene idleBlink. */
function scheduleNextBlink() {
  clearTimeout(idleBlinkTimer);
  const cfg = EXPRESSIONS[currentExpression];
  if (!cfg || !cfg.idleBlink) return;
  idleBlinkTimer = setTimeout(
    () => {
      triggerBlink();
      scheduleNextBlink();
    },
    2500 + Math.random() * 3500,
  );
}

// ---- Deriva de mirada: vistazo ocasional, lento (1.5–3.5s) y de poca
// amplitud — uno constante o brusco marea si alguien lo ve fijo minutos.
let gazeDriftTimer = null;
let gazeBaseOffset = { dx: 0, dy: 0 };
let gazeDriftOffset = { dx: 0, dy: 0 };
let pupilCurrent = { dx: 0, dy: 0 };

function scheduleNextGazeDrift() {
  clearTimeout(gazeDriftTimer);
  gazeDriftTimer = setTimeout(
    () => {
      if (EXPRESSIONS[currentExpression]?.gazeDrift) {
        gazeDriftOffset = {
          dx: Math.round((Math.random() - 0.5) * 40),
          dy: Math.round((Math.random() - 0.5) * 28),
        };
      }
      scheduleNextGazeDrift();
    },
    1500 + Math.random() * 2000,
  );
}

// ============================================================================
// ANIMACIÓN CONTINUA (un solo requestAnimationFrame): boca reactiva a la voz,
// parpadeo asimétrico y glow dinámico, todo con easing
// (current += (target - current) * factor) en vez de saltos.
//
// La boca es una aproximación procedural (ver HONESTIDAD arriba): 3 "bandas"
// que se re-sortean solas mientras se habla, más un empujón real por cada
// onboundary de la síntesis.
// ============================================================================

const MOUTH_EASE = 0.35;
const PUPIL_EASE = 0.08;
const EYE_CLOSE_EASE = 0.55;
const EYE_OPEN_EASE = 0.16;
const GLOW_EASE = 0.12;
const GLOW_IDLE_TARGET = 0.12; // nunca 0 plano: presencia sutil incluso callada

let mouthBandTargets = [0, 0, 0]; // grave (apertura) / media (esquina izq.) / aguda (esquina der.)
let mouthBandCurrent = [0, 0, 0];
let mouthNeedsReset = false; // true tras hablar, hasta que las bandas se asienten en ~0
let talking = false;
let mouthBandTimer = null;

let eyeOpenness = 1; // 0 cerrado, 1 abierto
let eyeOpennessTarget = 1;

let glowIntensity = GLOW_IDLE_TARGET;
let glowTarget = GLOW_IDLE_TARGET;

/** Boca al hablar: forma CERRADA (labio superior + inferior). Una curva
 * abierta con fill:none no se lee como boca abriendo/cerrando (bug real:
 * "solo parecen líneas moviéndose"); con apertura 0 los labios colapsan en
 * una línea = boca cerrada de verdad. */
function mouthTalkPath(bands) {
  const cx = 500;
  const midY = 460;
  const w = 190;
  const [low, mid, high] = bands;
  const openAmount = low * 95;
  const leftY = midY - mid * 18;
  const rightY = midY - high * 18;
  const topY = midY - openAmount * 0.55;
  const bottomY = midY + openAmount * 0.85;
  return (
    `M ${cx - w} ${leftY} ` +
    `Q ${cx} ${topY} ${cx + w} ${rightY} ` +
    `Q ${cx} ${bottomY} ${cx - w} ${leftY} Z`
  );
}

/** Re-sortea las bandas a ritmo variable (70–140ms) mientras `talking`. La
 * banda grave usa el rango completo 0–1 (un piso >0 nunca dejaba cerrar). */
function randomizeMouthBandTargets() {
  mouthBandTargets = [Math.random(), Math.random() * 0.6, Math.random() * 0.6];
  if (!talking) return;
  mouthBandTimer = setTimeout(randomizeMouthBandTargets, 70 + Math.random() * 70);
}

function startTalkingAnimation() {
  talking = true;
  mouthNeedsReset = true;
  clearTimeout(mouthBandTimer);
  randomizeMouthBandTargets();
}

function stopTalkingAnimation() {
  talking = false;
  clearTimeout(mouthBandTimer);
  mouthBandTargets = [0, 0, 0]; // el loop las relaja solas hacia 0
}

/** onboundary real de SpeechSynthesisUtterance: el único timing de habla genuino. */
function mouthBoundaryBurst() {
  mouthBandTargets[0] = Math.min(1, mouthBandTargets[0] + 0.25);
}

function currentBaseMouthShape() {
  const cfg = EXPRESSIONS[currentExpression];
  return cfg ? cfg.mouth : "flat";
}

let lastTalkGlow = "";

function livelinessFrame() {
  requestAnimationFrame(livelinessFrame);
  // El estado de voz lo lee también el orbe de la consola: siempre corre.
  updateStatusIndicator();
  // La cara no se ve con la consola abierta: no tiene caso moverla.
  if (document.documentElement.dataset.view === "dashboard") return;

  // --- Boca ---
  let bandsMoving = false;
  for (let i = 0; i < 3; i++) {
    const delta = mouthBandTargets[i] - mouthBandCurrent[i];
    mouthBandCurrent[i] += delta * MOUTH_EASE;
    if (Math.abs(delta) > 0.004) bandsMoving = true;
  }
  if (talking || bandsMoving) {
    mouthEl.setAttribute("d", mouthTalkPath(mouthBandCurrent));
    mouthNeedsReset = true;
  } else if (mouthNeedsReset) {
    mouthEl.setAttribute("d", mouthPath(currentBaseMouthShape()));
    mouthNeedsReset = false;
  }

  const avgBand = (mouthBandCurrent[0] + mouthBandCurrent[1] + mouthBandCurrent[2]) / 3;

  // --- Parpadeo (easing asimétrico) + pupilas ---
  const cfg = EXPRESSIONS[currentExpression];
  const blinkFactor = eyeOpennessTarget < eyeOpenness ? EYE_CLOSE_EASE : EYE_OPEN_EASE;
  eyeOpenness += (eyeOpennessTarget - eyeOpenness) * blinkFactor;
  const scaleY = Math.max(0.05, eyeOpenness).toFixed(3);
  // 'pensando' gira por CSS: su transform no se toca aquí.
  if (!cfg?.eyeSpin) {
    // Al hablar, un leve scaleX atado a la energía de la boca.
    const talkScaleX = talking ? (1 - avgBand * 0.05).toFixed(3) : 1;
    eyeLeftEl.style.transform = `scaleY(${scaleY}) scaleX(${talkScaleX})`;
    eyeRightEl.style.transform = `scaleY(${scaleY}) scaleX(${talkScaleX})`;
  }
  const pupilShouldShow = !!cfg?.pupil && eyeOpenness > 0.35;
  pupilLeftEl.classList.toggle("face-pupil--visible", pupilShouldShow);
  pupilRightEl.classList.toggle("face-pupil--visible", pupilShouldShow);

  pupilCurrent.dx += (gazeBaseOffset.dx + gazeDriftOffset.dx - pupilCurrent.dx) * PUPIL_EASE;
  pupilCurrent.dy += (gazeBaseOffset.dy + gazeDriftOffset.dy - pupilCurrent.dy) * PUPIL_EASE;
  pupilLeftEl.setAttribute("cx", EYE_L.x + pupilCurrent.dx);
  pupilLeftEl.setAttribute("cy", EYE_L.y + pupilCurrent.dy);
  pupilRightEl.setAttribute("cx", EYE_R.x + pupilCurrent.dx);
  pupilRightEl.setAttribute("cy", EYE_R.y + pupilCurrent.dy);

  // --- Glow dinámico (ver .face-eye/.face-mouth en lumina.css) ---
  glowTarget = talking ? Math.min(1, avgBand * 1.3) : GLOW_IDLE_TARGET;
  glowIntensity += (glowTarget - glowIntensity) * GLOW_EASE;
  // En el <svg> y no en #face-screen: una custom property en un ancestro
  // recalcula el estilo de TODOS sus descendientes (subtítulos, chip...).
  const talkGlow = glowIntensity.toFixed(3);
  if (talkGlow !== lastTalkGlow) {
    lastTalkGlow = talkGlow;
    faceSvg.style.setProperty("--talk-glow", talkGlow);
  }
}
requestAnimationFrame(livelinessFrame);

/** Barras del waveform en "respondiendo": nada de análisis de audio real (ver
 * HONESTIDAD arriba, mismo motivo que la boca) — cada barra reusa la energía
 * de banda ya calculada para la boca (mouthBandCurrent) más una fase propia
 * por índice, así se ve reactiva sin inventar una segunda fuente de "verdad". */
function updateWaveformSpeaking() {
  const now = performance.now();
  waveformBarEls.forEach((bar, i) => {
    const band = mouthBandCurrent[i % 3];
    const phase = Math.sin(now / 110 + i * 0.8) * 0.12;
    const h = Math.min(1, Math.max(0.15, band * 0.9 + phase + 0.15));
    bar.style.setProperty("--waveform-h", h.toFixed(2));
  });
}

// Se lee cada frame (en vez de engancharse a cada cambio de estado) para no
// poder "olvidar" un call site; solo toca el DOM cuando el texto/estado cambia.
// data-voice en <html> lo leen el orbe de la consola y la barra de estado.
const voiceStateTextEl = document.getElementById("voiceStateText");
// Motivo corto por el que no se puede escuchar (micrófono bloqueado, etc.).
let voiceProblem = null;
let lastStatusLabel = null;
let lastWaveState = null;
function updateStatusIndicator() {
  let label = "Dormida";
  let waveState = "idle";
  if (mode === "conversation") {
    label = voiceProblem || "En espera";
    if (talking) {
      label = "Hablando";
      waveState = "speaking";
    } else if (searchModeActive) {
      label = "Buscando con la cámara";
      waveState = "processing";
    } else if (conversationSubState === "thinking") {
      label = "Pensando…";
      waveState = "processing";
    } else if (conversationSubState === "listening" && currentExpression === "escuchando") {
      // Solo si la expresión es realmente 'escuchando': restingExpression()
      // ya comprueba que el reconocimiento exista; sin eso mentiría.
      label = "Te escucho";
      waveState = "listening";
    }
  }

  if (waveState !== lastWaveState) {
    lastWaveState = waveState;
    waveformEl.className = `waveform waveform--${waveState}`;
    document.documentElement.dataset.voice = waveState;
  }
  if (talking) updateWaveformSpeaking();

  if (label === lastStatusLabel) return;
  lastStatusLabel = label;
  voiceStateTextEl.textContent = label;
  statusIndicatorEl.textContent = label;
}

/** Cambia la expresión de la cara. Válidas: las llaves de EXPRESSIONS. */
function setFaceExpression(name) {
  const cfg = EXPRESSIONS[name];
  if (!cfg) {
    console.warn(`Lumina: expresión desconocida "${name}". Válidas: ${Object.keys(EXPRESSIONS).join(", ")}`);
    return;
  }
  const isChange = name !== currentExpression;
  currentExpression = name;
  applyExpression(cfg);
  if (cfg.idleBlink) {
    scheduleNextBlink();
  } else {
    clearTimeout(idleBlinkTimer);
  }
  if (isChange) playExpressionSound(name);
}
window.setFaceExpression = setFaceExpression;

/** 'feliz' sostenida en Modo Presentación; 'escuchando' si hay reconocimiento
 * real disponible; 'inactivo' si no (más honesto que mentir). */
function restingExpression() {
  if (presentationModeActive) return "feliz";
  return voiceAvailable ? "escuchando" : "inactivo";
}

// ============================================================================
// Efectos de sonido — Web Audio API, osciladores generados en vivo.
// ============================================================================

let audioCtx = null;

function getAudioContext() {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  if (!audioCtx) audioCtx = new Ctx();
  // Los navegadores crean el contexto "suspended" hasta el primer gesto real
  // del usuario: antes de eso no suena, es la política estándar de autoplay.
  if (audioCtx.state === "suspended") audioCtx.resume().catch(() => {});
  return audioCtx;
}

/** Tono simple de freqStart a freqEnd, con caída de volumen para no "tronar". */
function playTone({ freqStart, freqEnd = freqStart, duration = 0.15, gain = 0.06 }) {
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const osc = ctx.createOscillator();
    const gainNode = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(freqStart, ctx.currentTime);
    if (freqEnd !== freqStart) {
      osc.frequency.exponentialRampToValueAtTime(freqEnd, ctx.currentTime + duration);
    }
    gainNode.gain.setValueAtTime(gain, ctx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
    osc.connect(gainNode).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  } catch (err) {
    console.warn("Lumina: no se pudo reproducir sonido.", err);
  }
}

// Un tono por categoría, no uno por cada expresión.
const EXPRESSION_SOUND_CATEGORY = {
  inactivo: "neutral",
  neutral: "neutral",
  feliz: "positive",
  confundido: "neutral",
  sorprendido: "neutral",
  pensando: "neutral",
  triste: "negative",
  error: "negative",
  escuchando: "neutral",
  activando: "startup",
};

function playExpressionSound(name) {
  switch (EXPRESSION_SOUND_CATEGORY[name]) {
    case "positive":
      playTone({ freqStart: 480, freqEnd: 760, duration: 0.18 });
      break;
    case "negative":
      playTone({ freqStart: 480, freqEnd: 260, duration: 0.22 });
      break;
    case "startup": // dos notas ascendentes rápidas: "encendiendo"
      playTone({ freqStart: 392, freqEnd: 523, duration: 0.14, gain: 0.07 });
      setTimeout(() => playTone({ freqStart: 523, freqEnd: 784, duration: 0.18, gain: 0.07 }), 130);
      break;
    case "neutral":
    default:
      playTone({ freqStart: 420, duration: 0.08, gain: 0.04 });
      break;
  }
}

// ============================================================================
// Pantalla de espera (arranque) — negra hasta oír "Lumina" o usar el botón
// invisible de la esquina superior izquierda.
// ============================================================================

const bootScreenEl = document.getElementById("boot-screen");
const bootFlashEl = document.getElementById("boot-flash");
const bootHiddenBtn = document.getElementById("boot-hidden-btn");

let awakened = false; // evita encender dos veces

function enterConversationMode() {
  mode = "conversation";
  conversationSubState = "listening";
  setFaceExpression(restingExpression());
}

/** Destello + encendido progresivo; reutiliza 'activando' (que ya trae su
 * sonido de encendido). */
function wake() {
  if (awakened) return;
  awakened = true;
  bootFlashEl.classList.add("boot-flash--active");
  setTimeout(() => {
    setFaceExpression("activando");
    bootScreenEl.classList.add("boot-screen--hidden");
    bootScreenEl.inert = true;
  }, 150);
  setTimeout(() => {
    bootFlashEl.classList.remove("boot-flash--active");
    enterConversationMode();
  }, 950);
}

bootHiddenBtn.addEventListener("click", wake);

// ============================================================================
// Modo Conversación — LLM (POST ASK_URL) + síntesis de voz
// ============================================================================

// Heurística simple por palabras clave (no análisis de sentimiento real) para
// elegir con qué expresión reacciona Lumina a su propia respuesta. "No sé" es
// honestidad, no un fallo: se lee 'confundido', distinto de una disculpa real
// ('triste').
const UNCERTAIN_PATTERN =
  /\b(no s[ée]|no tengo (esa|esta|la) informaci[oó]n|no tengo acceso|no estoy segur[oa]|no puedo (recordar|asegurar|confirmar)|no tengo certeza|no lo s[ée] (con exactitud|con certeza))\b/i;
const APOLOGETIC_PATTERN =
  /\b(lo siento|disculpa|perd[oó]n|desafortunadamente|lamentablemente|qu[eé] pena|me entristece|triste)\b/i;
const POSITIVE_PATTERN =
  /\b(genial|excelente|perfecto|claro que s[ií]|con gusto|encantad[oa]|me encant\w*|feliz|content[oa]|alegre|entusiasmad[oa]|emocionad[oa]|maravillos[oa]|fant[aá]stic[oa]|incre[ií]ble|qu[eé] alegr[ií]a|orgullos[oa])\b/i;

/** Gana la categoría cuya ÚLTIMA coincidencia aparece más tarde en el texto: el
 * tono con que termina la respuesta es el más representativo. (Bug real: con
 * "la primera categoría gana", "Me encanta ayudar, aunque no estoy segura"
 * quedaba en 'confundido' por el orden de revisión y no por la idea principal.) */
function chooseExpressionForAnswer(text) {
  if (presentationModeActive) return "feliz";

  const categories = [
    { name: "confundido", pattern: UNCERTAIN_PATTERN },
    { name: "triste", pattern: APOLOGETIC_PATTERN },
    { name: "feliz", pattern: POSITIVE_PATTERN },
  ];

  let winnerName = null;
  let winnerLastIndex = -1;
  for (const { name, pattern } of categories) {
    const globalPattern = new RegExp(pattern.source, "gi");
    let match;
    let lastIndex = -1;
    while ((match = globalPattern.exec(text)) !== null) lastIndex = match.index;
    if (lastIndex > winnerLastIndex) {
      winnerLastIndex = lastIndex;
      winnerName = name;
    }
  }
  return winnerName || "neutral";
}

// ---- Selección de voz --------------------------------------------------------
// La Web Speech API no permite clonar la voz de un personaje ni dice el género
// de una voz: se infiere por el nombre propio con una lista CURADA A MANO (no
// exhaustiva) de nombres masculinos de las voces "Online (Natural)" de
// Microsoft en es-MX/es-ES/es-US/es-AR.
let selectedVoice = null;
let voicesLoggedOnce = false;

const MALE_VOICE_NAME_HINTS = ["jorge", "alvaro", "álvaro", "alonso", "tomas", "tomás"];
// Voz LOCAL (no de red) confirmada masculina: "Microsoft Raul - Spanish (Mexico)".
const MALE_VOICE_LOCAL_HINTS = ["raul", "raúl"];

/** Mejor voz en español disponible. Primero se decide el IDIOMA (es-MX si hay,
 * cualquier otro es-* de respaldo — bug real: sin distinguir país eligió una
 * es-AR teniendo una es-MX), y dentro del grupo esta cascada:
 *  1. override manual por localStorage (máxima prioridad, cualquier idioma)
 *  2. voz de red con nombre masculino conocido
 *  3. voz local con nombre masculino conocido
 *  4. cualquier voz de red
 *  5. cualquier voz que no sea "compact" (más robótica)
 *  6. la primera que haya */
function pickBestSpanishVoice(voices) {
  const spanishVoices = voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith("es"));
  if (spanishVoices.length === 0) return null;

  const isCompact = (v) => /compact/i.test(v.name);
  const isNetwork = (v) => v.localService === false;
  const matchesAny = (v, hints) => hints.some((hint) => v.name.toLowerCase().includes(hint));

  let override = "";
  try {
    override = (localStorage.getItem(VOICE_OVERRIDE_KEY) || "").trim().toLowerCase();
  } catch {
    // localStorage no disponible (ej. modo privado estricto)
  }
  if (override) {
    const forced = spanishVoices.find((v) => v.name.toLowerCase().includes(override));
    if (forced) return forced;
    console.warn(`Lumina: ${VOICE_OVERRIDE_KEY}="${override}" no coincide con ninguna voz en español — se ignora.`);
  }

  const pickFromCandidates = (candidates) =>
    candidates.find((v) => isNetwork(v) && matchesAny(v, MALE_VOICE_NAME_HINTS) && !isCompact(v)) ||
    candidates.find((v) => matchesAny(v, MALE_VOICE_LOCAL_HINTS) && !isCompact(v)) ||
    candidates.find((v) => isNetwork(v) && !isCompact(v)) ||
    candidates.find((v) => !isCompact(v)) ||
    candidates[0];

  const mexicanVoices = spanishVoices.filter((v) => v.lang.toLowerCase() === "es-mx");
  return pickFromCandidates(mexicanVoices.length > 0 ? mexicanVoices : spanishVoices);
}

/** getVoices() puede devolver [] al principio: la lista real llega async vía
 * "voiceschanged", por eso se llama al cargar y en cada disparo del evento. */
function refreshSelectedVoice() {
  if (!("speechSynthesis" in window)) return;
  const voices = window.speechSynthesis.getVoices();
  if (voices.length === 0) return;

  if (!voicesLoggedOnce) {
    voicesLoggedOnce = true;
    // Solo las de español: Edge/Chrome traen 500+ y la consola trunca ese array.
    const spanish = voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith("es"));
    console.log(
      `Lumina · voces en español disponibles (${spanish.length}):`,
      spanish.map((v) => `${v.name} (${v.lang})${v.localService === false ? " · red" : ""}`),
    );
  }

  const best = pickBestSpanishVoice(voices);
  if (best && best !== selectedVoice) {
    selectedVoice = best;
    const isMexican = best.lang.toLowerCase() === "es-mx";
    console.log(
      `Lumina · voz elegida: ${best.name} (${best.lang})` +
        (isMexican ? " · es-MX" : " · NO es es-MX, ningún es-MX disponible — respaldo de otro país"),
    );
  }
}

if ("speechSynthesis" in window) {
  refreshSelectedVoice();
  window.speechSynthesis.onvoiceschanged = refreshSelectedVoice;
}

// ============================================================================
// Subtítulos: lo que oyó Lumina (sans, tenue) y lo que responde (serif),
// revelado palabra por palabra al ritmo de la voz. El ritmo real viene de
// onboundary (voz del navegador) o del avance del audio (ElevenLabs); si el
// motor no manda nada, una estimación de ~13 caracteres/s lo cubre. El
// avance nunca retrocede: se toma el máximo de las dos fuentes.
// ============================================================================

const captionUserEl = document.getElementById("captionUser");
const captionLuminaEl = document.getElementById("captionLumina");
const CAPTION_LINGER_MS = 8000;
const ESTIMATED_CHARS_PER_SECOND = 13;
let captionFadeTimer = null;

function scheduleCaptionFade() {
  clearTimeout(captionFadeTimer);
  captionFadeTimer = setTimeout(() => {
    captionUserEl.classList.add("is-faded");
    captionLuminaEl.classList.add("is-faded");
  }, CAPTION_LINGER_MS);
}

function showUserCaption(text, interim = false) {
  clearTimeout(captionFadeTimer);
  captionUserEl.textContent = `«${text}»`;
  captionUserEl.classList.toggle("is-interim", interim);
  captionUserEl.classList.remove("is-faded");
  if (!interim) {
    captionLuminaEl.classList.add("is-faded");
    scheduleCaptionFade(); // si nadie contesta (comando silencioso), igual se va
  }
}

/** Pinta `text` como palabras apagadas y devuelve con qué encenderlas. */
function showLuminaCaption(text) {
  clearTimeout(captionFadeTimer);
  captionLuminaEl.textContent = "";
  const words = [];
  for (const match of text.matchAll(/\S+/g)) {
    const span = document.createElement("span");
    span.className = "caption-word";
    span.textContent = match[0];
    captionLuminaEl.append(span, " ");
    words.push({ span, start: match.index });
  }
  captionLuminaEl.classList.remove("is-faded");

  let revealedUpTo = 0;
  let startedAt = 0;
  let estimateTimer = null;
  const markUpTo = (charIndex) => {
    if (charIndex <= revealedUpTo) return;
    revealedUpTo = charIndex;
    for (const word of words) if (word.start < charIndex) word.span.classList.add("is-spoken");
  };
  return {
    start() {
      startedAt = performance.now();
      clearInterval(estimateTimer);
      estimateTimer = setInterval(() => {
        markUpTo(((performance.now() - startedAt) / 1000) * ESTIMATED_CHARS_PER_SECOND);
      }, 120);
    },
    markUpTo,
    finish() {
      clearInterval(estimateTimer);
      markUpTo(Infinity);
      scheduleCaptionFade();
    },
  };
}

// true tras un 501 de SPEAK_URL (ElevenLabs no configurado): no tiene sentido
// reintentar el fetch en cada respuesta si ya sabemos que no hay API key.
let elevenLabsUnavailable = false;

/** Dice `text` en voz alta. Intenta ElevenLabs primero (voz real, ver
 * lumina.py); si no está configurado o falla, cae a speechSynthesis. */
async function speak(text, { onend } = {}) {
  // Micrófono completamente apagado mientras habla, sea cual sea la voz
  // (ver pauseRecognitionForSpeech). Se hace una sola vez aquí, no en cada
  // función de voz, para no pisarse entre el intento y el fallback.
  pauseRecognitionForSpeech();
  const caption = showLuminaCaption(text);
  const done = () => {
    caption.finish();
    if (onend) onend();
  };
  if (!elevenLabsUnavailable && (await speakWithElevenLabs(text, { onend: done, caption }))) return;
  speakWithBrowserVoice(text, { onend: done, caption });
}

/** true si reprodujo audio real de ElevenLabs (ya llamó a onend por su cuenta);
 * false si hay que caer a speechSynthesis (no configurado, cuota agotada, red
 * caída, etc. — nunca lanza, solo devuelve false). */
async function speakWithElevenLabs(text, { onend, caption }) {
  let response;
  try {
    response = await fetch(SPEAK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch (err) {
    console.warn("Lumina: no se pudo contactar ElevenLabs.", err);
    return false;
  }
  if (response.status === 501) {
    elevenLabsUnavailable = true;
    return false;
  }
  if (!response.ok) {
    console.warn(`Lumina: ElevenLabs no pudo generar la voz (${response.status}).`);
    return false;
  }

  const url = URL.createObjectURL(await response.blob());
  const audio = new Audio(url);
  const finish = () => {
    URL.revokeObjectURL(url);
    stopTalkingAnimation();
    resumeRecognitionAfterSpeech();
    if (onend) onend();
  };
  audio.onplay = () => {
    startTalkingAnimation();
    caption.start();
  };
  audio.ontimeupdate = () => {
    if (audio.duration) caption.markUpTo((text.length * audio.currentTime) / audio.duration);
  };
  audio.onended = finish;
  audio.onerror = (event) => {
    console.warn("Lumina: error reproduciendo audio de ElevenLabs.", event);
    finish();
  };

  try {
    await audio.play();
  } catch (err) {
    console.warn("Lumina: no se pudo reproducir el audio de ElevenLabs.", err);
    URL.revokeObjectURL(url);
    return false;
  }
  return true;
}

/** Fallback: la voz sintetizada del navegador (comportamiento original). */
function speakWithBrowserVoice(text, { onend, caption } = {}) {
  if (!("speechSynthesis" in window)) {
    console.warn("Lumina: speechSynthesis no está disponible en este navegador.");
    if (onend) onend();
    return;
  }

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "es-MX";
  utterance.pitch = 1.1; // cálido, no robótico
  utterance.rate = 1.0;
  if (selectedVoice) utterance.voice = selectedVoice;

  utterance.onstart = () => {
    startTalkingAnimation();
    caption?.start();
  };
  // Algunos navegadores/voces nunca disparan onboundary: la boca sigue viva
  // y los subtítulos siguen con la estimación de ritmo.
  utterance.onboundary = (event) => {
    mouthBoundaryBurst();
    caption?.markUpTo(event.charIndex + (event.charLength || 1));
  };

  const finish = () => {
    stopTalkingAnimation();
    resumeRecognitionAfterSpeech();
    if (onend) onend();
  };
  utterance.onend = finish;
  utterance.onerror = (event) => {
    console.warn("Lumina: error de síntesis de voz.", event);
    finish();
  };

  window.speechSynthesis.cancel(); // corta cualquier habla anterior
  window.speechSynthesis.speak(utterance);
}

/** Le manda `question` a Lumina y dice la respuesta. Solo debe llamarse con
 * conversationSubState === 'listening' (handleVoiceCommand ya lo garantiza). */
async function askLumina(question) {
  conversationSubState = "thinking";
  setFaceExpression("pensando");

  let answer;
  try {
    const response = await fetch(ASK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail || `Lumina no pudo responder (error ${response.status}).`);
    }
    answer = (await response.json()).answer;
  } catch (err) {
    console.warn("Lumina: no se pudo consultar a Lumina.", err);
    conversationSubState = "listening";
    setFaceExpression("error");
    setTimeout(() => {
      if (conversationSubState === "listening") setFaceExpression(restingExpression());
    }, 2000);
    return;
  }

  console.log(`Lumina · responde: "${answer}"`);
  setFaceExpression(chooseExpressionForAnswer(answer));
  conversationSubState = "speaking";
  speak(answer, {
    onend: () => {
      conversationSubState = "listening";
      setFaceExpression(restingExpression());
    },
  });
}

// ============================================================================
// Comandos de voz — Web Speech API nativa. Diagnóstico por consola + un punto
// de estado mínimo (la vista de reposo debe sentirse como presencia, no como
// una interfaz con indicadores).
// ============================================================================

const voiceStatusDotEl = document.getElementById("voice-status-dot");

// Qué frase es qué comando lo decide routeVoiceCommand() en
// voice-commands.js (probado con frases reales de Chrome y Edge en
// voice_commands_check.js). Aquí solo se ejecuta.

/** Comando de voz "busca X": cambia a la vista del dashboard (transición ya
 * definida en app-shell.css) y delega la búsqueda real en dashboard.js —
 * este archivo no sabe nada de cámaras, solo de voz y de la cara. */
function startVoiceObjectSearch(objectName) {
  if (typeof window.switchToView === "function") window.switchToView("dashboard");
  if (typeof window.startCameraObjectSearch === "function") {
    window.startCameraObjectSearch(objectName);
  } else {
    console.warn("Lumina: dashboard.js no está cargado, no puedo buscar con la cámara.");
  }
}

// ---------------------------------------------------------------------------
// La casa por voz (secciones 3.4 y 3.5). Salir/llegar es más que armar o
// desarmar: el backend (/home/depart, /home/arrive) revisa riesgos, lee los
// recordatorios del momento y la agenda, y devuelve la frase ya armada —
// aquí solo se dice. Proteger/desproteger sin salir es otro comando aparte.
// ---------------------------------------------------------------------------

const TRIGGER_SPEECH = {
  leave: "Listo. Te lo recuerdo cuando salgas.",
  arrive: "Listo. Te lo recuerdo cuando llegues.",
  any: "Listo, lo anoté.",
};

/** ["a", "b", "c"] -> "a, b y c" (mismo criterio que briefing.join_es). */
function joinEs(items) {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

/** POST con JSON; lanza con el `detail` del backend si responde error. */
async function postJson(url, payload) {
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

function toast(options) {
  if (typeof window.showToast === "function") window.showToast(options);
}

function refreshHomeViews() {
  if (typeof window.refreshHome === "function") window.refreshHome();
}

async function handleProtectionVoice(armed) {
  try {
    await postJson("/home/protection", { armed });
    refreshHomeViews();
    speak(armed ? "Protección activada. Si se abre la puerta, te aviso." : "Protección desactivada.");
  } catch (err) {
    console.error("Lumina: no se pudo cambiar la protección.", err);
    speak("No pude cambiar la protección ahora mismo.");
  }
}

async function handleLeavingHome() {
  try {
    const body = await postJson("/home/depart");
    refreshHomeViews();
    toast({ title: "Protección activada", body: "Te aviso si se abre la puerta mientras no estás.", tone: "ok" });
    if (body.situation.severity !== "normal" && typeof window.switchToView === "function") {
      window.switchToView("dashboard");
    }
    speak(body.speech);
  } catch (err) {
    console.error("Lumina: no se pudo registrar la salida.", err);
    speak("No pude revisar la casa antes de que salgas.");
  }
}

async function handleArrivingHome() {
  try {
    const body = await postJson("/home/arrive");
    refreshHomeViews();
    toast({ title: "Protección desactivada", body: "Qué bueno que llegaste.", tone: "info" });
    speak(body.speech);
  } catch (err) {
    console.error("Lumina: no se pudo registrar la llegada.", err);
    speak("No pude desactivar la protección. Revísalo en la consola.");
  }
}

async function handleHomeStatusQuery() {
  try {
    const { situation, summary } = await fetch("/home/overview?events=1").then((r) => r.json());
    speak(`${summary.headline} ${summary.detail}`);
    if (situation.severity !== "normal" && typeof window.switchToView === "function") {
      window.switchToView("dashboard");
    }
  } catch (err) {
    console.error("Lumina: no se pudo consultar el estado de la casa.", err);
    speak("No pude consultar el estado de la casa ahora mismo.");
  }
}

async function handleAddReminderVoice(text, when) {
  const trigger = !when ? "any" : /salga|salir|vaya/i.test(when) ? "leave" : "arrive";
  try {
    await postJson("/reminders", { text, trigger });
    if (typeof window.refreshReminders === "function") window.refreshReminders();
    toast({ title: "Recordatorio guardado", body: text, tone: "ok" });
    speak(TRIGGER_SPEECH[trigger]);
  } catch (err) {
    console.error("Lumina: no se pudo guardar el recordatorio.", err);
    speak("No pude guardar ese recordatorio.");
  }
}

async function handleListRemindersVoice() {
  try {
    const items = await fetch("/reminders").then((r) => r.json());
    if (items.length === 0) {
      speak("No tienes recordatorios pendientes.");
      return;
    }
    const plural = items.length === 1 ? "un pendiente" : `${items.length} pendientes`;
    speak(`Tienes ${plural}: ${joinEs(items.map((r) => r.text))}.`);
  } catch (err) {
    console.error("Lumina: no se pudieron leer los recordatorios.", err);
    speak("No pude leer tus recordatorios ahora mismo.");
  }
}

async function handleEscalateVoice() {
  try {
    await postJson("/alerts/escalate");
    toast({ title: "Aviso enviado", body: "Le mandé la alerta a tu contacto.", tone: "ok" });
    speak("Listo, le avisé a tu contacto.");
  } catch (err) {
    if (err.status === 409) {
      speak("Ahora no hay ninguna alerta activa. Si es una emergencia, llama al 911.");
    } else {
      console.error("Lumina: no se pudo avisar al contacto.", err);
      speak("No pude avisar a tu contacto. Si es una emergencia, llama al 911.");
    }
  }
}

async function handleCameraToggleVoice(turnOn) {
  try {
    const response = await fetch(turnOn ? "/vision/start" : "/vision/stop", { method: "POST" });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail ?? "la cámara no respondió");
    if (typeof window.setCameraUiFromVoice === "function") window.setCameraUiFromVoice(body.running);
    if (turnOn) window.switchToView?.("dashboard"); // que se vea lo que ve
    speak(turnOn ? "Cámara encendida." : "Cámara apagada.");
  } catch (err) {
    speak(`No pude ${turnOn ? "encender" : "apagar"} la cámara: ${err.message}`);
  }
}

async function handleCalibrateDoorVoice() {
  try {
    const response = await fetch("/vision/calibrate_door", { method: "POST" });
    if (!response.ok) throw new Error("sin señal de cámara");
    speak("Puerta calibrada como cerrada.");
  } catch (err) {
    speak("No pude calibrar la puerta. Enciende la cámara primero.");
  }
}

/** "Lumina, analiza este mensaje: <texto>" (sección 3.9) — nunca afirma que
 * ES una estafa, solo lee las señales que backend/fraud_detector.py
 * encontró, igual que el panel del dashboard. */
async function analyzeMessageByVoice(text) {
  if (typeof window.switchToView === "function") window.switchToView("dashboard");
  try {
    const response = await fetch("/messages/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail ?? "no se pudo analizar");
    if (result.signals_found.length === 0) {
      speak("No encontré señales de riesgo conocidas en ese mensaje. Eso no garantiza que sea seguro.");
    } else {
      const plural = result.signals_found.length === 1 ? "señal" : "señales";
      speak(
        `Encontré ${result.signals_found.length} ${plural} de riesgo: ${result.signals_found.join(", ")}. ` +
          `Nivel de riesgo ${result.risk_level}. Nunca compartas contraseñas ni hagas transferencias por presión.`,
      );
    }
  } catch (err) {
    console.error("Lumina: no se pudo analizar el mensaje.", err);
    speak("No pude analizar ese mensaje ahora mismo.");
  }
}

// ---- Modo búsqueda: mientras la cámara busca algo, Lumina deja de mandar
// CUALQUIER frase al LLM (pedido explícito) — solo sigue oyendo comandos
// propios (buscar otra cosa, cancelar). dashboard.js activa/desactiva esto
// desde runObjectSearch()/pollSearchStatus() vía window.setSearchMode.
let searchModeActive = false;
let lastSearchBusyNoticeAt = 0;
const SEARCH_BUSY_NOTICE_COOLDOWN_MS = 8000;

function setSearchMode(active) {
  searchModeActive = active;
  if (active) {
    setFaceExpression("pensando");
  } else if (conversationSubState === "listening") {
    setFaceExpression(restingExpression());
  }
}
window.setSearchMode = setSearchMode;

function togglePresentationMode() {
  presentationModeActive = !presentationModeActive;
  console.log(`Lumina · modo presentación: ${presentationModeActive ? "activado" : "desactivado"}`);
  if (conversationSubState === "listening") setFaceExpression(restingExpression());
}

// El navegador a veces parte un comando corto ("lumina inicio") en DOS
// resultados finales; evaluados por separado, el fragmento suelto terminaba
// mandándose al LLM como pregunta basura. Se acumulan en un buffer y se evalúa
// el texto combinado tras un breve silencio.
const VOICE_COMMAND_DEBOUNCE_MS = 600;
let pendingTranscriptBuffer = "";
let voiceCommandDebounceTimer = null;

function queueVoiceFragment(transcript) {
  pendingTranscriptBuffer = pendingTranscriptBuffer ? `${pendingTranscriptBuffer} ${transcript}` : transcript;
  clearTimeout(voiceCommandDebounceTimer);
  voiceCommandDebounceTimer = setTimeout(() => {
    const combined = pendingTranscriptBuffer;
    pendingTranscriptBuffer = "";
    console.log(`Lumina · escuchado (${mode}): "${combined}"`);
    handleVoiceCommand(combined);
  }, VOICE_COMMAND_DEBOUNCE_MS);
}

// Bug real: "Lumina, busca mi mochila" a veces llega en DOS resultados
// finales separados (la pausa natural tras la coma alcanza a cortar el
// resultado) — para cuando llega "busca mi mochila" solo, ya no trae
// "lumina" y el comando se le escapaba a askLumina() como pregunta suelta.
// Se mantiene la activación válida un rato corto tras oír "Lumina" para que
// el resto del comando, aunque llegue en otro fragmento, se siga procesando.
const WAKE_WORD_GRACE_MS = 4000;
let lastWakeWordAt = 0;
const FALL_REASK_COOLDOWN_MS = 6000;
let lastFallReaskAt = 0;

/** "Lumina, abre mi calendario": abre Google Calendar (vista de agenda) en su
 * propia pestaña, lleva la consola al panel "Hoy" y te dice qué tienes hoy.
 * Chrome y Edge bloquean ventanas que no abrió un clic; si pasa, queda un
 * aviso con el enlace (un toque sí la abre) — o permite ventanas emergentes
 * para esta página y la voz la abre directo. */
async function handleOpenCalendarVoice() {
  const link = document.getElementById("openCalendarLink");
  const opened = window.open(link.href, link.target);
  window.switchToView?.("dashboard");
  window.spotlightAgenda?.();

  let agenda = "";
  try {
    agenda = (await postJson(ASK_URL, { question: "¿Qué tengo hoy?" })).answer;
  } catch (err) {
    console.warn("Lumina: no se pudo leer la agenda.", err);
  }

  if (opened) {
    speak(`Abrí tu Google Calendar. ${agenda}`.trim());
    return;
  }
  toast({
    title: "Google Calendar",
    body: "Tu navegador bloqueó la ventana que iba a abrir.",
    action: { label: "Abrir Google Calendar", href: link.href, target: link.target },
    duration: 15000,
  });
  speak(`${agenda} Tu navegador no me dejó abrir Google Calendar; toca el aviso en la pantalla.`.trim());
}

/** "Lumina, agenda dentista mañana a las 5": el servidor entiende la fecha.
 * Con el Apps Script configurado queda creado; si no, se abre Google Calendar
 * con el evento ya lleno y solo falta tocar Guardar (ver
 * backend/calendar_writer.py). */
async function handleAddCalendarEventVoice(text) {
  // Google tarda 10-30 s en contestar: se avisa de una vez para que el
  // silencio no parezca que Lumina se trabó.
  speak("Dame un momento, lo estoy agendando.");
  toast({ title: "Agendando en Google Calendar…", body: "Google tarda unos segundos en contestar.", tone: "info" });
  let result;
  try {
    result = await postJson("/calendar/events", { text });
  } catch (err) {
    // 422 trae la frase exacta de qué faltó ("¿Para qué día y hora?...").
    speak(err.status === 422 ? err.message : "No pude agendar eso ahora mismo.");
    return;
  }
  if (result.created) {
    toast({ title: "Agendado en Google Calendar", body: result.event.title, tone: "ok" });
    window.refreshAgenda?.();
    speak(result.speech);
    return;
  }
  if (result.unconfirmed) {
    // Pudo haberse creado: se manda a revisar, nunca a guardar otra vez.
    toast({
      title: "Revisa tu calendario",
      body: `No pude confirmar si ${result.event.title} quedó guardado.`,
      action: { label: "Abrir Google Calendar", href: result.open_url, target: "google-calendar" },
      tone: "warning",
      duration: 20000,
    });
    speak(result.speech);
    return;
  }
  const opened = window.open(result.open_url, "google-calendar");
  if (!opened) {
    toast({
      title: "Falta guardar el evento",
      body: `${result.event.title}: tu navegador bloqueó la ventana.`,
      action: { label: "Abrir y guardar", href: result.open_url, target: "google-calendar" },
      duration: 20000,
    });
  }
  speak(opened ? result.speech : `${result.speech} Toca el aviso en la pantalla para abrirlo.`);
}

/** "Me caí", "auxilio", "necesito ayuda": pedir ayuda no puede depender de
 * que la cámara lo haya visto. Abre la alerta de caída ya marcada como "pidió
 * ayuda" (avisa y llama al contacto) y la pantalla muestra el aviso. */
async function handleHelpNowVoice() {
  if (window.fallAlertState?.active) {
    window.respondToFall?.(false); // ya había alerta: esto es su respuesta
    return;
  }
  setFaceExpression("sorprendido");
  speak("Ya voy. Estoy avisando a tu contacto.");
  try {
    await postJson("/events", { source: "voice", type: "possible_fall", location: "home" });
    await postJson("/vision/fall/confirm", { ok: false });
  } catch (err) {
    console.error("Lumina: no se pudo pedir ayuda.", err);
    speak("No pude avisar a tu contacto. Si puedes, llama al 911.");
  }
  window.refreshHome?.();
}

/** Hora dicha como persona ("Son las 3 y 5 de la tarde."). */
function speakTime() {
  speak(spokenTime(new Date()));
}

function speakDate() {
  const text = typeof window.formatLongDate === "function" ? window.formatLongDate(new Date()) : new Date().toDateString();
  speak(`Hoy es ${text.charAt(0).toLowerCase()}${text.slice(1)}.`);
}

// Nombre del comando (voice-commands.js) -> qué hacer. Agregar un comando =
// una regla allá (con su frase de prueba) + una línea aquí.
const COMMAND_HANDLERS = {
  fraud: ([text]) => analyzeMessageByVoice(text),
  reminderAdd: ([text, when]) => handleAddReminderVoice(text, when),
  reminderList: () => handleListRemindersVoice(),
  search: ([objectName]) => startVoiceObjectSearch(objectName),
  cancelSearch: () => window.cancelCameraObjectSearch?.(),
  protectionOff: () => handleProtectionVoice(false),
  protectionOn: () => handleProtectionVoice(true),
  leave: () => handleLeavingHome(),
  arrive: () => handleArrivingHome(),
  status: () => handleHomeStatusQuery(),
  cameraOn: () => handleCameraToggleVoice(true),
  cameraOff: () => handleCameraToggleVoice(false),
  calibrate: () => handleCalibrateDoorVoice(),
  escalate: () => handleEscalateVoice(),
  helpNow: () => handleHelpNowVoice(),
  openCalendar: () => handleOpenCalendarVoice(),
  calendarAdd: ([text]) => handleAddCalendarEventVoice(text),
  time: () => speakTime(),
  date: () => speakDate(),
  showHouse: () => {
    window.switchToView?.("dashboard");
    speak("Aquí está la casa.");
  },
  showFace: () => window.switchToView?.("lumina"),
  presentation: () => togglePresentationMode(),
  expression: ([name]) => setFaceExpression(name),
};

/** Un solo lugar decide qué hacer con una frase YA FINALIZADA.
 *
 * Los comandos de la casa NO exigen decir "Lumina": en modo conversación
 * Lumina ya está escuchando todo (cualquier otra frase va al LLM), y exigirla
 * hacía que un "Lumina" mal transcrito ("Lúmina", "la mina") mandara el
 * comando al LLM, que contestaba cualquier cosa. Solo los comandos de prueba
 * de la cara ("feliz", "error") la piden, porque son palabras comunes. */
function handleVoiceCommand(transcript) {
  // Alerta de caída abierta: lo primero es la respuesta a "¿Estás bien?", sin
  // exigir "Lumina" y aunque esté en pantalla de espera. Si no se entiende,
  // se vuelve a preguntar (nunca se manda al LLM mientras corre la cuenta).
  if (window.fallAlertState?.active) {
    const reply = routeFallReply(transcript);
    if (reply) {
      console.log(`Lumina · respuesta a la caída: ${reply}`);
      window.respondToFall?.(reply === "ok");
      return;
    }
    if (window.fallAlertState.status === "asking") {
      const now = Date.now();
      if (now - lastFallReaskAt > FALL_REASK_COOLDOWN_MS) {
        lastFallReaskAt = now;
        speak("No te entendí. ¿Estás bien? Di «estoy bien» o «necesito ayuda».");
      }
      return;
    }
  }

  // Pantalla de espera: lo único que se procesa es la palabra de encendido.
  if (mode === "boot") {
    if (hasWakeWord(transcript)) wake();
    return;
  }

  if (hasWakeWord(transcript)) {
    lastWakeWordAt = Date.now();
    // Solo "Lumina": es la pausa antes del comando. Un tono corto dice "te
    // oí" (como el de Alexa) y se espera el resto.
    if (isOnlyWakeWord(transcript)) {
      playTone({ freqStart: 660, freqEnd: 880, duration: 0.12, gain: 0.05 });
      return;
    }
  }

  const command = routeVoiceCommand(transcript, {
    searching: searchModeActive,
    wake: Date.now() - lastWakeWordAt < WAKE_WORD_GRACE_MS,
  });
  if (command) {
    console.log(`Lumina · comando: ${command.name}`, command.args);
    COMMAND_HANDLERS[command.name](command.args);
    return;
  }

  // Modo búsqueda activo: solo pasan comandos (ya evaluados arriba). Todo lo
  // demás se ignora con un aviso breve, sin repetirlo si sigues hablando.
  if (searchModeActive) {
    const now = Date.now();
    if (now - lastSearchBusyNoticeAt > SEARCH_BUSY_NOTICE_COOLDOWN_MS) {
      lastSearchBusyNoticeAt = now;
      speak("Sigo buscando. Dime «cancela» si quieres que pare.");
    }
    return;
  }

  if (conversationSubState !== "listening") return; // ya está pensando/hablando
  askLumina(transcript);
}

// Mensajes en español para SpeechRecognitionErrorEvent.error.
const VOICE_ERROR_MESSAGES = {
  "no-speech": "no se detectó voz (normal en reconocimiento continuo; reintenta solo)",
  "audio-capture": "no se encontró ningún micrófono disponible",
  "not-allowed": "permiso de micrófono denegado",
  "service-not-allowed": "el navegador bloqueó el servicio de reconocimiento de voz",
  network: "error de red con el servicio de reconocimiento de voz",
  aborted: "reconocimiento cancelado",
  "language-not-supported": "el idioma configurado (es-MX) no está soportado",
  "bad-grammar": "error de gramática de reconocimiento",
};

function setListeningIndicator(active) {
  voiceStatusDotEl.classList.toggle("voice-status-dot--listening", active);
  voiceStatusDotEl.title = active
    ? "Reconocimiento de voz: escuchando activamente"
    : "Reconocimiento de voz: inactivo";
  console.log(active ? "Lumina · reconocimiento: escuchando" : "Lumina · reconocimiento: inactivo");
}

const VOICE_PROBLEM_LABEL = {
  "permiso de micrófono denegado": "Micrófono bloqueado",
  "micrófono denegado": "Micrófono bloqueado",
  "el navegador bloqueó el servicio de reconocimiento de voz": "Voz bloqueada",
  "este navegador no soporta reconocimiento de voz": "Sin reconocimiento de voz",
};

function setAttentionIndicator(message) {
  voiceStatusDotEl.classList.remove("voice-status-dot--listening");
  voiceStatusDotEl.classList.add("voice-status-dot--attention");
  voiceStatusDotEl.title = `Voz: ${message}`;
  voiceProblem = VOICE_PROBLEM_LABEL[message] || "Sin micrófono";
}

async function logMicPermission() {
  if (!navigator.permissions || !navigator.permissions.query) {
    console.log("Lumina · micrófono: este navegador no permite verificar el permiso.");
    return;
  }
  try {
    const status = await navigator.permissions.query({ name: "microphone" });
    const labels = { granted: "permitido", denied: "denegado", prompt: "pendiente de confirmar" };
    const logState = (s) => {
      console.log(`Lumina · micrófono: ${labels[s] || s}`);
      if (s === "denied") setAttentionIndicator("micrófono denegado");
    };
    logState(status.state);
    status.onchange = () => logState(status.state); // si lo cambian con la pestaña abierta
  } catch {
    console.log("Lumina · micrófono: este navegador no permite verificar el permiso.");
  }
}

logMicPermission();

if (SpeechRecognitionImpl) {
  recognition = new SpeechRecognitionImpl();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "es-MX";

  recognition.addEventListener("start", () => setListeningIndicator(true));

  // event.results acumula TODO lo dicho desde que arrancó la sesión (minutos):
  // unirlo mezclaba comandos dichos en momentos distintos. resultIndex marca
  // lo NUEVO, y solo se toman resultados YA FINALIZADOS (isFinal).
  // Los parciales solo alimentan el subtítulo (se ve que Lumina está oyendo
  // mientras hablas); nunca se procesan como comando.
  recognition.addEventListener("result", (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      const raw = result[0].transcript.trim();
      if (!result.isFinal) {
        interim += `${raw} `;
        continue;
      }
      // Sin pasar a minúsculas: routeVoiceCommand ya ignora mayúsculas, y así
      // un evento o recordatorio conserva nombres ("Junta con Ana").
      const transcript = raw;
      if (!transcript) continue;
      if (mode === "conversation") showUserCaption(raw);
      queueVoiceFragment(transcript);
    }
    if (interim.trim() && mode === "conversation") showUserCaption(interim.trim(), true);
  });

  recognition.addEventListener("error", (event) => {
    const message = VOICE_ERROR_MESSAGES[event.error] || event.error;
    console.warn(`Lumina · error de voz: ${message}`);

    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      shouldKeepListening = false;
      voiceAvailable = false;
      setAttentionIndicator(message);
      if (mode === "conversation" && conversationSubState === "listening") {
        setFaceExpression(restingExpression());
      }
    }
    // los demás ("no-speech", "network") son transitorios: "end" reinicia solo.
  });

  // El reconocimiento "continuo" igual se corta tras un silencio: hay que
  // reiniciarlo a mano. Si el corte fue A PROPÓSITO (Lumina hablando), lo
  // reinicia resumeRecognitionAfterSpeech(), nunca antes.
  recognition.addEventListener("end", () => {
    setListeningIndicator(false);
    if (recognitionPausedForSpeech || !shouldKeepListening) return;
    try {
      recognition.start();
    } catch (err) {
      console.warn(`Lumina · no se pudo reiniciar el reconocimiento: ${err.message}`);
    }
  });

  try {
    recognition.start();
  } catch (err) {
    setAttentionIndicator("no se pudo iniciar el reconocimiento");
    console.warn("Lumina · no se pudo iniciar el reconocimiento de voz.", err);
  }
} else {
  setAttentionIndicator("este navegador no soporta reconocimiento de voz");
  console.warn("Lumina · este navegador no soporta Web Speech API. Toca la pantalla para despertarla.");
}

// ============================================================================
// Estado inicial y parallax
// ============================================================================

setFaceExpression(restingExpression());
scheduleNextGazeDrift();

// Parallax de mouse sobre #face-stage (ver lumina.css); se omite con
// "menos movimiento" o sin puntero fino (las pantallas táctiles no generan
// mousemove real).
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if (!reduceMotion && window.matchMedia("(pointer: fine)").matches) {
  window.addEventListener("mousemove", (event) => {
    const relX = (event.clientX / window.innerWidth - 0.5) * 2; // -1..1
    const relY = (event.clientY / window.innerHeight - 0.5) * 2;
    faceStageEl.style.setProperty("--parallax-x", relX.toFixed(3));
    faceStageEl.style.setProperty("--parallax-y", relY.toFixed(3));
  });
}

// ============================================================================
// Sugerencias rotativas bajo la casa: enseñan qué se le puede pedir sin un
// manual. Solo corren con la cara a la vista y la pestaña visible.
// ============================================================================

const HINTS = [
  "Di «Lumina, ¿cómo está la casa?»",
  "Di «Lumina, busca mi celular»",
  "Di «Lumina, salgo de casa»",
  "Di «Lumina, recuérdame sacar la basura cuando salga»",
  "Di «Lumina, ¿qué tengo hoy?»",
  "Di «Lumina, activa la protección»",
  "Di «Lumina, analiza este mensaje: …»",
  "Di «Lumina, ¿dónde dejé mi mochila?»",
];
const HINT_INTERVAL_MS = 7000;
const hintEl = document.getElementById("hint");
let hintIndex = 0;

setInterval(() => {
  if (document.hidden || document.documentElement.dataset.view !== "lumina") return;
  hintIndex = (hintIndex + 1) % HINTS.length;
  if (reduceMotion) {
    hintEl.textContent = HINTS[hintIndex];
    return;
  }
  hintEl.classList.add("is-swapping");
  setTimeout(() => {
    hintEl.textContent = HINTS[hintIndex];
    hintEl.classList.remove("is-swapping");
  }, 300);
}, HINT_INTERVAL_MS);
