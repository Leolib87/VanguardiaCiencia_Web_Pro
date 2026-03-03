import feedparser
import json
import os
import re
from pathlib import Path

# Configuración de múltiples fuentes
RSS_FEEDS = [
    "https://www.nature.com/nature.rss",
    "https://www.sciencenews.org/feed"
]
BANDEJA_DIR = Path("C:/Users/leoli/OneDrive/Desktop/VanguardiaCiencia_Web/bot/bandeja_de_entrada")

def clean_filename(text):
    """Convierte un título en un nombre de archivo seguro."""
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)[:60]

def ejecutar_radar():
    print(f"📡 Radar v3.0: Escaneando fuentes científicas...")
    
    count = 0
    for rss_url in RSS_FEEDS:
        print(f"🔍 Revisando: {rss_url}")
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            print(f"⚠️ No se obtuvieron datos de {rss_url}")
            continue

        # Buscamos noticias en cada feed
        for entry in feed.entries[:15]:
            filename = f"{clean_filename(entry.title)}.json"
            filepath = BANDEJA_DIR / filename
            
            if not filepath.exists():
                data = {
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.summary,
                    "source": "Nature" if "nature.com" in rss_url else "ScienceNews"
                }
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                count += 1
                if count >= 20: break 
        if count >= 20: break
    
    print(f"🏁 Radar finalizado. {count} noticias nuevas añadidas a la bandeja.")

if __name__ == "__main__":
    ejecutar_radar()
