import feedparser
import requests
import json
import os
from pathlib import Path

RSS_URL = "https://www.boe.es/rss/boe.php"

KEYWORDS = [
    "sistemas y tecnologías de la información",
    "gestión de sistemas e informática",
    "técnicos auxiliares de informática",
    "1166",
    "1177",
    "tai",
]

SEEN_FILE = "seen_items.json"

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


def load_seen():
    path = Path(SEEN_FILE)

    if path.exists():
        return set(json.loads(path.read_text(encoding="utf-8")))

    return set()


def save_seen(seen):
    Path(SEEN_FILE).write_text(
        json.dumps(list(seen), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def send_telegram(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=30
    )

    print(response.text)


def main():
    
    seen = load_seen()

    feed = feedparser.parse(RSS_URL)

    new_items = []

    for entry in feed.entries:

        title = entry.title
        summary = entry.get("summary", "")
        link = entry.link

        text = f"{title} {summary}".lower()

        matched = any(
            keyword in text
            for keyword in KEYWORDS
        )

        if matched and link not in seen:

            new_items.append({
                "title": title,
                "link": link
            })

            seen.add(link)

    if new_items:

        for item in new_items:

            message = (
                "🚨 BOE TIC detectado\n\n"
                f"{item['title']}\n\n"
                f"{item['link']}"
            )

            send_telegram(message)

    else:
        print("Sin novedades")
        send_telegram("✅ Monitor ejecutado correctamente")

    save_seen(seen)


if __name__ == "__main__":
    main()
