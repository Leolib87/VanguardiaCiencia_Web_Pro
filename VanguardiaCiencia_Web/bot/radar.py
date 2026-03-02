import feedparser
import json
import os
import re
from pathlib import Path

# Configuración
RSS_URL = "https://www.nature.com/nature.rss"
BANDEJA_DIR = Path("C:/Users/leoli/OneDrive/Desktop/VanguardiaCiencia_Web/bot/bandeja_de_entrada")

def clean_filename(text):
    """Convierte un título en un nombre de archivo seguro."""
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)[:50]

def ejecutar_radar():
    print(f"📡 Iniciando Radar en {RSS_URL}...")
    feed = feedparser.parse(RSS_URL)
    
    if not feed.entries:
        print("❌ No se pudieron obtener noticias de Nature.")
        return

    count = 0
    for entry in feed.entries[:10]:
        filename = f"{clean_filename(entry.title)}.json"
        filepath = BANDEJA_DIR / filename
        
        # Solo guardar si no existe ya
        if not filepath.exists():
            data = {
                "title": entry.title,
                "link": entry.link,
                "summary": entry.summary,
                "processed": False
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"✅ Noticia guardada: {entry.title[:50]}...")
            count += 1
    
    print(f"🏁 Radar finalizado. {count} nuevas noticias en la bandeja.")

if __name__ == "__main__":
    ejecutar_radar()
