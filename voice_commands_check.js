// node voice_commands_check.js — lo corre test_voice_commands.py (pytest).
// Frases tal como las transcriben Chrome (minúsculas, sin puntuación) y Edge
// (mayúsculas, ¿?, comas y punto final). Si una falla, ese comando de voz
// "no funciona" para quien lo diga así.
const assert = require("node:assert/strict");
const { routeVoiceCommand, routeFallReply, hasWakeWord, isOnlyWakeWord, spokenTime } = require("./web/voice-commands.js");

const route = (text, ctx) => {
  const result = routeVoiceCommand(text, ctx);
  return result ? [result.name, ...result.args.filter((a) => a !== undefined)] : null;
};

const CASES = [
  // salir / llegar
  ["Lumina, salgo de casa.", ["leave"]],
  ["salgo de casa", ["leave"]],
  ["Bueno, ya me voy.", ["leave"]],
  ["voy de salida", ["leave"]],
  ["Ya nos vamos, Lumina.", ["leave"]],
  ["Lumina, ya llegué.", ["arrive"]],
  ["ya llegue", ["arrive"]],
  ["Ya volví.", ["arrive"]],
  ["Ya estoy aquí.", ["arrive"]],
  ["llegué a casa", ["arrive"]],
  ["Ya estoy de vuelta", ["arrive"]],
  // protección
  ["Lumina, activa la protección.", ["protectionOn"]],
  ["activa el modo protección", ["protectionOn"]],
  ["Arma la casa.", ["protectionOn"]],
  ["Lumina, desactiva la protección.", ["protectionOff"]],
  ["desarma la casa", ["protectionOff"]],
  ["Quita la protección, por favor.", ["protectionOff"]],
  // estado
  ["¿Cómo está la casa?", ["status"]],
  ["lumina como esta la casa", ["status"]],
  ["¿Está todo bien?", ["status"]],
  ["¿Hay algún riesgo?", ["status"]],
  // búsqueda
  ["Lumina, busca mi mochila.", ["search", "mochila"]],
  ["busca el celular", ["search", "celular"]],
  ["Lumina, ¿puedes buscar mi celular?", ["search", "celular"]],
  ["Búscame la taza, por favor.", ["search", "taza"]],
  ["Oye Lumina, encuentra mis tijeras", ["search", "tijeras"]],
  ["Cancela.", ["cancelSearch"], { searching: true }],
  ["Lumina, ya no busques", ["cancelSearch"], { searching: true }],
  ["Párale.", ["cancelSearch"], { searching: true }],
  // recordatorios (conservan acentos)
  ["Lumina, recuérdame sacar la basura cuando salga.", ["reminderAdd", "sacar la basura", "cuando salga"]],
  ["recuérdame llamar a mamá cuando llegue", ["reminderAdd", "llamar a mamá", "cuando llegue"]],
  ["Recuérdame comprar leche.", ["reminderAdd", "comprar leche"]],
  ["Recuérdame buscar las llaves al salir", ["reminderAdd", "buscar las llaves", "al salir"]],
  ["¿Qué pendientes tengo?", ["reminderList"]],
  ["lumina mis recordatorios", ["reminderList"]],
  // anti-extorsión (conserva el mensaje con su puntuación interna)
  [
    "Lumina, analiza este mensaje: deposita ya o le pasa algo a tu hijo.",
    ["fraud", "deposita ya o le pasa algo a tu hijo"],
  ],
  ["revisa si esto es una estafa soy del banco dame tu nip", ["fraud", "soy del banco dame tu nip"]],
  // cámara
  ["Lumina, enciende la cámara.", ["cameraOn"]],
  ["prende la camara", ["cameraOn"]],
  ["Apaga la cámara.", ["cameraOff"]],
  ["Calibra la puerta.", ["calibrate"]],
  // ayuda
  ["Lumina, avisa a mi contacto.", ["escalate"]],
  ["Avísale a mi contacto", ["escalate"]],
  ["pide ayuda", ["helpNow"]],
  // emergencia dicha en voz (sin que la cámara haya visto nada)
  ["¡Ayuda! Me caí", ["helpNow"]],
  ["Lumina, me caí", ["helpNow"]],
  ["Auxilio", ["helpNow"]],
  ["No me puedo levantar", ["helpNow"]],
  ["Necesito ayuda", ["helpNow"]],
  ["Ayuda, ayuda", ["helpNow"]],
  ["Necesito ayuda con la tarea", null],
  ["¿Me ayudas a buscar una receta?", null],
  // Google Calendar
  ["Lumina, abre Google Calendar.", ["openCalendar"]],
  ["abre mi agenda", ["openCalendar"]],
  ["Muéstrame mi calendario.", ["openCalendar"]],
  ["Ábreme el calendario de Google", ["openCalendar"]],
  ["Lumina, quiero ver mi agenda", ["openCalendar"]],
  ["Enséñame la agenda.", ["openCalendar"]],
  ["Oye, ¿puedes abrir mi calendario?", ["openCalendar"]],
  // agregar eventos (el texto sigue con su fecha; la entiende el servidor)
  ["Lumina, agenda dentista mañana a las 5.", ["calendarAdd", "dentista mañana a las 5"]],
  ["Agéndame una cita con el doctor el lunes a las 10", ["calendarAdd", "una cita con el doctor el lunes a las 10"]],
  ["Crea un evento: examen de cálculo el viernes a las 8", ["calendarAdd", "un evento: examen de cálculo el viernes a las 8"]],
  ["Pon una reunión con Ana hoy a las 6", ["calendarAdd", "una reunión con Ana hoy a las 6"]],
  ["Añade pagar la luz a mi calendario mañana", ["calendarAdd", "pagar la luz a mi calendario mañana"]],
  ["Lumina, agenda de mañana", null], // es pregunta, no orden
  ["Pon la protección", ["protectionOn"]],
  // hora y fecha
  ["¿Qué hora es?", ["time"]],
  ["Lumina, ¿qué día es hoy?", ["date"]],
  // vistas
  ["Muéstrame la casa.", ["showHouse"]],
  ["Lumina, enséñame la cámara", ["showHouse"]],
  ["Lumina, vuelve.", ["showFace"]],
  ["regresa", ["showFace"]],
  // cara: solo con "Lumina"
  ["Lumina, feliz.", ["expression", "feliz"]],
  ["Lumina confundida", ["expression", "confundido"]],
  ["Lumina, presentación.", ["presentation"]],
  ["triste", ["expression", "triste"], { wake: true }],

  // NO son comandos: van al LLM (o se ignoran en modo búsqueda)
  ["¿Qué tengo hoy?", null],
  ["¿Qué tengo en mi agenda hoy?", null], // pregunta: la contesta el servidor, no abre nada
  ["¿Dónde dejé mi mochila?", null],
  ["Me voy a dormir.", null],
  ["Estoy muy feliz hoy", null],
  ["¿A qué hora regresa mi mamá?", null],
  ["no sé dónde busca la gente trabajo", null],
  ["para mañana tengo examen", null, { searching: true }],
  ["cancela", null], // sin búsqueda en curso no hay nada que cancelar
];

