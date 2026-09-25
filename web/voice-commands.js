/**
 * voice-commands.js — decide QUÉ comando es una frase ya transcrita. Función
 * pura (sin DOM ni red): lumina.js ejecuta el comando y
 * voice_commands_check.js (raíz del repo, lo corre pytest) la prueba con
 * frases tal como las escriben Chrome y Edge.
 *
 * Por qué se "dobla" el texto antes de comparar:
 *  - En JavaScript `\b` solo reconoce [A-Za-z0-9_]: "ya llegué" nunca
 *    coincidía con /ya llegu[eé]\b/ porque la "é" final no cuenta como letra.
 *  - Edge devuelve mayúsculas y puntuación ("¿Cómo está la casa?"); Chrome no.
 * Se pasa todo a minúsculas sin acentos y la puntuación a espacios, con un
 * reemplazo 1 a 1: los índices siguen valiendo para recortar del texto
 * original (con acentos) lo que se va a guardar o decir, como un recordatorio.
 */
(function (root) {
  const FOLD = { á: "a", é: "e", í: "i", ó: "o", ú: "u", ü: "u", ñ: "n" };
  const PUNCTUATION = /[¿?¡!.,;:«»"“”()]/;

  function fold(lower) {
    let out = "";
    for (const ch of lower) out += FOLD[ch] || (PUNCTUATION.test(ch) ? " " : ch);
    return out;
  }

  // Variantes reales de cómo el reconocimiento escribe "Lumina".
  const WAKE = /\b(lumina|luminia|ilumina|alumina|lumi|la mina|lu mina)\b/;

  const EXPRESSION_NAME = {
    feliz: "feliz",
    triste: "triste",
    pensando: "pensando",
    error: "error",
    neutral: "neutral",
    confundido: "confundido",
    confundida: "confundido",
    sorprendido: "sorprendido",
    sorprendida: "sorprendido",
    inactivo: "inactivo",
    inactiva: "inactivo",
    inectivo: "inactivo",
    inectiva: "inactivo",
  };

  // Las órdenes ("busca…", "apaga la cámara") tienen que ir al inicio de la
  // frase, después de lo que la gente suele decir antes; así un "busca" a
  // media plática no dispara nada. Preguntas y avisos ("ya me voy", "¿cómo
  // está la casa?") pueden ir en cualquier parte.
  const LEAD_IN = String.raw`^\s*(?:(?:oye|hey|ey|hola|lumina|luminia|ilumina|alumina|lumi|la\s+mina|lu\s+mina|por\s+favor|puedes|podrias|me\s+puedes|quiero\s+que|y)\s+)*`;

  // En orden: gana el primero que coincide. Lo que lleva texto libre (un
  // mensaje, un recordatorio) va primero, para que "recuérdame buscar las
  // llaves" no se lea como "busca". `wake: true` = solo si se dijo "Lumina"
  // (comandos de prueba de la cara, que usan palabras comunes).
  const COMMANDS = [
    {
      name: "fraud",
      start: true,
      re: /\b(?:analiza|analizar|revisa|revisar)\s+(?:si\s+esto\s+es\s+(?:una\s+)?(?:estafa|fraude|extorsion)|este\s+mensaje|el\s+mensaje)\s+(\S[\s\S]*?)\s*$/d,
    },
    {
      name: "reminderAdd",
      start: true,
      re: /\brecuerda(?:me|nos)\s+(?:que\s+)?(.+?)(?:\s+(cuando\s+salga|al\s+salir|antes\s+de\s+salir|cuando\s+me\s+vaya|cuando\s+llegue|al\s+llegar|al\s+volver|cuando\s+vuelva|cuando\s+regrese))?\s*$/d,
    },
    {
      name: "reminderList",
      re: /\b(?:que\s+(?:recordatorios|pendientes)\s+tengo|mis\s+(?:recordatorios|pendientes)|que\s+tengo\s+pendiente|tengo\s+(?:algun\s+)?pendientes?)\b/d,
    },
    // Agregar a Google Calendar: "agenda X", "crea un evento X", "añade X a mi
    // calendario". "Agenda de mañana" es pregunta (va al LLM), no orden.
    {
      name: "calendarAdd",
      start: true,
      re: /\bagenda(?:me|r)?\s+(?!(?:de|para)\s+(?:hoy|manana)\b)(.+?)\s*$/d,
    },
    {
      name: "calendarAdd",
      start: true,
      re: /\b(?:crea|anade|agrega|pon|apunta|anota)(?:me|r)?\s+((?:un\s+|una\s+)?(?:evento|cita|reunion)\b.*?)\s*$/d,
    },
    {
      name: "calendarAdd",
      start: true,
      re: /\b(?:anade|agrega|pon|apunta|anota)(?:me|r)?\s+(.+?\s+(?:en|a)\s+(?:mi|el|la)\s+(?:calendario|agenda)\b.*?)\s*$/d,
    },
    {
      name: "search",
      start: true,
      re: /\b(?:busca(?:r|me)?|encuentra(?:me)?)\s+(?:a\s+)?(?:mi\s+|mis\s+|el\s+|la\s+|los\s+|las\s+|un\s+|una\s+)?(.+?)(?:\s+por\s+favor)?\s*$/d,
    },
    {
      name: "cancelSearch",
      searching: true,
      re: /\b(?:cancela\w*|detente|parale|ya\s+no\s+busques|deja\s+de\s+buscar|olvidalo)\b/d,
    },
    {
      name: "protectionOff",
      start: true,
      re: /\b(?:(?:desactiva|quita|apaga)r?\s+(?:el\s+|la\s+)?(?:modo\s+(?:de\s+)?)?proteccion|desarmar?\s+la\s+casa)\b/d,
    },
    {
      name: "protectionOn",
      start: true,
      re: /\b(?:(?:activa|pon|prende|enciende)r?\s+(?:el\s+|la\s+)?(?:modo\s+(?:de\s+)?)?proteccion|(?:arma|protege|cuida)r?\s+la\s+casa)\b/d,
    },
    {
      name: "leave",
      re: /\b(?:salgo\s+de\s+(?:la\s+)?casa|ya\s+salgo|voy\s+de\s+salida|ya\s+me\s+voy|me\s+voy\s+de\s+(?:la\s+)?casa|me\s+voy\s+a\s+(?:salir|ir)|ya\s+nos\s+vamos|nos\s+vamos)\b/d,
    },
    {
      name: "arrive",
      re: /\b(?:llegue\s+a\s+(?:la\s+)?casa|ya\s+llegue|ya\s+llegamos|ya\s+estoy\s+(?:en\s+casa|aqui|de\s+vuelta)|estoy\s+en\s+casa|ya\s+volvi|ya\s+regrese|(?:volvi|regrese)\s+a\s+casa)\b/d,
    },
    {
      name: "status",
      re: /\b(?:como\s+(?:esta|va|anda)\s+(?:la\s+)?casa|hay\s+algun\s+(?:riesgo|problema)|esta\s+todo\s+bien|todo\s+bien\s+en\s+(?:la\s+)?casa|estado\s+de\s+la\s+casa|que\s+(?:pasa|hay)\s+en\s+(?:la\s+)?casa|revisa\s+la\s+casa)\b/d,
    },
    { name: "cameraOn", start: true, re: /\b(?:enciende|prende|activa)r?\s+(?:la\s+)?camara\b/d },
    { name: "cameraOff", start: true, re: /\b(?:apaga|desactiva|cierra)r?\s+(?:la\s+)?camara\b/d },
    { name: "calibrate", start: true, re: /\bcalibrar?\s+(?:la\s+)?puerta\b/d },
    // Emergencia dicha en voz: funciona aunque la cámara no haya visto nada.
    // "Necesito ayuda" solo si es toda la frase ("…con la tarea" no lo es).
    {
      name: "helpNow",
      re: /\b(?:auxilio|socorro|me\s+cai|me\s+desmaye|no\s+me\s+puedo\s+levantar|pide\s+ayuda|llama\s+a\s+(?:emergencias|una\s+ambulancia))\b|^\s*(?:(?:lumina|oye|por\s+favor)\s+)*(?:ayuda|ayudame|necesito\s+ayuda)(?:\s+(?:ayuda|por\s+favor))*\s*$/d,
    },
    {
      name: "escalate",
      start: true,
      re: /\b(?:(?:avisa|llama|marca)(?:le)?\s+a\s+mi\s+contacto|manda(?:le)?\s+(?:un\s+|el\s+|la\s+)?(?:aviso|mensaje|alerta)\s+a\s+mi\s+contacto|manda\s+la\s+alerta)\b/d,
    },
    // Antes que showHouse: "abre" y "muéstrame" también abren la consola.
    {
      name: "openCalendar",
      start: true,
      re: /\b(?:abre(?:me)?|abrir|muestra(?:me)?|ensena(?:me)?|quiero\s+ver|pon(?:me)?)\s+(?:mi\s+|el\s+|la\s+|tu\s+)?(?:(?:google|gugl)\s+calendar\w*|calendar\w*(?:\s+de\s+google)?|agenda)\b/d,
    },
    { name: "time", re: /\b(?:que\s+hora\s+es|me\s+dices\s+la\s+hora|dime\s+la\s+hora)\b/d },
    { name: "date", re: /\b(?:que\s+(?:dia|fecha)\s+es\s+hoy|a\s+que\s+(?:dia|fecha)\s+estamos|que\s+dia\s+es)\b/d },
    {
      name: "showHouse",
      start: true,
      re: /\b(?:muestra(?:me)?|ensena(?:me)?|abre|quiero\s+ver)\s+(?:la\s+|el\s+)?(?:casa|consola|panel|dashboard|tablero|camara)\b/d,
    },
    // Al final de la frase: "Lumina, vuelve" sí; "¿a qué hora regresa mi mamá?" no.
    { name: "showFace", re: /(?:^|\s)(?:vuelve|regresa|muestra\s+tu\s+cara|cierra\s+la\s+consola|ven\s+aca)\s*$/d },
    { name: "presentation", wake: true, re: /\b(?:presentacion|presentate)\b/d },
    {
      name: "expression",
      wake: true,
      re: /\b(feliz|triste|pensando|error|neutral|confundid[oa]|sorprendid[oa]|inactiv[oa]|inectiv[oa])\b/d,
    },
  ];

  for (const command of COMMANDS) {
    if (command.start) command.re = new RegExp(LEAD_IN + command.re.source, "d");
  }

  // `original` conserva mayúsculas ("Reunión con Ana"); en español
  // toLowerCase() no cambia la longitud, así que los índices valen igual.
  function prepare(text) {
    const original = String(text).normalize("NFC");
    return { original, folded: fold(original.toLowerCase()) };
  }

  function hasWakeWord(text) {
    return WAKE.test(prepare(text).folded);
  }

  /** "Lumina" sola (o casi): es la pausa antes del comando, no una pregunta. */
  function isOnlyWakeWord(text) {
    return prepare(text).folded.replace(WAKE, " ").trim().length < 3;
  }

  /**
   * @param {string} text  frase transcrita
   * @param {{searching?: boolean, wake?: boolean}} ctx
   *   searching: hay una búsqueda con la cámara en curso
   *   wake: se dijo "Lumina" hace poco (en otro fragmento)
   * @returns {{name: string, args: string[]} | null}
   */
  function routeVoiceCommand(text, { searching = false, wake = false } = {}) {
    const { original, folded } = prepare(text);
    const heardWake = wake || WAKE.test(folded);
    for (const command of COMMANDS) {
      if (command.searching && !searching) continue;
      if (command.wake && !heardWake) continue;
      const match = command.re.exec(folded);
      if (!match) continue;
      // Los argumentos se recortan del texto original: conservan acentos.
      const args = [];
      for (let i = 1; i < match.length; i++) {
        const span = match.indices[i];
        args.push(span ? original.slice(span[0], span[1]).trim() : undefined);
      }
      if (command.name === "expression") args[0] = EXPRESSION_NAME[match[1]];
      if (args[0] === "") continue;
      return { name: command.name, args };
    }
    return null;
  }

  // Respuesta a "¿Estás bien?" tras una posible caída. Solo se usa mientras
  // hay alerta (fuera de ella, "estoy bien" es plática normal). En orden: las
  // frases con "no" que dicen lo contrario de lo que parece van primero
  // ("no me caí" = bien; "no estoy bien" = ayuda). Un "no" suelto pide ayuda:
  // ante la duda, avisar es lo seguro.
  const FALL_REPLIES = [
    ["help", /\b(no\s+estoy\s+bien|no\s+me\s+puedo\s+(levantar|mover|parar)|no\s+puedo\s+(levantarme|moverme|pararme))\b/],
    ["ok", /\b(no\s+me\s+(cai|paso\s+nada|lastime)|no\s+pasa\s+nada|no\s+fue\s+nada|no\s+te\s+preocupes|no\s+hace\s+falta)\b/],
    ["help", /\b(ayuda|ayudame|auxilio|socorro|necesito\s+ayuda|me\s+cai|me\s+lastime|me\s+duele|me\s+pegue|llama(le)?\s+a|avisa(le)?\s+a|estoy\s+mal)\b/],
    ["ok", /\b(estoy\s+(bien|ok|okay)|todo\s+bien|todo\s+esta\s+bien|falsa\s+alarma|tranquila|tranquilo|ya\s+me\s+levante|si\s+estoy|sigo\s+bien|estoy\s+perfect[oa])\b/],
    ["ok", /^\s*(?:lumina\s+)?(si|sip|claro|ok|okay|bien)\s*$/],
    ["help", /^\s*(?:lumina\s+)?no\s*$/],
  ];

  /** "ok" | "help" | null (no entendió: Lumina vuelve a preguntar). */
  function routeFallReply(text) {
    const { folded } = prepare(text);
    for (const [answer, re] of FALL_REPLIES) if (re.test(folded)) return answer;
    return null;
  }

  /** 15:05 -> "Son las 3 y 5 de la tarde." (así lo dice una persona). */
  function spokenTime(date) {
    const hours = date.getHours();
    const minutes = date.getMinutes();
    const h12 = hours % 12 || 12;
    const period =
      hours < 6 ? "de la madrugada" : hours < 12 ? "de la mañana" : hours < 19 ? "de la tarde" : "de la noche";
    const minuteText = minutes === 0 ? "en punto" : minutes === 30 ? "y media" : `y ${minutes}`;
    return `${h12 === 1 ? "Es la" : "Son las"} ${h12} ${minuteText} ${period}.`;
  }

  const api = { routeVoiceCommand, routeFallReply, hasWakeWord, isOnlyWakeWord, spokenTime };
  Object.assign(root, api);
  if (typeof module !== "undefined") module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
