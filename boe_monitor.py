import feedparser
import requests
import json
import os
import unicodedata
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

# RSS oficial del BOE específico de OPOSICIONES
RSS_URL = "https://www.boe.es/rss/canal_per.php?c=140&l=p"

SEEN_FILE = "seen_items.json"

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


# ============================================================
# OBJETIVOS PRIORITARIOS
# ============================================================

TARGET_BODIES = [
    "cuerpo superior de sistemas y tecnologias de la informacion",
    "cuerpo de gestion de sistemas e informatica",
    "cuerpo de tecnicos auxiliares de informatica",

    "escala de cientificos superiores de la defensa",

    "tecnicos superiores especializados de organismos publicos de investigacion",
    "tecnicos especializados de organismos publicos de investigacion",
    "tecnologos de organismos publicos de investigacion",
    "personal cientifico titular",
]


# Organismos especialmente interesantes
PRIORITY_INSTITUTIONS = [
    "instituto nacional de tecnica aeroespacial",
    "inta",
    "cetedex",
    "ministerio de defensa",
    "organismos publicos de investigacion",
    "opi",
]


# Campos profesionales compatibles con Ingeniería Informática
TECH_TERMS = [
    "ingenieria informatica",
    "ingeniero informatico",
    "informatica",
    "tecnologias de la informacion",
    "sistemas de informacion",
    "inteligencia artificial",
    "aprendizaje automatico",
    "machine learning",
    "ciencia de datos",
    "analisis de datos",
    "big data",
    "ciberseguridad",
    "seguridad informatica",
    "software",
    "computacion",
    "arquitectura de computadores",
    "redes de comunicaciones",
    "telecomunicaciones",
    "robotica",
    "sistemas autonomos",
    "vision artificial",
    "procesamiento de lenguaje natural",
]


# Publicaciones que nos interesan durante un proceso selectivo
PROCESS_TERMS = [
    "convoca proceso selectivo",
    "proceso selectivo",
    "acceso libre",
    "ingreso libre",
    "relacion provisional",
    "relacion definitiva",
    "admitidos",
    "excluidos",
    "primer ejercicio",
    "segundo ejercicio",
    "tercer ejercicio",
    "fecha de celebracion",
    "fecha de examen",
    "calificacion",
    "calificaciones",
    "puntuacion",
    "puntuaciones",
    "resultados",
    "aspirantes que han superado",
    "plantilla correctora",
    "tribunal",
    "cronograma",
]


# Zonas geográficas prioritarias.
# NO actúan como filtro; aumentan la prioridad.
PRIORITY_LOCATIONS = [
    "andalucia",
    "jaen",
    "sevilla",
    "granada",
    "malaga",
    "cordoba",
    "cadiz",
    "huelva",
    "almeria",
    "madrid",
]


# Filtro adicional contra publicaciones que claramente
# no sean empleo público.
NEGATIVE_TERMS = [
    "licitacion",
    "contratacion del sector publico",
    "contrato de obras",
    "contrato de suministro",
    "planta fotovoltaica",
    "planta de almacenamiento",
    "autorizacion administrativa",
    "impacto ambiental",
    "expropiacion",
    "informacion publica",
]


# ============================================================
# UTILIDADES
# ============================================================

def normalize(text):
    """Minúsculas y eliminación de tildes."""
    text = text.lower()

    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def find_matches(text, terms):
    return [term for term in terms if term in text]


def load_seen():
    path = Path(SEEN_FILE)

    if path.exists():
        try:
            return set(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return set()

    return set()


def save_seen(seen):
    Path(SEEN_FILE).write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ============================================================
# CLASIFICACIÓN
# ============================================================

def classify(text):

    body_matches = find_matches(text, TARGET_BODIES)
    institution_matches = find_matches(text, PRIORITY_INSTITUTIONS)
    tech_matches = find_matches(text, TECH_TERMS)
    process_matches = find_matches(text, PROCESS_TERMS)
    location_matches = find_matches(text, PRIORITY_LOCATIONS)
    negative_matches = find_matches(text, NEGATIVE_TERMS)

    score = 0

    # Cuerpo concreto que nos interesa
    if body_matches:
        score += 10

    # Organismo prioritario
    if institution_matches:
        score += 5

    # Perfil tecnológico
    if tech_matches:
        score += 4

    # Publicación relacionada con proceso selectivo
    if process_matches:
        score += 3

    # Andalucía / Madrid
    if location_matches:
        score += 2

    # Algo claramente no relacionado con empleo
    if negative_matches:
        score -= 20

    # --------------------------------------------------------
    # Decisión de relevancia
    # --------------------------------------------------------

    relevant = False

    # Un cuerpo que seguimos explícitamente siempre interesa.
    if body_matches:
        relevant = True

    # Organismo prioritario + proceso/tecnología
    elif institution_matches and (tech_matches or process_matches):
        relevant = True

    # Convocatoria tecnológica aunque sea de otra administración
    elif tech_matches and process_matches:
        relevant = True

    # Si aparecen términos claramente negativos, se descarta
    if negative_matches:
        relevant = False

    return {
        "relevant": relevant,
        "score": score,
        "body": body_matches,
        "institution": institution_matches,
        "tech": tech_matches,
        "process": process_matches,
        "location": location_matches,
    }


def priority_label(result):

    if result["score"] >= 12:
        return "🔴 PRIORIDAD ALTA"

    elif result["score"] >= 8:
        return "🟠 PRIORIDAD MEDIA"

    else:
        return "🟡 POSIBLE INTERÉS"


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": False
        },
        timeout=30
    )

    response.raise_for_status()


# ============================================================
# MONITOR
# ============================================================

def main():
    
    seen = load_seen()

    feed = feedparser.parse(RSS_URL)

    print(f"Publicaciones RSS encontradas: {len(feed.entries)}")

    notifications = 0

    for entry in feed.entries:

        title = entry.get("title", "")
        summary = entry.get("summary", "")
        link = entry.get("link", "")

        text = normalize(f"{title} {summary}")

        result = classify(text)

        if not result["relevant"]:
            continue

        if link in seen:
            continue

        priority = priority_label(result)

        reasons = []

        if result["body"]:
            reasons.append("🎯 Cuerpo prioritario")

        if result["institution"]:
            reasons.append(
                "🏛 Organismo: " +
                ", ".join(result["institution"][:2])
            )

        if result["tech"]:
            reasons.append(
                "💻 Perfil: " +
                ", ".join(result["tech"][:3])
            )

        if result["process"]:
            reasons.append(
                "📋 Tipo: " +
                ", ".join(result["process"][:2])
            )

        if result["location"]:
            reasons.append(
                "📍 Prioridad geográfica: " +
                ", ".join(result["location"])
            )

        message = (
            f"{priority}\n\n"
            f"📢 {title}\n\n"
            + "\n".join(reasons)
            + f"\n\n🔗 {link}"
        )

        send_telegram(message)

        seen.add(link)
        notifications += 1

    save_seen(seen)

    if notifications == 0:
        print("Sin publicaciones relevantes.")

    else:
        print(f"Alertas enviadas: {notifications}")


if __name__ == "__main__":
    main()
