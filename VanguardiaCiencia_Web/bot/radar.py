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
    return re.sub(r'[-\s]+', '_', text)[:60]

def ejecutar_radar():
    print(f"📡 Radar v2.0: Escaneando {RSS_URL}...")
    feed = feedparser.parse(RSS_URL)
    
    if not feed.entries:
        print("❌ Error de conexión con Nature.")
        return

    count = 0
    # Escaneamos las primeras 30 entradas para encontrar 20 nuevas
    for entry in feed.entries[:30]:
        filename = f"{clean_filename(entry.title)}.json"
        filepath = BANDEJA_DIR / filename
        
        if not filepath.exists():
            data = {
                "title": entry.title,
                "link": entry.link,
                "summary": entry.summary
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            count += 1
            if count >= 20: break # Límite de carga por radar
    
    print(f"🏁 Radar finalizado. {count} noticias añadidas a la bandeja.")

if __name__ == "__main__":
    ejecutar_radar()
