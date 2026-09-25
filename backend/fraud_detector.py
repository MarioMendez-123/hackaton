"""Protección ante posibles extorsiones/fraudes (sección 3.9).

Asistente de PREVENCIÓN, no detector infalible — regla explícita del doc
maestro: "el sistema debe evitar afirmar como hecho que un mensaje es una
extorsión". Por eso `analyze()` nunca dice "esto ES una estafa": reporta qué
señales lingüísticas de riesgo encontró y lo deja como indicio, siempre con
la misma nota de precaución.
"""

import re

# ponytail: listas de frases a mano, pensadas para las extorsiones telefónicas
# y por WhatsApp más comunes en México; se amplían agregando frases aquí.
_SIGNALS: list[tuple[str, re.Pattern]] = [
    (
        "urgencia extrema",
        re.compile(
            r"\b(urgente|inmediatamente|de inmediato|ahora mismo|ahorita mismo|en este momento|hoy mismo|"
            r"cuanto antes|[uú]ltima oportunidad|antes de que sea tarde|"
            r"(deposit|pag|transfier|mand|env[ií])\w* ya|"
            r"tienes \d+ (minutos|horas))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "solicitud de dinero o datos financieros",
        re.compile(
            r"\b(transfi[ei]r\w*|transferencia|deposit\w*|dep[oó]sito|env[ií]a (el )?dinero|manda (el )?dinero|"
            r"oxxo|recargas?|rescate|cobro de piso|tarjeta de cr[eé]dito|n[uú]mero de cuenta|"
            r"c[oó]digo de verificaci[oó]n|clave de tu tarjeta|nip)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "amenaza",
        re.compile(
            r"\b(te tenemos vigilad[oa]|sabemos d[oó]nde vives|(le|te|les) (va a |van a )?pas(a|ar) algo|"
            r"tenemos a tu|secuestrad[oa]s?|lo vamos a lastimar|hacer(le|te) da[ñn]o|matar|"
            r"c[aá]rtel|consecuencias|denunciad[oa]|embargo)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "presión para actuar en secreto",
        re.compile(
            r"\b(no le digas a nadie|no cuelgues|mant[eé]nte en l[ií]nea|no avises a nadie|no le avises|"
            r"no llames a la polic[ií]a|es confidencial)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "supuesta emergencia de un familiar",
        re.compile(
            r"\b(tu (hij[oa]|mam[aá]|pap[aá]|espos[oa]|herman[oa]|niet[oa]|familiar) "
            r"(tuvo un accidente|est[aá] detenid[oa]|est[aá] en problemas|est[aá] con nosotros)|"
            r"soy tu (hij[oa]|sobrin[oa]|niet[oa])|adivina qui[eé]n (soy|habla)|sabes qui[eé]n habla)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "posible suplantación de identidad",
        re.compile(
            r"\b(soy (de|del)|hablo (de|del)|departamento de)\b.{0,30}\b(banco|gobierno|polic[ií]a|hacienda|soporte t[eé]cnico)\b",
            re.IGNORECASE,
        ),
    ),
]

_CAUTION_NOTE = (
    "Es un indicio automático por palabras clave, no una conclusión. "
    "No compartas contraseñas ni códigos, y no transfieras dinero con prisa: "
    "antes, llama tú a la institución o a la persona por el número que ya conoces."
)


def analyze(message: str) -> dict:
    """Nunca afirma que `message` ES fraude — solo qué señales encontró."""
    signals_found = [name for name, pattern in _SIGNALS if pattern.search(message)]
    if len(signals_found) >= 3:
        risk_level = "alto"
    elif signals_found:
        risk_level = "medio"
    else:
        risk_level = "bajo"

    return {"signals_found": signals_found, "risk_level": risk_level, "note": _CAUTION_NOTE}
