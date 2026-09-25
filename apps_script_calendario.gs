/**
 * Lumina -> Google Calendar. Se pega en https://script.google.com (Nuevo
 * proyecto), con la sesión de la cuenta dueña del calendario, y se publica
 * como "Aplicación web". Ver backend/calendar_writer.py y el README.
 *
 * TOKEN: la clave secreta de google_calendar_webapp.json. Sin ella nadie más
 * puede crear eventos aunque conozca la URL.
 */
const TOKEN = "PEGA_AQUI_EL_TOKEN";

// Calendario donde se agregan los eventos: el principal de la cuenta. Para
// otro, cambia esta línea por:
//   CalendarApp.getCalendarsByName("Mi Rutina :D")[0]
function calendario() {
  return CalendarApp.getDefaultCalendar();
}

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    if (data.token !== TOKEN) return respuesta({ ok: false, error: "token incorrecto" });

    // Google a veces tarda o falla al ENTREGAR la respuesta aunque el evento
    // sí se creó; Lumina entonces reintenta con el mismo requestId. El candado
    // y la caché hacen que el reintento devuelva el evento ya creado en vez de
    // crear otro igual.
    const candado = LockService.getScriptLock();
    candado.waitLock(30000);
    try {
      const cache = CacheService.getScriptCache();
      const previo = data.requestId && cache.get(data.requestId);
      if (previo) return respuesta(JSON.parse(previo));

      const inicio = new Date(data.start);
      const fin = new Date(data.end);
      // Sin esto, una fecha inválida crea el evento el 1 de enero de 1970.
      if (!data.title || isNaN(inicio) || (!data.allDay && isNaN(fin))) {
        return respuesta({ ok: false, error: "faltan título o fechas válidas" });
      }
      const cal = calendario();
      const evento = data.allDay ? cal.createAllDayEvent(data.title, inicio) : cal.createEvent(data.title, inicio, fin);
      const resultado = { ok: true, id: evento.getId() };
      if (data.requestId) cache.put(data.requestId, JSON.stringify(resultado), 21600); // 6 horas
      return respuesta(resultado);
    } finally {
      candado.releaseLock();
    }
  } catch (err) {
    return respuesta({ ok: false, error: String(err) });
  }
}

function respuesta(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