let failures = 0;
for (const [text, expected, ctx] of CASES) {
  const got = route(text, ctx);
  try {
    assert.deepEqual(got, expected);
  } catch {
    failures++;
    console.log(`FALLA  ${JSON.stringify(text)}  esperaba ${JSON.stringify(expected)}  obtuvo ${JSON.stringify(got)}`);
  }
}

// Respuestas a "¿Estás bien?" (solo se consultan con una alerta de caída abierta)
const FALL_CASES = [
  ["Estoy bien.", "ok"],
  ["Sí, estoy bien", "ok"],
  ["sí", "ok"],
  ["Lumina, estoy bien", "ok"],
  ["No me caí.", "ok"],
  ["No me pasó nada", "ok"],
  ["Falsa alarma", "ok"],
  ["Todo bien, tranquila", "ok"],
  ["Ya me levanté", "ok"],
  ["No, no te preocupes", "ok"],
  ["No estoy bien.", "help"],
  ["Necesito ayuda", "help"],
  ["¡Ayuda!", "help"],
  ["Me caí", "help"],
  ["Me duele la pierna", "help"],
  ["No me puedo levantar", "help"],
  ["Auxilio", "help"],
  ["no", "help"],
  ["Llama a mi hija", "help"],
  ["¿Qué hora es?", null],
  ["mmm", null],
];
for (const [text, expected] of FALL_CASES) {
  const got = routeFallReply(text);
  if (got !== expected) {
    failures++;
    console.log(`FALLA (caída)  ${JSON.stringify(text)}  esperaba ${expected}  obtuvo ${got}`);
  }
}

assert.ok(hasWakeWord("Lúmina, busca mi mochila"));
assert.ok(hasWakeWord("la mina"));
assert.ok(isOnlyWakeWord("Lumina."));
assert.ok(!isOnlyWakeWord("Lumina, busca mi mochila"));
assert.equal(spokenTime(new Date(2026, 8, 25, 15, 5)), "Son las 3 y 5 de la tarde.");
assert.equal(spokenTime(new Date(2026, 8, 25, 13, 0)), "Es la 1 en punto de la tarde.");
assert.equal(spokenTime(new Date(2026, 8, 25, 9, 30)), "Son las 9 y media de la mañana.");

if (failures) {
  console.log(`${failures} de ${CASES.length} frases fallaron`);
  process.exit(1);
}
console.log(`ok: ${CASES.length} frases`);
